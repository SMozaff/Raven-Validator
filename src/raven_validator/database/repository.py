"""Repository — typed CRUD over the ORM models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from raven_validator.database.models import (
    APICandidateRecord,
    CapabilitySnapshotRecord,
    CredentialProfileRecord,
    ModelSnapshotRecord,
    ProbeResultRecord,
    QuotaSnapshotRecord,
    RateLimitSnapshotRecord,
    ValidationErrorRecord,
    ValidationRunRecord,
)
from raven_validator.domain.candidates import APICandidate
from raven_validator.domain.results import ValidationResult
from raven_validator.security.redaction import redact_excerpt


class Repository:
    """Thin, testable data-access layer."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- candidates --

    def save_candidate(self, candidate: APICandidate) -> APICandidateRecord:
        record = APICandidateRecord(
            id=str(candidate.id),
            name=candidate.name,
            base_url=str(candidate.base_url),
            provider_hint=candidate.provider_hint,
            protocol_hint=candidate.protocol_hint,
            source_url=str(candidate.source_url) if candidate.source_url else None,
            source_type=candidate.source_type,
            notes=candidate.notes,
            credential_profile_id=(
                str(candidate.credential_profile_id) if candidate.credential_profile_id else None
            ),
        )
        self.session.merge(record)
        self.session.flush()
        return record

    def get_candidate(self, candidate_id: UUID) -> APICandidateRecord | None:
        return self.session.get(APICandidateRecord, str(candidate_id))

    def list_candidates(self) -> list[APICandidateRecord]:
        return list(
            self.session.query(APICandidateRecord).order_by(APICandidateRecord.created_at).all()
        )

    def delete_candidate(self, candidate_id: UUID) -> None:
        record = self.get_candidate(candidate_id)
        if record is not None:
            self.session.delete(record)
            self.session.flush()

    # -- runs --

    def create_run(
        self,
        candidate_id: UUID,
        mode: str = "standard",
        run_id: UUID | None = None,
    ) -> ValidationRunRecord:
        rid = str(run_id or uuid4())
        record = ValidationRunRecord(
            id=rid,
            candidate_id=str(candidate_id),
            mode=mode,
            status="UNKNOWN",
        )
        self.session.add(record)
        self.session.flush()
        return record

    def update_run(self, run_id: UUID, **fields: object) -> ValidationRunRecord | None:
        record = self.session.get(ValidationRunRecord, str(run_id))
        if record is None:
            return None
        for key, value in fields.items():
            setattr(record, key, value)
        if "completed_at" not in fields and any(k in fields for k in ("status", "reachable")):
            record.completed_at = datetime.now(UTC)
        self.session.flush()
        return record

    def get_run(self, run_id: UUID) -> ValidationRunRecord | None:
        return self.session.get(ValidationRunRecord, str(run_id))

    def list_runs_for_candidate(self, candidate_id: UUID) -> list[ValidationRunRecord]:
        return list(
            self.session.query(ValidationRunRecord)
            .filter(ValidationRunRecord.candidate_id == str(candidate_id))
            .order_by(ValidationRunRecord.started_at.desc())
            .all()
        )

    # -- probe results --

    def save_probe_result(
        self,
        run_id: UUID,
        probe_type: str,
        endpoint: str | None = None,
        method: str | None = None,
        status: str | None = None,
        http_status: int | None = None,
        latency_ms: float | None = None,
        excerpt: str | None = None,
    ) -> ProbeResultRecord:
        record = ProbeResultRecord(
            id=str(uuid4()),
            run_id=str(run_id),
            probe_type=probe_type,
            endpoint=endpoint,
            method=method,
            status=status,
            http_status=http_status,
            latency_ms=latency_ms,
            safe_response_excerpt=redact_excerpt(excerpt or "", max_length=2000) if excerpt else None,
        )
        self.session.add(record)
        self.session.flush()
        return record

    # -- snapshots --

    def save_capability_snapshot(self, run_id: UUID, **caps: bool | None) -> CapabilitySnapshotRecord:
        record = CapabilitySnapshotRecord(id=str(uuid4()), run_id=str(run_id), **caps)  # type: ignore[arg-type]
        self.session.add(record)
        self.session.flush()
        return record

    def save_model_snapshots(self, run_id: UUID, models: list[str]) -> list[ModelSnapshotRecord]:
        records: list[ModelSnapshotRecord] = []
        for mid in models:
            rec = ModelSnapshotRecord(id=str(uuid4()), run_id=str(run_id), model_id=mid)
            self.session.add(rec)
            records.append(rec)
        self.session.flush()
        return records

    def save_rate_limit_snapshot(
        self,
        run_id: UUID,
        known: bool = False,
        limit: int | None = None,
        remaining: int | None = None,
        reset_at: datetime | None = None,
        source: str | None = None,
    ) -> RateLimitSnapshotRecord:
        record = RateLimitSnapshotRecord(
            id=str(uuid4()),
            run_id=str(run_id),
            known=known,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            source=source,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def save_quota_snapshot(
        self,
        run_id: UUID,
        status: str = "UNKNOWN",
        known: bool = False,
        balance: float | None = None,
        unit: str | None = None,
        reason: str | None = None,
    ) -> QuotaSnapshotRecord:
        record = QuotaSnapshotRecord(
            id=str(uuid4()),
            run_id=str(run_id),
            status=status,
            known=known,
            balance=balance,
            unit=unit,
            reason=reason,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def save_error(
        self,
        run_id: UUID,
        error_type: str,
        message: str,
        probe_type: str | None = None,
        details: str | None = None,
    ) -> ValidationErrorRecord:
        # Never persist raw secrets — redact the message.
        redacted = redact_excerpt(message, max_length=2000)
        record = ValidationErrorRecord(
            id=str(uuid4()),
            run_id=str(run_id),
            probe_type=probe_type,
            error_type=error_type,
            message=redacted,
            details=redact_excerpt(details, max_length=2000) if details else None,
        )
        self.session.add(record)
        self.session.flush()
        return record

    # -- credential profiles (metadata only) --

    def save_credential_profile(
        self,
        profile_id: UUID,
        display_name: str,
        auth_type: str = "bearer",
        header_name: str | None = None,
        keychain_service: str = "raven-validator",
        keychain_username: str = "",
    ) -> CredentialProfileRecord:
        record = CredentialProfileRecord(
            id=str(profile_id),
            display_name=display_name,
            auth_type=auth_type,
            header_name=header_name,
            keychain_service=keychain_service,
            keychain_username=keychain_username,
        )
        self.session.merge(record)
        self.session.flush()
        return record

    def get_credential_profile(self, profile_id: UUID) -> CredentialProfileRecord | None:
        return self.session.get(CredentialProfileRecord, str(profile_id))

    def list_credential_profiles(self) -> list[CredentialProfileRecord]:
        return list(self.session.query(CredentialProfileRecord).all())

    def delete_credential_profile(self, profile_id: UUID) -> None:
        record = self.get_credential_profile(profile_id)
        if record is not None:
            self.session.delete(record)
            self.session.flush()

    # -- convenience: persist a full ValidationResult --

    def save_validation_result(self, result: ValidationResult, mode: str = "standard") -> ValidationRunRecord:
        run = self.create_run(result.candidate_id, mode=mode, run_id=result.run_id)
        run.status = result.overall_status.value
        run.reachable = result.reachable
        run.detected_protocol = result.detected_protocol
        run.confidence = result.confidence
        run.request_count = len(result.errors)  # placeholder; engine tracks real count
        run.error_count = len(result.errors)
        run.completed_at = result.tested_at
        self.session.flush()

        caps = result.capabilities
        self.save_capability_snapshot(
            result.run_id,
            models=caps.models,
            chat_completions=caps.chat_completions,
            responses=caps.responses,
            streaming=caps.streaming,
            embeddings=caps.embeddings,
            images=caps.images,
            audio=caps.audio,
        )
        if result.models:
            self.save_model_snapshots(result.run_id, result.models)
        self.save_rate_limit_snapshot(
            result.run_id,
            known=result.rate_limit.known,
            limit=result.rate_limit.limit,
            remaining=result.rate_limit.remaining,
            reset_at=result.rate_limit.reset_at,
            source=result.rate_limit.source,
        )
        self.save_quota_snapshot(
            result.run_id,
            status="KNOWN" if result.quota.known else "UNKNOWN",
            known=result.quota.known,
            balance=result.quota.balance,
            unit=result.quota.unit,
            reason=result.quota.reason,
        )
        for err in result.errors:
            self.save_error(result.run_id, error_type=err.error_type, message=err.message, details=err.details)
        return run
