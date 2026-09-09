"""Models probe tests."""

import httpx

from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import ProbeContext
from raven_validator.probes.models import ModelsProbe

BASE = "https://api.example.com"


def make_ctx(handler: object) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(name="M", base_url=BASE)  # type: ignore[arg-type]
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(candidate=candidate, client=client, base_url=BASE)
    return ctx, client


async def test_models_success_openai_shape() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "gpt-4"}, {"id": "gpt-3.5"}]})

    ctx, client = make_ctx(_handle)
    try:
        r = await ModelsProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.success
    assert r.data["count"] == 2
    assert "gpt-4" in r.data["models"]


async def test_models_deduplicates() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "a"}, {"id": "b"}]})

    ctx, client = make_ctx(_handle)
    try:
        r = await ModelsProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["models"] == ["a", "b"]


async def test_models_failure_not_found() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    ctx, client = make_ctx(_handle)
    try:
        r = await ModelsProbe().run(ctx)
    finally:
        await client.aclose()
    assert not r.success
    assert r.error is not None
