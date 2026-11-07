"""Mock registry lookups backed by the synthetic data pack [SIMULATED] (POLICIES.md §8)."""

from __future__ import annotations

from sqlalchemy import Engine, select

from app.data.schema import gstin_registry, historical_leads, udyam_registry

REGISTRY_LABEL = "Mock registry (synthetic data pack, as of 15 Jul 2026)"


class DbRegistry:
    def __init__(self, engine: Engine):
        with engine.connect() as conn:
            self._gst = {r["gstin"]: dict(r) for r in conn.execute(select(gstin_registry)).mappings()}
            self._udy = {r["udyam_number"]: dict(r) for r in conn.execute(select(udyam_registry)).mappings()}
            # Simulated GSTIN -> Udyam link. The real Udyam portal links by PAN; the data
            # pack only links them through the leads file, so we use that.
            self._link = {g: u for g, u in conn.execute(
                select(historical_leads.c.gstin, historical_leads.c.udyam_number)
                .where(historical_leads.c.gstin.is_not(None), historical_leads.c.udyam_number.is_not(None)))}

    def gstin(self, gstin: str) -> dict | None:
        return self._gst.get(gstin)

    def udyam(self, number: str) -> dict | None:
        return self._udy.get(number)

    def udyam_for_gstin(self, gstin: str) -> str | None:
        return self._link.get(gstin)
