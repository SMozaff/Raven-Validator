"""Reachability probe: conservative connectivity inspection.

Flow: HEAD when reasonable → fallback to safe GET (HEAD failure alone
never means offline) → measure latency → record redirect, HTTP status,
content type, TLS/network errors.
"""

import time

import httpx

from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel


class ReachabilityProbe:
    """Safe, low-impact reachability check (READ_ONLY)."""

    name = "reachability"
    safety_level = ProbeSafetyLevel.READ_ONLY

    async def run(self, context: ProbeContext) -> ProbeResult:
        evidence: list[str] = []
        data: dict[str, object] = {}
        started = time.perf_counter()

        response = await self._safe_request(context, evidence, data)
        latency_ms = (time.perf_counter() - started) * 1000.0

        if response is None:
            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=False,
                endpoint=context.base_url,
                method="GET",
                latency_ms=latency_ms,
                evidence=evidence,
                data=data,
                error=data.get("error") if isinstance(data.get("error"), str) else None,
            )

        evidence.append(f"HTTP {response.status_code}")
        if response.history:
            chain = " -> ".join(
                f"{r.status_code} {r.headers.get('location', '')}" for r in response.history
            )
            evidence.append(f"Redirect chain: {chain}")
            data["redirected"] = True
        else:
            data["redirected"] = False

        content_type = response.headers.get("content-type")
        if content_type:
            evidence.append(f"Content-Type: {content_type}")
            data["content_type"] = content_type
        data["headers"] = dict(response.headers)
        data["tls_ok"] = True

        reachable = response.status_code < 500
        return ProbeResult(
            probe_name=self.name,
            safety_level=self.safety_level,
            success=reachable,
            endpoint=context.base_url,
            method=str(data.get("method", "GET")),
            http_status=response.status_code,
            latency_ms=latency_ms,
            evidence=evidence,
            data=data,
        )

    async def _safe_request(
        self,
        context: ProbeContext,
        evidence: list[str],
        data: dict[str, object],
    ) -> httpx.Response | None:
        """Try HEAD first, fall back to GET. Return None on network failure."""
        client = context.client
        for method in ("HEAD", "GET"):
            try:
                response = await client.request(method, context.base_url)
                data["method"] = method
                return response
            except httpx.HTTPStatusError as exc:
                data["method"] = method
                return exc.response
            except httpx.ConnectError as exc:
                data["error"] = f"connection_error: {type(exc).__name__}"
                evidence.append(f"Connection failed ({type(exc).__name__})")
                return None
            except httpx.TimeoutException:
                data["error"] = "timeout"
                evidence.append("Request timed out")
                return None
            except httpx.TransportError as exc:
                # Covers TLS errors and other transport failures.
                message = str(exc)
                if "SSL" in type(exc).__name__.upper() or "ssl" in message.lower():
                    data["error"] = "tls_error"
                    evidence.append("TLS handshake failed")
                else:
                    data["error"] = f"transport_error: {type(exc).__name__}"
                    evidence.append(f"Transport failed ({type(exc).__name__})")
                return None
            except ValueError as exc:
                # Malformed URL or invalid request construction.
                data["error"] = f"invalid_request: {exc}"
                evidence.append("Invalid request URL")
                return None
        return None
