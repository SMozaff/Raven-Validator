"""OpenAI-compatible adapter."""
from __future__ import annotations

import json
import time

import httpx

from raven_validator.adapters.base import AuthorizedContext, DetectionResult, ProbeOutcome, PublicContext
from raven_validator.security.redaction import redact_text


def _join(base: str, suffix: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1") and suffix.startswith("/v1/"):
        return b + suffix[3:]
    if not b.endswith("/v1") and suffix.startswith("/v1/"):
        return b + suffix
    return b + suffix


class OpenAICompatibleAdapter:
    name = "openai-compatible"

    async def detect(self, ctx: PublicContext) -> DetectionResult:
        evidence: list[str] = []
        score = 0.0
        hint = (ctx.candidate.protocol_hint or "").lower()
        if "openai" in hint:
            evidence.append("Imported protocol hint: OpenAI-compatible")
            score += 0.2
        # Safe GET only. A 401 at the canonical models route is a useful signal.
        url = _join(ctx.base_url, "/v1/models")
        try:
            r = await ctx.client.get(url)
        except (httpx.HTTPError, ValueError) as exc:
            return DetectionResult("unknown", score, [*evidence, f"models probe failed: {type(exc).__name__}"])
        if r.status_code == 401:
            evidence.append("/v1/models returned 401")
            score += 0.3
        elif r.status_code == 200:
            try:
                body = r.json()
            except ValueError:
                body = None
            if isinstance(body, dict) and isinstance(body.get("data"), list):
                evidence.append("/v1/models returned OpenAI-style data[]")
                score += 0.6
        return DetectionResult("openai-compatible" if score >= 0.35 else "unknown", min(score, 1.0), evidence)

    async def public_models(self, ctx: PublicContext) -> ProbeOutcome:
        return await self._models(ctx.client, ctx.base_url, {})

    async def authorized_models(self, ctx: AuthorizedContext) -> ProbeOutcome:
        return await self._models(ctx.client, ctx.base_url, ctx.auth_headers)

    async def _models(self, client, base: str, headers: dict[str, str]) -> ProbeOutcome:
        url = _join(base, "/v1/models")
        started = time.perf_counter()
        try:
            r = await client.get(url, headers=headers or None)
        except Exception as exc:
            return ProbeOutcome("models", False, error=f"{type(exc).__name__}: {exc}")
        latency = (time.perf_counter() - started) * 1000
        models: list[str] = []
        if r.status_code == 200:
            try:
                body = r.json()
                if isinstance(body, dict) and isinstance(body.get("data"), list):
                    models = [x["id"] for x in body["data"] if isinstance(x, dict) and isinstance(x.get("id"), str)]
            except ValueError:
                pass
        return ProbeOutcome("models", bool(models), r.status_code, latency, {"models": list(dict.fromkeys(models)), "headers": dict(r.headers)}, [f"HTTP {r.status_code}"])

    async def generate(self, ctx: AuthorizedContext) -> ProbeOutcome:
        url = _join(ctx.base_url, "/v1/chat/completions")
        model = ctx.model or "gpt-3.5-turbo"
        payload = {"model": model, "messages": [{"role": "user", "content": "Reply with OK."}], "max_tokens": 3}
        started = time.perf_counter()
        try:
            r = await ctx.client.post(url, json=payload, headers=ctx.auth_headers)
        except Exception as exc:
            return ProbeOutcome("generation", False, error=f"{type(exc).__name__}: {exc}")
        latency = (time.perf_counter() - started) * 1000
        data = {"model": model, "excerpt": redact_text(r.text, 500), "headers": dict(r.headers)}
        try:
            body = r.json()
            if isinstance(body, dict) and body.get("usage") is not None:
                data["usage"] = body.get("usage")
        except ValueError:
            pass
        return ProbeOutcome("generation", r.status_code in {200, 201}, r.status_code, latency, data, [f"HTTP {r.status_code}"])

    async def stream(self, ctx: AuthorizedContext) -> ProbeOutcome:
        # Use the normal request interface; evidence is a valid SSE response + data lines.
        url = _join(ctx.base_url, "/v1/chat/completions")
        model = ctx.model or "gpt-3.5-turbo"
        payload = {"model": model, "messages": [{"role": "user", "content": "Reply with OK."}], "max_tokens": 3, "stream": True}
        started = time.perf_counter()
        try:
            r = await ctx.client.post(url, json=payload, headers=ctx.auth_headers)
        except Exception as exc:
            return ProbeOutcome("streaming", False, error=f"{type(exc).__name__}: {exc}")
        latency = (time.perf_counter() - started) * 1000
        ctype = r.headers.get("content-type", "")
        success = r.status_code == 200 and ("text/event-stream" in ctype or "data:" in r.text[:1000])
        return ProbeOutcome("streaming", success, r.status_code, latency, {"excerpt": redact_text(r.text, 500), "headers": dict(r.headers)})

    async def quota(self, ctx: AuthorizedContext) -> ProbeOutcome:
        # Only an explicit endpoint configured by the user/imported trusted metadata is allowed.
        endpoint = ctx.candidate.quota_endpoint
        if not endpoint:
            return ProbeOutcome("quota", False, data={"status": "UNSUPPORTED", "known": False, "reason": "No documented quota endpoint configured"})
        try:
            r = await ctx.client.get(endpoint, headers=ctx.auth_headers)
        except Exception as exc:
            return ProbeOutcome("quota", False, error=f"{type(exc).__name__}: {exc}")
        if r.status_code == 429:
            return ProbeOutcome("quota", False, 429, data={"status": "UNKNOWN", "known": False, "reason": "Rate limited; credit balance not inferred"})
        if r.status_code != 200:
            return ProbeOutcome("quota", False, r.status_code, data={"status": "UNKNOWN", "known": False, "reason": f"HTTP {r.status_code}"})
        try:
            body = r.json()
        except ValueError:
            return ProbeOutcome("quota", False, r.status_code, data={"status": "UNKNOWN", "known": False, "reason": "Non-JSON quota response"})
        candidate = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else body
        if isinstance(candidate, dict):
            for key in ("total_available", "balance", "remaining", "credits", "available"):
                value = candidate.get(key)
                if isinstance(value, (int, float)):
                    return ProbeOutcome("quota", True, r.status_code, data={"status": "KNOWN", "known": True, "balance": float(value), "unit": str(candidate.get("unit") or candidate.get("currency") or "credits")})
        return ProbeOutcome("quota", False, r.status_code, data={"status": "UNKNOWN", "known": False, "reason": "Documented endpoint returned unsupported shape"})
