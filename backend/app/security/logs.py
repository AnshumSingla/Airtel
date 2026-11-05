"""Keep session tokens and identifiers out of logs (POLICIES.md §3, §13).

Access log lines contain request paths such as
/api/advisor/sessions/<token>/messages and ?session_id=<token>. This filter
replaces long URL-safe tokens and identifier patterns before the line is written.
"""

from __future__ import annotations

import logging
import re

from app.privacy.masking import mask_text

_TOKEN = re.compile(r"(?<=/)[A-Za-z0-9_-]{16,}(?=/|\?|\s|$|\")")
_QUERY = re.compile(r"(session_id=)[^&\s\"]+")


def redact(text: str) -> str:
    return mask_text(_QUERY.sub(r"\1[redacted]", _TOKEN.sub("[id]", text)))


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def install() -> None:
    for name in ("uvicorn.access", "uvicorn.error", "udyam"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactingFilter) for f in logger.filters):
            logger.addFilter(RedactingFilter())
