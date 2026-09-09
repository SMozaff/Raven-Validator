"""Capability detection result model."""

from pydantic import BaseModel


class CapabilityResult(BaseModel):
    """Independent capability flags with evidence-based detection.

    Each flag means: Known-supported (True), Known-unsupported (False),
    or Unknown/Not-tested (None).
    """

    models: bool | None = None
    chat_completions: bool | None = None
    responses: bool | None = None
    streaming: bool | None = None
    embeddings: bool | None = None
    images: bool | None = None
    audio: bool | None = None
