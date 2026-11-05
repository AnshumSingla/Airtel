# What the data says (and how it shapes the product)

Source: `data/raw/smb_leads.csv` (5,000 leads, Apr–Jun 2026), registries and catalogue. All synthetic.
These numbers were computed during design and will be reproduced in a script under `ml/` so the deck can cite them.

## Funnel baseline

| Metric | Value |
|---|---|
| Lead → activation | 7.4% (368 / 5,000) |
| Lead → activation time | 17.6 days average |
| Status chase calls per activated customer | 3.0 |
| Blended CAC per activation (total spend / activations) | ₹15,053 |
| 6-month churn (activated) | 15.2% |
| NPS (mean, 0–10) | 6.86 |
| Median bundle | ₹6,900 / month |

## Signal 1: a third of drops are caused by our own process

1,583 of 4,632 drops (34%) have a reason the digital journey removes directly:

| Reason | Leads | Fixed by |
|---|---|---|
| Owner had no time for a visit | 531 | Advisor (no visit needed) |
| Visit not scheduled by sales | 296 | Advisor |
| Quote too complex to understand | 206 | One-price quote in plain words |
| Quote took too long to arrive | 179 | Instant quote |
| Missing GST/Udyam document, paperwork too long, details did not match, signatory not available | 273 | Smart KYC with registry prefill and fix hints |
| Installation delayed beyond 21 days | 98 | Tracker, feasibility check, 5G AirFiber fallback |

Price-driven drops (price too high 414, competitor cheaper 207) are addressed by the transparent band pricing and the "vs what you pay today" line, not removed.

## Signal 2: GSTIN is the strongest single predictor

Leads with a GSTIN activate at 9.6%, without at 2.0%. Also 167 GSTINs in the registry are Cancelled and 101 Suspended. **Product idea:** ask for the GSTIN early and prefill the rest of the journey from the registry (name, constitution, state, address). That turns the biggest predictor into the shortest path.

## Signal 3: human selling breaks the catalogue rules

56 of 368 activated bundles violate the catalogue's own eligibility rules: 24 on city tier (for example 1 Gbps fibre in tier-2 cities), 22 GSTIN-only products sold without an **active** GSTIN (18 activations on Cancelled and 4 on Suspended GSTINs), 9 missing dependencies, 8 below minimum employees. That's a compliance risk. The rules engine makes it impossible.

## Signal 4: status chasing goes with churn

| Follow-up calls | Activated | 6-month churn | NPS |
|---|---|---|---|
| 1 | 34 | 6% | 7.5 |
| 3 | 137 | 12% | 6.9 |
| 5 | 43 | 28% | 6.0 |

NPS also drops about a point once lead-to-activation passes 20 days. **Product idea:** the tracker with proactive notifications is a churn lever, not a nice-to-have.

## Signal 5: cheap digital channels don't convert, expensive human ones do

| Source | Share of leads | Conversion | CAC per activation |
|---|---|---|---|
| Field sales | 34% | 7.3% | ₹24,335 |
| Channel partner | 20% | 8.0% | ₹20,851 |
| Website form | 20% | 4.3% | ₹6,352 |
| Inbound call | 10% | 9.5% | ₹5,113 |
| Referral | 8% | 14.8% | ₹4,099 |
| WhatsApp campaign | 7% | 2.8% | ₹4,026 |

Website and WhatsApp leads are cheap but convert poorly, and almost not at all for regional-language owners (near 0% for Tamil, Kannada, Punjabi, Bengali). **Product idea:** the advisor raises conversion on the cheapest channels; vernacular support matters most there. Referral converts best but churns most (24.6%), so a referral programme needs a fit check, not just a reward.

## Signal 6: segments behave very differently

| Segment | Share | Conversion | CAC / activation | Median bundle / month | 6-mo churn | Contract |
|---|---|---|---|---|---|---|
| Micro retail & services | 54% | 4.1% | ₹20,007 | ₹2,470 | 22.7% | 12 m |
| Professional offices | 25% | 11.1% | ₹10,695 | ₹6,575 | 13.8% | 12 m |
| Small multi-site | 15% | 11.0% | ₹15,614 | ₹28,080 | 10.8% | 12–24 m |
| Small manufacturers | 6% | 12.8% | ₹15,324 | ₹15,910 | 8.1% | 24 m |

Micro retail costs ₹20k to acquire for a ₹2.5k/month customer who churns 23% of the time: unprofitable through human channels, viable only self-serve.

## Answer to key question 1 (segment priority), first draft

1. **Professional offices first** (clinics, CA firms, coaching): good conversion, mid value, low churn, comfortable with a phone journey. Fully self-serve. Starter bundle: Biz Fibre 300 + cloud email per user + endpoint security + 1–2 postpaid 599, 12 months, about ₹5–7k/month.
2. **Micro retail at scale, self-serve only**: kirana, salon, pharmacy. Bundle: Biz Fibre 100 (or 5G AirFiber) + postpaid 299 + Cloud POS / UPI + secure guest Wi-Fi, optional WhatsApp API if GSTIN, under ₹2,500/month, 12 months, with a channel partner doing install. The goal is to get CAC under about ₹3k.
3. **Multi-site and manufacturers: assisted.** The advisor qualifies and quotes, then hands off to field sales with full context (SD-WAN, leased lines, failover, IoT, 24-month terms).

## Answer to key question 5 (metrics), first draft

| Metric | Baseline | 6-month target |
|---|---|---|
| Lead → activation conversion | 7.4% | 12% (digital-journey leads) |
| Lead → activation time | 17.6 days | ≤ 7 days for connectivity bundles |
| Blended CAC per activation | ₹15,053 | ≤ ₹7,000 |
| Status chase calls per customer | 3.0 | ≤ 0.5 |
| 6-month churn | 15.2% | ≤ 10% |

Guardrails: share of bundles passing eligibility checks (target 100%), KYC first-pass approval rate, advisor-to-human handoff rate.
