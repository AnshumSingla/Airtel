"""FastAPI entry point.

Run locally from the ``backend`` folder:

    .venv/Scripts/python -m uvicorn app.main:app --reload

Environment (all optional): UDYAM_DB_PATH, UDYAM_CLOCK_MODE (demo|live),
ADVISOR_MODE (scripted|llm, default scripted), GEMINI_API_KEY, GEMINI_MODELS
(comma-separated, first is tried first), GEMINI_RPM, GEMINI_RPD,
ADVISOR_LLM_EXPLAIN (1 to let Gemini rephrase reason sentences).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.advisor.api import router as advisor_router
from app.kyc.api import router as kyc_router
from app.kyc.ocr import OcrPool
from app.kyc.registry import DbRegistry
from app.kyc.service import KycService
from app.orders.api import router as orders_router
from app.orders.service import OrderService
from app.privacy.consent import ConsentLedger
from app.privacy.crypto import FieldCipher
from app.advisor.lexicon import build_lexicon
from app.advisor.service import AdvisorService
from app.catalogue.models import load_catalogue
from app.catalogue.recommend import build_segment_stats
from app.clock import FixedClock, SystemClock
from app.config import load_settings
from app.data.schema import products
from app.data.seed import make_engine, seed
from app.llm.client import LLMClient, ModelChain, RateLimiter
from app.privacy_gate.gate import PrivacyGate
from app.privacy_gate.redteam import run_redteam

log = logging.getLogger("udyam")


def build_llm_client(gate: PrivacyGate, allowed: set[str]) -> tuple[LLMClient, dict]:
    """Enable Gemini only if every condition holds (POLICIES.md §15 stop condition)."""
    redteam = run_redteam(gate)
    status = {"redteam_passed": redteam.passed, "redteam_leaks": len(redteam.leaks)}
    mode = os.environ.get("ADVISOR_MODE", "scripted")
    key = os.environ.get("GEMINI_API_KEY", "")
    reason = ""
    if not redteam.passed:
        reason = "privacy-gate self-test failed"
    elif mode != "llm":
        reason = "ADVISOR_MODE is scripted"
    elif not key:
        reason = "GEMINI_API_KEY not set"
    if reason:
        status["llm"] = f"disabled: {reason}"
        return LLMClient(None, allowed, enabled=False, disabled_reason=reason), status
    from app.llm.gemini import GeminiProvider  # imported only when enabled

    models = [m.strip() for m in os.environ.get("GEMINI_MODELS", "gemini-flash-lite-latest,gemini-flash-latest").split(",") if m.strip()]
    rpm, rpd = int(os.environ.get("GEMINI_RPM", "5")), int(os.environ.get("GEMINI_RPD", "20"))
    chain = ModelChain(GeminiProvider(key), models, {m: RateLimiter(rpm, rpd) for m in models})
    status["llm"] = f"enabled: {', '.join(models)} (rpm {rpm}, rpd {rpd} per model)"
    return LLMClient(chain, allowed, enabled=True), status


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
    lex = build_lexicon(engine)
    gate = PrivacyGate(lex)
    llm, app.state.llm_status = build_llm_client(gate, lex.allowed_tokens())
    log.info("advisor LLM %s", app.state.llm_status["llm"])
    cat = load_catalogue(engine)
    app.state.advisor = AdvisorService(engine, lex, cat, build_segment_stats(engine), gate, llm,
                                       explain_with_llm=os.environ.get("ADVISOR_LLM_EXPLAIN") == "1")
    app.state.consent = ConsentLedger(engine)
    cipher = FieldCipher()
    if cipher.ephemeral and settings.clock_mode != "demo":
        raise RuntimeError("KYC_FIELD_KEYS must be set outside demo mode")
    app.state.kyc_key = "ephemeral (demo; data resets on restart)" if cipher.ephemeral else "from KYC_FIELD_KEYS"
    app.state.ocr_pool = OcrPool()
    app.state.kyc = KycService(engine, DbRegistry(engine), app.state.consent, cipher, app.state.clock, cat,
                               pool=app.state.ocr_pool)
    app.state.orders = OrderService(engine, cat)
    yield
    app.state.ocr_pool.shutdown()
    engine.dispose()


app = FastAPI(title="Udyam Digital", lifespan=lifespan)
app.include_router(advisor_router)
app.include_router(kyc_router)
app.include_router(orders_router)


@app.get("/api/health")
def health() -> dict:
    clock = app.state.clock
    return {
        "status": "ok",
        "business_as_of": clock.business_as_of().isoformat(),
        "demo_clock": clock.is_fixture,
        "seeded": app.state.seed_counts,
        "advisor": app.state.llm_status,
        "kyc_field_key": app.state.kyc_key,
    }


@app.get("/api/catalogue")
def catalogue() -> list[dict]:
    """The product catalogue. Contains no personal data."""
    with app.state.engine.connect() as conn:
        rows = conn.execute(select(products).order_by(products.c.product_id)).mappings().all()
    return [dict(r) for r in rows]


# Serve the built PWA (frontend/dist) from the same origin as the API, if it has been built.
_DIST = load_settings().data_dir.parents[1] / "frontend" / "dist"
if _DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_DIST, html=True), name="pwa")
