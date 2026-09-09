"""OpenAI adapter tests."""

import httpx

from raven_validator.adapters.openai_compatible import OpenAICompatibleAdapter
from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import ProbeContext

BASE = "https://api.example.com/v1"


def make_ctx(  # type: ignore[no-untyped-def]
    handler, options: dict[str, object] | None = None
) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(name="OA", base_url=BASE)  # type: ignore[arg-type]
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(candidate=candidate, client=client, base_url=BASE, options=options or {})
    return ctx, client


async def test_public_models_success() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "gpt-4"}]})

    ctx, client = make_ctx(_handle)
    try:
        results = await OpenAICompatibleAdapter().probe_public(ctx)
    finally:
        await client.aclose()
    assert results[0].success
    assert results[0].http_status == 200


async def test_public_models_failure_propagates() -> None:
    def _handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    ctx, client = make_ctx(_handle)
    try:
        results = await OpenAICompatibleAdapter().probe_public(ctx)
    finally:
        await client.aclose()
    assert not results[0].success
    assert results[0].http_status == 401


async def test_authorized_generation_sends_minimal_request() -> None:
    captured: list[dict[str, object]] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}], "usage": {"total_tokens": 5}},
        )

    ctx, client = make_ctx(_handle)
    try:
        results = await OpenAICompatibleAdapter().probe_authorized(ctx, "sk-test")
    finally:
        await client.aclose()
    assert results[0].success
    assert captured[0]["max_tokens"] == 3
    assert captured[0]["messages"][0]["content"] == "Reply with OK."
    assert results[0].data["usage"] == {"total_tokens": 5}


async def test_capability_detection_independent_per_route() -> None:
    """Each capability probe result is independent — models vs chat."""
    from raven_validator.core.capability_detector import detect_capabilities
    from raven_validator.probes.base import ProbeResult
    from raven_validator.security.request_policy import ProbeSafetyLevel

    probe_results = [
        ProbeResult(
            probe_name="openai_models_public",
            safety_level=ProbeSafetyLevel.READ_ONLY,
            success=True,
            http_status=200,
        ),
        ProbeResult(
            probe_name="openai_generation",
            safety_level=ProbeSafetyLevel.MINIMAL_GENERATION,
            success=False,
            http_status=404,
        ),
    ]
    caps = detect_capabilities("openai-compatible", probe_results)
    assert caps.models is True
    assert caps.chat_completions is False
