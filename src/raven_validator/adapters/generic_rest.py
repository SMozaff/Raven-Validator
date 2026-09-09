"""Conservative generic REST adapter."""
from __future__ import annotations

from raven_validator.adapters.base import AuthorizedContext, DetectionResult, ProbeOutcome, PublicContext
from raven_validator.security.redaction import redact_text


class GenericRESTAdapter:
    name = "generic-rest"

    async def detect(self, ctx: PublicContext) -> DetectionResult:
        hint = (ctx.candidate.protocol_hint or "").lower()
        if hint in {"generic-rest", "generic", "rest"}:
            return DetectionResult("generic-rest", 0.55, ["Explicit generic-rest hint"])
        try:
            r = await ctx.client.get(ctx.base_url)
        except Exception as exc:
            return DetectionResult("unknown", 0.0, [f"GET failed: {type(exc).__name__}"])
        if r.status_code < 500:
            return DetectionResult("generic-rest", 0.2, [f"Reachable HTTP endpoint: {r.status_code}"])
        return DetectionResult("unknown", 0.0, [f"Server error: {r.status_code}"])

    async def public_models(self, ctx: PublicContext) -> ProbeOutcome:
        return ProbeOutcome("models", False, data={"models": []}, evidence=["No generic model endpoint guessed"])

    async def authorized_models(self, ctx: AuthorizedContext) -> ProbeOutcome:
        return ProbeOutcome("models", False, data={"models": []}, evidence=["No generic model endpoint guessed"])

    async def generate(self, ctx: AuthorizedContext) -> ProbeOutcome:
        template = ctx.candidate.custom_probe
        if not isinstance(template, dict):
            return ProbeOutcome("generation", False, data={"status": "UNSUPPORTED"}, evidence=["No explicit custom probe template configured"])
        method = str(template.get("method", "GET")).upper()
        url = str(template.get("url") or ctx.base_url)
        if method not in {"GET", "HEAD", "POST", "PUT", "PATCH"}:
            return ProbeOutcome("generation", False, error="Unsupported custom method")
        headers = dict(ctx.auth_headers)
        headers.update({str(k): str(v) for k,v in dict(template.get("headers") or {}).items()})
        try:
            r = await ctx.client.request(method, url, headers=headers, json=template.get("body") if method in {"POST","PUT","PATCH"} else None)
        except Exception as exc:
            return ProbeOutcome("generation", False, error=f"{type(exc).__name__}: {exc}")
        return ProbeOutcome("generation", r.status_code < 400, r.status_code, data={"excerpt": redact_text(r.text, 500), "headers": dict(r.headers)})

    async def stream(self, ctx: AuthorizedContext) -> ProbeOutcome:
        return ProbeOutcome("streaming", False, data={"status": "UNSUPPORTED"})

    async def quota(self, ctx: AuthorizedContext) -> ProbeOutcome:
        if not ctx.candidate.quota_endpoint:
            return ProbeOutcome("quota", False, data={"status": "UNSUPPORTED", "known": False, "reason": "No documented quota endpoint configured"})
        try:
            r = await ctx.client.get(ctx.candidate.quota_endpoint, headers=ctx.auth_headers)
        except Exception as exc:
            return ProbeOutcome("quota", False, error=f"{type(exc).__name__}: {exc}")
        return ProbeOutcome("quota", False, r.status_code, data={"status": "UNKNOWN", "known": False, "reason": "Generic quota response is not interpreted without provider schema"})
