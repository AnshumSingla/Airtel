"""Order and tracker API. Fulfilment is simulated.

Ownership: every call names the session; the order must belong to it. (Cookie-
bound sessions and CSRF come with the security step, POLICIES.md §13.)
Commands accept an ``Idempotency-Key`` header.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.advisor.service import SessionNotFound
from app.kyc.service import CaseNotFound, ConsentRequired
from app.orders.service import OrderNotFound
from app.orders.states import IllegalTransition
from app.security.web import require_owner

router = APIRouter(prefix="/api", tags=["orders"])


class CreateIn(BaseModel):
    session_id: str
    quote_version: int = Field(..., ge=1)


class SessionIn(BaseModel):
    session_id: str


class KycIn(SessionIn):
    case_id: str


class DecisionIn(SessionIn):
    accept_substitute: bool


class LineIn(SessionIn):
    product_id: str


class AdvanceIn(SessionIn):
    days: int = Field(1, ge=1, le=30)


def _owned(request: Request, order_id: str, session_id: str) -> None:
    require_owner(request, session_id)
    try:
        if request.app.state.orders.session_of(order_id) != session_id:
            raise HTTPException(404, "order not found")
    except OrderNotFound:
        raise HTTPException(404, "order not found")


def _run(fn):
    try:
        return fn()
    except (OrderNotFound, CaseNotFound):
        raise HTTPException(404, "not found")
    except SessionNotFound:
        raise HTTPException(404, "session not found or expired")
    except ConsentRequired as exc:
        raise HTTPException(403, str(exc))
    except IllegalTransition as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/orders")
def create(body: CreateIn, request: Request, idempotency_key: str | None = Header(None)) -> dict:
    st = request.app.state
    require_owner(request, body.session_id)

    def go():
        state = st.advisor._load(body.session_id)
        versions = state.get("quote_versions", [])
        if not 1 <= body.quote_version <= len(versions):
            raise ValueError("no such accepted quote version")
        return st.orders.create(body.session_id, versions[body.quote_version - 1], state["language"])

    return _run(lambda: st.orders.idempotent(idempotency_key, f"create:{body.session_id}", go))


@router.get("/orders/{order_id}")
def get(order_id: str, session_id: str, request: Request) -> dict:
    _owned(request, order_id, session_id)
    return _run(lambda: request.app.state.orders.view(order_id))


@router.post("/orders/{order_id}/submit-kyc")
def submit_kyc(order_id: str, body: KycIn, request: Request, idempotency_key: str | None = Header(None)) -> dict:
    st = request.app.state
    _owned(request, order_id, body.session_id)

    def go():
        case = st.kyc._case(body.case_id)
        if case["session_id"] != body.session_id:
            raise CaseNotFound(body.case_id)
        result = st.kyc.evaluate(body.case_id)
        if result.gstin_status in {"active", "inactive"}:
            st.advisor.set_gstin_status(body.session_id, result.gstin_status)  # KYC found the real status
        order = st.orders.view(order_id)
        ids = [ln["product_id"] for ln in order["lines"]]
        lines = st.kyc.line_eligibility(result, st.advisor.slots(body.session_id), ids)
        return st.orders.submit_kyc(order_id, body.case_id, result.outcome,
                                    {ln["product_id"]: ln["codes"] for ln in lines})

    return _run(lambda: st.orders.idempotent(idempotency_key, f"kyc:{order_id}", go))


@router.post("/orders/{order_id}/continue-without-excluded")
def continue_without(order_id: str, body: SessionIn, request: Request, idempotency_key: str | None = Header(None)) -> dict:
    st = request.app.state
    _owned(request, order_id, body.session_id)

    def go():
        order = st.orders.view(order_id)
        items = [{"product_id": ln["product_id"], "quantity": ln["quantity"]}
                 for ln in order["lines"] if ln["status"] != "EXCLUDED"]
        snapshot = st.advisor.accept(body.session_id, items)   # new immutable quote version (re-acceptance)
        return st.orders.continue_without_excluded(order_id, snapshot)

    return _run(lambda: st.orders.idempotent(idempotency_key, f"continue:{order_id}", go))


@router.post("/orders/{order_id}/feasibility-decision")
def feasibility_decision(order_id: str, body: DecisionIn, request: Request, idempotency_key: str | None = Header(None)) -> dict:
    st = request.app.state
    _owned(request, order_id, body.session_id)

    def go():
        order = st.orders.view(order_id)
        offer = order["substitute_offer"]
        snapshot = None
        if body.accept_substitute:
            if not offer or not offer["substitute"]:
                raise ValueError("no substitute on offer")
            failed = next(ln for ln in order["lines"] if ln["product_id"] == offer["failed"])
            items = [{"product_id": ln["product_id"], "quantity": ln["quantity"]} for ln in order["lines"]
                     if ln["status"] not in {"EXCLUDED", "CANCELLED", "FEASIBILITY_FAILED"}]
            items.append({"product_id": offer["substitute"], "quantity": failed["quantity"]})
            snapshot = st.advisor.accept(body.session_id, items)
        return st.orders.feasibility_decision(order_id, body.accept_substitute, snapshot)

    return _run(lambda: st.orders.idempotent(idempotency_key, f"feasibility:{order_id}", go))


@router.post("/orders/{order_id}/reschedule")
def reschedule(order_id: str, body: LineIn, request: Request) -> dict:
    _owned(request, order_id, body.session_id)
    return _run(lambda: request.app.state.orders.reschedule(order_id, body.product_id))


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: str, body: SessionIn, request: Request, idempotency_key: str | None = Header(None)) -> dict:
    st = request.app.state
    _owned(request, order_id, body.session_id)
    return _run(lambda: st.orders.idempotent(idempotency_key, f"cancel:{order_id}", lambda: st.orders.cancel(order_id)))


# ---------------------------------------------------------------- demo controls (demo clock only)

def _demo_only(request: Request) -> None:
    if request.app.state.settings.clock_mode != "demo":
        raise HTTPException(404, "not available")


@router.post("/demo/orders/{order_id}/advance")
def demo_advance(order_id: str, body: AdvanceIn, request: Request) -> dict:
    """[SIMULATED] Move this order's simulated timeline forward. Never changes business_as_of."""
    _demo_only(request)
    _owned(request, order_id, body.session_id)
    return _run(lambda: request.app.state.orders.advance(order_id, body.days))


