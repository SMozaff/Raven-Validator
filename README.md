# Raven-Validator

**Is this API reachable? What protocol does it use? Does it require authentication? What capabilities does it expose? If I provide an authorized credential, does it work, what models are available, and what quota/rate-limit information can be verified?**

Raven-Validator is a cross-platform desktop application for validating AI API endpoints. It takes candidate APIs (entered manually or imported from JSON/CSV/Raven-Targeter exports) and determines what can safely be verified about them.

## Relationship to Raven-Targeter

- **Raven-Targeter** discovers candidate APIs from public sources.
- **Raven-Validator** receives API candidates and validates them.

The two applications are separate products. They share only a versioned JSON/CSV interchange format (`raven-discovery-export-v1`). Neither imports the other's Python package.

## Critical Security Rule

A credential-like string discovered in a public repository, README, Gist, log, or imported discovery record must **never** be automatically used for authentication. Authenticated testing is allowed only with a credential the user explicitly configures as an authorized credential profile (stored in the OS keychain).

## Features (V1)

- Manual API entry, JSON/CSV/Raven-Targeter import
- Safe reachability tests, protocol detection (OpenAI-compatible, Anthropic-compatible, Generic REST)
- Authentication requirement detection
- Authorized minimal generation tests, streaming tests
- Rate-limit and quota/credit inspection
- SQLite persistence, JSON/CSV export
- PySide6 desktop GUI (Dashboard, Candidates, Validator, Results, Credentials, Settings)

## Quickstart

```bash
pip install -e ".[dev]"
python app.py
```

## Development

```bash
ruff check .
pytest
```

Copy `.env.example` to `.env` to override defaults. Credentials belong in credential profiles (OS keychain), never in environment variables.

## License

MIT
