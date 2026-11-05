"""Orders and the tracker (POLICIES.md §10). Fulfilment is [SIMULATED].

- An order is created from an accepted, immutable quote version.
- KYC drives the order: owner action / specialist review put it ON_HOLD;
  excluded lines put it ON_HOLD(BUNDLE_CHANGE_NEEDED) until the owner accepts a
  new quote version without them (the KYC result is reused).
- Fixed connectivity (P01-P06) gets a simulated feasibility check; products
  with no site install go ACTIVE once KYC passes; the rest follow the
  catalogue's typical install days ("about N days", indicative).
- A feasibility failure offers a substitute only as a new quote version.
- Every transition is checked against app.orders.states, recorded as an
  event, and produces an in-app message labelled "Simulated message, not sent".
- Commands accept an idempotency key: a repeat returns the first response.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import Column, DateTime, Engine, Integer, MetaData, String, Text, Table, delete, select

from app.catalogue.models import Catalogue
from app.catalogue.recommend import FIXED_CONNECTIVITY
from app.orders.states import TERMINAL_LINE, IllegalTransition, check_line, check_order

orders_metadata = MetaData()
orders = Table(
    "orders", orders_metadata,
    Column("order_id", String, primary_key=True),
    Column("session_id", String, nullable=False, index=True),
    Column("doc", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
order_events = Table(
    "order_events", orders_metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("order_id", String, nullable=False, index=True),
    Column("product_id", String),
    Column("from_state", String), Column("to_state", String, nullable=False),
    Column("actor", String, nullable=False), Column("trigger", String, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
)
order_messages = Table(
    "order_messages", orders_metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("order_id", String, nullable=False, index=True),
    Column("text", Text, nullable=False),
    Column("sim_day", Integer, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
)
idempotency = Table(
    "idempotency_keys", orders_metadata,
    Column("key", String, primary_key=True),
    Column("command", String, nullable=False),
    Column("response", Text, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
)

MESSAGES = {
    "en": {
        "ACCEPTED": "Your order is placed (quote version {v}). Next: document checks.",
        "KYC_PENDING": "We're checking your documents.",
        "KYC_OK": "Document checks passed.",
        "ON_HOLD:KYC_ACTION": "Your documents need attention. Open the tracker to see what to fix.",
        "ON_HOLD:KYC_REVIEW": "A specialist is reviewing your documents.",
        "ON_HOLD:BUNDLE_CHANGE_NEEDED": "Some items can't be provided. Open the tracker to continue without them.",
        "ON_HOLD:FEASIBILITY_DECISION": "{name} isn't available at your address. Open the tracker to choose an option.",
        "IN_FULFILMENT": "Your services are being set up.",
        "COMPLETED": "Everything in your order is active.",
        "CANCELLED": "Your order is cancelled.",
        "LINE_SCHEDULED": "{name}: installation scheduled, ready in about {days} days (indicative).",
        "LINE_ACTIVE": "{name} is active.",
    },
    "hi": {
        "ACCEPTED": "आपका ऑर्डर हो गया (कोटेशन संस्करण {v})। अगला: दस्तावेज़ जाँच।",
        "KYC_PENDING": "हम आपके दस्तावेज़ जाँच रहे हैं।",
        "KYC_OK": "दस्तावेज़ जाँच पास हो गई।",
        "ON_HOLD:KYC_ACTION": "आपके दस्तावेज़ों में कुछ ठीक करना है। ट्रैकर खोलकर देखें।",
        "ON_HOLD:KYC_REVIEW": "एक विशेषज्ञ आपके दस्तावेज़ देख रहे हैं।",
        "ON_HOLD:BUNDLE_CHANGE_NEEDED": "कुछ आइटम नहीं दिए जा सकते। ट्रैकर में उनके बिना आगे बढ़ें।",
        "ON_HOLD:FEASIBILITY_DECISION": "{name} आपके पते पर उपलब्ध नहीं है। ट्रैकर में विकल्प चुनें।",
        "IN_FULFILMENT": "आपकी सेवाएँ सेट की जा रही हैं।",
        "COMPLETED": "आपके ऑर्डर की सभी सेवाएँ चालू हैं।",
        "CANCELLED": "आपका ऑर्डर रद्द हो गया।",
        "LINE_SCHEDULED": "{name}: इंस्टॉलेशन तय, लगभग {days} दिन में तैयार (अनुमानित)।",
        "LINE_ACTIVE": "{name} चालू है।",
    },
}


class OrderNotFound(KeyError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _needs_site_install(cat: Catalogue, pid: str) -> bool:
    return cat[pid].install_days > 1


class OrderService:
    def __init__(self, engine: Engine, cat: Catalogue, reset: bool = True):
        self.engine, self.cat = engine, cat
        if reset:
            orders_metadata.drop_all(engine)
        orders_metadata.create_all(engine)

    # ------------------------------------------------------------ storage
    def _load(self, order_id: str) -> dict:
        with self.engine.connect() as conn:
            row = conn.execute(select(orders.c.doc).where(orders.c.order_id == order_id)).first()
        if row is None:
            raise OrderNotFound(order_id)
        return json.loads(row[0])

    def _save(self, doc: dict, conn=None) -> None:
        def write(c):
            c.execute(delete(orders).where(orders.c.order_id == doc["order_id"]))
            c.execute(orders.insert().values(order_id=doc["order_id"], session_id=doc["session_id"],
                                             doc=json.dumps(doc), updated_at=_now()))
        if conn is None:
            with self.engine.begin() as c:
                write(c)
        else:
            write(conn)

    def idempotent(self, key: str | None, command: str, fn: Callable[[], dict]) -> dict:
        """Run fn once per key; a repeated key returns the stored response (no second effect)."""
        if not key:
            return fn()
        with self.engine.connect() as conn:
            row = conn.execute(select(idempotency).where(idempotency.c.key == key)).mappings().first()
        if row:
            if row["command"] != command:
                raise ValueError("idempotency key reused for a different command")
            return json.loads(row["response"])
        result = fn()
        with self.engine.begin() as conn:
            conn.execute(idempotency.insert().values(key=key, command=command, response=json.dumps(result), at=_now()))
        return result

    # ------------------------------------------------------------ transitions
    def _event(self, conn, doc, pid, frm, to, actor, trigger):
        conn.execute(order_events.insert().values(order_id=doc["order_id"], product_id=pid, from_state=frm,
                                                  to_state=to, actor=actor, trigger=trigger, at=_now()))

    def _message(self, conn, doc, key, **kw):
        lang = doc.get("language", "en") if doc.get("language") in MESSAGES else "en"
        text = MESSAGES[lang][key].format(**kw)
        conn.execute(order_messages.insert().values(order_id=doc["order_id"], text=text,
                                                    sim_day=doc["sim_day"], at=_now()))

    def _order_to(self, conn, doc, to, actor, trigger, hold=None, **msg):
        check_order(doc["status"], to, actor)
        self._event(conn, doc, None, doc["status"], to if not hold else f"{to}:{hold}", actor, trigger)
        doc["status"], doc["hold_reason"] = to, hold
        self._message(conn, doc, f"{to}:{hold}" if hold else to, **msg)

    def _line_to(self, conn, doc, line, to, actor, trigger, reason=None):
        check_line(line["status"], to, actor)
        self._event(conn, doc, line["product_id"], line["status"], to, actor, trigger)
        line["status"] = to
        if reason:
            line["reason"] = reason
        if to == "ACTIVE":
            self._message(conn, doc, "LINE_ACTIVE", name=line["name"])

    # ------------------------------------------------------------ commands
    def create(self, session_id: str, snapshot: dict, language: str) -> dict:
        doc = {"order_id": secrets.token_urlsafe(16), "session_id": session_id, "status": "ACCEPTED",
               "hold_reason": None, "language": language, "sim_day": 0, "kyc_case_id": None,
               "quote_versions": [snapshot], "force_feasibility_fail": [], "substitute_offer": None,
               "lines": [{"product_id": ln["product_id"], "name": ln["name"], "quantity": ln["quantity"],
                          "status": "PENDING", "install_days": ln["install_days"], "eta_day": None,
                          "reason": None} for ln in snapshot["lines"]]}
        with self.engine.begin() as conn:
            self._event(conn, doc, None, None, "ACCEPTED", "owner", f"accepted quote v{snapshot['version']}")
            self._message(conn, doc, "ACCEPTED", v=snapshot["version"])
            self._save(doc, conn)
        return self.view(doc["order_id"])

    def submit_kyc(self, order_id: str, case_id: str, outcome: str, line_results: dict[str, list[str]]) -> dict:
        """outcome: applicant KYC result; line_results: product_id -> exclusion codes ([] = eligible)."""
        doc = self._load(order_id)
        with self.engine.begin() as conn:
            if doc["status"] == "ON_HOLD" and doc["hold_reason"] not in {"KYC_ACTION", "KYC_REVIEW"}:
                raise IllegalTransition(f"order is on hold for {doc['hold_reason']}, not documents")
            self._order_to(conn, doc, "KYC_PENDING", "owner", "KYC submitted")
            doc["kyc_case_id"] = case_id
            if outcome == "owner_action_needed":
                self._order_to(conn, doc, "ON_HOLD", "system", "KYC needs owner action", hold="KYC_ACTION")
            elif outcome == "manual_review":
                self._order_to(conn, doc, "ON_HOLD", "system", "KYC needs specialist review", hold="KYC_REVIEW")
            else:
                excluded = [ln for ln in doc["lines"] if line_results.get(ln["product_id"])]
                for ln in excluded:
                    self._line_to(conn, doc, ln, "EXCLUDED", "system", "line not eligible",
                                  reason=",".join(line_results[ln["product_id"]]))
                if excluded:
                    self._order_to(conn, doc, "ON_HOLD", "system", "lines excluded", hold="BUNDLE_CHANGE_NEEDED")
                else:
                    self._order_to(conn, doc, "KYC_OK", "system", "KYC checks passed")
                    self._start_fulfilment(conn, doc)
            self._save(doc, conn)
        return self.view(order_id)

    def continue_without_excluded(self, order_id: str, new_snapshot: dict) -> dict:
        """Owner accepted quote vN+1 without the excluded lines. KYC is reused, not redone."""
        doc = self._load(order_id)
        if doc["status"] != "ON_HOLD" or doc["hold_reason"] != "BUNDLE_CHANGE_NEEDED":
            raise IllegalTransition("there is no bundle change waiting")
        keep = {ln["product_id"] for ln in new_snapshot["lines"]}
        if any(ln["status"] != "EXCLUDED" and ln["product_id"] not in keep for ln in doc["lines"]):
            raise ValueError("the new quote must keep every eligible line")
        with self.engine.begin() as conn:
            doc["quote_versions"].append(new_snapshot)
            self._order_to(conn, doc, "KYC_OK", "owner", f"accepted quote v{new_snapshot['version']} without excluded lines")
            self._start_fulfilment(conn, doc)
            self._save(doc, conn)
        return self.view(order_id)

    def _start_fulfilment(self, conn, doc) -> None:
        self._order_to(conn, doc, "IN_FULFILMENT", "system", "first line item starts")
        for ln in doc["lines"]:
            if ln["status"] != "PENDING":
                continue
            if ln["product_id"] in FIXED_CONNECTIVITY:
                self._line_to(conn, doc, ln, "FEASIBILITY_CHECK", "system", "feasibility check (simulated)")
            elif not _needs_site_install(self.cat, ln["product_id"]):
                self._line_to(conn, doc, ln, "ACTIVE", "system", "no site install needed")
            else:
                self._schedule(conn, doc, ln)
        self._maybe_complete(conn, doc)

    def _schedule(self, conn, doc, ln) -> None:
        self._line_to(conn, doc, ln, "SCHEDULED", "system", "installation slot booked (simulated)")
        ln["eta_day"] = doc["sim_day"] + ln["install_days"]
        self._message(conn, doc, "LINE_SCHEDULED", name=ln["name"], days=ln["install_days"])

    def _maybe_complete(self, conn, doc) -> None:
        if doc["status"] == "IN_FULFILMENT" and all(ln["status"] in TERMINAL_LINE for ln in doc["lines"]) \
                and any(ln["status"] == "ACTIVE" for ln in doc["lines"]):
            self._order_to(conn, doc, "COMPLETED", "system", "all lines active")

    def advance(self, order_id: str, days: int) -> dict:
        """[SIMULATED] Move the demo clock for this order's timeline only (never business_as_of)."""
        if not 1 <= days <= 30:
            raise ValueError("days must be 1-30")
        doc = self._load(order_id)
        with self.engine.begin() as conn:
            for _ in range(days):
                doc["sim_day"] += 1
                if doc["status"] != "IN_FULFILMENT":
                    continue
                for ln in doc["lines"]:
                    if ln["status"] == "FEASIBILITY_CHECK":
                        if ln["product_id"] in doc["force_feasibility_fail"]:
                            self._line_to(conn, doc, ln, "FEASIBILITY_FAILED", "system", "not feasible at address (simulated)")
                            self._feasibility_hold(conn, doc, ln)
                            break
                        self._line_to(conn, doc, ln, "SCHEDULED", "system", "feasible (simulated)")
                        ln["eta_day"] = doc["sim_day"] - 1 + ln["install_days"]
                        self._message(conn, doc, "LINE_SCHEDULED", name=ln["name"], days=ln["install_days"])
                    elif ln["status"] == "SCHEDULED" and doc["sim_day"] >= ln["eta_day"] - 1:
                        self._line_to(conn, doc, ln, "INSTALLING", "system", "engineer visit (simulated)")
                    elif ln["status"] == "INSTALLING" and doc["sim_day"] >= ln["eta_day"]:
                        self._line_to(conn, doc, ln, "ACTIVE", "system", "installed (simulated)")
                self._maybe_complete(conn, doc)
            self._save(doc, conn)
        return self.view(order_id)

    def _feasibility_hold(self, conn, doc, ln) -> None:
        sub = "P04" if ln["product_id"] in {"P01", "P02", "P03"} else None
        doc["substitute_offer"] = {"failed": ln["product_id"], "substitute": sub,
                                   "substitute_name": self.cat[sub].name if sub else None,
                                   "substitute_description": self.cat[sub].description if sub else None}
        self._order_to(conn, doc, "ON_HOLD", "system", "feasibility failed", hold="FEASIBILITY_DECISION", name=ln["name"])

    def force_feasibility_fail(self, order_id: str, product_id: str) -> dict:
        """[SIMULATED] demo control: the next feasibility check for this line fails."""
        doc = self._load(order_id)
        doc["force_feasibility_fail"] = sorted(set(doc["force_feasibility_fail"]) | {product_id})
        self._save(doc)
        return self.view(order_id)

    def feasibility_decision(self, order_id: str, accept_substitute: bool, new_snapshot: dict | None) -> dict:
        doc = self._load(order_id)
        offer = doc.get("substitute_offer")
        if doc["status"] != "ON_HOLD" or doc["hold_reason"] != "FEASIBILITY_DECISION" or not offer:
            raise IllegalTransition("no feasibility decision is waiting")
        failed = next(ln for ln in doc["lines"] if ln["product_id"] == offer["failed"])
        with self.engine.begin() as conn:
            self._line_to(conn, doc, failed, "CANCELLED", "owner",
                          "replaced by substitute" if accept_substitute else "owner declined substitute")
            if accept_substitute:
                if not offer["substitute"] or new_snapshot is None:
                    raise ValueError("no substitute to accept")
                doc["quote_versions"].append(new_snapshot)
                sub_line = next(ln for ln in new_snapshot["lines"] if ln["product_id"] == offer["substitute"])
                doc["lines"].append({"product_id": sub_line["product_id"], "name": sub_line["name"],
                                     "quantity": sub_line["quantity"], "status": "PENDING",
                                     "install_days": sub_line["install_days"], "eta_day": None, "reason": None})
            else:
                # Lines that needed the cancelled connection can't go ahead without it.
                remaining = {ln["product_id"] for ln in doc["lines"] if ln["status"] != "CANCELLED"}
                for ln in doc["lines"]:
                    deps = self.cat[ln["product_id"]].requires_one_of
                    if ln["status"] not in TERMINAL_LINE and deps and not set(deps) & remaining:
                        self._line_to(conn, doc, ln, "CANCELLED", "system", "needed the cancelled connection",
                                      reason="DEP_LOST")
            doc["substitute_offer"] = None
            self._order_to(conn, doc, "IN_FULFILMENT", "owner", "feasibility decision made")
            for ln in doc["lines"]:
                if ln["status"] == "PENDING":
                    self._line_to(conn, doc, ln, "FEASIBILITY_CHECK", "system", "feasibility check (simulated)")
            self._maybe_complete(conn, doc)
            self._save(doc, conn)
        return self.view(order_id)

    def reschedule(self, order_id: str, product_id: str) -> dict:
        doc = self._load(order_id)
        ln = next((x for x in doc["lines"] if x["product_id"] == product_id), None)
        if ln is None:
            raise ValueError("no such line")
        with self.engine.begin() as conn:
            self._line_to(conn, doc, ln, "RESCHEDULED", "owner", "owner moved the slot")
            self._line_to(conn, doc, ln, "SCHEDULED", "system", "new slot booked (simulated)")
            ln["eta_day"] = max(ln["eta_day"] or 0, doc["sim_day"]) + 2
            self._save(doc, conn)
        return self.view(order_id)

    def cancel(self, order_id: str) -> dict:
        doc = self._load(order_id)
        if any(ln["status"] == "ACTIVE" for ln in doc["lines"]) and doc["status"] == "COMPLETED":
            raise IllegalTransition("an active order can't be cancelled here")
        with self.engine.begin() as conn:
            for ln in doc["lines"]:
                if ln["status"] not in TERMINAL_LINE:
                    self._line_to(conn, doc, ln, "CANCELLED", "owner", "order cancelled")
            self._order_to(conn, doc, "CANCELLED", "owner", "owner cancelled")
            self._save(doc, conn)
        return self.view(order_id)

    # ------------------------------------------------------------ reads
    def view(self, order_id: str) -> dict:
        doc = self._load(order_id)
        with self.engine.connect() as conn:
            msgs = conn.execute(select(order_messages.c.text, order_messages.c.sim_day)
                                .where(order_messages.c.order_id == order_id).order_by(order_messages.c.seq)).all()
            events = conn.execute(select(order_events).where(order_events.c.order_id == order_id)
                                  .order_by(order_events.c.seq)).mappings().all()
        return {
            "order_id": doc["order_id"], "status": doc["status"], "hold_reason": doc["hold_reason"],
            "sim_day": doc["sim_day"], "quote_version": doc["quote_versions"][-1]["version"],
            "quote": doc["quote_versions"][-1]["quote"], "kyc_case_id": doc["kyc_case_id"],
            "substitute_offer": doc["substitute_offer"],
            "lines": [{**ln, "days_left": (max(0, ln["eta_day"] - doc["sim_day"]) if ln["eta_day"] is not None else None)}
                      for ln in doc["lines"]],
            "messages": [{"text": t, "sim_day": d, "label": "Simulated message, not sent"} for t, d in msgs],
            "events": [{"product_id": e["product_id"], "from": e["from_state"], "to": e["to_state"],
                        "actor": e["actor"], "trigger": e["trigger"]} for e in events],
            "labels": {"eta": "indicative, from the catalogue's typical install days", "fulfilment": "simulated"},
        }

    def session_of(self, order_id: str) -> str:
        return self._load(order_id)["session_id"]

    def open_orders_for_session(self, session_id: str) -> list[str]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(orders.c.order_id, orders.c.doc).where(orders.c.session_id == session_id)).all()
        return [oid for oid, d in rows if json.loads(d)["status"] not in {"CANCELLED", "COMPLETED"}]

    def delete_for_session(self, session_id: str) -> int:
        with self.engine.begin() as conn:
            ids = [r[0] for r in conn.execute(select(orders.c.order_id).where(orders.c.session_id == session_id))]
            for t in (order_events, order_messages):
                conn.execute(delete(t).where(t.c.order_id.in_(ids)))
            conn.execute(delete(orders).where(orders.c.order_id.in_(ids)))
        return len(ids)