@router.post("/demo/orders/{order_id}/fail-feasibility")
def demo_fail(order_id: str, body: LineIn, request: Request) -> dict:
    """[SIMULATED] Make the next feasibility check for this line fail."""
    _demo_only(request)
    _owned(request, order_id, body.session_id)
    return _run(lambda: request.app.state.orders.force_feasibility_fail(order_id, body.product_id))


# ---------------------------------------------------------------- demo specimens (demo clock only)

@router.get("/demo/specimens")
def demo_specimens(request: Request) -> dict:
    """[SIMULATED] The synthetic KYC specimen sets from the data pack, so the demo can be tried without files."""
    _demo_only(request)
    docs = request.app.state.settings.data_dir / "kyc_documents"
    sets: dict[str, list[str]] = {}
    for p in sorted(docs.glob("K*.png")):
        sets.setdefault(p.stem[:3], []).append(p.stem.split("_", 1)[1])
    return {"sets": sets, "label": "Synthetic specimens from the data pack"}


@router.get("/demo/specimens/{name}")
def demo_specimen(name: str, request: Request):
    from fastapi.responses import FileResponse
    import re

    _demo_only(request)
    if not re.fullmatch(r"K\d{2}_(gst_certificate|udyam_certificate|address_proof|signatory_id)", name):
        raise HTTPException(404, "not found")
    path = request.app.state.settings.data_dir / "kyc_documents" / f"{name}.png"
    if not path.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="image/png")
