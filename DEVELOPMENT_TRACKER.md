# DEVELOPMENT_TRACKER.md

## Current Milestone

Milestone 0 — Bootstrap (complete, pending commit)

## Completed

- M0.1 Project skeleton (pyproject.toml, .gitignore, .env.example, dirs)
- M0.2 Documentation (README, QWEN.md, DEVELOPMENT_TRACKER.md, CHANGELOG.md)
- M0.3 Config & logging (settings.py, defaults.py, logging.py, dates.py, urls.py stub)
- M0.4 Minimal GUI (app.py, main_window.py, 6 stub pages)
- M0.5 Initial tests (test_settings.py, conftest.py)
- M0.6 Verification (ruff clean, 4/4 pytest pass, GUI launches offscreen)

## In Progress

- (none)

## Next

- Milestone 1 — Domain & Security Foundation

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

## Known Issues

- (none)

## Architecture Decisions

- Python 3.12+, PySide6 GUI, httpx async networking, SQLAlchemy 2.x, Pydantic 2.x, keyring for secrets, SQLite for V1.
- Package layout: `src/raven_validator/` with config/domain/core/adapters/probes/credentials/security/database/services/gui/utils subpackages.

## Security Decisions

- Raw credentials live only in OS keychain. SQLite stores profile metadata only.
- Discovered credential-like material is classified/redacted, never auto-used.
- Central redaction module applies to logs, DB excerpts, GUI, exports.
