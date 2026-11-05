"""Orders and tracker (POLICIES.md §10), including the mixed-order worked example."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import make_client

from app.orders.service import OrderService
from app.orders.states import IllegalTransition, check_line, check_order
from app.pricing.quote import build_quote


@pytest.fixture
def svc(seeded_engine, cat):
    return OrderService(seeded_engine, cat, reset=True)


def snapshot(cat, items, version=1):
    q = build_quote(cat, items)
    return {"version": version, "lines": [{"product_id": ln.product_id, "name": ln.name, "quantity": ln.quantity,
                                           "install_days": ln.install_days} for ln in q.lines],
            "quote": {"monthly_ex_tax": q.monthly_ex_tax, "monthly_incl_tax": q.monthly_incl_tax}}


def status(view):
    return view["status"], view["hold_reason"]


def lines(view):
    return {ln["product_id"]: ln["status"] for ln in view["lines"]}


def test_illegal_transitions_are_rejected():
    with pytest.raises(IllegalTransition):
        check_order("ACCEPTED", "COMPLETED", "system")
    with pytest.raises(IllegalTransition):
        check_order("KYC_PENDING", "KYC_OK", "owner")      # owners can't pass their own KYC
    with pytest.raises(IllegalTransition):
        check_line("PENDING", "INSTALLING", "system")
    with pytest.raises(IllegalTransition):
        check_line("ACTIVE", "CANCELLED", "owner")


def test_happy_path_with_simulated_fulfilment(svc, cat):
    o = svc.create("s1", snapshot(cat, [("P02", 1), ("P16", 7), ("P23", 2)]), "en")
    assert status(o) == ("ACCEPTED", None)
    o = svc.submit_kyc(o["order_id"], "case", "checks_passed", {"P02": [], "P16": [], "P23": []})
    assert status(o) == ("IN_FULFILMENT", None)
    assert lines(o) == {"P02": "FEASIBILITY_CHECK", "P16": "ACTIVE", "P23": "SCHEDULED"}   # email has no site visit
    o = svc.advance(o["order_id"], 1)
    assert lines(o)["P02"] == "SCHEDULED"
    p02 = next(ln for ln in o["lines"] if ln["product_id"] == "P02")
    assert p02["eta_day"] == 5 and p02["days_left"] == 4
    o = svc.advance(o["order_id"], 4)
    assert status(o) == ("COMPLETED", None) and set(lines(o).values()) == {"ACTIVE"}
    assert all(m["label"] == "Simulated message, not sent" for m in o["messages"])
    assert o["labels"]["eta"].startswith("indicative")


def test_mixed_order_worked_example(svc, cat):
    """POLICIES.md §10: GSTIN Cancelled, Udyam valid -> P15 excluded, owner continues without it."""
    o = svc.create("s2", snapshot(cat, [("P02", 1), ("P16", 7), ("P15", 1)]), "en")
    assert o["quote"]["monthly_ex_tax"] == 3864 and o["quote"]["monthly_incl_tax"] == 4560
    o = svc.submit_kyc(o["order_id"], "case", "checks_passed",
                       {"P02": [], "P16": [], "P15": ["EXCL_GSTIN_INACTIVE"]})
    assert status(o) == ("ON_HOLD", "BUNDLE_CHANGE_NEEDED")
    assert lines(o) == {"P02": "PENDING", "P16": "PENDING", "P15": "EXCLUDED"}
    v2 = snapshot(cat, [("P02", 1), ("P16", 7)], version=2)
    assert v2["quote"]["monthly_ex_tax"] == 2615 and v2["quote"]["monthly_incl_tax"] == 3086
    o = svc.continue_without_excluded(o["order_id"], v2)
    assert status(o) == ("IN_FULFILMENT", None) and o["quote_version"] == 2
    assert lines(o) == {"P02": "FEASIBILITY_CHECK", "P16": "ACTIVE", "P15": "EXCLUDED"}
    assert any(e["trigger"].startswith("accepted quote v2") for e in o["events"])


def test_continue_must_keep_every_eligible_line(svc, cat):
    o = svc.create("s3", snapshot(cat, [("P02", 1), ("P16", 7), ("P15", 1)]), "en")
    svc.submit_kyc(o["order_id"], "c", "checks_passed", {"P15": ["EXCL_GSTIN_INACTIVE"]})
    with pytest.raises(ValueError):
        svc.continue_without_excluded(o["order_id"], snapshot(cat, [("P02", 1)], version=2))


def test_kyc_hold_then_resubmit(svc, cat):
    o = svc.create("s4", snapshot(cat, [("P01", 1), ("P07", 1)]), "hi")
    o = svc.submit_kyc(o["order_id"], "c", "owner_action_needed", {})
    assert status(o) == ("ON_HOLD", "KYC_ACTION")
    assert o["messages"][-1]["text"].startswith("आपके दस्तावेज़ों")       # Hindi messages
    o = svc.submit_kyc(o["order_id"], "c", "checks_passed", {"P01": [], "P07": []})
    assert status(o) == ("IN_FULFILMENT", None) and lines(o)["P07"] == "ACTIVE"


def test_review_hold_blocks_owner_resubmit_of_other_holds(svc, cat):
    o = svc.create("s5", snapshot(cat, [("P02", 1), ("P15", 1)]), "en")
    svc.submit_kyc(o["order_id"], "c", "checks_passed", {"P15": ["EXCL_GSTIN_INACTIVE"]})
    with pytest.raises(IllegalTransition):
        svc.submit_kyc(o["order_id"], "c", "checks_passed", {})   # bundle change pending, not documents


def test_feasibility_failure_with_substitute(svc, cat):
    o = svc.create("s6", snapshot(cat, [("P02", 1), ("P23", 2)]), "en")
    oid = o["order_id"]
    svc.submit_kyc(oid, "c", "checks_passed", {})
    svc.force_feasibility_fail(oid, "P02")
    o = svc.advance(oid, 1)
    assert status(o) == ("ON_HOLD", "FEASIBILITY_DECISION")
    assert o["substitute_offer"]["substitute"] == "P04" and lines(o)["P02"] == "FEASIBILITY_FAILED"
    o = svc.feasibility_decision(oid, True, snapshot(cat, [("P23", 2), ("P04", 1)], version=2))
    assert status(o) == ("IN_FULFILMENT", None) and o["quote_version"] == 2
    assert lines(o) == {"P02": "CANCELLED", "P23": "SCHEDULED", "P04": "FEASIBILITY_CHECK"}
    o = svc.advance(oid, 5)
    assert status(o) == ("COMPLETED", None)


def test_feasibility_failure_declined_cancels_dependent_lines(svc, cat):
    o = svc.create("s7", snapshot(cat, [("P02", 1), ("P23", 2), ("P07", 1)]), "en")
    oid = o["order_id"]
    svc.submit_kyc(oid, "c", "checks_passed", {})
    svc.force_feasibility_fail(oid, "P02")
    svc.advance(oid, 1)
    o = svc.feasibility_decision(oid, False, None)
    assert lines(o) == {"P02": "CANCELLED", "P23": "CANCELLED", "P07": "ACTIVE"}
    assert next(ln for ln in o["lines"] if ln["product_id"] == "P23")["reason"] == "DEP_LOST"
    assert status(o) == ("COMPLETED", None)


def test_reschedule_and_cancel(svc, cat):
    o = svc.create("s8", snapshot(cat, [("P19", 1), ("P07", 1)]), "en")
    oid = o["order_id"]
    svc.submit_kyc(oid, "c", "checks_passed", {})
    before = next(ln for ln in svc.view(oid)["lines"] if ln["product_id"] == "P19")["eta_day"]
    o = svc.reschedule(oid, "P19")
    assert next(ln for ln in o["lines"] if ln["product_id"] == "P19")["eta_day"] == before + 2
    o = svc.cancel(oid)
    assert status(o) == ("CANCELLED", None) and lines(o) == {"P19": "CANCELLED", "P07": "ACTIVE"}


def test_idempotency(svc, cat):
    calls = []
    first = svc.idempotent("k1", "cmd", lambda: calls.append(1) or {"n": len(calls)})
    again = svc.idempotent("k1", "cmd", lambda: calls.append(1) or {"n": len(calls)})
    assert first == again == {"n": 1} and calls == [1]
    with pytest.raises(ValueError):
        svc.idempotent("k1", "other", lambda: {})


DOCS = Path(__file__).resolve().parents[2] / "data" / "raw" / "kyc_documents"


def test_order_journey_over_http_with_real_kyc(tmp_path, monkeypatch):
    monkeypatch.setenv("UDYAM_DB_PATH", str(tmp_path / "orders.db"))
    from app.main import app

    with make_client(app) as c:
        sid = c.post("/api/advisor/sessions", json={"language": "en"}).json()["session_id"]
        for a in ["__set:segment=prof", "__set:city_tier=1", "__set:employees=12", "__set:sites=1",
                  "__set:has_gstin=true", "__need:none"]:
            c.post(f"/api/advisor/sessions/{sid}/messages", json={"text": a})
        rec = c.post(f"/api/advisor/sessions/{sid}/confirm", json={"edits": {}}).json()
        items = [{"product_id": ln["product_id"], "quantity": ln["quantity"]} for ln in rec["lines"]]
        v = c.post(f"/api/advisor/sessions/{sid}/accept", json={"items": items}).json()["version"]
        h = {"Idempotency-Key": "create-1"}
        o1 = c.post("/api/orders", json={"session_id": sid, "quote_version": v}, headers=h).json()
        o2 = c.post("/api/orders", json={"session_id": sid, "quote_version": v}, headers=h).json()
        assert o1["order_id"] == o2["order_id"]                       # retried tap: one order
        oid = o1["order_id"]
        assert c.get(f"/api/orders/{oid}", params={"session_id": "someone-else"}).status_code == 404
        # End and delete is refused while the order is open.
        assert c.post(f"/api/advisor/sessions/{sid}/end").status_code == 409
        c.post("/api/consents", json={"session_id": sid, "purpose": "P3", "decision": "given"})
        case = c.post("/api/kyc/cases", json={"session_id": sid}).json()["case_id"]
        for path in sorted(DOCS.glob("K03_*.png")):
            c.post(f"/api/kyc/cases/{case}/documents", data={"doc_type": path.stem.split("_", 1)[1]},
                   files={"file": (path.name, path.read_bytes(), "image/png")})
        o = c.post(f"/api/orders/{oid}/submit-kyc", json={"session_id": sid, "case_id": case}).json()
        assert o["status"] == "IN_FULFILMENT"
        o = c.post(f"/api/demo/orders/{oid}/advance", json={"session_id": sid, "days": 6}).json()
        assert o["status"] == "COMPLETED"
        assert c.post(f"/api/orders/{oid}/cancel", json={"session_id": sid}).status_code == 409
        assert c.post(f"/api/advisor/sessions/{sid}/end").json()["deleted"] is True


def test_demo_specimens_are_served_only_by_safe_name(tmp_path, monkeypatch):
    monkeypatch.setenv("UDYAM_DB_PATH", str(tmp_path / "spec.db"))
    from app.main import app

    with make_client(app) as c:
        sets = c.get("/api/demo/specimens").json()["sets"]
        assert len(sets) == 12 and "udyam_certificate" not in sets["K05"]
        assert c.get("/api/demo/specimens/K03_gst_certificate").content[:4] == b"\x89PNG"
        assert c.get("/api/demo/specimens/..%2F..%2Fsmb_leads").status_code == 404
        assert c.get("/api/demo/specimens/K03_passport").status_code == 404
