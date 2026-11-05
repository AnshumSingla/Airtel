"""Consent ("Your choices") and KYC HTTP API.

Gap for the security step (POLICIES.md §13): session cookies, CSRF and Origin
checks aren't wired yet; ids are random tokens passed in the request.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.advisor.service import SessionNotFound
from app.kyc.ocr import MAX_BYTES, OcrBusy
from app.kyc.service import CaseNotFound, ConsentRequired

router = APIRouter(prefix="/api", tags=["consent", "kyc"])

NOTICE_VERSIONS = {"P1": "p1-2026-11-05", "P2": "p2-2026-11-05", "P3": "p3-2026-11-05",
                   "P4": "p4-2026-11-05", "P5": "p5-2026-11-05", "P6": "p6-2026-11-05"}


class ConsentIn(BaseModel):
    session_id: str
    purpose: str = Field(..., pattern="^P[1-6]$")
    decision: str = Field(..., pattern="^(given|declined)$")
    language: str = Field("en", pattern="^(en|hi|hinglish)$")


class WithdrawIn(BaseModel):
    session_id: str
    purpose: str = Field(..., pattern="^P[1-6]$")


class CaseIn(BaseModel):
    session_id: str


class SubmitIn(BaseModel):
    product_ids: list[str] = Field(default_factory=list)


class ConfirmIn(BaseModel):
    field: str = Field("gstin", pattern="^gstin$")
    accept: bool


def _session_exists(request: Request, sid: str) -> None:
    try:
        request.app.state.advisor._load(sid)
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")


@router.post("/consents")
def give_consent(body: ConsentIn, request: Request) -> dict:
    _session_exists(request, body.session_id)
    event = request.app.state.consent.record(body.session_id, body.purpose, body.decision,
                                             NOTICE_VERSIONS[body.purpose], body.language)
    return {"event_id": event, "notice_version": NOTICE_VERSIONS[body.purpose]}


@router.post("/consents/withdraw")
def withdraw(body: WithdrawIn, request: Request) -> dict:
    """Processing for the purpose stops now (POLICIES.md §2 rule 3)."""
    st = request.app.state
    st.consent.record(body.session_id, body.purpose, "withdrawn", NOTICE_VERSIONS[body.purpose])
    effects: list[str] = []
    if body.purpose in {"P2", "P3"}:
        effects.append(f"kyc_cases_deleted={st.kyc.delete_for_session(body.session_id)}")
    if body.purpose == "P1":
        effects.append(f"kyc_cases_deleted={st.kyc.delete_for_session(body.session_id)}")
        effects.append(f"session_deleted={st.advisor.end(body.session_id)}")
        effects.append(f"consent_events_unlinked={st.consent.unlink(body.session_id)}")
    return {"withdrawn": body.purpose, "effects": effects}


@router.post("/kyc/cases")
def open_case(body: CaseIn, request: Request) -> dict:
    _session_exists(request, body.session_id)
    try:
        return {"case_id": request.app.state.kyc.open_case(body.session_id)}
    except ConsentRequired as exc:
        raise HTTPException(403, str(exc))


def _call(fn, *args):
    try:
        return fn(*args)
    except CaseNotFound:
        raise HTTPException(404, "case not found")
    except ConsentRequired as exc:
        raise HTTPException(403, str(exc))
    except OcrBusy:
        raise HTTPException(503, "busy, please try again in a moment")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/kyc/cases/{case_id}/documents")
async def upload(case_id: str, request: Request, doc_type: str = Form(...), file: UploadFile = File(...)) -> dict:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file larger than 8 MB")
    if not (data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff"):
        raise HTTPException(415, "only JPEG or PNG photos")
    return _call(request.app.state.kyc.add_document, case_id, doc_type, data)


@router.post("/kyc/cases/{case_id}/submit")
def submit(case_id: str, body: SubmitIn, request: Request) -> dict:
    kyc = request.app.state.kyc
    result = _call(kyc.evaluate, case_id)
    out = kyc.view(result)
    if body.product_ids:
        case = kyc._case(case_id)
        slots = request.app.state.advisor._load(case["session_id"])["slots"]
        out["lines"] = _call(kyc.line_eligibility, result, slots, body.product_ids)
    return out


@router.post("/kyc/cases/{case_id}/confirm-identifier")
def confirm_identifier(case_id: str, body: ConfirmIn, request: Request) -> dict:
    kyc = request.app.state.kyc
    return kyc.view(_call(kyc.confirm_identifier, case_id, body.field, body.accept))
