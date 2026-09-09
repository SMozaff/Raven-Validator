"""OS keychain backend; memory backend exists only for tests/injection."""
from __future__ import annotations

import hashlib
from typing import Protocol


class KeychainError(RuntimeError):
    pass


class SecretBackend(Protocol):
    def set(self, service: str, username: str, secret: str) -> None: ...
    def get(self, service: str, username: str) -> str | None: ...
    def delete(self, service: str, username: str) -> None: ...


class OSKeychain:
    def _keyring(self):
        try:
            import keyring
            import keyring.errors
        except ImportError as exc:
            raise KeychainError("keyring package is unavailable") from exc
        return keyring

    def set(self, service: str, username: str, secret: str) -> None:
        kr = self._keyring()
        try:
            kr.set_password(service, username, secret)
        except Exception as exc:  # backend-specific errors
            raise KeychainError(str(exc)) from exc

    def get(self, service: str, username: str) -> str | None:
        kr = self._keyring()
        try:
            return kr.get_password(service, username)
        except Exception as exc:
            raise KeychainError(str(exc)) from exc

    def delete(self, service: str, username: str) -> None:
        kr = self._keyring()
        try:
            kr.delete_password(service, username)
        except Exception:
            # Deleting a missing key is idempotent for our UI.
            return


class MemoryKeychain:
    """Explicit test backend. Production GUI must never instantiate this implicitly."""
    def __init__(self) -> None:
        self.data: dict[tuple[str, str], str] = {}

    def set(self, service: str, username: str, secret: str) -> None:
        self.data[(service, username)] = secret

    def get(self, service: str, username: str) -> str | None:
        return self.data.get((service, username))

    def delete(self, service: str, username: str) -> None:
        self.data.pop((service, username), None)


def fingerprint(secret: str | None) -> str:
    if not secret:
        return "••••••••----"
    digest = hashlib.sha256(secret.encode()).hexdigest().upper()[:4]
    return f"••••••••{digest}"
