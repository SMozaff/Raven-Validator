"""Application settings loaded from environment variables and .env file.

Credentials are NOT configured here. They belong in credential profiles
stored in the OS keychain.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

from raven_validator.config import defaults


class AppSettings(BaseSettings):
    """Typed application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="RAVEN_VALIDATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = defaults.DEFAULT_DB_URL
    log_level: str = defaults.DEFAULT_LOG_LEVEL
    connect_timeout: float = defaults.DEFAULT_CONNECT_TIMEOUT
    read_timeout: float = defaults.DEFAULT_READ_TIMEOUT
    max_concurrency: int = defaults.DEFAULT_MAX_CONCURRENCY
    max_requests_per_api: int = defaults.DEFAULT_MAX_REQUESTS_PER_API


def get_settings() -> AppSettings:
    """Return a fresh AppSettings instance from the current environment."""
    return AppSettings()
