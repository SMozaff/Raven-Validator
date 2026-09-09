"""Generic REST adapter.

Never guesses dangerous request formats or automatically POSTs arbitrary
payloads to unknown APIs. Allowed to: test the supplied endpoint,
inspect safe responses, inspect public schemas, and use a custom probe
template only when explicitly configured by the user.
"""

import httpx

from raven_validator.adapters.base import DetectionResult
from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel


class GenericRESTAdapter:
    """Safe, non-assumptive adapter for unknown/generic APIs."""

    name = "generic-rest"

    async def detect(self, context: ProbeContext) -> DetectionResult:
        hint = (context.candidate.protocol_hint or "").lower()
        if hint in ("generic-rest", "generic", "rest"):
            return DetectionResult(
                protocol="generic-rest",
                confidence=0.55,
                evidence=["Protocol hint explicitly set to generic-rest"],
                adapter_name=self.name,
            )

        # Generic is the low-confidence fallback — only claim it when
        # nothing more specific matched. Caller (protocol_detector)
        # picks the highest-confidence adapter, so return low here.
        try:
            response = await context.client.get(context.base_url)
        except httpx.HTTPError:
            return DetectionResult(
                protocol="unknown",
                confidence=0.0,
                evidence=["Generic probe: no connection"],
                adapter_name=self.name,
            )

        if response.status_code < 500:
            return DetectionResult(
                protocol="generic-rest",
                confidence=0.2,
                evidence=[
                    f"Generic REST: HTTP {response.status_code} (no specific protocol)"
                ],
                adapter_name=self.name,
            )
        return DetectionResult(
            protocol="unknown",
            confidence=0.0,
            evidence=["Generic probe: server error, cannot classify"],
            adapter_name=self.name,
        )

    async def probe_public(self, context: ProbeContext) -> list[ProbeResult]:
        """Inspect the supplied endpoint only — safe GET, no payload guessing."""
        try:
            response = await context.client.get(context.base_url)
        except httpx.HTTPError as exc:
            return [
                ProbeResult(
                    probe_name="generic_public",
                    safety_level=ProbeSafetyLevel.READ_ONLY,
                    success=False,
                    endpoint=context.base_url,
                    method="GET",
                    error=str(exc),
                )
            ]
        return [
            ProbeResult(
                probe_name="generic_public",
                safety_level=ProbeSafetyLevel.READ_ONLY,
                success=response.status_code < 400,
                endpoint=context.base_url,
                method="GET",
                http_status=response.status_code,
                evidence=[f"HTTP {response.status_code}"],
                data={"excerpt": response.text[:1000], "headers": dict(response.headers)},
            )
        ]

    async def probe_authorized(
        self, context: ProbeContext, credential: str
    ) -> list[ProbeResult]:
        """Only run a custom template when explicitly configured; otherwise safe GET."""
        template = context.options.get("custom_template")
        if not template or not isinstance(template, dict):
            # Safe fallback: same as public but with auth header supplied.
            method = context.options.get("custom_method", "GET").upper()
            if method not in ("GET", "HEAD"):
                return [
                    ProbeResult(
                        probe_name="generic_authorized",
                        safety_level=ProbeSafetyLevel.CUSTOM_AUTHORIZED,
                        success=False,
                        endpoint=context.base_url,
                        method=method,
                        error="Custom template required for non-GET authorized requests",
                    )
                ]
            try:
                headers = {"Authorization": f"Bearer {credential}"}
                response = await context.client.get(
                    context.base_url, headers=headers
                )
            except httpx.HTTPError as exc:
                return [
                    ProbeResult(
                        probe_name="generic_authorized",
                        safety_level=ProbeSafetyLevel.CUSTOM_AUTHORIZED,
                        success=False,
                        endpoint=context.base_url,
                        method="GET",
                        error=str(exc),
                    )
                ]
            return [
                ProbeResult(
                    probe_name="generic_authorized",
                    safety_level=ProbeSafetyLevel.CUSTOM_AUTHORIZED,
                    success=response.status_code < 400,
                    endpoint=context.base_url,
                    method="GET",
                    http_status=response.status_code,
                    evidence=[f"HTTP {response.status_code}"],
                    data={"excerpt": response.text[:1000]},
                )
            ]

        # Explicit template path — user has reviewed and configured this.
        method = str(template.get("method", "GET")).upper()
        path = str(template.get("path", ""))
        headers = dict(template.get("headers", {}))
        body = template.get("body")
        # Resolve credential placeholder.
        for key, value in list(headers.items()):
            if isinstance(value, str) and "{{credential}}" in value:
                headers[key] = value.replace("{{credential}}", credential)
        url = f"{context.base_url.rstrip('/')}{path}" if path else context.base_url
        try:
            if method in ("POST", "PUT", "PATCH"):
                response = await context.client.request(
                    method, url, json=body, headers=headers
                )
            else:
                response = await context.client.request(method, url, headers=headers)
        except httpx.HTTPError as exc:
            return [
                ProbeResult(
                    probe_name="generic_authorized",
                    safety_level=ProbeSafetyLevel.CUSTOM_AUTHORIZED,
                    success=False,
                    endpoint=url,
                    method=method,
                    error=str(exc),
                )
            ]
        return [
            ProbeResult(
                probe_name="generic_authorized",
                safety_level=ProbeSafetyLevel.CUSTOM_AUTHORIZED,
                success=response.status_code < 400,
                endpoint=url,
                method=method,
                http_status=response.status_code,
                data={"excerpt": response.text[:1000]},
            )
        ]

    def normalize_error(self, response: object) -> str:
        if isinstance(response, httpx.Response):
            return response.text[:500]
        return str(response)
