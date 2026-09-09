from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, HttpUrl


class APICandidate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    base_url: HttpUrl
    provider_hint: str | None = None
    protocol_hint: str | None = None
    source_url: HttpUrl | None = None
    source_type: str | None = None
    notes: str | None = None
    credential_profile_id: str | None = None
    # Explicit trusted configuration only; never imported from discovered secrets.
    quota_endpoint: str | None = None
    custom_probe: dict[str, Any] | None = None
