"""Advisor HTTP API.

Security (POLICIES.md §13, app/security/web.py): starting a session sets an HttpOnly
session cookie and a CSRF cookie; every other route checks that the path session
belongs to that cookie, and the middleware enforces CSRF, Origin and rate limits.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.advisor.service import AdvisorService, SessionNotFound
from app.security.web import clear_session_cookies, require_owner, set_session_cookies

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


class StartIn(BaseModel):
    language: str = Field("en", pattern="^(en|hi|hinglish)$")
    ref: str | None = Field(None, max_length=32)   # partner referral code: credit only, never access


class MessageIn(BaseModel):
    text: str = Field(..., max_length=500)


class ConfirmIn(BaseModel):
    edits: dict = Field(default_factory=dict)


def _svc(request: Request) -> AdvisorService:
    return request.app.state.advisor


@router.post("/sessions")
def start(body: StartIn, request: Request, response: Response) -> dict:
    sid, turn = _svc(request).start(body.language)
    set_session_cookies(request, response, sid)   # binds the session to this browser
    from app.backoffice.accounts import REFERRAL_CODES

    if body.ref and body.ref.lower() in REFERRAL_CODES and hasattr(request.app.state, "referrals"):
        request.app.state.referrals.attribute(sid, REFERRAL_CODES[body.ref.lower()])
    return {"session_id": sid, "p1_notice_version": "p1-2026-11-05", **asdict(turn)}


@router.post("/sessions/{sid}/messages")
def message(sid: str, body: MessageIn, request: Request) -> dict:
    require_owner(request, sid)
    try:
        return asdict(_svc(request).message(sid, body.text))
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")


@router.post("/sessions/{sid}/confirm")
def confirm(sid: str, body: ConfirmIn, request: Request) -> dict:
    require_owner(request, sid)
    try:
        return _svc(request).confirm(sid, body.edits)
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/sessions/{sid}/end")
def end(sid: str, request: Request, response: Response) -> dict:
    """'End and delete' (POLICIES.md §2): session, chat, drafts and KYC data go; consent events are unlinked."""
    require_owner(request, sid)
    st = request.app.state
    if hasattr(st, "orders") and st.orders.open_orders_for_session(sid):
        # POLICIES.md §2: order data can't be removed on its own; cancel the order first.
        raise HTTPException(409, "you have an open order; cancel it first, then End and delete")
    if hasattr(st, "orders"):
        st.orders.delete_for_session(sid)   # demo: closed/cancelled orders go with the session
    kyc_deleted = st.kyc.delete_for_session(sid) if hasattr(st, "kyc") else 0
    if hasattr(st, "backoffice"):
        st.backoffice.delete_for_session(sid)     # claims and notes about this lead
        st.referrals.delete_for_session(sid)
    unlinked = st.consent.unlink(sid) if hasattr(st, "consent") else 0
    clear_session_cookies(response)
    return {"deleted": _svc(request).end(sid), "kyc_cases_deleted": kyc_deleted, "consent_events_unlinked": unlinked}


class ItemsIn(BaseModel):
    items: list[dict] = Field(..., max_length=40)


@router.get("/options")
def options(request: Request) -> dict:
    """Choices for the editable summary card. No personal data."""
    svc = _svc(request)
    cities = sorted({v[0]: v for v in svc.lex.cities.values()}.values())
    from app.advisor.explain import NEED_LABEL, SEGMENT_LABEL

    return {
        "segments": [{"code": c, "label": {lang: SEGMENT_LABEL[lang][c] for lang in ("en", "hi")}}
                     for c in ("micro", "prof", "multi", "mfg")],
        "cities": [{"name": n, "tier": t, "state": s} for n, t, s in cities],
        "needs": [{"product_id": p, "label": {lang: NEED_LABEL[lang][p] for lang in ("en", "hi")}}
                  for p in NEED_LABEL["en"]],
    }


@router.post("/sessions/{sid}/quote")
def quote(sid: str, body: ItemsIn, request: Request) -> dict:
    require_owner(request, sid)
    try:
        return _svc(request).quote_preview(sid, body.items)
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/sessions/{sid}/accept")
def accept(sid: str, body: ItemsIn, request: Request) -> dict:
    """Accept the quote (mock e-sign): freezes an immutable quote version."""
    require_owner(request, sid)
    try:
        return _svc(request).accept(sid, body.items)
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
