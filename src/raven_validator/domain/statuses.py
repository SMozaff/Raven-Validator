"""Central validation status taxonomy.

Use precise statuses — never collapse distinct failures into a generic
"failed". A more specific status must be preferred whenever evidence
supports it.
"""

from enum import StrEnum


class ValidationStatus(StrEnum):
    """Normalized overall status of an API validation run."""

    WORKING = "WORKING"
    REACHABLE_AUTH_REQUIRED = "REACHABLE_AUTH_REQUIRED"
    REACHABLE_UNSUPPORTED = "REACHABLE_UNSUPPORTED"
    INVALID_CREDENTIAL = "INVALID_CREDENTIAL"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    RATE_LIMITED = "RATE_LIMITED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    ENDPOINT_NOT_FOUND = "ENDPOINT_NOT_FOUND"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    TLS_ERROR = "TLS_ERROR"
    TIMEOUT = "TIMEOUT"
    DNS_ERROR = "DNS_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"
