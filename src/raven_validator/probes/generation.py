"""Minimal generation probe — one small, deterministic request.

Default: 1 request per API, tiny prompt, single-digit max_tokens,
harmless and attributable. Records HTTP status, latency, model,
usage metadata, and a short redacted diagnostic excerpt.
"""

from __future__ import annotations

import time

import httpx

from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel

PROMPT = "Reply with OK."
DEFAULT_MODEL = "gpt-3.5-turbo"


class GenerationProbe:
    """Single minimal generation test (MINIMAL_GENERATION)."""

    name = "generation"
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
        # Prefer /v1/chat/completions; fall back to /v1/completions.
        endpoints = [f"{base}/chat/completions", f"{base}/v1/chat/completions"]
        if not base.endswith("/v1"):
            endpoints = [f"{base}/v1/chat/completions", f"{base}/chat/completions"]
        # Deduplicate while preserving order.
        endpoints = list(dict.fromkeys(endpoints))

        model = context.options.get("model") or DEFAULT_MODEL
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 3,
        }
        headers = {"Authorization": f"Bearer {context.credential}"}
        # Allow explicit header override via options (e.g., x-api-key).
        custom_headers = context.options.get("headers")
        if isinstance(custom_headers, dict):
            headers.update(custom_headers)  # type: ignore[arg-type]

        last_result: ProbeResult | None = None
        for url in endpoints:
            started = time.perf_counter()
            try:
                response = await context.client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                last_result = ProbeResult(
                    probe_name=self.name,
                    safety_level=self.safety_level,
                    success=False,
                    endpoint=url,
                    method="POST",
                    error=str(exc),
                    evidence=[f"Request failed: {type(exc).__name__}"],
                )
                continue

            latency_ms = (time.perf_counter() - started) * 1000
            success = response.status_code in (200, 201)
            data: dict[str, object] = {
                "model": model,
                "excerpt": response.text[:500],
                "headers": dict(response.headers),
                "latency_ms": round(latency_ms, 1),
            }
            try:
                body = response.json()
                if isinstance(body, dict):
                    usage = body.get("usage")
                    if usage is not None:
                        data["usage"] = usage
            except ValueError:
                pass

            evidence = [f"HTTP {response.status_code}"]
            if not success and response.status_code in (401, 403):
                evidence.append("authentication failed")
            elif success:
                evidence.append("generation succeeded")

            last_result = ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=success,
                endpoint=url,
                method="POST",
                http_status=response.status_code,
                latency_ms=latency_ms,
                evidence=evidence,
                data=data,  # type: ignore[arg-type]
                error=None if success else response.text[:300],
            )
            # On 404 try the next endpoint; otherwise return.
            if response.status_code != 404:
                return last_result

        return last_result or ProbeResult(
            probe_name=self.name,
            safety_level=self.safety_level,
            success=False,
            error="no endpoint responded",
        )
