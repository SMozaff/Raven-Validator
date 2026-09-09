"""Normalized validation result model."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from raven_validator.domain.capabilities import CapabilityResult
from raven_validator.domain.statuses import ValidationStatus
from raven_validator.utils.dates import utc_now


class RateLimitResult(BaseModel):
    """Normalized rate-limit information."""

    known: bool = False
    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None
    source: str | None = None


class QuotaResult(BaseModel):
    """Normalized quota/credit information."""

    known: bool = False
    balance: float | None = None
    unit: str | None = None
    reason: str | None = None


class ValidationError(BaseModel):
    """Structured validation error."""

    error_type: str
    message: str
    details: str | None = None


class ValidationResult(BaseModel):
    """Evidence-based normalized result of validating one candidate."""

    candidate_id: UUID
    run_id: UUID

    reachable: bool | None = None
    overall_status: ValidationStatus = ValidationStatus.UNKNOWN

    detected_protocol: str | None = None
    protocol_confidence: float = 0.0

    auth_required: bool | None = None
    auth_scheme: str | None = None

    credential_configured: bool = False
    credential_used: bool = False

    capabilities: CapabilityResult = Field(default_factory=CapabilityResult)

    models: list[str] = Field(default_factory=list)

    latency_ms: float | None = None

    rate_limit: RateLimitResult = Field(default_factory=RateLimitResult)
    quota: QuotaResult = Field(default_factory=QuotaResult)

    errors: list[ValidationError] = Field(default_factory=list)

    confidence: float = 0.0
    tested_at: datetime = Field(default_factory=utc_now)
