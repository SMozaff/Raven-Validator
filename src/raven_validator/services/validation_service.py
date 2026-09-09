"""Validation service — batch orchestration, persistence, progressive events."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx

from raven_validator.config.settings import AppSettings
from raven_validator.core.capability_detector import detect_capabilities
from raven_validator.core.protocol_detector import detect_protocol
from raven_validator.core.result_normalizer import normalize_probe_results
from raven_validator.core.validator import ProbeRunner
from raven_validator.database.database import Database
from raven_validator.database.repository import Repository
from raven_validator.domain.candidates import APICandidate
from raven_validator.domain.results import ValidationResult
from raven_validator.domain.statuses import ValidationStatus
from raven_validator.probes.auth import AuthProbe
from raven_validator.probes.base import Probe, ProbeContext, ProbeResult
from raven_validator.probes.generation import GenerationProbe
from raven_validator.probes.models import ModelsProbe
from raven_validator.probes.openapi import OpenAPISchemaProbe
from raven_validator.probes.quota import QuotaProbe
from raven_validator.probes.rate_limits import RateLimitProbe
from raven_validator.probes.reachability import ReachabilityProbe
from raven_validator.probes.streaming import StreamingProbe
from raven_validator.security.request_policy import ProbeSafetyLevel, RequestPolicy


@dataclass
class ValidationOptions:
    mode: str = "standard"  # quick | standard | authorized | custom
    test_streaming: bool = False
    check_quota: bool = False
    model: str | None = None
    headers: dict[str, str] | None = None


@dataclass
class BatchEvent:
    kind: str  # run_started | candidate_started | probe_finished | candidate_finished | progress | run_finished | run_cancelled
    candidate_id: UUID | None = None
    run_id: UUID | None = None
    probe_name: str | None = None
    status: str | None = None
    progress: tuple[int, int] | None = None  # (done, total)
    result: ValidationResult | None = None


class ValidationService:
    """Orchestrates validation for batches of candidates."""

    def __init__(
        self,
        settings: AppSettings,
        database: Database,
        credential_store: dict[UUID, str] | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.credential_store = credential_store or {}
        self._cancelled = False
        self._runner = ProbeRunner(settings)

    def cancel(self) -> None:
        self._cancelled = True

    def reset_cancel(self) -> None:
        self._cancelled = False

    def _probes_for_mode(self, options: ValidationOptions, has_credential: bool) -> list[Probe]:
        probes: list[Probe] = [ReachabilityProbe(), AuthProbe()]
        if options.mode == "quick":
            return probes
        probes.extend([ModelsProbe(), RateLimitProbe(), OpenAPISchemaProbe()])
        if options.mode in ("authorized", "custom") and has_credential:
            probes.append(GenerationProbe())
            if options.test_streaming:
                probes.append(StreamingProbe())
            if options.check_quota:
                probes.append(QuotaProbe())
        return probes

    def _policy_for(self, options: ValidationOptions, has_credential: bool, profile_id: str | None) -> RequestPolicy:
        # Quick/Standard are READ_ONLY; Authorized elevates to MINIMAL_GENERATION.
        ceiling = ProbeSafetyLevel.READ_ONLY
        if options.mode in ("authorized", "custom") and has_credential:
            if options.check_quota:
                ceiling = ProbeSafetyLevel.CUSTOM_AUTHORIZED
            else:
                ceiling = ProbeSafetyLevel.MINIMAL_GENERATION
        policy = RequestPolicy(
            max_requests_per_api=self.settings.max_requests_per_api,
            max_concurrency=self.settings.max_concurrency,
            max_safety_level=ceiling,
        )
        if has_credential and profile_id:
            policy.authorize_credential(profile_id)
        return policy

    async def validate_one(
        self,
        candidate: APICandidate,
        options: ValidationOptions,
        client: httpx.AsyncClient | None = None,
        _transport: httpx.BaseTransport | None = None,
    ) -> ValidationResult:
        run_id = uuid4()
        has_credential = candidate.credential_profile_id is not None and candidate.credential_profile_id in self.credential_store
        credential = self.credential_store.get(candidate.credential_profile_id) if candidate.credential_profile_id else None
        profile_id = str(candidate.credential_profile_id) if candidate.credential_profile_id else None

        probes = self._probes_for_mode(options, has_credential)
        policy = self._policy_for(options, has_credential, profile_id)

        # Create run row.
        with self.database.session() as sess:
            repo = Repository(sess)
            repo.save_candidate(candidate)
            repo.create_run(candidate.id, mode=options.mode, run_id=run_id)

        # Build httpx client (or use injected).
        own_client = client is None
        if own_client:
            timeout = httpx.Timeout(
                connect=self.settings.connect_timeout,
                read=self.settings.read_timeout,
                write=self.settings.read_timeout,
                pool=self.settings.connect_timeout,
            )
            kwargs: dict[str, object] = {
                "timeout": timeout,
                "max_redirects": 5,
                "follow_redirects": True,
                "headers": {"User-Agent": "Raven-Validator/0.1"},
            }
            if _transport is not None:
                kwargs["transport"] = _transport
            client = httpx.AsyncClient(**kwargs)  # type: ignore[arg-type]

        probe_results: list[ProbeResult] = []
        protocol_name = "unknown"
        protocol_conf = 0.0
        try:
            # Protocol detection (best-effort, needs a client context).
            from raven_validator.utils.urls import normalize_url
            base_url = normalize_url(str(candidate.base_url))
            ctx = ProbeContext(
                candidate=candidate,
                client=client,
                base_url=base_url,
                credential=credential,
                options={"model": options.model, "headers": options.headers} if options.model or options.headers else {},
            )
            detection = await detect_protocol(ctx)
            protocol_name = detection.protocol
            protocol_conf = detection.confidence

            # Run probe sequence.
            for probe in probes:
                if self._cancelled:
                    break
                if not policy.check_probe_allowed(probe.safety_level):
                    continue
                if not policy.check_budget():
                    break
                ctx_probe = ProbeContext(
                    candidate=candidate,
                    client=client,
                    base_url=base_url,
                    credential=credential,
                    options={"model": options.model, "headers": options.headers} if options.model or options.headers else {},
                )
                # For generation/streaming/quota, propagate credential in options too if needed.
                result = await self._runner.run(probe, ctx_probe, policy)
                probe_results.append(result)
        finally:
            if own_client:
                await client.aclose()  # type: ignore[union-attr]

        # Capabilities from probe results.
        caps = detect_capabilities(protocol_name, probe_results)

        # Normalize with extended fields (models, rate-limit, quota).
        # Use existing normalizer then patch extended fields.
        result = normalize_probe_results(
            candidate.id,
            run_id,
            probe_results,
            credential_configured=has_credential,
            credential_used=has_credential and any(p.probe_name in ("generation", "streaming", "quota") for p in probe_results),
        )
        result.detected_protocol = protocol_name
        result.protocol_confidence = protocol_conf
        result.capabilities = caps
        # Override status if cancelled.
        if self._cancelled:
            result.overall_status = ValidationStatus.CANCELLED

        # Patch models / rate-limit / quota from probe data.
        for pr in probe_results:
            if pr.probe_name == "models" and pr.success:
                models = pr.data.get("models")
                if isinstance(models, list):
                    result.models = [str(m) for m in models]
            if pr.probe_name == "rate_limits":
                rl = pr.data
                result.rate_limit.known = bool(rl.get("known"))
                result.rate_limit.limit = rl.get("limit") if isinstance(rl.get("limit"), int) else None  # type: ignore[assignment]
                result.rate_limit.remaining = rl.get("remaining") if isinstance(rl.get("remaining"), int) else None  # type: ignore[assignment]
                result.rate_limit.source = rl.get("source") if isinstance(rl.get("source"), str) else None  # type: ignore[assignment]
            if pr.probe_name == "quota":
                q = pr.data
                result.quota.known = bool(q.get("known"))
                status = q.get("status")
                if status == "INSUFFICIENT":
                    result.overall_status = ValidationStatus.INSUFFICIENT_CREDITS
                bal = q.get("balance")
                if isinstance(bal, (int, float)):
                    result.quota.balance = float(bal)
                unit = q.get("unit")
                if isinstance(unit, str):
                    result.quota.unit = unit
                reason = q.get("reason")
                if isinstance(reason, str):
                    result.quota.reason = reason

        # Persist.
        with self.database.session() as sess:
            repo = Repository(sess)
            run = repo.get_run(run_id)
            if run is not None:
                run.status = result.overall_status.value
                run.reachable = result.reachable
                run.detected_protocol = result.detected_protocol
                run.confidence = result.confidence
                from datetime import UTC, datetime

                run.completed_at = datetime.now(UTC)
                run.request_count = len(probe_results)
                run.error_count = len(result.errors)
            # Snapshots.
            repo.save_capability_snapshot(
                run_id,
                models=caps.models,
                chat_completions=caps.chat_completions,
                responses=caps.responses,
                streaming=caps.streaming,
                embeddings=caps.embeddings,
                images=caps.images,
                audio=caps.audio,
            )
            if result.models:
                repo.save_model_snapshots(run_id, result.models)
            repo.save_rate_limit_snapshot(
                run_id,
                known=result.rate_limit.known,
                limit=result.rate_limit.limit,
                remaining=result.rate_limit.remaining,
                reset_at=result.rate_limit.reset_at,
                source=result.rate_limit.source,
            )
            repo.save_quota_snapshot(
                run_id,
                status="KNOWN" if result.quota.known else ("INSUFFICIENT" if result.overall_status == ValidationStatus.INSUFFICIENT_CREDITS else "UNKNOWN"),
                known=result.quota.known,
                balance=result.quota.balance,
                unit=result.quota.unit,
                reason=result.quota.reason,
            )
            for pr in probe_results:
                repo.save_probe_result(
                    run_id,
                    probe_type=pr.probe_name,
                    endpoint=pr.endpoint,
                    method=pr.method,
                    status=pr.probe_name,
                    http_status=pr.http_status,
                    latency_ms=pr.latency_ms,
                    excerpt=str(pr.data.get("excerpt", "")) if pr.data else pr.error,
                )
                if pr.error:
                    repo.save_error(run_id, error_type=pr.probe_name, message=pr.error)

        return result

    async def validate_batch(
        self,
        candidates: list[APICandidate],
        options: ValidationOptions,
        _transport: httpx.BaseTransport | None = None,
    ) -> AsyncGenerator[BatchEvent, None]:
        self._cancelled = False
        total = len(candidates)
        yield BatchEvent(kind="run_started", progress=(0, total))
        sem = asyncio.Semaphore(self.settings.max_concurrency)
        completed = 0

        async def _one(cand: APICandidate) -> BatchEvent:
            if self._cancelled:
                return BatchEvent(kind="candidate_finished", candidate_id=cand.id, status="CANCELLED", progress=(0, total))
            async with sem:
                if self._cancelled:
                    return BatchEvent(kind="candidate_finished", candidate_id=cand.id, status="CANCELLED", progress=(0, total))
                result = await self.validate_one(cand, options, _transport=_transport)
                return BatchEvent(
                    kind="candidate_finished",
                    candidate_id=cand.id,
                    run_id=result.run_id,
                    status=result.overall_status.value,
                    result=result,
                )

        # Schedule tasks respecting cancel.
        tasks: list[asyncio.Task[BatchEvent]] = []
        for cand in candidates:
            if self._cancelled:
                break
            yield BatchEvent(kind="candidate_started", candidate_id=cand.id)
            tasks.append(asyncio.create_task(_one(cand)))

        pending: set[asyncio.Task[BatchEvent]] = set(tasks)
        while pending:
            if self._cancelled:
                for t in list(pending):
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                yield BatchEvent(kind="run_cancelled", progress=(completed, total))
                break
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                try:
                    event = t.result()
                except asyncio.CancelledError:
                    continue
                completed += 1
                event.progress = (completed, total)
                yield BatchEvent(kind="progress", progress=(completed, total))
                yield event

        if not self._cancelled or completed < total:
            yield BatchEvent(kind="run_finished", progress=(completed, total))
