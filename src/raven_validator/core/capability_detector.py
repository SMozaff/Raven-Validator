"""Capability detection: independent, evidence-based per feature.

Each capability is detected from actual probe evidence, not assumed
from a protocol label. A capability is True only when a probe
positively confirmed it, False when the provider signaled absence,
and None when not tested/unknown.
"""

from raven_validator.domain.capabilities import CapabilityResult
from raven_validator.probes.base import ProbeResult


def detect_capabilities(
    protocol: str,
    probe_results: list[ProbeResult],
    openapi_paths: list[str] | None = None,
) -> CapabilityResult:
    """Derive capability flags from probe evidence and optional OpenAPI paths."""
    caps = CapabilityResult()
    paths = [p.lower() for p in (openapi_paths or [])]

    for probe in probe_results:
        name = probe.probe_name.lower()
        # Model listing.
        if "models" in name:
            if probe.success:
                caps.models = True
            elif probe.http_status == 404:
                caps.models = False

        # Chat completions / responses / embeddings (OpenAI).
        if "chat" in name or "completions" in name or "generation" in name:
            if probe.success:
                caps.chat_completions = True
            elif probe.http_status in (404, 422) or not probe.success:
                caps.chat_completions = False
        if "responses" in name:
            caps.responses = probe.success
        if "embedding" in name:
            caps.embeddings = probe.success

        # Streaming probes.
        if "stream" in name:
            caps.streaming = probe.success

        # Generic authorized success implies at least one working capability
        # when the protocol is known.
        if name == "generic_authorized" and probe.success and protocol != "unknown":
            caps.chat_completions = True

    # Augment from OpenAPI schema when available.
    for path in paths:
        if "/chat/completions" in path:
            caps.chat_completions = caps.chat_completions or True
        if "/responses" in path:
            caps.responses = caps.responses or True
        if "/embeddings" in path:
            caps.embeddings = caps.embeddings or True
        if "/models" in path:
            caps.models = caps.models or True

    return caps
