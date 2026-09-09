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
- No network operations in Qt main thread. Use `ValidatorPage.ValidationWorker (QObject + asyncio.new_event_loop in QThread)` → `ValidationService.validate_batch` (`AsyncGenerator[BatchEvent]`) → `ValidationEngine`/`ProbeRunner` → Adapters/Probes. Emit Qt signals (`batch_event` → Results/Dashboard `refresh()`) progressively.
- Central status/error mapping (`core/status_mapper.py`), central redaction (`security/redaction.py` + `utils/logging.RedactionFilter`).
- No giant God classes. No silent `except Exception: pass`. No hard-coded absolute paths.
- Pydantic models for domain. UTC-aware datetimes. pathlib everywhere.
- Async HTTP via httpx with bounded concurrency (default 10), request budget (default 6/API), tenacity transient-only retries.

## Testing Rules

- Normal tests must NOT require live APIs. Use httpx `MockTransport`, mocks, fixtures.
- Security tests: auth headers never in logs, keys never in SQLite/export, discovered secrets never auto-used — 138 tests in `pytest`.
- Integration tests marked `integration`, excluded from default `pytest` run. No real credentials in test code.

## GUI/Threading Rules

- PySide6. Never block Qt main thread with network I/O.
- Signals: `run_started`, `candidate_started`, `candidate_finished`, `progress`, `run_finished`, `run_cancelled` (via `BatchEvent.kind`). Detail: `ResultsPage` filter (`Search` + status `ComboBox`) + sorted `QTableWidget`; `ResultDetailDialog` shows full Probe Timeline + Capabilities + Rate Limits + Quota + Errors (all redacted).

## Coding Conventions

- Python 3.12+, type hints everywhere, line-length 100, ruff (`E/F/I/W/UP/B/C4/SIM`, per-file-ignores for `E501` in DB/GUI/services/tests).
- Probe safety levels: `PASSIVE < READ_ONLY < MINIMAL_GENERATION < CUSTOM_AUTHORIZED`.
- Default run must not exceed `READ_ONLY` unless user enables authorized testing + links a credential profile.

## Current Status

**V1 Release Candidate — 2026-09-09** (commits `94805ba` → `4156e8e`, M0–M9 done, M10 in progress).

- M0 Bootstrap, M1 Domain/Security, M2 Networking/Public Probes, M3 Protocol Adapters, M4 Authorized Credentials, M5 Functional Probes, M6 Persistence, M7 GUI Shell, M8 End-to-End Validation, M9 Import/Export — all committed, `ruff` clean, `pytest` 138 passed.
- M10 Polish: Results filtering/sorting, detail evidence (Probe Timeline etc.), README/CHANGELOG/QWEN.md final, security review — in progress.

## Commands

```bash
python app.py          # Launch GUI
ruff check .           # Lint
pytest                 # Unit tests (no live APIs)
pytest -m integration  # Optional live tests (none by default)
QT_QPA_PLATFORM=offscreen python -c "from raven_validator.gui.main_window import MainWindow; ..."  # CI smoke
```
