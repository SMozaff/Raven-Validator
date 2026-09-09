"""OS keychain abstraction — raw secrets live ONLY here.

Wraps `keyring` with a testable backend interface. Never logs or
returns a secret except to an authorized caller that immediately
uses it for a single authenticated request.
"""

from __future__ import annotations

import hashlib

import keyring
import keyring.errors


class KeychainError(RuntimeError):
    """Keychain is unavailable or the operation failed."""


class KeychainBackend:
    """Thin wrapper over `keyring` with a pluggable in-memory fallback for tests."""

    def __init__(self, service_prefix: str = "raven-validator") -> None:
        self.service_prefix = service_prefix
        self._memory: dict[tuple[str, str], str] = {}
        self._use_memory = False

    def enable_memory_backend(self) -> None:
        """Use in-memory store (tests / CI without a system keychain)."""
        self._use_memory = True

    # -- core ops --

    def store_secret(self, service: str, username: str, secret: str) -> None:
        if self._use_memory:
            self._memory[(service, username)] = secret
            return
        try:
            keyring.set_password(service, username, secret)
        except keyring.errors.KeyringError as exc:
            raise KeychainError(str(exc)) from exc

    def retrieve_secret(self, service: str, username: str) -> str | None:
        if self._use_memory:
            return self._memory.get((service, username))
        try:
            return keyring.get_password(service, username)
        except keyring.errors.KeyringError as exc:
            raise KeychainError(str(exc)) from exc

    def delete_secret(self, service: str, username: str) -> None:
        if self._use_memory:
            self._memory.pop((service, username), None)
            return
        try:
            keyring.delete_password(service, username)
        except keyring.errors.PasswordDeleteError:
            pass
        except keyring.errors.KeyringError as exc:
            raise KeychainError(str(exc)) from exc


def fingerprint(secret: str) -> str:
    """Return a masked fingerprint like ••••••••7A2F for GUI display.

    Derived via SHA-256 so it never leaks the secret, but still
    lets the user confirm which key is configured.
    """
    if not secret:
        return "••••••••----"
    digest = hashlib.sha256(secret.encode()).hexdigest().upper()[:4]
    return f"••••••••{digest}"


# Singleton for app use; tests create their own instances.
_default_backend: KeychainBackend | None = None


def get_keychain() -> KeychainBackend:
    global _default_backend
    if _default_backend is None:
        _default_backend = KeychainBackend()
    return _default_backend
