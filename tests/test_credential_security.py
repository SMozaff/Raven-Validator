"""Release-blocking credential security tests."""

import json
import logging

from raven_validator.credentials.keychain import KeychainBackend, fingerprint
from raven_validator.credentials.manager import CredentialManager
from raven_validator.credentials.profiles import CredentialProfileStore
from raven_validator.domain.credentials import AuthScheme
from raven_validator.security.redaction import redact_headers, redact_text
from raven_validator.security.secret_detector import detect_secrets
from raven_validator.utils.logging import RedactionFilter


def test_credential_never_stored_in_sqlite_dict() -> None:
    """Profile dict for SQLite/export must not contain the secret."""
    store = CredentialProfileStore()
    profile = store.create(display_name="Test", secret="sk-super-secret-12345")
    dumped = profile.model_dump_safe()
    assert "sk-super-secret-12345" not in json.dumps(dumped, default=str)
    assert "secret" not in dumped
    assert "token" not in dumped


def test_credential_never_logged() -> None:
    """Log filter must redact bearer/api-key material."""
    filt = RedactionFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer sk-super-secret-12345",
        args=(),
        exc_info=None,
    )
    filt.filter(record)
    assert "sk-super-secret-12345" not in record.msg  # type: ignore[operator]
    assert "[REDACTED]" in record.msg  # type: ignore[operator]


def test_credential_never_exported() -> None:
    """Manager's profile listing must be secret-free."""
    mgr = CredentialManager()
    mgr.create_profile("Export Test", secret="sk-export-me-999")
    for p in mgr.list_profiles():
        assert "sk-export-me-999" not in json.dumps(p.model_dump_safe(), default=str)
        assert "sk-export-me-999" not in json.dumps(p.model_dump(mode="json"), default=str)


def test_credential_absent_from_headers_for_logging() -> None:
    mgr = CredentialManager()
    profile = mgr.create_profile("Log Test", secret="sk-log-secret", auth_type=AuthScheme.BEARER)
    safe = mgr.safe_headers_for_logging(profile.id)
    assert "sk-log-secret" not in json.dumps(safe, default=str)
    assert safe["Authorization"] == "[REDACTED]"


def test_discovered_credential_like_material_cannot_become_active_credential() -> None:
    """No API accepts a DetectedSecret — only CredentialManager profiles are usable."""
    text = "found sk-abcdef1234567890 in README"
    detected = detect_secrets(text, location="README excerpt")
    assert len(detected) >= 1
    # DetectedSecret has no usable secret field — it is redacted by design.
    for d in detected:
        assert d.value == "[REDACTED]"
        assert not hasattr(d, "secret")
        assert not hasattr(d, "raw_value")

    # There is no code path that converts a DetectedSecret into a profile.
    # The only creation path requires an explicit secret argument.
    store = CredentialProfileStore()
    # This would be the wrong thing to do — store.create from detected value.
    # Even if someone tried, they'd only store "[REDACTED]", not a valid key.
    bad = store.create(display_name="Bad", secret=detected[0].value)
    assert store.get_secret(bad.id) == "[REDACTED]"
    # "[REDACTED]" will never authenticate against a real API.


def test_fingerprint_never_leaks_secret() -> None:
    secret = "sk-very-secret-value-12345"
    fp = fingerprint(secret)
    assert secret not in fp
    assert fp.startswith("••••••••")
    # Same secret → same fingerprint (deterministic for UX).
    assert fingerprint(secret) == fp
    # Different secret → different fingerprint.
    assert fingerprint("other-secret") != fp


def test_api_key_header_masked() -> None:
    headers = {"x-api-key": "my-secret-key", "Content-Type": "application/json"}
    redacted = redact_headers(headers)
    assert redacted["x-api-key"] == "[REDACTED]"
    assert "my-secret-key" not in json.dumps(redacted, default=str)


def test_redact_text_masks_bearer_token() -> None:
    text = "Authorization: Bearer sk-abcdef1234567890 and x-api-key: mykey123"
    redacted = redact_text(text)
    assert "sk-abcdef1234567890" not in redacted
    assert "mykey123" not in redacted


def test_keychain_memory_backend_isolated() -> None:
    kb = KeychainBackend()
    kb.enable_memory_backend()
    kb.store_secret("svc", "user", "shhh")
    assert kb.retrieve_secret("svc", "user") == "shhh"
    kb.delete_secret("svc", "user")
    assert kb.retrieve_secret("svc", "user") is None


def test_keychain_delete_nonexistent_is_noop() -> None:
    kb = KeychainBackend()
    kb.enable_memory_backend()
    kb.delete_secret("svc", "nope")  # should not raise


def test_profile_replace_and_delete() -> None:
    store = CredentialProfileStore()
    profile = store.create(display_name="Rot", secret="first")
    fp1 = store.get_fingerprint(profile.id)
    store.replace_secret(profile.id, "second")
    fp2 = store.get_fingerprint(profile.id)
    assert fp1 != fp2
    store.delete(profile.id)
    assert store.get(profile.id) is None
    assert store.get_secret(profile.id) is None
    assert store.get_fingerprint(profile.id) == "Not configured"


def test_manager_build_auth_headers_variants() -> None:
    mgr = CredentialManager()
    bearer = mgr.create_profile("B", secret="tok", auth_type=AuthScheme.BEARER)
    assert mgr.build_auth_headers(bearer.id) == {"Authorization": "Bearer tok"}

    api_key = mgr.create_profile(
        "K", secret="k123", auth_type=AuthScheme.API_KEY_HEADER, header_name="X-Custom-Key"
    )
    assert mgr.build_auth_headers(api_key.id) == {"X-Custom-Key": "k123"}

    custom = mgr.create_profile(
        "C", secret="cval", auth_type=AuthScheme.CUSTOM_HEADER, header_name="X-Foo"
    )
    assert mgr.build_auth_headers(custom.id) == {"X-Foo": "cval"}

    # Unknown profile → empty
    import uuid

    assert mgr.build_auth_headers(uuid.uuid4()) == {}
