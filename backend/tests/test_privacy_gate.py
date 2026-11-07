from __future__ import annotations

import json

import pytest

from app.privacy_gate.gate import (
    PrivacyGate, coarse_slots, explanation_payload, slot_extraction_payload,
)
from app.privacy_gate.redteam import run_redteam


@pytest.fixture(scope="module")
def gate(lex):
    return PrivacyGate(lex)


def test_redteam_has_no_unexpected_leaks(gate):
    result = run_redteam(gate)
    assert result.leaks == [], json.dumps(result.leaks, ensure_ascii=False, indent=1)


def test_known_residual_is_still_observed_and_reported(gate):
    """If this starts failing, the residual changed: update the fixture and the report."""
    result = run_redteam(gate)
    assert [r["observed"] for r in result.residual] == [r["leaks"] for r in result.residual]


def test_benign_messages_mostly_stay_callable(gate):
    result = run_redteam(gate)
    assert result.benign_callable / result.benign_total >= 0.9


def test_example_from_architecture_doc(gate):
    g = gate.apply("Do branch hain, ek Kothrud wali Mrs. Joshi ke ghar ke paas")
    assert g.outbound_text == "do branch hain ek [?] wali [?] [?] ke [?] ke paas"
    assert g.may_call


def test_mostly_masked_message_is_refused(gate):
    g = gate.apply("Rakesh Malhotra Laxmi Road Dagdusheth")
    assert not g.may_call
    with pytest.raises(ValueError):
        slot_extraction_payload(g, {}, ["segment"], "en")


def test_payloads_carry_only_coarse_slots(gate):
    slots = {"business_type": "Dental clinic", "segment": "prof", "city": "Pune", "city_tier": 1,
             "state": "Maharashtra", "employees": 12, "sites": 1, "has_gstin": True}
    p = slot_extraction_payload(gate.apply("GST hai"), slots, ["needs"], "hinglish")
    e = explanation_payload([("SEGMENT_DEFAULT", "P02")], slots, "en")
    for payload in (p, e):
        text = json.dumps(payload)
        assert "Pune" not in text and "Dental" not in text and "Maharashtra" not in text
        assert payload["known"] == coarse_slots(slots) == {
            "segment": "prof", "city_tier": 1, "employees_band": "6-20", "sites_band": "1", "has_gstin": True}
    assert "message" not in e


def test_long_number_word_runs_are_masked(gate):
    g = gate.apply("five staff and nine eight seven six five four")
    assert "nine" not in g.outbound_text and g.outbound_text.startswith("five staff and")
