"""Shared pytest fixtures."""

import pytest

from raven_validator.config import defaults
from raven_validator.config.settings import AppSettings


@pytest.fixture
def default_settings() -> AppSettings:
    """AppSettings with defaults (no env overrides)."""
    return AppSettings(
        db_url=defaults.DEFAULT_DB_URL,
        log_level=defaults.DEFAULT_LOG_LEVEL,
        connect_timeout=defaults.DEFAULT_CONNECT_TIMEOUT,
        read_timeout=defaults.DEFAULT_READ_TIMEOUT,
        max_concurrency=defaults.DEFAULT_MAX_CONCURRENCY,
        max_requests_per_api=defaults.DEFAULT_MAX_REQUESTS_PER_API,
    )
