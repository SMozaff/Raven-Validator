"""Quota / credit probe — optional, evidence-driven.

Must be visibly optional in GUI (default off). When enabled and an
authorized credential exists, use only a documented quota/usage/balance
endpoint or explicit quota info from a normal authorized response.

Never infer balance by consuming requests.
"""

from __future__ import annotations

import httpx

from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel


class QuotaProbe:
    """Optional quota/balance inspection (CUSTOM_AUTHORIZED)."""

    name = "quota"
    safety_level = ProbeSafetyLevel.CUSTOM_AUTHORIZED

    # Provider-specific documented quota endpoints (tried in order).
    QUOTA_PATHS = (
        "/v1/usage",
        "/v1/billing/usage",
        "/v1/dashboard/billing/usage",
        "/v1/account/usage",
        "/v1/balance",
        "/v1/credits",
    )

    async def run(self, context: ProbeContext) -> ProbeResult:
        if not context.credential:
            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=False,
                evidence=["No authorized credential — quota check skipped"],
                data={
                    "known": False,
                    "status": "UNKNOWN",
                    "reason": "No authorized credential configured",
                },
                error="credential_required",
            )

        base = context.base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {context.credential}"}
        custom = context.options.get("headers")
        if isinstance(custom, dict):
            headers.update(custom)  # type: ignore[arg-type]

        # Allow explicit override (e.g., provider documents /v1/billing/credit_grants).
        explicit = context.options.get("quota_endpoint")
        paths: tuple[str, ...] = (str(explicit),) if explicit else self.QUOTA_PATHS

        last_error: str | None = None
        for path in paths:
            url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
            try:
                response = await context.client.get(url, headers=headers)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue

            if response.status_code in (404, 501):
                last_error = f"HTTP {response.status_code}: no quota endpoint at {path}"
                continue

            if response.status_code == 401:
                return ProbeResult(
                    probe_name=self.name,
                    safety_level=self.safety_level,
                    success=False,
                    endpoint=url,
                    method="GET",
                    http_status=401,
                    evidence=["Quota endpoint returned 401 — invalid credential"],
                    data={
                        "known": False,
                        "status": "UNKNOWN",
                        "reason": "Invalid credential",
                    },
                    error="invalid_credential",
                )

            if response.status_code == 429:
                body_text = response.text.lower()
                credit_markers = ("insufficient", "quota", "credit", "balance", "billing")
                if any(m in body_text for m in credit_markers):
                    return ProbeResult(
                        probe_name=self.name,
                        safety_level=self.safety_level,
                        success=True,
                        endpoint=url,
                        method="GET",
                        http_status=429,
                        evidence=["Quota endpoint indicates insufficient credits"],
                        data={
                            "known": True,
                            "status": "INSUFFICIENT",
                            "balance": 0,
                            "excerpt": response.text[:500],
                        },
                    )

            if response.status_code not in (200, 201):
                last_error = f"HTTP {response.status_code}"
                continue

            try:
                body_obj = response.json()
            except ValueError:
                last_error = "malformed JSON from quota endpoint"
                continue

            parsed = self._parse_quota_body(body_obj)
            if parsed is None:
                last_error = "quota endpoint returned unexpected shape"
                continue

            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=True,
                endpoint=url,
                method="GET",
                http_status=response.status_code,
                evidence=[f"Quota: {parsed['status']}"],
                data={**parsed, "headers": dict(response.headers)},
            )

        return ProbeResult(
            probe_name=self.name,
            safety_level=self.safety_level,
            success=False,
            endpoint=f"{base}{paths[0]}",
            method="GET",
            evidence=["No supported quota/balance endpoint"],
            data={
                "known": False,
                "status": "UNKNOWN",
                "reason": "Provider exposes no supported quota/balance endpoint",
            },
            error=last_error,
        )

    @staticmethod
    def _parse_quota_body(body: object) -> dict[str, object] | None:
        if not isinstance(body, dict):
            return None
        # Common shapes:
        # {"total_granted": 10, "total_used": 3, "total_available": 7}
        # {"balance": 5.2, "unit": "USD"}
        # {"credits": 42}
        # {"data": {"balance": ...}}
        candidate = body
        if isinstance(body.get("data"), dict):
            candidate = body["data"]  # type: ignore[assignment]

        for bal_key in (
            "total_available",
            "balance",
            "remaining",
            "credits",
            "available",
        ):
            val = candidate.get(bal_key)
            if isinstance(val, (int, float)):
                unit = candidate.get("unit") or candidate.get("currency") or "credits"
                return {
                    "known": True,
                    "status": "KNOWN",
                    "balance": float(val),
                    "unit": str(unit),
                }

        # Explicit insufficient marker
        if any(k in candidate for k in ("insufficient", "exhausted")):
            return {"known": True, "status": "INSUFFICIENT", "balance": 0}

        return None
