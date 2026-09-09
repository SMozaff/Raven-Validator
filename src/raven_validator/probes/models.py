"""Models probe — retrieve, deduplicate, and snapshot available models."""

from __future__ import annotations

import httpx

from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel


class ModelsProbe:
    """GET model list where the provider exposes one.

    Supports OpenAI-style (/v1/models) and generic /models fallbacks.
    Chooses a model for downstream generation from the deduplicated list
    when the caller has not supplied one.
    """

    name = "models"
    safety_level = ProbeSafetyLevel.READ_ONLY

    async def run(self, context: ProbeContext) -> ProbeResult:
        base = context.base_url.rstrip("/")
        if base.endswith("/v1"):
            candidates = [f"{base}/models"]
        else:
            candidates = [f"{base}/models", f"{base}/v1/models"]
        # Always try /v1/models as well when base does not already contain it.
        if "/v1" not in base:
            candidates.append(f"{base}/v1/models")

        headers: dict[str, str] = {}
        if context.credential:
            scheme = (context.credential_scheme or "bearer").lower()
            if scheme == "bearer":
                headers["Authorization"] = f"Bearer {context.credential}"
            else:
                headers[scheme] = context.credential

        last_error: str | None = None
        for url in candidates:
            try:
                response = await context.client.get(url, headers=headers or None)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue

            if response.status_code not in (200, 201):
                last_error = f"HTTP {response.status_code}"
                continue

            try:
                body = response.json()
            except ValueError:
                last_error = "malformed JSON"
                continue

            models = self._extract_models(body)
            if not models:
                last_error = "no models in response"
                continue

            deduped = self._deduplicate(models)
            return ProbeResult(
                probe_name=self.name,
                safety_level=self.safety_level,
                success=True,
                endpoint=url,
                method="GET",
                http_status=response.status_code,
                evidence=[f"Found {len(deduped)} model(s)"],
                data={
                    "models": deduped,
                    "count": len(deduped),
                    "excerpt": str(deduped[:20]),
                    "headers": dict(response.headers),
                },
            )

        return ProbeResult(
            probe_name=self.name,
            safety_level=self.safety_level,
            success=False,
            endpoint=candidates[0],
            method="GET",
            evidence=[last_error or "model list unavailable"],
            error=last_error,
        )

    @staticmethod
    def _extract_models(body: object) -> list[str]:
        if isinstance(body, dict):
            # OpenAI: {"data": [{"id": "gpt-4"}, ...]}
            data = body.get("data")
            if isinstance(data, list):
                ids = [
                    x.get("id")
                    for x in data
                    if isinstance(x, dict) and isinstance(x.get("id"), str)
                ]
                if ids:
                    return ids
            # Alternate: {"models": [...]} or {"items": [...]}
            for key in ("models", "items"):
                alt = body.get(key)
                if isinstance(alt, list):
                    flat: list[str] = []
                    for entry in alt:
                        if isinstance(entry, str):
                            flat.append(entry)
                        elif isinstance(entry, dict):
                            mid = entry.get("id") or entry.get("name")
                            if isinstance(mid, str):
                                flat.append(mid)
                    if flat:
                        return flat
            # Single object with id
            if isinstance(body.get("id"), str):
                return [body["id"]]  # type: ignore[index]
        if isinstance(body, list):
            flat2: list[str] = []
            for entry in body:
                if isinstance(entry, str):
                    flat2.append(entry)
                elif isinstance(entry, dict) and isinstance(entry.get("id"), str):
                    flat2.append(entry["id"])  # type: ignore[index]
            return flat2
        return []

    @staticmethod
    def _deduplicate(models: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for m in models:
            if m not in seen:
                seen.add(m)
                out.append(m)
        return out
