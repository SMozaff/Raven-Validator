"""Tests for application settings and defaults."""

import os
from unittest import mock

from raven_validator.config import defaults
from raven_validator.config.settings import AppSettings, get_settings


def test_defaults_match_expected_values() -> None:
    assert defaults.DEFAULT_CONNECT_TIMEOUT == 10.0
    assert defaults.DEFAULT_READ_TIMEOUT == 30.0
    assert defaults.DEFAULT_MAX_CONCURRENCY == 10
    assert defaults.DEFAULT_MAX_REQUESTS_PER_API == 6
    assert defaults.DEFAULT_LOG_LEVEL == "INFO"


def test_default_settings(default_settings: AppSettings) -> None:
    assert default_settings.db_url == defaults.DEFAULT_DB_URL
    assert default_settings.log_level == defaults.DEFAULT_LOG_LEVEL
    assert default_settings.connect_timeout == defaults.DEFAULT_CONNECT_TIMEOUT
    assert default_settings.read_timeout == defaults.DEFAULT_READ_TIMEOUT
    assert default_settings.max_concurrency == defaults.DEFAULT_MAX_CONCURRENCY
    assert default_settings.max_requests_per_api == defaults.DEFAULT_MAX_REQUESTS_PER_API


def test_env_override() -> None:
    with mock.patch.dict(
        os.environ,
        {
            "RAVEN_VALIDATOR_LOG_LEVEL": "DEBUG",
            "RAVEN_VALIDATOR_MAX_CONCURRENCY": "4",
        },
    ):
        settings = get_settings()
    assert settings.log_level == "DEBUG"
    assert settings.max_concurrency == 4


def test_db_url_is_sqlite_by_default(default_settings: AppSettings) -> None:
    assert default_settings.db_url.startswith("sqlite:///")
