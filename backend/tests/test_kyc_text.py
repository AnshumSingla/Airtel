"""Cases taken from the day-1 OCR spike output (evidence/ocr_spike/results.json)."""

from __future__ import annotations

from datetime import date

import pytest

from app.kyc.text import clean_value, is_watermark_fragment, iso_date, norm_name, pincode


@pytest.mark.parametrize("raw, clean", [
    ("NOT A VALID DOCUM 22,425", "22,425"),
    ("Shop/Unit 238, Ring Road, Vadodara, Gujarat - 348176 IOT", "Shop/Unit 238, Ring Road, Vadodara, Gujarat - 348176"),
    ("Regular", "Regular"),
    ("Proprietorship", "Proprietorship"),
    ("2025-06-07", "2025-06-07"),
])
def test_clean_value(raw, clean):
    assert clean_value(raw) == clean


@pytest.mark.parametrize("token, expected", [
    ("CUM", True), ("DOCUM", True), ("IOT", True), ("NOTA", True),
    ("LLP", False), ("Regular", False), ("ABC", False), ("Services", False),
])
def test_watermark_fragments(token, expected):
    assert is_watermark_fragment(token) is expected


def test_norm_name_ignores_spacing_and_suffixes():
    assert norm_name("VindhyaTours&Travels") == norm_name("Vindhya Tours & Travels")
    assert norm_name("Kaveri StaysLLP") == norm_name("Kaveri Stays LLP") == "kaveristays"
    assert norm_name("Harmony Pvt Ltd") == "harmony"
    assert norm_name("Neha Kaur (Prop. Vindhya Tours & Travels)") == "nehakaurvindhyatourstravels"


@pytest.mark.parametrize("address, pin", [
    ("Shop/Unit 38, Civil Lines, Kochi, Kerala - 75 2083", "752083"),
    ("Shop/Unit 21, Sector 14, Mumbai, Maharashtra -570043", "570043"),
    ("Shop/Unit 238, Ring Road, Vadodara, Gujarat - 348176 IOT", "348176"),
    ("no pin here", None),
])
def test_pincode(address, pin):
    assert pincode(address) == pin


def test_iso_date():
    assert iso_date("2025-10-31") == date(2025, 10, 31)
    assert iso_date("2025-13-31") is None
    assert iso_date("") is None
