"""Central HTTP error mapping.

Maps HTTP statuses + response signals to precise ValidationStatus
values. Never collapse distinct failures into a generic error, and
never infer insufficient credits from a bare 429 — inspect body
and headers first.
"""

import httpx

from raven_validator.domain.statuses import ValidationStatus

_CREDIT_MARKERS = (
    "insufficient",
    "out of credit",
    "no credit",
    "balance",
    "quota exceeded",
    "billing",
)


def _body_text(response: httpx.Response) -> str:
    try:
        return response.text.lower()[:4000]
    except (ValueError, UnicodeDecodeError):
        return ""


def map_http_status(
    status_code: int,
    body: str = "",
    headers: dict[str, str] | None = None,
) -> ValidationStatus:
    """Map an HTTP status (+ optional body/headers) to a ValidationStatus."""
    lowered = body.lower()
    if 200 <= status_code <= 299:
        return ValidationStatus.WORKING
    if status_code in (301, 302, 307, 308):
        return ValidationStatus.UNKNOWN
    if status_code == 400:
        return ValidationStatus.PROTOCOL_MISMATCH
    if status_code == 401:
        return ValidationStatus.REACHABLE_AUTH_REQUIRED
    if status_code == 403:
        if any(m in lowered for m in ("blocked", "forbidden", "not allowed")):
            return ValidationStatus.BLOCKED
        return ValidationStatus.REACHABLE_AUTH_REQUIRED
    if status_code == 404:
        return ValidationStatus.ENDPOINT_NOT_FOUND
    if status_code == 409:
        return ValidationStatus.SERVER_ERROR
    if status_code == 422:
        return ValidationStatus.PROTOCOL_MISMATCH
    if status_code == 429:
        if any(m in lowered for m in _CREDIT_MARKERS):
            return ValidationStatus.INSUFFICIENT_CREDITS
        return ValidationStatus.RATE_LIMITED
    if status_code == 500:
        return ValidationStatus.SERVER_ERROR
    if status_code in (502, 503):
        return ValidationStatus.SERVER_ERROR
    if status_code == 504:
        return ValidationStatus.TIMEOUT
    if 500 <= status_code <= 599:
        return ValidationStatus.SERVER_ERROR
    return ValidationStatus.UNKNOWN


def map_exception(exc: BaseException) -> ValidationStatus:
    """Map a transport exception to a precise status."""
    name = type(exc).__name__
    message = str(exc).lower()
    if isinstance(exc, httpx.TimeoutException):
        return ValidationStatus.TIMEOUT
    if "ssl" in name.lower() or "ssl" in message or "certificate" in message:
        return ValidationStatus.TLS_ERROR
    if isinstance(exc, httpx.ConnectError):
        if "dns" in message or "name resolution" in message or "nodename" in message:
            return ValidationStatus.DNS_ERROR
        return ValidationStatus.CONNECTION_ERROR
    if isinstance(exc, httpx.NetworkError):
        return ValidationStatus.CONNECTION_ERROR
    return ValidationStatus.UNKNOWN


def map_response(response: httpx.Response) -> ValidationStatus:
    """Map a full httpx response, inspecting body and headers."""
    headers = {k.lower(): v for k, v in response.headers.items()}
    return map_http_status(response.status_code, _body_text(response), headers)
