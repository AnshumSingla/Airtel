# Udyam Digital

Airtel SYNC 2026, Digital Track. A phone-first journey that lets a small-business owner discover the right Accel Business bundle, buy it, complete KYC and track activation in their own language, with minimal human effort.

**Status:** architecture and stack decided, no application code yet.

| Doc | What's in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flows, module layout, failure modes, deployment |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Each stack/design choice with options weighed, plus open questions |
| [docs/DATA_INSIGHTS.md](docs/DATA_INSIGHTS.md) | Funnel baseline and the signals in the leads data that shape features |
| [docs/DELIVERABLES.md](docs/DELIVERABLES.md) | Deadlines, deliverable checklist, deck outline, demo script, build timeline |
| [docs/COMPETITOR_SCAN.md](docs/COMPETITOR_SCAN.md) | How other public repos approach this case, and where we differ |

Planned stack: FastAPI (Python 3.11) modular monolith · React + Vite + TypeScript + Tailwind PWA · SQLite · local OCR (RapidOCR) · Gemini free tier behind a provider interface, used for conversation only (one call per turn, scripted fallback) · scikit-learn propensity model · one Docker image.

## Data

`data/raw/` holds the synthetic dataset supplied with the case (`YTL_TrackA_Udyam_Digital_Data.zip`); see [data/raw/README.md](data/raw/README.md). Every business, person and identifier in it is fictional. `deliverables/reference/` holds the case PDF and the submission template.
