"""Credential profiles and protocol-correct auth header construction."""
from __future__ import annotations

import base64
from raven_validator.credentials.keychain import OSKeychain, SecretBackend
from raven_validator.domain.credentials import AuthScheme, CredentialProfile


class CredentialManager:
    def __init__(self, backend: SecretBackend | None = None) -> None:
        self.backend = backend or OSKeychain()

    def store_secret(self, profile: CredentialProfile, secret: str) -> None:
        self.backend.set(profile.keychain_service, profile.keychain_username, secret)

    def retrieve_secret(self, profile: CredentialProfile) -> str | None:
        return self.backend.get(profile.keychain_service, profile.keychain_username)

    def delete_secret(self, profile: CredentialProfile) -> None:
        self.backend.delete(profile.keychain_service, profile.keychain_username)

    @staticmethod
    def build_headers(profile: CredentialProfile, secret: str) -> dict[str, str]:
        if profile.auth_type == AuthScheme.BEARER:
            return {"Authorization": f"Bearer {secret}"}
        if profile.auth_type == AuthScheme.API_KEY_HEADER:
            return {profile.header_name or "x-api-key": secret}
        if profile.auth_type == AuthScheme.BASIC:
            encoded = base64.b64encode(secret.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        if profile.auth_type == AuthScheme.CUSTOM_HEADER:
            return {profile.header_name or "Authorization": secret}
        return {}
