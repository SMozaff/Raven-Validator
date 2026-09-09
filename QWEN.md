# QWEN.md — Raven-Validator Agent Instructions

## Product Purpose

Raven-Validator is a cross-platform desktop app that validates AI API endpoints. Core question: "What can be safely verified about this API, and—when I provide an authorized credential—does the API actually work and what limits are explicitly exposed?"

## Separation from Raven-Targeter

- Raven-Targeter discovers candidate APIs. Raven-Validator validates them.
- Never merge the two apps or import Raven-Targeter as a Python package.
- Only relationship: versioned JSON/CSV interchange (`raven-discovery-export-v1`).

## Security Boundary (Architectural, Not Optional)

- Credential-like strings in public sources (repos, READMEs, gists, logs, imports) must NEVER be auto-used for auth.
- Raven-Validator may: detect, classify, redact, report location of such material.
- Raven-Validator must NOT: store raw secret, test it, validate it, or use it in requests.
- Authenticated testing only with user-configured authorized credential profiles (OS keychain via `keyring`).
- Enforce in: code architecture, GUI wording, tests, docs.
- Security tests are release-blocking.

## Architecture Rules

- Business logic independent from GUI. Adapters independent from widgets.
- No network operations in Qt main thread. Use ValidationController → async worker → ValidationService → Engine → Adapters/Probes. Emit Qt signals progressively.
- Central status/error mapping (`core/status_mapper.py`), central redaction (`security/redaction.py`).
- No giant God classes. No silent `except Exception: pass`. No hard-coded absolute paths.
- Pydantic models for domain. UTC-aware datetimes. pathlib everywhere.
- Async HTTP via httpx with bounded concurrency (default 10).

## Testing Rules

- Normal tests must NOT require live APIs. Use httpx MockTransport, mocks, fixtures.
- Security tests: auth headers never in logs, keys never in SQLite/export, discovered secrets never auto-used.
- Integration tests marked `integration`, excluded from default `pytest` run. No real credentials in test code.

## GUI/Threading Rules

- PySide6. Never block Qt main thread with network I/O.
- Signals: run_started, candidate_started, probe_started, probe_finished, candidate_finished, progress_changed, run_cancelled, run_finished.

## Coding Conventions

- Python 3.12+, type hints everywhere, line-length 100, ruff.
- Probe safety levels: PASSIVE < READ_ONLY < MINIMAL_GENERATION < CUSTOM_AUTHORIZED.
- Default run must not exceed READ_ONLY unless user enables authorized testing.

## Current Status

Milestone 0 (Bootstrap): in progress. See DEVELOPMENT_TRACKER.md.

## Commands

```bash
python app.py          # Launch GUI
ruff check .           # Lint
pytest                 # Unit tests (no live APIs)
pytest -m integration  # Optional live tests
```
