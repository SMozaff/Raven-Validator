"""Central secret redaction.

Applies to: logs, database diagnostic excerpts, GUI diagnostics,
exports, and exception messages where practical. Never emit a full
credential — always mask or drop the sensitive value.
"""

import re
from enum import StrEnum

SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "x-api-key",
        "api-key",
        "apikey",
        "x-auth-token",
        "cookie",
        "set-cookie",
        "proxy-authorization",
    }
)

_MASKED_TAIL_LENGTH = 4


class SecretKind(StrEnum):
    """Probable type of detected credential-like material."""

    BEARER_TOKEN = "bearer-token-like"
    API_KEY = "api-key-like"
    BASIC_AUTH = "basic-auth-like"
    PRIVATE_KEY = "private-key-like"
    GENERIC_TOKEN = "generic-token-like"
    UNKNOWN = "unknown"


# Heuristic patterns for token-like strings in free text.
_TOKEN_PATTERNS: tuple[tuple[SecretKind, re.Pattern[str]], ...] = (
    (
        SecretKind.BEARER_TOKEN,
        re.compile(r"\bsk-[A-Za-z0-9\-_]{8,}\b"),
    ),
    (
        SecretKind.API_KEY,
        re.compile(
            r"\b(?:api[_-]?key|apikey|x-api-key)\s*[:=]\s*['\"]?([^\s'\",;]+)",
            re.IGNORECASE,
        ),
    ),
    (
        SecretKind.PRIVATE_KEY,
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    ),
    (
        SecretKind.GENERIC_TOKEN,
        re.compile(r"\b(?:ghp|gho|glpat|AKIA)[A-Za-z0-9]{8,}\b"),
    ),
)


def mask_secret(value: str, keep_tail: int = _MASKED_TAIL_LENGTH) -> str:
    """Mask a secret, optionally keeping a short tail for identification."""
    if not value:
        return "[REDACTED]"
    if len(value) <= keep_tail:
        return "[REDACTED]"
    return f"{'•' * 8}{value[-keep_tail:]}"


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of headers with sensitive values masked."""
    redacted: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() in SENSITIVE_HEADERS:
            redacted[name] = "[REDACTED]"
        else:
            redacted[name] = value
    return redacted


def redact_text(text: str) -> str:
    """Mask credential-like substrings inside free text."""
    redacted = text
    for _, pattern in _TOKEN_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    # Generic bearer-token shape after an Authorization marker.
    redacted = re.sub(
        r"(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+",
        r"\1[REDACTED]",
        redacted,
        flags=re.IGNORECASE,
    )
    return redacted


def redact_excerpt(text: str, max_length: int = 500) -> str:
    """Produce a redacted, length-bounded diagnostic excerpt."""
    excerpt = text[:max_length]
    if len(text) > max_length:
        excerpt += "…[truncated]"
    return redact_text(excerpt)
