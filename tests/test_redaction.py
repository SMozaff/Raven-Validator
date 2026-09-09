"""Security tests for secret redaction.

Release-blocking: no raw credential may reach logs, database excerpts,
GUI diagnostics, or exports through any tested path.
"""

from raven_validator.security.redaction import (
    mask_secret,
    redact_excerpt,
    redact_headers,
    redact_text,
)
from raven_validator.security.secret_detector import (
    DetectedSecret,
    contains_credential_like_material,
    detect_secrets,
)


def test_authorization_header_redacted() -> None:
    headers = {"Authorization": "Bearer sk-abcdef123456", "Content-Type": "application/json"}
    redacted = redact_headers(headers)
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/json"
    assert "sk-abcdef123456" not in str(redacted)


def test_api_key_header_redacted() -> None:
    headers = {"x-api-key": "secret-key-value", "Accept": "application/json"}
    redacted = redact_headers(headers)
    assert redacted["x-api-key"] == "[REDACTED]"
    assert "secret-key-value" not in str(redacted)


def test_cookie_redacted() -> None:
    assert redact_headers({"Cookie": "session=abc123"})["Cookie"] == "[REDACTED]"


def test_bearer_token_in_text_redacted() -> None:
    text = "Authorization: Bearer sk-abcdef1234567890"
    redacted = redact_text(text)
    assert "sk-abcdef1234567890" not in redacted
    assert "[REDACTED]" in redacted


def test_mask_secret_keeps_short_tail() -> None:
    masked = mask_secret("sk-abcdef7A2F")
    assert masked.endswith("7A2F")
    assert "sk-abcdef" not in masked


def test_mask_secret_empty() -> None:
    assert mask_secret("") == "[REDACTED]"


def test_excerpt_truncated_and_redacted() -> None:
    long_text = "data " * 200 + "sk-abcdef1234567890"
    excerpt = redact_excerpt(long_text, max_length=100)
    assert len(excerpt) < len(long_text)
    assert "sk-abcdef1234567890" not in excerpt


def test_detect_secrets_never_returns_raw_value() -> None:
    results = detect_secrets("key is sk-abcdef1234567890 here", location="README excerpt")
    assert len(results) >= 1
    for result in results:
        assert isinstance(result, DetectedSecret)
        assert "sk-abcdef" not in result.value
        assert result.value == "[REDACTED]"
        assert result.location == "README excerpt"


def test_credential_like_material_detected() -> None:
    assert contains_credential_like_material("api-key: mysecretkey123")
    assert contains_credential_like_material("-----BEGIN RSA PRIVATE KEY-----")
    assert not contains_credential_like_material("Hello, this is a normal message.")


def test_detected_secret_has_no_credential_api() -> None:
    """DetectedSecret must expose no usable secret — metadata only."""
    result = detect_secrets("token sk-abcdef1234567890")[0]
    assert not hasattr(result, "secret")
    assert not hasattr(result, "raw")
    assert not hasattr(result, "token")
