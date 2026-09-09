from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from raven_validator.domain.statuses import ValidationStatus


class RateLimitInfo(BaseModel):
    known: bool = False
    limit: int | None = None
    remaining: int | None = None
    reset_at: str | None = None
    retry_after: float | None = None


class QuotaInfo(BaseModel):
    status: str = "NOT_TESTED"
    known: bool = False
    balance: float | None = None
    unit: str | None = None
    reason: str | None = None


class ValidationError(BaseModel):
    probe: str
    message: str
    http_status: int | None = None


class ValidationResult(BaseModel):
    candidate_id: UUID
    run_id: UUID
    base_url: str
    overall_status: ValidationStatus = ValidationStatus.UNKNOWN
    reachable: bool | None = None
    detected_protocol: str = "unknown"
    protocol_confidence: float = 0.0
    auth_required: bool | None = None
    auth_scheme: str | None = None
    credential_configured: bool = False
    credential_used: bool = False
    authorized_test_succeeded: bool = False
    models: list[str] = Field(default_factory=list)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    latency_ms: float | None = None
    rate_limit: RateLimitInfo = Field(default_factory=RateLimitInfo)
    quota: QuotaInfo = Field(default_factory=QuotaInfo)
    request_count: int = 0
    evidence: list[str] = Field(default_factory=list)
    errors: list[ValidationError] = Field(default_factory=list)
    tested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
