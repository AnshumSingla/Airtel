# Architecture and stack decisions (grilled)

Each decision lists the options we weighed, what we picked, why, and what would make us change it.
The overriding constraint: **the submission closes 07 Nov 2026, 11:59 PM IST**, about 2.5 days after design freeze, with a 2-person team. Anything that does not show up in a 3-minute demo or the deck has to justify its build time.

---

## D1. Monolith or services?

- **Options:** microservices with a queue (one public repo for this case uses 8 Go services + Kafka); FastAPI + separate AI service + Spring backend (another repo); one modular monolith.
- **Pick:** one FastAPI modular monolith, with clear package boundaries (`catalogue`, `pricing`, `advisor`, `kyc`, `orders`, `backoffice`, `privacy`).
- **Why:** with 2.5 days, every extra service costs setup, ports, auth and debugging time and adds nothing judges can see. Package boundaries still let us draw a clean component diagram and argue how it splits at scale (KYC and the advisor are the first candidates to become services).
- **Would change if:** never inside this deadline.

## D2. Backend language

- **Options:** Python/FastAPI; Node/Express or Next.js API routes; Java/Spring.
- **Pick:** Python 3.11 + FastAPI + Pydantic v2.
- **Why:** pandas for the CSVs, scikit-learn for propensity, local OCR libraries, and every LLM SDK are all native Python. Pydantic models double as tool schemas for the LLM. Python 3.11 is already installed on this machine.
- **Would change if:** a teammate is much faster in TypeScript; then a single Next.js app with tesseract.js is the alternative (a public repo shows it works), at the cost of weaker OCR and ML.

## D3. Frontend

- **Options:** Next.js; React + Vite SPA; server-rendered templates; Flutter.
- **Pick:** React 18 + Vite + TypeScript + Tailwind, react-i18next, installable PWA, built and served by FastAPI.
- **Why:** fastest to iterate, no SSR needed, one deploy unit. Mobile-first layout because the case says "on a phone". PWA install gives the app feel without app-store work.
- **Would change if:** nothing realistic in this window.

## D4. Database

- **Options:** Postgres (Neon/Supabase), SQLite, in-memory only.
- **Pick:** SQLite via SQLAlchemy, CSVs loaded at startup.
- **Why:** zero setup, ships inside the Docker image, enough for a demo. SQLAlchemy keeps the swap to Postgres a connection-string change, which we state in the deck's scale story.
- **Would change if:** the host has an ephemeral disk that wipes sessions mid-demo; then use a free managed Postgres.

## D5. Who decides the bundle: LLM or rules?

- **Options:** LLM picks from the catalogue in its prompt; LLM with RAG; LLM collects slots, rules engine decides.
- **Pick:** LLM collects slots through tool calls; **a deterministic rules engine picks products, quantities and price**; the LLM explains the engine's reason codes; an output guard checks that every product name and rupee amount in the reply matches the engine output.
- **Why:** correctness under live judge scenarios, reproducibility, auditability, and the data shows unchecked selling already breaks the rules (56 of 368 activated bundles). 25 products don't need RAG; they fit in code.
- **Would change if:** never. This is the core of the pitch.

## D6. Which LLM

- **Options:** Gemini (free tier); Groq-hosted open models (free, fast, weaker at Indic languages); Claude (paid); Sarvam (Indic-first, voice).
- **Pick (team decision, 05 Nov): Gemini on the free tier**, through the `google-genai` SDK, behind a thin `LLMProvider` interface. A fake provider is used for tests and evals, and the scripted advisor is the fallback.
- **Why the interface still matters:** moving to paid Gemini (or Vertex AI in an India region) for production is a config change, which is what we tell judges.

## D6a. Living inside the free-tier quota

**The numbers are not stable.** Google no longer publishes one fixed table: limits show per project in AI Studio. Third-party figures from the last few months range from 10 RPM / 500 requests per day for Flash down to **5 RPM / 20 requests per day** for the newest Flash. Flash-Lite models have looked more generous (around 10 RPM / 500 a day). Daily quotas reset at midnight Pacific, which is **1:30 PM IST** in November. Design for the worst case:

1. **Day-1 check:** read the actual RPM/RPD for each model in AI Studio and write them in `.env.example` comments. Pick the primary model from that, not from memory.
2. **Primary model = the Flash-Lite tier** (higher daily quota), with a Flash model as the second entry in the fallback chain. Model names come from `GEMINI_MODELS` in the environment (ordered list), with the `-latest` aliases as defaults once verified.
3. **One call per normal turn.** No multi-step tool loop. Each turn sends the redacted history, the profile so far and the list of missing slots, and asks for **structured JSON output** (`response_schema`): `{slots_extracted, reply, intent: ask | recommend | handoff | off_topic, language}`. The server merges the slots and decides what happens next.
4. **One extra call on the recommendation turn only:** once the profile is complete, the server runs the rules engine and sends the reason codes for a plain-language explanation in the owner's language. The prompt forbids prices; amounts appear only on the deterministic quote card. If that call fails, we use **templated EN/HI explanations** for each reason code, so the recommendation never depends on the LLM.
   Budget: about 6–8 calls per full advisor session.
