"""Application settings."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True)
    db_url: str = Field("sqlite:///data/raven_validator.db", alias="RAVEN_VALIDATOR_DB_URL")
    log_level: str = Field("INFO", alias="RAVEN_VALIDATOR_LOG_LEVEL")
    connect_timeout: float = Field(10.0, ge=0.1, le=120, alias="RAVEN_VALIDATOR_CONNECT_TIMEOUT")
    read_timeout: float = Field(30.0, ge=0.1, le=300, alias="RAVEN_VALIDATOR_READ_TIMEOUT")
    max_concurrency: int = Field(10, ge=1, le=100, alias="RAVEN_VALIDATOR_MAX_CONCURRENCY")
    max_requests_per_api: int = Field(6, ge=1, le=50, alias="RAVEN_VALIDATOR_MAX_REQUESTS_PER_API")
    allow_private_networks: bool = Field(False, alias="RAVEN_VALIDATOR_ALLOW_PRIVATE_NETWORKS")


def get_settings() -> AppSettings:
    return AppSettings()
