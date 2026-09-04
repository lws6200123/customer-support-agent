"""Small deterministic redaction helpers for persisted runtime summaries."""

from __future__ import annotations

import re


_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_ -]?key|access[_ -]?token|password|secret)\b\s*[:=]\s*\S+"
)
_KEY_SIGNATURE = re.compile(
    r"(?i)\b(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})\b"
)


def sanitize_text(value: str | None, *, max_length: int = 4000) -> str | None:
    if value is None:
        return None
    redacted = _SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    redacted = _KEY_SIGNATURE.sub("[REDACTED_SECRET]", redacted)
    redacted = redacted.replace("\x00", "")
    return redacted[:max_length]
