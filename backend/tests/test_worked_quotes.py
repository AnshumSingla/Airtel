"""Every number in docs/WORKED_QUOTES.md and the POLICIES.md §10 mixed-order example.

If one of these fails, either the engine or the doc is wrong; fix whichever
one is, never just the expected value.
"""

from __future__ import annotations

import pytest

from app.catalogue.models import load_catalogue_csv
from app.catalogue.rules import GstinStatus, Profile, check_bundle
from app.pricing.quote import build_quote, tax_on, unit_price


@pytest.fixture(scope="module")
def cat(data_dir):
    return load_catalogue_csv(data_dir / "product_catalogue.csv")


PROF = Profile("prof", 1, 12, 1, GstinStatus.ACTIVE)            # A: dental clinic, Pune
MICRO = Profile("micro", 2, 3, 1, GstinStatus.NONE)              # B: kirana, Ludhiana
MULTI = Profile("multi", 1, 40, 4, GstinStatus.ACTIVE)           # C: restaurant chain

QUOTES = {
    # name: (profile, items, monthly ex, monthly tax, monthly incl, one-time ex, one-time tax, first payment)
    "A": (PROF, [("P02", 1), ("P16", 7), ("P20", 5), ("P08", 2)], 4633, 834, 5467, 0, 0, 5467),
    "B": (MICRO, [("P01", 1), ("P07", 1), ("P19", 1)], 2197, 395, 2592, 2500, 450, 5542),
    "B+": (MICRO, [("P01", 1), ("P07", 2), ("P19", 1), ("P22", 1), ("P23", 2)], 3543, 638, 4181, 7100, 1278, 12559),
    "C": (MULTI, [("P02", 4), ("P09", 4), ("P10", 4), ("P19", 4), ("P23", 8), ("P08", 4)],
          28576, 5144, 33720, 50400, 9072, 93192),
    "C with P01": (MULTI, [("P01", 4), ("P09", 4), ("P10", 4), ("P19", 4), ("P23", 8), ("P08", 4)],
                   26376, 4748, 31124, 50400, 9072, 90596),
}


@pytest.mark.parametrize("name", QUOTES)
def test_worked_quote_totals(cat, name):
    _profile, items, m_ex, m_tax, m_inc, o_ex, o_tax, first = QUOTES[name]
    q = build_quote(cat, items)
    assert (q.monthly_ex_tax, q.monthly_tax, q.monthly_incl_tax) == (m_ex, m_tax, m_inc)
    assert (q.one_time_ex_tax, q.one_time_tax, q.first_payment) == (o_ex, o_tax, first)


@pytest.mark.parametrize("name", ["A", "B", "B+", "C"])
def test_worked_quotes_pass_hard_rules_and_are_on_target(cat, name):
    profile, items, *_ = QUOTES[name]
    checks = check_bundle(cat, profile, [pid for pid, _ in items])
    assert [c.product_id for c in checks if not c.eligible] == []
    assert [c.product_id for c in checks if "INFO_OFF_TARGET" in c.info] == []


def test_p01_for_multi_site_is_allowed_but_flagged_off_target(cat):
    profile, items, *_ = QUOTES["C with P01"]
    checks = {c.product_id: c for c in check_bundle(cat, profile, [p for p, _ in items])}
    assert all(c.eligible for c in checks.values())
    assert checks["P01"].info == ("INFO_OFF_TARGET",)


def test_quote_a_line_details(cat):
    q = build_quote(cat, QUOTES["A"][1])
    assert [(ln.product_id, ln.unit_monthly, ln.monthly) for ln in q.lines] == [
        ("P02", 1649, 1649), ("P16", 138, 966), ("P20", 124, 620), ("P08", 699, 1398)]
    assert {ln.product_id: ln.term_months for ln in q.lines} == {"P02": 12, "P16": 12, "P20": 12, "P08": 1}
    assert q.slowest_install_days == 5


def test_quote_c_terms_and_install(cat):
    q = build_quote(cat, QUOTES["C"][1])
    assert q.longest_term_months == 24 and q.slowest_install_days == 14


def test_mixed_order_example_from_policies_section_10(cat):
    v1 = build_quote(cat, [("P02", 1), ("P16", 7), ("P15", 1)])
    assert (v1.monthly_ex_tax, v1.monthly_incl_tax) == (3864, 4560)
    profile = Profile("prof", 1, 12, 1, GstinStatus.INACTIVE)  # GSTIN Cancelled
    checks = {c.product_id: c for c in check_bundle(cat, profile, ["P02", "P16", "P15"])}
    assert checks["P15"].excluded == ("EXCL_GSTIN_INACTIVE",)
    assert checks["P02"].eligible and checks["P16"].eligible
    v2 = build_quote(cat, [("P02", 1), ("P16", 7)])
    assert (v2.monthly_ex_tax, v2.monthly_incl_tax) == (2615, 3086)


def test_negative_n1_tier2_cannot_get_1g(cat):
    [c] = check_bundle(cat, Profile("prof", 2, 12, 1, GstinStatus.ACTIVE), ["P03"])
    assert c.excluded == ("EXCL_TIER",)


def test_negative_n2_no_gstin_cannot_get_whatsapp_api(cat):
    checks = {c.product_id: c for c in check_bundle(cat, MICRO, ["P15", "P01"])}
    assert checks["P15"].excluded == ("EXCL_GSTIN_MISSING",)
    assert checks["P01"].eligible


def test_gstin_not_yet_checked_is_its_own_reason(cat):
    [c] = check_bundle(cat, Profile("micro", 2, 3, 1, GstinStatus.UNKNOWN), ["P15"])
    assert c.excluded == ("EXCL_GSTIN_UNKNOWN",)


def test_negative_n3_cctv_without_connectivity(cat):
    [c] = check_bundle(cat, Profile("micro", 1, 3, 1, GstinStatus.NONE), ["P23"])
    assert c.excluded == ("EXCL_DEP_UNRESOLVED",)


def test_dependency_needs_an_eligible_provider(cat):
    """Fibre 1G in a tier-2 city can't satisfy the CCTV dependency."""
    profile = Profile("prof", 2, 12, 1, GstinStatus.ACTIVE)
    checks = {c.product_id: c for c in check_bundle(cat, profile, ["P03", "P23"])}
    assert checks["P03"].excluded == ("EXCL_TIER",)
    assert checks["P23"].excluded == ("EXCL_DEP_UNRESOLVED",)


def test_size_minimums(cat):
    checks = {c.product_id: c for c in check_bundle(cat, Profile("multi", 1, 5, 2, GstinStatus.ACTIVE),
                                                     ["P02", "P10"])}
    assert set(checks["P10"].excluded) == {"EXCL_MIN_EMP", "EXCL_MIN_SITES"}


def test_rounding_rules():
    assert tax_on(4633) == 834      # 833.94
    assert tax_on(2615) == 471      # 470.70
    assert tax_on(25) == 5          # 4.5 rounds half up


def test_unit_price_is_band_midpoint_half_up(cat):
    assert unit_price(cat["P16"]) == 138   # (125 + 150) / 2 = 137.5
    assert unit_price(cat["P01"]) == 1099


def test_quantity_must_be_positive(cat):
    with pytest.raises(ValueError):
        build_quote(cat, [("P01", 0)])


def test_unknown_product_is_rejected(cat):
    with pytest.raises(KeyError):
        check_bundle(cat, PROF, ["P99"])
