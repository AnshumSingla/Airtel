"""Eligibility, dependency and targeting checks (POLICIES.md §6).

Hard rules (from data/raw/README.md "eligibility rules"): city tier, minimum
employees and sites, active GSTIN, and `requires_one_of` dependencies. A line
that fails one is excluded with a reason code.

Soft rule: `target_segments` never excludes a line. An off-target line gets the
non-blocking `INFO_OFF_TARGET` code; the recommender (not this module) keeps
off-target products out of defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from app.catalogue.models import Catalogue


class GstinStatus(str, Enum):
    ACTIVE = "active"        # registry says Active
    INACTIVE = "inactive"    # registry says Cancelled or Suspended
    UNKNOWN = "unknown"      # owner says they have one, not checked yet (no P2 consent)
    NONE = "none"            # owner has no GSTIN


@dataclass(frozen=True)
class Profile:
    segment: str            # micro | prof | multi | mfg
    city_tier: int          # 1 | 2
    employees: int
    sites: int
    gstin: GstinStatus


@dataclass(frozen=True)
class LineCheck:
    product_id: str
    excluded: tuple[str, ...] = field(default_factory=tuple)  # EXCL_* codes
    info: tuple[str, ...] = field(default_factory=tuple)      # INFO_* codes

    @property
    def eligible(self) -> bool:
        return not self.excluded


_GSTIN_EXCLUSION = {
    GstinStatus.INACTIVE: "EXCL_GSTIN_INACTIVE",
    GstinStatus.UNKNOWN: "EXCL_GSTIN_UNKNOWN",
    GstinStatus.NONE: "EXCL_GSTIN_MISSING",
}


def check_line(cat: Catalogue, profile: Profile, product_id: str, bundle: Iterable[str]) -> LineCheck:
    p = cat[product_id]
    bundle_ids = set(bundle)
    excluded: list[str] = []
    if profile.city_tier not in p.city_tiers:
        excluded.append("EXCL_TIER")
    if profile.employees < p.min_employees:
        excluded.append("EXCL_MIN_EMP")
    if profile.sites < p.min_sites:
        excluded.append("EXCL_MIN_SITES")
    if p.requires_gstin and profile.gstin is not GstinStatus.ACTIVE:
        excluded.append(_GSTIN_EXCLUSION[profile.gstin])
    if p.requires_one_of and not (set(p.requires_one_of) & bundle_ids):
        excluded.append("EXCL_DEP_UNRESOLVED")
    info = () if profile.segment in p.target_segments else ("INFO_OFF_TARGET",)
    return LineCheck(product_id, tuple(excluded), info)


def check_bundle(cat: Catalogue, profile: Profile, product_ids: Iterable[str]) -> list[LineCheck]:
    """Check each line against the profile and against the rest of the bundle.

    A dependency is satisfied only by another line that is itself eligible on
    the hard rules, so an excluded fibre line can't satisfy a CCTV line.
    """
    ids = list(dict.fromkeys(product_ids))
    unknown = [i for i in ids if i not in cat]
    if unknown:
        raise KeyError(f"unknown product ids: {unknown}")
    # First pass without dependencies, to know which lines can satisfy others.
    standalone = {i: check_line(cat, profile, i, ids) for i in ids}
    usable = [i for i, c in standalone.items() if not set(c.excluded) - {"EXCL_DEP_UNRESOLVED"}]
    return [check_line(cat, profile, i, [u for u in usable if u != i]) for i in ids]
