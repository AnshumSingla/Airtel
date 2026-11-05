"""FastAPI entry point.

Run locally from the ``backend`` folder:

    .venv/Scripts/python -m uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.clock import FixedClock, SystemClock
from app.config import load_settings
from app.data.schema import products
from app.data.seed import make_engine, seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    engine = make_engine(settings.db_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.clock = (
        FixedClock(settings.demo_business_date) if settings.clock_mode == "demo" else SystemClock()
    )
    # Demo instance: rebuilt from the synthetic CSVs at every boot (ARCHITECTURE.md §7).
    app.state.seed_counts = seed(engine, settings.data_dir)
    yield
    engine.dispose()


app = FastAPI(title="Udyam Digital", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    clock = app.state.clock
    return {
        "status": "ok",
        "business_as_of": clock.business_as_of().isoformat(),
        "demo_clock": clock.is_fixture,
        "seeded": app.state.seed_counts,
    }


@app.get("/api/catalogue")
def catalogue() -> list[dict]:
    """The product catalogue. Contains no personal data."""
    with app.state.engine.connect() as conn:
        rows = conn.execute(select(products).order_by(products.c.product_id)).mappings().all()
    return [dict(r) for r in rows]
