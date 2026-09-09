# Qwen / Coding-Agent Instructions

Raven-Validator is a validation product, not a discovery product.

Hard invariants:
1. A publicly discovered token-like string is never an authorized credential.
2. Quick/Standard contexts contain no credential.
3. Every outbound HTTP request must pass through `BudgetedSafeClient`.
4. Protocol detection must not send generation/state-changing requests.
5. Functional requests are adapter-specific.
6. Unknown quota stays unknown; never infer balance by consuming requests.
7. Private/local targets remain blocked unless the user explicitly opts in.
8. Secrets never enter SQLite, exports, logs or GUI diagnostics.
9. Targeter source URLs are provenance, never fallback API endpoints.

Run `pytest` and `ruff check .` after each change.
