"""POLICIES.md §13: session binding, CSRF, Origin, ownership via direct API calls, rate limits, headers, logs."""

from __future__ import annotations

import pytest

from app.security.logs import redact
from tests.conftest import make_client


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import os

    os.environ["UDYAM_DB_PATH"] = str(tmp_path_factory.mktemp("sec") / "sec.db")
    from app.main import app as fastapi_app

    return fastapi_app


def started(client):
    sid = client.post("/api/advisor/sessions", json={"language": "en"}).json()["session_id"]
    for a in ["__set:segment=prof", "__set:city_tier=1", "__set:employees=12", "__set:sites=1",
              "__set:has_gstin=true", "__need:none"]:
        client.post(f"/api/advisor/sessions/{sid}/messages", json={"text": a})
    return sid


def test_session_cookies(app):
    with make_client(app) as c:
        r = c.post("/api/advisor/sessions", json={"language": "en"})
        cookies = r.headers.get_list("set-cookie")
        sid_cookie = next(h for h in cookies if h.startswith("udyam_sid="))
        csrf_cookie = next(h for h in cookies if h.startswith("udyam_csrf="))
        assert "HttpOnly" in sid_cookie and "SameSite=lax" in sid_cookie and "Max-Age=86400" in sid_cookie
        assert "HttpOnly" not in csrf_cookie            # the page must read it to send the header
        assert "Secure" not in sid_cookie                # plain http locally


def test_cookies_are_secure_behind_https_proxy(app):
    with make_client(app) as c:
        r = c.post("/api/advisor/sessions", json={"language": "en"}, headers={"X-Forwarded-Proto": "https"})
        assert all("Secure" in h for h in r.headers.get_list("set-cookie"))


def test_csrf_token_is_required(app):
    with make_client(app) as c:
        sid = c.post("/api/advisor/sessions", json={"language": "en"}).json()["session_id"]
        c.event_hooks["request"].clear()                 # stop echoing the token
        assert c.post(f"/api/advisor/sessions/{sid}/messages", json={"text": "hi"}).status_code == 403
        bad = c.post(f"/api/advisor/sessions/{sid}/messages", json={"text": "hi"}, headers={"X-CSRF-Token": "guess"})
        assert bad.status_code == 403
        good = c.post(f"/api/advisor/sessions/{sid}/messages", json={"text": "hi"},
                      headers={"X-CSRF-Token": c.cookies.get("udyam_csrf")})
        assert good.status_code == 200


def test_foreign_origin_is_refused(app):
    with make_client(app) as c:
        sid = c.post("/api/advisor/sessions", json={"language": "en"}).json()["session_id"]
        evil = c.post(f"/api/advisor/sessions/{sid}/messages", json={"text": "hi"}, headers={"Origin": "https://evil.example"})
        assert evil.status_code == 403
        own = c.post(f"/api/advisor/sessions/{sid}/messages", json={"text": "hi"}, headers={"Origin": "http://testserver"})
        dev = c.post(f"/api/advisor/sessions/{sid}/messages", json={"text": "hi"}, headers={"Origin": "http://localhost:5173"})
        assert own.status_code == 200 and dev.status_code == 200
        # Starting a session from a foreign site is refused too (no CSRF token exists yet, so Origin is the guard).
        assert c.post("/api/advisor/sessions", json={"language": "en"}, headers={"Origin": "https://evil.example"}).status_code == 403


def test_another_browser_cannot_use_a_victims_ids(app):
    with make_client(app) as victim, make_client(app) as attacker:
        sid = started(victim)
        victim.post("/api/consents", json={"session_id": sid, "purpose": "P3", "decision": "given"})
        case = victim.post("/api/kyc/cases", json={"session_id": sid}).json()["case_id"]
        rec = victim.post(f"/api/advisor/sessions/{sid}/confirm", json={"edits": {}}).json()
        items = [{"product_id": ln["product_id"], "quantity": ln["quantity"]} for ln in rec["lines"]]
        v = victim.post(f"/api/advisor/sessions/{sid}/accept", json={"items": items}).json()["version"]
        order = victim.post("/api/orders", json={"session_id": sid, "quote_version": v}).json()["order_id"]

        started(attacker)                                # the attacker has a valid session and CSRF token of their own
        calls = [
            ("post", f"/api/advisor/sessions/{sid}/messages", {"json": {"text": "hi"}}),
            ("post", f"/api/advisor/sessions/{sid}/confirm", {"json": {"edits": {}}}),
            ("post", f"/api/advisor/sessions/{sid}/end", {}),
            ("post", "/api/consents", {"json": {"session_id": sid, "purpose": "P2", "decision": "given"}}),
            ("post", "/api/consents/withdraw", {"json": {"session_id": sid, "purpose": "P3"}}),
            ("post", "/api/kyc/cases", {"json": {"session_id": sid}}),
            ("post", f"/api/kyc/cases/{case}/submit", {"json": {}}),
            ("post", f"/api/kyc/cases/{case}/confirm-identifier", {"json": {"field": "gstin", "accept": True}}),
            ("get", f"/api/orders/{order}", {"params": {"session_id": sid}}),
            ("post", f"/api/orders/{order}/cancel", {"json": {"session_id": sid}}),
            ("post", "/api/registry/gstin-check", {"json": {"session_id": sid, "gstin": "27XUIXG0767D1ZP"}}),
        ]
        for method, url, kw in calls:
            r = getattr(attacker, method)(url, **kw)
            assert r.status_code == 404, (url, r.status_code, r.text)
        # The victim's order is untouched.
        assert victim.get(f"/api/orders/{order}", params={"session_id": sid}).json()["status"] == "ACCEPTED"


def test_security_headers(app):
    with make_client(app) as c:
        h = c.get("/api/health").headers
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in h["content-security-policy"] and h["cache-control"] == "no-store"
        assert "access-control-allow-origin" not in h      # CORS stays off


def test_rate_limit(app):
    limiter = app.state.rate_limiter
    saved = dict(limiter.limits)
    limiter.limits["start"] = (2, 60)
    limiter._hits.clear()            # earlier tests in this module used the same client IP
    try:
        with make_client(app) as c:
            codes = [c.post("/api/advisor/sessions", json={"language": "en"}).status_code for _ in range(3)]
            assert codes[:2] == [200, 200] and codes[2] == 429
            r = c.post("/api/advisor/sessions", json={"language": "en"})
            assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    finally:
        limiter.limits.update(saved)
        limiter._hits.clear()


def test_log_redaction():
    line = '127.0.0.1 - "POST /api/advisor/sessions/mjksY5TwMg11CXFkCcHqHEKaxvdTjQEJ/messages HTTP/1.1" 200'
    assert "mjksY5Tw" not in redact(line) and "/api/advisor/sessions/[id]/messages" in redact(line)
    assert "session_id=[redacted]" in redact("GET /api/orders/abc?session_id=secret-token-value HTTP/1.1")
    assert "37IHKXV5167L1ZS" not in redact("gst 37IHKXV5167L1ZS")
