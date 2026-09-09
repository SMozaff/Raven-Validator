"""SQLAlchemy ORM models — no secrets ever stored here."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class APICandidateRecord(Base):
    __tablename__ = "api_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    provider_hint: Mapped[str | None] = mapped_column(String(128))
    protocol_hint: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    credential_profile_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list[ValidationRunRecord]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class ValidationRunRecord(Base):
    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("api_candidates.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mode: Mapped[str] = mapped_column(String(32), default="standard")
    status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    reachable: Mapped[bool | None] = mapped_column(Boolean)
    detected_protocol: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    candidate: Mapped[APICandidateRecord] = relationship(back_populates="runs")
    probe_results: Mapped[list[ProbeResultRecord]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    errors: Mapped[list[ValidationErrorRecord]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ProbeResultRecord(Base):
    __tablename__ = "probe_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_runs.id"), nullable=False)
    probe_type: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str | None] = mapped_column(String(32))
    http_status: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    safe_response_excerpt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[ValidationRunRecord] = relationship(back_populates="probe_results")


class CapabilitySnapshotRecord(Base):
    __tablename__ = "capability_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_runs.id"), nullable=False)
    models: Mapped[bool | None] = mapped_column(Boolean)
    chat_completions: Mapped[bool | None] = mapped_column(Boolean)
    responses: Mapped[bool | None] = mapped_column(Boolean)
    streaming: Mapped[bool | None] = mapped_column(Boolean)
    embeddings: Mapped[bool | None] = mapped_column(Boolean)
    images: Mapped[bool | None] = mapped_column(Boolean)
    audio: Mapped[bool | None] = mapped_column(Boolean)


class ModelSnapshotRecord(Base):
    __tablename__ = "model_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_runs.id"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256))


class RateLimitSnapshotRecord(Base):
    __tablename__ = "rate_limit_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_runs.id"), nullable=False)
    known: Mapped[bool] = mapped_column(Boolean, default=False)
    limit: Mapped[int | None] = mapped_column(Integer)
    remaining: Mapped[int | None] = mapped_column(Integer)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(String(256))


class QuotaSnapshotRecord(Base):
    __tablename__ = "quota_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_runs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    known: Mapped[bool] = mapped_column(Boolean, default=False)
    balance: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)


class CredentialProfileRecord(Base):
    """Profile metadata only — secret lives in OS keychain."""

    __tablename__ = "credential_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(32), default="bearer")
    header_name: Mapped[str | None] = mapped_column(String(128))
    keychain_service: Mapped[str] = mapped_column(String(256), default="raven-validator")
    keychain_username: Mapped[str] = mapped_column(String(256), nullable=False)


class ValidationErrorRecord(Base):
    __tablename__ = "validation_errors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_runs.id"), nullable=False)
    probe_type: Mapped[str | None] = mapped_column(String(64))
    error_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)

    run: Mapped[ValidationRunRecord] = relationship(back_populates="errors")
