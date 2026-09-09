"""Central secret redaction."""
from __future__ import annotations

import re

_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
]
SENSITIVE_HEADERS = {"authorization", "x-api-key", "api-key", "cookie", "set-cookie"}


def redact_text(text: str, max_length: int | None = None) -> str:
    out = text
    for p in _SECRET_PATTERNS:
        out = p.sub("[REDACTED]", out)
    out = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[REDACTED]", out)
    out = re.sub(r"(?i)((?:api[_-]?key|token|secret)\s*[=:]\s*)[^\s\"']+", r"\1[REDACTED]", out)
    return out[:max_length] if max_length is not None else out


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: ("[REDACTED]" if k.lower() in SENSITIVE_HEADERS else redact_text(str(v), 500)) for k, v in headers.items()}
