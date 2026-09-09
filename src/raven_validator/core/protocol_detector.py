"""Protocol detector that selects among registered adapters."""

from raven_validator.adapters.anthropic_compatible import AnthropicCompatibleAdapter
from raven_validator.adapters.base import DetectionResult
from raven_validator.adapters.generic_rest import GenericRESTAdapter
from raven_validator.adapters.openai_compatible import OpenAICompatibleAdapter
from raven_validator.probes.base import ProbeContext


async def detect_protocol(context: ProbeContext) -> DetectionResult:
    """Try each adapter's detect() and return the highest-confidence result.

    Evidence may include URL structure, response shape, documented headers,
    endpoint probes (/v1/models, /v1/messages, etc.), OpenAPI metadata,
    and imported protocol hints. Never claim compatibility from a provider
    name alone.
    """
    adapters = [
        OpenAICompatibleAdapter(),
        AnthropicCompatibleAdapter(),
        GenericRESTAdapter(),
    ]
    best: DetectionResult | None = None
    for adapter in adapters:
        result = await adapter.detect(context)
        if best is None or result.confidence > best.confidence:
            best = result

    if best is None:
        return DetectionResult(
            protocol="unknown", confidence=0.0, evidence=["No adapter responded"]
        )
    return best
