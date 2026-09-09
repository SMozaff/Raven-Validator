"""Safe batch validation orchestration with protocol-specific authorized testing."""
from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx

from raven_validator.adapters.base import AuthorizedContext, ProbeOutcome, PublicContext
from raven_validator.config.settings import AppSettings
from raven_validator.core.http_client import BudgetedSafeClient
from raven_validator.core.protocol_detector import detect_protocol
from raven_validator.core.status_mapper import transport_status
from raven_validator.domain.candidates import APICandidate
from raven_validator.domain.credentials import CredentialProfile
from raven_validator.domain.results import (
    QuotaInfo,
    RateLimitInfo,
    ValidationError,
    ValidationResult,
)
from raven_validator.domain.statuses import ValidationStatus
from raven_validator.security.network_policy import NetworkPolicy, UnsafeNetworkTarget
from raven_validator.security.redaction import redact_text
from raven_validator.security.request_policy import (
    ProbeSafetyLevel,
    RequestBudgetExceeded,
    RequestPolicy,
)

CredentialResolver = Callable[[APICandidate], tuple[CredentialProfile, str] | None]


@dataclass(frozen=True)
class ValidationOptions:
    mode: str = "standard"  # quick | standard | authorized
    test_streaming: bool = False
    check_quota: bool = False
    inspect_rate_limits: bool = True
    model: str | None = None
    timeout_override: float | None = None


@dataclass
class BatchEvent:
    kind: str
    candidate_id: UUID | None = None
    result: ValidationResult | None = None
    progress: tuple[int, int] | None = None
    message: str | None = None


def _auth_from_response(response: httpx.Response) -> tuple[bool, str | None, list[str]]:
    if response.status_code not in {401, 403}:
        return False, None, [f"HTTP {response.status_code}: no auth challenge at base URL"]
    text = response.text.lower()[:2000]
    www = response.headers.get("www-authenticate", "").lower()
    if "bearer" in www or "bearer" in text or "authorization" in text:
        return True, "bearer", [f"HTTP {response.status_code}", "Bearer/Authorization signal"]
    if "x-api-key" in text or "api key" in text or "apikey" in text:
        return True, "api-key-header", [f"HTTP {response.status_code}", "API-key signal"]
    if "basic" in www or "basic" in text:
        return True, "basic", [f"HTTP {response.status_code}", "Basic auth signal"]
    return True, "unknown", [f"HTTP {response.status_code}: authentication required"]


def _parse_rate_limit(headers: dict[str, str]) -> RateLimitInfo:
    lower = {k.lower(): v for k, v in headers.items()}
    def as_int(*keys: str) -> int | None:
        for key in keys:
            try:
                return int(float(lower[key]))
            except (KeyError, ValueError):
                continue
        return None
    retry: float | None = None
    try:
        retry = float(lower["retry-after"])
    except (KeyError, ValueError):
        pass
    limit = as_int("ratelimit-limit", "x-ratelimit-limit")
    remaining = as_int("ratelimit-remaining", "x-ratelimit-remaining")
    return RateLimitInfo(
        known=limit is not None or remaining is not None or retry is not None,
        limit=limit,
        remaining=remaining,
        reset_at=lower.get("ratelimit-reset") or lower.get("x-ratelimit-reset"),
        retry_after=retry,
    )


def _explicit_insufficient(outcome: ProbeOutcome) -> bool:
    if outcome.http_status != 429:
        return False
    text = str(outcome.data.get("excerpt", "")).lower()
    # Narrow provider-style signals only; generic "quota" is not sufficient.
    return bool(re.search(r"insufficient[_ -]?(quota|credit|credits)|billing[_ -]?hard[_ -]?limit", text))


