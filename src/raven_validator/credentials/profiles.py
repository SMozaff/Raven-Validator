"""Credential profile store — metadata only, no secrets."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from raven_validator.credentials.keychain import KeychainBackend, fingerprint
from raven_validator.domain.credentials import AuthScheme


class CredentialProfileRecord(BaseModel):
    """Persisted profile metadata. Raw secret lives in keychain only."""

    id: UUID = Field(default_factory=uuid4)
    display_name: str
    auth_type: AuthScheme = AuthScheme.BEARER
    header_name: str | None = None
    keychain_service: str = "raven-validator"
    keychain_username: str = ""

    @property
    def fingerprint_label(self) -> str:
        """Placeholder label shown after creation; replaced once secret is stored."""
        return "••••••••----"

    def model_dump_safe(self) -> dict[str, object]:
        """Dict for SQLite/logging/export — guaranteed secret-free."""
        data = self.model_dump(mode="json")
        # Defensive: strip anything credential-like if fields evolve.
        data.pop("secret", None)
        data.pop("api_key", None)
        data.pop("token", None)
        return data


class CredentialProfileStore:
    """In-memory store for profiles (SQLite-backed in M6)."""

    def __init__(self, keychain: KeychainBackend | None = None) -> None:
        self._profiles: dict[UUID, CredentialProfileRecord] = {}
        self._keychain = keychain or KeychainBackend()
        self._keychain.enable_memory_backend()

    # -- CRUD (metadata only) --

    def create(
        self,
        display_name: str,
        auth_type: AuthScheme = AuthScheme.BEARER,
        header_name: str | None = None,
        secret: str | None = None,
    ) -> CredentialProfileRecord:
        profile = CredentialProfileRecord(
            display_name=display_name,
            auth_type=auth_type,
            header_name=header_name,
            keychain_username=str(uuid4()),
        )
        self._profiles[profile.id] = profile
        if secret is not None:
            self._keychain.store_secret(
                profile.keychain_service, profile.keychain_username, secret
            )
        return profile

    def get(self, profile_id: UUID) -> CredentialProfileRecord | None:
        return self._profiles.get(profile_id)

    def list_all(self) -> list[CredentialProfileRecord]:
        return list(self._profiles.values())

    def update_metadata(
        self,
        profile_id: UUID,
        display_name: str | None = None,
        auth_type: AuthScheme | None = None,
        header_name: str | None = None,
    ) -> CredentialProfileRecord:
        profile = self._profiles[profile_id]
        if display_name is not None:
            profile.display_name = display_name
        if auth_type is not None:
            profile.auth_type = auth_type
        if header_name is not None:
            profile.header_name = header_name
        return profile

    def replace_secret(self, profile_id: UUID, secret: str) -> None:
        profile = self._profiles[profile_id]
        self._keychain.store_secret(
            profile.keychain_service, profile.keychain_username, secret
        )

    def delete(self, profile_id: UUID) -> None:
        profile = self._profiles.pop(profile_id, None)
        if profile is not None:
            self._keychain.delete_secret(
                profile.keychain_service, profile.keychain_username
            )

    def get_secret(self, profile_id: UUID) -> str | None:
        profile = self._profiles.get(profile_id)
        if profile is None:
            return None
        return self._keychain.retrieve_secret(
            profile.keychain_service, profile.keychain_username
        )

    def get_fingerprint(self, profile_id: UUID) -> str:
        secret = self.get_secret(profile_id)
        if secret is None:
            return "Not configured"
        return fingerprint(secret)
