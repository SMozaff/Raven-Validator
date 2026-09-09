# Raven-Validator 0.2

Raven-Validator is a separate desktop application for validating AI API endpoints discovered by Raven-Targeter or entered manually.

It answers:

- Is this endpoint reachable?
- What protocol does it appear to implement?
- Does it require authentication?
- Which models/capabilities can be verified?
- If an **authorized user-supplied credential** is configured, does a minimal request work?
- What rate-limit metadata is explicitly exposed?
- What quota/balance data is explicitly exposed by a documented endpoint?

## Critical fixes in this build

- **Public/Standard validation never receives or sends a credential.** Secrets are introduced only after the user chooses Authorized mode.
- Protocol detection is GET/OPTIONS-only; it does not send an unauthenticated generation POST.
- Functional testing is routed through the detected protocol adapter:
  - OpenAI-compatible -> Bearer/custom configured auth + `/v1/chat/completions`
  - Anthropic-compatible -> `x-api-key` + `/v1/messages`
  - Generic REST -> only an explicit custom probe template
- The production GUI uses the operating-system keychain. The in-memory backend exists only as an explicit test dependency.
- Candidates can be associated with a credential profile in the GUI.
- The request budget counts **every actual HTTP request**, including protocol detection and redirects.
- Quota checking does not guess a list of endpoints. A documented/explicit `quota_endpoint` is required.
- HTTP 429 is not automatically converted to zero credits.
- Successful authorized generation produces `WORKING` even when `auth_required=True`.
- Cancellation has exactly one terminal event.
- Worker exceptions are surfaced instead of silently swallowed.
- Validator timeout, concurrency and rate-limit controls are wired.
- Imported Raven-Targeter records without `candidate_endpoints` are rejected; GitHub source URLs are never tested as APIs.
- Private, loopback, link-local, reserved and metadata-network targets are blocked by default, including redirect destinations.
- CI is included.

## Modes

### Quick
Public only:
- base reachability
- authentication challenge
- protocol detection

### Standard
Quick plus:
- public model listing where supported
- rate-limit metadata when exposed

No configured credential is sent in Quick or Standard.

### Authorized
Standard plus:
- retrieve the explicitly associated credential from the OS keychain
- protocol-specific authorized model listing
- one minimal generation request
- optional streaming test
- optional quota check

## Quota semantics

Quota/credit checking is optional and requires an explicit documented endpoint on the candidate. Unknown results remain `UNKNOWN`/`UNSUPPORTED`. A generic 429 is treated as rate limiting, not proof that monetary credits are zero.

## Network safety

By default the app blocks localhost/private/link-local/reserved targets. For a deliberate local development environment, set:

```text
RAVEN_VALIDATOR_ALLOW_PRIVATE_NETWORKS=true
```

Only do this when you intentionally want the app to access local/private services.

## Raven-Targeter interchange

Expected input:

```json
{
  "schema": "raven-discovery-export-v1",
  "discoveries": [
    {
      "title": "user/project",
      "source_url": "https://github.com/user/project",
      "candidate_endpoints": [
        {
          "url": "https://api.example.com/v1",
          "kind": "api-base",
          "confidence": 0.9,
          "evidence": "README configuration"
        }
      ]
    }
  ]
}
```

A discovery without a `candidate_endpoints` list is skipped. The `source_url` is provenance, not an API endpoint.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e '.[dev]'
cp .env.example .env
python app.py
```

Credentials are added through the Credentials tab and stored with `keyring` in the operating-system credential store.

## Tests

```bash
pytest
ruff check .
```

The unit suite uses `httpx.MockTransport`; it does not call third-party APIs or use real credentials.
