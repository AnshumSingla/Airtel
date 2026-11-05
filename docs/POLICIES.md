# Business rules and policies (prototype)

> **Status: specification only.** No application code, tests or CI exist yet. Every control in this file is **planned**. Where a sentence says the system "does" something, read it as "is specified to". The status and planned evidence for each control are tracked in the [controls register (§15)](#15-controls-register), and a control counts as done only when its evidence exists there.

This file defines the rules the code will implement. Each rule carries one of three labels, which also show up in the UI and the deck:

- **[DATA]**: observed in, or derived from, the supplied synthetic dataset.
- **[ASSUMPTION]**: a prototype business rule we chose because the case material does not define one. It is labelled as an assumption wherever a customer sees it.
- **[SIMULATED]**: a mock of a real integration (registry, DigiLocker, e-sign, feasibility, provisioning, WhatsApp/SMS). It is labelled "simulated" in every screen where it appears.

None of this is legal advice or a compliance claim. The prototype uses synthetic data and mock services, and is **designed around the case's DPDP principles** (consent, purpose limitation, data minimisation). The DPDP Rules 2025 were notified on 13 Nov 2025 with phased commencement; most data-fiduciary obligations apply from 14 May 2027. A real launch needs qualified legal review.

---

## 1. Clock

- All date-based rules read `business_as_of` from an injected clock, never `date.today()` scattered through the code.
- **Demo mode:** a fixture clock fixed to **2026-07-15**, because the data pack defines "today" as that date for its checks [DATA]. The UI shows a "Demo date: 15 Jul 2026" badge.
- **Live mode** (any real integration): the real current timestamp; freshness is evaluated at the order's KYC submission time and re-checked if KYC is resubmitted.
- The back-office demo clock only moves the **simulated** order timeline. It never changes `business_as_of` for KYC rules.

## 2. Consent and purposes

Each purpose is a separate, unticked choice with its own notice text and version. Nothing optional is a condition of getting a quote. In the UI this is called **"Your choices"** and internally the **consent ledger**. It is never called a "Consent Manager", which is a registered role under the DPDP Rules that this prototype does not have.

| # | Purpose | Asked when | Needed for | If declined |
|---|---|---|---|---|
| P1 | **Get a recommendation and quote** (business type, city, size, needs; no identifiers). Covers processing **during the session only** | Advisor start, one-line notice | Advisor + quote | No journey; we explain why |
| P2 | **One-time GSTIN/Udyam eligibility lookup** | Only when the owner chooses to enter a GSTIN | Prefill and unlocking GSTIN-only products | Quote still works; GSTIN-only products shown as "needs an active GSTIN, checked at KYC" |
| P3 | **KYC document checks** | Before the upload screen | Placing an order | Can keep the quote for the session, cannot order online; offered assisted KYC with a partner (needs P5) |
| P4 | **Save my application so I can resume** | When the owner leaves mid-journey, or taps "Save" | Resume link (30 days) | Nothing kept after the session ends (see the P1 + P4-declined rule below) |
| P5 | **Share my application with a named team**: one toggle per team, each naming it ("Accel Business sales", "Sharma Telecom, who referred you") | On handoff or "call me" | Human follow-up by that team only | No human follow-up; self-serve only. A referring partner gets referral credit but sees nothing (§11) |
| P6 | **Marketing messages** (optional) | After order placement only | Offers | Nothing changes |
| — | **Order notice** (not a toggle) | On "Accept quote" | Keeping the accepted quote, profile and order for the contract | The owner doesn't accept; nothing is ordered |

**P1 with P4 declined: exact behaviour**
1. During the session, slots, chat history (needed for the next LLM turn) and draft quotes live in a server-side `sessions` row keyed by a random session ID in the owner's cookie.
2. The session ends when the owner taps **"End and delete"** (always visible in the menu), or after **24 hours without activity**, whichever is first.
3. At that point the retention job deletes the session row, its chat and draft quotes. Nothing from the session remains except the unlinked consent events (rule 5).
4. If the owner **accepts a quote** before that, the order notice applies: the accepted quote version and the structured profile move to the `orders` record and are kept for the contract life (or 30 days if no KYC is started). The chat itself is still deleted at session end.

Rules:
1. A GSTIN typed into the chat **before P2** is detected server-side, never sent to the LLM and **not looked up or stored**. The chat shows a consent card ("Want us to check this GSTIN to fill in your details?"). If the owner declines, the value is discarded.
2. The advisor asks "Do you have a GSTIN? (yes/no)". The number itself is collected only in the P2 form, never in free chat.
3. **Withdrawal** from the "My data" page (or by the back office on request) stops processing for that purpose at once:
   - **P1**: same as "End and delete": session, chat and drafts deleted now. If an order exists, P1 withdrawal cannot remove order data on its own; the page offers cancellation instead (§10), which then triggers deletion of order data except what is needed to close the order.
   - **P2/P3**: lookup results and extracted KYC fields are deleted; an open order goes to `ON_HOLD`.
   - **P4**: the saved application is deleted at once, unless it has become an order.
   - **P5**: the lead leaves that team's queue immediately; their notes on it are deleted.
4. Consent events are append-only and hold only: random event ID, purpose, notice version, language shown, decision, timestamp, channel, and a link (session ID or order ID).
5. **When a session is deleted, its consent events are unlinked**: the session ID is replaced by a random tombstone value, so they can show that a choice was made and when, but can no longer be connected to any person or business. Events linked to an order stay linked for the order's life, then are unlinked the same way. Unlinked events are kept 1 year [ASSUMPTION].

## 3. Data inventory and retention

| Data | Stored? | Where | Who can see | Retention [ASSUMPTION] | Deleted when |
|---|---|---|---|---|---|
| Structured slots, chat history, draft quotes | With P1, in the session | `sessions`, `advisor_messages` | Owner | **24 h after last activity**; 30 days with P4 | "End and delete", P1/P4 withdrawal, retention job |
| Accepted quote version + structured profile | On quote acceptance (order notice) | `orders`, `quote_versions` | Owner; staff with P5 | Contract life; 30 days if KYC never starts | Order cancelled + closed, retention job |
| Raw chat after the session | **Never** | — | — | 0 | Deleted with the session (also with P4 after 30 days) |
| Conversation summary for staff | Only with P5 for that team | `handoffs` | That team only | 30 days after handoff closes | P5 withdrawn |
| Referral attribution | When a session starts from a referral link/code | `attributions` (partner ID, session/order ID, time) | Admin; partner sees counts only | Same as the session or order it belongs to | With the session or order |
| GSTIN/Udyam lookup result | With P2 | `registry_checks` | Owner; KYC reviewer | Same as KYC fields | P2 withdrawn, retention job |
| Document images | **Never stored** | Processed from request bytes in memory | Nobody after processing | 0 | Dropped after extraction |
| Extracted KYC fields | With P3 | `kyc_fields` (identifiers encrypted at rest, §13) | Owner (masked); KYC reviewer (full, logged) | Failed or abandoned KYC: 30 days. Order: contract life (production: as the telecom regulator requires, confirmed by legal) | P3 withdrawn, retention job |
| Check results and repair trail | With P3 | `kyc_checks` | KYC reviewer | Same as fields | Same as fields |
| Consent events | Always | `consent_events` | Admin | Linked: session/order life; then unlinked, 1 year | Retention job |
| LLM dev cache | Developer machines only, off by default | `.cache/llm/` (git-ignored), **gated payloads only** (§5.2) | Developer | Until `make clean-cache`; never enabled on the hosted demo | Manual |
| Audit log | Yes | `audit_events` (masked values only) | Admin | 1 year [ASSUMPTION] | Retention job |

- **Masking:** GSTIN shown as `37IH••••••••1ZS` style (first 4, last 3), Udyam as `UDYAM-KL-00-•••8801`, IDs as last 4. Every API response, log line and back-office list uses masked values. Full values appear only on the KYC reviewer's case screen, and each view writes an audit event.
- **Logging:** no request or response bodies in logs; a logging filter masks identifier patterns as a backstop; exception handlers drop request payloads; no third-party analytics or session-replay scripts.
- **Retention job:** runs daily (and on a back-office button in demo mode, so the deletion can be shown on video).
- **Backups:** the prototype keeps none. In production, deletion has to reach backups within the backup rotation window; that is listed as a launch requirement, not claimed.
- **Demo instance:** the hosted demo is seeded from the synthetic CSVs at boot and **resets on every restart** ([ARCHITECTURE.md §7](ARCHITECTURE.md#7-deployment)). A banner says: "Demo with synthetic data. Do not enter real personal information."

## 4. Advisor inputs

| Slot | Required | Source | Validation |
|---|---|---|---|
| Business type → segment | Yes | Chat (LLM extraction or scripted buttons) | Mapped through a fixed table of business types from the leads data; unknown types → ask segment directly with 4 buttons |
| City → tier, state | Yes | Chat or pick list | Must resolve to a city in the leads data; else ask state + "big city or smaller city?" for tier; still unknown → tier treated as 2 (the stricter set) and the quote says so |
| Employee count | Yes | Chat | Integer 1–500 |
| Number of sites | Yes | Chat | Integer 1–50 |
| Has a GSTIN (yes/no) | Yes | Chat | Boolean; the number only via P2 |
| Needs (payments/POS, WhatsApp, CCTV, email, security, failover, IoT, fleet, website) | No | Chat | Fixed enum list |
| Current internet / provider / monthly spend | No | Chat | Enum / enum / integer ₹0–5,00,000 |
| Monthly budget | No | Chat | Integer |

- **Conflicts:** the latest answer wins, and before recommending the advisor shows a **summary card** ("Dental clinic · Pune · 12 people · 1 site · has GSTIN") that the owner can edit. The recommendation uses the card, not the chat history.
- **Question cap:** after 8 owner turns without the required slots, the advisor offers (a) a quote based on what it knows, with the gaps filled by segment defaults and shown as assumptions, or (b) a callback (needs P5).
- **Out-of-catalogue requests** (for example "do you sell laptops?"): the advisor says Accel doesn't offer it and moves on. It never invents a product.
- **Prompt injection:** the LLM can only propose slot values in a fixed JSON schema. Every value is validated against the table above. The LLM cannot trigger lookups, consent, pricing or state changes. Those are server actions behind buttons. Policy text lives in the system prompt and is never built from user text.

## 5. LLM boundary (Gemini free tier)

Google's terms for unpaid services say content may be used to improve products, may be read by human reviewers, and that sensitive, confidential or personal information must not be submitted. A banner is a warning, not a boundary, so the boundary is specified as a code-level control (planned; see §15 for its test and stop condition): **raw owner text must never leave the server on the free tier.**

### 5.1 Two LLM profiles

| Profile | When | What may be sent |
|---|---|---|
| `free_demo` (the only profile in this prototype) | Gemini free tier, synthetic demo | Only the output of the privacy gate (§5.2), never raw text |
| `approved` (production, not built) | Only after the launch gate below is signed off | Decided at launch review |

**Launch gate for `approved`** (a **production requirement**, not a current property: the `approved` profile, the launch record and the start-up check are not built). A paid service under a data-processing agreement is necessary but **not sufficient**. The planned start-up check would refuse `approved` mode unless a launch record confirms all of: processing and storage region; prompt/response retention and abuse-monitoring logging period; whether human review can occur; sub-processors; the data categories allowed in prompts; age and regional terms; incident notification; and legal sign-off. None of this is claimed for the prototype.

### 5.2 The privacy gate (runs before every outbound LLM request)

1. **Local first.** Every message goes through the local slot parser (EN/HI/Hinglish keywords, a business-type and needs lexicon, a city gazetteer from the leads data, number parsing). If it fills what the turn needs, **no LLM call is made.**
2. **Strip identifiers.** GSTIN, Udyam, PAN, phone, email, pincode and long digit-run patterns are removed outright (not masked), and so are runs of more than 4 number words ("nine eight seven…").
3. **Token allowlist.** The outbound text is rebuilt from tokens that are in a fixed vocabulary: the lexicon above, city names, numbers up to 4 digits, and about 400 EN/HI/Hinglish function words in Latin and Devanagari script. **Every other token becomes `[?]`.** Names, street names and other volunteered details are not in the vocabulary, so they never leave. We accept that this hurts understanding of unusual phrasing.
4. **Too much masked → no call.** If more than half the tokens became `[?]`, the turn goes to scripted mode ("I didn't catch that", plus buttons) instead of calling the LLM.
5. **Payload.** Gated text + the slots so far as enums and size bands + the list of missing slots. Never raw text, names, addresses, identifiers or the city's address-level detail.
6. **Explanation call.** Receives only reason codes, product IDs and coarse slots (segment, tier, size band, needs). No text from the owner at all.
7. **Planned test and stop condition:** a red-team fixture set (categories in §15) is run through the gate, and the test asserts on the **actual outbound payload** that the Gemini client would send. It will run in CI, and also at server start-up: if any fixture leaks a disallowed token, the Gemini provider stays disabled and the advisor runs in scripted mode only.
8. **Dev cache** stores the gated payload and response only, on developer machines, off by default, never on the hosted demo.

Consequences, stated openly:
- **Judges can type freely** in the demo. Once implemented and passing its test, the gate is what keeps personal data from reaching Gemini; the banner is an extra warning.
- **The gate trades understanding for privacy, on purpose.** Unusual phrasing and non-EN/HI messages lose most of their words, so they fall back to buttons. **Conversation in other Indian languages is not part of the free-tier demo** (it needs the `approved` profile). The UI stays EN/HI. We will **show this fallback in the demo** and measure how often it happens (share of turns where the gate masked more than half the message, and share of sessions that ended in scripted mode). We do not claim the gate gives both full privacy and full understanding.
- **Known residual risk:** a personal name that is also an allowlisted word (a city, a business word, a common Hindi word) passes the gate. The red-team report lists every such case it finds, rather than hiding them.

### 5.3 Voice typing: cut from the prototype

Browser speech recognition (Web Speech API) sends audio to a speech service chosen by the browser. In Chrome that is normally Google's service, and we have **not verified** its retention, human review, account or region settings, or whether a given browser uses a different service. So, as the review recommends, **voice is out of the prototype and the demo**: no mic button, no PV consent, typing and buttons only. It stays on the roadmap, conditional on choosing and verifying a specific speech provider (notice, terms, retention, user choice) for the exact browsers in scope.

### 5.4 Rendering and guard

- **Rendering:** product names, quantities and prices on the recommendation card and quote are always rendered by the server from product IDs. The LLM only writes **one short sentence per reason code**, returned as JSON keyed by the codes we sent.
- **Guard on explanations:** reject and fall back to the templated EN/HI sentence if the JSON keys differ from the codes sent; a sentence is over 160 characters; it contains digits, "₹", "rupee/rupaye/रुपये", "%", or SLA/uptime/speed claims; or it names a catalogue product (from an alias list including Hindi transliterations) other than the one it is attached to. Negation needs no special case, because the card, not the sentence, lists what is in the bundle.

## 6. Recommendation rules

0. **Catalogue targeting (`target_segments`) is a soft rule.** The dataset README lists the eligibility rules (city tier, minimum staff and sites, active GSTIN, `requires_one_of`), and `target_segments` isn't among them, so the engine **never rejects** a product for being off-target. It does govern **defaults**: anything the engine adds on its own (segment starter set, dependency fill, substitutions) must be **on-target** for the owner's segment. An off-target product appears only if the owner chooses it (a toggle or an explicit request). It then gets the info code `INFO_OFF_TARGET` and the catalogue note "Listed by Accel for <segments> businesses". Historical purchase shares can **rank on-target candidates** but never override targeting.
1. Segment starter set [DATA: most-bought **on-target** products per segment among activated customers]. If two on-target candidates are close, the catalogue order and the owner's stated needs decide, and the other is offered as a choice on the quote.
2. Add products for stated needs.
3. **Eligibility filter:** city tier, `min_employees`, `min_sites`, and `requires_gstin = Y` needs an **Active** registry status (a passed check digit is not enough). Before P2 the status is "unknown": GSTIN-only products are shown as locked with the reason.
4. **Dependencies (`requires_one_of`):** satisfied first by a connectivity product already in the bundle. Otherwise pick by **need and site constraints, then price**: the speed tier the owner asked for or the segment default, available in that city tier, feasible at the address (simulated). If no candidate fits, the dependent product is left out with the reason and the owner is offered assisted review. It is never silently added.
5. **Substitution is a suggestion, not an action:** tier 2 + 1 Gbps request → "300 Mbps is the fastest fibre here"; no fibre feasibility → "5G AirFiber is **100 Mbps** wireless; want that instead?". Each needs the owner's tap, and the quote is recalculated.
6. Budget: if over the stated budget, optional add-ons are dropped in reverse priority, and the card lists what was dropped.
7. Each decision emits a reason code; exclusions emit an exclusion code (`EXCL_TIER`, `EXCL_GSTIN_UNKNOWN` (has one, not checked yet), `EXCL_GSTIN_MISSING` (has none), `EXCL_GSTIN_INACTIVE`, `EXCL_MIN_EMP`, `EXCL_MIN_SITES`, `EXCL_DEP_UNRESOLVED`); off-target choices emit the non-blocking `INFO_OFF_TARGET`.
8. **Fibre speed for multi-site and manufacturing bundles:** the prototype doesn't ask for site-level bandwidth. It defaults to the on-target fibre (P02 Biz Fibre 300 for multi-site) and shows the speed as a **choice on the quote**: P01 (100 Mbps, cheaper, flagged `INFO_OFF_TARGET` for multi-site) and P03 (1 Gbps, where tier and eligibility allow). Each option is described only with its catalogue description (speed, data, static IP option). No uptime or SLA wording, since only P05/P06 state an SLA.

## 7. Rate card and quote

The catalogue gives a monthly price band, setup fee, unit and minimum term, but no discount schedule. We checked how the 368 historical deals were priced:

- Every deal's monthly value falls inside the sum of the bands; on average it sits **48% of the way** from minimum to maximum, with no difference by city tier (48% vs 48%) or contract length [DATA].
- One-time setup = setup fee × quantity in 100% of deals [DATA].
- Contract months = the longest minimum term among the items in 100% of deals [DATA].

Our rate card:

| Rule | Value | Label |
|---|---|---|
| Unit monthly price | Band midpoint, rounded half up to ₹1 | [ASSUMPTION], consistent with the 48% observed average |
| Discounts | None. No term-based or bundle discount, and no "save ₹X" claim | (no discount schedule in the data) |
| Setup | Catalogue setup fee × quantity, charged once | [DATA] |
| Term | **Per line item**: each item shows its own minimum term (for example fibre 12 months, mobile lines month-to-month). Historical deals used one bundle-wide term; we show item terms because it is clearer and doesn't tie a monthly product to a long contract | [ASSUMPTION], flagged as a business decision |
| Tax | **Illustrative uniform tax of 18%** on every recurring and one-time line, shown as a separate line labelled "Tax (illustrative 18%)". This is a mock rule, **not** a tax classification: the catalogue mixes telecom services, software, hardware-backed services and setup charges, which may be treated differently. A real quote needs a tax category and rate per SKU and per charge type from finance | [ASSUMPTION], mock tax |
| Rounding | Line amounts in whole rupees; GST rounded half up per total | [ASSUMPTION] |
| First payment | Month 1 recurring + all one-time charges, incl. GST | [ASSUMPTION] |
| Savings line | "You told us you spend about ₹X/month today on telecom" shown next to the new monthly total, **without** calling the difference a saving, because the stated spend may cover other vendors and products | — |

Quantity defaults (editable within caps, with the cap shown) [DATA: medians among activated deals]:

| Unit | Default | Cap |
|---|---|---|
| per site (fibre, failover, SD-WAN, Wi-Fi, firewall) | number of sites (≥ 90% of deals) | number of sites |
| per user (cloud email) | 60% of employees, rounded to nearest (min 1) | employees |
| per device (endpoint security) | 40% of employees, rounded to nearest (min 1) | 2 × employees |
| per line (postpaid) | micro 1; professional 2; multi-site and manufacturers 1 per site (min 2) | employees |
| per camera | 2 per site | 8 per site |
| per counter (POS) | 1 per site | 4 per site |
| per account / pack / number / IP | 1 | 1 (IP: sites) |
| per channel (SIP) | 2 | employees |
| per device (IoT), per vehicle | asked | 50 |

**Quote snapshot:** the quote that the owner accepts is frozen as an immutable `quote_version` (catalogue version, rate-card version, line items, prices, taxes, terms, assumptions shown). Any later change (substitution, quantity edit, catalogue update) creates a new version that needs a new acceptance. Fully worked examples are in [WORKED_QUOTES.md](WORKED_QUOTES.md).

## 8. Registry lookups [SIMULATED]

Every registry screen shows "Mock registry (synthetic data pack, as of 15 Jul 2026)".

| Response | Meaning | Effect |
|---|---|---|
| `format_invalid` | Wrong length/pattern or the check digit fails | Ask the owner to re-enter; no lookup made |
| `not_found` | Valid format, no record | Owner can re-check; otherwise manual review |
| `active` | Record with status Active | GSTIN-only products unlocked |
| `cancelled` / `suspended` | Record with that status | GSTIN-only **lines** are excluded (`EXCLUDED`, reason `GSTIN_INACTIVE`, §10); the GST certificate is not accepted as business proof; the applicant's other checks continue for the remaining lines (§9) |
| `unavailable` | Simulated outage (a back-office toggle for the demo) | "We'll check shortly": quote can proceed, KYC waits; no product unlocked |

A valid check digit only proves the number is well formed; status comes from the registry response.

## 9. KYC outcomes

KYC produces **two separate results**: an **applicant result** (about the documents and the business) and a **line eligibility result** for each item in the accepted quote.

**Documents required** [ASSUMPTION; 45% of leads have no Udyam and 29% no GSTIN, so we cannot require both]:
- Always: authorised signatory ID and address proof.
- Business registration: at least one of a GST certificate (with an Active GSTIN) or a Udyam certificate (found in the Udyam registry).
- If the bundle contains GSTIN-only items: a GST certificate with an Active GSTIN is required for **those lines**.
- If the registry shows a Udyam registration for this business (linked by GSTIN) but no Udyam certificate was uploaded: `owner_action_needed` (upload it, or accept the registry record via DigiLocker, simulated).

**Applicant result**, what each means and does not mean:

| Outcome | Means | Does **not** mean |
|---|---|---|
| `checks_passed` | All automated consistency checks passed for the documents provided: formats, registry status of the business proof used, cross-document agreement, freshness, completeness, image quality | That the documents are genuine, unaltered, or submitted by an authorised person. We do not detect tampering and do not claim to |
| `owner_action_needed` | Something the owner can fix in the app: retake a blurry photo, upload a newer bill, add a missing document, confirm an OCR reading, provide a valid business registration | — |
| `manual_review` | A specialist must decide: name or address mismatch below the similarity threshold, any repaired identifier the owner disputes, `not_found` registry result, a document whose **printed** identifier fails its own format or check digit (for example K06), and a proprietorship signatory who doesn't match the proprietor on the GST record | — |

**Line eligibility result**, per item: `eligible`, or `excluded` with a reason (`GSTIN_INACTIVE`, `GSTIN_MISSING`, plus the catalogue exclusions from §6). A Cancelled or Suspended GSTIN is **not** an applicant-level stop: it excludes the GSTIN-only lines, and the GST certificate cannot be the business proof. If the owner also has a valid Udyam certificate, the applicant result can still be `checks_passed` for the remaining lines. The screen says what the owner can do (remove those items, or sort out the GST registration and come back). The old applicant-level `blocked` outcome is removed.

The word **"verified"** is not used anywhere for an automated result.

OCR identifier policy:
- OCR output is never silently corrected. If the raw GSTIN fails the check digit, we try the known confusions (O↔0, I↔1, S↔5, B↔8, Z↔2) and, if exactly one candidate passes, **show it to the owner to confirm** ("We read 37IHKXV5167L1ZS. Is that right?"). The raw value, the candidate, and the owner's confirmation are all stored in the repair trail.
- A repaired identifier can reach at most `checks_passed` only after owner confirmation **and** a registry record whose legal name matches; otherwise `manual_review`.
- **Linking** documents to a business uses identifiers (GSTIN, Udyam number). **Names** are only a consistency check between documents and the registry, never the way records are matched, and a name mismatch can only lower the outcome, never raise it.

Matching thresholds [ASSUMPTION, tuned on the 12 specimen sets and reported]:
- Names: normalise (case, spacing, punctuation, "Prop." wrappers and Pvt Ltd/LLP suffixes, even when OCR has glued them on), then character similarity. **≥ 0.95 pass; < 0.95 `manual_review`.** Revised after the OCR spike: the earlier "0.80–0.95 pass with a note" band would have passed K07, whose legal name was altered ("Shri Physio Clinic" vs the registry's "Neelgiri Physio Clinic", similarity 0.87). That is a false accept. Every clean specimen scores ≥ 0.95.
- Signatory: for a **proprietorship**, the ID name must match the proprietor in the GST legal name. For partnerships, LLPs and companies the mock registry holds no partner or director names, so the signatory **can't be checked**. That is recorded as a reviewer note, not `manual_review`, and the UI never implies it was checked.
- Address: compare pincode, city and state from the bill against the GST principal place of business. Pincode + state equal → pass; state equal but pincode different → `manual_review` (could be a second site); state different → `manual_review`. The **installation address** is captured separately and may differ from the address proof.
- GSTIN state code must equal the state on the GST record.
- Freshness: address proof dated within **90 days** before `business_as_of` [ASSUMPTION from the data pack, configurable in `policy.yaml`]; signatory ID `valid till` ≥ `business_as_of`. Accepted address-proof types for the prototype: electricity bill only (the only specimen type supplied).

Reviewer authority: only the `kyc_reviewer` role can change an outcome, must pick a reason, and every decision is audited. The owner can **appeal** from the tracker (upload again or ask for review), which reopens the case.

Evaluation: we hand-build an answer key for all 47 images (12 applicants), record every field we expect, and report per-field and per-applicant results. **False accepts** (a planted problem that ends in `checks_passed`) are the headline number; the target is zero on the specimen set.

## 10. Orders and tracker [SIMULATED]

Order state (whole order) and line-item state are separate.

**Order states:** `DRAFT → ACCEPTED (quote vN frozen) → KYC_PENDING → KYC_OK → IN_FULFILMENT → COMPLETED`, plus `ON_HOLD` with a reason (`KYC_ACTION`, `KYC_REVIEW`, `BUNDLE_CHANGE_NEEDED`, `CONSENT_WITHDRAWN`, `FEASIBILITY_DECISION`), and `CANCELLED`.

**Line-item states:** `PENDING → FEASIBILITY_CHECK → SCHEDULED → INSTALLING → ACTIVE`, plus `EXCLUDED` (with a reason, from the line eligibility result), `FEASIBILITY_FAILED`, `INSTALL_FAILED → SCHEDULED` (retry), `RESCHEDULED`, `CANCELLED`.

| Transition | Trigger | Actor |
|---|---|---|
| `DRAFT → ACCEPTED` | Owner accepts quote vN (mock e-sign) | Owner |
| `ACCEPTED → KYC_PENDING` | KYC submitted | Owner |
| `KYC_PENDING → KYC_OK` | Applicant `checks_passed` (or reviewer approves) **and every line `eligible`** | System / KYC reviewer |
| `KYC_PENDING → ON_HOLD (KYC_ACTION / KYC_REVIEW)` | Applicant `owner_action_needed` / `manual_review` | System |
| Line `PENDING → EXCLUDED` | Line eligibility `excluded` | System |
| `KYC_PENDING → ON_HOLD (BUNDLE_CHANGE_NEEDED)` | Applicant `checks_passed` but one or more lines `EXCLUDED` | System |
| `ON_HOLD (BUNDLE_CHANGE_NEEDED) → KYC_OK` | Owner accepts quote vN+1 without the excluded lines; **the existing KYC result is reused** (same applicant, same documents) | Owner |
| `ON_HOLD (BUNDLE_CHANGE_NEEDED) → CANCELLED` | Owner cancels, or 30 days pass without a decision [ASSUMPTION] | Owner / system |
| `KYC_OK → IN_FULFILMENT` | First line item starts | System |
| Line `PENDING → FEASIBILITY_CHECK → SCHEDULED` | Simulated feasibility pass, slot booked | System / ops (simulated) |
| Line `FEASIBILITY_FAILED` | Simulated feasibility fail | System |
| Line `SCHEDULED → RESCHEDULED → SCHEDULED` | Owner or ops moves the slot | Owner / ops |
| Line `INSTALLING → ACTIVE` / `INSTALL_FAILED` | Engineer outcome (simulated) | Ops (simulated) |
| `IN_FULFILMENT → COMPLETED` | All non-cancelled lines `ACTIVE` | System |
| any → `CANCELLED` | Owner cancels before activation (refund policy: [ASSUMPTION] full refund of unbilled one-time charges) | Owner / ops |

- **Why eligible lines don't start automatically when one is excluded:** removing a line changes the price and the terms the owner agreed to, so it needs a new acceptance. Re-acceptance is one tap; documents are not uploaded again and checks are not re-run.
- **Mobile lines** need no site install and can go `ACTIVE` once the order is `KYC_OK`, independent of fibre.

**Worked mixed-order example** (catalogue prices, demo rate card, illustrative 18% tax):

| Step | State |
|---|---|
| Professional office accepts **quote v1**: P02 Biz Fibre 300 × 1 (₹1,649), P16 Cloud Email × 7 (₹966), P15 WhatsApp Business API × 1 (₹1,249, GSTIN-only). Monthly ₹3,864 ex-tax, ₹4,560 incl. tax | Order `ACCEPTED` |
| KYC submitted: GSTIN is **Cancelled** in the registry; Udyam certificate found in the Udyam registry; ID and electricity bill pass | Order `KYC_PENDING` |
| Applicant result `checks_passed` (business proof = Udyam). Line results: P02 `eligible`, P16 `eligible`, P15 `excluded (GSTIN_INACTIVE)` | Lines P02, P16 `PENDING`; P15 `EXCLUDED`; order `ON_HOLD (BUNDLE_CHANGE_NEEDED)` |
| Owner sees: "WhatsApp Business API needs an active GSTIN. Your GSTIN shows as cancelled in the (mock) registry. Remove it and continue?" → taps **Continue without it**. **Quote v2**: P02 + P16, monthly ₹2,615 ex-tax, ₹3,086 incl. tax | v2 accepted; KYC result reused; order `KYC_OK` |
| P15 line stays `EXCLUDED` (shown greyed with the reason); P02 and P16 proceed | P16 `ACTIVE` in about 1 day, P02 `SCHEDULED` (about 5 days, indicative); order `IN_FULFILMENT` |

The applicant in this example is a test fixture built from one of the **144 leads** whose GSTIN is Cancelled or Suspended but who have a Udyam registration. None of the 12 KYC specimens fits it.

If the applicant has **no** valid Udyam registration either, there is no valid business proof: the applicant result is `owner_action_needed` ("we need a valid GST or Udyam registration") and the order waits in `ON_HOLD (KYC_ACTION)`. **K01 is this case:** its GSTIN is Cancelled and its Udyam certificate has no registration number, with no matching record in the Udyam registry.
- **Feasibility failure** puts the order `ON_HOLD` and offers the substitute as a **new quote version**; nothing changes until the owner accepts it. If they decline, that line is `CANCELLED` and the rest continues.
- **ETAs** are "indicative, from the catalogue's typical install days", shown as "about N days". They are not a commitment and do not come from an address-level feasibility result.
- **Notifications** appear in an in-app inbox styled like WhatsApp/SMS and labelled **"Simulated message, not sent"**.
- All commands (accept, submit KYC, transitions, cancel) take an idempotency key; a transition not listed above is rejected.

**As built (06 Nov):** the code (`backend/app/orders/states.py`) adds three transitions the table above implies but didn't list: line `PENDING → SCHEDULED` (a site visit with no feasibility check, for example POS or CCTV), order `IN_FULFILMENT → ON_HOLD (FEASIBILITY_DECISION)`, and `ON_HOLD → IN_FULFILMENT` once the owner decides. Products with no site install (mobile lines, cloud services) go `PENDING → ACTIVE` when KYC passes. If the owner declines a substitute, lines that needed the cancelled connection (`requires_one_of`) are cancelled with the reason `DEP_LOST`. In demo mode only, `/api/demo/*` moves an order's simulated timeline, forces a feasibility failure, and serves the synthetic KYC specimens, so the demo can be run without files.

## 11. Back office: roles and scope

| Role | Sees | Can do |
|---|---|---|
| `sales_agent` | Leads with P5 consent assigned to Accel field sales; historical synthetic leads | Claim, call notes, resume a journey, hand back |
| `partner` (one account per partner) | **Only** leads where the owner gave P5 naming **that** partner. A referral code alone grants no access | Claim, assisted KYC upload, call notes |
| `kyc_reviewer` | KYC cases in `manual_review` | View full identifiers (audited), decide with a reason |
| `admin` | Everything masked; audit log | Toggles (registry outage, demo clock), retention job, assignment rules |

**Attribution and disclosure are separate permissions:**
- **Attribution (credit):** a referral link or QR code records `partner_id` + time on the session (`attributions`). That credits the partner for 30 days if an order is placed, even if field sales closes it; conflicts go to admin. It grants **no access** to the application.
- **Disclosure (access):** only P5 naming that partner. The owner sees the partner's name in the P5 notice ("Share my application with Sharma Telecom, who referred you?") at handoff or when asking for a call, never before.
- **If the owner declines P5:** the partner sees **no identifiable application data**. The partner dashboard shows only aggregate counts for its referrals (sessions started, orders placed, activations), and only once a count reaches 5, so a single customer can't be singled out.
- Partner payout and incentive design are out of scope for the prototype.

- **Lead ownership:** a claim lasts 48 h [ASSUMPTION]; unclaimed or expired leads return to the queue.
- **Two lead lists, kept apart:** "Historical leads (synthetic data pack)", scored offline in batch, and "Live journey leads", created by the prototype and scored by the same model at handoff time. They never mix in one table.

## 12. Labelling at a glance

| Shown to owner/judge | Label |
|---|---|
| Registry, DigiLocker, e-sign, feasibility, install progress, messages | "Simulated" |
| Prices, terms, quantities | "Demo rate card (assumptions listed)" |
| Data findings in the deck | "Observed in synthetic data, association not causation" |
| Targets | "Pilot hypothesis" |
| KYC result | "Automated checks", never "verified" |
| Tax line | "Tax (illustrative 18%)" |
| Consent screens | "Your choices", never "Consent Manager" |

## 13. Security specifics (prototype)

**State-changing routes** (all `POST`; nothing changes state on `GET`):
- Owner: `/consents`, `/consents/{id}/withdraw`, `/session/end`, `/advisor/messages`, `/registry/gstin-check`, `/quotes/{id}/versions`, `/quotes/{id}/accept`, `/kyc/{case}/documents`, `/kyc/{case}/confirm-identifier`, `/kyc/{case}/submit`, `/kyc/{case}/appeal`, `/orders/{id}/reschedule`, `/orders/{id}/cancel`.
- Back office: `/bo/login`, `/bo/logout`, `/bo/leads/{id}/claim`, `/bo/leads/{id}/notes`, `/bo/kyc/{id}/decision`, `/bo/admin/*`.

**Cross-site request protection:** the PWA is served from the same origin as the API, and CORS is off. Every state-changing request must carry an `X-CSRF-Token` header matching a per-session token (double-submit), **and** its `Origin` header must equal the app's origin; otherwise `403`. Cookies are `SameSite=Lax` for owners and `SameSite=Strict` for the back office.

**Sessions and cookies:**
- Sessions are server-side rows (so they can be revoked), referenced by a random ID in an `HttpOnly` cookie, `Secure` on the hosted HTTPS demo (Render terminates TLS); locally over `http://localhost` the `Secure` flag is off, and that is the only difference.
- Owner session: 24 h idle expiry (30 days for a P4 resume link, which is a single-use token that starts a new session).
- Back office: 30 min idle, 8 h absolute; logout deletes the session row; changing a password revokes all that account's sessions.

**Staff accounts:**
- Seeded accounts per role (`sales_agent`, two partners, `kyc_reviewer`, `admin`), passwords from environment variables at boot, stored as **Argon2id** hashes (`argon2-cffi`); never logged.
- 5 failed logins → 15-minute lockout for that account; login rate limit per IP.
- No MFA in the prototype (stated as a gap); production would add it for reviewer and admin roles first.
- Least privilege will be enforced in the API, not the UI, and **tested with direct API calls** (planned, §15) for each role: partner A cannot read partner B's lead, a partner cannot open a KYC case, a sales agent cannot decide a KYC case, and an owner session cannot call `/bo/*`.

**KYC field encryption:**
- Full identifiers in `kyc_fields` are encrypted with Fernet (`cryptography`), using a key from the `KYC_FIELD_KEYS` environment variable (Render secret on the hosted demo, `.env` locally, never committed or logged).
- **Rotation:** `KYC_FIELD_KEYS` is an ordered list (MultiFernet): the first key encrypts, all keys decrypt; a rotate command re-encrypts all rows with the new key, then the old key is removed.
- **Restart:** the key comes from the environment, so restarts should be fine (and the hosted demo re-seeds anyway). Planned test: encrypt, restart the process, decrypt; rotate, then decrypt with the new key only.
- **Lost key:** encrypted fields can't be recovered. Affected cases return to `owner_action_needed` ("please upload again"). Production would keep the key in a managed key store with backup; that is a launch requirement, not a prototype feature.

**Rate limits and sizes:** per-IP limits on public routes; uploads JPEG/PNG ≤ 8 MB, 4 per case; request timeout 30 s.

## 14. Claims register (what the owner is told, and where it comes from)

Every user-visible statement about a product or the owner's situation must come from one of these sources.
- **"You told us" wording is allowed only when the slot is present on the owner's confirmed summary card.** Without a confirmed slot, a reason must be worded as a segment default ("most businesses like yours choose this", with its data share) or replaced by a question.
- Reasons never infer sensitive details or internal roles the owner didn't state (for example "patient data on your PCs" or "doctor + front desk").
- **Audit scope (planned):** the EN/HI reason-code templates, the LLM's per-reason sentences (via the guard, §5.4), the reason texts in [WORKED_QUOTES.md](WORKED_QUOTES.md) (which are fixtures for the template tests), and the demo script in DELIVERABLES.md. The planned test checks that every factual word maps to a source below, and that every "you told us" maps to a confirmed slot in the fixture's summary card.

| Kind of claim | Allowed source | Example | Not allowed |
|---|---|---|---|
| What a product is | Catalogue `product_name`, `description`, `unit`, `category` | "Business fibre broadband, 300 Mbps, unlimited data" | Uptime, reliability or SLA language unless the description states it (only P05/P06 state an SLA: 99.5% / 99.9%) |
| Why it is in the bundle | Reason code + the owner's own stated slots (segment, need, size) | "You said you take card and UPI payments" | Inferred needs the owner didn't state, except the segment default, which is labelled "most businesses like yours choose this" [DATA: share of activated customers in the segment] |
| Popularity | [DATA] share of activated customers in the segment who bought it, **with its denominator kept in the fixture**; used only to rank on-target candidates | "Chosen by most professional offices we've served" | Market-wide claims; calling a small difference a preference (for example 52% vs 48% of 83 customers) |
| Targeting | Catalogue `target_segments` | "Listed by Accel for multi-site businesses" / "Listed for micro and professional businesses" (off-target choice) | Implying an off-target product is wrong or unavailable |
| Eligibility | Catalogue rules + registry status | "Needs an active GSTIN" | Legal advice |
| Price, quantity, terms, tax | Rate card (§7), server-rendered only | Card and quote lines | Any number in an LLM sentence |
| Install time | Catalogue `typical_install_days`, shown as "about N days (indicative)" | "About 5 days" | Dates or promises |
| Savings | None | "You told us you spend about ₹X today" | "You save ₹X" |

Wording fixes from this rule: the P02 reason in WORKED_QUOTES §A no longer says "uptime" (P02's catalogue entry has no availability commitment), and since round 4 every reason there is tagged [YOU TOLD US], [SEGMENT DEFAULT] or [QTY DEFAULT], with no inferred details such as patient data or staff roles.

## 15. Controls register

**Every row is planned.** Nothing is implemented or tested yet. "Evidence" is what has to exist before a control may be described as working, in the deck or anywhere else. Evidence files will be written by CI (planned GitHub Actions workflow `.github/workflows/ci.yml`) and committed for the demo build under `evidence/<commit>/`. The deck will cite that commit.

| Control | Spec | Planned evidence | Stop condition if it fails | Status |
|---|---|---|---|---|
| Privacy gate | §5.2 | `privacy-gate-report.md`: for each red-team category, messages run, disallowed tokens leaked (target 0), **every leaked token listed** (false negatives), plus the benign-message parse rate (utility). Asserts on the **actual outbound payload** built by the Gemini client, with the network call stubbed | Gemini provider disabled (scripted mode only) at start-up and in CI; no deploy; `GEMINI_API_KEY` is not set on the demo build until the report for that commit shows 0 leaks | **Implemented, tested locally**: `backend/app/privacy_gate/`; red-team test and start-up self-test in place; report at `evidence/privacy_gate/report.md` (0 leaks, 1 reported residual). CI not set up, so not yet an `evidence/<commit>/` file |
| Consent and retention | §2–3 | `test_consent_retention`: P1 with P4 declined deletes the session after 24 h (clock fixture) and on "End and delete"; accepted-quote data moves to the order; withdrawals of P1–P5 delete the right rows; consent events are unlinked. Plus a screenshot or log of "End and delete" in the demo build | No deploy | **Partial, tested locally**: P3 gate on KYC, P2/P3/P1 withdrawal effects, "End and delete", consent-event unlinking, 24 h advisor-session expiry and 30-day KYC purge are built and tested; P4 resume, P5 sharing and a scheduled retention job are not built |
| Authorisation and scope | §11, §13 | `test_scope_direct_api`: every back-office route called directly with each role's session, including partner A vs B and a referral code without P5 | No deploy | Planned |
| CSRF / Origin | §13 | `test_csrf`: every mutating route rejects a missing or wrong token and a foreign `Origin` | No deploy | Planned |
| KYC field encryption | §13 | `test_kyc_crypto`: round-trip across a process restart; rotation | No deploy | **Implemented, tested locally**: Fernet key ring, restart, rotation and lost-key behaviour (`backend/tests/test_kyc_service.py`); the test also checks the database file holds no plaintext GSTIN or trade name; ephemeral key only in demo mode |
| KYC answer key | §9 | `kyc-answer-key-report.md`: per-field and per-applicant results for 47 images, **false accepts first** | False accepts > 0 → that applicant is not used in the demo, and the deck reports the miss | **Implemented, tested locally**: production pipeline matches the drafted key for all 12 applicants, 0 false accepts (`evidence/kyc_pipeline/report.md`); per-field hand transcription of all 47 images still to do; not CI |
| Order and line states | §10 | `test_orders`: the mixed-order example (§10) and every transition in the table, including rejected ones | No deploy | **Implemented, tested locally**: `backend/app/orders/`; the mixed-order example, every hold, feasibility failure with substitute or decline, reschedule, cancel and idempotency (`backend/tests/test_orders.py`); walked through in the browser; reviewer approval waits for the back office |
| Quote arithmetic | §7, WORKED_QUOTES | `test_worked_quotes`: all worked quotes and negative cases reproduce exactly | No deploy | **Implemented, tested locally**: `backend/tests/test_worked_quotes.py` passes; CI not set up yet, so no `evidence/` file |
| Explanation guard and claims | §5.4, §14 | `test_guard`: banned content rejected; templates audited against §14 | Guard failures fall back to templates; template failures block deploy | **Guard implemented, tested locally** (`backend/tests/test_explain.py`); template audit against §14 not automated yet |
| Advisor evals | DECISIONS D17 | `advisor-evals.md`: about 20 scenarios on the fake provider, plus one capped live run | Live-run failures → demo uses scripted mode | **Partial**: end-to-end conversation tests with a fake provider (`backend/tests/test_advisor.py`); the ~20-scenario eval runner and live run are not built |
| `approved` LLM profile | §5.1 | Not built; a production requirement | — | Not in scope |
