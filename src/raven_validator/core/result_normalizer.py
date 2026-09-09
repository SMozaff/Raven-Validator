"""Result normalizer: merge probe outcomes into a ValidationResult.

Evidence-based: unknown fields stay unknown, confidence reflects what
was actually verified. Never infer success from absent evidence.
"""

from uuid import UUID

from raven_validator.core.status_mapper import map_exception, map_http_status
from raven_validator.domain.results import (
    ValidationError,
    ValidationResult,
)
from raven_validator.domain.statuses import ValidationStatus
from raven_validator.probes.base import ProbeResult
from raven_validator.utils.dates import utc_now


def normalize_probe_results(
    candidate_id: UUID,
    run_id: UUID,
    probe_results: list[ProbeResult],
    credential_configured: bool = False,
    credential_used: bool = False,
) -> ValidationResult:
    """Build a normalized ValidationResult from raw probe outcomes."""
    result = ValidationResult(
        candidate_id=candidate_id,
        run_id=run_id,
        credential_configured=credential_configured,
        credential_used=credential_used,
        tested_at=utc_now(),
    )

    confidences: list[float] = []

    for probe in probe_results:
        if probe.probe_name == "reachability":
            _apply_reachability(result, probe, confidences)
        elif probe.probe_name == "auth_requirement":
            _apply_auth(result, probe, confidences)
        if probe.error and probe.probe_name not in ("openapi_schema",):
            result.errors.append(
                ValidationError(
                    error_type=probe.probe_name,
                    message=probe.error,
                )
            )

    result.overall_status = _derive_status(result, probe_results)
    result.confidence = (
        sum(confidences) / len(confidences) if confidences else 0.0
    )
    return result


def _apply_reachability(
    result: ValidationResult,
    probe: ProbeResult,
    confidences: list[float],
) -> None:
    if probe.http_status is not None:
        result.reachable = probe.http_status < 500
        result.latency_ms = probe.latency_ms
        confidences.append(1.0 if probe.success else 0.5)
    elif probe.error:
        result.reachable = False
        status = _status_from_error(probe.error)
        result.errors.append(
            ValidationError(error_type="reachability", message=probe.error)
        )
        if status is not ValidationStatus.UNKNOWN:
            result.overall_status = status
        confidences.append(0.7)


def _apply_auth(
    result: ValidationResult,
    probe: ProbeResult,
    confidences: list[float],
) -> None:
    auth_required = probe.data.get("auth_required")
    if isinstance(auth_required, bool):
        result.auth_required = auth_required
        scheme = probe.data.get("auth_scheme")
        if isinstance(scheme, str):
            result.auth_scheme = scheme
        confidences.append(0.9 if probe.success else 0.3)


def _status_from_error(error: str) -> ValidationStatus:
    lowered = error.lower()
    if "timeout" in lowered:
        return ValidationStatus.TIMEOUT
    if "tls" in lowered or "ssl" in lowered or "certificate" in lowered:
        return ValidationStatus.TLS_ERROR
    if "dns" in lowered:
        return ValidationStatus.DNS_ERROR
    if "connection" in lowered or "connect" in lowered:
        return ValidationStatus.CONNECTION_ERROR
    # Fall back to exception mapping for anything else.
    return map_exception(RuntimeError(error))


def _derive_status(
    result: ValidationResult,
    probes: list[ProbeResult],
) -> ValidationStatus:
    # Transport-level failures take precedence.
    if result.overall_status not in (ValidationStatus.UNKNOWN,):
        return result.overall_status
    if result.reachable is False:
        for probe in probes:
            if probe.http_status is not None:
                return map_http_status(probe.http_status)
        return ValidationStatus.CONNECTION_ERROR
    if result.auth_required:
        if result.credential_used:
            return ValidationStatus.REACHABLE_AUTH_REQUIRED
        return ValidationStatus.REACHABLE_AUTH_REQUIRED
    if result.reachable:
        return ValidationStatus.WORKING
    return ValidationStatus.UNKNOWN
