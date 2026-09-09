"""Protocol detection tests (OpenAI, Anthropic, Generic, Unknown)."""

import httpx

from raven_validator.adapters.anthropic_compatible import AnthropicCompatibleAdapter
from raven_validator.adapters.generic_rest import GenericRESTAdapter
from raven_validator.adapters.openai_compatible import OpenAICompatibleAdapter
from raven_validator.core.protocol_detector import detect_protocol
from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import ProbeContext

BASE = "https://api.example.com/v1"


def make_ctx(
    handler: object, protocol_hint: str | None = None, base_url: str = BASE
) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(
        name="Probe", base_url=base_url, protocol_hint=protocol_hint  # type: ignore[arg-type]
    )
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(candidate=candidate, client=client, base_url=base_url)
    return ctx, client


async def test_openai_detected_via_models_endpoint() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        if "/models" in request.url.path:
            return httpx.Response(
                200, json={"object": "list", "data": [{"id": "gpt-4"}]}
            )
        return httpx.Response(200, json={"ok": True})

    ctx, client = make_ctx(_handle)
    try:
        result = await OpenAICompatibleAdapter().detect(ctx)
    finally:
        await client.aclose()
    assert result.protocol == "openai-compatible"
    assert result.confidence >= 0.35
    assert any("models" in e.lower() for e in result.evidence)


async def test_openai_not_claimed_from_provider_name_alone() -> None:
    """Never claim OpenAI-compat from a name/hint without evidence."""

    def _handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    candidate = APICandidate(
        name="OpenAI Wrapper", base_url=BASE, provider_hint="openai"  # type: ignore[arg-type]
    )
    transport = httpx.MockTransport(_handle)
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(candidate=candidate, client=client, base_url=BASE)
    try:
        result = await OpenAICompatibleAdapter().detect(ctx)
    finally:
        await client.aclose()
    # Provider hint is openai, but adapter only checks protocol_hint.
    assert result.protocol == "unknown"


async def test_anthropic_detected_via_messages_endpoint() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        if "/messages" in request.url.path:
            return httpx.Response(
                401, json={"error": {"message": "missing x-api-key"}}, headers={}
            )
        return httpx.Response(404, json={})

    ctx, client = make_ctx(_handle)
    try:
        result = await AnthropicCompatibleAdapter().detect(ctx)
    finally:
        await client.aclose()
    assert result.protocol == "anthropic-compatible"
    assert any("x-api-key" in e for e in result.evidence)


async def test_generic_rest_low_confidence_fallback() -> None:
    def _handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    ctx, client = make_ctx(_handle, base_url="https://api.example.com")
    try:
        result = await GenericRESTAdapter().detect(ctx)
    finally:
        await client.aclose()
    assert result.protocol == "generic-rest"
    assert result.confidence < 0.35


async def test_protocol_detector_picks_highest_confidence() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        if "/models" in request.url.path:
            return httpx.Response(
                200, json={"object": "list", "data": [{"id": "gpt-4"}]}
            )
        if "/messages" in request.url.path:
            return httpx.Response(404, json={})
        return httpx.Response(200, json={"ok": True})

    ctx, client = make_ctx(_handle)
    try:
        result = await detect_protocol(ctx)
    finally:
        await client.aclose()
    assert result.protocol == "openai-compatible"


async def test_generic_never_auto_posts() -> None:
    """Generic adapter must not POST without an explicit template."""
    received: list[str] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        received.append(request.method)
        return httpx.Response(200, json={"ok": True})

    ctx, client = make_ctx(_handle, base_url="https://api.example.com")
    try:
        results = await GenericRESTAdapter().probe_authorized(ctx, "secret")
    finally:
        await client.aclose()
    # No custom template: authorized path should GET, not POST.
    assert "POST" not in received
    assert results[0].method == "GET"
