# DEVELOPMENT_TRACKER.md

## Current Milestone

Packaging — PyInstaller (complete, verified on Linux)

## Completed

- M0 Bootstrap (committed 94805ba)
- M1 Domain & Security Foundation (committed e6bf009)
- M2 Networking & Public Probes (committed 1ce51be)
- M3 Protocol Adapters (committed ef810ed)
- M4 Authorized Credentials (committed 366835a)
- M5 Functional Probes (committed 1b7832d)
- M6 Persistence (committed b1661a5)
- M7 GUI Shell (committed c003846)
- M8 End-to-End Validation (committed 6eb46f9)
- M9 Import / Export (committed 4156e8e)
- M10 Polish & Release Candidate (committed 8c175a4)
- Packaging — PyInstaller 6.22.2: `pyinstaller --windowed --name Raven-Validator --paths src --collect-all pydantic/pydantic-settings/sqlalchemy/httpx/tenacity/keyring --hidden-import raven_validator app.py` → `dist/Raven-Validator/` (directory, ELF 64-bit, 12 MB binary + 51 MB _internal, 221 MB total, PySide6 + all deps); tested `QT_QPA_PLATFORM=offscreen dist/Raven-Validator/Raven-Validator` (propagateSizeHints warning only, GUI up); one-file variant documented; Windows `.exe` / macOS `.app` / Linux AppImage instructions + `Raven-Validator.spec` checked in
- Packaging verification: `ruff` clean, `pytest` 138 passed, `python app.py` still works via `python app.py`

## Completed

- M0 Bootstrap (committed 94805ba)
- M1 Domain & Security Foundation (committed e6bf009)
- M2 Networking & Public Probes (committed 1ce51be)
- M3 Protocol Adapters (committed ef810ed)
- M4 Authorized Credentials (committed 366835a)
- M5 Functional Probes (committed 1b7832d)
- M6 Persistence (committed b1661a5)
- M7 GUI Shell (committed c003846)
- M8 End-to-End Validation (committed 6eb46f9)
- M9 Import / Export (committed 4156e8e)
- M10.1 GUI polish — Results filtering (Search + status combo, filtered-empty hint) + sorting (QTableWidget), detail evidence (Summary/Connectivity/Protocol/Authentication/Probe Timeline/Capabilities/Models/Functional Test/Streaming/Rate Limits/Quota/Errors/Evidence; UserRole id storage surviving sort/filter), empty-state & error-message improvements
- M10.2 Documentation — README (quickstart, architecture, features, packaging), CHANGELOG 1.0.0 RC, QWEN.md (V1 RC status, ValidationWorker→ValidationService→Engine signal chain)
- M10.3 Verification (ruff clean, 138/138 pytest pass, security review PASS, offscreen GUI smoke: nav + import + validation run + detail + filter + export)

## In Progress

- (none)

## Next

- Distribute: Windows build on Windows host (`dist\Raven-Validator\Raven-Validator.exe`), macOS build (`dist/Raven-Validator.app` + DMG), Linux AppImage via `linuxdeploy`; `build/` and `dist/` remain gitignored
- V1.1 (Gemini/Ollama/HF adapters, custom probe templates, scheduled re-validation, etc.) — see Manifest

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
- `pytest` (M9) → 138 passed (added JSON/CSV/Targeter imports, malformed-row tolerance, secret-absent exports)
- `pytest` (M10) → 138 passed (no new tests; polish verified via GUI smoke)
- GUI smoke (M7) → MainWindow 6 nav items, dashboard stats live from DB, candidates CRUD, validator toggles, results table, credentials fingerprint — no network on main thread, no detached instance
- GUI smoke (M8) → QThread ValidationWorker, batch_event→progressive Results/Dashboard refresh, CANCEL preserves partial results
- GUI smoke (M9) → JSON import (1 good/1 bad) → candidates table, JSON export round-trip
- GUI smoke (M10) → Results filter (Search+status) + filtered-empty hint, sorting survives detail lookup via UserRole, detail shows Probe Timeline (latency/http/excerpt), auth evidence, functional/streaming/quota sections; .env not leaked
- Engine smoke test → REACHABLE_AUTH_REQUIRED with bearer evidence, confidence 0.95
- M5 smoke → authorized generation + streaming + rate-limit parse + UNKNOWN quota (no failure collapse)
- E2E smoke (M8) → quick/standard/authorized modes with openai-compatible detection, model snapshot + rate-limit persistence
- Security review (M10) → PASS: no secret in logs (RedactionFilter), SQLite (model_dump_safe), exports (JSON/CSV), DetectedSecret metadata-only, RequestPolicy ceiling

## Known Issues

- (none)

## Architecture Decisions

- Python 3.12+, PySide6 GUI, httpx async networking, SQLAlchemy 2.x, Pydantic 2.x, keyring for secrets, SQLite for V1.
- Package layout: `src/raven_validator/` with config/domain/core/adapters/probes/credentials/security/database/services/gui/utils subpackages.

## Security Decisions

- Raw credentials live only in OS keychain. SQLite stores profile metadata only.
- Discovered credential-like material is classified/redacted, never auto-used.
- Central redaction module applies to logs, DB excerpts, GUI, exports.
