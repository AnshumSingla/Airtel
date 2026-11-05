"""Consent ledger, shown to owners as "Your choices" (POLICIES.md §2).

Append-only events. When a session is deleted its events are unlinked: the
session id is replaced by a random tombstone, so the event still shows that a
choice was made and when, but can't be connected to anyone.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Engine, MetaData, String, Table, select, update

PURPOSES = {"P1", "P2", "P3", "P4", "P5", "P6"}
DECISIONS = {"given", "declined", "withdrawn"}

consent_metadata = MetaData()
consent_events = Table(
    "consent_events", consent_metadata,
    Column("event_id", String, primary_key=True),
    Column("link", String, nullable=False, index=True),        # session id, or a tombstone once unlinked
    Column("purpose", String, nullable=False),
    Column("decision", String, nullable=False),
    Column("notice_version", String, nullable=False),
    Column("language", String, nullable=False),
    Column("channel", String, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
)


class ConsentLedger:
    def __init__(self, engine: Engine, reset: bool = True):
        self.engine = engine
        if reset:
            consent_metadata.drop_all(engine)
        consent_metadata.create_all(engine)

    def record(self, session_id: str, purpose: str, decision: str, notice_version: str,
               language: str = "en", channel: str = "web") -> str:
        if purpose not in PURPOSES or decision not in DECISIONS:
            raise ValueError("unknown purpose or decision")
        event_id = secrets.token_hex(12)
        with self.engine.begin() as conn:
            conn.execute(consent_events.insert().values(
                event_id=event_id, link=session_id, purpose=purpose, decision=decision,
                notice_version=notice_version, language=language, channel=channel,
                at=datetime.now(timezone.utc)))
        return event_id

    def has(self, session_id: str, purpose: str) -> bool:
        with self.engine.connect() as conn:
            last = conn.execute(select(consent_events.c.decision)
                                .where(consent_events.c.link == session_id, consent_events.c.purpose == purpose)
                                .order_by(consent_events.c.at.desc(), consent_events.c.event_id.desc())).first()
        return bool(last and last[0] == "given")

    def events(self, link: str) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(consent_events).where(consent_events.c.link == link)
                                                  .order_by(consent_events.c.at)).mappings()]

    def unlink(self, session_id: str) -> int:
        tombstone = "unlinked:" + secrets.token_hex(12)
        with self.engine.begin() as conn:
            return conn.execute(update(consent_events).where(consent_events.c.link == session_id)
                                .values(link=tombstone)).rowcount
