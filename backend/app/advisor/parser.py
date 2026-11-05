"""Local slot parser for English, Hindi (Devanagari) and Hinglish (POLICIES.md §4, §5.2).

Runs on every message before anything else. When it fills what the turn
needs, no LLM call is made. Identifiers are detected and removed first, so a
GSTIN's digits can never be read as a headcount.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.advisor.lexicon import (
    BUSINESS_ALIASES, DEVANAGARI_DIGITS, GSTIN_WORDS, NEED_PHRASES, NEED_WORDS,
    NO_WORDS, NUMBER_WORDS, ONLY_WORDS, PEOPLE_WORDS, SITE_WORDS, YES_WORDS, Lexicon, tokenize,
)

# Identifier-like patterns (POLICIES.md §5.2 step 2). Order matters: longest first.
IDENTIFIER_PATTERNS = {
    "gstin": re.compile(r"\b\d{2}\s*[A-Za-z]{5}\s*\d{4}\s*[A-Za-z][0-9A-Za-z]\s*[Zz]\s*[0-9A-Za-z]\b"),
    "udyam": re.compile(r"\budyam[\s-]*[a-z]{2}[\s-]*\d{2}[\s-]*\d{7}\b", re.I),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "pan": re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"),
    "long_number": re.compile(r"(?<!\d)\d(?:[\s-]?\d){4,}(?!\d)"),  # 5+ digits: pincodes, accounts
}

HINGLISH_MARKERS = {"hai", "hain", "mera", "meri", "mere", "mein", "nahi", "nahin", "log", "ka",
                    "ki", "ke", "kya", "haan", "chahiye", "hum", "hamara", "hamari", "aur", "jagah"}


@dataclass
class ParseResult:
    slots: dict = field(default_factory=dict)
    needs: set[str] = field(default_factory=set)
    identifiers_found: set[str] = field(default_factory=set)
    language: str = "en"   # en | hi | hinglish
    clean_text: str = ""   # message with identifiers removed


def strip_identifiers(text: str) -> tuple[str, set[str]]:
    found: set[str] = set()
    for kind, pattern in IDENTIFIER_PATTERNS.items():
        if pattern.search(text):
            found.add(kind)
            text = pattern.sub(" ", text)
    return text, found


def detect_language(text: str, tokens: list[str]) -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    if HINGLISH_MARKERS & set(tokens):
        return "hinglish"
    return "en"


def _number(tok: str) -> int | None:
    t = tok.translate(DEVANAGARI_DIGITS)
    if t.isdigit() and len(t) <= 4:
        return int(t)
    return NUMBER_WORDS.get(t)


def _count_near(tokens: list[str], i: int) -> int | None:
    """A number up to 2 tokens before (skipping 'only'-words) or 2 after token i."""
    back = [j for j in range(i - 1, max(-1, i - 4), -1)]
    for j in back:
        if tokens[j] in ONLY_WORDS:
            continue
        n = _number(tokens[j])
        if n is not None:
            return n
        if tokens[j] not in {"ka", "ki", "ke", "of", "का", "की", "के"}:
            break
    for j in range(i + 1, min(len(tokens), i + 3)):
        n = _number(tokens[j])
        if n is not None:
            return n
    return None


_BUDGET_RE = re.compile(
    r"(?:budget|बजट|max(?:imum)?|upto|up to|under)\D{0,12}?((?:\d[\d,]{2,7}))|"
    r"(?:₹|rs\.?|inr)\s*((?:\d[\d,]{2,7}))\s*(?:tak|तक|max|budget|बजट)",
    re.I,
)


def _budget(text: str) -> int | None:
    """Budget is read from the raw text, but only right next to a budget word, before identifiers are stripped."""
    m = _BUDGET_RE.search(text.translate(DEVANAGARI_DIGITS))
    if not m:
        return None
    n = int((m.group(1) or m.group(2)).replace(",", ""))
    return n if 100 <= n <= 999_999 else None


def parse(text: str, lex: Lexicon, expecting: str | None = None) -> ParseResult:
    budget = _budget(text)
    clean, ids = strip_identifiers(text)
    tokens = tokenize(clean)
    res = ParseResult(identifiers_found=ids, clean_text=clean, language=detect_language(text, tokens))
    lowered = " " + " ".join(tokens) + " "

    # Business type: canonical names first (longest first), then aliases.
    for btype in sorted(lex.business_types, key=len, reverse=True):
        if f" {btype} " in lowered:
            res.slots["business_type"] = lex.business_types[btype]
            break
    else:
        for alias in sorted(BUSINESS_ALIASES, key=len, reverse=True):
            if f" {alias} " in lowered:
                res.slots["business_type"] = BUSINESS_ALIASES[alias]
                break
    if "business_type" in res.slots:
        res.slots["segment"] = lex.business_segment[res.slots["business_type"]]

    # City.
    for name in sorted(lex.cities, key=len, reverse=True):
        if f" {name} " in lowered:
            city, tier, state = lex.cities[name]
            res.slots.update(city=city, city_tier=tier, state=state)
            break

    # Employees and sites: a number next to a people word / site word.
    for i, tok in enumerate(tokens):
        if tok in PEOPLE_WORDS and "employees" not in res.slots:
            n = _count_near(tokens, i)
            if n is not None and 1 <= n <= 500:
                res.slots["employees"] = n
        if tok in SITE_WORDS and "sites" not in res.slots:
            n = _count_near(tokens, i)
            if n is not None and 1 <= n <= 50:
                res.slots["sites"] = n

    # GSTIN yes/no (never the number itself: that only comes through the P2 form).
    gst_positions = [i for i, t in enumerate(tokens) if t in GSTIN_WORDS]
    if gst_positions or expecting == "has_gstin":
        window = set()
        for i in gst_positions or range(len(tokens)):
            window |= set(tokens[max(0, i - 3): i + 4])
        if window & NO_WORDS:
            res.slots["has_gstin"] = False
        elif window & YES_WORDS or "gstin" in ids:
            res.slots["has_gstin"] = True

    # Needs.
    for phrase, pid in NEED_PHRASES.items():
        if f" {phrase} " in lowered:
            res.needs.add(pid)
    for tok in tokens:
        if tok in NEED_WORDS:
            res.needs.add(NEED_WORDS[tok])

    if budget is not None:
        res.slots["budget"] = budget

    # A bare answer to the question just asked ("12", "haan", "do").
    if expecting in {"employees", "sites"} and expecting not in res.slots:
        nums = [n for n in (_number(t) for t in tokens) if n is not None]
        if len(nums) == 1:
            lo, hi = (1, 500) if expecting == "employees" else (1, 50)
            if lo <= nums[0] <= hi:
                res.slots[expecting] = nums[0]
    return res
