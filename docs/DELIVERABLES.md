# Deliverables and build plan

## Deadlines (from the Unstop page, checked 05 Nov 2026)

| What | When |
|---|---|
| Registration closes | 06 Nov 2026, 11:59 PM IST |
| Case release & detailed (prototype) submission round | 26 Oct – **07 Nov 2026, 11:59 PM IST** |
| Then | virtual presentation to Airtel leadership → top 15 → mentorship → Grand Finale at the Airtel office (15 min talk + 5 min Q&A) |

Team size: 2. Submission format for this round: **PDF and PPT**, file name **`TeamName_CampusName`**, a **7-slide** deck on the provided template (`deliverables/reference/Submission Template_Sync.pptx`, which is a cover slide plus one blank branded content slide).

## Everything the case asks for

| # | Deliverable (case PDF) | Where it lives | Notes |
|---|---|---|---|
| 1a | Working prototype: code repository | this repo (public on GitHub at submission) | README with one-command run |
| 1b | Demo video, max 3 minutes | `deliverables/demo.md` (link) | Recorded on a local run; script below |
| 2 | Solution architecture diagram | `docs/ARCHITECTURE.md` → exported PNG in deck | Components + data flows |
| 3 | Business case, ≤ 10 slides | deck (7 slides for this round) | Target customer, value, pricing/savings, rollout, risks |
| 4 | 1-page data privacy & security note | `deliverables/privacy_note.pdf` + deck appendix | Consent, minimisation, masking, retention |

Build challenge coverage:

| Required | Planned feature |
|---|---|
| Advisor (GenAI, asks about business, recommends from catalogue, explains why) | Chat + voice, EN/HI UI, replies in owner's language, rules-engine recommendation with reasons |
| Quote & checkout (one monthly price, toggle add-ons) | Quote screen with toggles, contract-length slider, GST and setup lines, savings vs current spend, mock e-sign |
| Smart KYC (upload, extraction, validation, mocked GSTIN/Udyam lookups, consent screen) | Consent ledger, GSTIN-first prefill, local OCR, 7 check groups, fix hints, DigiLocker mock |
| Tracker (order status instead of calling support) | Timeline, per-product ETAs, simulated WhatsApp/SMS updates |
| Stretch: voice or WhatsApp | Browser voice input (regional); WhatsApp-style simulator if time |
| Stretch: back office for leads advisor could not close | Queue with reasons and conversation summary, assignment to field/partner |
| Stretch: propensity score | LR model, expected-value ranked call list, reason codes |

Key questions the deck must answer: (1) segments and bundles, (2) needs discovery without a salesperson, (3) near-instant compliant KYC, (4) role of field force and partners, (5) 3–5 metrics with targets. First drafts of 1 and 5 are in [DATA_INSIGHTS.md](DATA_INSIGHTS.md).

## 7-slide deck outline

1. **Problem, in numbers**: 7.4% conversion, 17.6 days, ₹15k CAC, 3 chase calls; a third of drops are caused by our process.
2. **Who first and what we sell them**: segment priority and 3 starter bundles with price points and contracts.
3. **The journey**: advisor → quote → KYC → tracker, phone screenshots, regional language and voice.
4. **How it works**: architecture diagram; "LLM talks, rules decide"; KYC images stay on our servers.
5. **Field force and partners**: handoff queue, propensity × value, partner attribution, assisted KYC.
6. **Business case and metrics**: CAC, conversion, time-to-activate, churn targets; savings maths; rollout (pilot city → tier 1 → tier 2).
7. **Risks, privacy and next steps**: DPDP choices, failure modes, roadmap (real DigiLocker/e-sign, WhatsApp API, server ASR). Links to repo and demo video.

Appendix (if allowed): full privacy note, KYC check list, eval results.

## 3-minute demo script (draft)

| Time | Scene |
|---|---|
| 0:00–0:20 | Hook: the numbers, then a clinic owner opens the app on a phone |
| 0:20–1:05 | Advisor in Hindi (voice), GSTIN prefill, recommendation with reasons; quick second case: tier-2 owner asks for 1 Gbps and gets a substitution explained |
| 1:05–1:30 | Quote: toggle CCTV, switch to 24 months, price updates, accept |
| 1:30–2:10 | Consent, upload K-set: one clean pass, one caught problem (cancelled GSTIN or stale bill) with fix hint |
| 2:10–2:35 | Tracker: timeline, ETA, WhatsApp-style update; demo clock moves to activation |
| 2:35–3:00 | Back office: queue, propensity × value list, partner handoff; close on metrics |

## Build timeline (2 people: A = backend/AI, B = frontend/deck)

| Slot | A | B |
|---|---|---|
| **Nov 5 night** | Repo skeleton, CSV→SQLite loader, GSTIN validator + tests, **OCR spike on all 47 images**, **read real Gemini limits in AI Studio** and create a separate demo key | Vite app shell, routing, i18n, mobile layout, deploy empty skeleton |
| **Nov 6 morning** | Rules engine + pricing + tests, mock registry endpoints | Advisor chat UI, quote screen against stub API |
| **Nov 6 afternoon** | Advisor orchestrator, tool calls, guard, scripted fallback, eval runner | Consent + KYC upload screens, tracker UI |
| **Nov 6 night** | KYC pipeline + answer-key tests, orders state machine | Back office UI; **confirm registration** before 11:59 PM |
| **Nov 7 morning** | Propensity model + scoring endpoint, deploy, bug fixes | Deck slides 1–7, architecture PNG, privacy note |
| **Nov 7 afternoon** | Feature freeze 3 PM; end-to-end run of all evals (fake provider, then one capped live run) | Record and edit demo video, after the 1:30 PM IST Gemini quota reset, using the demo key |
| **Nov 7 evening** | README, final push, make repo public | Export PDF + PPT as `TeamName_CampusName`, **submit by 9 PM** (3-hour buffer) |

Cut order if behind: WhatsApp simulator → voice output → DigiLocker mock → propensity GBM comparison → back-office filters. Never cut: advisor, quote, KYC, tracker, deck, video.
