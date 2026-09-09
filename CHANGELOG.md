# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] - 2026-09-09 — Release Candidate

### Added

- **Bootstrap (M0)**: project skeleton, `pyproject.toml`, `.gitignore`, `.env.example`, PySide6 shell (Dashboard/Candidates/Validator/Results/Credentials/Settings), config/logging/settings, `app.py`, `ruff` + `pytest` harness.
- **Domain & Security (M1)**: `ValidationStatus` (18 statuses), `APICandidate`/`ValidationResult`/`CapabilityResult`/`CredentialProfile` Pydantic models, strict URL normalization (http/https only, no silent http→https), central redaction, secret detector (metadata-only), `RequestPolicy` safety ceilings + budgets.
- **Networking & Public Probes (M2)**: `ValidationEngine` (pooled `httpx.AsyncClient`, semaphore), `ReachabilityProbe` (HEAD→GET, latency/redirect/TLS), `AuthProbe` (401/403 + WWW-Authenticate + body markers), `OpenAPISchemaProbe`, tenacity transient-only retries, central `status_mapper`, `result_normalizer`.
- **Protocol Adapters (M3)**: `APIAdapter` contract, `DetectionResult`, `detect_protocol` (highest-confidence), `OpenAICompatibleAdapter` (`/v1/models` shape), `AnthropicCompatibleAdapter` (`/v1/messages` + `x-api-key`), `GenericRESTAdapter` (safe GET only; `{{credential}}` template only when explicit), `capability_detector`.
- **Authorized Credentials (M4)**: `KeychainBackend` (keyring + memory fallback, SHA-256 `••••••••XXXX` fingerprint), `CredentialProfileStore` / `CredentialManager` (bearer / api-key-header / basic / custom-header injection, redacted logging).
- **Functional Probes (M5)**: `ModelsProbe` (dedupe/snapshot), `GenerationProbe` (1× `Reply with OK.` / 3 tokens), `StreamingProbe` (SSE, first-chunk latency), `RateLimitProbe` (X-RateLimit/RateLimit/Retry-After), `QuotaProbe` (optional, `KNOWN/UNKNOWN/INSUFFICIENT`, never by consumption).
- **Persistence (M6)**: SQLAlchemy ORM (9 tables: `api_candidates`, `validation_runs`, `probe_results`, `capability_snapshots`, `model_snapshots`, `rate_limit_snapshots`, `quota_snapshots`, `credential_profiles`, `validation_errors`), `Database` (auto-create, `check_same_thread=False`), `Repository` (CRUD + `save_validation_result`).
- **GUI Shell (M7)**: `MainWindow` with `Database` injection + auto-refresh, Dashboard live stats, Candidates table (CRUD + URL validation + import placeholders + detached-instance fix), Validator (depth/modes + concurrency/timeout + streaming/quota toggles + progress/Cancel), Results (13 columns + sorting + empty states), `ResultDetailDialog` (Summary/Connectivity/Capabilities/Models/…/Evidence redacted), Credentials (fingerprint-only), Settings (session-only save).
- **End-to-End Validation (M8)**: `ValidationService` (mode-aware pipeline, `asyncio.Semaphore`, `validate_one` + `validate_batch` as `AsyncGenerator[BatchEvent]`, real cancellation via `asyncio.wait` + pending drain), `ValidationWorker` (`QObject` + `asyncio.new_event_loop()` in `QThread`, `batch_event` Signal, progressive `Results`/`Dashboard` refresh, no network on Qt main thread).
- **Import / Export (M9)**: `ImportService` (JSON/CSV/Targeter tolerant per-row, `candidate_endpoints` expansion, `raven-discovery-export-v1`), `ExportService` (JSON/CSV secret-free), GUI wiring for import/export dialogs.
- **Polish (M10)**: Results filtering (`Search` + status `All/WORKING/...`) + filtered-empty hint, detail evidence sections (Summary/Connectivity/Protocol/Authentication/Probe Timeline/Capabilities/Models/Functional Test/Streaming/Rate Limits/Quota/Errors/Evidence), README/QWEN.md/CHANGELOG final, security review.

### Security

- No raw credential reaches logs, SQLite, GUI diagnostics, or exports (central redaction + `model_dump_safe` + `RedactionFilter`).
- `DetectedSecret` is metadata-only (`value == "[REDACTED]"`, no usable API).
- `RequestPolicy` ceiling: `READ_ONLY` by default; `MINIMAL_GENERATION`/`CUSTOM_AUTHORIZED` only with an explicitly authorized profile.

## [Unreleased]

- (none)
