from enum import StrEnum

from pydantic import BaseModel


class AuthScheme(StrEnum):
    NONE = "none"
    BEARER = "bearer"
    API_KEY_HEADER = "api-key-header"
    BASIC = "basic"
    CUSTOM_HEADER = "custom-header"
    UNKNOWN = "unknown"


class CredentialProfile(BaseModel):
    id: str
    display_name: str
    auth_type: AuthScheme = AuthScheme.BEARER
    header_name: str | None = None
    keychain_service: str = "raven-validator"
    keychain_username: str
