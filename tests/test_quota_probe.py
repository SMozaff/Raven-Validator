"""Quota probe tests."""

import httpx

from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import ProbeContext
from raven_validator.probes.quota import QuotaProbe

BASE = "https://api.example.com/v1"


def make_ctx(  # type: ignore[no-untyped-def]
    handler, credential: str | None = "tok",
) -> tuple[ProbeContext, httpx.AsyncClient]:
    candidate = APICandidate(name="Q", base_url=BASE)  # type: ignore[arg-type]
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    client = httpx.AsyncClient(transport=transport)
    ctx = ProbeContext(
        candidate=candidate, client=client, base_url=BASE, credential=credential
    )
    return ctx, client


async def test_quota_known_balance() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"balance": 12.5, "unit": "USD"})

    ctx, client = make_ctx(_handle)
    try:
        r = await QuotaProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.success
    assert r.data["known"] is True
    assert r.data["status"] == "KNOWN"
    assert r.data["balance"] == 12.5


async def test_quota_unknown_no_endpoint() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    ctx, client = make_ctx(_handle)
    try:
        r = await QuotaProbe().run(ctx)
    finally:
        await client.aclose()
    assert not r.success
    assert r.data["status"] == "UNKNOWN"
    assert "no supported quota" in r.data["reason"].lower()


async def test_quota_unsupported_is_unknown_not_failure_collapse() -> None:
    """Unknown quota must be UNKNOWN, not a hard failure status."""
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    ctx, client = make_ctx(_handle)
    try:
        r = await QuotaProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["known"] is False
    assert r.data["status"] == "UNKNOWN"


async def test_quota_insufficient_via_429() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "insufficient credits"})

    ctx, client = make_ctx(_handle)
    # Only first quota path returns 429-insufficient; need to ensure probe hits it.
    # QuotaProbe checks body for credit markers on 429.
    try:
        r = await QuotaProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["status"] == "INSUFFICIENT"


async def test_quota_no_credential_is_unknown() -> None:
    def _handle(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"balance": 5})

    ctx, client = make_ctx(_handle, credential=None)
    try:
        r = await QuotaProbe().run(ctx)
    finally:
        await client.aclose()
    assert r.data["status"] == "UNKNOWN"
