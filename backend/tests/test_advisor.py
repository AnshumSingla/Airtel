"""End-to-end advisor conversations, scripted and with a fake LLM behind the gate."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.advisor.service import AdvisorService, SessionNotFound, _now, advisor_sessions
from app.catalogue.recommend import build_segment_stats
from app.llm.client import FakeProvider, LLMClient, ModelChain
from app.privacy_gate.gate import PrivacyGate


@pytest.fixture(scope="module")
def stats(seeded_engine):
    return build_segment_stats(seeded_engine)


def make_service(seeded_engine, lex, cat, stats, provider=None, explain=False):
    gate = PrivacyGate(lex)
    chain = ModelChain(provider, ["fake"], {}, sleep=lambda s: None) if provider else None
    llm = LLMClient(chain, lex.allowed_tokens(), enabled=provider is not None)
    return AdvisorService(seeded_engine, lex, cat, stats, gate, llm, explain_with_llm=explain, reset=False)


@pytest.fixture
def svc(seeded_engine, lex, cat, stats):
    return make_service(seeded_engine, lex, cat, stats)


def raw_state(engine, sid):
    with engine.connect() as conn:
        return conn.execute(select(advisor_sessions.c.state).where(advisor_sessions.c.session_id == sid)).scalar_one()


def test_hinglish_conversation_to_quote_a(svc):
    sid, first = svc.start()
    assert first.expecting == "segment" and first.buttons
    t = svc.message(sid, "Meri dental clinic hai Pune mein, 12 log")
    assert t.language == "hinglish" and t.expecting == "sites"
    t = svc.message(sid, "1 hi jagah hai")
    assert t.expecting == "has_gstin"
    t = svc.message(sid, "haan")
    assert t.expecting == "needs"
    t = svc.message(sid, "nahi bas itna")
    assert t.status == "confirm" and t.summary["employees"] == 12 and t.summary["city"] == "Pune"
    # The owner has a GSTIN but hasn't consented to a check: GSTIN-only items stay locked.
    rec = svc.confirm(sid, {})
    assert {ln["product_id"]: ln["quantity"] for ln in rec["lines"]} == {"P02": 1, "P08": 2, "P16": 7, "P20": 5}
    assert rec["quote"]["monthly_ex_tax"] == 4633 and rec["quote"]["tax_label"] == "Tax (illustrative 18%)"
    p02 = next(ln for ln in rec["lines"] if ln["product_id"] == "P02")
    assert p02["reasons"][0]["text"].startswith("Professional offices sabse zyada")


def test_several_needs_in_one_tap_and_junk_ids_are_ignored(svc):
    sid, _ = svc.start("en")
    for action in ["__set:segment=micro", "__set:city_tier=2", "__set:employees=3", "__set:sites=1",
                   "__set:has_gstin=true"]:
        t = svc.message(sid, action)
    assert t.expecting == "needs"
    t = svc.message(sid, "__need:P19,P23,P16,NOT_A_PRODUCT,")
    assert t.status == "confirm"
    rec = svc.confirm(sid, {})
    assert {"P19", "P23", "P16"} <= {ln["product_id"] for ln in rec["lines"]}
    assert "NOT_A_PRODUCT" not in {ln["product_id"] for ln in rec["lines"]}


def test_buttons_only_path_works_without_any_text(svc):
    sid, _ = svc.start("en")
    for action in ["__set:segment=micro", "__set:city_tier=2", "__set:employees=3", "__set:sites=1",
                   "__set:has_gstin=false", "__need:P19", "__need:none"]:
        t = svc.message(sid, action)
    assert t.status == "confirm"
    rec = svc.confirm(sid, {})
    assert {ln["product_id"] for ln in rec["lines"]} == {"P01", "P07", "P19"}
    assert rec["quote"]["first_payment"] == 5542


def test_summary_card_edits_win_over_chat(svc):
    sid, _ = svc.start()
    svc.message(sid, "restaurant chain in Bangalore, 4 outlets, 40 staff, GST hai")
    rec = svc.confirm(sid, {"sites": 2, "needs": ["P23"]})
    assert rec["summary"]["sites"] == 2
    assert next(ln for ln in rec["lines"] if ln["product_id"] == "P23")["quantity"] == 4


def test_confirm_refuses_incomplete_card(svc):
    sid, _ = svc.start()
    svc.message(sid, "salon in Kochi")
    with pytest.raises(ValueError, match="missing"):
        svc.confirm(sid, {})


def test_typed_gstin_gets_consent_card_and_is_never_stored(svc, seeded_engine):
    sid, _ = svc.start()
    t = svc.message(sid, "kirana store, my GSTIN is 37IHKXV5167L1ZS")
    assert t.consent_card and t.consent_card["purpose"] == "P2"
    stored = raw_state(seeded_engine, sid)
    assert "37IHKXV5167L1ZS" not in stored and "IHKXV" not in stored
    assert json.loads(stored)["slots"]["has_gstin"] is True


def test_unclear_message_says_so_and_offers_buttons(svc):
    sid, _ = svc.start()
    t = svc.message(sid, "hmm let me think")
    assert t.reply.startswith("Sorry, I didn't catch that") and t.buttons


def test_answering_a_later_slot_is_not_called_unclear(svc):
    sid, _ = svc.start()
    t = svc.message(sid, "Pune mein")
    assert t.expecting == "segment" and "didn't catch" not in t.reply and "samajh nahi" not in t.reply


def test_question_cap_offers_partial_quote(svc):
    sid, _ = svc.start()
    for _ in range(8):
        t = svc.message(sid, "hmm")
    assert t.status == "offer_partial" and {b["value"] for b in t.buttons} == {"__partial", "__handoff"}
    t = svc.message(sid, "__partial")
    rec = svc.confirm(sid, {})
    assert set(rec["summary"]["assumed"]) == {"segment", "city_tier", "employees", "sites", "has_gstin"}


def test_end_and_delete_removes_the_session(svc):
    sid, _ = svc.start()
    assert svc.end(sid) is True
    with pytest.raises(SessionNotFound):
        svc.message(sid, "hello")


def test_idle_sessions_expire_after_24h(svc, seeded_engine):
    sid, _ = svc.start()
    with seeded_engine.begin() as conn:
        conn.execute(update(advisor_sessions).where(advisor_sessions.c.session_id == sid)
                     .values(last_activity=_now() - timedelta(hours=25)))
    assert svc.purge_idle() >= 1
    with pytest.raises(SessionNotFound):
        svc.message(sid, "hello")


def test_llm_is_called_only_when_local_parser_fails_and_only_with_gated_text(seeded_engine, lex, cat, stats):
    fake = FakeProvider(lambda model, payload: {"segment": "prof", "employees": 9999, "city_tier": 7})
    svc = make_service(seeded_engine, lex, cat, stats, provider=fake)
    sid, _ = svc.start()
    svc.message(sid, "Meri dental clinic hai Pune mein, 12 log")   # parser handles it
    assert fake.calls == []
    t = svc.message(sid, "hum log ek hi jagah se kaam karte, Mrs Joshi ke ghar ke paas")
    # 'ek hi jagah' is parsed locally, so still no call
    assert fake.calls == [] and t.expecting == "has_gstin"
    t = svc.message(sid, "kuch pata nahi Rakesh bhai se puchna padega")
    sent = json.dumps([p for _, p in fake.calls])
    assert "rakesh" not in sent.lower() and "joshi" not in sent.lower()
    # Invalid values from the LLM are dropped by validation.
    state = json.loads(raw_state(seeded_engine, sid))
    assert state["slots"]["employees"] == 12 and state["slots"]["city_tier"] == 1


def test_llm_failure_falls_back_to_scripted_reply(seeded_engine, lex, cat, stats):
    from app.llm.client import TransientError

    svc = make_service(seeded_engine, lex, cat, stats, provider=FakeProvider(fail_with=TransientError("503")))
    sid, _ = svc.start()
    t = svc.message(sid, "we do things for customers")
    assert t.status == "asking" and t.buttons


def test_llm_explanations_pass_through_the_guard(seeded_engine, lex, cat, stats):
    def respond(model, payload):
        if payload["task"] == "explain":
            return {f"{r['product_id']}:{r['code']}": ("Only 999 rupees!" if r["product_id"] == "P02"
                                                       else "A sensible fit for offices like yours.")
                    for r in payload["reasons"]}
        return {}

    svc = make_service(seeded_engine, lex, cat, stats, provider=FakeProvider(respond), explain=True)
    sid, _ = svc.start("en")
    for a in ["__set:segment=prof", "__set:city_tier=1", "__set:employees=12", "__set:sites=1",
              "__set:has_gstin=false", "__need:none"]:
        svc.message(sid, a)
    rec = svc.confirm(sid, {})
    assert rec["explanation_fallbacks"] == ["P02:MOST_CHOSEN_IN_SEGMENT"]
    p02 = next(ln for ln in rec["lines"] if ln["product_id"] == "P02")
    assert "999" not in p02["reasons"][0]["text"]
    p16 = next(ln for ln in rec["lines"] if ln["product_id"] == "P16")
    assert p16["reasons"][0]["text"] == "A sensible fit for offices like yours."
