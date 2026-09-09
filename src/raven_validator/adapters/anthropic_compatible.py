"""Anthropic-compatible adapter; detection never sends POST."""
from __future__ import annotations

import time

from raven_validator.adapters.base import AuthorizedContext, DetectionResult, ProbeOutcome, PublicContext
from raven_validator.security.redaction import redact_text


def _join(base: str, path: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/v1") and path.startswith("/v1/"):
        return b + path[3:]
    return b + path


class AnthropicCompatibleAdapter:
    name = "anthropic-compatible"

    async def detect(self, ctx: PublicContext) -> DetectionResult:
        score = 0.0; evidence: list[str] = []
        hint = (ctx.candidate.protocol_hint or "").lower()
        if "anthropic" in hint or "claude" in hint:
            score += 0.25; evidence.append("Imported protocol hint: Anthropic-compatible")
        # OPTIONS is non-state-changing and does not carry credentials.
        url = _join(ctx.base_url, "/v1/messages")
        try:
            r = await ctx.client.options(url)
            allow = r.headers.get("allow", "").lower()
            if "post" in allow:
                score += 0.35; evidence.append("OPTIONS /v1/messages advertises POST")
            if "anthropic" in " ".join(f"{k}:{v}" for k,v in r.headers.items()).lower():
                score += 0.35; evidence.append("Anthropic header signal")
        except Exception as exc:
            evidence.append(f"OPTIONS detection failed: {type(exc).__name__}")
        return DetectionResult("anthropic-compatible" if score >= 0.35 else "unknown", min(score, 1.0), evidence)

    async def public_models(self, ctx: PublicContext) -> ProbeOutcome:
        # Most Anthropic-style deployments are auth-gated; avoid an unnecessary request.
        return ProbeOutcome("models", False, data={"models": []}, evidence=["Public model listing not assumed"])

    async def authorized_models(self, ctx: AuthorizedContext) -> ProbeOutcome:
        url = _join(ctx.base_url, "/v1/models")
        try:
            r = await ctx.client.get(url, headers=ctx.auth_headers)
        except Exception as exc:
            return ProbeOutcome("models", False, error=f"{type(exc).__name__}: {exc}")
        models: list[str] = []
        if r.status_code == 200:
            try:
                body = r.json()
                data = body.get("data") if isinstance(body, dict) else None
                if isinstance(data, list):
                    models = [x["id"] for x in data if isinstance(x, dict) and isinstance(x.get("id"), str)]
            except ValueError:
                pass
        return ProbeOutcome("models", bool(models), r.status_code, data={"models": models, "headers": dict(r.headers)})

    async def generate(self, ctx: AuthorizedContext) -> ProbeOutcome:
        url = _join(ctx.base_url, "/v1/messages")
        model = ctx.model or "claude-3-haiku-20240307"
        payload = {"model": model, "max_tokens": 5, "messages": [{"role": "user", "content": "Reply with OK."}]}
        headers = {**ctx.auth_headers, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        started = time.perf_counter()
        try:
            r = await ctx.client.post(url, json=payload, headers=headers)
        except Exception as exc:
            return ProbeOutcome("generation", False, error=f"{type(exc).__name__}: {exc}")
        latency = (time.perf_counter() - started) * 1000
        return ProbeOutcome("generation", r.status_code in {200, 201}, r.status_code, latency, {"excerpt": redact_text(r.text, 500), "headers": dict(r.headers)}, [f"HTTP {r.status_code}"])

    async def stream(self, ctx: AuthorizedContext) -> ProbeOutcome:
        # Anthropic compatible SSE uses stream=true on messages.
        url = _join(ctx.base_url, "/v1/messages")
        model = ctx.model or "claude-3-haiku-20240307"
        headers = {**ctx.auth_headers, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {"model": model, "max_tokens": 5, "stream": True, "messages": [{"role": "user", "content": "Reply with OK."}]}
        try:
            r = await ctx.client.post(url, json=payload, headers=headers)
        except Exception as exc:
            return ProbeOutcome("streaming", False, error=f"{type(exc).__name__}: {exc}")
        ctype = r.headers.get("content-type", "")
        return ProbeOutcome("streaming", r.status_code == 200 and ("event-stream" in ctype or "event:" in r.text[:1000]), r.status_code, data={"excerpt": redact_text(r.text, 500), "headers": dict(r.headers)})

    async def quota(self, ctx: AuthorizedContext) -> ProbeOutcome:
        if not ctx.candidate.quota_endpoint:
            return ProbeOutcome("quota", False, data={"status": "UNSUPPORTED", "known": False, "reason": "No documented quota endpoint configured"})
        try:
            r = await ctx.client.get(ctx.candidate.quota_endpoint, headers=ctx.auth_headers)
        except Exception as exc:
            return ProbeOutcome("quota", False, error=f"{type(exc).__name__}: {exc}")
        if r.status_code == 429:
            return ProbeOutcome("quota", False, 429, data={"status": "UNKNOWN", "known": False, "reason": "Rate limited; balance not inferred"})
        if r.status_code != 200:
            return ProbeOutcome("quota", False, r.status_code, data={"status": "UNKNOWN", "known": False, "reason": f"HTTP {r.status_code}"})
        try:
            body = r.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            for key in ("balance", "remaining", "credits"):
                val = body.get(key)
                if isinstance(val, (int, float)):
                    return ProbeOutcome("quota", True, r.status_code, data={"status": "KNOWN", "known": True, "balance": float(val), "unit": str(body.get("unit") or "credits")})
        return ProbeOutcome("quota", False, r.status_code, data={"status": "UNKNOWN", "known": False, "reason": "Unsupported response shape"})
