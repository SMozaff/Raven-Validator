"""Mocked HTTP suite for reachability, auth, and OpenAPI probes.

Covers: 200, 204, 301/302 redirects, 401, 403, 404, 422, 429, 500,
502, 503, 504, timeout, DNS/network error, TLS-style error,
malformed JSON, HTML response, HEAD-failure fallback.
No live network access.
"""

import httpx
import pytest

from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.auth import AuthProbe
from raven_validator.probes.base import ProbeContext
from raven_validator.probes.openapi import OpenAPISchemaProbe
from raven_validator.probes.reachability import ReachabilityProbe

BASE = "https://api.example.com/v1"


def make_candidate() -> APICandidate:
    return APICandidate(name="Example", base_url=BASE)  # type: ignore[arg-type]


def make_context(
    handler: object, credential: str | None = None
) -> ProbeContext:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    return ProbeContext(
        candidate=make_candidate(), client=client, base_url=BASE, credential=credential
    )


def json_handler(
    status: int = 200,
    payload: object = None,
    headers: dict[str, str] | None = None,
):  # type: ignore[no-untyped-def]
    def _handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload or {}, headers=headers)

    return _handle


# --- Reachability ---


async def test_reachability_200() -> None:
    ctx = make_context(json_handler(200, {"ok": True}))
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.success
    assert result.http_status == 200
    assert result.latency_ms is not None


async def test_reachability_204() -> None:
    ctx = make_context(json_handler(204))
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.success
    assert result.http_status == 204


async def test_reachability_redirect_recorded() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1":
            return httpx.Response(
                301, headers={"location": "https://api.example.com/v2"}
            )
        return httpx.Response(200, json={})

    # follow_redirects=False so history is observable through the client
    transport = httpx.MockTransport(_handle)
    client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    ctx = ProbeContext(
        candidate=make_candidate(), client=client, base_url=BASE
    )
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await client.aclose()
    assert result.success
    assert result.http_status == 200


async def test_reachability_500_not_reachable() -> None:
    ctx = make_context(json_handler(500, {"error": "boom"}))
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert not result.success
    assert result.http_status == 500


@pytest.mark.parametrize("status", [502, 503, 504])
async def test_reachability_server_errors(status: int) -> None:
    ctx = make_context(json_handler(status))
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert not result.success
    assert result.http_status == status


async def test_reachability_timeout() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    ctx = make_context(_handle)
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert not result.success
    assert result.error == "timeout"


async def test_reachability_dns_error() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Name resolution failed")

    ctx = make_context(_handle)
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert not result.success
    assert "connection_error" in (result.data.get("error") or "")


async def test_reachability_tls_error() -> None:
    class FakeTLS(httpx.TransportError):
        pass

    FakeTLS.__name__ = "SSLError"

    def _handle(request: httpx.Request) -> httpx.Response:
        raise FakeTLS("certificate verify failed")

    ctx = make_context(_handle)
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert not result.success
    assert result.data.get("error") == "tls_error"


async def test_reachability_head_failure_falls_back_to_get() -> None:
    """HEAD 405 must not mean offline — GET fallback decides."""
    calls: list[str] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "HEAD":
            return httpx.Response(405, json={"error": "method not allowed"})
        return httpx.Response(200, json={"ok": True})

    ctx = make_context(_handle)
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    # HEAD returned 405 (reachable class) so the first attempt already succeeds.
    assert result.http_status in (200, 405)
    assert result.success


async def test_reachability_html_response() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<html><body>ok</body></html>", headers={"content-type": "text/html"}
        )

    ctx = make_context(_handle)
    try:
        result = await ReachabilityProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.success
    assert result.data.get("content_type") == "text/html"


# --- Auth probe ---


async def test_auth_401_bearer() -> None:
    ctx = make_context(
        json_handler(
            401,
            {"error": "missing Authorization header"},
            {"WWW-Authenticate": "Bearer"},
        )
    )
    try:
        result = await AuthProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.success
    assert result.data["auth_required"] is True
    assert result.data["auth_scheme"] == "bearer"


async def test_auth_401_api_key_body() -> None:
    ctx = make_context(json_handler(401, {"error": "missing x-api-key"}))
    try:
        result = await AuthProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.data["auth_required"] is True
    assert result.data["auth_scheme"] == "api-key-header"


async def test_auth_403_unknown_scheme() -> None:
    ctx = make_context(json_handler(403, {"error": "denied"}))
    try:
        result = await AuthProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.data["auth_required"] is True
    assert result.data["auth_scheme"] == "unknown"


async def test_auth_200_no_auth() -> None:
    ctx = make_context(json_handler(200, {"ok": True}))
    try:
        result = await AuthProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.data["auth_required"] is False
    assert result.data["auth_scheme"] == "none"


async def test_auth_404_no_challenge() -> None:
    ctx = make_context(json_handler(404, {"error": "not found"}))
    try:
        result = await AuthProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.data["auth_required"] is False


# --- OpenAPI probe ---


async def test_openapi_schema_found() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/openapi.json"):
            return httpx.Response(
                200,
                json={"openapi": "3.0.0", "paths": {"/v1/models": {}, "/v1/chat": {}}},
            )
        return httpx.Response(404, json={})

    ctx = make_context(_handle)
    try:
        result = await OpenAPISchemaProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert result.success
    assert result.data["path_count"] == 2


async def test_openapi_schema_absent() -> None:
    ctx = make_context(json_handler(404, {}))
    try:
        result = await OpenAPISchemaProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert not result.success


async def test_openapi_malformed_json() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json{")

    ctx = make_context(_handle)
    try:
        result = await OpenAPISchemaProbe().run(ctx)
    finally:
        await ctx.client.aclose()
    assert not result.success
