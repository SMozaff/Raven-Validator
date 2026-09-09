# DEVELOPMENT_TRACKER.md

## Current Milestone

Milestone 8 — End-to-End Validation (complete, pending commit)

## Completed

- M0 Bootstrap (committed 94805ba)
- M1 Domain & Security Foundation (committed e6bf009)
- M2 Networking & Public Probes (committed 1ce51be)
- M3 Protocol Adapters (committed ef810ed)
- M4 Authorized Credentials (committed 366835a)
- M5 Functional Probes (committed 1b7832d)
- M6 Persistence (committed b1661a5)
- M7 GUI Shell (committed c003846)
- M8.1 ValidationService — mode-aware probe pipeline (Quick/Standard/Authorized+streaming/quota), protocol detection, capability merge, rate-limit/quota/status mapping, SQLite persistence of runs/snapshots/probe results/errors
- M8.2 GUI wiring — ValidationWorker (QObject+asyncio loop) in QThread, batch_event Signal, progress bar, START/CANCEL, progressive results via MainWindow batch_event→Results/Dashboard refresh, no network on main thread
- M8.3 Verification (ruff clean, 131/131 pytest pass; batch 10/partial/progress/cancellation; E2E quick/standard/authorized smoke with persistence)

## In Progress

- (none)

## Next

- Milestone 9 — Import / Export

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
- `pytest` (M8) → 131 passed (added batch 10/partial/progress/cancellation + E2E service)
- GUI smoke (M7) → MainWindow 6 nav items, dashboard stats live from DB, candidates CRUD, validator toggles, results table, credentials fingerprint — no network on main thread, no detached instance
- GUI smoke (M8) → QThread ValidationWorker, batch_event→progressive Results/Dashboard refresh, CANCEL preserves partial results
- Engine smoke test → REACHABLE_AUTH_REQUIRED with bearer evidence, confidence 0.95
- M5 smoke → authorized generation + streaming + rate-limit parse + UNKNOWN quota (no failure collapse)
- E2E smoke (M8) → quick/standard/authorized modes with openai-compatible detection, model snapshot + rate-limit persistence

## Known Issues

- (none)

## Architecture Decisions

- Python 3.12+, PySide6 GUI, httpx async networking, SQLAlchemy 2.x, Pydantic 2.x, keyring for secrets, SQLite for V1.
- Package layout: `src/raven_validator/` with config/domain/core/adapters/probes/credentials/security/database/services/gui/utils subpackages.

## Security Decisions

- Raw credentials live only in OS keychain. SQLite stores profile metadata only.
- Discovered credential-like material is classified/redacted, never auto-used.
- Central redaction module applies to logs, DB excerpts, GUI, exports.
