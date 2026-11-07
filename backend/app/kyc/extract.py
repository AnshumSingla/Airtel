"""Turn OCR boxes into named fields per document type (layouts from the specimen pack)."""

from __future__ import annotations

import re

from app.kyc.ocr import Box
from app.kyc.text import clean_value, is_watermark_fragment

DOC_TYPES = ("gst_certificate", "udyam_certificate", "address_proof", "signatory_id")

TITLES = {
    "gst_certificate": "GSTREGISTRATIONCERTIFICATE",
    "udyam_certificate": "UDYAMREGISTRATIONCERTIFICATE",
    "address_proof": "ELECTRICITYBILL",
    "signatory_id": "AUTHORISEDSIGNATORYID",
}

A4_LABELS = {
    "gst_certificate": {"GSTIN": "gstin", "Legal name": "legal_name", "Trade name": "trade_name",
                        "Constitution": "constitution", "Address of principal": "address",
                        "Date of liability": "date_of_liability", "Type of registration": "registration_type"},
    "udyam_certificate": {"Udyam reg. number": "udyam_number", "Enterprise name": "enterprise_name",
                          "Major activity": "major_activity", "City": "city", "State": "state",
                          "Date of registration": "date_of_registration"},
    "address_proof": {"Consumer no.": "consumer_no", "Billed to": "billed_to", "Supply address": "address",
                      "Bill date": "bill_date", "Units consumed": "units", "Amount due (INR)": "amount_due"},
}
CARD_LABELS = {"Name": "name", "Designation": "designation", "For business": "for_business",
               "ID no.": "id_no", "Valid till": "valid_till"}
LABEL_CONTINUATIONS = {"PLACEOFBUSINESS"}
VALUE_X = 480


def squash(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", s).upper()


def is_noise(text: str) -> bool:
    t = squash(text)
    if not t or "SPECIMEN" in t or t.startswith(("ACCELYTL", "FORMATFOR", "FICTIONAL")):
        return True
    return is_watermark_fragment(text)


def detect_type(boxes: list[Box]) -> str | None:
    head = squash(" ".join(b.text for b in sorted(boxes, key=lambda b: b.y)[:4]))
    for kind, title in TITLES.items():
        if title in head:
            return kind
    return None


def _join(parts: list[str]) -> str:
    out = ""
    for p in parts:
        p = p.strip()
        if not out:
            out = p
        elif p[:1].islower() and out[-1:].isalpha():
            out += p        # word split across lines: "...Visakhapatnam, A" + "ndhra Pradesh"
        else:
            out += " " + p
    return out


def _parse_a4(boxes: list[Box], labels: dict[str, str]) -> dict[str, str]:
    by_squash = {squash(k): v for k, v in labels.items()}
    rows: list[tuple[float, str]] = []
    values: list[tuple[float, str]] = []
    for b in boxes:
        key = by_squash.get(squash(b.text)) if b.x < VALUE_X else None
        if key:
            rows.append((b.y, key))
        elif b.x >= VALUE_X:
            values.append((b.y, b.text))
        # label continuations and stray left-column text are ignored
    rows.sort()
    grouped: dict[str, list[tuple[float, str]]] = {k: [] for _, k in rows}
    for y, text in sorted(values):
        owner = None
        for ly, key in rows:
            if ly - 25 <= y:
                owner = key
        if owner:
            grouped[owner].append((y, text))
    return {k: clean_value(_join([t for _, t in sorted(v)])) for k, v in grouped.items()}


def _parse_card(boxes: list[Box]) -> dict[str, str]:
    by_squash = {squash(k): v for k, v in CARD_LABELS.items()}
    labels = [(b, by_squash[squash(b.text)]) for b in boxes if squash(b.text) in by_squash]
    others = [b for b in boxes if squash(b.text) not in by_squash]
    out = {}
    for lab, key in labels:
        below = sorted((b for b in others if abs(b.x - lab.x) < 40 and 10 < b.y - lab.y < 60), key=lambda b: b.y)
        if below:
            out[key] = clean_value(below[0].text)
    return out


def extract(boxes: list[Box], declared_type: str) -> tuple[dict[str, str], str | None]:
    """Fields for the declared document slot, plus the type the title says it is (None if unknown)."""
    clean = [b for b in boxes if not is_noise(b.text)]
    seen_type = detect_type(boxes)
    if declared_type == "signatory_id":
        return _parse_card(clean), seen_type
    return _parse_a4(clean, A4_LABELS[declared_type]), seen_type
