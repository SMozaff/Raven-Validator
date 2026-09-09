"""Strict URL normalization and validation.

Rules:
- Only http:// and https:// schemes are accepted.
- Never silently upgrade http to https.
- Trailing slashes normalized; API paths (including /v1) preserved.
- canonical_url() produces a dedup key: lowercase scheme+host,
  default ports stripped, single trailing slash removed.
"""

from urllib.parse import urlparse, urlunparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


class URLValidationError(ValueError):
    """Raised when a URL fails strict validation."""


def validate_scheme(url: str) -> bool:
    """Return True only for http:// and https:// URLs."""
    try:
        return urlparse(url.strip()).scheme.lower() in ALLOWED_SCHEMES
    except (ValueError, AttributeError):
        return False


def normalize_url(url: str) -> str:
    """Normalize a URL, preserving scheme and API path.

    Raises:
        URLValidationError: If the scheme is unsupported or the URL
            has no host.
    """
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise URLValidationError(f"Unsupported URL scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise URLValidationError(f"URL has no host: {cleaned!r}")
    host = host.lower()

    # Rebuild netloc with explicit port only when non-default.
    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    netloc = host if port in (None, default_port) else f"{host}:{port}"

    # Normalize path: collapse a lone "/" to "", keep the rest as-is.
    path = parsed.path
    if path == "/":
        path = ""
    # Drop trailing slashes beyond the root but preserve /v1 etc.
    path = path.rstrip("/") if len(path) > 1 else path

    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def canonical_url(url: str) -> str:
    """Return the deduplication key for a URL.

    Same normalization as normalize_url(); callers may use this name
    to express dedup intent.
    """
    return normalize_url(url)


def is_safe_url(url: str) -> bool:
    """Best-effort safety check: valid scheme + resolvable host shape.

    This is user-directed input validation, not an SSRF sandbox.
    Returns False for unsupported schemes, missing hosts, and
    obviously malformed input.
    """
    try:
        normalize_url(url)
    except URLValidationError:
        return False
    return True
