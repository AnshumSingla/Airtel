# What the data says, and what it doesn't

Source: `data/raw/smb_leads.csv` (5,000 synthetic leads created Apr–Jun 2026), the mock registries and the catalogue. These numbers will be reproduced by a script in `ml/` so the deck cites a run, not a hand calculation.

Reading rule for everything below: these are **observations in one quarter of synthetic data**. Where two things move together we say "associated with", not "causes". Targets are **pilot hypotheses**, measured against a comparison group (section 8).

## 1. Funnel baseline

| Metric | Value | Note |
|---|---|---|
| Lead → activation | 7.4% (368 / 5,000) | |
| Lead → activation time | 17.6 days average | From lead creation to activation. **Not the same measure** as the case text's "installation and activation take 10–14 days", which covers only the period after the order |
| Status chase calls per activated customer | 3.0 | `customer_follow_up_calls` |
| Blended CAC per activation | ₹15,053 | Total acquisition cost of all leads ÷ activations |
| 6-month churn (activated) | 15.2% | |
| NPS (mean, 0–10) | 6.86 | |
| Median bundle | ₹6,900 / month | Ex-tax, inside the catalogue bands |

## 2. Where leads drop, and which drops the journey targets

1,583 of 4,632 dropped leads (34%) give a reason tied to our own process. The digital journey is **designed to address** these; whether it recovers them is what the pilot measures.

| Reason | Leads | Journey feature aimed at it |
|---|---|---|
| Owner had no time for a visit | 531 | Advisor, no visit needed |
| Visit not scheduled by sales | 296 | Advisor |
| Quote too complex to understand | 206 | One-page quote in plain words |
| Quote took too long to arrive | 179 | Instant quote |
| Missing GST/Udyam document, paperwork too long, details did not match, signatory not available | 273 | GSTIN prefill, upload checks with fix hints |
| Installation delayed beyond 21 days | 98 | Tracker and feasibility step (simulated); doesn't make installs faster |

Price-driven drops (price too high 414, competitor cheaper 207) are not addressed by the journey beyond showing a clear price.

## 3. GSTIN status is strongly associated with activation

Leads with a GSTIN activate at 9.6%, without at 2.0%. The registry has 167 Cancelled and 101 Suspended GSTINs. **Design response:** offer an optional, consented GSTIN check early, to prefill details and unlock GSTIN-only products. This is a convenience; asking earlier does not by itself raise activation.

## 4. Some historical bundles break the catalogue rules

56 of 368 activated bundles violate at least one rule. Leads per rule: 24 city tier (for example 1 Gbps in tier-2 cities), **21 with a GSTIN-only product but no active GSTIN** (22 product lines: 12 with no GSTIN at all, 7 Cancelled, 3 Suspended), 9 missing dependencies, 8 below minimum staff. Separately, 22 activations overall sit on Cancelled (18) or Suspended (4) GSTINs.
Not counted as a violation: 43 multi-site bundles include P01 Biz Fibre 100, which the catalogue targets at micro and professional businesses only. `target_segments` is not one of the README's eligibility rules, so the design treats it as a soft rule for defaults, not a rejection (POLICIES §6 step 0). These are the only off-target lines among all 1,651 lines in the activated bundles.
**Design response:** every bundle will go through the same rule checks, and **planned tests will cover these cases** (none exist yet; see the controls register in POLICIES §15). We will claim the engine rejects these combinations only once that test output exists, and never that the business has no other compliance gaps.

## 5. Status chasing is associated with churn and lower NPS

| Follow-up calls | Activated | 6-month churn | NPS |
|---|---|---|---|
| 1 | 34 | 6% | 7.5 |
| 3 | 137 | 12% | 6.9 |
| 5 | 43 | 28% | 6.0 |

NPS is also about a point lower once lead-to-activation passes 20 days. **This is correlation:** difficult or delayed orders may cause both more calls and more churn. **Hypothesis:** a tracker with proactive updates reduces repeat contacts; whether that lowers churn is a pilot readout, not a claim.

