"""SQLite persistence: candidate/profile metadata and secret-free result JSON."""
from __future__ import annotations

import json
from pathlib import Path
from sqlalchemy import String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from raven_validator.domain.candidates import APICandidate
from raven_validator.domain.credentials import AuthScheme, CredentialProfile
from raven_validator.domain.results import ValidationResult


class Base(DeclarativeBase): pass


class CandidateRow(Base):
    __tablename__ = "api_candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class CredentialProfileRow(Base):
    __tablename__ = "credential_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    auth_type: Mapped[str] = mapped_column(String(32))
    header_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    keychain_service: Mapped[str] = mapped_column(Text)
    keychain_username: Mapped[str] = mapped_column(Text)


class ResultRow(Base):
    __tablename__ = "validation_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(String(36), index=True)
    payload: Mapped[str] = mapped_column(Text)


class Database:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine)

    def save_candidate(self, c: APICandidate) -> None:
        with Session(self.engine) as s:
            s.merge(CandidateRow(id=str(c.id), payload=c.model_dump_json())); s.commit()

    def list_candidates(self) -> list[APICandidate]:
        with Session(self.engine) as s:
            return [APICandidate(**json.loads(r.payload)) for r in s.scalars(select(CandidateRow)).all()]

    def delete_candidate(self, candidate_id: str) -> None:
        with Session(self.engine) as s:
            row = s.get(CandidateRow, candidate_id)
            if row: s.delete(row); s.commit()

    def save_profile(self, p: CredentialProfile) -> None:
        with Session(self.engine) as s:
            s.merge(CredentialProfileRow(id=p.id, display_name=p.display_name, auth_type=p.auth_type.value, header_name=p.header_name, keychain_service=p.keychain_service, keychain_username=p.keychain_username)); s.commit()

    def list_profiles(self) -> list[CredentialProfile]:
        with Session(self.engine) as s:
            rows = s.scalars(select(CredentialProfileRow)).all()
            return [CredentialProfile(id=r.id, display_name=r.display_name, auth_type=AuthScheme(r.auth_type), header_name=r.header_name, keychain_service=r.keychain_service, keychain_username=r.keychain_username) for r in rows]

    def get_profile(self, profile_id: str) -> CredentialProfile | None:
        with Session(self.engine) as s:
            r = s.get(CredentialProfileRow, profile_id)
            return None if r is None else CredentialProfile(id=r.id, display_name=r.display_name, auth_type=AuthScheme(r.auth_type), header_name=r.header_name, keychain_service=r.keychain_service, keychain_username=r.keychain_username)

    def delete_profile(self, profile_id: str) -> None:
        with Session(self.engine) as s:
            r = s.get(CredentialProfileRow, profile_id)
            if r: s.delete(r); s.commit()

    def save_result(self, r: ValidationResult) -> None:
        with Session(self.engine) as s:
            s.merge(ResultRow(id=str(r.run_id), candidate_id=str(r.candidate_id), payload=r.model_dump_json())); s.commit()

    def list_results(self) -> list[ValidationResult]:
        with Session(self.engine) as s:
            return [ValidationResult(**json.loads(r.payload)) for r in s.scalars(select(ResultRow)).all()]
