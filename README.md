# Udyam Digital

Submitted to **Airtel SYNC 2026, Digital Track**. Case: **"Project Udyam Digital"**, YTL Hackathon 2026, Enterprise Track A (fictional operator Accel Telecom / Accel Business).

A phone-first journey that lets a small-business owner find a suitable Accel Business bundle, see a reproducible quote, complete consented document checks and follow the order. English and Hindi end to end; other Indian languages are roadmap, behind a privacy launch gate for the AI service.

**Status:** specification revised over three rounds of adversarial review ([review.md](review.md)). **No application code, tests or CI yet**; every control in the docs is planned, and is tracked with its planned evidence in the [controls register](docs/POLICIES.md#15-controls-register). Prototype only: synthetic data, simulated integrations, no compliance or identity-verification claims.

| Doc | What's in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flows, module layout, failure modes, deployment |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Each stack/design choice with options weighed, plus open questions |
| [docs/POLICIES.md](docs/POLICIES.md) | Business rules: clock, consent purposes, retention, advisor inputs, LLM boundary, rate card, KYC outcomes, order states, back-office roles, labelling |
| [docs/WORKED_QUOTES.md](docs/WORKED_QUOTES.md) | Fully worked, rule-checked quotes from catalogue rows (future unit tests) |
| [docs/DATA_INSIGHTS.md](docs/DATA_INSIGHTS.md) | Funnel baseline and the signals in the leads data that shape features |
| [docs/DELIVERABLES.md](docs/DELIVERABLES.md) | Deadlines, deliverable checklist, deck outline, demo script, build timeline |
| [docs/COMPETITOR_SCAN.md](docs/COMPETITOR_SCAN.md) | How other public repos approach this case, and where we differ |

Planned stack: FastAPI (Python 3.11) single-instance modular monolith · React + Vite + TypeScript + Tailwind PWA · SQLite seeded from the CSVs at boot · local OCR (RapidOCR) · Gemini free tier behind a provider interface and a planned privacy gate (specified so that raw owner text never leaves the server), used only when the local parser can't fill a turn, plus short explanations (scripted mode as the zero-quota path) · baseline lead queue, with a scikit-learn model only if it beats it · one Docker image.

## Data

`data/raw/` holds the synthetic dataset supplied with the case (`YTL_TrackA_Udyam_Digital_Data.zip`); see [data/raw/README.md](data/raw/README.md). Every business, person and identifier in it is fictional. `deliverables/reference/` holds the case PDF and the submission template.