## 6. Channels

| Source | Share of leads | Conversion | CAC per activation |
|---|---|---|---|
| Field sales | 34% | 7.3% | ₹24,335 |
| Channel partner | 20% | 8.0% | ₹20,851 |
| Website form | 20% | 4.3% | ₹6,352 |
| Inbound call | 10% | 9.5% | ₹5,113 |
| Referral | 8% | 14.8% | ₹4,099 |
| WhatsApp campaign | 7% | 2.8% | ₹4,026 |

Website and WhatsApp leads are cheap and convert poorly, and in this data almost never convert for some regional-language groups (near 0% for Tamil, Kannada, Punjabi and Bengali on those channels; small groups, so wide uncertainty). Referral converts best but has the highest 6-month churn (24.6%). These are channel averages, not proof that a channel causes the outcome; leads differ by segment and size across channels.

## 7. Segments

| Segment | Share | Conversion | CAC / activation | Median bundle / month (ex-tax) | Months of revenue to recover CAC | 6-mo churn |
|---|---|---|---|---|---|---|
| Micro retail & services | 54% | 4.1% | ₹20,007 | ₹2,470 | ~8.1 | 22.7% |
| Professional offices | 25% | 11.1% | ₹10,695 | ₹6,575 | ~1.6 | 13.8% |
| Small multi-site | 15% | 11.0% | ₹15,614 | ₹28,080 | ~0.6 | 10.8% |
| Small manufacturers | 6% | 12.8% | ₹15,324 | ₹15,910 | ~1.0 | 8.1% |

"Months of revenue to recover CAC" uses **revenue, not margin**: the data has no gross margin, servicing cost, partner payout or lifetime value, so real payback is longer. With 22.7% of micro customers churning within 6 months, many leave before 8 months of revenue. **Hypothesis:** micro retail is only worth acquiring through low-cost channels; to be tested, not asserted.

## 8. Answers to the case's key questions (first drafts)

**Q1: Segment priority.**
1. **Professional offices first:** best mix of conversion (11.1%), revenue recovery (~1.6 months) and churn (13.8%), and the journey fits them well. Worked bundle: ₹4,633/month ex-tax (₹5,467 incl. tax), no setup fee ([WORKED_QUOTES.md §A](WORKED_QUOTES.md)).
2. **Micro retail as a low-cost self-serve test:** core bundle ₹2,197/month ex-tax (₹2,592 incl. tax) + ₹2,500 setup, add-ons as toggles ([§B](WORKED_QUOTES.md)). Installation by a channel partner.
3. **Multi-site and manufacturers assisted:** the advisor qualifies and quotes, then hands off to field sales. Example: ₹28,576/month ex-tax, 24-month SD-WAN, ~14-day install ([§C](WORKED_QUOTES.md)).

**Q5: Metrics: pilot design and hypotheses.**

*Design (corrected in review round 2; the round-1 figure of "650 per arm, one quarter" was wrong):*

