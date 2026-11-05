"""Text clean-up for OCR'd KYC fields.

Found in the day-1 OCR spike (evidence/ocr_spike/): OCR drops or inserts
spaces ("VindhyaTours&Travels", "75 2083"), and pieces of the diagonal
"SYNTHETIC SPECIMEN - NOT A VALID DOCUMENT" watermark land inside or next to
values ("NOT A VALID DOCUM 22,425", "... 348176 IOT").
"""

from __future__ import annotations

import re
from datetime import date

WATERMARK = "SYNTHETICSPECIMENNOTAVALIDDOCUMENT"

# Watermark phrase merged into a value, possibly cut off at either end.
_WATERMARK_PHRASE = re.compile(
    r"(?:SYN\w*\s*)?(?:S?PECI\w*\s*)?-?\s*\bN?OT\s*A\s*V?ALI\w*\s*(?:DO\w*)?", re.I
)
_NAME_SUFFIXES = ("privatelimited", "pvtltd", "limited", "ltd", "llp")


def _levenshtein_at_most_one(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def is_watermark_fragment(token: str) -> bool:
    """A short all-caps token that is (nearly) a piece of the watermark, e.g. 'CUM', 'IOT'."""
    t = re.sub(r"[^A-Z]", "", token.upper())
    if not t or len(t) > 12 or not token.strip().isupper():
        return False
    if t in WATERMARK:
        return True
    if len(t) <= 5:
        return any(_levenshtein_at_most_one(t, WATERMARK[i:i + n])
                   for n in (len(t) - 1, len(t), len(t) + 1) if n > 0
                   for i in range(len(WATERMARK) - n + 1))
    return False


def clean_value(value: str) -> str:
    """Remove watermark pieces from an OCR'd field value."""
    v = _WATERMARK_PHRASE.sub(" ", value or "")
    tokens = v.split()
    while tokens and is_watermark_fragment(tokens[-1]) and len(tokens) > 1:
        tokens.pop()
    while tokens and is_watermark_fragment(tokens[0]) and len(tokens) > 1:
        tokens.pop(0)
    return " ".join(tokens).strip(" -")


def norm_name(name: str) -> str:
    """Compare names without spacing, punctuation, '(Prop.' wrappers or company suffixes."""
    s = re.sub(r"\(prop\.?", " ", (name or "").lower())
    s = re.sub(r"[^a-z0-9]", "", s)
    changed = True
    while changed:
        changed = False
        for suf in _NAME_SUFFIXES:
            if s.endswith(suf) and len(s) > len(suf):
                s, changed = s[: -len(suf)], True
    return s


def pincode(address: str) -> str | None:
    """The 6-digit PIN at the end of an address, tolerating OCR spaces inside it."""
    m = re.search(r"((?:\d\s*){6})\s*$", clean_value(address or ""))
    return re.sub(r"\s", "", m.group(1)) if m else None


def iso_date(text: str) -> date | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text or "")
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None
