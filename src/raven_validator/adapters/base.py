"""Protocol detection and adapter base contract."""

from dataclasses import dataclass
from typing import Protocol

from raven_validator.probes.base import ProbeContext, ProbeResult


@dataclass
class DetectionResult:
    """Output of protocol detection — always evidence-based."""

    protocol: str  # openai-compatible | anthropic-compatible | generic-rest | unknown
    confidence: float  # 0.0-1.0
    evidence: list[str]
    adapter_name: str | None = None


class APIAdapter(Protocol):
    """Contract every protocol adapter must satisfy."""

    name: str

    async def detect(self, context: ProbeContext) -> DetectionResult:
        """Return protocol detection with confidence and evidence."""
        ...

    async def probe_public(self, context: ProbeContext) -> list[ProbeResult]:
        """Run public (READ_ONLY) probes for this protocol."""
        ...

    async def probe_authorized(
        self,
        context: ProbeContext,
        credential: str,
    ) -> list[ProbeResult]:
        """Run authorized probes — only when user supplied a credential."""
        ...

    def normalize_error(self, response: object) -> str:
        """Map a provider-specific error response to a normalized message."""
        ...


def clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))
