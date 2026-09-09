"""Auth scheme detection — no auth, bearer, api-key, invalid credential."""

import httpx

from raven_validator.domain.candidates import APICandidate
from raven_validator.domain.credentials import AuthScheme
from raven_validator.probes.auth import AuthProbe
from raven_validator.probes.base import ProbeContext

BASE = "https://api.example.com/v1"


def make_ctx(handler: object) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(name="Auth", base_url=BASE)  # type: ignore[arg-type]
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(candidate=candidate, client=client, base_url=BASE)
    return ctx, client


async def test_no_auth_required() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    ctx, client = make_ctx(_handle)
    try:
        r = await AuthProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["auth_required"] is False
    assert r.data["auth_scheme"] == AuthScheme.NONE.value


async def test_bearer_via_www_authenticate() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": "unauthorized"}, headers={"WWW-Authenticate": "Bearer realm=api"}
        )

    ctx, client = make_ctx(_handle)
    try:
        r = await AuthProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["auth_required"] is True
    assert r.data["auth_scheme"] == AuthScheme.BEARER.value


async def test_api_key_via_body() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "missing x-api-key header"})

    ctx, client = make_ctx(_handle)
    try:
        r = await AuthProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["auth_scheme"] == AuthScheme.API_KEY_HEADER.value


async def test_invalid_credential_401_still_auth_required() -> None:
    """AuthProbe never validates credentials — it only detects the requirement."""
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    ctx, client = make_ctx(_handle)
    try:
        r = await AuthProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["auth_required"] is True


async def test_missing_credential_no_probe_failure() -> None:
    """AuthProbe succeeds even when no credential is present — it checks requirement only."""
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    ctx, client = make_ctx(_handle)
    try:
        r = await AuthProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.success is True
