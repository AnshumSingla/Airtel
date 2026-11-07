"""KYC over HTTP with real OCR: consent gate, encryption at rest, masking, repairs, deletion."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import make_client
from sqlalchemy import create_engine, text

from app.privacy.crypto import FieldCipher

DOCS = Path(__file__).resolve().parents[2] / "data" / "raw" / "kyc_documents"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os

    db = tmp_path_factory.mktemp("kycapi") / "api.db"
    os.environ["UDYAM_DB_PATH"] = str(db)
    os.environ.pop("KYC_FIELD_KEYS", None)
    from app.main import app

    with make_client(app) as c:
        c.db_path = db
        yield c
    os.environ.pop("UDYAM_DB_PATH", None)


def new_session(client, consent_p3=True):
    sid = client.post("/api/advisor/sessions", json={"language": "en"}).json()["session_id"]
    for a in ["__set:segment=prof", "__set:city_tier=2", "__set:employees=12", "__set:sites=1",
              "__set:has_gstin=true", "__need:none"]:
        client.post(f"/api/advisor/sessions/{sid}/messages", json={"text": a})
    if consent_p3:
        client.post("/api/consents", json={"session_id": sid, "purpose": "P3", "decision": "given"})
    return sid


def upload_all(client, case_id, applicant):
    for path in sorted(DOCS.glob(f"{applicant}_*.png")):
        kind = path.stem.split("_", 1)[1]
        r = client.post(f"/api/kyc/cases/{case_id}/documents", data={"doc_type": kind},
                        files={"file": (path.name, path.read_bytes(), "image/png")})
        assert r.status_code == 200, r.text
        yield kind, r.json()


def test_kyc_needs_p3_consent(client):
    sid = new_session(client, consent_p3=False)
    assert client.post("/api/kyc/cases", json={"session_id": sid}).status_code == 403


def test_k02_full_flow_with_owner_confirmation_masking_and_encryption(client):
    sid = new_session(client)
    case = client.post("/api/kyc/cases", json={"session_id": sid}).json()["case_id"]
    uploads = dict(upload_all(client, case, "K02"))
    assert uploads["gst_certificate"]["quality"]["deskewed"] is True
    assert "•" in uploads["gst_certificate"]["fields"]["gstin"]          # masked in the response
    res = client.post(f"/api/kyc/cases/{case}/submit", json={"product_ids": ["P02", "P15"]}).json()
    assert res["outcome"] == "owner_action_needed" and res["label"].startswith("Automated checks")
    assert res["confirm"] == [{"field": "gstin", "doc": "gst_certificate", "reading": "19EOGXH4115Y1ZL"}]
    # Before confirmation the GSTIN is provisionally used, so the WhatsApp API line is eligible.
    assert all(ln["eligible"] for ln in res["lines"])
    after = client.post(f"/api/kyc/cases/{case}/confirm-identifier", json={"field": "gstin", "accept": True}).json()
    assert after["outcome"] == "checks_passed" and after["confirm"] == []
    # Encryption at rest: neither the GSTIN nor the trade name appears in the database file.
    raw = Path(client.db_path).read_bytes()
    assert b"19EOGXH4115Y1ZL" not in raw and b"19E0GXH4115Y1ZL" not in raw and b"Harmony" not in raw


def test_disputed_reading_goes_to_review(client):
    sid = new_session(client)
    case = client.post("/api/kyc/cases", json={"session_id": sid}).json()["case_id"]
    list(upload_all(client, case, "K08"))
    client.post(f"/api/kyc/cases/{case}/submit", json={})
    res = client.post(f"/api/kyc/cases/{case}/confirm-identifier", json={"field": "gstin", "accept": False}).json()
    assert res["outcome"] == "manual_review"
    assert any(f["code"] == "REPAIR_DISPUTED" for f in res["findings"])


def test_k01_cancelled_gstin_excludes_gstin_only_lines(client):
    sid = new_session(client)
    case = client.post("/api/kyc/cases", json={"session_id": sid}).json()["case_id"]
    list(upload_all(client, case, "K01"))
    res = client.post(f"/api/kyc/cases/{case}/submit", json={"product_ids": ["P02", "P16", "P15"]}).json()
    assert res["outcome"] == "owner_action_needed" and res["gstin_status"] == "inactive"
    assert {f["code"] for f in res["findings"]} >= {"GSTIN_INACTIVE", "NO_VALID_BUSINESS_PROOF"}
    lines = {ln["product_id"]: ln for ln in res["lines"]}
    assert lines["P15"]["codes"] == ["EXCL_GSTIN_INACTIVE"] and lines["P02"]["eligible"]


def test_upload_limits(client):
    sid = new_session(client)
    case = client.post("/api/kyc/cases", json={"session_id": sid}).json()["case_id"]
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (8 * 1024 * 1024)
    assert client.post(f"/api/kyc/cases/{case}/documents", data={"doc_type": "gst_certificate"},
                       files={"file": ("x.png", big, "image/png")}).status_code == 413
    assert client.post(f"/api/kyc/cases/{case}/documents", data={"doc_type": "gst_certificate"},
                       files={"file": ("x.pdf", b"%PDF-1.7", "application/pdf")}).status_code == 415
    assert client.post(f"/api/kyc/cases/{case}/documents", data={"doc_type": "passport"},
                       files={"file": ("x.png", (DOCS / "K03_signatory_id.png").read_bytes(), "image/png")}
                       ).status_code == 422


def test_p3_withdrawal_deletes_kyc_data_and_end_unlinks_consent(client):
    sid = new_session(client)
    case = client.post("/api/kyc/cases", json={"session_id": sid}).json()["case_id"]
    list(upload_all(client, case, "K03"))
    w = client.post("/api/consents/withdraw", json={"session_id": sid, "purpose": "P3"}).json()
    assert "kyc_cases_deleted=1" in w["effects"]
    assert client.post(f"/api/kyc/cases/{case}/submit", json={}).status_code in (403, 404)
    end = client.post(f"/api/advisor/sessions/{sid}/end").json()
    assert end["deleted"] is True and end["consent_events_unlinked"] >= 2
    eng = create_engine(f"sqlite:///{Path(client.db_path).as_posix()}")
    with eng.connect() as conn:
        assert conn.execute(text("select count(*) from consent_events where link = :s"), {"s": sid}).scalar() == 0
        assert conn.execute(text("select count(*) from kyc_cases where session_id = :s"), {"s": sid}).scalar() == 0
    eng.dispose()


def test_cipher_restart_rotation_and_lost_key():
    from cryptography.fernet import Fernet

    k1, k2 = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    token = FieldCipher(keys=[k1]).encrypt({"gstin": "37IHKXV5167L1ZS"})
    assert "37IHKXV5167L1ZS" not in token
    assert FieldCipher(keys=[k1]).decrypt(token) == {"gstin": "37IHKXV5167L1ZS"}   # same key after a restart
    rotated = FieldCipher(keys=[k2, k1]).rotate(token)                             # new key first, re-encrypt
    assert FieldCipher(keys=[k2]).decrypt(rotated)["gstin"] == "37IHKXV5167L1ZS"   # old key removable
    with pytest.raises(ValueError):
        FieldCipher(keys=[k2]).decrypt(token)                                       # lost key: unrecoverable
    assert FieldCipher(keys=[]).ephemeral and not FieldCipher(keys=[k1]).ephemeral
