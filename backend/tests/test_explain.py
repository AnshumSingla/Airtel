from __future__ import annotations

import pytest

from app.advisor.explain import exclusion_sentence, guard_sentences, template_sentence
from app.catalogue.recommend import Reason


def test_templates_match_worked_quote_wording():
    r = Reason("SEGMENT_DEFAULT", "MOST_CHOSEN_IN_SEGMENT", {"share": 0.44, "n": 138})
    assert template_sentence(r, "prof", "en", "P02") == \
        "The option professional offices choose most often (44% of 138 we've served)."
    r = Reason("SEGMENT_DEFAULT", "MOST_CHOSEN_IN_SEGMENT", {"share": 1.0, "n": 138})
    assert "every one" in template_sentence(r, "prof", "en", "P16")
    r = Reason("SEGMENT_DEFAULT", "MOST_CHOSEN_IN_SEGMENT", {"share": 0.49, "n": 138})
    assert template_sentence(r, "prof", "en", "P20").startswith("About half")
    assert template_sentence(Reason("CATALOGUE_TARGET", "LISTED_FOR_SEGMENT", {"share": 0.48, "n": 83}),
                             "multi", "en", "P02") == "Listed by Accel for multi-outlet businesses."
    assert template_sentence(Reason("YOU_TOLD_US", "STATED_NEED", {}), "micro", "en", "P19") == \
        "You told us you need billing and UPI/card payments."


@pytest.mark.parametrize("lang, needle", [("hi", "आपने बताया"), ("hinglish", "Aapne bataya")])
def test_hindi_and_hinglish_templates(lang, needle):
    assert needle in template_sentence(Reason("YOU_TOLD_US", "STATED_NEED", {}), "micro", lang, "P23")


def test_unknown_language_falls_back_to_english():
    assert template_sentence(Reason("YOU_TOLD_US", "STATED_NEED", {}), "micro", "ta", "P23").startswith("You told us")


def test_exclusion_text():
    assert exclusion_sentence(["EXCL_GSTIN_MISSING"], "en") == "Needs an active GSTIN."
    assert "GSTIN" in exclusion_sentence(["EXCL_GSTIN_INACTIVE"], "hi")


EXPECTED = {"P02:MOST_CHOSEN_IN_SEGMENT": "template A", "P16:MOST_CHOSEN_IN_SEGMENT": "template B"}


def test_guard_keeps_clean_sentences(cat):
    proposed = {"P02:MOST_CHOSEN_IN_SEGMENT": "A popular fibre choice for offices like yours.",
                "P16:MOST_CHOSEN_IN_SEGMENT": "Email on your own domain, used by offices like yours."}
    final, fallbacks = guard_sentences(cat, proposed, EXPECTED)
    assert final == proposed and fallbacks == []


@pytest.mark.parametrize("bad", [
    "Only 999 a month!",                          # digits
    "Costs a few rupees only",                    # currency word
    "Guaranteed uptime for your clinic",          # SLA claim
    "300 Mbps, fastest in town",                  # speed claim
    "Add Cloud CCTV too for safety",              # names another product
    "बहुत सस्ता, केवल ₹९९९",                        # Devanagari digits and rupee sign
    "x" * 161,                                    # too long
    "Save money with this plan",                  # savings claim
])
def test_guard_rejects_claims(cat, bad):
    proposed = {"P02:MOST_CHOSEN_IN_SEGMENT": bad, "P16:MOST_CHOSEN_IN_SEGMENT": "Fine sentence here."}
    final, fallbacks = guard_sentences(cat, proposed, EXPECTED)
    assert final["P02:MOST_CHOSEN_IN_SEGMENT"] == "template A" and fallbacks == ["P02:MOST_CHOSEN_IN_SEGMENT"]
    assert final["P16:MOST_CHOSEN_IN_SEGMENT"] == "Fine sentence here."


@pytest.mark.parametrize("proposed", [
    {"P02:MOST_CHOSEN_IN_SEGMENT": "ok"},                                    # missing key
    {**{k: "ok" for k in EXPECTED}, "P99:EXTRA": "sneaky extra claim"},     # extra key
    "not a dict",
])
def test_guard_rejects_wrong_shape(cat, proposed):
    final, fallbacks = guard_sentences(cat, proposed, EXPECTED)
    assert final == EXPECTED and fallbacks == sorted(EXPECTED)
