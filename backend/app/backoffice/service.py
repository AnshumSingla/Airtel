"""Back office: queues, call-backs, referrals, KYC review, admin (POLICIES.md §11).

Scope is enforced here, not in the UI:
- sales_agent: live leads with P5 naming Accel Business sales; the historical call-back list.
- partner: live leads with P5 naming *that* partner only. A referral code alone
  gives no access; referrals are visible only as counts of at least 5.
- kyc_reviewer: KYC cases in manual_review; full identifiers only on the case
  screen, and every view is audited.
- admin: masked audit log and the retention job.
"""

from __future__ import annotations

import json
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import Column, DateTime, Engine, Integer, MetaData, String, Table, Text, delete, select

from app.backoffice.accounts import ACCEL_SALES, Staff
from app.backoffice.referrals import Referrals
from app.data.schema import historical_leads
from app.privacy.audit import AuditLog
from app.privacy.masking import mask_gstin

CLAIM_FOR = timedelta(hours=48)
PROCESS_FIXABLE = {"Owner had no time for a visit", "Visit not scheduled by sales", "Quote too complex to understand",
                   "Quote took too long to arrive", "Found paperwork too long", "Missing GST or Udyam document",
                   "Document details did not match", "Authorised signatory not available"}

bo_metadata = MetaData()
lead_claims = Table(
    "lead_claims", bo_metadata,
    Column("session_id", String, primary_key=True),
    Column("team", String, primary_key=True),
    Column("username", String, nullable=False),
    Column("until", DateTime(timezone=True), nullable=False),
)
lead_notes = Table(
    "lead_notes", bo_metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String, nullable=False, index=True),
    Column("team", String, nullable=False),
    Column("author", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
)


class NotInScope(LookupError):
    """The record isn't visible to this staff member (answered as 404)."""


