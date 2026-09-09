"""Anthropic adapter tests."""

import json

import httpx

from raven_validator.adapters.anthropic_compatible import AnthropicCompatibleAdapter
from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import ProbeContext

BASE = "https://api.example.com/v1"


def make_ctx(  # type: ignore[no-untyped-def]
    handler, options: dict[str, object] | None = None
) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(name="Anth", base_url=BASE)  # type: ignore[arg-type]
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(candidate=candidate, client=client, base_url=BASE, options=options or {})
    return ctx, client


async def test_anthropic_public_is_auth_gated() -> None:
    def _handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    ctx, client = make_ctx(_handle)
    try:
        results = await AnthropicCompatibleAdapter().probe_public(ctx)
    finally:
        await client.aclose()
    assert not results[0].success
    assert any("require" in e.lower() for e in results[0].evidence)


async def test_anthropic_authorized_sends_x_api_key() -> None:
    captured: list[dict[str, str]] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        captured.append(dict(request.headers))
        body = json.loads(request.content)
        assert body["max_tokens"] == 5
        return httpx.Response(200, json={"content": [{"text": "OK"}]})

    ctx, client = make_ctx(_handle)
    try:
        results = await AnthropicCompatibleAdapter().probe_authorized(ctx, "sk-ant-test")
    finally:
        await client.aclose()
    assert results[0].success
    assert captured[0]["x-api-key"] == "sk-ant-test"
    assert captured[0]["anthropic-version"] == "2023-06-01"


async def test_anthropic_authorized_failure() -> None:
    def _handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    ctx, client = make_ctx(_handle)
    try:
        results = await AnthropicCompatibleAdapter().probe_authorized(ctx, "bad")
    finally:
        await client.aclose()
    assert not results[0].success
    assert results[0].http_status == 401
