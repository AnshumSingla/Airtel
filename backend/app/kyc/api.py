"""Consent ("Your choices") and KYC HTTP API.

Security (POLICIES.md §13): the named session must be the one in this browser's
cookie, and a KYC case must belong to it (404 otherwise).
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.advisor.service import SessionNotFound
from app.kyc.ocr import MAX_BYTES, OcrBusy
from app.kyc.service import CaseNotFound, ConsentRequired
from app.security.web import cookie_sid, require_owner

router = APIRouter(prefix="/api", tags=["consent", "kyc"])

NOTICE_VERSIONS = {"P1": "p1-2026-11-05", "P2": "p2-2026-11-05", "P3": "p3-2026-11-05",
                   "P4": "p4-2026-11-05", "P5": "p5-2026-11-05", "P6": "p6-2026-11-05"}


class ConsentIn(BaseModel):
    session_id: str
    purpose: str = Field(..., pattern="^P[1-6]$")
    decision: str = Field(..., pattern="^(given|declined)$")
    language: str = Field("en", pattern="^(en|hi|hinglish)$")
    team: str | None = None          # P5 only: "accel_sales" or a partner id


class WithdrawIn(BaseModel):
    session_id: str
    purpose: str = Field(..., pattern="^P[1-6]$")
    team: str | None = None          # P5: one team; omitted = every team


class CaseIn(BaseModel):
    session_id: str


class SubmitIn(BaseModel):
    product_ids: list[str] = Field(default_factory=list)


class ConfirmIn(BaseModel):
    field: str = Field("gstin", pattern="^gstin$")
    accept: bool


def _session_exists(request: Request, sid: str) -> None:
    require_owner(request, sid)
    try:
        request.app.state.advisor._load(sid)
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")


@router.post("/consents")
def give_consent(body: ConsentIn, request: Request) -> dict:
    from app.backoffice.accounts import TEAM_NAMES

    _session_exists(request, body.session_id)
    if body.purpose == "P5" and body.team not in TEAM_NAMES:
        raise HTTPException(422, "P5 must name a team: " + ", ".join(TEAM_NAMES))
    if body.purpose != "P5" and body.team is not None:
        raise HTTPException(422, "only P5 names a team")
    event = request.app.state.consent.record(body.session_id, body.purpose, body.decision,
                                             NOTICE_VERSIONS[body.purpose], body.language, team=body.team)
    return {"event_id": event, "notice_version": NOTICE_VERSIONS[body.purpose]}


@router.post("/consents/withdraw")
def withdraw(body: WithdrawIn, request: Request) -> dict:
    """Processing for the purpose stops now (POLICIES.md §2 rule 3)."""
    st = request.app.state
    _session_exists(request, body.session_id)
    from app.backoffice.accounts import TEAM_NAMES

    effects: list[str] = []
    if body.purpose == "P5":
        teams = [body.team] if body.team else [t for t in TEAM_NAMES if st.consent.has(body.session_id, "P5", t)]
        for t in teams:
            st.consent.record(body.session_id, "P5", "withdrawn", NOTICE_VERSIONS["P5"], team=t)
            st.backoffice.delete_for_session(body.session_id, t)
            effects.append(f"removed_from_queue={t}")
    else:
        st.consent.record(body.session_id, body.purpose, "withdrawn", NOTICE_VERSIONS[body.purpose])
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


def _case_owned(request: Request, case_id: str) -> None:
    """The case must belong to the session in this browser's cookie (404 otherwise)."""
    from sqlalchemy import select

    from app.kyc.service import kyc_cases

    with request.app.state.engine.connect() as conn:
        owner = conn.execute(select(kyc_cases.c.session_id).where(kyc_cases.c.case_id == case_id)).scalar()
    if owner is None or owner != cookie_sid(request):
        raise HTTPException(404, "case not found")


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
    _case_owned(request, case_id)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file larger than 8 MB")
    if not (data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff"):
        raise HTTPException(415, "only JPEG or PNG photos")
    return _call(request.app.state.kyc.add_document, case_id, doc_type, data)


@router.post("/kyc/cases/{case_id}/submit")
def submit(case_id: str, body: SubmitIn, request: Request) -> dict:
    _case_owned(request, case_id)
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
    _case_owned(request, case_id)
    kyc = request.app.state.kyc
    return kyc.view(_call(kyc.confirm_identifier, case_id, body.field, body.accept))


class GstinCheckIn(BaseModel):
    session_id: str
    gstin: str = Field(..., max_length=20)


@router.post("/registry/gstin-check")
def gstin_check(body: GstinCheckIn, request: Request) -> dict:
    """One-time eligibility lookup (P2) [SIMULATED]. The GSTIN is used for this lookup only and not stored."""
    from app.privacy.masking import mask_gstin
    from app.registry.identifiers import validate_gstin

    st = request.app.state
    _session_exists(request, body.session_id)
    if not st.consent.has(body.session_id, "P2"):
        raise HTTPException(403, "P2 (one-time GSTIN check) has not been given")
    v = validate_gstin(body.gstin)
    base = {"registry": "Mock registry (synthetic data pack, as of 15 Jul 2026)", "simulated": True}
    if not v.ok:
        return {**base, "status": "format_invalid", "problems": list(v.problems)}
    row = st.kyc.reg.gstin(v.value)
    if row is None:
        return {**base, "status": "not_found", "gstin": mask_gstin(v.value)}
    status = "active" if row["status"] == "Active" else "inactive"
    st.advisor.set_gstin_status(body.session_id, status)
    return {**base, "status": status, "registry_status": row["status"], "gstin": mask_gstin(v.value),
            "prefill": {"trade_name": row["trade_name"], "constitution": row["constitution"], "state": row["state"]}}
