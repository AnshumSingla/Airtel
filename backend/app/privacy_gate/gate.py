"""Privacy gate: the only path from owner text to an outbound LLM request (POLICIES.md §5.2).

1. Identifier-like patterns are removed outright (shared with the parser).
2. Runs of more than 4 number words ("nine eight seven six five ...") are removed.
3. The text is rebuilt token by token: a token leaves the server only if it is
   in the allowlisted vocabulary or is a number of at most 4 digits. Every
   other token becomes "[?]". Names, streets and other volunteered details
   are not in the vocabulary, so they never leave.
4. If more than half the tokens were masked, no call is made at all.

Payload builders below are the only functions that create LLM request bodies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.advisor.lexicon import NUMBER_WORDS, Lexicon, tokenize
from app.advisor.parser import strip_identifiers

MASK = "[?]"
MAX_MASKED_SHARE = 0.5


@dataclass(frozen=True)
class GateResult:
    outbound_text: str
    tokens: int
    masked: int
    identifiers_removed: frozenset[str] = field(default_factory=frozenset)

    @property
    def masked_share(self) -> float:
        return self.masked / self.tokens if self.tokens else 1.0

    @property
    def may_call(self) -> bool:
        return self.tokens > 0 and self.masked_share <= MAX_MASKED_SHARE


class PrivacyGate:
    def __init__(self, lex: Lexicon):
        self._allowed = lex.allowed_tokens()

    def _token_ok(self, tok: str) -> bool:
        return tok in self._allowed or (tok.isdigit() and len(tok) <= 4)

    def apply(self, text: str) -> GateResult:
        stripped, ids = strip_identifiers(text)
        tokens = tokenize(stripped)
        # Step 2: long runs of number words could spell out a phone number.
        out: list[str] = []
        run: list[str] = []
        masked = 0

        def flush_run():
            nonlocal masked
            if len(run) > 4:
                out.append(MASK)
                masked += len(run)
            else:
                out.extend(run)
            run.clear()

        for tok in tokens:
            if tok in NUMBER_WORDS or tok.isdigit():
                run.append(tok if self._token_ok(tok) else MASK)
                if not self._token_ok(tok):
                    masked += 1
                continue
            flush_run()
            if self._token_ok(tok):
                out.append(tok)
            else:
                out.append(MASK)
                masked += 1
        flush_run()
        return GateResult(" ".join(out), len(tokens), masked, frozenset(ids))


# ---------------------------------------------------------------- payloads

SIZE_BANDS = ((1, 5, "1-5"), (6, 20, "6-20"), (21, 50, "21-50"), (51, 10_000, "51+"))
SITE_BANDS = ((1, 1, "1"), (2, 3, "2-3"), (4, 10, "4-10"), (11, 10_000, "11+"))


def _band(n: int | None, bands) -> str | None:
    if n is None:
        return None
    return next(label for lo, hi, label in bands if lo <= n <= hi)


def coarse_slots(slots: dict) -> dict:
    """The only slot values an LLM may see: enums and size bands, never names or the city."""
    return {
        "segment": slots.get("segment"),
        "city_tier": slots.get("city_tier"),
        "employees_band": _band(slots.get("employees"), SIZE_BANDS),
        "sites_band": _band(slots.get("sites"), SITE_BANDS),
        "has_gstin": slots.get("has_gstin"),
    }


def slot_extraction_payload(gated: GateResult, slots: dict, missing: list[str], language: str) -> dict:
    if not gated.may_call:
        raise ValueError("gate refused this message; no LLM call may be built from it")
    return {"task": "extract_slots", "language": language, "message": gated.outbound_text,
            "known": coarse_slots(slots), "missing": list(missing)}


def explanation_payload(reason_codes: list[tuple[str, str]], slots: dict, language: str) -> dict:
    """Reason codes and product ids only. No owner text of any kind."""
    return {"task": "explain", "language": language,
            "reasons": [{"code": c, "product_id": p} for c, p in reason_codes],
            "known": coarse_slots(slots)}
