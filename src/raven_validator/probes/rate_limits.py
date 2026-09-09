"""Rate-limit probe — parses common rate-limit headers.

Never intentionally exhausts limits. Normalizes into known/limit/
remaining/reset_at/source without making extra requests.
"""

from __future__ import annotations

from datetime import UTC, datetime

from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel


def _get_header(headers: dict[str, str], *candidates: str) -> str | None:
    lowered = {k.lower(): v for k, v in headers.items()}
    for c in candidates:
        val = lowered.get(c.lower())
        if val is not None:
            return val
    return None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _parse_reset(value: str | None) -> datetime | None:
    if value is None:
        return None
    value = value.strip()
    # Numeric: unix timestamp or seconds-until-reset.
    try:
        num = int(value)
        # Heuristic: large values are unix timestamps.
        if num > 1_000_000_000:
            return datetime.fromtimestamp(num, tz=UTC)
        # Small values are delta seconds — not converting to absolute without now().
        return None
    except ValueError:
        pass
    # HTTP-date.
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


class RateLimitProbe:
    """Inspect rate-limit headers from any safe response."""

    name = "rate_limits"
    safety_level = ProbeSafetyLevel.READ_ONLY

    async def run(self, context: ProbeContext) -> ProbeResult:
        url = context.base_url
        headers: dict[str, str] = {}
        if context.credential:
            scheme = (context.credential_scheme or "bearer").lower()
            if scheme == "bearer":
                headers["Authorization"] = f"Bearer {context.credential}"

        try:
            response = await context.client.get(url, headers=headers or None)
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=False,
                endpoint=url,
                method="GET",
                error=str(exc),
                evidence=[f"Rate-limit check failed: {type(exc).__name__}"],
            )

        resp_headers = dict(response.headers)
        lowered = {k.lower(): v for k, v in resp_headers.items()}

        limit = _parse_int(
            _get_header(resp_headers, "X-RateLimit-Limit", "RateLimit-Limit")
        )
        remaining = _parse_int(
            _get_header(resp_headers, "X-RateLimit-Remaining", "RateLimit-Remaining")
        )
        retry_after = _get_header(resp_headers, "Retry-After")
        reset_raw = _get_header(resp_headers, "X-RateLimit-Reset", "RateLimit-Reset")
        reset_at = _parse_reset(reset_raw)

        known = any(v is not None for v in (limit, remaining, retry_after, reset_raw))
        # Also consider provider-specific headers as known.
        if not known:
            for k in lowered:
                if "ratelimit" in k or k == "retry-after":
                    known = True
                    break

        evidence: list[str] = []
        if known:
            parts: list[str] = []
            if limit is not None:
                parts.append(f"limit={limit}")
            if remaining is not None:
                parts.append(f"remaining={remaining}")
            if retry_after is not None:
                parts.append(f"retry_after={retry_after}")
            header_summary = ", ".join(parts) if parts else "Rate-limit headers present"
            evidence.append(f"Rate-limit headers: {header_summary}" if parts else header_summary)
        else:
            evidence.append("No rate-limit headers found")

        # Determine source label.
        sources: list[str] = []
        for k in resp_headers:
            lk = k.lower()
            if "ratelimit" in lk or lk == "retry-after":
                sources.append(k)
        source = ", ".join(sources) if sources else None

        data: dict[str, object] = {
            "known": known,
            "limit": limit,
            "remaining": remaining,
            "reset_at": reset_at.isoformat() if reset_at else None,
            "retry_after": retry_after,
            "source": source,
            "headers": resp_headers,
        }

        return ProbeResult(
            probe_name=self.name,
            safety_level=self.safety_level,
            success=True,
            endpoint=url,
            method="GET",
            http_status=response.status_code,
            evidence=evidence,
            data=data,  # type: ignore[arg-type]
        )
