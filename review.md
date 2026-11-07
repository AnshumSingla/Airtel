# Architecture review: Project Udyam Digital

**Review stance:** Hackathon judge, adversarial product/architecture review  
**Materials reviewed:** `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/DATA_INSIGHTS.md`, `docs/DELIVERABLES.md`, `docs/COMPETITOR_SCAN.md`, `data/raw/README.md`, `data/raw/product_catalogue.csv`, `data/raw/smb_leads.csv`, and the supplied case PDF.  
**Project status in the docs:** design only; no application code yet.

## Judge's first reaction

The design has a strong central principle: a deterministic catalogue/rules/pricing layer owns the recommendation, while the model handles conversation. It also correctly notices that the journey, partner economics, and KYC matter as much as the chatbot. That is a credible starting point.

As written, however, this is a broad feature inventory presented as a production-like architecture. It has not yet established that the recommended bundles are valid and affordable, that its KYC verdicts mean what the UI says they mean, that the success targets follow from the data, or that the system can safely keep an abandoned owner moving. A judge can probe each of those seams quickly. The largest risk is overclaiming certainty: “compliant,” “near-instant,” “removes the reason,” “makes it impossible,” and “never stalls” are stronger than the design supports.

**Current score as a design submission: promising premise, not yet win-ready.** Keep the deterministic core. Narrow the promise, define the business rules precisely, and prove the happy path plus the uncomfortable paths with visible evidence.

## Must-fix before the deck or demo

### 1. Consent and registry lookups are out of order

The advisor sequence extracts a GSTIN from chat and queries the registry before any consent step. The KYC flow says consent comes first, but the architecture's component diagram routes advisor-to-registry separately from the consent ledger. The user may have supplied an identifier to ask a question, not agreed to a registry lookup, persistent profile, partner handoff, or marketing follow-up.

**Fix:** make consent/purpose explicit before any identifier lookup or retention. Separate at least: (a) one-time eligibility lookup, (b) KYC/document verification, (c) saving/resuming an application, and (d) sharing a lead with a named partner/sales team. Record the notice version, purpose, timestamp, and decision; provide a way to withdraw and explain what processing stops. Do not make optional marketing consent a condition of a quote. The prototype can simulate integrations, but should not describe itself as legally compliant on that basis.

### 2. “KYC approved” is not document authenticity or identity proof

The proposed checks establish that OCR text has plausible formats, registry fields line up, and documents are present. They do not establish that an image is genuine, unaltered, current at the time of use, or submitted by an authorized person. Fuzzy name/address agreement can produce false matches, and a checksum repair plus a matching registry name can silently turn a document's text into a different identifier. “Identity is matched by identifier, never by name” also conflicts with the proposed human-name and fuzzy cross-document checks.

**Fix:** name the outcome accurately: `automated checks passed`, `owner action needed`, `manual review`, or `blocked`. Keep “verified” for a defined verification source/process. Never auto-correct an identity identifier and approve it; show the OCR candidate, require the owner to confirm it, and preserve the original extracted value and repair trail for review. Confidence thresholds, mismatch policy, reviewer authority, appeal/correction path, and false-accept/false-reject handling need definitions. Do not claim OCR detects tampering unless you implement and evaluate that control.

### 3. The freshness rule is frozen to a data-pack date

`address proof <= 90 days before 2026-07-15` and ID validity “on that date” come from the synthetic data instructions, while the proposed submission/demo is in November 2026. A real order must evaluate freshness at the order's effective date; a demo fixture may deliberately use the pack's fixed date. A fixed date in the production rule will make stale evidence look current or vice versa.

**Fix:** use an injected `business_as_of` clock, with a clearly labelled fixture clock in demo mode and a real current timestamp in a real integration. Define which document types and issuers qualify, and make the permitted age configurable from an actual policy source. The 90-day threshold is a prototype/business rule unless the case material explicitly makes it a legal requirement.

### 4. Pricing is not yet derivable from the catalogue

The CSV provides price bands, a minimum contract length, and no discount schedule or maximum term. The proposed rule maps contract term to the low/mid/high point of the band, then exposes a contract slider. That invents a discount relationship the catalogue does not state. It can also create contradictory terms: a bundle-wide term set to the longest item minimum may bind unrelated one-month products for 12 or 24 months. “Save ₹X/month with 24 months” is unsupported until the catalogue/business owner supplies a term-price matrix.

There are further unpriced choices: quantities for per-user, per-device, per-line, per-camera and per-site products; what employee count means for billable seats/devices; whether a user can edit quantities; whether setup is charged once per site or once per order; whether GST applies to every listed amount; and how savings are calculated when the current-spend value may include unrelated vendors/products.

**Fix:** quote from an explicit rate card with effective dates, term eligibility, line-item term, quantities, setup basis, taxes, rounding, and discount authority. If the hackathon data does not define those, label the chosen pricing rule as a transparent demo assumption and do not claim a real saving or discount. Show monthly recurring subtotal, one-time charges, taxes, first-payment amount, and term commitments separately. Add a quote snapshot/version so acceptance cannot silently change when rules or catalogue rows change.

### 5. The starter bundle examples may fail the stated rules or price targets

The proposed micro bundle includes products with GSTIN-only restrictions as optional choices, which is okay only if the active-status check is correct and the owner understands what is excluded. More importantly, `under ₹2,500/month` is not demonstrated with a specified quantity and tax basis. Two postpaid lines, fibre, POS, guest Wi-Fi, and any camera count can move the number materially. A professional starter bundle with email per employee and security per device scales with employee count, but the example has no seat/device cap.

The recommendation recipe also says “add the cheapest eligible connectivity product” to satisfy dependencies. That may technically satisfy a catalogue dependency while being the wrong product for the stated need, availability, or service level. `requires_one_of` must be resolved against product semantics and site/address constraints, not just price.

**Fix:** publish 2–3 fully worked example quotes from actual catalogue rows, including assumptions, quantity, taxes, setup, term, and the reason every item is present. Test each bundle through the same eligibility/dependency/pricing functions the app uses. If a dependency cannot be satisfied, explain that and ask for assisted review rather than auto-adding a poor fit.

### 6. Order state machine contradicts its own fallback promise

The stated sequence is linear, but a multi-product order can have partial fulfilment, independent installation dates, failed feasibility, customer rescheduling, failed installation, cancellation/refund, and re-KYC. Side-state `NEEDS_ACTION` is not enough to show whether it suspends one product or the entire order. The claim that mobile lines activate on day one assumes provisioning can proceed independently while other KYC/order items are pending. The 5G substitution changes the quote after acceptance, which requires explicit customer re-acceptance and potentially a different contract.

`ETA = KYC date + typical_install_days` is a catalogue estimate, not an address-level serviceability result or an operational commitment. A demo clock must not make the user-facing ETA look like a real guarantee.

**Fix:** model order-level and line-item states separately, define allowed transitions and actor/trigger, and version every customer-visible quote change. State that the tracker is a simulation with indicative estimates. For a real service, use a feasibility/provisioning response and delivery window, preserve the accepted quote, and obtain confirmation before substitution.

### 7. The success story overreads observational data

The data says churn and NPS vary with follow-up-call count and activation delay. That is correlation, not evidence that status calls cause churn or that a tracker will reduce churn. Difficult/late orders may cause both more calls and more churn. The same issue affects claims that the journey “removes” 34% of drop reasons: it may address some process friction, but it does not establish recovered conversions.

The 12% conversion, ≤7-day activation, ≤₹7,000 blended CAC, ≤0.5 calls, and ≤10% churn targets have no experiment, rollout denominator, margin, or capacity model behind them. The ≤7-day promise conflicts with catalogue install times of 10, 14, 21, and 30 days for several products. “Micro is viable only self-serve” and “target CAC under ₹3k” are also not proven by the provided cohort. Revenue is not contribution margin; we have no gross margin, lifetime value, servicing cost, partner payout, discount cost, or segment-specific channel incrementality.

**Fix:** frame the numbers as hypotheses, state the population and measurement window, and separate leading indicators from outcomes. Pilot with a control/holdout or staged rollout. Segment targets by product/serviceability and measure quote acceptance, KYC completion, activation, gross margin/payback, partner-sourced conversion, time to install, repeat contacts, and churn after a full observation window. Do not promise ≤7 days for orders whose own install estimate exceeds that.

## Architecture questions a judge will ask

### Product choice and advisor

- What exact inputs make a recommendation eligible: segment, tier, employee count, site count, active GSTIN, address-level feasibility, budget, and stated need? Which are required versus inferred?
- What happens when the owner gives conflicting answers, changes their mind, asks for a product outside the catalogue, or supplies a location the mock registry cannot resolve?
- Is “needs assessed” sufficient to recommend, or can the system ask a maximum of N questions and then offer a useful partial quote or human handoff?
- How do you prevent a prompt injection or untrusted conversation history from changing system policy? Structured JSON constrains shape, not truth or authorization.
- The output guard checks named products and rupee amounts. How does it handle aliases, transliteration, negation (“you do not need X”), a bundle quantity, a price spoken in words, or hallucinated claims about uptime/eligibility? Prefer rendering the product/price card from IDs and keeping generated explanation constrained to validated reason codes.
- What does the fallback do in Tamil, Marathi, Kannada, Punjabi, or Bengali? The product promise says preferred language, but scripted fallback covers only EN/HI/Hinglish and browser speech recognition is device/browser-dependent. Be honest about supported languages and graceful typed fallback.
- The architecture's example emits “Maharashtra” and “Proprietorship” after a GSTIN lookup, yet the owner did not consent in that flow. Also decide whether raw conversation, summary, or only structured slots are retained or handed to staff.

### Registry and KYC

- How are mock GSTIN/Udyam lookups distinguished from real government integrations in every screen and deck? What is the source-of-truth timestamp and outage behavior?
- Does a GSTIN checksum prove that the registration is active? No: syntax/check digit and a registry status are separate checks. How are `Cancelled`, `Suspended`, not-found, ambiguous, and stale-registry responses represented?
- What prevents OCR temp files, exception traces, reverse-proxy logs, crash dumps, browser previews, or analytics from retaining the image/identifier after “in memory only” processing?
- What exact data is saved, for how long, who can see it, and what is deleted on withdrawal, abandonment, or failed KYC? How does deletion propagate to backups/logs/partners?
- Who may view/assign cases, and what stops one partner from opening another partner's lead or documents? Back-office auth, role-based access, tenant/partner scope, audit, and rate limits are absent from the diagram.
- Is address/state equality enough when an address may be differently formatted, a business has multiple sites, or the billing proof is not the installation address?
- Are all 47 images and all planted issues tested against a reviewed answer key? OCR accuracy needs per-field and per-applicant results, with false acceptance emphasized over average character accuracy.

### Orders, APIs, and deployment

- What is the idempotency strategy for repeated checkout, upload, KYC submission, state-transition, and notification requests?
- What protects a quote/order from cross-user ID guessing, replay, duplicate payment acceptance, or unauthorized state transition? The current design has no authentication/session or API security boundary.
- Is a persistent disk guaranteed by the chosen host? “Render or Railway” is not a deployment decision. A container-local SQLite file can disappear on redeploy or be unavailable across replicas. SQLite also creates write/concurrency constraints for concurrent demos.
- If the host scales to two replicas, where are the database, rate limiter, uploaded files, and job/notification state shared? If it never scales, say so and keep the architecture single-instance.
- The free-tier LLM fallback is not a reliability design by itself. API quotas are project/model/account dependent and the quota reset detail is not a dependable demo plan. What is the primary demo path if all live calls are unavailable from the first minute?
- What are upload limits, request timeouts, OCR worker limits, and overload behavior? A phone photo can be huge; CPU OCR and synchronous FastAPI handlers can block other users.
- What does “simulated WhatsApp/SMS” mean to the customer? Clearly label it as an in-app simulation; do not imply messages were sent externally.

## Data science and measurement review

1. **Leakage and time validity:** “features known at lead creation” is a good constraint, but current GSTIN/Udyam registry status may not be the status known at the original lead date. Use point-in-time features or exclude them. Keep all records from the same business/identifier in one fold if duplicates exist.
2. **Validation:** random cross-validation on one quarter can overstate future performance. Compare against a simple baseline and use a time-based split, calibration, precision/recall at the number of humans who can call, and confidence intervals. Report subgroup performance for language, source, and segment.
3. **Selection bias:** only activated leads have monthly value/churn labels. Expected monthly value for dropped or new leads needs a defined estimate, not a missing-value shortcut. Ranking by `p(activate) × monthly revenue` can prioritize large but low-margin deals and ignore servicing/partner capacity. Prefer expected contribution value and explicit queue capacity; until margin exists, label it expected revenue.
4. **Decision value:** show how a call list changes a real assignment/action and measure lift against the existing queue. A probability score that no one trusts or acts on is decoration.
5. **Causal claims:** use “associated with” for call/churn and delay/NPS comparisons. Treat the tracker impact as a hypothesis to measure, not a proven churn lever.
6. **Base rates:** 7.4% overall activation means an always-negative model has 92.6% accuracy. Do not present accuracy as evidence of useful propensity ranking.

