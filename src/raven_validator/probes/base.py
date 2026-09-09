"""Probe contract: base types for all validation probes."""

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from raven_validator.domain.candidates import APICandidate
from raven_validator.security.redaction import redact_excerpt, redact_headers
from raven_validator.security.request_policy import ProbeSafetyLevel
from raven_validator.utils.dates import utc_now


@dataclass
class ProbeContext:
    """Inputs available to every probe run."""

    candidate: APICandidate
    client: httpx.AsyncClient
    base_url: str
    credential: str | None = None
    credential_scheme: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeResult:
    """Outcome of a single probe execution."""

    probe_name: str
    safety_level: ProbeSafetyLevel
    success: bool
    endpoint: str | None = None
    method: str | None = None
    http_status: int | None = None
    latency_ms: float | None = None
    evidence: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    tested_at: Any = field(default_factory=utc_now)

    def safe_excerpt(self, max_length: int = 500) -> str:
        """Redacted diagnostic excerpt safe for DB/GUI/export."""
        raw = str(self.data.get("excerpt", ""))
        return redact_excerpt(raw, max_length)

    def safe_headers(self) -> dict[str, str]:
        """Redacted copy of any captured response headers."""
        headers = self.data.get("headers", {})
        if isinstance(headers, dict):
            return redact_headers(dict(headers))
        return {}


class Probe(Protocol):
    """Contract every probe must satisfy."""

    name: str
    safety_level: ProbeSafetyLevel

    async def run(self, context: ProbeContext) -> ProbeResult:
        """Execute the probe and return a normalized result."""
        ...
