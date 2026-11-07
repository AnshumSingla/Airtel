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
| Advisor (GenAI, asks about business, recommends from catalogue, explains why) | Chat + buttons; local parser first, Gemini only through the privacy gate; EN/HI; rules-engine recommendation with one reason per item |
| Quote & checkout (one monthly price, toggle add-ons) | Demo rate card; add-on toggles; monthly, one-time, illustrative tax line and first payment; per-item terms; immutable quote versions; mock e-sign |
| Smart KYC (upload, extraction, validation, mocked GSTIN/Udyam lookups, consent screen) | Per-purpose consent, optional GSTIN prefill, local OCR, check groups with fix hints, owner-confirmed repairs, four honest outcomes, DigiLocker (simulated) |
| Tracker (order status instead of calling support) | Order and line-item states, indicative ETAs, simulated message inbox, "My data" page with withdrawal |
| Stretch: voice or WhatsApp | Voice is **cut** (speech provider's data handling not verified); WhatsApp-style simulator if time |
| Stretch: back office for leads advisor could not close | Role- and partner-scoped queue (P5 consent only), summary, claim with expiry, attribution |
| Stretch: propensity score | Baseline rules queue first; LR model only if it beats the baseline on a June holdout; ranked by expected revenue |

Key questions the deck must answer: (1) segments and bundles, (2) needs discovery without a salesperson, (3) fast KYC that respects consent, purpose limitation and data minimisation (the case's wording is "near-instant" and "compliant"; we answer with what the prototype does and label it a design, not a compliance claim), (4) role of field force and partners, (5) 3–5 metrics with targets. Drafts of 1 and 5 are in [DATA_INSIGHTS.md §8](DATA_INSIGHTS.md#8-answers-to-the-cases-key-questions-first-drafts).

## 7-slide deck outline

Every slide keeps three distinctions visible, with small tags: **observed in data vs hypothesis**, **simulated vs real integration**, **automated check vs verified identity**.

1. **Problem, in numbers** [observed]: 7.4% conversion, 17.6 days lead-to-activation, ₹15k CAC, 3 chase calls; a third of drops cite our own process.
2. **Who first and what we sell** [observed + demo rate card]: professional offices first; the three worked quotes with monthly, one-time, GST and first payment.
3. **The journey**: advisor → quote → consent → KYC checks → tracker; EN/HI end to end; other Indian languages as roadmap behind the privacy launch gate.
4. **How it works**: architecture with trust boundaries; "the model talks, code decides"; the privacy data-flow diagram (what can reach third parties, and that voice was cut for that reason); a "planned / evidenced" tag on every control, citing the `evidence/` commit; consent gates; what is simulated.
5. **Field force and partners**: scoped queue, handoff with summary (with consent), referral attribution, assisted KYC; baseline queue vs model.
6. **Business case and pilot** [hypothesis]: randomised pilot design, leading vs outcome metrics, revenue (not margin) payback by segment, rollout.
7. **Risks, privacy, next steps**: what we don't claim (DPDP compliance, identity verification, real ETAs), privacy choices, roadmap. Links to repo and video.

Appendix (if allowed): privacy note, KYC answer-key results, advisor eval results, worked quotes.

## 3-minute demo script (draft)

One owner journey shown completely, then one hard case, then the handoff.

| Time | Scene |
|---|---|
| 0:00–0:15 | Hook: the numbers; a clinic owner opens the app (demo banner and "Demo date: 15 Jul 2026" badge visible) |
| 0:15–0:55 | Advisor in Hindi: 3–4 questions, editable summary card, recommendation card with one reason per item, each worded as "you told us" (only for confirmed card slots) or "most businesses like yours" (segment default with its data share). One message deliberately off-script (unusual phrasing) to show the privacy gate's button fallback |
| 0:55–1:20 | Quote: toggle an add-on, see monthly / one-time / "Tax (illustrative 18%)" / first payment and per-item terms; accept (mock e-sign) |
| 1:20–1:55 | "Your choices" (P2, P3, P5 optional); GSTIN check; upload a clean set → `checks_passed` (labelled "automated checks") |
| 1:55–2:25 | **Hard case:** K01: GSTIN Cancelled in the registry **and** a Udyam certificate with no registration number (none in the Udyam registry either) → no valid business proof → `owner_action_needed` ("we need a valid GST or Udyam registration"), with the GSTIN-only line shown as excluded. Quick cut to K11 stale bill (31 Oct 2025) → `owner_action_needed`. If the DigiLocker simulation is built, also show the mixed-order flow (one line excluded → "Continue without it" → quote v2, KYC reused) with a registry-backed applicant |
| 2:25–2:45 | Tracker: line items, mobile line active first, "about 5 days (indicative)", simulated message inbox |
| 2:45–3:00 | Back office as a partner: only own leads, summary, claim; close on the pilot hypothesis |

Backup: the same script rehearsed in scripted mode (no LLM), so the live judge demo works with zero quota.

**Demo stop conditions** (from the controls register, POLICIES §15): the Gemini key is set on the demo build only if that commit's privacy-gate report shows 0 leaks; any applicant with a KYC false accept is left out of the demo; a failing consent, scope, CSRF, crypto, order or quote test blocks the deploy.

## Evidence to produce (it backs the claims)

Nothing in this table exists yet. CI will write each item to `evidence/<commit>/` for the demo build, and the deck will cite that commit. Until an item exists, the deck calls the matching control "planned".

| Artifact | Backs the claim | Where |
|---|---|---|
| Worked quotes reproduced by unit tests | "Prices are reproducible from the catalogue" | `tests/`, [WORKED_QUOTES.md](WORKED_QUOTES.md) |
| KYC answer key + per-field / per-applicant results, false accepts first | "Catches the planted problems" | `tests/`, deck appendix |
| Advisor eval results (fake provider + one live run) | "Recommendations follow the rules" | `evals/`, deck appendix |
| Propensity vs baseline on the June holdout | "The call list helps", or that it doesn't | `ml/`, deck slide 5 |
| Data-insight script output | Every number in the deck | `ml/` |
| Retention job run on video | "We delete what we say we delete" | Demo / back office |
| Privacy-gate red-team report (per category, every leaked token listed, benign parse rate) | "Volunteered personal details don't reach Gemini" | `evidence/`, deck appendix |
| Consent/retention test + screenshot or log of "End and delete" | "P1 without P4 keeps nothing after the session" | `evidence/` |
| Gate fallback rate from advisor evals | "How often privacy costs us understanding" | `evidence/`, deck appendix |
| Mixed-order state test (POLICIES §10 example) | "A cancelled GSTIN doesn't freeze the eligible items" | `tests/` |
| Role-scope tests via direct API calls | "A partner sees only its own leads" | `tests/` |
| Pilot sample-size and matched-baseline script | The 841 / 935-per-arm figures and the digital-cohort baselines | `ml/` |

## Build timeline (2 people: A = backend/AI, B = frontend/deck)

| Slot | A | B |
|---|---|---|
| **Nov 5 night** | Repo skeleton, CSV→SQLite loader, GSTIN validator + tests, **OCR spike on all 47 images**, **read real Gemini limits in AI Studio** and create a separate demo key | Vite app shell, routing, i18n, mobile layout, deploy empty skeleton |
| **Nov 6 morning** | Rules engine + pricing + worked-quote tests, clock, simulated registry | Advisor chat UI, quote screen against stub API; KYC answer key by hand (47 images) |
| **Nov 6 afternoon** | Advisor adapter, slot validation, guard, scripted mode, eval runner; consent ledger | Consent + KYC upload screens, tracker UI |
| **Nov 6 night** | KYC pipeline + answer-key tests; order/line-item state machines, idempotency | Back office UI with roles; **confirm registration** before 11:59 PM |
| **Nov 7 morning** | Baseline queue, propensity vs baseline, retention job, deploy, bug fixes | Deck slides 1–7, architecture PNG, privacy note |
| **Nov 7 afternoon** | Feature freeze 3 PM; end-to-end run of all evals (fake provider, then one capped live run) | Record and edit demo video, after the 1:30 PM IST Gemini quota reset, using the demo key |
| **Nov 7 evening** | README, final push, make repo public | Export PDF + PPT as `TeamName_CampusName`, **submit by 9 PM** (3-hour buffer) |

Already cut: voice typing. Cut order if behind: WhatsApp simulator → DigiLocker mock → propensity model (keep the baseline queue) → back-office filters → regional-language testing beyond EN/HI. Never cut: advisor (incl. scripted mode), quote, consent, KYC with answer-key tests, tracker, back-office scoping, deck, video.
