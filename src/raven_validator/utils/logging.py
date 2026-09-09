"""Structured logging with built-in secret redaction.

Never log full credentials. All messages pass through a redaction filter
that masks Authorization headers, bearer tokens, API keys, and cookies.
"""

import logging
import re

# Patterns matched case-insensitively and replaced with [REDACTED].
_REDACT_PATTERNS = [
    re.compile(r"(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+", re.IGNORECASE),
    re.compile(r"(bearer\s+)[A-Za-z0-9\-._~+/=]+", re.IGNORECASE),
    re.compile(r"((?:x-api-key|api-key|apikey)\s*[:=]\s*)[^\s,;]+", re.IGNORECASE),
    re.compile(r"((?:cookie|session|token)\s*[:=]\s*)[^\s,;]+", re.IGNORECASE),
]


def redact_message(message: str) -> str:
    """Mask credential-like values in a log message."""
    redacted = message
    for pattern in _REDACT_PATTERNS:
        # Patterns with a capture group keep the prefix; bare patterns replace entirely.
        if pattern.groups >= 1:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class RedactionFilter(logging.Filter):
    """Logging filter that redacts secrets from every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_message(record.msg)
        if record.args:
            try:
                record.args = tuple(
                    redact_message(a) if isinstance(a, str) else a
                    for a in record.args  # type: ignore[union-attr]
                )
            except TypeError:
                # args is a dict (kwargs-style formatting)
                if isinstance(record.args, dict):
                    record.args = {
                        k: redact_message(v) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
        return True


_configured = False


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging with redaction. Safe to call multiple times."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (redaction applied at handler level)."""
    return logging.getLogger(name)
