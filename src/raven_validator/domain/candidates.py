"""API candidate domain model.

Never stores raw credentials. A candidate may reference a credential
profile by ID; the secret itself lives in the OS keychain.
"""

from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, Field


class APICandidate(BaseModel):
    """A single AI API endpoint to validate."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    base_url: AnyHttpUrl
    provider_hint: str | None = None
    protocol_hint: str | None = None
    source_url: AnyHttpUrl | None = None
    source_type: str | None = None
    notes: str | None = None
    credential_profile_id: UUID | None = None
