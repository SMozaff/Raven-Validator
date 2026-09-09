"""High-level credential manager — the ONLY authorized path to secrets.

Discovered credential-like material (secret_detector) must NEVER reach
this module. Only user-configured profiles flow through here.
"""

from __future__ import annotations

from uuid import UUID

from raven_validator.credentials.keychain import KeychainBackend
from raven_validator.credentials.profiles import (
    CredentialProfileRecord,
    CredentialProfileStore,
)
from raven_validator.domain.credentials import AuthScheme
from raven_validator.security.redaction import redact_headers


class CredentialManager:
    """Facade over profile store + keychain for GUI and engine."""

    def __init__(
        self,
        store: CredentialProfileStore | None = None,
        keychain: KeychainBackend | None = None,
    ) -> None:
        self._keychain = keychain or KeychainBackend()
        self._store = store or CredentialProfileStore(keychain=self._keychain)

    # -- profile lifecycle (metadata only in return values) --

    def create_profile(
        self,
        display_name: str,
        secret: str,
        auth_type: AuthScheme = AuthScheme.BEARER,
        header_name: str | None = None,
    ) -> CredentialProfileRecord:
        return self._store.create(
            display_name=display_name,
            auth_type=auth_type,
            header_name=header_name,
            secret=secret,
        )

    def update_metadata(
        self,
        profile_id: UUID,
        display_name: str | None = None,
        auth_type: AuthScheme | None = None,
        header_name: str | None = None,
    ) -> CredentialProfileRecord:
        return self._store.update_metadata(
            profile_id, display_name=display_name, auth_type=auth_type, header_name=header_name
        )

    def replace_secret(self, profile_id: UUID, secret: str) -> None:
        self._store.replace_secret(profile_id, secret)

    def delete_profile(self, profile_id: UUID) -> None:
        self._store.delete(profile_id)

    def list_profiles(self) -> list[CredentialProfileRecord]:
        return self._store.list_all()

    def get_profile(self, profile_id: UUID) -> CredentialProfileRecord | None:
        return self._store.get(profile_id)

    def get_fingerprint(self, profile_id: UUID) -> str:
        return self._store.get_fingerprint(profile_id)

    # -- auth header injection (the only place secrets touch requests) --

    def build_auth_headers(
        self, profile_id: UUID, credential_override: str | None = None
    ) -> dict[str, str]:
        """Build Authorization headers for an outgoing request.

        If `credential_override` is supplied it is used directly (engine
        already retrieved it). Otherwise the keychain is consulted.
        """
        profile = self._store.get(profile_id)
        if profile is None:
            return {}
        secret = credential_override
        if secret is None:
            secret = self._store.get_secret(profile_id)
        if not secret:
            return {}

        if profile.auth_type == AuthScheme.BEARER:
            return {"Authorization": f"Bearer {secret}"}
        if profile.auth_type == AuthScheme.API_KEY_HEADER:
            header = profile.header_name or "x-api-key"
            return {header: secret}
        if profile.auth_type == AuthScheme.BASIC:
            import base64

            encoded = base64.b64encode(secret.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        if profile.auth_type == AuthScheme.CUSTOM_HEADER:
            header = profile.header_name or "Authorization"
            return {header: secret}
        # OAUTH / UNKNOWN / NONE — no automatic injection in V1.
        return {}

    def safe_headers_for_logging(
        self, profile_id: UUID, credential_override: str | None = None
    ) -> dict[str, str]:
        """Redacted copy of auth headers safe for logs."""
        headers = self.build_auth_headers(profile_id, credential_override)
        return redact_headers(headers)
