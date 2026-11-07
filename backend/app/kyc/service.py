"""KYC cases: consented upload -> in-memory OCR -> encrypted fields -> checks -> owner confirmations.

POLICIES.md §2 (P3 required), §3 (no images stored; fields encrypted; 30-day
retention for failed or abandoned KYC), §9 (outcomes, repair trail), §10 (line
eligibility feeds the order).
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Engine, MetaData, String, Table, Text, delete, select

from app.catalogue.models import Catalogue
from app.catalogue.recommend import profile_from_slots
from app.catalogue.rules import GstinStatus, check_bundle
from app.clock import Clock
from app.kyc.checks import DocInput, KycResult, evaluate
from app.kyc.extract import DOC_TYPES
from app.kyc.ocr import OcrPool
from app.kyc.pipeline import read_document
from app.kyc.registry import REGISTRY_LABEL, DbRegistry
from app.privacy.consent import ConsentLedger
from app.privacy.crypto import FieldCipher
from app.privacy.masking import mask_gstin, mask_udyam

RETENTION_UNFINISHED = timedelta(days=30)
IDENTIFIER_FIELDS = {"gstin": mask_gstin, "udyam_number": mask_udyam,
                     "id_no": lambda v: "•" * max(0, len(v) - 4) + v[-4:],
                     "consumer_no": lambda v: "•" * max(0, len(v) - 4) + v[-4:]}

kyc_metadata = MetaData()
kyc_cases = Table(
    "kyc_cases", kyc_metadata,
    Column("case_id", String, primary_key=True),
    Column("session_id", String, nullable=False, index=True),
    Column("status", String, nullable=False),           # open | evaluated
    Column("outcome", String),
    Column("confirmed_enc", Text),                      # owner-confirmed identifier readings (encrypted)
    Column("trail_enc", Text),                          # repair trail: raw, candidate, decision (encrypted)
    Column("result_json", Text),                        # masked result for display
    Column("review_json", Text),                        # reviewer decision {decision, reason, reviewer, at}; cleared by a new upload
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
kyc_documents = Table(
    "kyc_documents", kyc_metadata,
    Column("case_id", String, primary_key=True),
    Column("doc_type", String, primary_key=True),
    Column("fields_enc", Text),                         # encrypted extracted fields; the image itself is never stored
    Column("refused", String),
    Column("seen_type", String),
    Column("quality_json", Text),
)


class ConsentRequired(PermissionError):
    pass


class CaseNotFound(KeyError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mask_fields(fields: dict[str, str]) -> dict[str, str]:
    return {k: (IDENTIFIER_FIELDS[k](v) if k in IDENTIFIER_FIELDS and v else v) for k, v in fields.items()}


class KycService:
    def __init__(self, engine: Engine, registry: DbRegistry, consent: ConsentLedger, cipher: FieldCipher,
                 clock: Clock, cat: Catalogue, pool: OcrPool | None = None, reset: bool = True):
        self.engine, self.reg, self.consent, self.cipher = engine, registry, consent, cipher
        self.clock, self.cat, self.pool = clock, cat, pool
        if reset:
            kyc_metadata.drop_all(engine)
        kyc_metadata.create_all(engine)

    # ------------------------------------------------------------ cases
    def open_case(self, session_id: str) -> str:
        if not self.consent.has(session_id, "P3"):
            raise ConsentRequired("P3 (KYC document checks) has not been given")
        case_id = secrets.token_urlsafe(18)
        now = _now()
        with self.engine.begin() as conn:
            conn.execute(kyc_cases.insert().values(case_id=case_id, session_id=session_id, status="open",
                                                   created_at=now, updated_at=now))
        return case_id

    def _case(self, case_id: str) -> dict:
        with self.engine.connect() as conn:
            row = conn.execute(select(kyc_cases).where(kyc_cases.c.case_id == case_id)).mappings().first()
        if row is None:
            raise CaseNotFound(case_id)
        if not self.consent.has(row["session_id"], "P3"):
            raise ConsentRequired("P3 was withdrawn")
        return dict(row)

    def add_document(self, case_id: str, doc_type: str, data: bytes) -> dict:
        self._case(case_id)
        if doc_type not in DOC_TYPES:
            raise ValueError("unknown document type")
        doc, quality = read_document(data, doc_type, self.pool)   # bytes are processed in memory only
        del data
        with self.engine.begin() as conn:
            conn.execute(delete(kyc_documents).where(kyc_documents.c.case_id == case_id,
                                                     kyc_documents.c.doc_type == doc_type))
            conn.execute(kyc_documents.insert().values(
                case_id=case_id, doc_type=doc_type, fields_enc=self.cipher.encrypt(doc.fields),
                refused=doc.refused, seen_type=doc.seen_type, quality_json=json.dumps(quality)))
            conn.execute(kyc_cases.update().where(kyc_cases.c.case_id == case_id)
                         .values(status="open", review_json=None, updated_at=_now()))
        return {"doc_type": doc_type, "refused": doc.refused, "seen_type": doc.seen_type,
                "quality": quality, "fields": mask_fields(doc.fields)}

    def _docs(self, case_id: str) -> dict[str, DocInput]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(kyc_documents).where(kyc_documents.c.case_id == case_id)).mappings().all()
        return {r["doc_type"]: DocInput(self.cipher.decrypt(r["fields_enc"]), r["refused"], r["seen_type"])
                for r in rows}

    def evaluate(self, case_id: str) -> KycResult:
        case = self._case(case_id)
        confirmed = self.cipher.decrypt(case["confirmed_enc"]) if case["confirmed_enc"] else {}
        trail = self.cipher.decrypt(case["trail_enc"]) if case["trail_enc"] else []
        # The latest decision per field wins; a disputed reading goes to a specialist (POLICIES.md §9).
        latest = {t["field"]: t["decision"] for t in trail}
        disputed = frozenset(f for f, d in latest.items() if d == "disputed")
        result = evaluate(self._docs(case_id), self.reg, self.clock.business_as_of(), confirmed, disputed)
        review = json.loads(case["review_json"]) if case.get("review_json") else None
        if review and result.outcome == "manual_review":
            # A specialist decided this case (POLICIES.md §9 reviewer authority). Findings stay listed.
            result.outcome = "checks_passed" if review["decision"] == "approved" else "owner_action_needed"
        with self.engine.begin() as conn:
            conn.execute(kyc_cases.update().where(kyc_cases.c.case_id == case_id).values(
                status="evaluated", outcome=result.outcome, result_json=json.dumps(self.view(result)),
                updated_at=_now()))
        return result

    def confirm_identifier(self, case_id: str, field: str, accept: bool) -> KycResult:
        case = self._case(case_id)
        current = evaluate(self._docs(case_id), self.reg, self.clock.business_as_of(),
                           self.cipher.decrypt(case["confirmed_enc"]) if case["confirmed_enc"] else {})
        proposal = next((p for p in current.repair_proposals if p["field"] == field), None)
        if proposal is None:
            raise ValueError("no reading to confirm for this field")
        confirmed = self.cipher.decrypt(case["confirmed_enc"]) if case["confirmed_enc"] else {}
        trail = self.cipher.decrypt(case["trail_enc"]) if case["trail_enc"] else []
        trail.append({"field": field, "raw": proposal["raw"], "candidate": proposal["candidate"],
                      "decision": "accepted" if accept else "disputed", "at": _now().isoformat()})
        if accept:
            confirmed[field] = proposal["candidate"]
        else:
            confirmed.pop(field, None)
        with self.engine.begin() as conn:
            conn.execute(kyc_cases.update().where(kyc_cases.c.case_id == case_id).values(
                confirmed_enc=self.cipher.encrypt(confirmed), trail_enc=self.cipher.encrypt(trail),
                updated_at=_now()))
        return self.evaluate(case_id)

    # ------------------------------------------------------------ views
    def view(self, result: KycResult, include_candidates: bool = True) -> dict:
        """What the owner sees. Identifiers masked, except the reading they're asked to confirm."""
        return {
            "outcome": result.outcome,
            "label": "Automated checks (not identity verification)",
            "registry": REGISTRY_LABEL,
            "findings": [{"code": f.code, "level": f.level, "doc": f.doc,
                          "detail": {k: (mask_gstin(v) if k in {"candidate"} and isinstance(v, str) and len(v) == 15
                                         else mask_udyam(v) if k == "registry_number" else v)
                                     for k, v in f.detail.items()}}
                         for f in result.findings],
            "gstin": mask_gstin(result.gstin) if result.gstin else None,
            "gstin_status": result.gstin_status,
            "business_proof": result.business_proof,
            "confirm": [{"field": p["field"], "doc": p["doc"],
                         "reading": p["candidate"] if include_candidates else mask_gstin(p["candidate"])}
                        for p in result.repair_proposals],
        }

    def line_eligibility(self, result: KycResult, slots: dict, product_ids: list[str]) -> list[dict]:
        """Per-line result for the accepted bundle (POLICIES.md §9-10)."""
        status = {"active": GstinStatus.ACTIVE, "inactive": GstinStatus.INACTIVE}.get(result.gstin_status,
                                                                                        GstinStatus.NONE)
        profile = profile_from_slots({**slots, "gstin_status": status.value})
        return [{"product_id": c.product_id, "eligible": c.eligible, "codes": list(c.excluded)}
                for c in check_bundle(self.cat, profile, product_ids)]

    # ------------------------------------------------------------ deletion
    def record_review(self, case_id: str, approve: bool, reason: str, reviewer: str) -> KycResult:
        case = self._case(case_id)
        if case["outcome"] != "manual_review":
            raise ValueError("this case is not waiting for review")
        review = {"decision": "approved" if approve else "rejected", "reason": reason, "reviewer": reviewer,
                  "at": _now().isoformat()}
        with self.engine.begin() as conn:
            conn.execute(kyc_cases.update().where(kyc_cases.c.case_id == case_id).values(review_json=json.dumps(review)))
        return self.evaluate(case_id)

    def cases_in_review(self) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(kyc_cases).where(kyc_cases.c.outcome == "manual_review")
                                .order_by(kyc_cases.c.updated_at)).mappings().all()
        return [{"case_id": r["case_id"], "session_id": r["session_id"], "updated_at": r["updated_at"].isoformat(),
                 "result": json.loads(r["result_json"]) if r["result_json"] else None} for r in rows]

    def full_fields(self, case_id: str) -> dict[str, dict]:
        """Unmasked extracted fields, for the KYC reviewer only (the caller audits the view)."""
        return {k: d.fields for k, d in self._docs(case_id).items()}

    def delete_for_session(self, session_id: str) -> int:
        """P2/P3 withdrawal or session deletion: extracted fields, results and trails go."""
        with self.engine.begin() as conn:
            ids = [r[0] for r in conn.execute(select(kyc_cases.c.case_id).where(kyc_cases.c.session_id == session_id))]
            if ids:
                conn.execute(delete(kyc_documents).where(kyc_documents.c.case_id.in_(ids)))
                conn.execute(delete(kyc_cases).where(kyc_cases.c.case_id.in_(ids)))
        return len(ids)

    def purge_unfinished(self) -> int:
        """Retention job: failed or abandoned KYC is kept 30 days (no orders exist yet, so that's every case)."""
        cutoff = _now() - RETENTION_UNFINISHED
        with self.engine.begin() as conn:
            ids = [r[0] for r in conn.execute(select(kyc_cases.c.case_id).where(kyc_cases.c.updated_at < cutoff))]
            if ids:
                conn.execute(delete(kyc_documents).where(kyc_documents.c.case_id.in_(ids)))
                conn.execute(delete(kyc_cases).where(kyc_cases.c.case_id.in_(ids)))
        return len(ids)