5. **Client-side rate limiter:** token bucket per model, set just under the real RPM. On 429 or 503, move down the chain: Flash-Lite → Flash → scripted advisor. The UI shows nothing broken; the scripted advisor continues from the same slots.
6. **Protect the quota during development:** unit tests and the eval runner use the fake provider by default, and `--live` is opt-in and capped (for example 20 calls). Cache live responses by prompt hash in dev so reruns cost nothing.
7. **Demo-day plan:** keep one API key (own project) only for the recording and judging, never used for development. Record the video on 7 Nov **after 1:30 PM IST**, when the daily quota has just reset. The scripted advisor is rehearsed as the backup path.
8. **Privacy consequence:** Google's terms for unpaid API use allow it to use submitted content to improve its products (re-read the current terms before writing the privacy note). So **no personal data or identifiers go to Gemini**: GSTIN, Udyam, PAN, phone, email and names are redacted server-side before every call, and KYC documents are never sent. The privacy note says production would use a paid or Vertex AI (asia-south1) setup, where content is not used for training.

- **Would change if:** the AI Studio check shows a daily quota too small for the eval run plus the demo. Then make the scripted advisor the default, use Gemini only for free-text understanding and explanations, and say so plainly.

## D7. Languages and voice

- **Options:** UI in EN only + LLM replies in any language; UI in EN/HI; full regional UI; Bhashini/Sarvam ASR+TTS; browser Web Speech API.
- **Pick:**
  - UI strings in **English and Hindi** (react-i18next), structured so adding Marathi (the largest regional group, 505 leads) is a JSON file.
  - The advisor **replies in the language the owner writes in** (Hindi, Hinglish, Tamil, Marathi, ...). The LLM does this for free; the scripted fallback covers EN/HI/Hinglish only.
  - Voice input through the **browser Web Speech API** (`hi-IN`, `ta-IN`, `mr-IN`, ...), and optional text-to-speech of replies. No new backend, works in Chrome on Android.
- **Why:** the data shows digital channels barely convert regional-language owners (website/WhatsApp conversion near 0% for Tamil, Kannada, Punjabi, Bengali). Language is a stated requirement and a cheap win. Server-side ASR is a stretch goal, not a day-1 build.
- **Would change if:** Web Speech is unreliable on the demo device; then type in the video and mention voice as roadmap.

## D8. OCR: local engine or vision LLM?

- **Options:** Tesseract (system binary, not installed here, Windows install friction); RapidOCR / PaddleOCR via pip (ONNX, no system binary); EasyOCR (heavy PyTorch); a vision LLM (Gemini/Claude) returning JSON.
- **Pick:** **local OCR (RapidOCR via pip)**, preceded by red-channel watermark removal and deskew, followed by a label-anchored parser and checksum-guided repair. Tesseract is the fallback if RapidOCR misbehaves on day 1.
- **Why:**
  - **Privacy story:** KYC images never leave our server, so there is no cross-border transfer of identity documents. This is a real DPDP point and a visible difference from teams that send documents to a cloud vision model.
  - The specimens are clean, typed, fixed-layout documents with a red diagonal watermark: ideal for classic OCR once the red channel is used.
  - pip-only install keeps the Docker image simple.
- **Risk:** RapidOCR accuracy on mixed alphanumerics (O/0, I/1). Mitigated by the GSTIN check digit and registry name confirmation. **Day-1 spike:** run it on all 47 images and compare against a hand-made answer key before building anything on top.
- **Would change if:** the spike shows under ~90% field accuracy after preprocessing. Then use a vision LLM with explicit consent text and PII-free prompts, and say so in the privacy note.

## D9. KYC rules

Checks we implement (all deterministic, each with an owner-facing fix hint):

| Group | Check |
|---|---|
| Quality | blur (Laplacian variance), skew, resolution, file type/size |
| Format | GSTIN 15-char structure, state code, embedded PAN pattern (4th char `X` accepted), mod-36 check digit; Udyam `UDYAM-SS-00-NNNNNNN` |
| Registry | GSTIN exists and is **Active** (not Cancelled/Suspended); Udyam exists; legal/trade name and constitution agree |
| Cross-document | names agree across GST, Udyam, ID, bill (fuzzy, token-based); address on bill matches principal place of business; GSTIN state code = address state |
| Freshness | address proof dated no more than 90 days before 2026-07-15; signatory ID valid on 2026-07-15 |
| Completeness | all 4 documents, or a registry match accepted in place of a missing Udyam certificate |
| Authority | signatory name matches the proprietor/partner/director on the GST record (or a flag for specialist review) |

Verdicts: `approved`, `needs_action` (owner can fix in-app), `review` (specialist), `blocked`.
We build our own answer key for K01–K12 by inspecting every image and test the pipeline against it. Other teams' published findings (K01 cancelled GSTIN, K02 tilted, K04 blurry, K05 missing Udyam, K07 altered name, K11 stale bill) are a cross-check, not our source of truth. We have confirmed K01's GSTIN is Cancelled in the registry ourselves.

