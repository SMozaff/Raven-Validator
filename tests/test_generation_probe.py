"""Generation probe tests."""

import json

import httpx

from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import ProbeContext
from raven_validator.probes.generation import GenerationProbe

BASE = "https://api.example.com/v1"


def make_ctx(  # type: ignore[no-untyped-def]
    handler, credential: str | None = "tok",
) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(name="G", base_url=BASE)  # type: ignore[arg-type]
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(
        candidate=candidate, client=client, base_url=BASE, credential=credential
    )
    return ctx, client


async def test_generation_success() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["max_tokens"] == 3
        assert body["messages"][0]["content"] == "Reply with OK."
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "OK"}}], "usage": {"total_tokens": 5}}
        )

    ctx, client = make_ctx(_handle)
    try:
        r = await GenerationProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.success
    assert r.http_status == 200
    assert r.latency_ms is not None
    assert r.data["usage"] == {"total_tokens": 5}


async def test_generation_failure_401() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid key"})

    ctx, client = make_ctx(_handle)
    try:
        r = await GenerationProbe().run(ctx)
    finally:
        await client.aclose()
    assert not r.success
    assert r.http_status == 401


async def test_generation_requires_credential() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    ctx, client = make_ctx(_handle, credential=None)
    try:
        r = await GenerationProbe().run(ctx)
    finally:
        await client.aclose()
    assert not r.success
    assert r.error == "credential_required"
