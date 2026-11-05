from __future__ import annotations

import csv
from datetime import date

import pytest
from sqlalchemy import func, select

from app.data.schema import gstin_registry, historical_leads, products, udyam_registry
from app.data.seed import SeedError, read_csv, seed


def test_row_counts_match_data_pack_readme(seeded_engine):
    expected = {products: 25, historical_leads: 5000, gstin_registry: 3534, udyam_registry: 2723}
    with seeded_engine.connect() as conn:
        for table, n in expected.items():
            assert conn.execute(select(func.count()).select_from(table)).scalar_one() == n, table.name


def test_types_are_coerced(seeded_engine):
    with seeded_engine.connect() as conn:
        p01 = conn.execute(select(products).where(products.c.product_id == "P01")).mappings().one()
        lead = conn.execute(
            select(historical_leads).where(historical_leads.c.lead_id == "L00002")
        ).mappings().one()
    assert p01["price_min_inr_per_month"] == 999 and p01["requires_one_of"] is None
    assert lead["created_date"] == date(2026, 5, 12)
    assert lead["monthly_bundle_value_inr"] == 2620 and lead["nps_score"] == 9


def test_funnel_counts_match_readme(seeded_engine):
    """README 'Funnel at a glance': activated 368 of 5,000."""
    with seeded_engine.connect() as conn:
        activated = conn.execute(
            select(func.count()).where(historical_leads.c.outcome == "Activated")
        ).scalar_one()
    assert activated == 368


def test_reseed_is_idempotent(seeded_engine, data_dir):
    counts = seed(seeded_engine, data_dir)
    assert counts["products"] == 25 and counts["historical_leads"] == 5000


def test_header_mismatch_is_rejected(tmp_path):
    bad = tmp_path / "products.csv"
    with bad.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(["product_id", "unexpected"])
    with pytest.raises(SeedError, match="header mismatch"):
        read_csv(products, bad)