## D10. Pricing

The catalogue gives a min–max monthly band per product. We need one transparent, repeatable rule:

- **Contract length sets the point in the band:** longest allowed contract → `price_min`; 12 months → midpoint; shorter (where the product allows it) → `price_max`. The owner sees the trade-off as a toggle on the quote ("Save ₹X/month with 24 months").
- Quantity rules by unit: per site × `num_sites`; per user/device from `employee_count` (editable); per line defaults from roles (editable); cameras default 2 per site.
- One-time setup fees shown separately; GST at 18% shown as a line, total shown both ex- and incl-GST.
- Contract term of the bundle = the longest `min_contract_months` among the chosen items, shown up front.
- "Compared with what you pay today" line using the stated current telecom spend.
- **Would change if:** the team prefers tier-based pricing. Either way it lives in one module with tests.

## D11. Recommendation logic (rules engine)

1. Map business type → segment (micro / professional / multi-site / manufacturer), city → tier and state.
2. Start from the **segment starter bundle, derived from what activated customers in that segment actually bought** (for example professional offices: cloud email 100%, postpaid 599 52%, endpoint security 49%; micro: postpaid 299 100%, fibre 100 92%, POS 34%).
3. Add products for stated needs (UPI/POS, WhatsApp catalogue, CCTV, failover, IoT, fleet).
4. Filter on eligibility: city tier, minimum employees and sites, **active GSTIN** for GSTIN-only products.
5. Resolve `requires_one_of` dependencies by adding the cheapest eligible connectivity product.
6. Substitute instead of failing: tier 2 asking for 1 Gbps → 300 Mbps; no fibre → 5G AirFiber; no GSTIN → explain which products a GSTIN would unlock.
7. If over the stated budget, drop add-ons by priority until it fits, and say which ones were dropped.
8. Emit reason codes (`SEGMENT_BASE`, `NEED_CCTV`, `DEP_ADDED`, `SUBSTITUTED_TIER`, `BLOCKED_NO_GSTIN`, ...) that the LLM turns into plain language.

## D12. Propensity score

- **Options:** heuristic score; logistic regression; gradient boosting.
- **Pick:** logistic regression on features known at lead creation (segment, source, tier, language, size, turnover band, GSTIN present and its registry status, Udyam, current internet/provider/spend, number of products of interest). No stage dates or outcomes (leakage). Compare with gradient boosting in the notebook and report cross-validated AUC; ship the LR unless GBM is clearly better, because coefficients give reason codes for the back office ("GSTIN active +", "WhatsApp source −").
- Rank the call list by `p(activate) × expected monthly value`, not by p alone.
- Trained offline in `ml/`, exported as JSON, scored in the API without heavy deps.

## D13. WhatsApp front end (stretch)

- **Options:** real WhatsApp Cloud API (Meta app setup, number verification: too slow and risky for the deadline); Twilio sandbox; an in-app WhatsApp-style simulator talking to the same advisor API.
- **Pick:** if time allows, a **WhatsApp-style simulator** page that reuses the advisor endpoint, plus simulated notifications in the tracker. Real integration is roadmap.

## D14. DigiLocker and e-sign

Mocked: a "Fetch from DigiLocker" button that returns the registry-backed document for the GSTIN, and a mock e-sign step on the quote acceptance. Both are shown as the target production integration in the architecture and privacy note.

## D15. Hosting

- **Pick:** one Docker image on a free tier (Render or Railway), plus a local run for recording. Decide on day 1 by deploying the empty skeleton first; never leave deployment to the last evening.

## D16. Testing and evals

- Unit tests: GSTIN checksum and repair, eligibility, dependencies, pricing, KYC answer key (K01–K12).
- Advisor evals: about 20 scripted scenarios modelled on what judges are likely to test (tier-2 owner asking for 1 Gbps, no-GSTIN kirana asking for WhatsApp API, 8-site restaurant chain, Hindi-only owner, budget cap, leased line for a 5-person shop, refusal or off-topic prompt). Assertions run on the **engine output**, so they are deterministic even with an LLM in the loop. By default they run on the fake provider; a capped `--live` run against Gemini is done once on day 2 and once after feature freeze (D6a).

---

## Open questions for the team

1. ~~LLM key~~: decided, Gemini free tier (D6, D6a). Still to do: read the real per-model limits in AI Studio on day 1.
2. **Deck length:** the Unstop page asks for a **7-slide PPT (PDF + PPT, file name `TeamName_CampusName`)** for this round; the case PDF asks for a business case of up to 10 slides plus a demo video, repo, architecture diagram and a 1-page privacy note. Plan: a 7-slide main deck that carries links to the video and repo, with architecture and privacy as appendix pages. Confirm on the Unstop discussion board if possible.
3. **Registration:** registration closes 06 Nov 2026, 11:59 PM IST. Confirm the team is registered.
4. **Team skills:** confirm both of us are comfortable with Python + React; otherwise revisit D2.