class WrongRole(PermissionError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def team_of(staff: Staff) -> str:
    if staff.role == "sales_agent":
        return ACCEL_SALES
    if staff.role == "partner" and staff.partner_id:
        return staff.partner_id
    raise WrongRole("only sales agents and partners have a lead queue")


class BackOffice:
    def __init__(self, engine: Engine, app_state, audit: AuditLog, referrals: Referrals, reset: bool = True):
        self.engine, self.st, self.audit, self.referrals = engine, app_state, audit, referrals
        if reset:
            bo_metadata.drop_all(engine)
        bo_metadata.create_all(engine)
        self._callbacks = self._build_callbacks()

    @staticmethod
    def _require(staff: Staff, *roles: str) -> None:
        if staff.role not in roles:
            raise WrongRole(f"needs role {' or '.join(roles)}")

    # ------------------------------------------------------------ live lead queue
    def _lead(self, sid: str, team: str) -> dict | None:
        try:
            state = self.st.advisor._load(sid)
        except KeyError:
            return None
        card = state.get("confirmed_card") or self.st.advisor.summary_card(state)
        orders = self.st.orders.orders_for_session(sid)
        order = orders[-1] if orders else None
        if order:
            stage = f"order: {order['status']}" + (f" ({order['hold_reason']})" if order["hold_reason"] else "")
        elif state.get("quote_versions"):
            stage = "quote accepted"
        elif "confirmed_card" in state:
            stage = "quote shown, not accepted"
        else:
            stage = "in conversation"
        with self.engine.connect() as conn:
            claim = conn.execute(select(lead_claims).where(lead_claims.c.session_id == sid,
                                                           lead_claims.c.team == team)).mappings().first()
            notes = conn.execute(select(lead_notes).where(lead_notes.c.session_id == sid, lead_notes.c.team == team)
                                 .order_by(lead_notes.c.seq)).mappings().all()
        claim_live = claim and _aware(claim["until"]) > _now()
        # Summary card only: no chat text, no identifiers (POLICIES.md §3: staff see a summary with P5).
        return {"lead_ref": sid[:8], "session_id": sid, "stage": stage, "language": state.get("language"),
                "summary": {k: card.get(k) for k in ("business_type", "segment", "city", "city_tier", "employees",
                                                    "sites", "has_gstin", "needs")},
                "monthly_incl_tax": (order or {}).get("quote_versions", [{}])[-1].get("quote", {}).get("monthly_incl_tax")
                if order else None,
                "claimed_by": claim["username"] if claim_live else None,
                "claim_until": claim["until"].isoformat() if claim_live else None,
                "notes": [{"author": n["author"], "text": n["text"], "at": n["at"].isoformat()} for n in notes]}

    def queue(self, staff: Staff) -> list[dict]:
        team = team_of(staff)
        out = [lead for sid in self.st.consent.sessions_sharing_with(team) if (lead := self._lead(sid, team))]
        self.audit.record(staff.username, staff.role, "view_queue", team, f"{len(out)} leads")
        return out

    def _in_scope(self, staff: Staff, sid: str) -> str:
        team = team_of(staff)
        if not self.st.consent.has(sid, "P5", team):
            raise NotInScope(sid)
        return team

    def claim(self, staff: Staff, sid: str) -> dict:
        team = self._in_scope(staff, sid)
        with self.engine.begin() as conn:
            cur = conn.execute(select(lead_claims).where(lead_claims.c.session_id == sid,
                                                         lead_claims.c.team == team)).mappings().first()
            if cur and _aware(cur["until"]) > _now() and cur["username"] != staff.username:
                raise ValueError(f"already claimed by {cur['username']}")
            conn.execute(delete(lead_claims).where(lead_claims.c.session_id == sid, lead_claims.c.team == team))
            conn.execute(lead_claims.insert().values(session_id=sid, team=team, username=staff.username,
                                                     until=_now() + CLAIM_FOR))
        self.audit.record(staff.username, staff.role, "claim_lead", sid[:8])
        return self._lead(sid, team)

    def add_note(self, staff: Staff, sid: str, text: str) -> dict:
        team = self._in_scope(staff, sid)
        text = text.strip()
        if not 1 <= len(text) <= 500:
            raise ValueError("note must be 1-500 characters")
        with self.engine.begin() as conn:
            conn.execute(lead_notes.insert().values(session_id=sid, team=team, author=staff.username, text=text, at=_now()))
        self.audit.record(staff.username, staff.role, "add_note", sid[:8])
        return self._lead(sid, team)

    def delete_for_session(self, sid: str, team: str | None = None) -> None:
        """P5 withdrawal (one team) or session deletion (all teams): claims and notes go."""
        with self.engine.begin() as conn:
            for t in (lead_claims, lead_notes):
                q = delete(t).where(t.c.session_id == sid)
                conn.execute(q.where(t.c.team == team) if team else q)

    # ------------------------------------------------------------ historical call-back list (sales)
    def _build_callbacks(self) -> list[dict]:
        """Dropped leads with a process-fixable reason, ranked by baseline p(activate) x expected revenue.

        Baseline (DECISIONS.md D12): the activation rate of similar historical leads (same segment,
        GSTIN yes/no and source), smoothed towards the overall rate. Revenue, not margin.
        """
        with self.engine.connect() as conn:
            rows = conn.execute(select(historical_leads)).mappings().all()
        overall = sum(r["outcome"] == "Activated" for r in rows) / len(rows)
        cells: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        values: dict[str, list[int]] = defaultdict(list)
        for r in rows:
            c = cells[(r["segment"], r["has_gstin"], r["lead_source"])]
            c[0] += r["outcome"] == "Activated"
            c[1] += 1
            if r["monthly_bundle_value_inr"]:
                values[r["segment"]].append(r["monthly_bundle_value_inr"])
        med = {seg: median(v) for seg, v in values.items()}
        k = 20  # smoothing strength
        out = []
        for r in rows:
            if r["outcome"] != "Dropped" or r["drop_reason"] not in PROCESS_FIXABLE:
                continue
            a, n = cells[(r["segment"], r["has_gstin"], r["lead_source"])]
            p = (a + k * overall) / (n + k)
            rev = med.get(r["segment"], 0)
            out.append({"lead_id": r["lead_id"], "business_name": r["business_name"], "business_type": r["business_type"],
                        "segment": r["segment"], "city": r["city"], "contact_name": r["contact_name"],
                        "contact_role": r["contact_role"], "stage_reached": r["stage_reached"],
                        "drop_reason": r["drop_reason"], "gstin": mask_gstin(r["gstin"]) if r["gstin"] else None,
                        "p_activate": round(p, 3), "expected_monthly_revenue": round(p * rev),
                        "why": [f"similar leads activated {round(100 * a / n)}% ({a}/{n})",
                                f"GSTIN {'yes' if r['has_gstin'] == 'Y' else 'no'}", f"source: {r['lead_source']}",
                                f"segment median bundle ₹{round(rev):,}/month"]})
        out.sort(key=lambda x: -x["expected_monthly_revenue"])
        return out

    def callbacks(self, staff: Staff, limit: int = 25) -> dict:
        self._require(staff, "sales_agent")
        self.audit.record(staff.username, staff.role, "view_callbacks", "historical", f"top {limit}")
        return {"label": "Historical synthetic leads (data pack). Ranked by a baseline score, revenue not margin.",
                "total": len(self._callbacks), "leads": self._callbacks[:limit]}

    # ------------------------------------------------------------ partner referrals
    def referral_counts(self, staff: Staff) -> dict:
        self._require(staff, "partner")
        sids = self.referrals.sessions_for(staff.partner_id)
        orders = [o for sid in sids for o in self.st.orders.orders_for_session(sid)]
        placed = len(orders)
        active = sum(o["status"] == "COMPLETED" for o in orders)
        show = self.referrals.shown
        self.audit.record(staff.username, staff.role, "view_referrals", staff.partner_id)
        return {"partner": staff.display, "sessions_started": show(len(sids)), "orders_placed": show(placed),
                "orders_completed": show(active),
                "note": "Counts only; shown once a count reaches 5. A referral gives credit, not access."}

    # ------------------------------------------------------------ KYC review
    def review_queue(self, staff: Staff) -> list[dict]:
        self._require(staff, "kyc_reviewer")
        cases = self.st.kyc.cases_in_review()
        self.audit.record(staff.username, staff.role, "view_review_queue", "kyc", f"{len(cases)} cases")
        return [{"case_id": c["case_id"], "updated_at": c["updated_at"],
                 "findings": [f["code"] for f in (c["result"] or {}).get("findings", []) if f["level"] != "note"],
                 "gstin": (c["result"] or {}).get("gstin")} for c in cases]

    def review_case(self, staff: Staff, case_id: str) -> dict:
        self._require(staff, "kyc_reviewer")
        if case_id not in {c["case_id"] for c in self.st.kyc.cases_in_review()}:
            raise NotInScope(case_id)
        result = self.st.kyc.evaluate(case_id)
        self.audit.record(staff.username, staff.role, "view_full_identifiers", case_id[:8])
        return {"case_id": case_id, "outcome": result.outcome,
                "findings": [{"code": f.code, "level": f.level, "doc": f.doc, "detail": f.detail} for f in result.findings],
                "fields": self.st.kyc.full_fields(case_id), "gstin_status": result.gstin_status,
                "business_proof": result.business_proof}

    def decide(self, staff: Staff, case_id: str, approve: bool, reason: str) -> dict:
        self._require(staff, "kyc_reviewer")
        reason = (reason or "").strip()
        if not 3 <= len(reason) <= 200:
            raise ValueError("a reason of 3-200 characters is required")
        if case_id not in {c["case_id"] for c in self.st.kyc.cases_in_review()}:
            raise NotInScope(case_id)
        sid = self.st.kyc._case(case_id)["session_id"]
        result = self.st.kyc.record_review(case_id, approve, reason, staff.username)
        moved = []
        for order in self.st.orders.orders_for_session(sid):
            if order["status"] == "ON_HOLD" and order["hold_reason"] == "KYC_REVIEW":
                lines = self.st.kyc.line_eligibility(result, self.st.advisor.slots(sid),
                                                     [ln["product_id"] for ln in order["lines"]])
                self.st.orders.reviewer_decision(order["order_id"], approve,
                                                 {ln["product_id"]: ln["codes"] for ln in lines}, reason)
                moved.append(order["order_id"][:8])
        self.audit.record(staff.username, staff.role, "kyc_decision", case_id[:8],
                          f"{'approved' if approve else 'rejected'}: {reason}; orders moved: {len(moved)}")
        return {"case_id": case_id, "outcome": result.outcome, "orders_moved": len(moved)}

    # ------------------------------------------------------------ admin
    def audit_log(self, staff: Staff) -> list[dict]:
        self._require(staff, "admin")
        entries = self.audit.recent()
        self.audit.record(staff.username, staff.role, "view_audit_log", "audit")
        return entries

    def run_retention(self, staff: Staff) -> dict:
        self._require(staff, "admin")
        result = {"advisor_sessions_deleted": self.st.advisor.purge_idle(),
                  "kyc_cases_deleted": self.st.kyc.purge_unfinished()}
        self.audit.record(staff.username, staff.role, "run_retention", "all", json.dumps(result))
        return result


def new_csrf() -> str:
    return secrets.token_urlsafe(24)
