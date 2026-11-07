"""Deterministic recommender (POLICIES.md §6, §7, §14).

The LLM never picks products. Given a confirmed summary card, this module
builds the bundle and a reason for every line:

0. Only on-target products (catalogue `target_segments`) become defaults.
1. Fixed connectivity (P01-P06): the eligible on-target product most often
   bought by activated customers in the segment.
2. Mobile plan (P07/P08): same rule.
3. Other on-target products bought by at least 45% of the segment [ASSUMPTION].
4. Products for needs the owner stated ("you told us"); off-target ones allowed,
   flagged INFO_OFF_TARGET.
5. Hard eligibility rules remove lines, with exclusion codes kept for the card.
6. Quantity defaults (§7 table); budget trimming drops segment defaults first.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import Engine, select

from app.catalogue.models import SEGMENT_CODES, Catalogue
from app.catalogue.rules import GstinStatus, Profile, check_bundle
from app.data.schema import historical_leads
from app.pricing.quote import Quote, build_quote

FIXED_CONNECTIVITY = ("P01", "P02", "P03", "P04", "P05", "P06")
MOBILE = ("P07", "P08")
DEFAULT_SHARE_THRESHOLD = 0.45


@dataclass(frozen=True)
class SegmentStats:
    """Share of activated customers per segment who bought each product, with denominators."""
    activated: dict[str, int]
    bought: dict[str, Counter]

    def share(self, segment: str, product_id: str) -> float:
        n = self.activated.get(segment, 0)
        return self.bought[segment][product_id] / n if n else 0.0


def build_segment_stats(engine: Engine) -> SegmentStats:
    with engine.connect() as conn:
        rows = conn.execute(select(historical_leads.c.segment, historical_leads.c.bundle_products)
                            .where(historical_leads.c.outcome == "Activated")).all()
    activated: Counter = Counter()
    bought: dict[str, Counter] = {code: Counter() for code in SEGMENT_CODES.values()}
    for segment, bundle in rows:
        code = SEGMENT_CODES[segment]
        activated[code] += 1
        for item in {x.split("x")[0] for x in bundle.split(";")}:
            bought[code][item] += 1
    return SegmentStats(dict(activated), bought)


@dataclass(frozen=True)
class Reason:
    tag: str          # YOU_TOLD_US | SEGMENT_DEFAULT | CATALOGUE_TARGET | QTY_DEFAULT
    code: str
    data: dict = field(default_factory=dict)


@dataclass
class RecLine:
    product_id: str
    quantity: int
    reasons: list[Reason]
    info: tuple[str, ...] = ()

    @property
    def stated(self) -> bool:
        return any(r.tag == "YOU_TOLD_US" for r in self.reasons)


@dataclass
class Recommendation:
    lines: list[RecLine]
    excluded: list[dict]                  # {"product_id", "codes", "source"}
    dropped_for_budget: list[str]
    quote: Quote
    notes: list[str] = field(default_factory=list)


def default_quantity(cat: Catalogue, pid: str, segment: str, employees: int, sites: int) -> tuple[int, bool]:
    """(quantity, is_default) per POLICIES.md §7. is_default=True means 'change it on the quote'."""
    half_up = lambda x: int(x + 0.5)  # noqa: E731
    unit = cat[pid].unit
    if pid == "P16":
        return max(1, half_up(0.6 * employees)), True
    if pid == "P20":
        return max(1, half_up(0.4 * employees)), True
    if unit == "per line":
        return {"micro": 1, "prof": 2}.get(segment, max(2, sites)), True
    if unit == "per camera":
        return 2 * sites, True
    if unit == "per counter":
        return sites, True
    if unit == "per channel":
        return 2, True
    if pid in ("P24", "P25"):
        return 1, True  # the advisor asks; 1 until answered
    if unit == "per site":
        return sites, False
    return 1, False


def _pick_family(cat: Catalogue, stats: SegmentStats, profile: Profile, family: tuple[str, ...]) -> tuple[str | None, Reason | None]:
    def eligible(pid: str) -> bool:
        [c] = check_bundle(cat, profile, [pid])
        return not set(c.excluded) - {"EXCL_DEP_UNRESOLVED"}

    seg = profile.segment
    on_target = [p for p in family if seg in cat[p].target_segments and eligible(p)]
    if not on_target:
        return None, None
    best = max(on_target, key=lambda p: (stats.share(seg, p), -family.index(p)))
    best_share = stats.share(seg, best)
    off_target_higher = [p for p in family if seg not in cat[p].target_segments
                         and stats.share(seg, p) > best_share]
    data = {"share": round(best_share, 2), "n": stats.activated.get(seg, 0)}
    if off_target_higher:
        return best, Reason("CATALOGUE_TARGET", "LISTED_FOR_SEGMENT", data)
    return best, Reason("SEGMENT_DEFAULT", "MOST_CHOSEN_IN_SEGMENT", data)


def recommend(cat: Catalogue, stats: SegmentStats, profile: Profile, needs: set[str] | None = None,
              budget_incl_tax: int | None = None) -> Recommendation:
    seg = profile.segment
    needs = set(needs or ())
    chosen: dict[str, list[Reason]] = {}
    notes: list[str] = []

    for family in (FIXED_CONNECTIVITY, MOBILE):
        pid, reason = _pick_family(cat, stats, profile, family)
        if pid:
            chosen[pid] = [reason]
        elif family is FIXED_CONNECTIVITY:
            notes.append("NO_ON_TARGET_CONNECTIVITY")
    for pid, p in cat.items():
        if pid in FIXED_CONNECTIVITY + MOBILE or seg not in p.target_segments:
            continue
        share = stats.share(seg, pid)
        if share >= DEFAULT_SHARE_THRESHOLD:
            chosen[pid] = [Reason("SEGMENT_DEFAULT", "MOST_CHOSEN_IN_SEGMENT",
                                  {"share": round(share, 2), "n": stats.activated.get(seg, 0)})]
    for pid in sorted(needs):
        chosen[pid] = [Reason("YOU_TOLD_US", "STATED_NEED", {"need": pid})]

    # Hard rules: drop excluded lines; repeat, because removing a provider can break a dependency.
    excluded: list[dict] = []
    while True:
        checks = check_bundle(cat, profile, list(chosen))
        bad = [c for c in checks if not c.eligible]
        if not bad:
            break
        for c in bad:
            excluded.append({"product_id": c.product_id, "codes": list(c.excluded),
                             "source": "need" if c.product_id in needs else "default"})
            chosen.pop(c.product_id)
    info = {c.product_id: c.info for c in check_bundle(cat, profile, list(chosen))}

    lines: list[RecLine] = []
    for pid in sorted(chosen):
        qty, is_default = default_quantity(cat, pid, seg, profile.employees, profile.sites)
        reasons = list(chosen[pid])
        if is_default:
            reasons.append(Reason("QTY_DEFAULT", "DEFAULT_QUANTITY", {"quantity": qty}))
        lines.append(RecLine(pid, qty, reasons, info.get(pid, ())))

    dropped: list[str] = []
    if budget_incl_tax is not None:
        droppable = sorted((ln for ln in lines if not ln.stated
                            and ln.product_id not in FIXED_CONNECTIVITY + MOBILE),
                           key=lambda ln: stats.share(seg, ln.product_id))
        while droppable and build_quote(cat, [(ln.product_id, ln.quantity) for ln in lines]).monthly_incl_tax > budget_incl_tax:
            victim = droppable.pop(0)
            lines.remove(victim)
            dropped.append(victim.product_id)
        # Dropping a provider never happens (connectivity isn't droppable), so dependencies still hold.
    quote = build_quote(cat, [(ln.product_id, ln.quantity) for ln in lines])
    if budget_incl_tax is not None and quote.monthly_incl_tax > budget_incl_tax:
        notes.append("OVER_BUDGET_AFTER_TRIMMING")
    return Recommendation(lines, excluded, dropped, quote, notes)


def profile_from_slots(slots: dict) -> Profile:
    has = slots.get("has_gstin")
    status = slots.get("gstin_status")  # set only after a consented (P2) registry check
    if status:
        gstin = GstinStatus(status)
    elif has is True:
        gstin = GstinStatus.UNKNOWN
    else:
        gstin = GstinStatus.NONE
    return Profile(slots["segment"], int(slots["city_tier"]), int(slots["employees"]),
                   int(slots["sites"]), gstin)
