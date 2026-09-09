"""Tests for the central status taxonomy and HTTP error mapping.

Full HTTP→status mapping lives in core/status_mapper.py (Milestone 2).
Here we lock the taxonomy itself: every required status exists and no
generic 'failed' status is available to collapse into.
"""

import httpx
import pytest

from raven_validator.core.status_mapper import (
    map_exception,
    map_http_status,
    map_response,
)
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


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, ValidationStatus.WORKING),
        (201, ValidationStatus.WORKING),
        (204, ValidationStatus.WORKING),
        (400, ValidationStatus.PROTOCOL_MISMATCH),
        (401, ValidationStatus.REACHABLE_AUTH_REQUIRED),
        (404, ValidationStatus.ENDPOINT_NOT_FOUND),
        (422, ValidationStatus.PROTOCOL_MISMATCH),
        (429, ValidationStatus.RATE_LIMITED),
        (500, ValidationStatus.SERVER_ERROR),
        (502, ValidationStatus.SERVER_ERROR),
        (503, ValidationStatus.SERVER_ERROR),
        (504, ValidationStatus.TIMEOUT),
    ],
)
def test_http_status_mapping(status_code: int, expected: ValidationStatus) -> None:
    assert map_http_status(status_code) == expected


def test_429_with_credit_body_is_insufficient() -> None:
    assert (
        map_http_status(429, "insufficient credits remaining")
        == ValidationStatus.INSUFFICIENT_CREDITS
    )
    assert (
        map_http_status(429, "quota exceeded for this billing period")
        == ValidationStatus.INSUFFICIENT_CREDITS
    )


def test_bare_429_is_rate_limited_not_credits() -> None:
    """Never infer insufficient credits from a bare 429."""
    assert map_http_status(429, "") == ValidationStatus.RATE_LIMITED
    assert (
        map_http_status(429, "too many requests") == ValidationStatus.RATE_LIMITED
    )


def test_map_response_inspects_body() -> None:
    request = httpx.Request("GET", "https://api.example.com/v1")
    response = httpx.Response(
        429, json={"error": "billing balance exhausted"}, request=request
    )
    assert map_response(response) == ValidationStatus.INSUFFICIENT_CREDITS


def test_map_exception_timeout() -> None:
    assert map_exception(httpx.ConnectTimeout("x")) == ValidationStatus.TIMEOUT
    assert map_exception(httpx.ReadTimeout("x")) == ValidationStatus.TIMEOUT


def test_map_exception_connection() -> None:
    assert (
        map_exception(httpx.ConnectError("refused")) == ValidationStatus.CONNECTION_ERROR
    )
