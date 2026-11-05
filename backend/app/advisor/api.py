"""Advisor HTTP API.

Gap noted for the security step (POLICIES.md §13): session cookies, CSRF
tokens and Origin checks are not wired in yet. The session id is a random
192-bit token returned in the body for now.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.advisor.service import AdvisorService, SessionNotFound

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


class StartIn(BaseModel):
    language: str = Field("en", pattern="^(en|hi|hinglish)$")


class MessageIn(BaseModel):
    text: str = Field(..., max_length=500)


class ConfirmIn(BaseModel):
    edits: dict = Field(default_factory=dict)


def _svc(request: Request) -> AdvisorService:
    return request.app.state.advisor


@router.post("/sessions")
def start(body: StartIn, request: Request) -> dict:
    sid, turn = _svc(request).start(body.language)
    return {"session_id": sid, "p1_notice_version": "p1-2026-11-05", **asdict(turn)}


@router.post("/sessions/{sid}/messages")
def message(sid: str, body: MessageIn, request: Request) -> dict:
    try:
        return asdict(_svc(request).message(sid, body.text))
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")


@router.post("/sessions/{sid}/confirm")
def confirm(sid: str, body: ConfirmIn, request: Request) -> dict:
    try:
        return _svc(request).confirm(sid, body.edits)
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/sessions/{sid}/end")
def end(sid: str, request: Request) -> dict:
    """'End and delete' (POLICIES.md §2)."""
    return {"deleted": _svc(request).end(sid)}
