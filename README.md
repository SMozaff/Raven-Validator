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

After verifying `ruff check .` and `pytest`:

```bash
# Windows (first target)
pyinstaller --windowed --name Raven-Validator app.py
# → dist/Raven-Validator/Raven-Validator.exe

# Later: macOS .app, Linux AppImage
```

During development always run via `python app.py`.

## License

MIT — see `LICENSE`.
