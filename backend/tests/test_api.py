from __future__ import annotations

from fastapi.testclient import TestClient


def test_app_boots_seeds_and_serves(tmp_path, monkeypatch):
    monkeypatch.setenv("UDYAM_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("UDYAM_CLOCK_MODE", "demo")
    from app.main import app

    with TestClient(app) as client:
        health = client.get("/api/health").json()
        assert health["status"] == "ok"
        assert health["business_as_of"] == "2026-07-15" and health["demo_clock"] is True
        assert health["seeded"] == {"products": 25, "gstin_registry": 3534,
                                    "udyam_registry": 2723, "historical_leads": 5000}
        cat = client.get("/api/catalogue").json()
        assert len(cat) == 25 and cat[0]["product_id"] == "P01"
        assert health["advisor"] == {"redteam_passed": True, "redteam_leaks": 0,
                                     "llm": "disabled: ADVISOR_MODE is scripted"}


def test_advisor_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("UDYAM_DB_PATH", str(tmp_path / "api2.db"))
    monkeypatch.delenv("ADVISOR_MODE", raising=False)
    from app.main import app

    with TestClient(app) as client:
        start = client.post("/api/advisor/sessions", json={"language": "en"}).json()
        sid = start["session_id"]
        assert start["expecting"] == "segment" and start["buttons"]
        t = client.post(f"/api/advisor/sessions/{sid}/messages",
                        json={"text": "We run a restaurant chain in Bangalore with 4 outlets and 40 staff"}).json()
        assert t["expecting"] == "has_gstin"
        client.post(f"/api/advisor/sessions/{sid}/messages", json={"text": "yes"})
        t = client.post(f"/api/advisor/sessions/{sid}/messages",
                        json={"text": "billing at each outlet, CCTV and manage all outlets centrally"}).json()
        assert t["status"] == "confirm"
        rec = client.post(f"/api/advisor/sessions/{sid}/confirm", json={"edits": {}}).json()
        ids = {ln["product_id"] for ln in rec["lines"]}
        # GSTIN not checked yet (no P2): SD-WAN is excluded with a reason, not silently dropped.
        assert "P10" not in ids and any(e["product_id"] == "P10" for e in rec["excluded"])
        assert {"P02", "P09", "P19", "P23", "P08"} <= ids
        assert client.post(f"/api/advisor/sessions/{sid}/end").json()["deleted"] is True
        assert client.post(f"/api/advisor/sessions/{sid}/messages", json={"text": "hi"}).status_code == 404
        assert client.post("/api/advisor/sessions", json={"language": "fr"}).status_code == 422


def test_quote_preview_accept_and_gstin_check(tmp_path, monkeypatch):
    monkeypatch.setenv("UDYAM_DB_PATH", str(tmp_path / "api3.db"))
    from app.main import app

    with TestClient(app) as client:
        opts = client.get("/api/advisor/options").json()
        assert {s["code"] for s in opts["segments"]} == {"micro", "prof", "multi", "mfg"} and len(opts["cities"]) == 22
        sid = client.post("/api/advisor/sessions", json={"language": "en"}).json()["session_id"]
        for a in ["__set:segment=micro", "__set:city_tier=2", "__set:employees=3", "__set:sites=1",
                  "__set:has_gstin=true", "__need:P19", "__need:none"]:
            client.post(f"/api/advisor/sessions/{sid}/messages", json={"text": a})
        # Preview before confirming the card is refused.
        assert client.post(f"/api/advisor/sessions/{sid}/quote", json={"items": []}).status_code == 422
        rec = client.post(f"/api/advisor/sessions/{sid}/confirm", json={"edits": {}}).json()
        items = [{"product_id": ln["product_id"], "quantity": ln["quantity"]} for ln in rec["lines"]]
        assert rec["addons"] and all(a["product_id"] not in {i["product_id"] for i in items} for a in rec["addons"])
        # WhatsApp API is locked until the GSTIN is checked (P2).
        prev = client.post(f"/api/advisor/sessions/{sid}/quote", json={"items": items + [{"product_id": "P15", "quantity": 1}]}).json()
        assert prev["rejected"][0]["codes"] == ["EXCL_GSTIN_UNKNOWN"]
        assert client.post(f"/api/advisor/sessions/{sid}/accept",
                           json={"items": items + [{"product_id": "P15", "quantity": 1}]}).status_code == 422
        # GSTIN check needs P2; then an Active GSTIN unlocks P15.
        assert client.post("/api/registry/gstin-check", json={"session_id": sid, "gstin": "27XUIXG0767D1ZP"}).status_code == 403
        client.post("/api/consents", json={"session_id": sid, "purpose": "P2", "decision": "given"})
        chk = client.post("/api/registry/gstin-check", json={"session_id": sid, "gstin": "27XUIXG0767D1ZP"}).json()
        assert chk["status"] == "active" and "•" in chk["gstin"] and chk["simulated"] is True
        prev = client.post(f"/api/advisor/sessions/{sid}/quote", json={"items": items + [{"product_id": "P15", "quantity": 1}]}).json()
        assert prev["rejected"] == [] and prev["quote"]["monthly_ex_tax"] == 2197 + 1249
        v1 = client.post(f"/api/advisor/sessions/{sid}/accept", json={"items": items}).json()
        assert v1["version"] == 1 and v1["quote"]["first_payment"] == 5542
        bad = client.post(f"/api/advisor/sessions/{sid}/quote", json={"items": [{"product_id": "P01", "quantity": 0}]})
        assert bad.status_code == 422
        assert client.post("/api/registry/gstin-check",
                           json={"session_id": sid, "gstin": "08YKZXS8189L1Z0"}).json()["status"] == "format_invalid"
