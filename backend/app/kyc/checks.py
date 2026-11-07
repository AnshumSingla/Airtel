"""Automated KYC consistency checks (POLICIES.md §9).

Outcome precedence: if anything is fixable by the owner -> owner_action_needed;
else if anything needs a specialist -> manual_review; else checks_passed.
``checks_passed`` means consistency checks passed for the documents given. It
does not mean the documents are genuine or that identity was verified.

Records are linked by identifier (GSTIN, Udyam number). Names and addresses
are consistency checks only and can lower an outcome, never raise it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from typing import Protocol

from app.kyc.text import iso_date, norm_name, pincode
from app.registry.identifiers import gstin_repair_candidates, validate_gstin, validate_udyam

NAME_MIN_SIMILARITY = 0.95
ADDRESS_PROOF_MAX_AGE_DAYS = 90   # [ASSUMPTION] from the data pack; configurable in policy

ACTION, REVIEW, NOTE = "action", "review", "note"


class Registry(Protocol):
    def gstin(self, gstin: str) -> dict | None: ...
    def udyam(self, number: str) -> dict | None: ...
    def udyam_for_gstin(self, gstin: str) -> str | None: ...   # simulated link


@dataclass
class DocInput:
    fields: dict[str, str] = field(default_factory=dict)
    refused: str | None = None        # OCR quality refusal code, e.g. TOO_BLURRY
    seen_type: str | None = None      # what the document's title says it is


@dataclass(frozen=True)
class Finding:
    code: str
    level: str      # action | review | note
    doc: str | None = None
    detail: dict = field(default_factory=dict)


@dataclass
class KycResult:
    outcome: str
    findings: list[Finding]
    gstin: str | None = None
    gstin_status: str | None = None       # "active" | "inactive" | None (no usable GSTIN)
    business_proof: str | None = None     # "gst" | "udyam" | None
    repair_proposals: list[dict] = field(default_factory=list)

    def codes(self) -> list[str]:
        return [f.code for f in self.findings]


def similarity(a: str, b: str) -> float:
    a, b = norm_name(a), norm_name(b)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def evaluate(docs: dict[str, DocInput], reg: Registry, as_of: date,
             confirmed: dict[str, str] | None = None, disputed: frozenset[str] = frozenset()) -> KycResult:
    """``confirmed``: identifier readings the owner accepted. ``disputed``: fields whose
    proposed reading the owner rejected; those go to a specialist."""
    confirmed = confirmed or {}
    F: list[Finding] = []
    repairs: list[dict] = []
    add = lambda code, level, doc=None, **d: F.append(Finding(code, level, doc, d))  # noqa: E731

    # ---- presence, refusals, wrong documents
    for kind in ("signatory_id", "address_proof"):
        if kind not in docs:
            add("DOC_MISSING", ACTION, kind)
    usable: dict[str, DocInput] = {}
    for kind, d in docs.items():
        if d.refused:
            add(f"DOC_{d.refused}", ACTION, kind, **({} if d.refused != "TOO_BLURRY" else {"hint": "retake"}))
        elif d.seen_type and d.seen_type != kind:
            add("DOC_WRONG_TYPE", ACTION, kind, seen=d.seen_type)
        else:
            usable[kind] = d

    # ---- GST certificate
    gst_row = None
    gstin = None
    gst = usable.get("gst_certificate")
    if gst:
        raw = gst.fields.get("gstin", "")
        if "gstin" in confirmed:
            v = validate_gstin(confirmed["gstin"])
            gstin = v.value if v.ok else None
        elif "gstin" in disputed:
            add("REPAIR_DISPUTED", REVIEW, "gst_certificate")
        else:
            v = validate_gstin(raw) if raw else None
            if not raw:
                add("GSTIN_UNREADABLE", ACTION, "gst_certificate")
            elif v.ok:
                gstin = v.value
            else:
                cands = [c for c in gstin_repair_candidates(raw) if reg.gstin(c)]
                if len(cands) == 1:
                    repairs.append({"doc": "gst_certificate", "field": "gstin", "raw": raw, "candidate": cands[0]})
                    add("GSTIN_CONFIRM_READING", ACTION, "gst_certificate", candidate=cands[0])
                    gstin = cands[0]   # used provisionally for the other checks; outcome waits for the owner
                else:
                    add("GSTIN_PRINTED_INVALID", REVIEW, "gst_certificate", problems=list(v.problems))
        if gstin:
            gst_row = reg.gstin(gstin)
            if gst_row is None:
                add("GSTIN_NOT_FOUND", REVIEW, "gst_certificate")
            else:
                if gst_row["status"] != "Active":
                    add("GSTIN_INACTIVE", NOTE, "gst_certificate", status=gst_row["status"])
                for f_doc, f_reg in (("legal_name", "legal_name"), ("trade_name", "trade_name")):
                    s = similarity(gst.fields.get(f_doc, ""), gst_row[f_reg])
                    if s < NAME_MIN_SIMILARITY:
                        add("GST_NAME_MISMATCH", REVIEW, "gst_certificate", field=f_doc, similarity=round(s, 2))
                if pincode(gst.fields.get("address", "")) != pincode(gst_row["principal_place_of_business"]):
                    add("GST_ADDRESS_MISMATCH", REVIEW, "gst_certificate")
    gst_active = bool(gst_row and gst_row["status"] == "Active")

    # ---- Udyam certificate
    udyam_valid = False
    udy = usable.get("udyam_certificate")
    if udy:
        number = udy.fields.get("udyam_number", "")
        vu = validate_udyam(number) if number else None
        if not number:
            add("UDYAM_NUMBER_MISSING", NOTE, "udyam_certificate")
        elif not vu.ok:
            add("UDYAM_PRINTED_INVALID", REVIEW, "udyam_certificate")
        else:
            row = reg.udyam(vu.value)
            if row is None:
                add("UDYAM_NOT_FOUND", REVIEW, "udyam_certificate")
            else:
                s = similarity(udy.fields.get("enterprise_name", ""), row["enterprise_name"])
                if s < NAME_MIN_SIMILARITY:
                    add("UDYAM_NAME_MISMATCH", REVIEW, "udyam_certificate", similarity=round(s, 2))
                else:
                    udyam_valid = True
                if gst_row and similarity(row["enterprise_name"], gst_row["trade_name"]) < NAME_MIN_SIMILARITY:
                    add("UDYAM_GST_NAME_MISMATCH", REVIEW, "udyam_certificate")
    elif "udyam_certificate" not in docs and gstin and reg.udyam_for_gstin(gstin):
        add("UDYAM_REGISTERED_NOT_UPLOADED", ACTION, "udyam_certificate", registry_number=reg.udyam_for_gstin(gstin))

    business_proof = "gst" if gst_active else "udyam" if udyam_valid else None
    if business_proof is None and not any(f.code.startswith("DOC_") and f.doc in ("gst_certificate", "udyam_certificate")
                                           for f in F):
        add("NO_VALID_BUSINESS_PROOF", ACTION)
    trade_name = gst_row["trade_name"] if gst_row else (udy.fields.get("enterprise_name") if udy else None)
    principal = gst_row["principal_place_of_business"] if gst_row else None

    # ---- address proof
    bill = usable.get("address_proof")
    if bill:
        d = iso_date(bill.fields.get("bill_date", ""))
        if d is None:
            add("ADDRESS_PROOF_DATE_UNREADABLE", ACTION, "address_proof")
        elif (as_of - d).days > ADDRESS_PROOF_MAX_AGE_DAYS:
            add("ADDRESS_PROOF_STALE", ACTION, "address_proof", bill_date=d.isoformat(), age_days=(as_of - d).days)
        if trade_name and similarity(bill.fields.get("billed_to", ""), trade_name) < NAME_MIN_SIMILARITY:
            add("BILL_NAME_MISMATCH", REVIEW, "address_proof")
        if principal and pincode(bill.fields.get("address", "")) != pincode(principal):
            add("ADDRESS_MISMATCH", REVIEW, "address_proof")

    # ---- signatory ID
    sid = usable.get("signatory_id")
    if sid:
        vt = iso_date(sid.fields.get("valid_till", ""))
        if vt is None:
            add("ID_VALIDITY_UNREADABLE", ACTION, "signatory_id")
        elif vt < as_of:
            add("ID_EXPIRED", ACTION, "signatory_id", valid_till=vt.isoformat())
        if trade_name and similarity(sid.fields.get("for_business", ""), trade_name) < NAME_MIN_SIMILARITY:
            add("ID_BUSINESS_MISMATCH", REVIEW, "signatory_id")
        legal = gst_row["legal_name"] if gst_row else ""
        if "(Prop." in legal:
            if similarity(sid.fields.get("name", ""), legal.split(" (Prop.")[0]) < NAME_MIN_SIMILARITY:
                add("SIGNATORY_MISMATCH", REVIEW, "signatory_id")
        elif gst_row:
            add("SIGNATORY_NOT_CHECKABLE", NOTE, "signatory_id", constitution=gst_row["constitution"])

    levels = {f.level for f in F}
    outcome = "owner_action_needed" if ACTION in levels else "manual_review" if REVIEW in levels else "checks_passed"
    status = None if gst_row is None else ("active" if gst_active else "inactive")
    return KycResult(outcome, F, gstin, status, business_proof, repairs)
