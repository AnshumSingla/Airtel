# Udyam Digital

Submitted to **Airtel SYNC 2026, Digital Track**. Case: **"Project Udyam Digital"**, YTL Hackathon 2026, Enterprise Track A (fictional operator Accel Telecom / Accel Business).

A phone-first journey that lets a small-business owner find a suitable Accel Business bundle, see a reproducible quote, complete consented document checks and follow the order. English and Hindi end to end; other Indian languages are roadmap, behind a privacy launch gate for the AI service.

**Status:** specification revised over five rounds of adversarial review ([review.md](review.md)). The backend foundation and the advisor are built and tested locally (see below); the frontend, KYC pipeline, orders, back office and CI are not. Each control's real status is tracked in the [controls register](docs/POLICIES.md#15-controls-register). Prototype only: synthetic data, simulated integrations, no compliance or identity-verification claims.

| Doc | What's in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flows, module layout, failure modes, deployment |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Each stack/design choice with options weighed, plus open questions |
| [docs/POLICIES.md](docs/POLICIES.md) | Business rules: clock, consent purposes, retention, advisor inputs, LLM boundary, rate card, KYC outcomes, order states, back-office roles, labelling |
| [docs/WORKED_QUOTES.md](docs/WORKED_QUOTES.md) | Fully worked, rule-checked quotes from catalogue rows (future unit tests) |
| [docs/DATA_INSIGHTS.md](docs/DATA_INSIGHTS.md) | Funnel baseline and the signals in the leads data that shape features |
| [docs/DELIVERABLES.md](docs/DELIVERABLES.md) | Deadlines, deliverable checklist, deck outline, demo script, build timeline |
| [docs/COMPETITOR_SCAN.md](docs/COMPETITOR_SCAN.md) | How other public repos approach this case, and where we differ |

Planned stack: FastAPI (Python 3.11) single-instance modular monolith · React + Vite + TypeScript + Tailwind PWA · SQLite seeded from the CSVs at boot · local OCR (RapidOCR) · Gemini free tier behind a provider interface and a privacy gate (built and red-team tested locally, so that raw owner text never leaves the server), used only when the local parser can't fill a turn, plus short explanations (scripted mode as the zero-quota path) · baseline lead queue, with a scikit-learn model only if it beats it · one Docker image.

## Backend: what's built so far (branch `build/foundation`)

| Area | State | Code | Evidence |
|---|---|---|---|
| CSV → SQLite seed at boot, demo clock | Built, tested | `backend/app/data/`, `clock.py` | `tests/test_seed.py` |
| GSTIN / Udyam validation, OCR repair candidates, masking | Built, tested | `app/registry/identifiers.py`, `app/privacy/masking.py` | every registry identifier validates |
| Catalogue rules, demo rate card, recommender | Built, tested | `app/catalogue/`, `app/pricing/` | reproduces every figure in `docs/WORKED_QUOTES.md` |
| Advisor (EN / HI / Hinglish parser, buttons, summary card, recommendation) | Built, tested | `app/advisor/` | `tests/test_advisor.py`, `tests/test_api.py` |
| Privacy gate in front of Gemini | Built, tested | `app/privacy_gate/` | `evidence/privacy_gate/report.md` |
| Gemini client (REST, model chain, rate limiter); off unless `ADVISOR_MODE=llm` + key + passing self-test | Built, tested with fakes; **not yet run against the real API** | `app/llm/` | `tests/test_llm_client.py` |
| OCR spike on all 47 KYC images | Done | `backend/scripts/` | `evidence/ocr_spike/` |
| Consent ledger, KYC pipeline, orders/tracker, back office, sessions/CSRF security, frontend, CI | **Not built yet** | | |

Run it (Windows, Python 3.11):

```bash
cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
```

```bash
cd backend && .venv/Scripts/python -m pytest
```

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload
```

The advisor runs in scripted mode by default. To try Gemini, set `ADVISOR_MODE=llm` and `GEMINI_API_KEY` (optionally `GEMINI_MODELS`, `GEMINI_RPM`, `GEMINI_RPD`). The privacy-gate self-test still has to pass at start-up before any call is made. API docs are served at `http://localhost:8000/docs`.

## Data

`data/raw/` holds the synthetic dataset supplied with the case (`YTL_TrackA_Udyam_Digital_Data.zip`); see [data/raw/README.md](data/raw/README.md). Every business, person and identifier in it is fictional. `deliverables/reference/` holds the case PDF and the submission template.
