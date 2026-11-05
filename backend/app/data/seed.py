"""Load the synthetic CSV data pack into SQLite.

The hosted demo is ephemeral by design (ARCHITECTURE.md §7): the database is
rebuilt from the CSVs at every boot, so this loader drops and recreates the
seed tables each time it runs.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Date, Engine, Integer, Table, create_engine, event

from app.data.schema import SEED_FILES, metadata


class SeedError(ValueError):
    """A CSV doesn't match the expected schema."""


def _check_header(table: Table, fieldnames: list[str] | None) -> None:
    expected = {c.name for c in table.columns}
    got = set(fieldnames or [])
    if got != expected:
        missing, extra = expected - got, got - expected
        raise SeedError(f"{table.name}: header mismatch (missing={sorted(missing)}, extra={sorted(extra)})")


def _coerce(table: Table, row: dict[str, str], line_no: int) -> dict[str, Any]:
    if None in row:  # more values than header columns
        raise SeedError(f"{table.name} line {line_no}: too many values")
    out: dict[str, Any] = {}
    for col in table.columns:
        value = row[col.name]
        if value is None:  # fewer values than header columns
            raise SeedError(f"{table.name} line {line_no}: missing value for '{col.name}'")
        raw = value.strip()
        if raw == "":
            if not col.nullable:
                raise SeedError(f"{table.name} line {line_no}: '{col.name}' is empty but required")
            out[col.name] = None
        elif isinstance(col.type, Integer):
            # Some generators write integers as "12.0"; accept that, reject real fractions.
            number = float(raw)
            if not number.is_integer():
                raise SeedError(f"{table.name} line {line_no}: '{col.name}'={raw!r} is not an integer")
            out[col.name] = int(number)
        elif isinstance(col.type, Date):
            out[col.name] = date.fromisoformat(raw)
        else:
            out[col.name] = raw
    return out


def read_csv(table: Table, path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        _check_header(table, reader.fieldnames)
        # DictReader line numbers count the header as line 1.
        return [_coerce(table, row, reader.line_num) for row in reader]


def make_engine(db_url: str) -> Engine:
    engine = create_engine(db_url, future=True)

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def seed(engine: Engine, data_dir: Path) -> dict[str, int]:
    """Drop and reload every seed table. Returns row counts per table."""
    tables = list(SEED_FILES.values())
    metadata.drop_all(engine, tables=tables)
    metadata.create_all(engine, tables=tables)
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        for file_name, table in SEED_FILES.items():
            rows = read_csv(table, data_dir / file_name)
            if rows:
                conn.execute(table.insert(), rows)
            counts[table.name] = len(rows)
    return counts
