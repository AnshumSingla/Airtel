"""Real OCR on the specimen images. Three hard cases always run; set RUN_SLOW=1 for all 47."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from app.kyc.checks import evaluate
from app.kyc.ocr import MAX_BYTES, OcrRefused, decode
from app.kyc.pipeline import read_document
from app.kyc.registry import DbRegistry
from tests.test_kyc_checks import AFTER_CONFIRM, ANSWER_KEY

DOCS = Path(__file__).resolve().parents[2] / "data" / "raw" / "kyc_documents"
AS_OF = date(2026, 7, 15)


def read(name: str):
    kind = name.split("_", 1)[1]
    return read_document((DOCS / f"{name}.png").read_bytes(), kind)


def test_tilted_k02_gst_is_deskewed_and_read(seeded_engine):
    doc, quality = read("K02_gst_certificate")
    assert quality["deskewed"] and abs(quality["skew"] - 6.97) < 0.1
    assert doc.seen_type == "gst_certificate"
    assert doc.fields["trade_name"].replace(" ", "") == "HarmonyDentalCare"
    assert doc.fields["gstin"] in {"19E0GXH4115Y1ZL", "19EOGXH4115Y1ZL"}


def test_blurry_k04_gst_is_refused_before_ocr():
    doc, quality = read("K04_gst_certificate")
    assert doc.refused == "TOO_BLURRY" and quality["sharpness"] < 100


def test_k01_gst_reads_the_gstin_through_the_watermark():
    doc, _ = read("K01_gst_certificate")
    assert doc.fields["gstin"] == "37IHKXV5167L1ZS"


def test_input_limits():
    with pytest.raises(OcrRefused, match="FILE_TOO_LARGE"):
        decode(b"\x89PNG\r\n\x1a\n" + b"0" * MAX_BYTES)
    with pytest.raises(OcrRefused, match="UNSUPPORTED_TYPE"):
        decode(b"%PDF-1.7 not an image")
    with pytest.raises(OcrRefused, match="UNREADABLE_IMAGE"):
        decode(b"\x89PNG\r\n\x1a\n" + b"garbage")


@pytest.mark.skipif(os.environ.get("RUN_SLOW") != "1", reason="full 47-image OCR run takes ~2.5 min")
def test_full_pipeline_matches_answer_key(seeded_engine):
    reg = DbRegistry(seeded_engine)
    for applicant, (outcome, must_have) in ANSWER_KEY.items():
        docs = {}
        for path in sorted(DOCS.glob(f"{applicant}_*.png")):
            kind = path.stem.split("_", 1)[1]
            docs[kind], _ = read_document(path.read_bytes(), kind)
        res = evaluate(docs, reg, AS_OF)
        assert res.outcome == outcome, (applicant, res.codes())
        assert must_have <= set(res.codes()), (applicant, res.codes())
        if applicant in AFTER_CONFIRM:
            after = evaluate(docs, reg, AS_OF, confirmed={"gstin": res.repair_proposals[0]["candidate"]})
            assert after.outcome == AFTER_CONFIRM[applicant], (applicant, after.codes())
