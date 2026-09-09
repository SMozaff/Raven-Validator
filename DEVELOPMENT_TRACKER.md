# DEVELOPMENT_TRACKER.md

## Current Milestone

Milestone 7 — GUI Shell (complete, pending commit)

## Completed

- M0 Bootstrap (committed 94805ba)
- M1 Domain & Security Foundation (committed e6bf009)
- M2 Networking & Public Probes (committed 1ce51be)
- M3 Protocol Adapters (committed ef810ed)
- M4 Authorized Credentials (committed 366835a)
- M5 Functional Probes (committed 1b7832d)
- M6 Persistence (committed b1661a5)
- M7.1 MainWindow with Database injection, auto-refresh on navigation, dispose on close
- M7.2 Dashboard — live stats from DB (Total/Working/Auth Required/Rate Limited/Insufficient/Offline/Unknown/Last Validation)
- M7.3 Candidates — QTableWidget with add/edit/delete, import placeholders, validate hooks, URL validation, empty state
- M7.4 Validator — depth (Quick/Standard/Authorized/Custom), concurrency, timeout, streaming/quota/rate-limit toggles (quota & streaming visibly optional), progress + start/cancel
- M7.5 Results — runs table with 13 columns, status handling, double-click detail; ResultDetail dialog with Summary/Connectivity/Capabilities/Models/RateLimits/Quota/Errors/Evidence (redacted)
- M7.6 Credentials — profile CRUD (add/edit/replace/delete), fingerprint display (••••••••XXXX), memory keychain fallback
- M7.7 Settings — DB URL, log level, timeouts, concurrency, max requests per API, default depth (session-only save)
- M7.8 Verification (ruff clean, 127/127 pytest pass, GUI smoke: nav + candidates + dashboard + persistence OK, no detached instance)

## In Progress

- (none)

## Next

- Milestone 8 — End-to-End Validation

## Files Changed

- pyproject.toml (created)
- .gitignore (created)
- .env.example (created)
- README.md (expanded)
- QWEN.md (created)
- DEVELOPMENT_TRACKER.md (created)
- CHANGELOG.md (created)

## Tests Run

- `ruff check .` → All checks passed
- `pytest -v` → 4 passed (test_settings.py)
- GUI smoke test (QT_QPA_PLATFORM=offscreen) → MainWindow OK, 6 nav items, 6 pages
- `pytest -v` (M1) → 37 passed (settings, url_normalizer, redaction, request_policy, status_mapper)
- `pytest` (M2) → 74 passed (added reachability/auth/openapi mocked suite + HTTP mapping)
- `pytest` (M3) → 87 passed (added protocol/openai/anthropic adapter tests)
- `pytest` (M4) → 104 passed (added auth_detector + credential_security: no secret in SQLite/logs/export)
- `pytest` (M5) → 121 passed (added models/generation/streaming/rate_limit/quota probes)
- `pytest` (M6) → 127 passed (schema, candidate/run/probe/snapshot/credential CRUD; no secret in DB; persistence across restarts)
- `pytest` (M7) → 127 passed (no new tests; GUI verified via offscreen smoke)
- GUI smoke (M7) → MainWindow 6 nav items, dashboard stats live from DB, candidates CRUD, validator toggles, results table, credentials fingerprint — no network on main thread, no detached instance
- Engine smoke test → REACHABLE_AUTH_REQUIRED with bearer evidence, confidence 0.95
- M5 smoke → authorized generation + streaming + rate-limit parse + UNKNOWN quota (no failure collapse)

## Known Issues

- (none)

## Architecture Decisions

- Python 3.12+, PySide6 GUI, httpx async networking, SQLAlchemy 2.x, Pydantic 2.x, keyring for secrets, SQLite for V1.
- Package layout: `src/raven_validator/` with config/domain/core/adapters/probes/credentials/security/database/services/gui/utils subpackages.

## Security Decisions

- Raw credentials live only in OS keychain. SQLite stores profile metadata only.
- Discovered credential-like material is classified/redacted, never auto-used.
- Central redaction module applies to logs, DB excerpts, GUI, exports.
