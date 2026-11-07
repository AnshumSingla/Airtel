"""Audit log: who did what to which record (POLICIES.md §3, §11). Masked values only; kept 1 year."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Engine, Integer, MetaData, String, Table, Text, select

from app.privacy.masking import mask_text

audit_metadata = MetaData()
audit_events = Table(
    "audit_events", audit_metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("actor", String, nullable=False),
    Column("role", String, nullable=False),
    Column("action", String, nullable=False),
    Column("target", String, nullable=False),
    Column("detail", Text),
)


class AuditLog:
    def __init__(self, engine: Engine, reset: bool = True):
        self.engine = engine
        if reset:
            audit_metadata.drop_all(engine)
        audit_metadata.create_all(engine)

    def record(self, actor: str, role: str, action: str, target: str, detail: str = "") -> None:
        with self.engine.begin() as conn:
            conn.execute(audit_events.insert().values(at=datetime.now(timezone.utc), actor=actor, role=role,
                                                      action=action, target=mask_text(target)[:200],
                                                      detail=mask_text(detail)[:500]))

    def recent(self, limit: int = 100) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(audit_events).order_by(audit_events.c.seq.desc()).limit(limit)).mappings().all()
        return [{**dict(r), "at": r["at"].isoformat()} for r in rows]
