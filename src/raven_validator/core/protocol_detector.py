"""Protocol selection from safe public signals only."""
from __future__ import annotations

from raven_validator.adapters.anthropic_compatible import AnthropicCompatibleAdapter
from raven_validator.adapters.base import APIAdapter, DetectionResult, PublicContext
from raven_validator.adapters.generic_rest import GenericRESTAdapter
from raven_validator.adapters.openai_compatible import OpenAICompatibleAdapter


async def detect_protocol(context: PublicContext, reachable: bool) -> tuple[DetectionResult, APIAdapter]:
    """No POSTs and no credentials are available in PublicContext."""
    hint = (context.candidate.protocol_hint or "").lower()
    if "anthropic" in hint or "claude" in hint:
        order: list[APIAdapter] = [AnthropicCompatibleAdapter(), OpenAICompatibleAdapter()]
    elif "openai" in hint:
        order = [OpenAICompatibleAdapter(), AnthropicCompatibleAdapter()]
    else:
        order = [OpenAICompatibleAdapter(), AnthropicCompatibleAdapter()]

    best: tuple[DetectionResult, APIAdapter] | None = None
    for adapter in order:
        result = await adapter.detect(context)
        if best is None or result.confidence > best[0].confidence:
            best = (result, adapter)
        if result.confidence >= 0.75:
            break

    if best and best[0].protocol != "unknown" and best[0].confidence >= 0.35:
        return best
    generic = GenericRESTAdapter()
    return DetectionResult(
        "generic-rest" if reachable else "unknown",
        0.2 if reachable else 0.0,
        ["Reachable HTTP endpoint; no specific protocol signal"] if reachable else ["No protocol signal"],
    ), generic
