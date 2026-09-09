# DEVELOPMENT_TRACKER.md

## Current Milestone

Milestone 6 — Persistence (complete, pending commit)

## Completed

- M0 Bootstrap (committed 94805ba)
- M1 Domain & Security Foundation (committed e6bf009)
- M2 Networking & Public Probes (committed 1ce51be)
- M3 Protocol Adapters (committed ef810ed)
- M4 Authorized Credentials (committed 366835a)
- M5 Functional Probes (committed 1b7832d)
- M6.1 SQLAlchemy ORM (9 tables: api_candidates, validation_runs, probe_results, capability/model/rate_limit/quota_snapshots, credential_profiles, validation_errors; auto-create on first run)
- M6.2 Database + Repository (engine, session context, candidate/run/probe/snapshot/error/credential-profile CRUD with redaction, save_validation_result convenience)
- M6.3 Verification (ruff clean, 127/127 pytest pass; no secret in DB; history persists across restarts)

## In Progress

- (none)

## Next

- Milestone 7 — GUI Shell

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
