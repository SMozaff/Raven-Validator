# Raven-Validator

**Is this API reachable? What protocol does it use? Does it require authentication? What capabilities does it expose? If I provide an authorized credential, does it work, what models are available, and what quota/rate-limit information can be verified?**

Cross-platform desktop application for validating AI API endpoints. Built with Python 3.12+, PySide6, httpx (async), SQLAlchemy + SQLite, Pydantic, tenacity, and keyring.

## Relationship to Raven-Targeter

- **Raven-Targeter** discovers candidate APIs from public sources.
- **Raven-Validator** receives API candidates and validates them.

The two are separate products. They share only a versioned interchange format (`raven-discovery-export-v1`: `title/url/provider/classification/candidate_endpoints/source/source_type/evidence`). Neither imports the other's Python package.

## Critical Security Rule

A credential-like string discovered in a public repository, README, Gist, log, or imported discovery record is **never** automatically used for authentication. Raven-Validator will detect/classify/redact/report it, but will not store the raw secret, test it, or send it. Authenticated testing is allowed only with a credential the user explicitly configures as an authorized credential profile (OS keychain via `keyring`).

## Features (V1)

- Manual API entry + JSON / CSV / Raven-Targeter (`raven-discovery-export-v1`) import (tolerant per-row error handling)
- Safe public inspection: URL normalization, reachability (HEAD→GET fallback, latency, redirects, TLS), auth-requirement detection, public `/models` and OpenAPI metadata
- Protocol detection (openai-compatible / anthropic-compatible / generic-rest / unknown) with confidence + evidence
- Authorized tests (only with user credential): model list, minimal generation (`Reply with OK.` / 3 tokens), optional streaming (first-chunk latency), rate-limit header parsing, optional quota/credit (`KNOWN/UNKNOWN/UNSUPPORTED/INSUFFICIENT`)
- Normalized result model: `WORKING / REACHABLE_AUTH_REQUIRED / RATE_LIMITED / INSUFFICIENT_CREDITS / ... / CANCELLED / UNKNOWN` (18 precise statuses)
- Batch validation with bounded concurrency (default 10), request budget (default 6 per API), tenacity retries (transient only), real cancellation
- SQLite persistence (candidates, runs, probe results, capability/model/rate-limit/quota snapshots, credential metadata), never secrets
- PySide6 GUI: Dashboard (live stats), Candidates (table + filters/sort + CRUD + import), Validator (Quick/Standard/Authorized + streaming/quota toggles + progress/Cancel), Results (13 columns + filter + detail + sorting), Credentials (fingerprint `••••••••XXXX`), Settings
- Exports: JSON / CSV (secret-free)
- No network on the Qt main thread (QThread + asyncio worker + Qt signals)

## Quickstart

```bash
pip install -e ".[dev]"
python app.py
```

Copy `.env.example` to `.env` to override defaults:

```
RAVEN_VALIDATOR_DB_URL=sqlite:///data/raven_validator.db
RAVEN_VALIDATOR_LOG_LEVEL=INFO
RAVEN_VALIDATOR_CONNECT_TIMEOUT=10
RAVEN_VALIDATOR_READ_TIMEOUT=30
RAVEN_VALIDATOR_MAX_CONCURRENCY=10
RAVEN_VALIDATOR_MAX_REQUESTS_PER_API=6
```

Credentials belong in **Credentials → Add Credential Profile** (stored in OS keychain, shown as `Configured` + `••••••••XXXX` fingerprint), never in `.env`.

## Development

```bash
ruff check .          # lint
pytest                # unit tests (no live APIs; 138+ tests)
pytest -m integration # optional live tests (none by default)

python app.py         # launch GUI (QT_QPA_PLATFORM=offscreen for CI smoke)
```

## Architecture

```
PySide6 GUI (main thread)
      │
      ▼
ValidationController (QThread + event loop)
      │
      ▼
ValidationService  ──►  ValidationEngine (httpx.AsyncClient, semaphore, ProbeRunner/tenacity)
                            │
               ┌────────────┼────────────┐
               ▼            ▼            ▼
           OpenAI      Anthropic     Generic REST
           Adapter      Adapter       Adapter
               │            │            │
               └────────────┼────────────┘
                            ▼
                    Probes (reachability, auth, openapi, models, generation, streaming, rate_limits, quota)
                            │
                            ▼
                     SQLite (SQLAlchemy ORM)  ──►  keyring (secrets)
```

Key invariants: central `status_mapper`, central `redaction`, `request_policy` budgets/safety ceilings, evidence-based confidence.

## Packaging

After verifying `ruff check .` and `pytest` (138 tests):

```bash
# Development — always runnable as:
python app.py

# ── Linux (this host, Debian 13) — tested 2026-09-09 ──
# Requires: pip install pyinstaller
# The src-layout needs --paths src; collect-all ensures pydantic/sqlalchemy/httpx/keyring
pyinstaller --windowed --name Raven-Validator --paths src \
  --collect-all pydantic --collect-all pydantic-settings \
  --collect-all sqlalchemy --collect-all httpx --collect-all tenacity --collect-all keyring \
  --hidden-import raven_validator --hidden-import raven_validator.gui.main_window \
  --noconfirm app.py
# → dist/Raven-Validator/ (directory, ~221 MB with PySide6)
# → binary: dist/Raven-Validator/Raven-Validator  (ELF 64-bit, tested QT_QPA_PLATFORM=offscreen)
dist/Raven-Validator/Raven-Validator  # launch (needs display; use offscreen for CI)

# Single-file variant (optional):
# pyinstaller --windowed --onefile --name Raven-Validator --paths src ... app.py
# → dist/Raven-Validator (single ~120 MB binary)

# ── Windows (first target, must build on Windows) ──
# On a Windows host with Python 3.12+:
#   pip install -e ".[dev]" && pip install pyinstaller
#   pyinstaller --windowed --name Raven-Validator --paths src --collect-all pydantic --collect-all pydantic-settings --collect-all sqlalchemy --collect-all httpx --collect-all tenacity --collect-all keyring --hidden-import raven_validator --noconfirm app.py
# → dist\Raven-Validator\Raven-Validator.exe  (directory build)
# For a single EXE: add --onefile
# Icon: add --icon assets/app_icon.ico  (and --icon assets/app_icon.icns for macOS)

# ── macOS ──
# Same as Windows, plus --icon assets/app_icon.icns
# → dist/Raven-Validator.app  (bundle)
# For distribution, create DMG:  hdiutil create -volname Raven-Validator -srcfolder dist/Raven-Validator.app -ov dist/Raven-Validator.dmg

# ── Linux AppImage (later) ──
# Use linuxdeploy or appimage-builder on top of the dist/Raven-Validator directory.
```

Notes:
- `build/` and `dist/` are gitignored — never commit them.
- The checked-in `Raven-Validator.spec` is the generated spec for the Linux directory build (tune `datas/binaries/hiddenimports` there for custom builds).
- `data/` and `exports/` are created at runtime; the packaged app writes to the same relative paths (or `RAVEN_VALIDATOR_DB_URL`).

During development always prefer `python app.py` over the packaged binary.

## License

MIT — see `LICENSE`.
