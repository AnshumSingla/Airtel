# Architecture and stack decisions

Each decision lists the options weighed, the pick, why, and what would change it. Detailed rules live in [POLICIES.md](POLICIES.md).
The overriding constraint: **the submission closes 07 Nov 2026, 11:59 PM IST**, with a 2-person team. Anything that doesn't show up in a 3-minute demo or the deck has to justify its build time.
Revised after the adversarial review in [review.md](../review.md) (see the response sections there).

> **Status: specification only.** No code, tests or CI exist yet. Every control below is planned; its evidence and stop condition are in the [controls register, POLICIES.md §15](POLICIES.md#15-controls-register).

---

## D1. Monolith or services?

- **Options:** microservices with a queue; Spring + separate AI service; one modular monolith.
- **Pick:** one FastAPI modular monolith, **single instance**, with explicit trust boundaries (Journey API, Back-office API, domain core, advisor adapter, KYC worker pool).
- **Why:** with 2.5 days, every extra service adds setup and debugging and nothing judges can see. Single instance lets the rate limiter, sessions and worker pool live in-process honestly.
- **Would change if:** never inside this deadline. The deck shows how it would split (KYC and advisor first).

## D2. Backend language

- **Pick:** Python 3.11 + FastAPI + Pydantic v2.
- **Why:** pandas, scikit-learn, local OCR and the Gemini SDK are native Python; Pydantic models double as the LLM's JSON schema. Python 3.11 is installed here.
- **Would change if:** a teammate is much faster in TypeScript (then a single Next.js app with tesseract.js).

## D3. Frontend

- **Pick:** React 18 + Vite + TypeScript + Tailwind, react-i18next, installable PWA, served by FastAPI.
- **Why:** fastest to iterate, no SSR needed, one deploy unit, mobile-first.

## D4. Database and persistence

- **Options:** managed Postgres; SQLite on a persistent disk; SQLite seeded at boot on an ephemeral disk.
- **Pick:** SQLite via SQLAlchemy, **seeded from the CSVs at every boot**. The hosted demo is ephemeral by design and says so; live demos run locally.
- **Why:** zero setup; with synthetic data, resetting on restart is acceptable and even reduces what we hold. Writes are low (one demo user at a time), so SQLite's single-writer limit is not a problem; WAL mode is on.
- **Would change if:** we need state to survive restarts on the hosted copy; then a free managed Postgres (SQLAlchemy keeps this to a config change plus a migration run, which we would test, not assume).

## D5. Who decides the bundle: LLM or rules?

- **Pick:** the LLM fills a fixed slot schema; the **rules engine** picks products, quantities and prices; the server renders all product/price details from IDs; the LLM writes one sentence per reason code, checked by a guard.
- **Why:** correctness under live judge scenarios, reproducibility, and the data shows unchecked selling breaks the rules (56 of 368 activated bundles).

## D6. Which LLM

- **Pick (team decision, 05 Nov):** **Gemini on the free tier** via `google-genai`, behind an `LLMProvider` interface, with a fake provider for tests and a scripted mode.
- **Constraint we accept:** Google's terms for unpaid services allow submitted content to be used to improve products and read by human reviewers, and say not to submit sensitive, confidential or personal information. Therefore the free tier is **for the synthetic-data demo only**, and that is to be enforced in code rather than by a banner: a **privacy gate** (planned) runs before every outbound request (local parser first, identifiers stripped, outbound text rebuilt from an allowlisted vocabulary, no call if most tokens are masked). Raw owner text never leaves the server ([POLICIES.md §5.2](POLICIES.md#52-the-privacy-gate-runs-before-every-outbound-llm-request)).
- **Production:** a separate `approved` profile, not built. As a production requirement, the server would refuse to start in it without a signed launch record covering region, retention and logging, human review, sub-processors, allowed data categories, age and regional terms, incidents and legal sign-off ([POLICIES.md §5.1](POLICIES.md#51-two-llm-profiles)). A paid service is **necessary, not sufficient**. We will not claim "India residency" or "zero retention".
- **Trade-off we accept:** the gate hurts understanding of unusual phrasing and almost removes non-EN/HI conversation on the free tier (D7). We chose privacy over coverage.

## D6a. Living inside the free-tier quota

1. **Day-1 check:** read the real RPM/RPD per model in AI Studio (Google no longer publishes one fixed table; third-party figures range from 500 down to 20 requests/day for Flash models). Write them into `.env.example` comments. Choose the primary model from those numbers.
2. **Model chain from `GEMINI_MODELS`** (ordered), Flash-Lite first if its daily quota is larger.
3. **Call budget:** the local parser handles a turn when it can; otherwise at most one gated call per owner turn (slot extraction, structured JSON), plus one explanation call when the recommendation is shown. Typical session 1–4 calls, hard cap 12, then scripted mode.
4. **Retries:** `429` → no retry, next model. `5xx`/10 s timeout → one retry after 1 s, then next model. All fail → scripted for that turn.
5. **Server-side limiter:** a token bucket per model in the API process (not the browser), set just under the real RPM, plus a daily counter.
6. **Quota protection:** tests and evals use the fake provider by default; `--live` is opt-in and capped at 20 calls; a dev-only cache (off by default, never on the hosted demo) stores **gated payloads only**, keyed by hash, deleted with `make clean-cache`.
7. **Zero-quota path:** `ADVISOR_MODE=scripted` runs the whole journey. It is rehearsed as the backup for the live demo. A separate key is kept for recording and judging. The quota-reset time is a convenience, not the plan.

## D7. Languages and voice (what we actually promise)

| Path | EN | HI / Hinglish | Tamil, Marathi, Kannada, Punjabi, Bengali, … |
|---|---|---|---|
| UI strings | Yes | Yes | No (JSON files can be added) |
| Advisor, free tier (gated) | Yes | Yes | **No**: the gate's vocabulary covers EN/HI/Hinglish, so these messages fall back to buttons + a callback offer |
| Advisor, `approved` profile (production, not built) | Yes | Yes | Planned, after the launch gate |
| Scripted mode (no LLM) | Yes | Yes | No: EN/HI buttons + callback offer |
| Voice typing | **Cut from the prototype and the demo.** The browser's speech service receives the audio, and we have not verified its retention, human review or regional settings for any browser. Roadmap, once a specific provider is chosen and verified ([POLICIES.md §5.3](POLICIES.md#53-voice-typing-cut-from-the-prototype)) |

The deck says "English and Hindi end to end. Other Indian languages need a production AI setup that passes our privacy launch gate; the data shows why they matter (§6 of DATA_INSIGHTS)."

## D8. OCR: local engine

- **Pick:** RapidOCR (pip, ONNX) on in-memory images, after red-channel watermark removal and deskew; Tesseract as fallback if the day-1 spike disappoints.
- **Why:** documents are not sent to a third-party OCR or AI vendor, which **reduces** onward transfer. It is not a privacy guarantee on its own: collection, access, retention, hosting and logging are handled separately ([POLICIES.md §3](POLICIES.md#3-data-inventory-and-retention)). The specimens are clean, fixed-layout documents, which suits classic OCR.
- **Day-1 spike: done** ([evidence/ocr_spike/](../evidence/ocr_spike/README.md)). RapidOCR is adopted; Tesseract isn't needed. The red channel is essential (raw images: 2 of 12 GSTINs read; red channel: 8, with the other 4 explained by planted problems or owner-confirmable O/0 repairs). The blur gate and deskew are needed for K04 and K02. The answer key is drafted; per-field accuracy waits for the final hand-checked key.
- **Would change if:** field accuracy is too low after preprocessing; then a vision model under explicit consent, paid tier only, and the privacy note changes to say so.

## D9. KYC outcomes

Two results: an **applicant result** (`checks_passed`, `owner_action_needed`, `manual_review`) and a **line eligibility result** per item (`eligible` / `excluded` with a reason). A Cancelled or Suspended GSTIN excludes the GSTIN-only lines rather than stopping the whole applicant; the order waits for a one-tap new quote version without those lines, and the KYC result is reused. The old applicant-level `blocked` is removed. Required documents: ID + address proof + at least one valid business registration (GST or Udyam). Never "verified". No auto-correction of identifiers: repair candidates need the owner's confirmation, and the raw value and repair trail are kept. Identifiers link records; names and addresses only check consistency. Freshness uses an injected `business_as_of` clock (fixture 2026-07-15 in demo mode). Full definitions, thresholds, reviewer authority and appeal: [POLICIES.md §9](POLICIES.md#9-kyc-outcomes).

## D10. Pricing

- **Data check:** historical deal values always sit inside the catalogue band, on average 48% of the way up, with no difference by tier or contract length; setup is always fee × quantity; the contract always equals the longest item minimum.
- **Pick:** band midpoint as the demo rate card; no discounts and no "save ₹X" claim; setup × quantity; **per-item commitment terms**; an **illustrative uniform 18% tax** line, labelled as a mock rule (the catalogue has no tax categories, and its products are not all taxed the same way in reality; real quotes need a per-SKU tax category from finance); first payment shown; immutable quote versions. Labelled "demo rate card".
- **Dropped from the earlier draft:** the contract-length slider that moved the price inside the band. The data shows no such relationship and the catalogue defines no discount schedule.
- Rules and quantity defaults: [POLICIES.md §7](POLICIES.md#7-rate-card-and-quote). Worked examples: [WORKED_QUOTES.md](WORKED_QUOTES.md).

## D11. Recommendation logic

Catalogue targeting (`target_segments`) as a **soft rule**: never a rejection, but every engine-chosen default must be on-target, and off-target owner choices are flagged `INFO_OFF_TARGET` → segment starter set from historical purchases, ranking on-target products only → needs → eligibility (active GSTIN, not just a valid check digit) → dependencies resolved by **need and site constraints, then price**, and never added silently → substitutions offered, not applied → budget trimming with a list of what was dropped → reason and exclusion codes. Details: [POLICIES.md §6](POLICIES.md#6-recommendation-rules).

## D12. Propensity score

- **Baseline first:** a transparent rules-based queue (GSTIN, segment, source, stage, days waiting).
- **Model:** logistic regression on features recorded at lead creation. **Excluded:** current registry status (we don't know the status at lead time), stage dates, outcomes. GSTINs are unique in the leads file, so no group leakage by identifier.
- **Validation:** time-based split (created April–May train, June test; June activation rate is 7.5%, the same as April, so no obvious censoring). Report ROC-AUC and PR-AUC against the baseline, precision at the number of leads a team can call per day, calibration, and results by language, source and segment. Accuracy is not reported (always predicting "no" is 92.6% accurate).
- **Ranking value:** `p(activate) × expected monthly revenue`, labelled **expected revenue**. For historical leads it uses the segment median of activated deals; for live leads, the quote value. No margin claim (the data has none).
- **Ship rule:** the model replaces the baseline queue only if it beats it on the June holdout; otherwise we show the comparison and keep the baseline.

## D13. WhatsApp front end (stretch)

An in-app WhatsApp-style simulator on the same advisor API, labelled "Simulated". Real WhatsApp Cloud API is roadmap.

## D14. DigiLocker and e-sign

Simulated, labelled, and shown as the production integration target.

## D15. Hosting

Render free web service from the Dockerfile, single instance, ephemeral disk, re-seeded at boot, sleeps when idle (wake before judging). Live demo and video run locally. Day 1: deploy the empty skeleton to confirm.

## D16. Security (prototype)

Concrete rules are in [POLICIES.md §13](POLICIES.md#13-security-specifics-prototype). Summary:
- Server-side sessions (revocable) in `HttpOnly` cookies, `Secure` on the hosted HTTPS demo, `SameSite=Lax` for owners and `Strict` for staff; owner 24 h idle; staff 30 min idle / 8 h absolute; logout deletes the session.
- Every state-changing route is `POST` and needs a CSRF token header and a matching `Origin`; CORS off.
- Staff passwords stored as Argon2id hashes, lockout after 5 failures; no MFA in the prototype (stated gap).
- KYC identifiers encrypted with a Fernet key ring from the environment (rotation by re-encryption; a lost key means re-upload).
- Random UUIDs for quotes, orders and KYC cases; ownership checked on every route; role and record scope to be tested with direct API calls, not only through the UI.
- Idempotency keys on accept, upload, KYC submit and state transitions; transitions outside the table are rejected.
- Rate limits per IP on public routes; uploads limited to JPEG/PNG ≤ 8 MB, 4 per case; request timeout 30 s.
- No payment is taken: payment and e-sign are simulated, so there is no duplicate-charge risk to handle beyond idempotent acceptance.

## D17. Testing and evals

- **All planned.** Results will be written by CI to `evidence/<commit>/` for the demo build ([POLICIES.md §15](POLICIES.md#15-controls-register)); the deck cites that commit. Until then, the docs describe controls as specified, not working.
- Unit tests: GSTIN format and check digit, eligibility, dependencies, every worked quote and negative case, KYC answer key (K01–K12), state-machine transitions including the mixed-order example, P1-with-P4-declined deletion, consent-event unlinking, privacy-gate red-team set, CSRF rejection, and role scope via direct API calls (partner A cannot read partner B's lead; a referral code alone gives no access).
- Advisor evals: about 20 scenarios (tier-2 asking for 1 Gbps, no-GSTIN asking for WhatsApp API, 4-site chain, Hindi-only owner, budget cap, conflicting answers, out-of-catalogue request, prompt injection, unknown city). Assertions run on the engine output, so they are deterministic. Fake provider by default; capped live runs twice.

---

## Open questions for the team

1. ~~LLM key~~: decided, Gemini free tier. Still to do: read the real per-model limits in AI Studio.
2. **Deck length:** Unstop asks for a 7-slide PPT (PDF + PPT, `TeamName_CampusName`); the case PDF asks for a ≤ 10-slide business case plus video, repo, architecture and privacy note. Plan: 7 main slides with links, architecture and privacy as appendix. Confirm on the Unstop discussion board if possible.
3. **Registration** closes 06 Nov 2026, 11:59 PM IST: confirm the team is registered.
4. **Team skills:** confirm Python + React for both of us.
5. **Per-item vs bundle-wide terms** (D10): we chose per-item for clarity; the historical practice was bundle-wide. A business call, flagged in the deck.
6. **Regional languages on the free tier** (D6, D7): the privacy gate rules them out of the demo. If the team wants to show Tamil or Marathi, the honest options are adding those words to the gate's vocabulary (a stretch item, limited) or showing them only as roadmap.
