# Raven-Validator v0.2.1 — CI / Build Fixes

This clean replacement tree is intended to replace the repository contents, not be copied on top of an older tree.

## Why the current GitHub Actions run fails

The current GitHub repository still contains older GUI/probe modules from the previous implementation. Ruff is stopping the workflow before pytest or desktop packaging.

The latest failing run reports issues in stale files such as:

- `src/raven_validator/gui/candidates_page.py`
- `src/raven_validator/gui/credentials_page.py`
- `src/raven_validator/gui/results_page.py`
- `src/raven_validator/gui/validator_page.py`
- `src/raven_validator/probes/rate_limits.py`

Those files are not part of this clean v0.2.1 tree.

## CI changes

The workflow now:

1. runs lint, pytest, and compile checks on Ubuntu;
2. builds only after the quality gate passes;
3. repeats lint/tests/compile on Linux, Windows, and macOS;
4. builds with PyInstaller on every desktop OS;
5. verifies the expected executable/app exists;
6. packages and uploads each platform build as a GitHub Actions artifact;
7. uses current `actions/checkout@v7` and `actions/setup-python@v7`.

## Local verification performed

- `python -m compileall -q src app.py` — PASS
- `pytest -q` — 14 passed

Ruff is executed by GitHub Actions after installing the declared dev dependencies.
