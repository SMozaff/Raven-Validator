"""Authentication-requirement probe (READ_ONLY, no credentials sent).

Inspects status codes (401/403), WWW-Authenticate headers, and known
response-body signals to determine whether auth appears required and
which scheme is likely. Never sends credentials.
"""

import httpx

from raven_validator.domain.credentials import AuthScheme
from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel

_AUTH_BODY_MARKERS: tuple[tuple[str, AuthScheme], ...] = (
    ("x-api-key", AuthScheme.API_KEY_HEADER),
    ("api key", AuthScheme.API_KEY_HEADER),
    ("apikey", AuthScheme.API_KEY_HEADER),
    ("authorization header", AuthScheme.BEARER),
    ("bearer", AuthScheme.BEARER),
    ("basic", AuthScheme.BASIC),
    ("oauth", AuthScheme.OAUTH),
)


class AuthProbe:
    """Detect authentication requirement from public signals."""

    name = "auth_requirement"
    safety_level = ProbeSafetyLevel.READ_ONLY

    async def run(self, context: ProbeContext) -> ProbeResult:
        evidence: list[str] = []
        data: dict[str, object] = {}
        try:
            response = await context.client.get(context.base_url)
        except httpx.HTTPError as exc:
            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=False,
                endpoint=context.base_url,
                method="GET",
                evidence=[f"Request failed: {type(exc).__name__}"],
                data=data,
                error=str(exc),
            )

        data["headers"] = dict(response.headers)
        scheme = self.classify(response, evidence)
        data["auth_required"] = scheme is not None
        data["auth_scheme"] = scheme.value if scheme else AuthScheme.NONE.value

        return ProbeResult(
            probe_name=self.name,
            safety_level=self.safety_level,
            success=True,
            endpoint=context.base_url,
            method="GET",
            http_status=response.status_code,
            evidence=evidence,
            data=data,
        )

    def classify(
        self, response: httpx.Response, evidence: list[str]
    ) -> AuthScheme | None:
        """Return the likely scheme, or None when no auth appears required."""
        status = response.status_code
        www_auth = response.headers.get("www-authenticate", "")

        if status not in (401, 403):
            evidence.append(f"HTTP {status}: no auth challenge observed")
            return None

        evidence.append(f"HTTP {status}")
        lowered = www_auth.lower()
        if "bearer" in lowered:
            evidence.append(f"WWW-Authenticate: {www_auth}")
            return AuthScheme.BEARER
        if "basic" in lowered:
            evidence.append(f"WWW-Authenticate: {www_auth}")
            return AuthScheme.BASIC
        if www_auth:
            evidence.append(f"WWW-Authenticate: {www_auth}")

        body = self._safe_body(response)
        for marker, scheme in _AUTH_BODY_MARKERS:
            if marker in body:
                evidence.append(f"Response body indicates: {marker}")
                return scheme

        evidence.append("Auth required (scheme unknown)")
        return AuthScheme.UNKNOWN

    @staticmethod
    def _safe_body(response: httpx.Response) -> str:
        try:
            return response.text.lower()[:2000]
        except (ValueError, UnicodeDecodeError):
            return ""
