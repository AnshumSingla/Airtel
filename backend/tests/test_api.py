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
