# DEVELOPMENT_TRACKER.md

## Current Milestone

Milestone 2 — Networking & Public Probes (complete, pending commit)

## Completed

- M0 Bootstrap (committed 94805ba)
- M1 Domain & Security Foundation (committed e6bf009)
- M2.1 Engine + probe base (ValidationEngine, ProbeContext/ProbeResult/Probe contract)
- M2.2 Public probes (reachability HEAD→GET fallback, auth detection, OpenAPI schema)
- M2.3 Retry + status mapping (tenacity transient-only retry, central HTTP→status map)
- M2.4 Result normalization (evidence merge, confidence, precise status derivation)
- M2.5 Verification (ruff clean, 74/74 pytest pass, engine smoke test OK)

## In Progress

- (none)

## Next

- Milestone 3 — Protocol Adapters

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
