"""KYC checks against the drafted answer key (evidence/ocr_spike/answer_key_draft.md).

Fast tests use the OCR spike output (evidence/ocr_spike/results.json, gated mode)
so the check logic is exercised on what OCR really produced. The full pipeline
on all 47 images runs in test_kyc_pipeline.py (set RUN_SLOW=1).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.kyc.checks import DocInput, evaluate
from app.kyc.extract import A4_LABELS, CARD_LABELS
from app.kyc.registry import DbRegistry
from app.kyc.text import clean_value

AS_OF = date(2026, 7, 15)
RESULTS = Path(__file__).resolve().parents[2] / "evidence" / "ocr_spike" / "results.json"

ANSWER_KEY = {
    "K01": ("owner_action_needed", {"GSTIN_INACTIVE", "UDYAM_NUMBER_MISSING", "NO_VALID_BUSINESS_PROOF"}),
    "K02": ("owner_action_needed", {"GSTIN_CONFIRM_READING"}),
    "K03": ("checks_passed", set()),
    "K04": ("owner_action_needed", {"DOC_TOO_BLURRY"}),
    "K05": ("owner_action_needed", {"UDYAM_REGISTERED_NOT_UPLOADED"}),
    "K06": ("manual_review", {"GSTIN_PRINTED_INVALID"}),
    "K07": ("manual_review", {"GST_NAME_MISMATCH"}),
    "K08": ("owner_action_needed", {"GSTIN_CONFIRM_READING"}),
    "K09": ("checks_passed", set()),
    "K10": ("checks_passed", set()),
    "K11": ("owner_action_needed", {"ADDRESS_PROOF_STALE"}),
    "K12": ("checks_passed", set()),
}
# Owner confirms the proposed GSTIN reading -> outcome after confirmation.
AFTER_CONFIRM = {"K02": "checks_passed", "K08": "checks_passed"}


def spike_docs() -> dict[str, dict[str, DocInput]]:
    label_maps = {**{k: v for k, v in A4_LABELS.items()}, "signatory_id": CARD_LABELS}
    out: dict[str, dict[str, DocInput]] = {}
    for r in json.loads(RESULTS.read_text(encoding="utf-8")):
        if r["mode"] != "gated":
            continue
        mapping = label_maps[r["type"]]
        fields = {mapping[k]: clean_value(v) for k, v in r["fields"].items() if k in mapping}
        out.setdefault(r["applicant"], {})[r["type"]] = DocInput(fields, r["quality"].get("refused"))
    return out


@pytest.fixture(scope="module")
def reg(seeded_engine):
    return DbRegistry(seeded_engine)


@pytest.fixture(scope="module")
def docs():
    return spike_docs()


@pytest.mark.parametrize("applicant", sorted(ANSWER_KEY))
def test_answer_key(applicant, docs, reg):
    outcome, must_have = ANSWER_KEY[applicant]
    res = evaluate(docs[applicant], reg, AS_OF)
    assert res.outcome == outcome, res.codes()
    assert must_have <= set(res.codes()), res.codes()
    # Nothing beyond the expected action/review findings (notes are fine).
    unexpected = {f.code for f in res.findings if f.level != "note"} - must_have
    assert unexpected == set(), unexpected


@pytest.mark.parametrize("applicant", sorted(AFTER_CONFIRM))
def test_confirmed_repairs(applicant, docs, reg):
    res = evaluate(docs[applicant], reg, AS_OF)
    [proposal] = res.repair_proposals
    after = evaluate(docs[applicant], reg, AS_OF, confirmed={"gstin": proposal["candidate"]})
    assert after.outcome == AFTER_CONFIRM[applicant], after.codes()
    assert after.gstin == proposal["candidate"] and after.business_proof == "gst"


def test_no_false_accepts(docs, reg):
    """Every applicant with a planted problem must not reach checks_passed (before confirmations)."""
    clean = {a for a, (o, _) in ANSWER_KEY.items() if o == "checks_passed"}
    passed = {a for a in docs if evaluate(docs[a], reg, AS_OF).outcome == "checks_passed"}
    assert passed == clean


def test_k01_lines_and_status(docs, reg):
    res = evaluate(docs["K01"], reg, AS_OF)
    assert res.gstin_status == "inactive" and res.business_proof is None


def test_freshness_uses_the_injected_date(docs, reg):
    """K11's bill (2025-10-31) is fresh if business_as_of were 2025-12-01."""
    res = evaluate(docs["K11"], reg, date(2025, 12, 1))
    assert "ADDRESS_PROOF_STALE" not in res.codes()


def test_missing_documents(reg):
    res = evaluate({}, reg, AS_OF)
    assert res.outcome == "owner_action_needed"
    assert {"DOC_MISSING", "NO_VALID_BUSINESS_PROOF"} <= set(res.codes())


def test_wrong_document_in_slot(docs, reg):
    d = dict(docs["K03"])
    d["address_proof"] = DocInput(d["address_proof"].fields, seen_type="signatory_id")
    assert "DOC_WRONG_TYPE" in evaluate(d, reg, AS_OF).codes()
