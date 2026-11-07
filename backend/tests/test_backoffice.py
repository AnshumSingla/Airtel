"""Back office (POLICIES.md §11, §13): roles and scope tested with direct API calls."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import update

from app.backoffice.accounts import staff_sessions
from tests.conftest import make_client

DOCS = Path(__file__).resolve().parents[2] / "data" / "raw" / "kyc_documents"
PASSWORDS = {u: f"pw-{u}-test" for u in ("sales1", "partner_sharma", "partner_metro", "reviewer1", "admin1")}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import os

    os.environ["UDYAM_DB_PATH"] = str(tmp_path_factory.mktemp("bo") / "bo.db")
    for u, pw in PASSWORDS.items():
        os.environ[f"STAFF_PASSWORD_{u.upper()}"] = pw
    from app.main import app as fastapi_app

    yield fastapi_app
    for u in PASSWORDS:
        os.environ.pop(f"STAFF_PASSWORD_{u.upper()}", None)


@pytest.fixture(scope="module")
def server(app):
    """One app lifespan for the module; each test opens its own browsers (clients) against it."""
    with make_client(app) as c:
        yield c


def owner(app, ref=None, p5_team=None, segment="prof"):
    # No "with": entering a client re-runs start-up, which resets the demo database for everyone.
    c = make_client(app)
    body = {"language": "en", **({"ref": ref} if ref else {})}
    sid = c.post("/api/advisor/sessions", json=body).json()["session_id"]
    for a in [f"__set:segment={segment}", "__set:city_tier=1", "__set:employees=12", "__set:sites=1",
              "__set:has_gstin=true", "__need:none"]:
        c.post(f"/api/advisor/sessions/{sid}/messages", json={"text": a})
    if p5_team:
        assert c.post("/api/consents", json={"session_id": sid, "purpose": "P5", "decision": "given",
                                             "team": p5_team}).status_code == 200
    return c, sid


def staff(app, username):
    c = make_client(app)
    r = c.post("/api/bo/login", json={"username": username, "password": PASSWORDS[username]})
    assert r.status_code == 200, r.text
    return c


def test_login_cookies_and_lockout(server, app):
    c = make_client(app)
    if True:
        r = c.post("/api/bo/login", json={"username": "sales1", "password": PASSWORDS["sales1"]})
        cookies = r.headers.get_list("set-cookie")
        staff_cookie = next(h for h in cookies if h.startswith("udyam_staff="))
        assert "HttpOnly" in staff_cookie and "SameSite=strict" in staff_cookie and "Path=/api/bo" in staff_cookie
        assert c.get("/api/bo/me").json()["role"] == "sales_agent"
        c.post("/api/bo/logout")
        assert c.get("/api/bo/me").status_code == 401
    c = make_client(app)
    if True:
        for _ in range(5):
            assert c.post("/api/bo/login", json={"username": "admin1", "password": "wrong"}).status_code == 401
        # Locked now, even with the right password.
        assert c.post("/api/bo/login", json={"username": "admin1", "password": PASSWORDS["admin1"]}).status_code == 423
    app.state.staff._failures.clear()
    assert make_client(app).post("/api/bo/login", json={"username": "nobody", "password": "x"}).status_code == 401


def test_owner_cookies_never_open_the_back_office(server, app):
    c, _ = owner(app)
    for path in ("/api/bo/me", "/api/bo/queue", "/api/bo/kyc/review", "/api/bo/audit", "/api/bo/callbacks"):
        assert c.get(path).status_code == 401


def test_staff_csrf_is_required(server, app):
    c = staff(app, "sales1")
    c.event_hooks["request"].clear()
    assert c.post("/api/bo/logout").status_code == 403
    assert c.post("/api/bo/logout", headers={"X-CSRF-Token": c.cookies.get("udyam_staff_csrf")}).status_code == 200


def test_partner_scope_referral_is_credit_not_access(server, app):
    a, sid_a = owner(app, p5_team="P-SHARMA")        # shared with Sharma Telecom
    b, sid_b = owner(app, ref="metro")               # referred by Metro, no P5 at all
    sharma, metro, sales = staff(app, "partner_sharma"), staff(app, "partner_metro"), staff(app, "sales1")
    assert {lead["session_id"] for lead in sharma.get("/api/bo/queue").json()} == {sid_a}
    assert metro.get("/api/bo/queue").json() == []                    # referral code gives no access
    assert sid_a not in {lead["session_id"] for lead in sales.get("/api/bo/queue").json()}   # not shared with sales
    assert metro.post(f"/api/bo/leads/{sid_a}/claim").status_code == 404
    assert metro.post(f"/api/bo/leads/{sid_b}/notes", json={"text": "hi"}).status_code == 404
    counts = metro.get("/api/bo/referrals").json()
    assert counts["sessions_started"] == "fewer than 5"               # never a count that singles someone out
    lead = sharma.post(f"/api/bo/leads/{sid_a}/claim").json()
    assert lead["claimed_by"] == "partner_sharma"
    assert "chat" not in str(lead).lower() and "history" not in lead   # summary card only
    lead = sharma.post(f"/api/bo/leads/{sid_a}/notes", json={"text": "Called, will try tomorrow"}).json()
    assert lead["notes"][0]["text"].startswith("Called")
    # P5 withdrawal: the lead leaves Sharma's queue and their notes are deleted.
    a.post("/api/consents/withdraw", json={"session_id": sid_a, "purpose": "P5", "team": "P-SHARMA"})
    assert sharma.get("/api/bo/queue").json() == []
    assert sharma.post(f"/api/bo/leads/{sid_a}/claim").status_code == 404


def test_role_matrix(server, app):
    sharma, sales, reviewer, admin = (staff(app, u) for u in ("partner_sharma", "sales1", "reviewer1", "admin1"))
    assert sharma.get("/api/bo/kyc/review").status_code == 403
    assert sharma.get("/api/bo/callbacks").status_code == 403
    assert sales.post("/api/bo/kyc/cases/whatever/decision", json={"approve": True, "reason": "ok ok"}).status_code == 403
    assert sales.get("/api/bo/audit").status_code == 403
    assert reviewer.get("/api/bo/queue").status_code == 403
    assert reviewer.post("/api/bo/admin/retention").status_code == 403
    assert admin.get("/api/bo/queue").status_code == 403
    assert admin.post("/api/bo/admin/retention").status_code == 200
    assert sales.get("/api/bo/referrals").status_code == 403


def test_callback_list(server, app):
    data = staff(app, "sales1").get("/api/bo/callbacks").json()
    leads = data["leads"]
    assert data["total"] > 100 and len(leads) == 25 and "revenue not margin" in data["label"]
    values = [x["expected_monthly_revenue"] for x in leads]
    assert values == sorted(values, reverse=True)
    assert all(x["gstin"] is None or "•" in x["gstin"] for x in leads)
    assert all(x["why"] for x in leads)


def test_reviewer_flow_with_real_k07_documents(server, app):
    c, sid = owner(app)
    rec = c.post(f"/api/advisor/sessions/{sid}/confirm", json={"edits": {}}).json()
    items = [{"product_id": ln["product_id"], "quantity": ln["quantity"]} for ln in rec["lines"]]
    v = c.post(f"/api/advisor/sessions/{sid}/accept", json={"items": items}).json()["version"]
    oid = c.post("/api/orders", json={"session_id": sid, "quote_version": v}).json()["order_id"]
    c.post("/api/consents", json={"session_id": sid, "purpose": "P3", "decision": "given"})
    case = c.post("/api/kyc/cases", json={"session_id": sid}).json()["case_id"]
    for path in sorted(DOCS.glob("K07_*.png")):
        c.post(f"/api/kyc/cases/{case}/documents", data={"doc_type": path.stem.split("_", 1)[1]},
               files={"file": (path.name, path.read_bytes(), "image/png")})
    o = c.post(f"/api/orders/{oid}/submit-kyc", json={"session_id": sid, "case_id": case}).json()
    assert (o["status"], o["hold_reason"]) == ("ON_HOLD", "KYC_REVIEW")

    reviewer = staff(app, "reviewer1")
    assert case in {x["case_id"] for x in reviewer.get("/api/bo/kyc/review").json()}
    full = reviewer.get(f"/api/bo/kyc/cases/{case}").json()
    assert full["fields"]["gst_certificate"]["gstin"] == "07CPCXN0398P1ZT"        # unmasked for the reviewer only
    assert "GST_NAME_MISMATCH" in {f["code"] for f in full["findings"]}
    assert reviewer.post(f"/api/bo/kyc/cases/{case}/decision", json={"approve": True, "reason": ""}).status_code == 422
    d = reviewer.post(f"/api/bo/kyc/cases/{case}/decision",
                      json={"approve": True, "reason": "Trade name matches registry; legal name typo"}).json()
    assert d["outcome"] == "checks_passed" and d["orders_moved"] == 1
    o = c.get(f"/api/orders/{oid}", params={"session_id": sid}).json()
    assert o["status"] == "IN_FULFILMENT"
    assert any(e["actor"] == "kyc_reviewer" for e in o["events"])
    assert case not in {x["case_id"] for x in reviewer.get("/api/bo/kyc/review").json()}

    log = staff(app, "admin1").get("/api/bo/audit").json()
    actions = {(e["actor"], e["action"]) for e in log}
    assert ("reviewer1", "view_full_identifiers") in actions and ("reviewer1", "kyc_decision") in actions
    assert all("07CPCXN0398P1ZT" not in str(e) for e in log)                        # audit log stays masked


def test_staff_idle_expiry(server, app):
    c = staff(app, "sales1")
    from datetime import datetime, timezone

    with app.state.engine.begin() as conn:
        conn.execute(update(staff_sessions).values(last_seen=datetime.now(timezone.utc) - timedelta(minutes=31)))
    assert c.get("/api/bo/me").status_code == 401
