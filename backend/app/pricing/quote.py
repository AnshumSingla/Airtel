"""Demo rate card and quote builder (POLICIES.md §7).

- Unit monthly price: band midpoint, rounded half up to the rupee [ASSUMPTION].
- Setup: catalogue setup fee x quantity, charged once [DATA].
- Terms: per line item, each item's own minimum term [ASSUMPTION].
- Tax: illustrative uniform 18% on the recurring and the one-time totals,
  each rounded half up [ASSUMPTION; a mock rule, not a tax classification].
- First payment: month 1 recurring + all one-time charges, incl. tax.

All arithmetic is in whole rupees with integers, so results are exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.catalogue.models import Catalogue, Product

ILLUSTRATIVE_TAX_PERCENT = 18
RATE_CARD_VERSION = "demo-midpoint-v1"


def unit_price(p: Product) -> int:
    """Band midpoint, rounded half up: (min + max + 1) // 2 for integer bands."""
    return (p.price_min + p.price_max + 1) // 2


def tax_on(amount: int) -> int:
    """Illustrative 18% rounded half up to the rupee."""
    return (amount * ILLUSTRATIVE_TAX_PERCENT + 50) // 100


@dataclass(frozen=True)
class QuoteLine:
    product_id: str
    name: str
    unit: str
    quantity: int
    unit_monthly: int
    monthly: int
    setup_per_unit: int
    one_time: int
    term_months: int
    install_days: int


@dataclass(frozen=True)
class Quote:
    rate_card_version: str
    lines: tuple[QuoteLine, ...]
    monthly_ex_tax: int
    monthly_tax: int
    one_time_ex_tax: int
    one_time_tax: int

    @property
    def monthly_incl_tax(self) -> int:
        return self.monthly_ex_tax + self.monthly_tax

    @property
    def one_time_incl_tax(self) -> int:
        return self.one_time_ex_tax + self.one_time_tax

    @property
    def first_payment(self) -> int:
        return self.monthly_incl_tax + self.one_time_incl_tax

    @property
    def longest_term_months(self) -> int:
        return max((ln.term_months for ln in self.lines), default=0)

    @property
    def slowest_install_days(self) -> int:
        return max((ln.install_days for ln in self.lines), default=0)


def build_quote(cat: Catalogue, items: Iterable[tuple[str, int]]) -> Quote:
    lines = []
    for product_id, qty in items:
        if qty < 1:
            raise ValueError(f"{product_id}: quantity must be at least 1, got {qty}")
        p = cat[product_id]
        u = unit_price(p)
        lines.append(QuoteLine(p.product_id, p.name, p.unit, qty, u, u * qty, p.setup_fee,
                               p.setup_fee * qty, p.min_contract_months, p.install_days))
    monthly = sum(ln.monthly for ln in lines)
    one_time = sum(ln.one_time for ln in lines)
    return Quote(RATE_CARD_VERSION, tuple(lines), monthly, tax_on(monthly), one_time, tax_on(one_time))
