# Audit Fixes Applied

This corrected build addresses the highest-priority Raven-Validator findings from the 2026-09-09 audit.

- Public/Standard contexts cannot access a credential.
- Secrets are introduced only in explicit Authorized mode.
- Protocol detection is GET/OPTIONS only; no unauthenticated generation POST.
- Authorized generation is routed through the detected OpenAI/Anthropic/Generic adapter.
- Anthropic uses `/v1/messages` and `x-api-key` semantics.
- Production credential storage uses the OS keychain; memory storage is explicit test-only injection.
- Candidate editor includes credential-profile association.
- Request budget is enforced at the actual HTTP request boundary.
- Redirect destinations are revalidated.
- Local/private/link-local/reserved/metadata endpoints are blocked by default.
- Quota checks require an explicit documented endpoint.
- Generic HTTP 429 no longer implies zero credits.
- Successful authorized generation overrides `REACHABLE_AUTH_REQUIRED` to `WORKING` while preserving `auth_required=True`.
- Batch cancellation emits one terminal event.
- Worker exceptions surface to the GUI.
- Timeout, concurrency and rate-limit controls are wired.
- Targeter imports require `candidate_endpoints` and never fall back to GitHub source URLs.
- Added CI and focused security/correctness regression tests.
