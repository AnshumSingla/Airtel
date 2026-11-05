"""Catalogue model, parsed from the `products` table or the CSV."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from sqlalchemy import Engine, select

from app.data.schema import products

# Segment names in smb_leads.csv -> codes used by the catalogue's target_segments.
SEGMENT_CODES = {
    "Micro retail & services": "micro",
    "Professional offices": "prof",
    "Small multi-site businesses": "multi",
    "Small manufacturers": "mfg",
}


@dataclass(frozen=True)
class Product:
    product_id: str
    category: str
    name: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup_fee: int
    min_contract_months: int
    city_tiers: frozenset[int]
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: tuple[str, ...]
    install_days: int
    target_segments: frozenset[str]

    @classmethod
    def from_row(cls, r: Mapping) -> "Product":
        return cls(
            product_id=r["product_id"],
            category=r["category"],
            name=r["product_name"],
            description=r["description"],
            unit=r["unit"],
            price_min=int(r["price_min_inr_per_month"]),
            price_max=int(r["price_max_inr_per_month"]),
            setup_fee=int(r["one_time_setup_inr"]),
            min_contract_months=int(r["min_contract_months"]),
            city_tiers=frozenset(int(t) for t in str(r["available_city_tiers"]).split(";")),
            min_employees=int(r["min_employees"]),
            min_sites=int(r["min_sites"]),
            requires_gstin=r["requires_gstin"] == "Y",
            requires_one_of=tuple(p for p in (r["requires_one_of"] or "").split("|") if p),
            install_days=int(r["typical_install_days"]),
            target_segments=frozenset(str(r["target_segments"]).split(";")),
        )


Catalogue = dict[str, Product]


def _index(rows: Iterable[Mapping]) -> Catalogue:
    return {p.product_id: p for p in (Product.from_row(r) for r in rows)}


def load_catalogue(engine: Engine) -> Catalogue:
    with engine.connect() as conn:
        return _index(conn.execute(select(products)).mappings().all())


def load_catalogue_csv(path: Path) -> Catalogue:
    with path.open(encoding="utf-8", newline="") as fh:
        return _index(csv.DictReader(fh))
