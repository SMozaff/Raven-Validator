# DEVELOPMENT_TRACKER.md

## Current Milestone

Milestone 3 — Protocol Adapters (complete, pending commit)

## Completed

- M0 Bootstrap (committed 94805ba)
- M1 Domain & Security Foundation (committed e6bf009)
- M2 Networking & Public Probes (committed 1ce51be)
- M3.1 Adapter base contract + protocol detector (DetectionResult, adapter Protocol, detect_protocol)
- M3.2 Protocol adapters (OpenAI /v1/models shape, Anthropic /v1/messages + x-api-key, Generic REST safe-only)
- M3.3 Capability detector (independent per-route, OpenAPI path augmentation)
- M3.4 Verification (ruff clean, 87/87 pytest pass)

## In Progress

- (none)

## Next

- Milestone 4 — Authorized Credentials

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
- Engine smoke test → REACHABLE_AUTH_REQUIRED with bearer evidence, confidence 0.95

## Known Issues

- (none)

## Architecture Decisions

- Python 3.12+, PySide6 GUI, httpx async networking, SQLAlchemy 2.x, Pydantic 2.x, keyring for secrets, SQLite for V1.
- Package layout: `src/raven_validator/` with config/domain/core/adapters/probes/credentials/security/database/services/gui/utils subpackages.

## Security Decisions

- Raw credentials live only in OS keychain. SQLite stores profile metadata only.
- Discovered credential-like material is classified/redacted, never auto-used.
- Central redaction module applies to logs, DB excerpts, GUI, exports.
