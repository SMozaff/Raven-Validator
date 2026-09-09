# DEVELOPMENT_TRACKER.md

## Current Milestone

Milestone 1 — Domain & Security Foundation (complete, pending commit)

## Completed

- M0 Bootstrap (committed 94805ba)
- M1.1 Domain models (statuses, candidates, results, capabilities, credentials)
- M1.2 URL normalization (strict scheme/path/port handling, dedup canonicalization)
- M1.3 Security foundation (redaction, secret_detector, request_policy)
- M1.4 Security-first tests (url, redaction, request_policy, status taxonomy)
- M1.5 Verification (ruff clean, 37/37 pytest pass)

## In Progress

- (none)

## Next

- Milestone 2 — Networking & Public Probes

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

## Known Issues

- (none)

## Architecture Decisions

- Python 3.12+, PySide6 GUI, httpx async networking, SQLAlchemy 2.x, Pydantic 2.x, keyring for secrets, SQLite for V1.
- Package layout: `src/raven_validator/` with config/domain/core/adapters/probes/credentials/security/database/services/gui/utils subpackages.

## Security Decisions

- Raw credentials live only in OS keychain. SQLite stores profile metadata only.
- Discovered credential-like material is classified/redacted, never auto-used.
- Central redaction module applies to logs, DB excerpts, GUI, exports.
