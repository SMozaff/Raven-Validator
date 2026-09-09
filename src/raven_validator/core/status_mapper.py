"""Normalized HTTP/transport status helpers."""
from raven_validator.domain.statuses import ValidationStatus


def transport_status(message: str) -> ValidationStatus:
    low = message.lower()
    if "unsafe" in low or "blocked" in low or "private" in low:
        return ValidationStatus.BLOCKED
    if "timeout" in low:
        return ValidationStatus.TIMEOUT
    if "ssl" in low or "tls" in low or "certificate" in low:
        return ValidationStatus.TLS_ERROR
    if "dns" in low or "name or service" in low:
        return ValidationStatus.DNS_ERROR
    return ValidationStatus.CONNECTION_ERROR
