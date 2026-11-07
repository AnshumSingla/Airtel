"""Identifier masking for API responses, logs and back-office lists (POLICIES.md §3)."""

from __future__ import annotations

import re

_BULLET = "•"

_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
_UDYAM_RE = re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def mask_gstin(gstin: str) -> str:
    """Keep the first 4 and last 3 characters: 37IH••••••••1ZS."""
    if len(gstin) != 15:
        return _BULLET * len(gstin)
    return gstin[:4] + _BULLET * 8 + gstin[-3:]


def mask_udyam(udyam: str) -> str:
    """Keep the prefix, state, district and last 4 digits: UDYAM-KL-00-•••8801."""
    m = re.fullmatch(r"(UDYAM-[A-Z]{2}-\d{2}-)(\d{7})", udyam)
    if not m:
        return _BULLET * len(udyam)
    return m.group(1) + _BULLET * 3 + m.group(2)[-4:]


def mask_text(text: str) -> str:
    """Backstop for log lines: mask any identifier, phone or email pattern found in free text."""
    text = _GSTIN_RE.sub(lambda m: mask_gstin(m.group(0)), text)
    text = _UDYAM_RE.sub(lambda m: mask_udyam(m.group(0)), text)
    text = _EMAIL_RE.sub("[email]", text)
    return _PHONE_RE.sub("[phone]", text)