class ValidationService:
    def __init__(
        self,
        settings: AppSettings,
        credential_resolver: CredentialResolver | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        resolve_dns: bool = True,
    ) -> None:
        self.settings = settings
        self.credential_resolver = credential_resolver
        self.transport = transport
        self.resolve_dns = resolve_dns
        self._cancel_event = asyncio.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def reset_cancel(self) -> None:
        self._cancel_event = asyncio.Event()

    async def validate_one(self, candidate: APICandidate, options: ValidationOptions) -> ValidationResult:
        run_id = uuid4()
        result = ValidationResult(candidate_id=candidate.id, run_id=run_id, base_url=str(candidate.base_url))
        ceiling = ProbeSafetyLevel.MINIMAL_GENERATION if options.mode == "authorized" else ProbeSafetyLevel.READ_ONLY
        if options.check_quota and options.mode == "authorized":
            ceiling = ProbeSafetyLevel.CUSTOM_AUTHORIZED
        policy = RequestPolicy(self.settings.max_requests_per_api, ceiling)
        network = NetworkPolicy(self.settings.allow_private_networks, resolve_dns=self.resolve_dns)
        timeout_value = options.timeout_override or max(self.settings.connect_timeout, self.settings.read_timeout)
        timeout = httpx.Timeout(timeout_value)

        async with httpx.AsyncClient(timeout=timeout, transport=self.transport, headers={"User-Agent": "Raven-Validator/0.2"}) as raw:
            client = BudgetedSafeClient(raw, policy, network)
            public = PublicContext(candidate, client, str(candidate.base_url).rstrip("/"))

            # One public base request supplies both reachability and auth evidence.
            started = time.perf_counter()
            try:
                base_response = await client.get(public.base_url)
            except (UnsafeNetworkTarget, RequestBudgetExceeded, httpx.HTTPError, ValueError) as exc:
                message = f"{type(exc).__name__}: {exc}"
                result.overall_status = transport_status(message)
                result.reachable = False
                result.errors.append(ValidationError(probe="reachability", message=redact_text(message, 500)))
                result.request_count = policy.requests_made
                return result
            result.latency_ms = (time.perf_counter() - started) * 1000
            result.reachable = base_response.status_code < 500
            auth_required, auth_scheme, auth_evidence = _auth_from_response(base_response)
            result.auth_required = auth_required
            result.auth_scheme = auth_scheme
            result.evidence.extend([f"Base HTTP {base_response.status_code}", *auth_evidence])
            if options.inspect_rate_limits:
                result.rate_limit = _parse_rate_limit(dict(base_response.headers))

            if self._cancel_event.is_set():
                result.overall_status = ValidationStatus.CANCELLED
                result.request_count = policy.requests_made
                return result

            # Protocol detection gets a credential-free context and uses the same budgeted client.
            try:
                detection, adapter = await detect_protocol(public, bool(result.reachable))
            except (UnsafeNetworkTarget, RequestBudgetExceeded, httpx.HTTPError) as exc:
                result.errors.append(ValidationError(probe="protocol", message=redact_text(str(exc), 500)))
                detection = None
                from raven_validator.adapters.generic_rest import GenericRESTAdapter
                adapter = GenericRESTAdapter()
            if detection:
                result.detected_protocol = detection.protocol
                result.protocol_confidence = detection.confidence
                result.evidence.extend(detection.evidence)

            outcomes: list[ProbeOutcome] = []
            # Standard adds a public model probe. It cannot access any secret.
            if options.mode in {"standard", "authorized"} and not self._cancel_event.is_set():
                try:
                    model_out = await adapter.public_models(public)
                    outcomes.append(model_out)
                except RequestBudgetExceeded as exc:
                    result.errors.append(ValidationError(probe="models", message=str(exc)))

            credential: tuple[CredentialProfile, str] | None = None
            if options.mode == "authorized" and self.credential_resolver is not None:
                credential = self.credential_resolver(candidate)
            result.credential_configured = credential is not None

            # Only now is a secret introduced, after explicit Authorized mode.
            if options.mode == "authorized" and credential is not None and not self._cancel_event.is_set():
                profile, secret = credential
                from raven_validator.credentials.manager import CredentialManager
                auth_headers = CredentialManager.build_headers(profile, secret)
                # Anthropic adapters require x-api-key; if user picked generic bearer but
                # protocol is Anthropic, use the protocol-correct header without changing storage.
                if result.detected_protocol == "anthropic-compatible" and profile.auth_type.value == "bearer":
                    auth_headers = {"x-api-key": secret}
                authorized = AuthorizedContext(candidate, client, public.base_url, auth_headers, options.model)
                result.credential_used = True

                try:
                    auth_models = await adapter.authorized_models(authorized)
                    outcomes.append(auth_models)
                except RequestBudgetExceeded:
                    pass
                if not self._cancel_event.is_set():
                    try:
                        generation = await adapter.generate(authorized)
                        outcomes.append(generation)
                        result.authorized_test_succeeded = generation.success
                    except RequestBudgetExceeded as exc:
                        result.errors.append(ValidationError(probe="generation", message=str(exc)))
                if options.test_streaming and not self._cancel_event.is_set():
                    try:
                        outcomes.append(await adapter.stream(authorized))
                    except RequestBudgetExceeded:
                        pass
                if options.check_quota and not self._cancel_event.is_set():
                    try:
                        outcomes.append(await adapter.quota(authorized))
                    except RequestBudgetExceeded:
                        result.quota = QuotaInfo(status="UNKNOWN", known=False, reason="Request budget exhausted")

            # Consume normalized outcomes.
            for out in outcomes:
                if out.name == "models" and out.success:
                    models = out.data.get("models")
                    if isinstance(models, list):
                        result.models = list(dict.fromkeys(str(x) for x in models))
                        result.capabilities["models"] = True
                elif out.name == "generation":
                    result.capabilities["generation"] = out.success
                elif out.name == "streaming":
                    result.capabilities["streaming"] = out.success
                elif out.name == "quota":
                    q = out.data
                    result.quota = QuotaInfo(
                        status=str(q.get("status", "UNKNOWN")), known=bool(q.get("known")),
                        balance=float(q["balance"]) if isinstance(q.get("balance"), (int, float)) else None,
                        unit=str(q["unit"]) if q.get("unit") is not None else None,
                        reason=str(q["reason"]) if q.get("reason") is not None else None,
                    )
                if options.inspect_rate_limits and isinstance(out.data.get("headers"), dict):
                    parsed = _parse_rate_limit({str(k): str(v) for k,v in out.data["headers"].items()})
                    if parsed.known:
                        result.rate_limit = parsed
                result.evidence.extend(out.evidence)
                if out.error:
                    result.errors.append(ValidationError(probe=out.name, message=redact_text(out.error, 500), http_status=out.http_status))

            # Status precedence: successful authorized functional test means WORKING
            # even though auth_required remains True as an independent fact.
            generation = next((o for o in outcomes if o.name == "generation"), None)
            if self._cancel_event.is_set():
                result.overall_status = ValidationStatus.CANCELLED
            elif generation and generation.success:
                result.overall_status = ValidationStatus.WORKING
            elif generation and _explicit_insufficient(generation):
                result.overall_status = ValidationStatus.INSUFFICIENT_CREDITS
            elif generation and generation.http_status == 429:
                result.overall_status = ValidationStatus.RATE_LIMITED
            elif generation and generation.http_status in {401, 403}:
                result.overall_status = ValidationStatus.INVALID_CREDENTIAL
            elif result.auth_required:
                result.overall_status = ValidationStatus.REACHABLE_AUTH_REQUIRED
            elif result.reachable:
                result.overall_status = ValidationStatus.WORKING if result.detected_protocol != "unknown" else ValidationStatus.REACHABLE_UNSUPPORTED
            else:
                result.overall_status = ValidationStatus.SERVER_ERROR
            result.request_count = policy.requests_made
            return result

    async def validate_batch(self, candidates: list[APICandidate], options: ValidationOptions) -> AsyncGenerator[BatchEvent, None]:
        self.reset_cancel()
        total = len(candidates)
        done_count = 0
        yield BatchEvent("run_started", progress=(0, total))
        sem = asyncio.Semaphore(self.settings.max_concurrency)

        async def one(c: APICandidate) -> ValidationResult:
            async with sem:
                if self._cancel_event.is_set():
                    return ValidationResult(candidate_id=c.id, run_id=uuid4(), base_url=str(c.base_url), overall_status=ValidationStatus.CANCELLED)
                return await self.validate_one(c, options)

        tasks = {asyncio.create_task(one(c)): c for c in candidates}
        pending = set(tasks)
        while pending:
            if self._cancel_event.is_set():
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                yield BatchEvent("run_cancelled", progress=(done_count, total))
                return  # terminal event is mutually exclusive with run_finished
            finished, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in finished:
                c = tasks[task]
                try:
                    result = task.result()
                except asyncio.CancelledError:
                    continue
                except Exception as exc:  # noqa: BLE001 - isolate a single candidate's failure so it doesn't abort the batch
                    result = ValidationResult(
                        candidate_id=c.id, run_id=uuid4(), base_url=str(c.base_url),
                        overall_status=ValidationStatus.UNKNOWN,
                        errors=[ValidationError(probe="batch", message=redact_text(f"{type(exc).__name__}: {exc}", 500))],
                    )
                done_count += 1
                yield BatchEvent("candidate_finished", candidate_id=c.id, result=result, progress=(done_count, total))
        yield BatchEvent("run_finished", progress=(done_count, total))
