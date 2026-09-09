"""Detection and classification of credential-like material.

Purpose is classification/redaction/reporting ONLY. A detection result
must NEVER be converted into an active credential or used for
authenticated requests. That boundary is enforced by keeping this
module free of any credential-storage or request-injection API —
it returns metadata, never usable secrets.
"""

from dataclasses import dataclass

from raven_validator.security.redaction import _TOKEN_PATTERNS, SecretKind


@dataclass(frozen=True)
class DetectedSecret:
    """Metadata about credential-like material. Value is always redacted."""

    kind: SecretKind
    location: str
    value: str = "[REDACTED]"


def detect_secrets(text: str, location: str = "unknown") -> list[DetectedSecret]:
    """Classify credential-like substrings in text.

    Returns metadata only — raw values are never stored or returned.
    """
    found: list[DetectedSecret] = []
    seen: set[SecretKind] = set()
    for kind, pattern in _TOKEN_PATTERNS:
        if kind in seen:
            continue
        if pattern.search(text):
            found.append(DetectedSecret(kind=kind, location=location))
            seen.add(kind)
    return found


def contains_credential_like_material(text: str) -> bool:
    """Quick boolean check for credential-like content."""
    return bool(detect_secrets(text))
