from __future__ import annotations

import pytest

from app.advisor.parser import parse


def test_hinglish_first_message(lex):
    r = parse("Meri dental clinic hai Pune mein, 12 log", lex)
    assert r.language == "hinglish"
    assert r.slots == {"business_type": "Dental clinic", "segment": "prof", "city": "Pune",
                       "city_tier": 1, "state": "Maharashtra", "employees": 12}


def test_devanagari_message(lex):
    r = parse("मेरी किराना दुकान लुधियाना में है, 3 लोग काम करते हैं", lex)
    assert r.language == "hi"
    assert r.slots["business_type"] == "Kirana store" and r.slots["segment"] == "micro"
    assert r.slots["city"] == "Ludhiana" and r.slots["city_tier"] == 2
    assert r.slots["employees"] == 3


def test_devanagari_digits_and_words(lex):
    assert parse("१२ लोग", lex).slots["employees"] == 12
    assert parse("सिर्फ एक ही जगह", lex).slots["sites"] == 1


def test_english_multi_site_with_needs(lex):
    r = parse("We run a restaurant chain in Bangalore with 4 outlets and 40 staff, need billing at "
              "each outlet, CCTV and to manage all outlets centrally", lex)
    assert r.language == "en"
    assert r.slots["segment"] == "multi" and r.slots["city"] == "Bengaluru"
    assert r.slots["sites"] == 4 and r.slots["employees"] == 40
    assert r.needs == {"P19", "P23", "P10"}


def test_sites_in_hinglish(lex):
    assert parse("Do branch hain", lex).slots["sites"] == 2
    assert parse("1 hi jagah hai", lex).slots["sites"] == 1


@pytest.mark.parametrize("msg, value", [
    ("GST hai", True), ("haan GSTIN hai", True), ("GST nahi hai", False), ("no GST", False),
    ("जीएसटी नहीं है", False), ("जीएसटी है", True),
])
def test_gstin_yes_no(lex, msg, value):
    assert parse(msg, lex).slots["has_gstin"] is value


def test_bare_answers_need_context(lex):
    assert "has_gstin" not in parse("haan", lex).slots
    assert parse("haan", lex, expecting="has_gstin").slots["has_gstin"] is True
    assert "employees" not in parse("12", lex).slots
    assert parse("12", lex, expecting="employees").slots["employees"] == 12


def test_identifiers_are_stripped_before_parsing(lex):
    r = parse("my GSTIN is 37IHKXV5167L1ZS and phone 9876543210, 8 staff", lex)
    assert {"gstin", "phone"} <= r.identifiers_found
    assert "37IHKXV5167L1ZS" not in r.clean_text and "9876543210" not in r.clean_text
    assert r.slots["employees"] == 8      # not 37, 5167 or any phone digits
    assert r.slots["has_gstin"] is True   # a GSTIN was given, but its value is not kept


def test_budget_survives_identifier_stripping(lex):
    assert parse("budget ₹15,000 per month", lex).slots["budget"] == 15000
    assert parse("₹3000 tak", lex).slots["budget"] == 3000
    assert "budget" not in parse("call 9876543210", lex).slots


def test_backup_is_disambiguated(lex):
    assert parse("need backup internet", lex).needs == {"P09"}
    assert parse("need cloud backup for files", lex).needs == {"P17"}


def test_do_as_english_word_is_not_a_count(lex):
    assert "sites" not in parse("do you have fibre in Pune", lex).slots
