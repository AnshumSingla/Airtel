"""Referral attribution: credit, not access (POLICIES.md §11).

A referral code captured when a session starts records which partner gets
credit. It grants no access to the application; only P5 naming that partner
does. Partners see their referrals only as aggregate counts, shown once a
count reaches 5, so one customer can't be singled out.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Engine, MetaData, String, Table, delete, select

MIN_COUNT_SHOWN = 5

referral_metadata = MetaData()
attributions = Table(
    "attributions", referral_metadata,
    Column("session_id", String, primary_key=True),
    Column("partner_id", String, nullable=False, index=True),
    Column("at", DateTime(timezone=True), nullable=False),
)


class Referrals:
    def __init__(self, engine: Engine, reset: bool = True):
        self.engine = engine
        if reset:
            referral_metadata.drop_all(engine)
        referral_metadata.create_all(engine)

    def attribute(self, session_id: str, partner_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(attributions).where(attributions.c.session_id == session_id))
            conn.execute(attributions.insert().values(session_id=session_id, partner_id=partner_id,
                                                      at=datetime.now(timezone.utc)))

    def sessions_for(self, partner_id: str) -> list[str]:
        with self.engine.connect() as conn:
            return [r[0] for r in conn.execute(select(attributions.c.session_id)
                                               .where(attributions.c.partner_id == partner_id))]

    def delete_for_session(self, session_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(attributions).where(attributions.c.session_id == session_id))

    @staticmethod
    def shown(count: int) -> int | str:
        return count if count >= MIN_COUNT_SHOWN else f"fewer than {MIN_COUNT_SHOWN}"
