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
