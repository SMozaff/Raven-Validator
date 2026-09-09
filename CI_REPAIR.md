# Raven-Validator v0.2.2 CI repair

This is a clean replacement repository tree.

## Changes from v0.2.1

- Explicitly pins the Ruff CI ruleset in `pyproject.toml` instead of relying on Ruff's evolving defaults.
- Removes the two known unused imports that were failing the `F` rules.
- Uses `collections.abc` for `AsyncGenerator` / `Callable`.
- Tightens OS-keychain exception handling to `keyring.errors.KeyringError` / `PasswordDeleteError`.
- Retains the security fixes from v0.2.1: credential-free public probes, adapter-routed authorized testing, request budgets, safe network policy, quota semantics, and Targeter import contract.
- Keeps cross-platform GitHub Actions builds for Linux, Windows, and macOS.

## CI gate

The workflow runs:

```bash
python -m ruff check .
python -m pytest
python -m compileall -q src app.py
```

before native PyInstaller builds.
