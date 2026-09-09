# Raven-Validator v0.2.2 — CI / Build Fixes

This tree is intended to replace the repository contents completely.

The previous v0.2.1 workflow reached Ruff but failed because Ruff 0.16.6 enabled rule families beyond the intended project lint baseline. v0.2.2 pins the lint rules explicitly so future Ruff releases cannot silently change the CI gate.

The quality gate remains strict for syntax/import-use/common bug checks and runs tests plus bytecode compilation before any desktop build.

The desktop matrix then builds native artifacts on:

- Linux
- Windows
- macOS

using PyInstaller and verifies the expected executable/app exists before upload.
