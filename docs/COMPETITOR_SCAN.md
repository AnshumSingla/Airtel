# How other teams are approaching this case

GitHub search on 05 Nov 2026 found about 20 public repos for this exact case (search terms: "udyam digital", "airtel sync", file name `mock_gstin_registry`). Read from their READMEs only; we copy no code.

| Repo | Stack | Notable |
|---|---|---|
| [AgileSeagull/AirtelSync](https://github.com/AgileSeagull/AirtelSync) | React + Vite PWA, FastAPI, Gemini (Claude optional), Tesseract | Strongest README. "LLM handles conversation; deterministic code decides." Scripted fallback, Hindi/Hinglish, mock DigiLocker, local OCR with watermark removal + deskew + blur score, GSTIN repair via checksum + registry, masked IDs, audit log, Twilio WhatsApp, advisor evals. Publishes per-applicant KYC verdicts. |
| [CKofficial-1797/Airtel_Sync_2026](https://github.com/CKofficial-1797/Airtel_Sync_2026) | React, Spring Boot, FastAPI AI service, Gemini, Neon Postgres | Same "AI never decides" rule, 17 KYC checks, sends documents to Gemini for extraction, LR propensity exported to JSON and scored in Java. |
| [SimarSingh1910/UdyamSaathi](https://github.com/SimarSingh1910/UdyamSaathi) | Next.js full stack, Drizzle, PGlite, tesseract.js | Deployed on Render. Full WhatsApp journey + simulator, OTP via voice/WhatsApp, back office with product editor. |
| [Avi974/Airtel](https://github.com/Avi974/Airtel) | Next.js 14, FastAPI, SQLite, Tesseract | Pricing formula by tier and contract, "anti-substitution" check of edited fields against OCR tokens, consent ledger with revocation. |
| [D-Vspec/AirtelHack](https://github.com/D-Vspec/AirtelHack) | Go microservices, Kafka, Postgres, LangChain.js, Next.js, Expo | Heavy infrastructure; useful as a warning about scope. |
| [tandonhardik/udyam-digital](https://github.com/tandonhardik/udyam-digital) | Python, Tesseract, Groq optional | Counts 48 rule-breaking activated bundles (we count 56; differing rule interpretation). |
| [ArnavSurana/Project-Udyam-Digital](https://github.com/ArnavSurana/Project-Udyam-Digital) | FastAPI, React, Tesseract | Propensity 0–100, top-20 call queue. |
| [Hrithikkraj/Airtel-Udyam-hackathon](https://github.com/Hrithikkraj/Airtel-Udyam-hackathon) | FastAPI, React, SQLite, Groq | OCR in memory only. |
| [bhaweshwar/airtel-sync-udyam-digital](https://github.com/bhaweshwar/airtel-sync-udyam-digital) | React 19, Spring Boot, Gemini | Redacts PAN/GSTIN/Aadhaar/phone before sending to the LLM. |
| [HemantRaj-2005/airtel-hackathon](https://github.com/HemantRaj-2005/airtel-hackathon) | Next.js, Express, Prisma, Neon, Gemini | Mostly planning docs so far. |

## What this tells us

1. **The baseline is already high.** "LLM talks, rules decide", EN/HI, consent screen, GSTIN checksum, Tesseract OCR and a propensity score are table stakes. Matching them is not enough to stand out.
2. **Gemini free tier is the common LLM choice**, and at least one team documents its 5 requests/minute limit as a demo risk. A reliable provider plus a scripted fallback matters.
3. **Where we can differentiate:**
   - **Business judgement in the product**, not only in the deck: the data signals (GSTIN-first prefill, the 56 rule-breaking bundles, follow-up calls ↔ churn, regional-language conversion gap, ₹20k micro CAC) each map to a visible feature.
   - **Documents are not sent to a third-party OCR or AI vendor** (local OCR, images not stored). Some teams send documents to a cloud vision model. This reduces onward transfer; it is one privacy choice among several, not a privacy guarantee.
   - **Honest labelling** (simulated vs real, automated checks vs verified identity, observation vs hypothesis): most READMEs use "verified" and "compliant" freely, which is easy for a judge to puncture.
   - **Partner-friendly design** (key question 4) is thin in most READMEs: attribution codes, assisted KYC by partners, field-sales handoff with context.
   - **A privacy gate in front of the LLM** (specified so that raw text never leaves the server; to be proven by a red-team report), where other teams rely on redaction or send text as-is. Voice and regional-language conversation become roadmap items as a result, which we state openly.
   - **A call list that has to beat a baseline** (ranked by expected revenue), not just a probability score.
   - Metrics framed as a randomised pilot with leading and outcome measures, tied to the baseline we computed.
4. **Scope warning:** the microservice and Kafka builds are impressive but leave less time for the parts judges test live.
