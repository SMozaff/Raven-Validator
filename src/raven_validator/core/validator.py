"""Probe runner with bounded tenacity retry.

Retries transient failures only: timeouts, connection resets,
502/503/504, and 429 with a reasonable Retry-After. Never retries
400/401/403/404/422. Uses exponential backoff + jitter and respects
Retry-After.
"""

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from raven_validator.config.settings import AppSettings
from raven_validator.probes.base import Probe, ProbeContext, ProbeResult
from raven_validator.security.request_policy import (
    BudgetExceededError,
    RequestPolicy,
)
from raven_validator.utils.logging import get_logger

logger = get_logger(__name__)

_NO_RETRY_STATUSES = frozenset({400, 401, 403, 404, 422})


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (502, 503, 504):
            return True
        if status == 429:
            retry_after = exc.response.headers.get("retry-after")
            if retry_after is None:
                return False
            try:
                return float(retry_after) <= 120
            except ValueError:
                return False
        return False
    return isinstance(exc, httpx.TransportError)


def _retrying_call(settings: AppSettings):  # type: ignore[no-untyped-def]
    return retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )


class ProbeRunner:
    """Executes probes with retry accounting and budget enforcement."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    async def run(
        self, probe: Probe, context: ProbeContext, policy: RequestPolicy
    ) -> ProbeResult:
        retrying = _retrying_call(self.settings)

        @retrying
        async def _call() -> ProbeResult:
            policy.record_request()
            return await probe.run(context)

        try:
            return await _call()
        except BudgetExceededError as exc:
            logger.debug("Budget exceeded for probe %s", probe.name)
            return ProbeResult(
                probe_name=probe.name,
                safety_level=probe.safety_level,
                success=False,
                error=str(exc),
                evidence=["Request budget exhausted"],
            )
        except Exception as exc:  # noqa: BLE001 — normalized, never silent
            logger.debug("Probe %s failed: %s", probe.name, type(exc).__name__)
            return ProbeResult(
                probe_name=probe.name,
                safety_level=probe.safety_level,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                evidence=[f"Probe error: {type(exc).__name__}"],
            )
