"""OpenAI-compatible adapter.

Understands: GET /v1/models, POST /v1/chat/completions,
POST /v1/responses, POST /v1/embeddings. Capability detection is
independent per route — not all routes must exist.

Minimal authorized generation uses a tiny deterministic prompt and
single-digit max_tokens, never repeated unless explicitly requested.
"""

import httpx

from raven_validator.adapters.base import DetectionResult, clamp_confidence
from raven_validator.probes.base import ProbeContext, ProbeResult
from raven_validator.security.request_policy import ProbeSafetyLevel


class OpenAICompatibleAdapter:
    """Detects and probes OpenAI-compatible APIs."""

    name = "openai-compatible"

    async def detect(self, context: ProbeContext) -> DetectionResult:
        evidence: list[str] = []
        score = 0.0

        hint = (context.candidate.protocol_hint or "").lower()
        if "openai" in hint:
            evidence.append("Protocol hint suggests OpenAI-compatible")
            score += 0.2

        url = context.base_url.lower()
        if "/v1" in url:
            evidence.append("URL contains /v1 (OpenAI-style path)")
            score += 0.15

        # Probe GET /v1/models for OpenAI-shaped response.
        model_evidence, model_score = await self._probe_models_shape(context)
        evidence.extend(model_evidence)
        score += model_score

        # If the base itself returned OpenAI-shaped JSON, catch it.
        if not model_evidence:
            body_evidence, body_score = await self._probe_base_shape(context)
            evidence.extend(body_evidence)
            score += body_score

        confidence = clamp_confidence(score)
        protocol = "openai-compatible" if confidence >= 0.35 else "unknown"
        if protocol == "unknown" and not evidence:
            evidence.append("No OpenAI-compatible signals found")
        return DetectionResult(
            protocol=protocol,
            confidence=confidence,
            evidence=evidence,
            adapter_name=self.name,
        )

    async def _probe_models_shape(
        self, context: ProbeContext
    ) -> tuple[list[str], float]:
        url = f"{context.base_url.rstrip('/')}/models"
        try:
            response = await context.client.get(url)
        except httpx.HTTPError:
            return [], 0.0
        if response.status_code == 401:
            return ["GET /v1/models returned 401 (auth-gated OpenAI endpoint)"], 0.3
        if response.status_code != 200:
            return [], 0.0
        try:
            body = response.json()
        except ValueError:
            return [], 0.0
        if isinstance(body, dict) and "data" in body and isinstance(body["data"], list):
            return ["GET /v1/models returned OpenAI-style model list"], 0.55
        if isinstance(body, dict) and "object" in body and body["object"] == "list":
            return ["GET /v1/models returned object=list (OpenAI style)"], 0.45
        return [], 0.0

    async def _probe_base_shape(
        self, context: ProbeContext
    ) -> tuple[list[str], float]:
        try:
            response = await context.client.get(context.base_url)
        except httpx.HTTPError:
            return [], 0.0
        if response.status_code != 200:
            return [], 0.0
        try:
            body = response.json()
        except ValueError:
            return [], 0.0
        if not isinstance(body, dict):
            return [], 0.0
        if "choices" in body or "usage" in body:
            return ["Response contains choices/usage (OpenAI completion shape)"], 0.35
        return [], 0.0

    async def probe_public(self, context: ProbeContext) -> list[ProbeResult]:
        """GET /v1/models when it does not require auth (READ_ONLY)."""
        url = f"{context.base_url.rstrip('/')}/models"
        try:
            response = await context.client.get(url)
        except httpx.HTTPError as exc:
            return [
                ProbeResult(
                    probe_name="openai_models_public",
                    safety_level=ProbeSafetyLevel.READ_ONLY,
                    success=False,
                    endpoint=url,
                    method="GET",
                    error=str(exc),
                )
            ]
        try:
            body = response.json()
        except ValueError:
            body = {}
        success = response.status_code == 200 and isinstance(body, dict)
        return [
            ProbeResult(
                probe_name="openai_models_public",
                safety_level=ProbeSafetyLevel.READ_ONLY,
                success=success,
                endpoint=url,
                method="GET",
                http_status=response.status_code,
                data={"excerpt": str(body)[:2000]} if body else {},
            )
        ]

    async def probe_authorized(
        self, context: ProbeContext, credential: str
    ) -> list[ProbeResult]:
        """Single minimal generation request (MINIMAL_GENERATION)."""
        url = f"{context.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": context.options.get("model", "gpt-3.5-turbo"),
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 3,
        }
        headers = {"Authorization": f"Bearer {credential}"}
        try:
            response = await context.client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return [
                ProbeResult(
                    probe_name="openai_generation",
                    safety_level=ProbeSafetyLevel.MINIMAL_GENERATION,
                    success=False,
                    endpoint=url,
                    method="POST",
                    error=str(exc),
                )
            ]
        success = response.status_code in (200, 201)
        data: dict[str, object] = {"excerpt": response.text[:1000]}
        data["headers"] = dict(response.headers)
        try:
            body = response.json()
            if isinstance(body, dict):
                data["usage"] = body.get("usage")
        except ValueError:
            pass
        return [
            ProbeResult(
                probe_name="openai_generation",
                safety_level=ProbeSafetyLevel.MINIMAL_GENERATION,
                success=success,
                endpoint=url,
                method="POST",
                http_status=response.status_code,
                data=data,  # type: ignore[arg-type]
            )
        ]

    def normalize_error(self, response: object) -> str:
        if isinstance(response, httpx.Response):
            try:
                body = response.json()
                if isinstance(body, dict):
                    err = body.get("error")
                    if isinstance(err, dict):
                        return str(err.get("message", err))
                    if err:
                        return str(err)
            except ValueError:
                pass
            return response.text[:500]
        return str(response)
