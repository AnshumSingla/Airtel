"""Runtime settings, read once from the environment.

Every setting has a safe default for local demo runs. Secrets (API keys,
encryption keys, staff passwords) are never given defaults here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    # "demo" uses the fixture clock from the data pack (POLICIES.md §1);
    # "live" uses the real date.
    clock_mode: str
    demo_business_date: date

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("UDYAM_DATA_DIR", REPO_ROOT / "data" / "raw"))
    db_path = Path(os.environ.get("UDYAM_DB_PATH", REPO_ROOT / "backend" / "udyam.db"))
    clock_mode = os.environ.get("UDYAM_CLOCK_MODE", "demo")
    if clock_mode not in {"demo", "live"}:
        raise ValueError(f"UDYAM_CLOCK_MODE must be 'demo' or 'live', got {clock_mode!r}")
    return Settings(
        data_dir=data_dir,
        db_path=db_path,
        clock_mode=clock_mode,
        # The data pack README says to use 2026-07-15 as "today" for date checks.
        demo_business_date=date(2026, 7, 15),
    )
