"""The recommender must rebuild WORKED_QUOTES.md A, B and C from their summary cards alone."""

from __future__ import annotations

import pytest

from app.catalogue.recommend import build_segment_stats, recommend
from app.catalogue.rules import GstinStatus, Profile


@pytest.fixture(scope="module")
def stats(seeded_engine):
    return build_segment_stats(seeded_engine)


def lines(rec):
    return {ln.product_id: ln.quantity for ln in rec.lines}


def tags(rec, pid):
    return [r.tag for ln in rec.lines if ln.product_id == pid for r in ln.reasons]


def test_stats_denominators(stats):
    assert stats.activated == {"prof": 138, "micro": 110, "multi": 83, "mfg": 37}
    assert round(stats.share("multi", "P01"), 3) == 0.518 and round(stats.share("multi", "P02"), 3) == 0.482


def test_quote_a_professional_office(cat, stats):
    rec = recommend(cat, stats, Profile("prof", 1, 12, 1, GstinStatus.ACTIVE))
    assert lines(rec) == {"P02": 1, "P16": 7, "P20": 5, "P08": 2}
    assert rec.quote.monthly_ex_tax == 4633 and rec.quote.first_payment == 5467
    p02 = next(r for ln in rec.lines if ln.product_id == "P02" for r in ln.reasons)
    assert p02.tag == "SEGMENT_DEFAULT" and p02.data == {"share": 0.44, "n": 138}
    assert tags(rec, "P16") == ["SEGMENT_DEFAULT", "QTY_DEFAULT"]


def test_quote_b_micro_with_stated_billing_need(cat, stats):
    rec = recommend(cat, stats, Profile("micro", 2, 3, 1, GstinStatus.NONE), needs={"P19"})
    assert lines(rec) == {"P01": 1, "P07": 1, "P19": 1}
    assert rec.quote.monthly_ex_tax == 2197 and rec.quote.first_payment == 5542
    assert tags(rec, "P19")[0] == "YOU_TOLD_US"


def test_quote_c_multi_site(cat, stats):
    rec = recommend(cat, stats, Profile("multi", 1, 40, 4, GstinStatus.ACTIVE), needs={"P19", "P23", "P10"})
    assert lines(rec) == {"P02": 4, "P09": 4, "P10": 4, "P19": 4, "P23": 8, "P08": 4}
    assert rec.quote.monthly_ex_tax == 28576 and rec.quote.first_payment == 93192
    assert tags(rec, "P02")[0] == "CATALOGUE_TARGET"   # P01 is chosen more often but off-target
    assert tags(rec, "P09")[0] == "SEGMENT_DEFAULT"
    assert {tags(rec, p)[0] for p in ("P10", "P19", "P23")} == {"YOU_TOLD_US"}
    assert all("INFO_OFF_TARGET" not in ln.info for ln in rec.lines)


def test_no_gstin_whatsapp_need_is_excluded_with_reason(cat, stats):
    rec = recommend(cat, stats, Profile("micro", 2, 3, 1, GstinStatus.NONE), needs={"P15"})
    assert "P15" not in lines(rec)
    assert {"product_id": "P15", "codes": ["EXCL_GSTIN_MISSING"], "source": "need"} in rec.excluded


def test_gstin_not_checked_yet_locks_gstin_only_defaults(cat, stats):
    rec = recommend(cat, stats, Profile("multi", 1, 40, 4, GstinStatus.UNKNOWN))
    assert "P10" not in lines(rec)  # SD-WAN needs an active GSTIN
    assert any(e["product_id"] == "P10" and e["codes"] == ["EXCL_GSTIN_UNKNOWN"] for e in rec.excluded)


def test_tier2_professional_never_gets_1g(cat, stats):
    rec = recommend(cat, stats, Profile("prof", 2, 12, 1, GstinStatus.ACTIVE))
    assert "P03" not in lines(rec) and "P02" in lines(rec)


def test_stated_off_target_need_is_allowed_and_flagged(cat, stats):
    rec = recommend(cat, stats, Profile("prof", 1, 12, 1, GstinStatus.ACTIVE), needs={"P19"})
    p19 = next(ln for ln in rec.lines if ln.product_id == "P19")
    assert p19.info == ("INFO_OFF_TARGET",) and p19.stated


def test_budget_trims_segment_defaults_but_keeps_stated_and_connectivity(cat, stats):
    full = recommend(cat, stats, Profile("prof", 1, 12, 1, GstinStatus.ACTIVE), needs={"P23"})
    rec = recommend(cat, stats, Profile("prof", 1, 12, 1, GstinStatus.ACTIVE), needs={"P23"},
                    budget_incl_tax=full.quote.monthly_incl_tax - 1)
    assert rec.dropped_for_budget and set(rec.dropped_for_budget) <= {"P16", "P20"}
    assert {"P02", "P08", "P23"} <= set(lines(rec))
    assert rec.quote.monthly_incl_tax < full.quote.monthly_incl_tax


def test_manufacturer_without_gstin_gets_no_off_target_connectivity_default(cat, stats):
    rec = recommend(cat, stats, Profile("mfg", 2, 30, 1, GstinStatus.NONE))
    assert not set(lines(rec)) & {"P01", "P02", "P04"}  # all off-target for mfg
    assert "NO_ON_TARGET_CONNECTIVITY" in rec.notes
