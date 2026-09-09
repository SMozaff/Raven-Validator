"""Anthropic-compatible adapter.

Patterns: POST /v1/messages, x-api-key header, anthropic-version header.
Authorized probe only — no anonymous generation. Does not assume
official Anthropic behavior for every compatible implementation.
"""

import httpx

from raven_validator.adapters.base import DetectionResult, clamp_confidence
from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel


class AnthropicCompatibleAdapter:
    """Detects and probes Anthropic-compatible APIs."""

    name = "anthropic-compatible"

    async def detect(self, context: ProbeContext) -> DetectionResult:
        evidence: list[str] = []
        score = 0.0

        hint = (context.candidate.protocol_hint or "").lower()
        if "anthropic" in hint:
            evidence.append("Protocol hint suggests Anthropic-compatible")
            score += 0.2

        # Anthropic APIs typically use /v1/messages.
        url = f"{context.base_url.rstrip('/')}/messages"
        model_url = f"{context.base_url.rstrip('/')}/models"
        try:
            # Check if base declares anthropic headers or messages endpoint.
            response = await context.client.get(model_url)
            headers_lower = {k.lower(): v.lower() for k, v in response.headers.items()}
            if "anthropic-version" in headers_lower:
                evidence.append("Response declares anthropic-version header")
                score += 0.4
        except httpx.HTTPError:
            pass

        # OPTIONS or HEAD on /v1/messages — some gateways advertise it.
        try:
            response = await context.client.request("OPTIONS", url)
            if response.status_code in (200, 204, 405):
                allow = response.headers.get("allow", "").lower()
                if "post" in allow:
                    evidence.append("OPTIONS /v1/messages allows POST")
                    score += 0.3
        except httpx.HTTPError:
            pass

        # 401/403 on /v1/messages without credentials suggests Anthropic auth.
        try:
            response = await context.client.post(
                url, json={"model": "probe", "messages": []}
            )
            if response.status_code in (401, 403):
                try:
                    body = response.text.lower()
                except ValueError:
                    body = ""
                if "x-api-key" in body or "anthropic" in body or "api key" in body:
                    evidence.append(
                        "POST /v1/messages returned 401/403 mentioning x-api-key"
                    )
                    score += 0.45
                elif response.headers.get("www-authenticate"):
                    evidence.append("POST /v1/messages returned WWW-Authenticate")
                    score += 0.25
        except httpx.HTTPError:
            pass

        confidence = clamp_confidence(score)
        protocol = "anthropic-compatible" if confidence >= 0.35 else "unknown"
        if protocol == "unknown" and not evidence:
            evidence.append("No Anthropic-compatible signals found")
        return DetectionResult(
            protocol=protocol,
            confidence=confidence,
            evidence=evidence,
            adapter_name=self.name,
        )

    async def probe_public(self, context: ProbeContext) -> list[ProbeResult]:
        """No public probe beyond detection — Anthropic is auth-gated."""
        return [
            ProbeResult(
                probe_name="anthropic_public",
                safety_level=ProbeSafetyLevel.READ_ONLY,
                success=False,
                endpoint=f"{context.base_url.rstrip('/')}/messages",
                method="POST",
                evidence=["Anthropic-compatible APIs require authentication"],
            )
        ]

    async def probe_authorized(
        self, context: ProbeContext, credential: str
    ) -> list[ProbeResult]:
        url = f"{context.base_url.rstrip('/')}/messages"
        payload = {
            "model": context.options.get("model", "claude-3-haiku-20240307"),
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "Reply with OK."}],
        }
        headers = {
            "x-api-key": credential,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            response = await context.client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return [
                ProbeResult(
                    probe_name="anthropic_generation",
                    safety_level=ProbeSafetyLevel.MINIMAL_GENERATION,
                    success=False,
                    endpoint=url,
                    method="POST",
                    error=str(exc),
                )
            ]
        success = response.status_code in (200, 201)
        data: dict[str, object] = {"excerpt": response.text[:1000]}
        data["headers"] = dict(response.headers)
        return [
            ProbeResult(
                probe_name="anthropic_generation",
                safety_level=ProbeSafetyLevel.MINIMAL_GENERATION,
                success=success,
                endpoint=url,
                method="POST",
                http_status=response.status_code,
                data=data,  # type: ignore[arg-type]
            )
        ]

    def normalize_error(self, response: object) -> str:
        if isinstance(response, httpx.Response):
            try:
                body = response.json()
                if isinstance(body, dict):
                    err = body.get("error")
                    if isinstance(err, dict):
                        return str(err.get("message", err))
                    if err:
                        return str(err)
            except ValueError:
                pass
            return response.text[:500]
        return str(response)
