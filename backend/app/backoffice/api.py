"""Back-office API (POLICIES.md §11, §13). Staff cookies are separate from owner cookies.

- POST /api/bo/login sets ``udyam_staff`` (HttpOnly, SameSite=Strict, path /api/bo,
  Secure over HTTPS) and a readable ``udyam_staff_csrf`` token, which every other
  state-changing /api/bo request must echo in X-CSRF-Token (enforced by the
  security middleware).
- Wrong role -> 403. A record outside the caller's scope -> 404.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.backoffice.accounts import AccountLocked, LoginFailed, Staff
from app.backoffice.service import NotInScope, WrongRole, new_csrf
from app.orders.states import IllegalTransition
from app.security.web import _is_https

router = APIRouter(prefix="/api/bo", tags=["back office"])

STAFF_COOKIE = "udyam_staff"
STAFF_CSRF_COOKIE = "udyam_staff_csrf"


class LoginIn(BaseModel):
    username: str = Field(..., max_length=64)
    password: str = Field(..., max_length=256)


class NoteIn(BaseModel):
    text: str = Field(..., max_length=500)


class DecisionIn(BaseModel):
    approve: bool
    reason: str = Field(..., max_length=200)


def _staff(request: Request) -> Staff:
    staff = request.app.state.staff.session(request.cookies.get(STAFF_COOKIE))
    if staff is None:
        raise HTTPException(401, "please sign in")
    return staff


def _run(fn):
    try:
        return fn()
    except WrongRole as exc:
        raise HTTPException(403, str(exc))
    except (NotInScope, KeyError):
        raise HTTPException(404, "not found")
    except IllegalTransition as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    st = request.app.state
    try:
        token = st.staff.login(body.username, body.password)
    except AccountLocked:
        st.audit.record(body.username[:64], "unknown", "login_locked", "staff")
        raise HTTPException(423, "too many failed attempts; try again in 15 minutes")
    except LoginFailed:
        st.audit.record(body.username[:64], "unknown", "login_failed", "staff")
        raise HTTPException(401, "wrong username or password")
    secure = _is_https(request)
    response.set_cookie(STAFF_COOKIE, token, httponly=True, samesite="strict", secure=secure, path="/api/bo")
    response.set_cookie(STAFF_CSRF_COOKIE, new_csrf(), httponly=False, samesite="strict", secure=secure, path="/")
    staff = st.staff.accounts[body.username]
    st.audit.record(staff.username, staff.role, "login", "staff")
    return {"username": staff.username, "role": staff.role, "display": staff.display, "partner_id": staff.partner_id}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(STAFF_COOKIE)
    staff = request.app.state.staff.session(token)
    if token:
        request.app.state.staff.logout(token)
    if staff:
        request.app.state.audit.record(staff.username, staff.role, "logout", "staff")
    response.delete_cookie(STAFF_COOKIE, path="/api/bo")
    response.delete_cookie(STAFF_CSRF_COOKIE, path="/")
    return {"signed_out": True}


@router.get("/me")
def me(request: Request) -> dict:
    s = _staff(request)
    return {"username": s.username, "role": s.role, "display": s.display, "partner_id": s.partner_id}


@router.get("/queue")
def queue(request: Request) -> list[dict]:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.queue(s))


@router.post("/leads/{sid}/claim")
def claim(sid: str, request: Request) -> dict:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.claim(s, sid))


@router.post("/leads/{sid}/notes")
def note(sid: str, body: NoteIn, request: Request) -> dict:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.add_note(s, sid, body.text))


@router.get("/callbacks")
def callbacks(request: Request) -> dict:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.callbacks(s))


@router.get("/referrals")
def referrals(request: Request) -> dict:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.referral_counts(s))


@router.get("/kyc/review")
def review_queue(request: Request) -> list[dict]:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.review_queue(s))


@router.get("/kyc/cases/{case_id}")
def review_case(case_id: str, request: Request) -> dict:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.review_case(s, case_id))


@router.post("/kyc/cases/{case_id}/decision")
def decide(case_id: str, body: DecisionIn, request: Request) -> dict:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.decide(s, case_id, body.approve, body.reason))


@router.get("/audit")
def audit(request: Request) -> list[dict]:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.audit_log(s))


@router.post("/admin/retention")
def retention(request: Request) -> dict:
    s = _staff(request)
    return _run(lambda: request.app.state.backoffice.run_retention(s))
