"""Public OpenAPI/Swagger metadata probe (READ_ONLY).

Fetches well-known schema locations only when explicitly available:
openapi.json, swagger.json, docs. Never brute-forces path dictionaries.
"""

import httpx

from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel

SCHEMA_PATHS = ("/openapi.json", "/swagger.json")


class OpenAPISchemaProbe:
    """Inspect explicitly available OpenAPI/Swagger metadata."""

    name = "openapi_schema"
    safety_level = ProbeSafetyLevel.READ_ONLY

    async def run(self, context: ProbeContext) -> ProbeResult:
        evidence: list[str] = []
        data: dict[str, object] = {}
        base = context.base_url.rstrip("/")

        for path in SCHEMA_PATHS:
            url = f"{base}{path}"
            try:
                response = await context.client.get(url)
            except httpx.HTTPError as exc:
                evidence.append(f"{path}: request failed ({type(exc).__name__})")
                continue
            if response.status_code != 200:
                evidence.append(f"{path}: HTTP {response.status_code}")
                continue
            try:
                schema = response.json()
            except ValueError:
                evidence.append(f"{path}: non-JSON response")
                continue
            if not isinstance(schema, dict) or "openapi" not in schema and "swagger" not in schema:
                evidence.append(f"{path}: not an OpenAPI document")
                continue
            evidence.append(f"OpenAPI schema found at {path}")
            data["schema_url"] = url
            data["openapi_version"] = schema.get("openapi", schema.get("swagger"))
            paths = schema.get("paths", {})
            if isinstance(paths, dict):
                data["path_count"] = len(paths)
                evidence.append(f"Schema declares {len(paths)} paths")
            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=True,
                endpoint=url,
                method="GET",
                http_status=200,
                evidence=evidence,
                data=data,
            )

        return ProbeResult(
            probe_name=self.name,
            safety_level=self.safety_level,
            success=False,
            endpoint=base,
            method="GET",
            evidence=evidence or ["No public OpenAPI schema found"],
            data=data,
        )
