"""Validation engine: async HTTP orchestration with bounded concurrency.

Owns the httpx.AsyncClient (connection pooling), enforces per-run
concurrency via semaphore, and sequences probes through ProbeRunner.
No GUI dependencies — safe for worker threads with their own event loop.
"""

import asyncio
from collections.abc import Sequence

import httpx

from raven_validator.config.settings import AppSettings
from raven_validator.core.validator import ProbeRunner
from raven_validator.domain.candidates import APICandidate
from raven_validator.probes.base import Probe, ProbeContext, ProbeResult
from raven_validator.security.request_policy import RequestPolicy
from raven_validator.utils.logging import get_logger
from raven_validator.utils.urls import normalize_url

logger = get_logger(__name__)


class ValidationEngine:
    """Runs probe sequences against candidates with bounded concurrency."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self.runner = ProbeRunner(settings)

    def _build_client(self) -> httpx.AsyncClient:
        timeout = httpx.Timeout(
            connect=self.settings.connect_timeout,
            read=self.settings.read_timeout,
            write=self.settings.read_timeout,
            pool=self.settings.connect_timeout,
        )
        return httpx.AsyncClient(
            timeout=timeout,
            max_redirects=5,
            follow_redirects=True,
            headers={"User-Agent": "Raven-Validator/0.1"},
        )

    async def run_probes(
        self,
        candidate: APICandidate,
        probes: Sequence[Probe],
        policy: RequestPolicy,
        credential: str | None = None,
    ) -> list[ProbeResult]:
        """Run a probe sequence for one candidate under the concurrency limit."""
        base_url = normalize_url(str(candidate.base_url))
        async with self._semaphore, self._build_client() as client:
            context = ProbeContext(
                candidate=candidate,
                client=client,
                base_url=base_url,
                credential=credential,
            )
            results: list[ProbeResult] = []
            for probe in probes:
                if not policy.check_probe_allowed(probe.safety_level):
                    logger.debug(
                        "Skipping probe %s: above safety ceiling", probe.name
                    )
                    continue
                if not policy.check_budget():
                    logger.debug("Budget exhausted for %s", candidate.name)
                    break
                result = await self.runner.run(probe, context, policy)
                results.append(result)
            return results
