"""Tests for strict URL normalization."""

import pytest

from raven_validator.utils.urls import (
    URLValidationError,
    canonical_url,
    is_safe_url,
    normalize_url,
    validate_scheme,
)


def test_https_url_preserved() -> None:
    assert normalize_url("https://api.example.com/v1") == "https://api.example.com/v1"


def test_http_not_upgraded_to_https() -> None:
    assert normalize_url("http://api.example.com/v1").startswith("http://")


def test_trailing_slash_removed() -> None:
    assert normalize_url("https://api.example.com/v1/") == "https://api.example.com/v1"


def test_root_slash_collapsed() -> None:
    assert normalize_url("https://api.example.com/") == "https://api.example.com"


def test_v1_path_preserved() -> None:
    assert normalize_url("https://api.example.com/v1/") == "https://api.example.com/v1"


def test_host_lowercased() -> None:
    assert normalize_url("https://API.Example.COM/v1") == "https://api.example.com/v1"


def test_default_port_stripped() -> None:
    assert normalize_url("https://api.example.com:443/v1") == "https://api.example.com/v1"
    assert normalize_url("http://api.example.com:80/v1") == "http://api.example.com/v1"


def test_non_default_port_kept() -> None:
    assert normalize_url("http://localhost:11434/v1") == "http://localhost:11434/v1"


@pytest.mark.parametrize("url", ["ftp://example.com/v1", "file:///etc/passwd", "ws://example.com"])
def test_unsupported_scheme_rejected(url: str) -> None:
    with pytest.raises(URLValidationError):
        normalize_url(url)
    assert not validate_scheme(url)
    assert not is_safe_url(url)


def test_missing_host_rejected() -> None:
    with pytest.raises(URLValidationError):
        normalize_url("https://")


def test_canonical_url_dedup() -> None:
    a = canonical_url("https://API.example.com/v1/")
    b = canonical_url("https://api.example.com:443/v1")
    assert a == b


def test_is_safe_url_accepts_valid() -> None:
    assert is_safe_url("https://api.example.com/v1")
    assert is_safe_url("http://localhost:11434")
