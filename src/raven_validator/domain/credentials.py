"""Credential profile domain models.

Profile metadata may be stored in SQLite. Raw secrets live ONLY in the
OS keychain and are never represented here.
"""

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AuthScheme(StrEnum):
    """Normalized authentication scheme."""

    NONE = "none"
    BEARER = "bearer"
    API_KEY_HEADER = "api-key-header"
    BASIC = "basic"
    QUERY_KEY = "query-key"
    CUSTOM_HEADER = "custom-header"
    OAUTH = "oauth"
    UNKNOWN = "unknown"


class CredentialProfile(BaseModel):
    """Metadata for a user-authorized credential. No secret material."""

    id: UUID = Field(default_factory=uuid4)
    display_name: str
    auth_type: AuthScheme = AuthScheme.BEARER
    header_name: str | None = None
    keychain_service: str = "raven-validator"
    keychain_username: str = ""
