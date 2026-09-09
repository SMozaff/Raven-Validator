"""Streaming probe tests."""

import httpx

from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import ProbeContext
from raven_validator.probes.streaming import StreamingProbe

BASE = "https://api.example.com/v1"


def make_ctx(  # type: ignore[no-untyped-def]
    handler, credential: str | None = "tok",
) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(name="S", base_url=BASE)  # type: ignore[arg-type]
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(
        candidate=candidate, client=client, base_url=BASE, credential=credential
    )
    return ctx, client


async def test_streaming_success() -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'data: {"choices": [{"delta": {"content": "OK"}}]}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    ctx, client = make_ctx(_handle)
    try:
        r = await StreamingProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.success
    assert r.data["chunks"] >= 1
    assert "first_chunk_ms" in r.data


async def test_streaming_unsupported_422() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"error": "streaming not supported"})

    ctx, client = make_ctx(_handle)
    try:
        r = await StreamingProbe().run(ctx)
    finally:
        await client.aclose()
    assert not r.success
    assert any("not supported" in e for e in r.evidence)


async def test_streaming_no_credential() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"data: hi\n")

    ctx, client = make_ctx(_handle, credential=None)
    try:
        r = await StreamingProbe().run(ctx)
    finally:
        await client.aclose()
    assert not r.success
    assert r.error == "credential_required"
