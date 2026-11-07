from __future__ import annotations

import pytest
from sqlalchemy import select

from app.data.schema import gstin_registry, historical_leads, udyam_registry
from app.privacy.masking import mask_gstin, mask_text, mask_udyam
from app.registry.identifiers import (
    gstin_check_char,
    gstin_repair_candidates,
    validate_gstin,
    validate_udyam,
)

K01_GSTIN = "37IHKXV5167L1ZS"  # from data/raw/kyc_documents/K01_gst_certificate.png


def test_every_registry_gstin_is_valid_and_state_matches(seeded_engine):
    with seeded_engine.connect() as conn:
        rows = conn.execute(select(gstin_registry.c.gstin, gstin_registry.c.state)).all()
    assert len(rows) == 3534
    bad = [(g, s, validate_gstin(g)) for g, s in rows if not validate_gstin(g).ok or validate_gstin(g).state != s]
    assert bad == []


def test_every_lead_gstin_and_udyam_is_well_formed(seeded_engine):
    with seeded_engine.connect() as conn:
        rows = conn.execute(select(historical_leads.c.gstin, historical_leads.c.udyam_number)).all()
    gstins = [g for g, _ in rows if g]
    udyams = [u for _, u in rows if u]
    assert gstins and all(validate_gstin(g).ok for g in gstins)
    assert udyams and all(validate_udyam(u).ok for u in udyams)


def test_every_registry_udyam_is_valid_and_state_matches(seeded_engine):
    with seeded_engine.connect() as conn:
        rows = conn.execute(select(udyam_registry.c.udyam_number, udyam_registry.c.state)).all()
    bad = [(u, s) for u, s in rows if not validate_udyam(u).ok or validate_udyam(u).state != s]
    assert bad == []


def test_check_char_detects_single_change():
    assert gstin_check_char(K01_GSTIN[:14]) == K01_GSTIN[14]
    changed = K01_GSTIN[:7] + "6" + K01_GSTIN[8:]  # 5 -> 6 in the PAN digits
    assert validate_gstin(changed).problems == ("CHECK_DIGIT",)


@pytest.mark.parametrize(
    "raw, problem",
    [
        ("37IHKXV5167L1Z", "LENGTH"),
        ("37IHKXV5167L1Z#", "CHARSET"),
        ("00IHKXV5167L1ZS", "STATE_CODE"),
        ("37IHK1V5167L1ZS", "PAN_FORMAT"),
        ("37IHKQV5167L1ZS", "PAN_ENTITY_TYPE"),
        ("37IHKXV5167L1YS", "DEFAULT_Z"),
    ],
)
def test_format_problems_are_named(raw, problem):
    check = validate_gstin(raw)
    assert not check.ok and problem in check.problems


def test_entity_type_x_is_accepted_per_data_readme():
    assert validate_gstin(K01_GSTIN).ok
    assert K01_GSTIN[5] == "X"


def test_spaces_and_lowercase_are_normalised():
    assert validate_gstin(" 37ihkxv5167l1zs ").value == K01_GSTIN
    assert validate_gstin("37IH KXV5 167L 1ZS").ok


def test_repair_proposes_the_ocr_fix_but_does_not_apply_it():
    # OCR read the digit 1 as the letter I inside the PAN digits.
    misread = "37IHKXV5I67L1ZS"
    assert not validate_gstin(misread).ok
    assert gstin_repair_candidates(misread) == [K01_GSTIN]
    # Two confusions at once: 1 read as I in a digit slot, and the final S read as 5.
    assert K01_GSTIN in gstin_repair_candidates("37IHKXV5I67L1Z5")


def test_repair_returns_nothing_for_valid_or_hopeless_input():
    assert gstin_repair_candidates(K01_GSTIN) == []
    assert gstin_repair_candidates("37IHKXV5167L1Z") == []


def test_repair_never_breaks_position_types():
    """A digit slot is never repaired to a letter and vice versa."""
    for cand in gstin_repair_candidates("3ZIHKXV5I67L1ZS"):
        assert cand[:2].isdigit() and cand[7:11].isdigit()


@pytest.mark.parametrize(
    "raw, canonical",
    [
        ("UDYAM-KL-00-3078801", "UDYAM-KL-00-3078801"),
        ("udyam kl 00 3078801", "UDYAM-KL-00-3078801"),
        ("UDYAMKL003078801", "UDYAM-KL-00-3078801"),
    ],
)
def test_udyam_separators_are_tolerated(raw, canonical):
    check = validate_udyam(raw)
    assert check.ok and check.value == canonical and check.state == "Kerala"


def test_udyam_bad_inputs():
    assert validate_udyam("").problems == ("FORMAT",)
    assert validate_udyam("UDYAM-KL-00-30788").problems == ("FORMAT",)
    assert validate_udyam("UDYAM-ZZ-00-3078801").problems == ("STATE_CODE",)


def test_masking():
    assert mask_gstin(K01_GSTIN) == "37IH••••••••1ZS"
    assert mask_udyam("UDYAM-KL-00-3078801") == "UDYAM-KL-00-•••8801"
    text = f"gst {K01_GSTIN} udyam UDYAM-KL-00-3078801 call 98765 43210 mail a.b@example.com"
    masked = mask_text(text)
    for secret in (K01_GSTIN, "3078801", "98765 43210", "a.b@example.com"):
        assert secret not in masked
