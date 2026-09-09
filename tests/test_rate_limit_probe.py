"""Rate-limit probe tests."""

import httpx

from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import ProbeContext
from raven_validator.probes.rate_limits import RateLimitProbe

BASE = "https://api.example.com/v1"


def make_ctx(handler: object) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(name="R", base_url=BASE)  # type: ignore[arg-type]
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(candidate=candidate, client=client, base_url=BASE)
    return ctx, client


async def test_rate_limit_headers_parsed() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={},
            headers={
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "42",
                "X-RateLimit-Reset": "1700000000",
            },
        )

    ctx, client = make_ctx(_handle)
    try:
        r = await RateLimitProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.success
    assert r.data["known"] is True
    assert r.data["limit"] == 100
    assert r.data["remaining"] == 42
    assert "1700000000" not in str(r.data["reset_at"])  # parsed to ISO


async def test_retry_after_parsed() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={}, headers={"Retry-After": "120"})

    ctx, client = make_ctx(_handle)
    try:
        r = await RateLimitProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["known"] is True
    assert r.data["retry_after"] == "120"


async def test_no_rate_limit_headers() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    ctx, client = make_ctx(_handle)
    try:
        r = await RateLimitProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["known"] is False