## Legal, privacy, and vendor claims to tighten

- The design correctly flags the unpaid Gemini API data-use issue. Google's current developer terms state that content sent through unpaid services may be used to improve products and may be reviewed by humans; they say not to submit sensitive, confidential, or personal information. “Regex redaction” is not a sufficient guarantee: free text can contain names, phone numbers, addresses, IDs, or unique details that survive it. For a public demo with real users, use a paid service configured under the applicable terms or keep the LLM strictly synthetic/demo-only; use a tested allowlist of fields rather than relying on a blacklist redactor. See [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms).
- The terms say paid Gemini API prompts/responses are not used to improve products; that alone does not establish India residency, zero retention, or the exact enterprise safeguards claimed by “Vertex AI (asia-south1).” Verify region, service, logging/retention, processor terms, and configuration before making that promise. See [Gemini API data-use terms](https://ai.google.dev/gemini-api/terms) and [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
- As of the reviewed official notifications, DPDP Act and Rules commencement is phased. The 13 Nov 2025 notification schedules core sections 3–17 and related provisions for 18 months after publication (May 2027); other provisions commence earlier. The Rules also have phased commencement. For a Nov 2026 hackathon, say “designed around the case's DPDP principles; prototype uses synthetic data and mock services,” not “DPDP compliant.” Confirm the applicable date and get qualified legal review before a real launch. Sources: [MeitY commencement notification](https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf), [DPDP Rules 2025](https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf).
- Avoid implying that a local OCR engine alone means “privacy-safe.” It reduces transfer to the OCR vendor, but does not address collection, access, retention, hosting, telemetry, or onward sharing.

## Contradictions and loose ends to reconcile

- Case PDF calls this **Enterprise Track A**; repo README/architecture say **Digital Track**. Use the official case title/track consistently in the submission.
- The synthetic data README fixes “today” at **2026-07-15** for its date checks, while the actual submission materials are dated November. Make the fixture-vs-live clock distinction explicit.
- Case context says installation takes 10–14 days on average; the provided activated cohort averages 17.6 days lead-to-activation. These are different measures. Do not conflate lead-to-activation with install duration.
- The architecture says recommendation substitutes 5G AirFiber if fibre is infeasible, but the sample product P04 is **100 Mbps**, whereas the user's desired tier/bandwidth may differ. Ask before substituting and reprice/reconfirm.
- `DECISIONS.md` says “one call per normal turn” plus a recommendation explanation call; the sequence uses two user-turn calls and a third explanation call. Document the expected/maximum calls per session and quota budget, including 429 behavior, retries, model fallback, and scripted fallback.
- “Client-side rate limiter” is ambiguous. Rate limiting must happen on the server/provider client, keyed to the provider project's shared quotas, not in the browser.
- Staff/partner interface is a meaningful differentiator but auth, consent for sharing, attribution conflict resolution, partner incentives, lead ownership/claim expiry, and audit are missing.
- Architecture says the 5,000 historical leads plus new sessions all receive a score; clarify whether this is an offline demo list or a live model endpoint and how synthetic historical identities are separated from real user records.

## A tighter, judge-defensible architecture

For the deadline, present one deployable modular monolith with explicit trust boundaries:

1. **Phone PWA** collects only the minimum discovery slots. Explain supported languages and whether voice runs in the browser. Keep an unauthenticated demo mode separate from any real-user flow.
2. **Journey API** owns session identity, consent/purpose, quote version, and order transitions. Enforce auth/role checks for back-office and partner routes; scope every record to its owner/partner.
3. **Deterministic domain core** loads a versioned catalogue, validates inputs, returns eligible products plus exclusion reasons, resolves dependencies against site/address constraints, and calculates a reproducible quote. It never trusts model output for IDs, price, consent, or state changes.
4. **Advisor adapter** receives allowlisted, non-identifying slots and the eligible options/reason codes. Parse schema, validate each slot, constrain answer length/language, and render product/pricing details from server data. If unavailable, a visible scripted path works in every language claimed in the demo.
5. **KYC service** processes bounded uploads in isolated temporary storage, does quality/OCR/extraction, preserves correction provenance, and returns check results with explicit confidence/manual-review states. Document retention/deletion is a first-class job and observable in the demo.
6. **Order service** maintains per-line and order states, immutable accepted quote snapshots, idempotent commands, and simulated notifications clearly marked as simulated.
7. **Back office** sees only leads whose handoff/sharing purpose is recorded; assignment is scoped/audited. Start with a transparent rules-based queue. Add propensity only if the model beats a baseline and demonstrably improves which leads are called.
8. **Runtime choice:** one instance + persistent SQLite only if the selected host guarantees durable storage and the demo traffic is single-user. Otherwise use a managed database. State this as a deployment constraint, not “swap connection string later.” Add upload/request limits and keep OCR work from blocking the API.

This is a smaller and more defensible story than claiming every production integration is already solved.

## Questions to answer before calling the design frozen

1. What is the exact first target segment and the single quoted bundle, with a complete catalogue-backed monthly/first-payment example?
2. Which consent covers each lookup, saved application, document processing, and human/partner handoff? Can an owner get a quote without optional sharing/marketing consent?
3. What does each KYC verdict certify, and which failures must go to a human rather than automatic approval?
4. What are the exact contract and pricing rules in the source data? If terms/discounts are assumptions, how are they labelled to the customer?
5. Which real-language paths work when Gemini is down, and what is the demo's zero-quota path?
6. What is persisted after an abandoned session, for how long, and who can access it?
7. Which host is selected, where does SQLite persist, and what happens on redeploy/restart?
8. What outcome will the pilot actually measure, against what comparison group, over what period?
9. Which claims are prototype simulations, which are dataset observations, and which are production commitments? Can the UI and deck distinguish them at a glance?

## What would make this win-worthy

Do not try to show every module equally. Make one owner journey feel trustworthy and complete: state the need, see a bounded recommendation with a clear reason, understand a fully reproducible quote, choose whether to proceed, complete an honestly described mock KYC path, and see line-item status. Then show one difficult case: ineligible product, cancelled/suspended registry status, mismatch requiring review, low quota/model outage, or an address that cannot be served. Finish with the partner/human handoff and the measured business hypothesis.

The deck should make three distinctions visible: **observed data vs causal claim**, **mock prototype vs real integration**, and **automated consistency check vs verified identity**. Judges are more likely to trust a narrow system that admits its boundaries and handles them well than a broad system whose headline claims collapse under one follow-up question.

---

# Response from the design team (round 1, 05 Nov 2026)

**For the reviewing agent:** this section answers every point above and says where each change landed. Nothing was dismissed; where we disagree or cannot settle something without code or team input, it says so. Files changed in this round (uncommitted at time of writing, so `git diff` plus the two new files show the full change):

| File | Change |
|---|---|
| `docs/POLICIES.md` | **New.** Clock, consent purposes, data inventory and retention, advisor inputs, LLM boundary, recommendation rules, rate card, registry states, KYC outcomes, order and line-item states, back-office roles, labelling |
| `docs/WORKED_QUOTES.md` | **New.** Three full quotes, one add-on variant and three negative cases from catalogue rows, rule-checked |
| `docs/ARCHITECTURE.md` | Rewritten: trust boundaries, consent gate before lookups, revised advisor flow and call budget, KYC limits, failure modes, deployment decision, naming, "what we are not claiming" |
| `docs/DECISIONS.md` | Rewritten: D4 persistence, D6/D6a Gemini terms and quota, D7 honest language matrix, D8 OCR wording, D9 outcomes, D10 data-derived pricing, D12 propensity validation, D15 hosting, new D16 security, D17 tests |
| `docs/DATA_INSIGHTS.md` | Rewritten: association wording, corrected counts, revenue-not-margin payback, randomised pilot design, hypotheses instead of promises |
| `docs/DELIVERABLES.md` | Deck tags for the three distinctions, demo script with a hard case and zero-quota backup, evidence table, timeline and cut list |
| `README.md`, `docs/COMPETITOR_SCAN.md` | Naming, scope disclaimer, softened claims |

## Facts we checked during this round

| Claim | How it was checked | Result |
|---|---|---|
| Pricing is not derivable from the catalogue | Compared all 368 activated deals with the catalogue bands | 100% of deal values fall inside the summed bands; average position 48% of the way up; **no difference by tier (48% / 48%) or contract length**. The contract-term discount in our draft had no basis and is removed |
| Setup basis | Same deals | Setup = fee × quantity in 100% of deals |
| Bundle term | Same deals | Contract = longest item minimum in 100% of deals (we still chose per-item terms, see item 4) |
| Quantity rules | Quantity vs employees/sites per product | Per-site items = sites in ≥ 90% of deals; email ≈ 0.58 × staff; endpoint ≈ 0.38 × staff; cameras median 4. Adopted as editable defaults |
| "Under ₹2,500" micro bundle | Computed from catalogue rows | **Wrong.** Core micro bundle is ₹2,197 ex-GST / ₹2,592 incl. GST. Corrected |
| Rule-breaking bundles | Recounted per lead | 56 leads still correct; the GSTIN breakdown was conflated. Correct: 21 leads (22 lines: 12 no GSTIN, 7 Cancelled, 3 Suspended). Corrected |
| Censoring for a time split | Activation rate by creation month | Apr 7.1%, May 7.5%, Jun 7.5%; last activation 26 Jul. A June holdout is usable |
| Duplicate identities | GSTINs in leads | No duplicate GSTINs; business names repeat (3,066 repeats) across different businesses, so linking must use identifiers |
| Gemini unpaid-service terms | Read the current terms (ai.google.dev/gemini-api/terms, which redirects to aistudio.google.com/docs/terms) | Confirmed: content may be used to improve products, human review, "do not submit sensitive, confidential, or personal information"; paid prompts not used to improve products; users must be 18+ |
| DPDP commencement | Official and law-firm summaries | Rules notified 13 Nov 2025; phased; Consent Manager obligations from Nov 2026; substantive obligations from 14 May 2027. We now say "designed around the case's DPDP principles", never "compliant" |
| K01 and K11 planted problems used in the demo | Registry lookup; viewed the K11 image | K01 GSTIN `Cancelled` in the registry; K11 bill dated 2025-10-31 (257 days before 2026-07-15) |

## Must-fix items

### 1. Consent before lookups: fixed in design
Six separate purposes (P1 quote, P2 one-time GSTIN/Udyam lookup, P3 KYC, P4 save/resume, P5 share with a named team, P6 marketing), each unticked, versioned and withdrawable; no optional purpose is a condition of a quote. The advisor asks only "do you have a GSTIN (yes/no)"; the number goes into a P2 form. A GSTIN typed into chat before P2 is caught server-side, not sent to the LLM, not looked up and not stored. Withdrawal effects are defined per purpose. The docs now say "designed around DPDP principles", not compliant. → `POLICIES.md §2`, `ARCHITECTURE.md §3, §4.2`.

### 2. KYC outcomes that mean what they say: fixed in design
Outcomes renamed `checks_passed`, `owner_action_needed`, `manual_review`, `blocked`, each with "means / does not mean". "Verified" is banned for automated results; no tampering claim. OCR repairs are **never** auto-applied: the owner confirms a candidate, the raw value and repair trail are kept, and a repaired identifier reaches `checks_passed` only with owner confirmation and a matching registry name. The identifier-vs-name conflict is resolved: identifiers link records; names and addresses are consistency checks that can only lower an outcome. Thresholds, reviewer role, audit and appeal path are defined. False accepts are the headline metric of the answer-key test (target 0 on the specimen set). → `POLICIES.md §9`, `DECISIONS.md D9`.

### 3. Frozen freshness date: fixed in design
Injected `business_as_of` clock: fixture 2026-07-15 in demo mode with a visible badge; real time in live mode, evaluated at KYC submission. The 90-day rule is labelled a prototype rule from the data pack and lives in `policy.yaml`. Accepted address-proof type for the prototype: electricity bill only (the only specimen type supplied). → `POLICIES.md §1, §9`.

### 4. Pricing not derivable: fixed, with data
We checked the 368 deals (facts table). New rate card: band midpoint (consistent with the observed 48%), no discounts, no "save ₹X", setup × quantity, GST 18% on recurring and one-time charges, rounding rules, first payment, and **per-item commitment terms**, so a month-to-month line isn't bound to 12 months. Historical practice was one bundle-wide term; per-item is our deliberate choice, flagged as a business decision. Quantity defaults and caps come from the data. Accepted quotes are immutable versions; any change needs re-acceptance. The current-spend line is shown without calling the difference a saving. → `POLICIES.md §7`, `DECISIONS.md D10`.

### 5. Starter bundles may fail rules or price targets: fixed, with worked quotes
Three fully worked quotes (professional ₹4,633 ex-GST, micro core ₹2,197, multi-site ₹28,576) plus a micro add-on variant, each with quantities, reasons, taxes, setup, first payment and terms, all passing the rule checks. Three negative cases fail where they should. The "under ₹2,500" claim was wrong and is corrected. Dependency resolution is now "by need and site constraints, then price", never silent; an unresolved dependency is excluded with a reason and assisted review is offered. These cases become unit tests. → `WORKED_QUOTES.md`, `POLICIES.md §6`.

### 6. Order state machine: fixed in design
Separate order and line-item machines, with partial fulfilment, reschedule, install failure and retry, cancellation with a stated refund assumption, `ON_HOLD` for KYC/consent/feasibility, and a transition table with trigger and actor. Mobile lines go active after `KYC_OK`, independent of fibre. A substitution after acceptance is a new quote version that needs acceptance; P04 is stated as 100 Mbps wireless. ETAs say "about N days (indicative)"; messages say "Simulated message, not sent". → `POLICIES.md §10`, `ARCHITECTURE.md §4.4`.

### 7. Observational data overread: fixed
All causal wording removed ("removes", "churn lever", "only self-serve", "makes it impossible"). Targets are pilot hypotheses with a randomised 50/50 design on website + WhatsApp leads, a sample-size estimate (about 650 per arm), leading vs outcome metrics, and readout timing (churn 6 months after the pilot ends). The ≤ 7-day promise is gone: the time target applies only to orders whose items all install in ≤ 5 days; long-install items are tracked against their own estimates. Payback is labelled **revenue, not margin**, with the missing data listed. Lead-to-activation (17.6 days) and the case's 10–14 days are separated as different measures. → `DATA_INSIGHTS.md §1, §5, §7, §8`.

## Judge questions

### Product choice and advisor
- **Exact inputs, required vs inferred:** required: business type (→ segment), city (→ tier, state), employees, sites, has GSTIN (yes/no). Optional: needs, current internet/provider/spend, budget. Validation ranges and fallbacks per slot. → `POLICIES.md §4`.
- **Conflicts, changes of mind, out-of-catalogue, unknown location:** the latest answer wins, then an editable summary card is the only input to the engine. Out-of-catalogue → "Accel doesn't offer that", never invented. Unknown city → ask state and city size, else treat as tier 2 (stricter) and say so. → `POLICIES.md §4`.
- **Maximum questions:** after 8 owner turns without the required slots, offer a partial quote with defaults shown as assumptions, or a callback (with P5). → `POLICIES.md §4`.
- **Prompt injection:** the LLM fills a fixed schema; every value is validated; the LLM cannot trigger lookups, consent, pricing or state changes (server actions behind buttons); policy text is never built from user text. We agree structured output constrains shape, not truth, which is why each value is validated separately. → `POLICIES.md §4`, `ARCHITECTURE.md §3`.
- **Guard (aliases, transliteration, negation, numbers in words, SLA claims):** taken up as suggested. Product names, quantities and prices are rendered by the server from IDs. The LLM returns one sentence per reason code as keyed JSON. The guard rejects wrong keys, long sentences, digits, ₹ and rupee words (incl. Hindi), %, SLA/uptime/speed claims, and other products' names from an alias list with transliterations. Negation is moot because the card, not the sentence, lists the bundle. → `POLICIES.md §5`.
- **Fallback in Tamil, Marathi, Kannada, Punjabi, Bengali:** an honest matrix. EN/HI end to end in both modes; other languages best effort with Gemini only (we demo-test Tamil and Marathi and show only what passes); without the LLM, EN/HI buttons plus a callback offer; voice only where the browser supports it, typing always works. → `DECISIONS.md D7`, `ARCHITECTURE.md §6`.
- **Lookup without consent; what is kept or handed to staff:** the example sequence is redrawn so no lookup happens before P2. Raw chat is stored only with P4; staff see a summary only with P5; retention per item is in the data inventory. → `ARCHITECTURE.md §4.1, §4.2`, `POLICIES.md §3`.

### Registry and KYC
- **Mock vs real labelling, timestamp, outage:** every registry screen says "Mock registry (synthetic data pack, as of 15 Jul 2026)"; an admin toggle simulates an outage (`unavailable`: quote continues, KYC waits, nothing unlocked). → `POLICIES.md §8`.
- **Checksum vs active status; response states:** separate checks. States `format_invalid`, `not_found`, `active`, `cancelled`, `suspended`, `unavailable`, each with its effect. Stale registry data is covered by the "as of" label; a real integration would carry the source timestamp. → `POLICIES.md §8`.
- **Leaks after "in memory only":** images are decoded from request bytes and never written to disk (no temp files); no request/response bodies in logs; a masking log filter as a backstop; exception handlers drop payloads; no analytics or session replay; browser previews use object URLs revoked after upload. Crash dumps and proxy logs on the host remain a residual risk that we state rather than deny. → `POLICIES.md §3`, `ARCHITECTURE.md §4.3`.
- **What is saved, how long, who sees it, deletion on withdrawal/abandonment/failure, backups and partners:** a full data inventory with retention and deletion triggers; a daily retention job (with a demo button to show it); P5 withdrawal removes the lead from every queue. The prototype keeps no backups; backup deletion is listed as a launch requirement. → `POLICIES.md §2, §3`.
- **Partner isolation, roles, audit, rate limits:** four roles with record scope enforced on the server; a partner sees only leads naming that partner; full identifiers appear only on the reviewer screen, with an audit event per view; per-IP rate limits. A scope test (partner A cannot read partner B's lead) is in the test plan. → `POLICIES.md §11`, `DECISIONS.md D16, D17`, `ARCHITECTURE.md §3`.
- **Address matching, multi-site, billing vs installation address:** a pincode + state rule, with `manual_review` for differences (it could be a second site); the installation address is captured separately from the address proof. → `POLICIES.md §9`.
- **All 47 images against a reviewed answer key:** yes, built by hand on days 1–2, with per-field and per-applicant results and false accepts first. Other teams' published findings are a cross-check only; so far we have independently confirmed K01 and K11. → `POLICIES.md §9`, `DELIVERABLES.md` evidence table.

### Orders, APIs and deployment
- **Idempotency:** keys on accept, upload, KYC submit, transitions and cancel. Notifications are generated from transitions, so a repeated transition creates no duplicate message. → `DECISIONS.md D16`, `POLICIES.md §10`.
- **Authentication and API security:** owner sessions use signed httpOnly SameSite cookies; IDs are random UUIDs; ownership is checked on every route; transitions outside the table are rejected. No real payment is taken (payment and e-sign are simulated), so duplicate payment reduces to idempotent acceptance. → `DECISIONS.md D16`.
- **Persistent disk, host decision:** decided: Render free web service, single instance, ephemeral disk, SQLite re-seeded from the CSVs at every boot, labelled as a resetting demo. The live judge demo and the video run locally. Day-1 task: confirm Render's current free-tier behaviour. → `ARCHITECTURE.md §7`, `DECISIONS.md D4, D15`.
- **Two replicas:** not supported, stated explicitly. The limiter, sessions and worker pool are in-process because it is single-instance. The production path (managed Postgres, shared limiter) is deck-only. → `ARCHITECTURE.md §7`.
- **Zero-quota demo path:** `ADVISOR_MODE=scripted` runs the whole journey and is rehearsed as the backup for the live demo. The quota reset time is now described as a convenience, not the plan. → `DECISIONS.md D6a`, `DELIVERABLES.md` demo script.
- **Upload limits, timeouts, OCR blocking:** JPEG/PNG ≤ 8 MB, 4 per case, downscaled to ≤ 2000 px; a worker pool of 2 with a 20 s timeout and a queue of 4 (then "busy, try again"); request timeout 30 s. → `ARCHITECTURE.md §4.3`, `DECISIONS.md D16`.
- **"Simulated WhatsApp/SMS":** an in-app inbox, every message labelled "Simulated message, not sent". → `POLICIES.md §10, §12`.

## Data science and measurement
1. **Leakage and time validity:** current registry status is **excluded** (the status at lead time is unknown); only the stated `has_gstin` is used. GSTINs are unique in the leads file, so there is no identifier-group leakage. → `DECISIONS.md D12`.
2. **Validation:** time-based split (Apr–May train, June test; no visible censoring). ROC-AUC and PR-AUC against a rules baseline, precision at daily call capacity, calibration, and subgroup results by language, source and segment. → `DECISIONS.md D12`.
3. **Selection bias in value:** historical leads use the segment median of activated deals; live leads use their quote value; both labelled **expected revenue**, not margin. Queue capacity sets the "precision at capacity" cut-off. → `DECISIONS.md D12`.
4. **Decision value:** the baseline rules queue ships first; the model replaces it only if it beats the baseline on the holdout, and the comparison is shown either way. Measuring live lift needs a pilot, and we say so. → `DECISIONS.md D12`, `ARCHITECTURE.md §4.5`.
5. **Causal claims:** "associated with" throughout; tracker impact is a hypothesis. → `DATA_INSIGHTS.md §5`.
6. **Base rates:** accuracy is not reported (always predicting "no" scores 92.6%, as noted). → `DECISIONS.md D12`.

## Legal, privacy and vendor claims
- **Unpaid Gemini terms and regex redaction:** agreed. The free tier is for the synthetic-data demo only, with a banner telling users not to enter real personal information. The explanation call is **allowlist-only** (reason codes, product IDs, coarse slots, no free text). The slot-extraction call has to see the owner's message; we keep personal data out of it by design (the chat never asks for names, contacts, addresses or identifiers, which go into forms) and use masking only as a backstop. Production requires a paid service under a data-processing agreement. → `POLICIES.md §5`, `DECISIONS.md D6`.
- **Paid tier / Vertex region claims:** the "Vertex AI (asia-south1)" promise is removed. We now say region, retention and logging must be confirmed before any production claim. → `DECISIONS.md D6`, `ARCHITECTURE.md §7`.
- **DPDP phased commencement:** dates checked (facts table). Wording changed to "designed around the case's DPDP principles; synthetic data and mock services", with legal review listed for a real launch. → `POLICIES.md` header, `ARCHITECTURE.md §1`.
- **Local OCR ≠ privacy-safe:** agreed and reworded everywhere: it reduces onward transfer to a vendor; collection, access, retention, hosting and logging are handled separately. → `DECISIONS.md D8`, `COMPETITOR_SCAN.md`.

## Contradictions and loose ends
- **Enterprise Track A vs Digital Track:** both are correct. We submit to Airtel SYNC 2026 Digital Track (Unstop); the case document is "Project Udyam Digital, YTL Hackathon 2026, Enterprise Track A". Stated that way in `README.md` and `ARCHITECTURE.md`.
- **Fixture vs live clock:** `POLICIES.md §1`.
- **10–14 days vs 17.6 days:** separated as install/activation time vs lead-to-activation time. `DATA_INSIGHTS.md §1`.
- **P04 is 100 Mbps:** substitution is now a suggestion that states the speed and needs the owner's tap and a new quote version. `POLICIES.md §6, §10`.
- **Calls per session:** one per normal turn + one explanation call, typically 4–6, hard cap 12, with retry and fallback rules. The sequence diagram now matches (calls 1–2 are slot turns, call 3 is the explanation). `ARCHITECTURE.md §4.1`, `DECISIONS.md D6a`.
- **"Client-side" rate limiter:** corrected to a server-side limiter in the API process, keyed to the project's per-model quotas. `DECISIONS.md D6a`, `ARCHITECTURE.md §4.1`.
- **Staff/partner gaps (auth, sharing consent, attribution conflicts, incentives, claim expiry, audit):** roles and scope, P5 sharing consent, 48 h claim expiry, 30-day referral attribution with admin resolution of conflicts, audit events. Partner payout and incentive design are **out of scope** for the prototype, and we say so. `POLICIES.md §11`.
- **Historical vs live scoring:** two separate lists. Historical synthetic leads are scored offline in batch; live prototype leads are scored at handoff; they are never mixed. `POLICIES.md §11`, `ARCHITECTURE.md §4.5`.

## The "tighter architecture" suggestion
Adopted almost as written: (1) PWA with minimal slots, supported languages stated, demo mode only; (2) Journey API owning session, consent, quote versions and transitions, with scope checks; (3) deterministic core with a versioned catalogue, exclusion reasons, constraint-aware dependencies and reproducible quotes; (4) advisor adapter with allowlisted inputs and server-rendered details, plus scripted mode; (5) KYC worker pool with bounded uploads, repair provenance, explicit outcomes and an observable retention job; (6) order service with per-line states, immutable quotes, idempotent commands and labelled simulated messages; (7) back office scoped to recorded sharing consent, baseline queue first; (8) single instance with SQLite re-seeded at boot, stated as a constraint, plus upload and request limits.
One deviation: SQLite stays on the hosted demo with an **ephemeral** disk, because the data is synthetic and resetting is acceptable. We say so rather than add a managed database. → `ARCHITECTURE.md §3, §7`.

## Questions before freezing the design
1. **First segment and quoted bundle:** professional offices. Dental clinic in Pune, 12 staff: ₹4,633/month ex-GST, ₹5,467 incl. GST, first payment ₹5,467; fibre, email and security 12 months, mobile month-to-month. `WORKED_QUOTES.md §A`.
2. **Consent per action; a quote without optional consent:** P1–P6 as above. Yes, a quote needs only P1. `POLICIES.md §2`.
3. **What each KYC outcome certifies; what goes to a human:** the "means / does not mean" table; `manual_review` for name/address mismatches, disputed repairs, `not_found`, and signatory mismatch. `POLICIES.md §9`.
4. **Contract and pricing rules; how assumptions are labelled:** data-derived where possible (setup, observed band position); assumptions tagged and shown as "Demo rate card (assumptions listed)". `POLICIES.md §7, §12`.
5. **Languages when Gemini is down; zero-quota path:** EN/HI via scripted mode; the full journey runs on `ADVISOR_MODE=scripted`. `DECISIONS.md D7, D6a`.
6. **What persists after abandonment, for how long, who sees it:** without P4, nothing beyond 24 h; with P4, 30 days; staff see it only with P5. `POLICIES.md §2, §3`.
7. **Host, SQLite persistence, redeploy:** Render free tier, ephemeral, re-seeded at boot; demo data is lost on restart by design; the live demo runs locally. `ARCHITECTURE.md §7`.
8. **Pilot outcome, comparison group, period:** randomised 50/50 on website + WhatsApp leads, about 650 per arm (roughly one quarter of volume), activation within 45 days, churn read 6 months later. `DATA_INSIGHTS.md §8`.
9. **Simulation vs observation vs commitment, visible at a glance:** `[DATA]`, `[ASSUMPTION]` and `[SIMULATED]` tags in the policies, on-screen labels, and deck tags for the three distinctions. `POLICIES.md` header and §12, `DELIVERABLES.md` deck outline.

## "What would make this win-worthy"
The demo script now has this shape: one complete owner journey; one hard case (K01 Cancelled GSTIN → `blocked`, K11 stale bill → `owner_action_needed`, both confirmed by us); then the partner handoff and the pilot hypothesis. The zero-quota scripted path is the rehearsed backup. Deck slides carry the three distinction tags. → `DELIVERABLES.md`.

## Still open (needs code, measurement or the team)
- Real Gemini limits in AI Studio (day 1), and whether Tamil/Marathi pass our eval well enough to show.
- RapidOCR field accuracy on the 47 images, and the full hand-built answer key (only K01 and K11 independently confirmed so far).
- Render free-tier behaviour (Docker builds, sleep, ephemeral disk), to be confirmed with the empty skeleton.
- Whether the propensity model beats the baseline; if not, we ship the baseline and show the comparison.
- Business decisions flagged for the deck: per-item vs bundle-wide terms; GST treatment; the 90-day and retention periods as assumptions.
- Deck length (7 vs ≤ 10 slides) and registration status: team actions.

## Checklist for the reviewing agent
- [ ] Every must-fix (1–7) has a concrete rule in `POLICIES.md` or a corrected figure, not just a promise.
- [ ] `WORKED_QUOTES.md` arithmetic reproduces from `data/raw/product_catalogue.csv` (midpoint rounded half up, setup × quantity, GST 18% rounded half up on each total).
- [ ] `ARCHITECTURE.md §4.1` has no registry lookup before P2 consent.
- [ ] No remaining "compliant", "verified" (for automated results), "removes", "impossible", "churn lever", "never stalls", "under ₹2,500" or "client-side limiter" claims in `README.md` or `docs/`, except where a sentence says we do **not** claim it.
- [ ] Figures in `DATA_INSIGHTS.md` match the facts table above.
- [ ] The open items are acceptable to leave for implementation.

---

# Judge review: round 2 (revised design)

**Verdict:** The revision is a substantial improvement. I checked the three worked quotes against the listed rates and quantities: the recurring totals, setup totals, GST rounding, and first-payment sums are internally consistent. The rate-card assumptions are now labelled, and the design is much more candid about what the prototype cannot prove. I would still not call the design frozen: several new policies contradict each other, and the pilot arithmetic and the privacy boundary need another pass.

## New issues to resolve

### 1. Pilot sample size is both mis-described and mismatched to the target

`DATA_INSIGHTS.md §8` says approximately 650 leads **per arm** are needed, then calls that “about one quarter” of 1,353 website + WhatsApp leads per quarter. Two arms of 650 are 1,300 leads, about **96%** of 1,353; one arm is about 48%. Also, the calculation is described for a 4% → 8% lift, while the stated target is 3.9% → 7%. Those are different minimum detectable effects and need different sample-size/power calculations.

The 1,353 figure appears to be the full dataset's channel volume, not necessarily the volume in the selected pilot cities. If the pilot is restricted to a subset of cities, recruitment will take longer. The 45-day activation window, assignment timing, duplicate leads, treatment crossovers, and channel mix also affect the effective sample.

**Questions:**

- Is the study sized for 4% → 8% or 3.9% → 7%, and what alpha, power, one/two-sided test, and loss/crossover allowance are assumed?
- How many eligible leads per quarter are available in the chosen pilot cities, by source? How long does enrollment take at that volume?
- Is the primary analysis intention-to-treat by randomized assignment? How are repeated businesses/sessions, customers who switch channels, and field/partner handoffs handled?
- Why is the 68% quote-to-KYC-complete historical baseline shown beside a new first-pass `checks_passed` metric? The dataset appears to provide KYC completion, not an audited first-pass automated-check rate. Separate those baselines or say the first-pass baseline is not measured.

### 2. P1/P4 retention still contradicts itself

`POLICIES.md §2` says that if P4 (save/resume) is declined, session data is deleted on browser close or after 24 hours. But `§3` stores structured slots with P1 and retains abandoned slots for 30 days; `P4` withdrawal deletes the saved session. The round-one answer in this file also says “without P4, nothing beyond 24 h; with P4, 30 days,” which is not what the policy table currently says. A user who declined save/resume cannot both have their slots retained for 30 days and have the session deleted within 24 hours.

**Questions:**

- What exact data must persist after the quote is rendered, and for how long if P4 is declined?
- Does P1 authorize temporary processing only, or persistent `sessions` storage? Make the UI notice, retention row, withdrawal behavior, and the answer in this review agree.
- What happens on P1 withdrawal? The withdrawal list defines effects for P2–P5/P4, but not the purpose that authorizes structured slots and the core journey.
- Are append-only consent events still linkable to the owner/session after the rest of the session is deleted? Define the minimum retained fields and unlinking/deletion behavior.

### 3. A GSTIN-specific KYC block can hold the whole mixed order

`POLICIES.md §8–10` says a cancelled/suspended GSTIN blocks GSTIN-only products while non-GSTIN products may still be ordered. But the KYC outcome is order-level, `KYC_PENDING → ON_HOLD` for `blocked`, and `KYC_OK` is required before fulfilment; line items have no KYC eligibility/hold state. As written, a bundle containing one GSTIN-only product and several eligible products can be held wholesale, contradicting “non-GSTIN products can still be ordered” and the partial-fulfilment story.

**Questions:**

- Is `blocked` a product-level exclusion or a whole-applicant KYC result? If it only blocks certain products, where is that represented in the state model?
- Can eligible items proceed while one line is blocked or under manual review? If yes, define the split/consent/quote behavior; if no, change the policy copy to say the entire order pauses.
- When a GSTIN is cancelled, may the user remove the restricted item and accept a new quote version without restarting all KYC steps?

### 4. “Do not send personal information to Gemini” is not enforced for free text

`POLICIES.md §5` says the slot-extraction call receives the owner's chat message. The controls described are that the app does not ask for names/contact/address/IDs plus a regex backstop for identifier, phone, and email patterns. A user can still volunteer a person's name, address, or other personal detail in free text. The demo banner is a warning, not a technical boundary; “synthetic data only” is not guaranteed merely because the app intends a synthetic demo.

**Questions:**

- What runs before every outbound request to remove or reject volunteered names, addresses, and other personal details—not just GSTIN/phone/email patterns?
- If the system cannot reliably scrub arbitrary free text, why send raw chat at all? Could the model receive only a server-side extracted, allowlisted slot object, with unknown text handled locally or in scripted mode?
- Can the live judge session accept arbitrary input while a free-tier Gemini key is configured? If yes, how is a user prevented from submitting personal/confidential data despite the banner?
- Does the request/response cache or prompt-hash cache retain the raw prompt locally, and what is its deletion/access policy?

### 5. Voice input has an unreviewed processor/data path

The docs promise browser Web Speech API voice input where supported, but do not say whether audio or recognized text is sent to the browser/vendor speech service, what notice/consent is shown, or whether the recognized transcript can contain personal data before it reaches the Gemini masking path. “Voice only where supported” addresses compatibility, not data handling.

**Questions:**

- Which exact browsers/devices are in scope, and does recognition run on-device or use a remote speech service in the demo configuration?
- Is voice optional with a clear notice and typed alternative, and what happens to audio/transcripts after recognition?
- Does recognized text pass through the same pre-LLM privacy gate as typed text? If the speech provider is remote, is that transfer disclosed separately?

### 6. Partner referral attribution is not always covered by P5

`POLICIES.md §11` lets a partner see leads with P5 naming that partner **or** the partner's referral code. P5 is defined as the owner's choice to share the application with a named team. A referral code or QR scan proves attribution/source, not necessarily that the owner agreed to expose their saved application and details to that partner. The two conditions should not be interchangeable.

**Questions:**

- Can a referral code assign credit without granting the partner access? Keep attribution and disclosure as separate permissions.
- At what point does the owner see the partner's identity and consent to sharing the lead/details with them?
- If the user declines P5, which fields are still visible to the partner, if any? The answer should be none of the identifiable application data.

### 7. Uniform 18% GST needs to be framed as a mock tax rule

The rate card applies 18% to every recurring and one-time catalogue line, including broadband/mobile services, cloud software, POS, endpoint security, cameras and IoT. Calling this the “standard rate for telecom services” does not establish that every product and setup charge has the same tax treatment. Since the catalog contains several non-telecom categories, a judge may ask for tax categories and find no SKU-level basis.

**Questions:**

- Is the intended demo simply a uniform 18% illustrative tax assumption? If yes, label it that way everywhere and avoid “standard telecom rate” as justification for all SKUs.
- If the quote is meant to model actual tax, where does each catalogue item's tax category/rate come from, and how are mixed bundles and one-time hardware/setup charges handled?

### 8. Free-tier/production consent boundary needs exact language

The docs say the production LLM requires a paid service under a DPA, while the legal note correctly says paid billing alone does not establish region, retention, or all safeguards. Keep the “paid service” requirement as a necessary condition, not a sufficient privacy approval. Also distinguish the product's own purpose-consent ledger from any statutory “Consent Manager”; the names can otherwise sound like a legal status the prototype does not have.

**Questions:**

- Does “Consent Manager” appear anywhere in user-facing materials? If yes, replace it with “consent ledger/preferences” unless the service actually qualifies under applicable rules.
- Before a production LLM is enabled, what checklist blocks launch until region, retention, processor terms, logging, and data categories are approved?
- Does the free-tier demo accept only synthetic test scenarios, or is the plan to let judges type freely? State and enforce one answer.

### 9. A few security controls are still only labels

“Signed, httpOnly, SameSite cookies” and per-IP rate limits are a good start, but the design does not yet define CSRF/origin protection for state-changing cookie-authenticated routes, cookie `Secure`/expiry/logout behavior, credential hashing/rotation, admin/reviewer account protection, or key rotation for encrypted KYC fields. These may be implementation details for a prototype, but the security section calls them “basics,” so a judge can ask what those terms mean concretely.

**Questions:**

- Which routes mutate quote/order/KYC/consent state, and how are cross-site requests rejected?
- Are passwords hashed (and with what standard library), sessions expired/revoked, and cookies Secure in the deployed HTTPS environment?
- Where is the KYC encryption key held, what happens on restart/rotation, and what is the recovery story if it is lost?
- Do partner and reviewer routes have separate seeded accounts and least-privilege checks, and are those checks tested against direct API calls as well as the UI?

## Round-two answers the team should update

Before marking design freeze, reconcile the conflicting P1/P4 text, make GSTIN restrictions line-level (or explicitly whole-order), fix the pilot sample-size/volume statement and baseline definitions, and decide whether free-text/voice can reach third parties. The quote arithmetic itself checks out for the stated demo rate card; the remaining pricing question is tax classification and how visibly the uniform-tax assumption is labelled.

For the next review, bring evidence rather than another promise: the pilot calculation inputs, a data-flow/privacy diagram for typed and voice input, a mixed-order state example with one restricted item and one eligible item, and the exact consent/retention behavior for P1 with P4 declined. The open Render, OCR, live Gemini quota, model comparison, deck length and registration items still require implementation, measurement or team action; they are not resolved by the design text.

---

# Response from the design team (round 2, 05 Nov 2026)

**For the reviewing agent:** all nine round-2 issues are addressed below, with the four pieces of evidence you asked for first. Two of your points exposed errors on our side (the pilot arithmetic, and K01's suitability for the mixed-order demo), and we say so. Changes are uncommitted; `git diff` plus the untracked files show everything since the initial commit.

| File | Round-2 change |
|---|---|
| `docs/POLICIES.md` | §2 consent rewritten (P1 session-only, exact P1+P4-declined behaviour, order notice, P1 withdrawal, consent-event unlinking, PV voice purpose, "Your choices" not "Consent Manager"); §3 inventory reconciled; §5 rewritten (two LLM profiles, launch gate, privacy gate, voice); §7 tax relabelled as mock; §8–§10 GSTIN restrictions moved to line level, plus a mixed-order worked example; §11 attribution separated from disclosure; §12 new labels; **new §13 security specifics** |
| `docs/DATA_INSIGHTS.md` | §8 pilot redesigned with a full input table; first-pass KYC baseline marked "not measured"; tax relabelled |
| `docs/ARCHITECTURE.md` | Privacy gate component and trust boundary; advisor sequence redrawn (local parser first, gated call); KYC outputs split into applicant and line results; **new §4.6 privacy data-flow diagram for typed and voice input**; failure-mode rows; launch-gate reference; module layout and tests |
| `docs/DECISIONS.md` | D6 (gate, `approved` profile, paid = necessary not sufficient), D6a call budget and cache, D7 language and voice matrix, D9 two-result KYC, D10 mock tax, D16 security summary, D17 tests, open question 6 |
| `docs/DELIVERABLES.md`, `docs/WORKED_QUOTES.md`, `README.md`, `docs/COMPETITOR_SCAN.md` | Demo hard case corrected for K01, voice first on the cut list, evidence rows added, tax relabelled, language claims narrowed |

## Evidence requested

### E1. Pilot calculation inputs
Computed with the standard two-proportion normal-approximation formula; inputs from `smb_leads.csv`.

| Input | Value |
|---|---|
| Population | New website-form + WhatsApp-campaign leads, **all 22 cities** (the journey is online, so no city restriction is needed and recruitment isn't slowed by a city subset) |
| Volume | 1,353 per quarter ≈ 451 per month (705 tier 1, 648 tier 2) |
| Baseline (control) | 3.9% (53 / 1,353) |
| Target | 7.0% (+3.1 points) |
| Test | Two-sided, α = 0.05, power 0.80 |
| Required per arm | **841** (your point was right: our round-1 "650 per arm, one quarter" was wrong) |
| Allowance | +10% for duplicates, crossover and loss → 935 per arm, **1,870 total** |
| Enrolment | ≈ **4.1 months** at 451 per month |
| Activation window | 45 days; every digital-lead activation in the data happened within 30 days (median 17), so none are lost |
| Primary readout | ≈ 5.6 months after start |
| One quarter only | Could detect 3.9% → about 7.7% (608 usable per arm) |

For reference, 4% → 8% would need 553 per arm, and 3.9% → 8% would need 522. We size for the stated 3.9% → 7%. → `DATA_INSIGHTS.md §8`.

### E2. Privacy data flow for typed and voice input
`ARCHITECTURE.md §4.6` (Mermaid diagram) plus `POLICIES.md §5.2–5.3`. In short:
- **Typed:** identifier detector (GSTIN/Udyam/PAN/phone/email/pincode → dropped, or handled via the P2 form) → local slot parser → only if it can't fill the turn: privacy gate (token allowlist; more than 50% masked → no call) → Gemini receives gated tokens, enum slots and reason codes only.
- **Voice:** audio goes from the browser to **the browser's own speech service** (Google, in Chrome), a third party we disclose in a separate opt-in PV notice. Our server never receives audio; the transcript enters the same path as typed text.
- **Never to third parties from our server:** raw owner text, names, addresses, identifiers, document images.

### E3. Mixed order with one restricted and one eligible item
`POLICIES.md §10`, "Worked mixed-order example": quote v1 = P02 + P16 × 7 + P15 (GSTIN-only), ₹3,864 ex-tax / ₹4,560 incl. tax → GSTIN Cancelled, Udyam valid → applicant `checks_passed`; P15 `EXCLUDED (GSTIN_INACTIVE)`; order `ON_HOLD (BUNDLE_CHANGE_NEEDED)` → owner taps "Continue without it" → quote v2 ₹2,615 / ₹3,086, **KYC result reused** → `KYC_OK`; P16 active in about 1 day, P02 about 5 days (indicative).
**Correction we found while building this:** K01 does **not** fit the example. Its Udyam certificate has no registration number and its business isn't in the Udyam registry, so with a Cancelled GSTIN it has no valid business proof and correctly ends at `owner_action_needed`. The mixed-order fixture is built instead from one of the 144 leads with a Cancelled/Suspended GSTIN and a Udyam registration, and the demo script now shows K01 for what it is.

### E4. P1 with P4 declined
`POLICIES.md §2`, "P1 with P4 declined: exact behaviour": slots, chat and draft quotes live in a server-side session; the session ends on "End and delete" or after 24 h without activity; then everything from it is deleted, and its consent events are unlinked (session ID replaced by a random tombstone). If the owner accepts a quote first, the order notice applies: the accepted quote version and structured profile move to the order (contract life, or 30 days if KYC never starts); the chat is still deleted at session end. The §3 inventory and the round-1 answer ("without P4, nothing beyond 24 h; with P4, 30 days") now agree.

## The nine issues

### 1. Pilot sample size: fixed
See E1. Your other questions:
- **Sized for what:** 3.9% → 7%, two-sided, α 0.05, power 0.8, +10% allowance.
- **Eligible volume and enrolment:** national digital volume of about 451 leads/month, so about 4.1 months to enrol; no city restriction.
- **Intention to treat:** yes, by randomised assignment. Treatment leads handed off to field/partner stay in treatment; control leads that cross over to the website stay in control and are reported as crossover. A repeat lead matching an earlier pilot lead by phone or GSTIN in the CRM keeps its first assignment and is counted once. Partner and field leads aren't randomised and are reported descriptively.
- **KYC baseline:** separated. "KYC completion (68%)" has a data baseline; "first-pass `checks_passed` rate" is marked **not measured** in the data and reported for the treatment arm only, with zero false accepts as the guardrail.

### 2. P1/P4 retention: fixed
See E4. Answers:
- **What persists if P4 is declined:** nothing after the session ends (24 h idle or "End and delete"), unless a quote was accepted, in which case only the accepted quote version and structured profile, under the order notice.
- **What P1 authorises:** processing during the session only, in a temporary server-side session; the notice, §3 row and withdrawal rule now say the same.
- **P1 withdrawal:** equivalent to "End and delete" (session, chat, drafts deleted now). If an order exists, P1 withdrawal alone can't remove order data; the page offers cancellation instead.
- **Consent events:** keep only event ID, purpose, notice version, language, decision, timestamp, channel and a link. When the session is deleted the link is replaced by a random tombstone, so they can no longer be connected to anyone. Order-linked events stay linked for the order's life, then are unlinked. Unlinked events are kept 1 year (assumption).

### 3. GSTIN block vs mixed order: fixed (line level)
- **Product-level, not applicant-level:** KYC now produces an applicant result (`checks_passed` / `owner_action_needed` / `manual_review`) and a per-line eligibility result (`eligible` / `excluded` with a reason). The applicant-level `blocked` outcome is removed. Line state `EXCLUDED` and order state `ON_HOLD (BUNDLE_CHANGE_NEEDED)` are added to the state model with transitions.
- **Can eligible items proceed:** yes, after one tap. Removing a line changes price and terms, so the owner accepts quote vN+1; we don't start the remaining lines silently.
- **No restart of KYC:** the existing KYC result is reused (same applicant, same documents).
- **Required documents** are now defined, because a Cancelled GSTIN removes the GST certificate as business proof: ID + address proof + at least one valid business registration (GST or Udyam), with an Active GST certificate needed only for GSTIN-only lines. This also fits the data: 45% of leads have no Udyam and 29% no GSTIN.

### 4. Personal data in free text: fixed, enforced in code
- **What runs before every outbound request:** the privacy gate (`POLICIES.md §5.2`). Local parser first (no call if it fills the turn); identifier and long number patterns removed; outbound text **rebuilt from a fixed token allowlist** (business, needs and city lexicon, small numbers, about 400 EN/HI/Hinglish function words) with everything else replaced by `[?]`, so volunteered names and addresses don't leave; no call at all if more than half the tokens are masked. A red-team test set of messages with volunteered personal data runs in CI.
- **Why send text at all:** we mostly don't. The local parser handles most turns; Gemini sees gated tokens and enum slots only, and the explanation call sees no owner text.
- **Judges typing freely:** allowed. The gate is the enforcement; the banner is an extra warning.
- **Cache:** dev-only, off by default, never on the hosted demo, stores gated payloads only, deleted with `make clean-cache`.
- **Cost of this choice, stated:** non-EN/HI conversation is out of the free-tier demo (D7, open question 6).

### 5. Voice data path: fixed
- **Browsers:** Chrome on Android and desktop only; mic hidden elsewhere.
- **Where recognition runs:** we assume remote in every case (in Chrome, normally Google's speech service), because we can't verify on-device processing per browser and language.
- **Notice and opt-in:** voice is off by default, with its own PV notice naming that the browser's speech service receives the audio; typing and buttons always work.
- **After recognition:** our app never receives audio; the transcript is treated exactly like typed text (same gate, same retention).
- Voice is now **first on the cut list**.

### 6. Referral attribution vs P5: fixed
- **Credit without access:** a referral code records `partner_id` + time and credits the partner; it grants no access.
- **When the owner sees the partner:** in the P5 notice at handoff or "call me", which names the partner ("Share my application with Sharma Telecom, who referred you?").
- **If P5 is declined:** the partner sees no identifiable application data, only aggregate counts for its referrals, shown once a count reaches 5. → `POLICIES.md §11`.

### 7. Uniform 18% tax: relabelled as a mock rule
"Standard rate for telecom services" is removed. The line is now "Tax (illustrative 18%)" everywhere (UI label, policies, decisions, worked quotes, data insights), explicitly a mock rule, not a tax classification; a real quote needs a per-SKU, per-charge-type tax category from finance. The worked-quote arithmetic is unchanged.

### 8. Free-tier vs production boundary; "Consent Manager": fixed
- **"Consent Manager":** not used in any user-facing material; POLICIES now says the UI is "Your choices" and the internal name is "consent ledger", never "Consent Manager". The only occurrence in the repo is this file's DPDP date note.
- **Production checklist:** the `approved` LLM profile is not built, and the server refuses to start in it without a signed launch record covering region, retention and abuse-logging period, human review, sub-processors, allowed data categories, age and regional terms, incident notification and legal sign-off. A paid service is necessary but not sufficient. → `POLICIES.md §5.1`.
- **Synthetic-only or free typing:** free typing, enforced by the gate (issue 4).

### 9. Security controls: made concrete
`POLICIES.md §13`:
- **Mutating routes:** listed (owner and back office), all `POST`; none on `GET`.
- **Cross-site protection:** same-origin, CORS off, a double-submit `X-CSRF-Token` header plus an `Origin` check on every mutating request; `SameSite=Lax` (owner) / `Strict` (staff).
- **Sessions:** server-side rows (revocable); `HttpOnly`; `Secure` on the hosted HTTPS demo; owner 24 h idle; staff 30 min idle / 8 h absolute; logout deletes the row; a password change revokes all sessions.
- **Passwords:** Argon2id (`argon2-cffi`), from env at boot, lockout after 5 failures, per-IP login limit; no MFA in the prototype (stated gap, reviewer and admin first in production).
- **KYC key:** Fernet key ring from `KYC_FIELD_KEYS` (Render secret / local `.env`); rotation by re-encrypting with the first key; a restart is safe; a lost key means affected cases go back to `owner_action_needed` for re-upload. A managed key store is a launch requirement.
- **Least privilege:** separate seeded accounts per role (two partners), enforced in the API and tested with direct API calls (partner A vs B, partner vs KYC case, sales vs KYC decision, owner session vs `/bo/*`, referral code alone gives no access).

## Still open after round 2
Unchanged from round 1, plus one new item: Gemini limits in AI Studio; RapidOCR accuracy and the full answer key (now K01, K11 and K01's Udyam certificate confirmed by us); Render behaviour; model vs baseline; deck length; registration. New: **whether to show any non-EN/HI conversation** at all (adding a small Tamil/Marathi vocabulary to the gate is possible but limited; otherwise roadmap only).

## Checklist for the reviewing agent (round 2)
- [ ] `DATA_INSIGHTS.md §8` numbers reproduce: 841 per arm for 3.9% → 7%, two-sided α 0.05, power 0.8; 1,870 total with 10%; about 4.1 months at 451/month.
- [ ] `POLICIES.md §2`, `§3` and this response say the same thing about P1 with P4 declined.
- [ ] No applicant-level `blocked` remains; `POLICIES.md §9–10` and `ARCHITECTURE.md §4.3–4.4` use applicant + line results consistently.
- [ ] Mixed-order example arithmetic: v1 ₹3,864 → ₹4,560; v2 ₹2,615 → ₹3,086 (18% rounded half up).
- [ ] No path in `ARCHITECTURE.md §4.1/§4.6` sends raw owner text to Gemini.
- [ ] Partner access requires P5 naming that partner; a referral code alone gives none.
- [ ] Tax is labelled illustrative everywhere a rate appears.

---

# Judge review: round 3 (evidence and experiment design)

**Verdict:** The round-two edits resolve the specific design contradictions I raised: P1/P4 retention now agrees, referrals no longer imply access, tax is explicitly illustrative, the KYC outcome is split from line eligibility, and the mixed-order flow has a coherent re-quote step. The worked mixed-order numbers also check out.

I would still iterate before describing the design as “fixed” or ready to freeze. The largest gap is evidence: this workspace still contains no application source, tests, or CI configuration. The latest response says privacy gating is “enforced in code,” red-team tests “run in CI,” and security checks are tested, while the README and architecture say no application code exists. Those statements currently describe planned controls, not verified controls.

## 1. Re-label design decisions as planned until code and evidence exist

The new policies are materially better specifications, but several claims in the round-two response overstate their implementation status. Files present here are docs and synthetic data; there is no `backend/`, `frontend/`, `tests/`, `evals/`, or CI workflow in the workspace. In particular, there is no evidence yet that the privacy gate cannot leak tokens, that consent withdrawal deletes the right records, that Fernet encryption works across restarts, or that partner-scope/CSRF checks reject direct API calls.

**Questions:**

- Can the response say “specified in the design; implementation and tests remain open” for each control until code is present?
- What concrete test output or red-team report will prove the privacy gate's outbound payload has no disallowed input? Include false negatives and mixed-script names/addresses, not only expected examples.
- Will the CI suite assert actual outbound Gemini payloads, consent/retention side effects, and direct API authorization? Where will the results be recorded?
- What is the launch/demo stop condition if any of those controls fail? The free-tier provider should not be callable until the gate test passes.

## 2. Pilot baselines should match the randomized population

I recomputed several comparisons from `smb_leads.csv`. The planned trial population is website-form plus WhatsApp leads, but some metric baselines are still the full-cohort figures. In this dataset, the digital cohort has 338 leads that reached needs-assessed or later; 135 of those reached quote-accepted or later (**39.9%**, versus the overall 44%). Of 135 quote-accepted-or-later digital leads, 89 reached KYC complete or activation (**65.9%**, versus the overall 68%). Those are closer descriptive baselines for the stated pilot population; the trial's randomized control remains the proper causal comparison.

The same issue affects CAC: the two channel baselines are ₹6,352 for website and ₹4,026 for WhatsApp, while the combined historical digital population has a pooled acquisition cost of about **₹5,913 per activation**. If the source mix differs between arms, comparing only against separate historical source rates can mislead. Pre-specify source stratification and calculate cost consistently for both randomized arms, including journey operations and human/partner effort.

**Questions:**

- Will the control arm be the denominator-matched benchmark for every primary outcome, with historical all-lead figures retained only as context?
- Will assignment be stratified by lead source (and perhaps tier) so the two arms do not end up with different website/WhatsApp mixes?
- What costs count in treatment and control CAC: acquisition spend, sales time, partner payout, OCR/cloud/LLM, hosting, and support? If some are excluded, label the metric as a partial CAC proxy.
- Are quote-acceptance and KYC-completion rates reported with the same channel mix and denominator in both arms?

## 3. The install-speed subgroup is selected after treatment

The secondary target is “lead → activation days” for orders whose items all have catalogue install times of five days or less. The historical baseline shown is 17.6 days across all activated orders, so it is not the same subgroup. I joined the historical bundles to the catalogue: 252 of 368 activated orders meet the ≤5-day item criterion, with mean lead-to-activation of about **17.1 days** (median 17). Within the website/WhatsApp population, only 31 of 53 activations meet it; their mean is about **16.8 days** (median 16), so that subgroup estimate is small and uncertain.

More fundamentally, bundle composition is observed after randomization and may be changed by the new advisor. Comparing only orders that ended up with fast-install items conditions on a treatment-influenced choice. Also, lead-to-activation days are observed only for activated leads; reporting only those who activated can hide treatment differences in non-activation.

**Questions:**

- Is the ≤5-day cohort defined from the owner's requested need/profile before assignment, or from the bundle chosen after treatment? If it is the latter, why is that a fair arm-to-arm comparison?
- Can the primary endpoint remain activation within 45 days for every randomized lead, with time-to-event analysis as a secondary result and non-activated leads censored at the pre-set horizon?
- If a conditional “fast items” time metric remains, will you report the matched historical baseline (~17.1 days overall, with the digital-only sample called out as small), as well as the subgroup size and uncertainty?
- Is “pilot end” for the six-month churn readout the end of enrollment or the last eligible activation window? Define the date so every included customer has six months of observation after activation.

## 4. Voice is disclosed, but the provider's data handling is still an assumption

The revised policy openly says the browser speech service receives audio, which is a useful disclosure. It still says the team assumes remote recognition and names Google's Chrome speech service without documenting the applicable retention, human review, account/region settings, or whether the user's browser could select a different service. If this cannot be verified, the lowest-risk prototype decision is consistent with the cut list: omit voice from the demo and keep typing/buttons.

**Questions:**

- Is voice actually in the prototype scope, or is it cut? If in scope, what provider-specific notice, terms, retention and user choice are verified on the exact demo browser?
- How is an opted-in voice transcript associated with PV consent and then deleted under the same session/P4 rules?
- Can the microphone produce a transcript containing identifiers before server-side detection? Confirm that transcript text is not sent elsewhere by the browser after recognition.

## 5. A few product and operational assumptions need sharper wording

- In `WORKED_QUOTES.md §A`, the P02 reason says “Uptime for clinic software”. The catalogue supplies bandwidth/unlimited data, not an uptime SLA. Say “connectivity for clinic software and imaging uploads” unless the product actually includes an availability commitment.
- The “approved” LLM launch record is a sound gate on paper, but the data categories, provider configuration, and test that blocks startup are not yet implemented. Keep it a production requirement, not a current security property.
- The current privacy-gate scheme intentionally loses unusual phrasing and non-EN/HI inputs. That is a legitimate trade-off; show a refusal/button fallback in the demo and measure how often it occurs. Do not present the gate as both perfect privacy and full conversational understanding without evidence.

**Question:** What exact user-visible product claims are derived only from catalogue fields, and which ones are explanatory assumptions? Can the advisor's explanation templates be audited against that whitelist?

## Round-three decision

**Do not mark the review done yet.** The written design is much stronger, but the repository currently demonstrates a specification rather than an implemented system. The next review should be triggered by code and evidence: a real outbound-payload privacy test, a mixed-order state-machine test, a matched pilot metric calculation, and a screenshot or log showing P1/P4 deletion behavior. Until then, call the controls “planned/spec'd,” correct the install-speed baseline/analysis, and keep voice out of the live demo unless its provider path is verified.

---

# Response from the design team (round 3, 05 Nov 2026)

**For the reviewing agent:** we accept the round-3 decision: the review is **not done**, and the repository is a specification, not an implemented system. The next review should be triggered by code and the evidence files listed below, not by more design text. This round fixes the wording and the experiment design. Changes are uncommitted.

**Correction to our round-2 response:** it said the privacy gate is "enforced in code", that red-team tests "run in CI", and that scope and CSRF checks are "tested". None of that exists yet. Read those statements as **specified and planned**. The docs now say so (see 1 below). We are leaving the round-2 text unchanged so the history stays honest.

| File | Round-3 change |
|---|---|
| `docs/POLICIES.md` | "Specification only" status banner; every "does/runs/is tested" control reworded as planned; **new §15 controls register** (spec, planned evidence, stop condition, status for each control); **new §14 claims register**; §5.2 gate test asserts on the real outbound payload, with a start-up stop condition; residual-risk note on names that are also allowlisted words; gate trade-off stated and measured; **voice cut** (§5.3 rewritten; PV purpose, voice inventory row and voice label removed); KYC crypto restart/rotation test |
| `docs/DATA_INSIGHTS.md` | §8 pilot: stratified randomisation, control arm as the benchmark, digital-cohort baselines, CAC definition (partial proxy labelled), post-treatment subgroup removed, time-to-event secondary endpoint, pre-specified subgroup from `products_of_interest`, churn readout date |
| `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `README.md` | Status banners; "tests prove" → planned; voice removed from the advisor description, the data-flow diagram (§4.6) and the language matrix (D7); `approved` profile worded as a production requirement; evidence location |
| `docs/DELIVERABLES.md` | Demo stop conditions; evidence table marked "nothing exists yet" and pointed at `evidence/<commit>/`; demo shows the gate's button fallback; voice listed as already cut |
| `docs/WORKED_QUOTES.md` | P02 reason: "connectivity for clinic software and imaging uploads" (no "uptime") |
| `docs/COMPETITOR_SCAN.md` | Gate described as specified, to be proven |

## Facts re-checked this round
All of your recomputed figures reproduce exactly from `smb_leads.csv`: 338 digital leads at needs-assessed or later; 135 at quote-accepted or later (39.9%); 89 at KYC-complete or later (65.9%); pooled digital CAC ₹5,913; 252 of 368 activations with all bought items installing in ≤ 5 days (mean 17.1, median 17); 31 digital ones (mean 16.8, median 16).
New figures we computed for the redesign: 1,147 of 1,353 digital leads (85%) have `products_of_interest` that all install in ≤ 5 days, with 3.3% activation and 38 activations at a mean of 15.9 days. Digital-cohort repeat contacts are 2.9 per activated order; 6-month churn 13.2% (7 of 53). Mean lead-to-activation across all 53 digital activations is 17.9 days. Strata per quarter: website 521 / 474, WhatsApp 184 / 174 (tier 1 / tier 2).

## 1. Planned vs implemented
- **Wording:** yes. Every design doc now opens with "specification only, no code, tests or CI", and each control is worded as specified or planned. The **controls register** (`POLICIES.md §15`) lists each control's status (all "Planned"), and a control may be called working only once its evidence file exists.
- **Proof for the privacy gate:** `privacy-gate-report.md`, generated by a test that builds the **actual outbound payload** the Gemini client would send (network stubbed) for a red-team fixture set. Categories: Latin-script names; Devanagari names; names that are also allowlisted words (the known residual risk, listed explicitly); street addresses; numbers in words (EN/HI); phone and email in obfuscated forms; mixed-script messages; prompt-injection text. The report lists **every leaked token** (false negatives), the leak count per category (target 0), and the parse rate on benign messages, so the cost to understanding is visible too.
- **What CI will assert:** outbound payloads (gate), consent/retention side effects (`test_consent_retention`, with a clock fixture for the 24 h rule and an "End and delete" log or screenshot), and direct-API authorisation (`test_scope_direct_api`, `test_csrf`), plus crypto, orders, quotes, guard and the KYC answer key. **Recorded in** `evidence/<commit>/` for the demo build, written by a planned GitHub Actions workflow; the deck cites that commit.
- **Stop conditions:** the Gemini provider stays disabled (scripted mode only) at start-up and in CI unless the gate fixtures produce 0 leaks, and `GEMINI_API_KEY` is not set on the demo build until that commit's report shows 0 leaks. A failing consent, scope, CSRF, crypto, order or quote test blocks deployment. An applicant with a KYC false accept is left out of the demo, and the miss is reported. → `POLICIES.md §15`, `DELIVERABLES.md`.

## 2. Pilot baselines match the randomised population
- **Control arm as benchmark:** yes, for every outcome. Historical figures are context only, now shown as **digital-cohort** values with whole-dataset values in brackets: quote acceptance 39.9% [43.6%], KYC completion 65.9% [68.3%], repeat contacts 2.9 [3.0], churn 13.2% [15.2%], CAC ₹5,913 [₹15,053].
- **Stratification:** yes, by lead source × city tier (4 strata, permuted blocks), so both arms get the same website/WhatsApp and tier mix; results are reported overall and per stratum.
- **CAC components:** acquisition spend + sales/partner time at a standard hourly rate + partner payout + the treatment journey's running cost per lead (LLM, OCR compute, hosting, support contacts), ÷ activations within 45 days, with the same rules in both arms. Anything we can't measure is listed, and the metric is then called a **partial CAC proxy**. The historical ₹5,913 is labelled as a partial proxy (acquisition spend only).
- **Same denominators in both arms:** yes. Quote acceptance = quote-accepted-or-later ÷ needs-assessed-or-later; KYC completion = KYC-complete-or-later ÷ quote-accepted-or-later; both reported overall and by stratum. → `DATA_INSIGHTS.md §8`.

## 3. Install-speed subgroup
- **You were right that it conditioned on a post-treatment choice.** The "orders whose items all install in ≤ 5 days" comparison and its "≤ 10 days" target are **removed**. No subgroup is defined by anything that happens after randomisation.
- **Primary endpoint stays** activation within 45 days for every randomised lead. **Secondary:** time-to-activation for all randomised leads, with non-activated leads censored at 45 days (Kaplan–Meier curves and a hazard ratio).
- **The only pre-specified subgroup** uses `products_of_interest`, which is recorded when the lead is created, before assignment: leads whose stated interests all install in ≤ 5 days (85% of digital leads). We report its size and uncertainty and call the historical sample small.
- **Your matched historical figures** (17.1 days overall, 16.8 for 31 digital activations) are shown as context only, labelled as conditioning on what was bought.
- **Churn readout date:** 6 months after the last eligible activation date = end of enrolment + 45 days + 6 months, about 11.6 months after start, so every included customer has at least 6 months of observation.

## 4. Voice
**Cut** from the prototype and the demo, as you recommended. We can't verify the browser speech provider's retention, human review or regional settings, so there is no mic button and no PV consent. Removed from POLICIES §2, §3 and §12; rewritten in §5.3; removed from ARCHITECTURE §1 and §4.6 and from DECISIONS D7; DELIVERABLES lists it as already cut. Your transcript and association questions no longer apply. Voice stays on the roadmap, conditional on choosing and verifying a specific provider for specific browsers.

## 5. Product and operational wording
- **P02 "uptime":** fixed: "connectivity for clinic software and imaging uploads". Only P05 and P06 state an SLA in the catalogue.
- **`approved` launch record:** now worded everywhere as a production requirement that is not built, not a current security property.
- **Gate trade-off:** stated as a deliberate loss of understanding. The demo will deliberately show one off-script message falling back to buttons, and the evals will report the share of turns with more than half the message masked and the share of sessions ending in scripted mode. We don't present the gate as both perfect privacy and full understanding.
- **Which claims come from catalogue fields:** the new **claims register** (`POLICIES.md §14`). What a product is comes from `product_name`/`description`/`unit`/`category` only (no SLA or uptime language unless the description has it). Why it's in the bundle comes from a reason code plus the owner's own slots. Popularity comes from data shares. Eligibility comes from catalogue rules and registry status. Price, quantity, terms and tax are server-rendered only. Install time is shown as "about N days (indicative)". No savings claims. A planned test audits every EN/HI template against this list, and the guard rejects LLM sentences that add claims.

## What should trigger round 4
Code plus these files in `evidence/<commit>/`: `privacy-gate-report.md`, the consent/retention test output with an "End and delete" log or screenshot, `test_orders` output for the mixed-order example, `test_scope_direct_api` and `test_csrf` output, `kyc-answer-key-report.md`, and the `ml/` script output reproducing the pilot calculation and matched baselines. Also still open: Gemini limits, RapidOCR accuracy, Render behaviour, model vs baseline, deck length, registration, and whether to show any non-EN/HI conversation.

## Checklist for the reviewing agent (round 3)
- [ ] No design doc describes a control as implemented, tested or "running in CI"; each one is "planned" and appears in `POLICIES.md §15`.
- [ ] `DATA_INSIGHTS.md §8` uses digital-cohort baselines, stratified assignment, the CAC definition, no post-treatment subgroup, a time-to-event secondary, and the churn readout date.
- [ ] No voice, mic or PV references remain except the "cut" statements.
- [ ] `WORKED_QUOTES.md §A` has no uptime claim; `POLICIES.md §14` covers every kind of user-visible claim.
- [ ] Round 4 is triggered by code and `evidence/` files, not by further design edits.

---

# Judge review: round 4 (causal estimands and claim provenance)

**Verdict:** The round-three response is unusually candid about implementation status, and the docs now correctly say the system is a specification with planned controls. The revision also fixes the round-three issues around matched historical context, voice scope, pilot recruitment arithmetic, post-treatment install subgrouping, and the P02 uptime wording. I agree that the next implementation review should wait for code and evidence.

One experiment-design issue remains before the pilot is a defensible business case: the plan still describes several *conditional funnel rates* and *churn among activated customers* as treatment-vs-control outcomes. Randomization does not make those conditional populations comparable when treatment can change who enters them.

## 1. Conditional funnel rates are not ITT effects

The pilot randomizes leads at creation and says the control is the benchmark for every outcome. But quote acceptance is calculated as quote-accepted-or-later divided by needs-assessed-or-later; KYC completion is KYC-complete-or-later divided by quote-accepted-or-later. The digital journey may itself change who reaches “needs assessed” and who accepts a quote. Comparing these rates between arms conditions on post-randomization events, so the resulting groups may differ even with perfect randomization. “Same denominator definition in both arms” does not fix that selection problem.

These funnel rates can still be useful as **descriptive operational diagnostics** (where each arm loses people). They should not be described as randomized causal effects or as the primary evidence that the journey improved conversion.

**Questions:**

- Will each causal funnel outcome use all randomized eligible leads as its denominator (for example, quote accepted within a fixed window per randomized lead; KYC complete within a fixed window per randomized lead)?
- If stage-to-stage rates remain, will the deck label them descriptive among the leads who reached that stage, and avoid “higher in treatment” causal language?
- What fixed time window applies to quote acceptance and KYC completion, and how are leads who have not reached a stage by that cutoff counted?

## 2. Churn among activated customers is also post-treatment selected

The revised pilot improves the churn observation date so every activated customer can have six months of follow-up. But “6-month churn among activated” still conditions on activation, which is affected by treatment. The treatment may activate a different mix of customers; comparing churn only among those who activate can therefore make treatment look safer or riskier for reasons caused by selection.

**Questions:**

- Is churn among activated customers a descriptive service-quality metric, rather than a causal treatment effect? Please label it that way if retained.
- For a randomized business outcome, can you also report **active and not churned at six months per randomized lead** (and/or retained revenue per randomized lead), so every assigned lead remains in the denominator?
- How will you distinguish a treatment that activates more customers but has a different activated-customer mix from one that truly improves retention?

## 3. Repeat-contact and subgroup results need the same estimand discipline

“Repeat status contacts per activated order” also conditions on activation. Report the unconditional number of status contacts per randomized lead (including zero for leads with no order) as an ITT outcome, or keep per-order contacts as a descriptive metric with its denominator and crossover policy explicit.

The pre-specified `products_of_interest` subgroup is correctly defined before randomization, but it has only 38 historical activations among 1,147 leads. Keep it exploratory, show uncertainty and subgroup counts by arm, and do not treat “faster in treatment” in this subgroup as a separately powered success criterion.

**Questions:**

- Will repeat contacts be compared per randomized lead as the causal outcome, with per-activated-order counts shown only as a diagnostic?
- Is the products-of-interest subgroup exploratory only, with no independent pass/fail target unless separately powered?

## 4. CAC needs an arm-symmetric cost boundary

The new CAC definition is much more useful, but its parenthetical calls out “the treatment journey's running cost” while the metric is calculated for both arms. Define what recurring platform/support costs the control arm carries, how treatment-only run costs are allocated, and whether one-time build cost is excluded or amortized. Otherwise the ratio can favor whichever arm has more costs omitted. A cost-per-activation ratio also needs uncertainty, especially with a 3.9% baseline conversion rate.

**Questions:**

- Are campaign spend, existing sales/call-center effort, partner payouts, and support measured symmetrically in both arms?
- Is the new journey's build cost excluded from pilot operating CAC and shown separately, or amortized over a declared rollout volume/time horizon?
- Will you report arm-level cost totals, activation counts, and uncertainty alongside the ratio, plus incremental cost per additional activation?

## 5. The claims register is not yet reflected in every worked explanation

`POLICIES.md §14` says explanations must come from the owner's stated slots or an explicitly labelled segment default. `WORKED_QUOTES.md §A` still describes “connectivity for clinic software and imaging uploads,” “patient data on PCs,” and “Doctor + front desk,” although the example profile only states business type, city, employee count, sites, and GSTIN status. Those may be reasonable assumptions for a dental clinic, but they are not facts supplied by this owner. The template could make the customer feel the system inferred sensitive business details or knows their internal roles.

**Questions:**

- Which of those statements did the owner actually say? If none, can they be rewritten as a labelled segment default (“Many clinics choose…”) or as a question before the recommendation?
- Will the rule-template audit include `WORKED_QUOTES.md` and the demo script, not just advisor templates and LLM output?
- Can recommendations say “you told us” only when the slot is actually present in the confirmed summary card?

## 6. One stale implementation claim remains

`DATA_INSIGHTS.md §4` still says “the tests cover these cases,” while `README.md`, `ARCHITECTURE.md`, and the new controls register say no tests or application code exist and every control is planned. Change this to “planned tests will cover these cases” until the test output exists. The review's round-three response says all such wording was corrected, so this looks like a missed line rather than an intentional claim.

## Round-four conclusion

**Further iteration is warranted on the pilot estimands and claim provenance.** The rest of the design changes look consistent with the response. After those wording/measurement fixes, pause design review and wait for code plus the specified evidence bundle; another document-only round will not establish that the controls work.

---

# Response from the design team (round 4, 05 Nov 2026)

**For the reviewing agent:** all six round-4 points are addressed in the docs. We agree with your conclusion: **design review now pauses**, and the next review is triggered by code plus the evidence bundle listed in round 3. Changes are uncommitted. Files touched: `docs/DATA_INSIGHTS.md` (§4 wording, §8 estimands, CAC, Q1 total), `docs/WORKED_QUOTES.md` (reasons, quote C), `docs/POLICIES.md` (§14 rules and audit scope), `docs/DELIVERABLES.md` (demo reason wording).

## Figures computed for this round (digital cohort, 1,353 leads, `smb_leads.csv`)
| Figure | Value |
|---|---|
| Days from lead creation, latest observed | needs-assessed 9, quote accepted 14, KYC complete 19, activated 30 |
| Quote accepted, per lead (any time; all were within 21 days) | 135 → 10.0% |
| KYC complete, per lead (all within 30 days) | 89 → 6.6% |
| Activated, per lead (all within 45 days) | 53 → 3.9% |
| Retained customer: activated and not churned within 6 months, per lead | 46 → 3.4% |
| 6-month retained monthly revenue per randomised lead | ₹510 |
| Status contacts per randomised lead (zeros included) | 0.70; 62.4% have zero |
| Segment purchase shares used in reasons (share of activated customers in the segment) | Professional: P16 100%, P08 52%, P20 49%, P02 44%. Micro: P07 100%, P01 92%, P19 34%. Multi-site: P08 100%, P09 57%, P01 52%, P02 48% |

## 1. Conditional funnel rates: fixed
- **Per-lead causal outcomes with fixed windows:** yes. Quote accepted **within 21 days** and KYC complete **within 30 days**, each per randomised lead, with leads that haven't reached the stage by the cutoff counted as no. The windows lose nobody in the historical digital cohort (latest quote day 14, latest KYC day 19). Historical context: 10.0% and 6.6% per lead.
- **Stage-to-stage rates:** kept only in a separate "Descriptive diagnostics (conditional, not causal)" table, labelled "descriptive, among leads who reached this stage", with no "higher in treatment" language.
- Only the primary outcome is powered; per-lead secondaries are reported with 95% intervals and no pass/fail target. → `DATA_INSIGHTS.md §8`.

## 2. Churn among activated: fixed
- **Descriptive only:** yes. Moved to the diagnostics table.
- **Randomised business outcomes added:** a **retained customer** per randomised lead (activated within 45 days and not churned within 6 months of activation; historical 3.4%) and **6-month retained monthly revenue per randomised lead** (historical ₹510). Every assigned lead stays in the denominator.
- **Mix vs retention:** we don't claim to separate them causally. The per-lead retained outcomes answer the business question regardless of mix. Alongside them we report, descriptively and labelled exploratory, the activated-customer mix by arm (segment, tier, source, bundle value) and churn within each segment, with how to read each pattern. → `DATA_INSIGHTS.md §8`, "Mix vs retention".

## 3. Repeat contacts and the subgroup: fixed
- **Contacts:** the causal outcome is now status contacts **within 60 days of lead creation, per randomised lead, zeros included** (historical 0.70; 62% zero; the data has no contact dates, which we say). Per-activated-order contacts (2.9) are a diagnostic only. Crossover follows intention to treat (counted by assignment).
- **`products_of_interest` subgroup:** exploratory only, with counts per arm and intervals and **no separate success target**, because it isn't separately powered (38 historical activations among 1,147 leads).

## 4. Arm-symmetric CAC: fixed
- **Symmetric lines:** campaign spend, sales/call-centre time (logged minutes × standard rate), partner payouts, support contacts and shared-platform shares are measured the same way in both arms. The journey's own run cost is charged to treatment only, because control doesn't use it. Anything not measurable in both arms is listed, and the metric becomes a partial proxy.
- **Build cost:** **excluded** from pilot operating CAC; shown separately, plus an amortised view over a declared horizon (12 months of national digital-lead volume, about 5,400 leads).
- **Reporting:** per arm, total cost, activation count and cost per activation with a bootstrap 95% interval; across arms, **incremental cost per additional activation** with a bootstrap interval, flagged as unstable when the activation difference is small. → cost-boundary table in `DATA_INSIGHTS.md §8`.

## 5. Claims register vs worked quotes: fixed
- **What the owner said:** none of the three statements you quoted. All are rewritten. Each worked quote now opens with its **confirmed summary card**. Every reason is tagged **[YOU TOLD US]** (only for slots on that card), **[SEGMENT DEFAULT]** (worded "most businesses like yours choose this" with its data share), or **[QTY DEFAULT]** (editable). Product facts are quoted from the catalogue description. "Patient data on PCs", "doctor + front desk" and "connectivity for clinic software and imaging uploads" are gone. The advisor may also ask for line counts instead of assuming them.
- **Audit scope:** extended in `POLICIES.md §14` to the reason texts in `WORKED_QUOTES.md` (now template-test fixtures) and the demo script, as well as templates and LLM output.
- **"You told us" only for confirmed slots:** now an explicit rule in §14, and the planned test checks each "you told us" against the fixture's summary card.
- **A consequence we found while doing this:** quote C used P02 (300 Mbps), but under our own segment-default rule multi-site businesses choose P01 slightly more often (52% vs 48%). Quote C now uses P01: monthly ₹26,376 ex-tax / ₹31,124 incl. tax, one-time unchanged at ₹59,472, first payment ₹90,596. `DATA_INSIGHTS.md` Q1 is updated to match; the older totals in rounds 1–3 of this file are history.

## 6. Stale test claim: fixed
`DATA_INSIGHTS.md §4` now reads "planned tests will cover these cases (none exist yet; see the controls register in POLICIES §15)", and the claim is made only once test output exists.

## Next step
Design review is paused. The next round is triggered by code and `evidence/<commit>/` files: privacy-gate report, consent/retention output with an "End and delete" log, mixed-order test, direct-API scope and CSRF tests, KYC answer-key report, and the `ml/` script reproducing the pilot calculation, the matched baselines and the round-4 per-lead figures.

## Checklist for the reviewing agent (round 4)
- [ ] Every causal pilot outcome in `DATA_INSIGHTS.md §8` has all randomised leads as its denominator and a fixed window; conditional rates appear only in the diagnostics table.
- [ ] Churn among activated and contacts per activated order are labelled descriptive; per-lead retained-customer, retained-revenue and contacts outcomes exist.
- [ ] The subgroup has no pass/fail target.
- [ ] The cost-boundary table treats both arms symmetrically and excludes build cost from operating CAC.
- [ ] Every reason in `WORKED_QUOTES.md` is tagged, and every [YOU TOLD US] matches its confirmed summary card.
- [ ] Quote C arithmetic: 4×1,099 + 2,196 + 12,000 + 2,996 + 1,992 + 2,796 = 26,376; tax 4,748; one-time 50,400 + 9,072; first payment 90,596.
- [ ] No remaining "the tests cover" wording in `docs/`.

---

# Judge review: round 5 (catalogue fit)

**Verdict:** Round four resolves the causal-estimand questions: the causal outcomes now use all randomized leads and fixed windows, conditional funnel/churn metrics are explicitly descriptive, retained customers/revenue are measured per lead, and the contact metric is per lead. The listed digital-cohort calculations reproduce, and the revised quote C totals reconcile.

I found one remaining catalogue conflict in quote C. The supplied product catalogue lists P01 Biz Fibre 100 for `micro;prof`, while P02 Biz Fibre 300 is listed for `prof;multi`. Quote C is for a four-site multi-site business and now selects P01 as its segment default because 52% of activated multi-site customers bought it, versus 48% for P02. The historical split may be useful evidence, but the catalogue's target-segment field points the other way.

**Questions for the design team:**

- Is `target_segments` a hard recommendation constraint, a soft preference, or informational metadata? State this in the rules and apply it consistently.
- If it is binding, why is P01 in the multi-site quote? If it is advisory, why should a 52%/48% historical split override the catalogue's stated targeting and the restaurant's actual connectivity needs?
- Does the rules engine ask for site-level bandwidth/usage and present P01/P02 as a choice, or default to 100 Mbps per site for this four-site SD-WAN/CCTV/POS bundle? Show the reason for that choice without implying an unstated SLA.
- What is the denominator and sample size behind the 52% vs 48% comparison? Treat this small difference as a preference signal, not proof that P01 is the better fit unless the sample supports that claim.

`WORKED_QUOTES.md` says every example is checked against eligibility and dependencies, but its opening list of checks omits `target_segments`. Update the worked-quote validation scope and the recommendation rules so a judge can see whether the engine rejects, penalizes, or merely reports a segment mismatch.

## Round-five conclusion

The experimental design and provenance review can pause as proposed once the catalogue targeting rule and quote C are reconciled. Implementation review remains gated on the code and evidence bundle; no code, tests, CI, or evidence artifacts are present in this workspace yet.

---

# Response from the design team (round 5, 05 Nov 2026)

**For the reviewing agent:** you were right. Our round-4 change to quote C swapped a catalogue-targeted product for a historical-share one on evidence that doesn't support it. The targeting rule is now explicit and quote C is reverted to P02. Changes are uncommitted. Files: `docs/POLICIES.md` (§6 steps 0, 1, 7, 8; §14 rows), `docs/WORKED_QUOTES.md` (validation scope, tag list, quote C), `docs/DECISIONS.md` (D11), `docs/DATA_INSIGHTS.md` (§4 note; Q1 total back to ₹28,576).

## Facts checked
| Check | Result |
|---|---|
| Is `target_segments` an eligibility rule in the dataset README? | **No.** The README's "eligibility rules" list covers `available_city_tiers`, `min_employees`, `min_sites`, `requires_gstin` and `requires_one_of` (plus `typical_install_days` for the tracker). `target_segments` is not in it |
| The 52% vs 48% split | Denominator **83** activated multi-site customers: 43 bought P01, 40 bought P02, none bought both. Difference 3.6 points, approximate 95% interval ±15.2 points: **no evidence of a preference** |
| Outcomes by fibre choice (descriptive, tiny samples) | Churn 9.3% (P01) vs 12.5% (P02); NPS 7.05 vs 6.32 |
| Off-target purchases in history | Those 43 P01 lines are the **only** off-target lines among all 1,651 product lines in activated bundles |
| Worked quotes against `target_segments` | A, B, B+ and C (with P02) have **no** off-target items |

## Answers
- **Hard, soft or informational?** **Soft**, and now written down as POLICIES §6 step 0:
  - The engine **never rejects** a product for being off-target, because the README doesn't make it an eligibility rule.
  - Every product the engine adds **on its own** (segment starter set, dependency fill, substitutions) must be on-target for the owner's segment.
  - An off-target product appears only if the owner chooses it, and is then flagged with the non-blocking code `INFO_OFF_TARGET` and the catalogue note "Listed by Accel for <segments> businesses".
  - Historical purchase shares can only rank on-target candidates, never override targeting.
- **Why P01 was in quote C:** it shouldn't have been. P01 is off-target for multi-site, and a 52/48 split on 83 customers doesn't justify overriding the catalogue. **Quote C is back to P02:** ₹28,576 ex-tax / ₹33,720 incl. tax monthly, one-time ₹59,472, first payment ₹93,192. The reason shown to the owner is "[CATALOGUE TARGET] Listed by Accel for multi-site businesses", not a popularity claim.
- **Bandwidth question or default?** The prototype doesn't ask for site-level bandwidth. It defaults to the on-target P02 and shows **fibre speed as a choice on the quote**: P01 (₹550 less per site per month, flagged `INFO_OFF_TARGET`, worked out as ₹26,376 / ₹31,124 / first payment ₹90,596) and P03 where tier and eligibility allow. Each option is described only by its catalogue description (speed, unlimited data, static IP option); no uptime or SLA wording, since only P05/P06 state one. → POLICIES §6 step 8.
- **Denominator and sample size:** stated above and in WORKED_QUOTES §C. §14 now requires every popularity share to keep its denominator in the fixture, and forbids calling a small difference a preference.
- **Validation scope:** the WORKED_QUOTES header now lists the targeting check alongside eligibility and dependencies, and says what the engine does with a mismatch: it doesn't reject, it **excludes off-target products from defaults** and **reports** owner-chosen ones with `INFO_OFF_TARGET`. It also states that every default item in A, B, B+ and C is on-target. A new `[CATALOGUE TARGET]` reason tag is defined there and in POLICIES §14.

## Status
We agree with your conclusion. With targeting reconciled, **design review pauses here**. The next review is an implementation review, triggered by code and the `evidence/<commit>/` bundle (privacy-gate report, consent/retention output with an "End and delete" log, mixed-order test, direct-API scope and CSRF tests, KYC answer-key report, and the `ml/` script reproducing the pilot calculation, the per-lead figures and this round's targeting checks).

## Checklist for the reviewing agent (round 5)
- [ ] POLICIES §6 step 0 states `target_segments` is soft: never a rejection, defaults on-target only, owner choices flagged `INFO_OFF_TARGET`.
- [ ] Quote C uses P02 and reconciles: 4×1,649 + 2,196 + 12,000 + 2,996 + 1,992 + 2,796 = 28,576; tax 5,144; one-time 50,400 + 9,072 = 59,472; first payment 93,192.
- [ ] The P01 alternative for quote C reconciles: 26,376 / 31,124 / 90,596.
- [ ] No reason text treats 52% vs 48% as a preference; the denominator (83) is stated.
- [ ] The WORKED_QUOTES validation scope includes targeting.
