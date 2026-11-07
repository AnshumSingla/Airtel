"""Injected business clock (POLICIES.md §1).

All date-based rules ask a Clock for ``business_as_of`` instead of calling
``date.today()``, so demo mode can use the data pack's fixed date and tests
can pin any date they need.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


class Clock(Protocol):
    def business_as_of(self) -> date: ...

    @property
    def is_fixture(self) -> bool: ...


@dataclass(frozen=True)
class FixedClock:
    """Demo/test clock pinned to one date. The UI shows a 'Demo date' badge for it."""

    day: date

    def business_as_of(self) -> date:
        return self.day

    @property
    def is_fixture(self) -> bool:
        return True


class SystemClock:
    """Live clock: the real current date."""

    def business_as_of(self) -> date:
        return date.today()

    @property
    def is_fixture(self) -> bool:
        return False
