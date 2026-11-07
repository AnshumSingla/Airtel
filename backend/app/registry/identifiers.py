"""Format checks for GSTIN and Udyam numbers (POLICIES.md §8–§9).

A passing format check only means the identifier is well formed. Whether the
registration exists and is Active comes from the (mock) registry lookup.

OCR repair (POLICIES.md §9): ``gstin_repair_candidates`` proposes corrections
for common OCR confusions. It never applies them. The caller shows a single
candidate to the owner to confirm, and keeps the raw value and the candidate in
the repair trail.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_VALUE = {ch: i for i, ch in enumerate(GSTIN_ALPHABET)}

# GST state codes. The mock registry uses 14 of these; the rest are listed so a
# real-format GSTIN from another state is recognised rather than rejected.
GST_STATE_CODES: dict[str, str] = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory", "99": "Centre Jurisdiction",
}

# Udyam state codes as used by the mock registry (e.g. Karnataka is "KR").
UDYAM_STATE_CODES: dict[str, str] = {
    "AP": "Andhra Pradesh", "BR": "Bihar", "DL": "Delhi", "GJ": "Gujarat", "KL": "Kerala",
    "KR": "Karnataka", "MH": "Maharashtra", "MP": "Madhya Pradesh", "PB": "Punjab",
    "RJ": "Rajasthan", "TN": "Tamil Nadu", "TS": "Telangana", "UP": "Uttar Pradesh",
    "WB": "West Bengal",
}

# Real PAN 4th-character entity types, plus "X", which the data pack uses on
# purpose so no synthetic GSTIN can match a real taxpayer (data/raw/README.md).
PAN_ENTITY_TYPES = set("ABCFGHJLPT") | {"X"}

_UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")

# OCR confusions we are willing to propose a repair for (POLICIES.md §9).
OCR_CONFUSIONS: dict[str, str] = {"O": "0", "0": "O", "I": "1", "1": "I", "S": "5", "5": "S",
                                  "B": "8", "8": "B", "Z": "2", "2": "Z"}


@dataclass(frozen=True)
class IdentifierCheck:
    value: str
    ok: bool
    problems: tuple[str, ...] = field(default_factory=tuple)
    state: str | None = None


def normalise(raw: str) -> str:
    """Upper-case and drop spaces, dashes and dots that OCR or typing adds."""
    return re.sub(r"[\s.\-]", "", raw).upper()


def gstin_check_char(first14: str) -> str:
    """GSTN check character: mod-36 weighted sum, weights alternating 1, 2."""
    if len(first14) != 14 or any(ch not in _GSTIN_VALUE for ch in first14):
        raise ValueError("need 14 characters from 0-9A-Z")
    total = 0
    for i, ch in enumerate(first14):
        product = _GSTIN_VALUE[ch] * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return GSTIN_ALPHABET[(36 - total % 36) % 36]


def validate_gstin(raw: str) -> IdentifierCheck:
    g = normalise(raw)
    problems: list[str] = []
    if len(g) != 15:
        return IdentifierCheck(g, False, ("LENGTH",))
    if any(ch not in _GSTIN_VALUE for ch in g):
        return IdentifierCheck(g, False, ("CHARSET",))

    state = GST_STATE_CODES.get(g[:2])
    if state is None:
        problems.append("STATE_CODE")
    pan = g[2:12]
    if not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", pan):
        problems.append("PAN_FORMAT")
    elif pan[3] not in PAN_ENTITY_TYPES:
        problems.append("PAN_ENTITY_TYPE")
    if g[12] == "0":
        problems.append("ENTITY_NUMBER")
    if g[13] != "Z":
        problems.append("DEFAULT_Z")
    if not problems and gstin_check_char(g[:14]) != g[14]:
        problems.append("CHECK_DIGIT")
    return IdentifierCheck(g, not problems, tuple(problems), state)


# Character class expected at each GSTIN position: d = digit, a = letter, x = either.
_GSTIN_SHAPE = "dd" + "aaaaa" + "dddd" + "a" + "x" + "a" + "x"


def gstin_repair_candidates(raw: str, max_changes: int = 2) -> list[str]:
    """Valid GSTINs reachable from ``raw`` by at most ``max_changes`` OCR-confusion swaps.

    Returns an empty list if ``raw`` is already valid or nothing fits. Never
    applies a repair: POLICIES.md §9 requires the owner to confirm, and a
    repaired identifier needs a matching registry name before checks can pass.
    """
    g = normalise(raw)
    if len(g) != 15 or validate_gstin(g).ok:
        return []
    swappable = []
    for i, ch in enumerate(g):
        alt = OCR_CONFUSIONS.get(ch)
        if alt is None:
            continue
        kind = _GSTIN_SHAPE[i]
        if kind == "x" or (kind == "d") == alt.isdigit():
            swappable.append((i, alt))
    found: set[str] = set()
    for k in range(1, max_changes + 1):
        for combo in itertools.combinations(swappable, k):
            chars = list(g)
            for i, alt in combo:
                chars[i] = alt
            cand = "".join(chars)
            if validate_gstin(cand).ok:
                found.add(cand)
    return sorted(found)


_UDYAM_COMPACT_RE = re.compile(r"^UDYAM([A-Z]{2})(\d{2})(\d{7})$")


def validate_udyam(raw: str) -> IdentifierCheck:
    """Accept any spacing/dashes ("UDYAM KL 00 3078801"); report the canonical form."""
    compact = re.sub(r"[^0-9A-Z]", "", raw.upper())
    m = _UDYAM_COMPACT_RE.match(compact)
    if not m:
        return IdentifierCheck(compact, False, ("FORMAT",))
    u = f"UDYAM-{m.group(1)}-{m.group(2)}-{m.group(3)}"
    state = UDYAM_STATE_CODES.get(m.group(1))
    problems = [] if state else ["STATE_CODE"]
    return IdentifierCheck(u, not problems, tuple(problems), state)
