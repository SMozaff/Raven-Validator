"""Streaming probe — optional, one minimal stream request.

Default off in GUI. When enabled: send one minimal streaming request,
confirm chunks/events arrive, capture first-chunk latency, stop after
sufficient evidence. Avoid long output.
"""

from __future__ import annotations

import time

import httpx

from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel


class StreamingProbe:
    """Optional streaming test (MINIMAL_GENERATION)."""

    name = "streaming"
    safety_level = ProbeSafetyLevel.MINIMAL_GENERATION

    async def run(self, context: ProbeContext) -> ProbeResult:
        if not context.credential:
            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=False,
                evidence=["No authorized credential configured"],
                error="credential_required",
            )

        base = context.base_url.rstrip("/")
        url = (
            f"{base}/chat/completions"
            if base.endswith("/v1")
            else f"{base}/v1/chat/completions"
        )
        payload = {
            "model": context.options.get("model") or "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 3,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {context.credential}"}
        custom = context.options.get("headers")
        if isinstance(custom, dict):
            headers.update(custom)  # type: ignore[arg-type]

        started = time.perf_counter()
        try:
            async with context.client.stream(
                "POST", url, json=payload, headers=headers
            ) as response:
                if response.status_code not in (200, 201):
                    body = await response.aread()
                    unsupported = response.status_code in (400, 404, 422)
                    streaming_msg = "streaming not supported" if unsupported else "streaming failed"
                    return ProbeResult(
                        probe_name=self.name,
                        safety_level=self.safety_level,
                        success=False,
                        endpoint=url,
                        method="POST",
                        http_status=response.status_code,
                        evidence=[f"HTTP {response.status_code}", streaming_msg],
                        data={"excerpt": body[:500].decode(errors="replace")},
                        error=body[:300].decode(errors="replace"),
                    )

                first_chunk_ms: float | None = None
                chunks = 0
                async for chunk in response.aiter_text():
                    if not chunk.strip():
                        continue
                    if first_chunk_ms is None:
                        first_chunk_ms = (time.perf_counter() - started) * 1000
                    chunks += 1
                    # Enough evidence after first real chunk.
                    if chunks >= 1:
                        break

                total_ms = (time.perf_counter() - started) * 1000
                if chunks == 0:
                    return ProbeResult(
                        probe_name=self.name,
                        safety_level=self.safety_level,
                        success=False,
                        endpoint=url,
                        method="POST",
                        http_status=response.status_code,
                        latency_ms=total_ms,
                        evidence=["No stream chunks received"],
                        error="no_chunks",
                    )

                return ProbeResult(
                    probe_name=self.name,
                    safety_level=self.safety_level,
                    success=True,
                    endpoint=url,
                    method="POST",
                    http_status=response.status_code,
                    latency_ms=total_ms,
                    evidence=[f"Streaming supported ({chunks} chunk(s))"],
                    data={
                        "first_chunk_ms": round(first_chunk_ms or total_ms, 1),
                        "chunks": chunks,
                        "headers": dict(response.headers),
                    },
                )
        except httpx.HTTPError as exc:
            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=False,
                endpoint=url,
                method="POST",
                error=str(exc),
                evidence=[f"Streaming request failed: {type(exc).__name__}"],
            )
