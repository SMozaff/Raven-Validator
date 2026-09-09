"""Tests for the central status taxonomy.

Full HTTP→status mapping lives in core/status_mapper.py (Milestone 2).
Here we lock the taxonomy itself: every required status exists and no
generic 'failed' status is available to collapse into.
"""

from raven_validator.domain.statuses import ValidationStatus


def test_all_required_statuses_defined() -> None:
    required = {
        "WORKING",
        "REACHABLE_AUTH_REQUIRED",
        "REACHABLE_UNSUPPORTED",
        "INVALID_CREDENTIAL",
        "INSUFFICIENT_CREDITS",
        "RATE_LIMITED",
        "MODEL_UNAVAILABLE",
        "ENDPOINT_NOT_FOUND",
        "PROTOCOL_MISMATCH",
        "MALFORMED_RESPONSE",
        "TLS_ERROR",
        "TIMEOUT",
        "DNS_ERROR",
        "CONNECTION_ERROR",
        "SERVER_ERROR",
        "BLOCKED",
        "CANCELLED",
        "UNKNOWN",
    }
    defined = {s.value for s in ValidationStatus}
    assert required <= defined


def test_no_generic_failed_status() -> None:
    defined = {s.value for s in ValidationStatus}
    assert "FAILED" not in defined
    assert "ERROR" not in defined
    assert "NOT_WORKING" not in defined


def test_status_values_are_strings() -> None:
    for status in ValidationStatus:
        assert isinstance(status.value, str)
