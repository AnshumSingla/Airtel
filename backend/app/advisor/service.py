"""Advisor conversation: local parser first, gated LLM only when needed, rules engine decides.

POLICIES.md §2 (P1 session-only processing), §4 (inputs, conflicts, question
cap), §5 (privacy gate), §6 (recommendation), §14 (claims).
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Engine, MetaData, String, Table, Text, delete, select

from app.advisor import prompts
from app.advisor.explain import exclusion_sentence, guard_sentences, template_sentence
from app.advisor.lexicon import Lexicon
from app.advisor.parser import parse
from app.catalogue.models import Catalogue
from app.catalogue.recommend import SegmentStats, default_quantity, profile_from_slots, recommend
from app.catalogue.rules import check_bundle
from app.llm.client import LLMClient, LLMUnavailable
from app.pricing.quote import ILLUSTRATIVE_TAX_PERCENT, RATE_CARD_VERSION, build_quote, unit_price
from app.privacy_gate.gate import PrivacyGate, explanation_payload, slot_extraction_payload

SESSION_IDLE = timedelta(hours=24)       # P1 without P4 (POLICIES.md §2)
MAX_LLM_CALLS = 12                       # per session (DECISIONS.md D6a)
MAX_TURNS_BEFORE_OFFER = 8               # POLICIES.md §4 question cap
MAX_QUANTITY = 200
P1_NOTICE_VERSION = "p1-2026-11-05"

journey_metadata = MetaData()
advisor_sessions = Table(
    "advisor_sessions", journey_metadata,
    Column("session_id", String, primary_key=True),
    Column("state", Text, nullable=False),            # JSON; raw chat lives only here, deleted with the row
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_activity", DateTime(timezone=True), nullable=False),
)

SLOT_LIMITS = {"employees": (1, 500), "sites": (1, 50)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Turn:
    reply: str
    language: str
    status: str                              # asking | confirm | offer_partial | handoff_requested
    expecting: str | None = None
    buttons: list[dict] = field(default_factory=list)
    summary: dict | None = None
    consent_card: dict | None = None
    used_llm: bool = False


class SessionNotFound(KeyError):
    pass


class AdvisorService:
    def __init__(self, engine: Engine, lex: Lexicon, cat: Catalogue, stats: SegmentStats,
                 gate: PrivacyGate, llm: LLMClient, explain_with_llm: bool = False, reset: bool = True):
        self.engine, self.lex, self.cat, self.stats = engine, lex, cat, stats
        self.gate, self.llm, self.explain_with_llm = gate, llm, explain_with_llm
        if reset:  # demo instance: sessions don't survive a restart (ARCHITECTURE.md §7)
            journey_metadata.drop_all(engine)
        journey_metadata.create_all(engine)

    # ------------------------------------------------------------ storage
    def _load(self, sid: str) -> dict:
        with self.engine.connect() as conn:
            row = conn.execute(select(advisor_sessions).where(advisor_sessions.c.session_id == sid)).mappings().first()
        if row is None:
            raise SessionNotFound(sid)
        last = row["last_activity"]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if _now() - last > SESSION_IDLE:
            self.end(sid)
            raise SessionNotFound(sid)
        return json.loads(row["state"])

    def _save(self, sid: str, state: dict, new: bool = False) -> None:
        now = _now()
        with self.engine.begin() as conn:
            if new:
                conn.execute(advisor_sessions.insert().values(session_id=sid, state=json.dumps(state),
                                                              created_at=now, last_activity=now))
            else:
                conn.execute(advisor_sessions.update().where(advisor_sessions.c.session_id == sid)
                             .values(state=json.dumps(state), last_activity=now))

    def end(self, sid: str) -> bool:
        """'End and delete' (POLICIES.md §2): the session, its chat and drafts are gone now."""
        with self.engine.begin() as conn:
            return conn.execute(delete(advisor_sessions).where(advisor_sessions.c.session_id == sid)).rowcount > 0

    def purge_idle(self) -> int:
        """Retention job: delete sessions idle for more than 24 h."""
        with self.engine.begin() as conn:
            return conn.execute(delete(advisor_sessions)
                                .where(advisor_sessions.c.last_activity < _now() - SESSION_IDLE)).rowcount

    # ------------------------------------------------------------ conversation
    def start(self, language: str = "en") -> tuple[str, Turn]:
        sid = secrets.token_urlsafe(24)
        state = {"slots": {}, "needs": [], "needs_asked": False, "language": language, "turns": 0,
                 "llm_calls": 0, "expecting": "segment", "history": [], "p1_notice": P1_NOTICE_VERSION}
        self._save(sid, state, new=True)
        return sid, self._ask(state, "segment")

    def message(self, sid: str, text: str) -> Turn:
        state = self._load(sid)
        text = (text or "").strip()[:500]
        consent_card = None
        used_llm = False
        before = (json.dumps(state["slots"], sort_keys=True), tuple(state["needs"]))
        if text.startswith("__"):
            special = self._apply_action(state, text)
            if special:
                self._save(sid, state)
                return special
        else:
            parsed = parse(text, self.lex, state.get("expecting"))
            # Identifiers typed into chat are never stored (POLICIES.md §2 rule 1): keep the stripped text only.
            state["history"].append(parsed.clean_text.strip())
            if parsed.language != "en" or state["turns"] == 0:
                state["language"] = parsed.language
            if "gstin" in parsed.identifiers_found:
                consent_card = {"type": "gstin_check", "purpose": "P2",
                                "text": prompts.question("gstin_consent", state["language"])}
            new_slots = {k: v for k, v in parsed.slots.items() if state["slots"].get(k) != v}
            state["slots"].update(parsed.slots)          # latest answer wins (POLICIES.md §4)
            new_needs = parsed.needs - set(state["needs"])
            state["needs"] = sorted(set(state["needs"]) | parsed.needs)
            if parsed.needs and state.get("expecting") == "needs":
                state["needs_asked"] = True
            if not new_slots and not new_needs and consent_card is None:
                used_llm = self._try_llm_extract(state, text)
        state["turns"] += 1
        progressed = (json.dumps(state["slots"], sort_keys=True), tuple(state["needs"])) != before
        turn = self._next(state)
        turn.consent_card, turn.used_llm = consent_card, used_llm
        if (not progressed and consent_card is None and turn.status == "asking"
                and not text.startswith("__") and state.get("expecting") != "needs"):
            turn.reply = prompts.question("unclear", state["language"]) + " " + turn.reply
        self._save(sid, state)
        return turn

    def _apply_action(self, state: dict, action: str) -> Turn | None:
        lang = state["language"]
        if action.startswith("__set:"):
            key, _, raw = action[6:].partition("=")
            value = {"true": True, "false": False}.get(raw, raw)
            if key in {"employees", "sites", "city_tier"}:
                value = int(raw)
            self._set_slot(state, key, value)
        elif action.startswith("__need:"):
            # One tap or several at once ("__need:P19,P23"); only catalogue products are accepted.
            picked = {p for p in action[7:].split(",") if p in self.cat and p in prompts.NEED_CODES.values()}
            state["needs_asked"] = True
            state["needs"] = sorted(set(state["needs"]) | picked)
        elif action == "__handoff":
            return Turn(prompts.question("too_many_turns", lang), lang, "handoff_requested")
        elif action == "__partial":
            for slot, default in (("segment", "micro"), ("city_tier", 2), ("employees", 3), ("sites", 1),
                                  ("has_gstin", False)):
                state["slots"].setdefault(slot, default)
                state.setdefault("assumed", []).append(slot)
            state["needs_asked"] = True
        return None

    def _set_slot(self, state: dict, key: str, value) -> None:
        if key == "segment" and value in {"micro", "prof", "multi", "mfg"}:
            state["slots"]["segment"] = value
        elif key == "city_tier" and value in {1, 2}:
            state["slots"]["city_tier"] = value
        elif key in SLOT_LIMITS and isinstance(value, int) and SLOT_LIMITS[key][0] <= value <= SLOT_LIMITS[key][1]:
            state["slots"][key] = value
        elif key == "has_gstin" and isinstance(value, bool):
            state["slots"]["has_gstin"] = value

    def _try_llm_extract(self, state: dict, text: str) -> bool:
        if not self.llm.enabled or state["llm_calls"] >= MAX_LLM_CALLS:
            return False
        gated = self.gate.apply(text)
        if not gated.may_call:
            return False
        missing = self._missing(state)
        try:
            state["llm_calls"] += 1
            result = self.llm.send(prompts.EXTRACT_SYSTEM,
                                   slot_extraction_payload(gated, state["slots"], missing, state["language"]),
                                   prompts.EXTRACT_SCHEMA)
        except (LLMUnavailable, ValueError):
            return False
        if not isinstance(result, dict):
            return False
        for key in ("segment", "city_tier", "employees", "sites", "has_gstin"):   # validate each value
            if key in result:
                self._set_slot(state, key, result[key])
        needs = {prompts.NEED_CODES[n] for n in result.get("needs", []) if n in prompts.NEED_CODES}
        if needs:
            state["needs"] = sorted(set(state["needs"]) | needs)
        return True

    def _missing(self, state: dict) -> list[str]:
        return [s for s in prompts.REQUIRED_SLOTS if s not in state["slots"]]

    def _ask(self, state: dict, slot: str) -> Turn:
        state["expecting"] = slot
        lang = state["language"]
        return Turn(prompts.question(slot, lang), lang, "asking", slot, prompts.buttons(slot, lang))

    def _next(self, state: dict) -> Turn:
        missing = self._missing(state)
        lang = state["language"]
        if missing:
            if state["turns"] >= MAX_TURNS_BEFORE_OFFER:
                return Turn(prompts.question("too_many_turns", lang), lang, "offer_partial",
                            buttons=prompts.buttons("too_many_turns", lang))
            return self._ask(state, missing[0])
        if not state["needs_asked"]:
            state["needs_asked"] = True
            return self._ask(state, "needs")
        state["expecting"] = None
        return Turn(prompts.question("confirm", lang), lang, "confirm", summary=self.summary_card(state))

    def summary_card(self, state: dict) -> dict:
        s = state["slots"]
        return {"business_type": s.get("business_type"), "segment": s.get("segment"), "city": s.get("city"),
                "city_tier": s.get("city_tier"), "employees": s.get("employees"), "sites": s.get("sites"),
                "has_gstin": s.get("has_gstin"), "needs": list(state["needs"]),
                "budget": s.get("budget"), "assumed": state.get("assumed", [])}

    # ------------------------------------------------------------ recommendation
    def confirm(self, sid: str, edits: dict | None = None) -> dict:
        state = self._load(sid)
        for key, value in (edits or {}).items():
            if key == "needs" and isinstance(value, list):
                state["needs"] = sorted(p for p in value if p in self.cat)
            elif key == "budget" and (value is None or (isinstance(value, int) and value > 0)):
                state["slots"]["budget"] = value
            elif key == "city" and isinstance(value, str) and value.lower() in self.lex.cities:
                city, tier, st = self.lex.cities[value.lower()]
                state["slots"].update(city=city, city_tier=tier, state=st)
            else:
                self._set_slot(state, key, value)
        missing = self._missing(state)
        if missing:
            raise ValueError(f"summary card is missing: {missing}")
        state["confirmed_card"] = self.summary_card(state)
        self._save(sid, state)
        return self._recommendation(state)

    def _recommendation(self, state: dict) -> dict:
        lang = state["language"]
        slots = state["slots"]
        profile = profile_from_slots(slots)
        rec = recommend(self.cat, self.stats, profile, set(state["needs"]), slots.get("budget"))
        expected: dict[str, str] = {}
        for ln in rec.lines:
            for r in ln.reasons:
                if r.tag != "QTY_DEFAULT":
                    expected[f"{ln.product_id}:{r.code}"] = template_sentence(r, profile.segment, lang, ln.product_id)
        sentences, fallbacks = dict(expected), []
        if self.explain_with_llm and self.llm.enabled and state["llm_calls"] < MAX_LLM_CALLS:
            try:
                state["llm_calls"] += 1
                codes = [(k.split(":")[1], k.split(":")[0]) for k in expected]
                proposed = self.llm.send(prompts.EXPLAIN_SYSTEM, explanation_payload(codes, slots, lang),
                                         prompts.explain_schema(sorted(expected)))
                sentences, fallbacks = guard_sentences(self.cat, proposed, expected)
            except (LLMUnavailable, ValueError):
                pass
        q = rec.quote
        out_lines = []
        for ln, ql in zip(rec.lines, q.lines):
            p = self.cat[ln.product_id]
            reasons = []
            for r in ln.reasons:
                text = (template_sentence(r, profile.segment, lang, ln.product_id) if r.tag == "QTY_DEFAULT"
                        else sentences[f"{ln.product_id}:{r.code}"])
                reasons.append({"tag": r.tag, "text": text})
            if "INFO_OFF_TARGET" in ln.info:
                reasons.append({"tag": "INFO_OFF_TARGET",
                                "text": f"Listed by Accel for {', '.join(sorted(p.target_segments))} businesses."})
            out_lines.append({"product_id": p.product_id, "name": p.name, "description": p.description,
                              "unit": p.unit, "quantity": ql.quantity, "unit_monthly": ql.unit_monthly,
                              "monthly": ql.monthly, "one_time": ql.one_time, "term_months": ql.term_months,
                              "install_days": ql.install_days, "reasons": reasons})
        return {
            "summary": state["confirmed_card"],
            "lines": out_lines,
            "excluded": [{"product_id": e["product_id"], "name": self.cat[e["product_id"]].name,
                          "codes": e["codes"], "text": exclusion_sentence(e["codes"], lang), "source": e["source"]}
                         for e in rec.excluded],
            "dropped_for_budget": rec.dropped_for_budget,
            "notes": rec.notes,
            "quote": quote_dict(q),
            "addons": self._addons(state, {ln["product_id"] for ln in out_lines}),
            "explanation_fallbacks": fallbacks,
            "language": lang,
        }

    # ------------------------------------------------------------ quote editing and acceptance
    def _addons(self, state: dict, chosen: set[str], limit: int = 6) -> list[dict]:
        """On-target, eligible products not in the bundle, most chosen first (owner toggles them)."""
        profile = profile_from_slots(state["slots"])
        out = []
        for pid, p in self.cat.items():
            if pid in chosen or profile.segment not in p.target_segments:
                continue
            [c] = check_bundle(self.cat, profile, [pid, *chosen])[:1]
            if not c.eligible:
                continue
            qty, _ = default_quantity(self.cat, pid, profile.segment, profile.employees, profile.sites)
            out.append({"product_id": pid, "name": p.name, "description": p.description, "unit": p.unit,
                        "default_quantity": qty, "unit_monthly": unit_price(p), "setup_per_unit": p.setup_fee,
                        "share": round(self.stats.share(profile.segment, pid), 2)})
        out.sort(key=lambda a: (-a["share"], a["product_id"]))
        return out[:limit]

    def quote_preview(self, sid: str, items: list[dict]) -> dict:
        state = self._load(sid)
        return self._preview(state, items)

    def _preview(self, state: dict, items: list[dict]) -> dict:
        if "confirmed_card" not in state:
            raise ValueError("confirm the summary card first")
        clean: list[tuple[str, int]] = []
        for it in items:
            pid, qty = it.get("product_id"), it.get("quantity")
            if pid not in self.cat or not isinstance(qty, int) or not 1 <= qty <= MAX_QUANTITY:
                raise ValueError(f"invalid line {it!r}")
            if pid not in {c for c, _ in clean}:
                clean.append((pid, qty))
        profile = profile_from_slots(state["slots"])
        checks = {c.product_id: c for c in check_bundle(self.cat, profile, [p for p, _ in clean])}
        eligible = [(p, q) for p, q in clean if checks[p].eligible]
        q = build_quote(self.cat, eligible)
        lines = [{"product_id": ln.product_id, "name": ln.name, "unit": ln.unit, "quantity": ln.quantity,
                  "unit_monthly": ln.unit_monthly, "monthly": ln.monthly, "one_time": ln.one_time,
                  "term_months": ln.term_months, "install_days": ln.install_days,
                  "info": list(checks[ln.product_id].info)} for ln in q.lines]
        lang = state["language"]
        rejected = [{"product_id": p, "name": self.cat[p].name, "codes": list(checks[p].excluded),
                     "text": exclusion_sentence(list(checks[p].excluded), lang)} for p, _ in clean if not checks[p].eligible]
        return {"lines": lines, "rejected": rejected, "quote": quote_dict(q),
                "addons": self._addons(state, {p for p, _ in clean})}

    def accept(self, sid: str, items: list[dict]) -> dict:
        """Freeze an immutable quote version (POLICIES.md §7). Orders are not built yet."""
        state = self._load(sid)
        preview = self._preview(state, items)
        if preview["rejected"]:
            raise ValueError("remove the lines that can't be provided before accepting")
        if not preview["lines"]:
            raise ValueError("the quote is empty")
        versions = state.setdefault("quote_versions", [])
        snapshot = {"version": len(versions) + 1, "accepted_at": _now().isoformat(),
                    "rate_card": RATE_CARD_VERSION, "summary": state["confirmed_card"],
                    "lines": preview["lines"], "quote": preview["quote"]}
        versions.append(snapshot)
        self._save(sid, state)
        return snapshot

    def set_gstin_status(self, sid: str, status: str) -> None:
        """Result of a consented (P2) registry check. The GSTIN itself is not stored."""
        state = self._load(sid)
        state["slots"]["has_gstin"] = True
        state["slots"]["gstin_status"] = status
        self._save(sid, state)

    def slots(self, sid: str) -> dict:
        return dict(self._load(sid)["slots"])


def quote_dict(q) -> dict:
    return {"rate_card": RATE_CARD_VERSION, "label": "Demo rate card (assumptions listed)",
            "tax_label": f"Tax (illustrative {ILLUSTRATIVE_TAX_PERCENT}%)",
            "monthly_ex_tax": q.monthly_ex_tax, "monthly_tax": q.monthly_tax,
            "monthly_incl_tax": q.monthly_incl_tax, "one_time_ex_tax": q.one_time_ex_tax,
            "one_time_tax": q.one_time_tax, "one_time_incl_tax": q.one_time_incl_tax,
            "first_payment": q.first_payment, "slowest_install_days": q.slowest_install_days,
            "longest_term_months": q.longest_term_months}