| Input | Value | Source / reason |
|---|---|---|
| Population | New **website-form and WhatsApp-campaign** leads, **all cities** | The digital journey is online, so it needs no city restriction; installs use the existing teams in all 22 cities. This avoids the slower recruitment of a city-limited pilot |
| Volume | 1,353 per quarter (≈ 451 per month): 705 tier 1, 648 tier 2 | `smb_leads.csv`, Apr–Jun 2026 |
| Unit and assignment | The lead, randomised 50/50 at creation, before any contact, **stratified by lead source × city tier** (4 strata: website/WhatsApp × tier 1/2, permuted blocks) so both arms get the same source and tier mix | Stratum sizes per quarter: website 521 / 474, WhatsApp 184 / 174 (tier 1 / tier 2) |
| Baseline conversion (control) | **3.9%** (53 / 1,353 activated) | Data |
| Target (minimum detectable effect) | **7.0%** in treatment (+3.1 points) | Hypothesis |
| Test | Two-sided two-proportion z-test, α = 0.05, power 0.80 | — |
| Required per arm | **841** | Standard normal-approximation formula |
| Allowance for duplicates, crossover and loss | +10% → **935 per arm, 1,870 total** | Assumption |
| Enrolment time | 1,870 ÷ 451 per month ≈ **4.1 months** | — |
| Activation window | 45 days after lead creation | Every activation of a digital lead in the data happened within 30 days (median 17, max 30), so 45 days loses none |
| Primary readout | ≈ 5.6 months after start (enrolment + 45 days) | — |
| Churn readout date | **6 months after the last eligible activation date**, i.e. end of enrolment + 45 days + 6 months ≈ **11.6 months after start**, so every included customer has at least 6 months of observation after activation | Defined to answer the round-3 review |
| What one quarter alone could detect | 3.9% → about **7.7%** (608 usable per arm) | Same test |

*Analysis rules:*
- **Intention to treat** by randomised assignment is the primary analysis. A treatment-arm lead that is handed off to field sales or a partner still counts as treatment; a control lead that later finds the website journey still counts as control (reported separately as crossover).
- **Repeat businesses:** a new lead that matches an earlier pilot lead (same phone number or GSTIN in the CRM) keeps its first assignment and is not counted twice.
- Partner- and field-sourced leads are **not** randomised; they keep the current process, and their handoff-queue results are reported separately as descriptive numbers.
- **Causal comparisons use every randomised lead as the denominator** (intention to treat). Each outcome asks whether a randomised lead reached X within a fixed window after lead creation; a lead that hasn't reached X by the cutoff counts as **no**. The windows are set so the historical digital cohort loses nobody: quote acceptance by day 21 (latest seen: day 14), KYC completion by day 30 (latest: day 19), activation by day 45 (latest: day 30).
- **Anything conditional on a post-randomisation event is descriptive only.** Stage-to-stage funnel rates, churn among activated customers and contacts per activated order show *where* each arm loses people. But treatment can change who reaches each stage, so arm differences in these are **not** treatment effects. The deck labels them "descriptive, among leads who reached this stage" and never uses "higher in treatment" for them.
- **Only the primary outcome is powered** (activation within 45 days, sample size above). Other per-lead outcomes are secondary, reported with 95% confidence intervals and no pass/fail target.
- **Historical figures are context, not benchmarks.** The control arm is the benchmark. Historical values shown are for the **digital cohort** (website + WhatsApp, the randomised population), with whole-dataset values in brackets.
- Every outcome is reported overall and by stratum (source × tier).
- **No subgroup is defined by what happens after randomisation.** "Orders whose items install fast" is not a valid comparison group, because the advisor in the treatment arm influences which items are chosen. The only pre-specified subgroup uses `products_of_interest`, recorded at lead creation. It is **exploratory**: shown with counts per arm and confidence intervals and no separate success target, because it is not separately powered (38 historical activations among 1,147 leads).

**Causal outcomes (per randomised lead, intention to treat)**

| Outcome | Role | Historical context: digital cohort, per lead | Pilot hypothesis | Readout |
|---|---|---|---|---|
| Activated within 45 days | **Primary** (powered) | **3.9%** (53 / 1,353; website 4.3%, WhatsApp 2.8%) [7.4%] | ≥ 7% in treatment | ≈ 5.6 months |
| Quote accepted within 21 days | Secondary | 10.0% (135 / 1,353) | Higher in treatment | ≈ 4.8 months |
| KYC complete within 30 days | Secondary | 6.6% (89 / 1,353) | Higher in treatment | ≈ 5.1 months |
| Time to activation, all randomised leads, censored at day 45 (Kaplan–Meier, hazard ratio) | Secondary | Activated leads averaged 17.9 days | Faster in treatment | ≈ 5.6 months |
| **Retained customer:** activated within 45 days **and** not churned within 6 months of activation | Secondary (business outcome) | 3.4% (46 / 1,353) | Higher in treatment | ≈ 11.6 months |
| **6-month retained monthly revenue per randomised lead** (monthly bundle value if a retained customer, else 0) | Secondary (business outcome) | ₹510 per lead | Higher in treatment | ≈ 11.6 months |
| Status contacts within 60 days of lead creation, per randomised lead (zeros included) | Secondary | 0.70 per lead (62% have zero). The historical data has no contact dates, so this figure covers all contacts | Lower in treatment | ≈ 6.1 months |
| The same outcomes in the `products_of_interest` subgroup | Exploratory | 1,147 leads, 3.3% activated, 38 activations | No target | With the above |

