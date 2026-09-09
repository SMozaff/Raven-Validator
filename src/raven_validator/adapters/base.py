"""Protocol adapter contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from raven_validator.core.http_client import BudgetedSafeClient
from raven_validator.domain.candidates import APICandidate


@dataclass
class DetectionResult:
    protocol: str
    confidence: float
    evidence: list[str] = field(default_factory=list)


@dataclass
class ProbeOutcome:
    name: str
    success: bool
    http_status: int | None = None
    latency_ms: float | None = None
    data: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class PublicContext:
    """No credential field by design."""
    candidate: APICandidate
    client: BudgetedSafeClient
    base_url: str


@dataclass
class AuthorizedContext:
    candidate: APICandidate
    client: BudgetedSafeClient
    base_url: str
    auth_headers: dict[str, str]
    model: str | None = None


class APIAdapter(Protocol):
    name: str
    async def detect(self, context: PublicContext) -> DetectionResult: ...
    async def public_models(self, context: PublicContext) -> ProbeOutcome: ...
    async def authorized_models(self, context: AuthorizedContext) -> ProbeOutcome: ...
    async def generate(self, context: AuthorizedContext) -> ProbeOutcome: ...
    async def stream(self, context: AuthorizedContext) -> ProbeOutcome: ...
    async def quota(self, context: AuthorizedContext) -> ProbeOutcome: ...