**Descriptive diagnostics (conditional, not causal)**

| Diagnostic | Historical context: digital cohort [whole dataset] |
|---|---|
| Quote acceptance among leads who reached needs-assessed | 39.9% (135 / 338) [43.6%] |
| KYC completion among leads who accepted a quote | 65.9% (89 / 135) [68.3%] |
| First-pass `checks_passed` rate, and false accepts in an audited sample (treatment only) | Not measured in the data; zero false accepts is a guardrail |
| Status contacts per activated order | 2.9 [3.0] |
| 6-month churn among activated customers | 13.2% (7 / 53, very small) [15.2%] |

**Mix vs retention.** If treatment activates more customers, churn among activated customers can change simply because a different kind of customer activates. We do not try to separate the two causally. The randomised answer is the **retained-customer** and **retained-revenue per lead** outcomes above: they show whether the journey leaves Accel with more retained customers and revenue per lead, whatever the mix. Alongside them we show, descriptively, the mix of activated customers in each arm (segment, tier, source, bundle value) and churn within each segment, labelled exploratory. A higher retained-customer rate with similar within-segment churn suggests a volume effect. Lower within-segment churn would suggest better retention, but that comparison is still not randomised.

For reference, the historical figure the reviewer computed for **bought** fast-install bundles (252 of 368 activations, mean 17.1 days; 31 digital activations, mean 16.8 days) is context only. It is not used as a comparison, because it conditions on what was bought.

**Cost per activation: an arm-symmetric boundary.** Every cost line is measured the same way in both arms. Anything we can't measure in both is listed, and the metric is then called a **partial proxy**.

| Cost line | Control arm | Treatment arm |
|---|---|---|
| Campaign / media spend | Per lead, from the lead's source (same source mix by stratification) | Same |
| Sales and call-centre time | Logged minutes per lead × standard hourly rate | Same (handoffs from the journey are logged the same way) |
| Partner payouts | Per activation, actual | Same |
| Support contacts | Contacts × standard cost per contact | Same |
| Shared platforms (CRM, billing, existing quote tools) | Per-lead share of the monthly run cost | Same per-lead share |
| Journey run cost (LLM, OCR compute, hosting, operations) | 0 (control doesn't use it) | Actual monthly run cost ÷ treatment leads |
| One-time build cost of the journey | **Excluded** from pilot operating CAC | **Excluded** from pilot operating CAC; shown separately, plus an amortised view over a declared horizon (12 months of national digital-lead volume, about 5,400 leads) |

Reported per arm: total cost, activation count, and cost per activation with a bootstrap 95% interval. Reported across arms: **incremental cost per additional activation** = (treatment cost − control cost) ÷ (treatment activations − control activations), with a bootstrap interval. It is unstable when the activation difference is small, and we flag that rather than hide it. Historical context: ₹5,913 per activation, pooled for the digital cohort, acquisition spend only, so a partial proxy [whole dataset ₹15,053].

Guardrails (descriptive): bundles passing rule checks (100%), advisor-to-human handoff rate, complaint rate, share of turns where the privacy gate masked more than half the message, and share of sessions that ended in scripted mode.
