# Worked example quotes

Computed from `data/raw/product_catalogue.csv` with the rate card in [POLICIES.md §7](POLICIES.md#7-rate-card-and-quote): band midpoint, setup × quantity, an illustrative uniform 18% tax on recurring and one-time charges (a mock rule, not a tax classification), no discounts. Every bundle below was run through the eligibility and dependency rules (tier, minimum employees, minimum sites, active GSTIN, `requires_one_of`) **and the catalogue targeting rule** (`target_segments`, a soft rule per [POLICIES.md §6](POLICIES.md#6-recommendation-rules) step 0: never a rejection, but every default must be on-target). All default items in A, B, B+ and C are on-target for their segment. These same cases become unit tests for the pricing and rules engine, so the code has to reproduce these numbers exactly.

All prices are a **demo rate card** for synthetic data, not Accel tariffs.

**How the "Why" column is written** ([POLICIES.md §14](POLICIES.md#14-claims-register-what-the-owner-is-told-and-where-it-comes-from)). Each reason is tagged with its source, and the owner sees it worded that way:
- **[YOU TOLD US]** is used only when the slot is on the owner's **confirmed summary card**.
- **[SEGMENT DEFAULT]** is shown as "most businesses like yours choose this", with the share of activated customers in that segment who bought it [DATA].
- **[QTY DEFAULT]** is an editable quantity assumption from §7, shown as "change it on the quote".
- **[CATALOGUE TARGET]** quotes the catalogue's `target_segments` ("Listed by Accel for multi-site businesses"). It is used when purchase shares between on-target options don't show a clear preference.
- Product facts come only from the catalogue description.

No reason guesses at the owner's internal roles or sensitive details (for example, that the PCs hold patient data). These texts are fixtures for the planned template tests, and the claims audit covers this file and the demo script as well as the advisor templates.

## A. Professional office: the first target segment

**Confirmed summary card:** Dental clinic · Pune (tier 1) · 12 staff · 1 site · has GSTIN (checked: Active, mock registry) · needs stated: none. Rule check: passes.

| ID | Product | Unit | Qty | Why it is here (as the owner sees it) | ₹/unit/mo (band) | Monthly | One-time | Min term | Install |
|---|---|---|---|---|---|---|---|---|---|
| P02 | Biz Fibre 300 | per site | 1 | [SEGMENT DEFAULT] "The fibre speed professional offices choose most often (44%)." [YOU TOLD US] 1 site | 1,649 (1,499–1,799) | 1,649 | 0 | 12 m | 5 d |
| P16 | Cloud Email & Office Suite | per user | 7 | [SEGMENT DEFAULT] "Chosen by every professional office we've served." [QTY DEFAULT] 60% of the 12 staff you told us about; change it on the quote | 138 (125–150) | 966 | 0 | 12 m | 1 d |
| P20 | Endpoint Security | per device | 5 | [SEGMENT DEFAULT] "About half of professional offices add antivirus and ransomware protection (49%)." [QTY DEFAULT] 40% of your 12 staff; change it on the quote | 124 (99–149) | 620 | 0 | 12 m | 1 d |
| P08 | Business Postpaid 599 | per line | 2 | [SEGMENT DEFAULT] "The business mobile plan most professional offices choose (52%)." [QTY DEFAULT] 2 lines for offices like yours; change it on the quote | 699 (599–799) | 1,398 | 0 | 1 m | 1 d |

The advisor may instead **ask** "How many business mobile lines do you need?" before recommending. If the owner answers, that answer becomes a [YOU TOLD US] slot.

| | Ex-tax | Tax (illustrative 18%) | Incl. tax |
|---|---|---|---|
| Monthly recurring | ₹4,633 | ₹834 | **₹5,467** |
| One-time | ₹0 | ₹0 | ₹0 |
| **First payment** | | | **₹5,467** |

Commitments: fibre, email and security 12 months; mobile lines month-to-month. Slowest item about 5 days (indicative).
The segment's historical median bundle is ₹6,575/month, so this bundle sits below it.

## B. Micro retail: core bundle

**Confirmed summary card:** Kirana · Ludhiana (tier 2) · 3 staff · 1 site · no GSTIN · needs stated: **billing and UPI/card payments**. Rule check: passes.

| ID | Product | Unit | Qty | Why (as the owner sees it) | ₹/unit/mo (band) | Monthly | One-time | Min term | Install |
|---|---|---|---|---|---|---|---|---|---|
| P01 | Biz Fibre 100 | per site | 1 | [SEGMENT DEFAULT] "Fibre that most shops like yours choose (92%)." [YOU TOLD US] 1 site | 1,099 (999–1,199) | 1,099 | 0 | 12 m | 5 d |
| P07 | Business Postpaid 299 | per line | 1 | [SEGMENT DEFAULT] "A business mobile line, chosen by every shop we've served." [QTY DEFAULT] 1 line; change it on the quote | 349 (299–399) | 349 | 0 | 1 m | 1 d |
| P19 | Cloud POS & Billing | per counter | 1 | [YOU TOLD US] "You want billing and UPI/card payments." Catalogue: "GST-ready billing, inventory, UPI/card acceptance on a tablet." [QTY DEFAULT] 1 counter per site | 749 (599–899) | 749 | 2,500 | 12 m | 3 d |

| | Ex-tax | Tax (illustrative 18%) | Incl. tax |
|---|---|---|---|
| Monthly recurring | ₹2,197 | ₹395 | **₹2,592** |
| One-time | ₹2,500 | ₹450 | ₹2,950 |
| **First payment** | | | **₹5,542** |

Correction to the earlier draft: the core micro bundle is **₹2,197/month ex-tax (₹2,592 incl. tax)**, not "under ₹2,500" including GST. The historical micro median is ₹2,470 ex-tax.
Locked for this owner: WhatsApp Business API (P15) and Business SMS (P14) need an active GSTIN, and the card says so.

### B+. Same owner, add-ons toggled on

The owner switches these on themselves on the quote screen, so each one's reason is "[YOU TOLD US] you added this": +1 postpaid line, + Secure Wi-Fi with guest network (P22, needs fibre: satisfied by P01), + 2 Cloud CCTV cameras (P23, needs connectivity: satisfied by P01). Rule check: passes.

| | Ex-tax | Tax (illustrative 18%) | Incl. tax |
|---|---|---|---|
| Monthly recurring | ₹3,543 | ₹638 | **₹4,181** |
| One-time | ₹7,100 | ₹1,278 | ₹8,378 |
| **First payment** | | | **₹12,559** |

This shows why add-ons are toggles, not defaults, for the price-sensitive micro segment.

## C. Multi-site restaurant chain (assisted, then handed to field sales)

**Confirmed summary card:** Restaurant chain · Bengaluru (tier 1) · 40 staff · 4 sites · has GSTIN (checked: Active, mock registry) · needs stated: **billing at each outlet, CCTV, manage all outlets centrally**. Rule check: passes (SD-WAN needs ≥ 3 sites, ≥ 10 employees, an active GSTIN and a fibre/leased-line link: all met).

| ID | Product | Qty | Why (as the owner sees it) | ₹/unit/mo | Monthly | Setup/unit | One-time | Min term | Install |
|---|---|---|---|---|---|---|---|---|---|
| P02 | Biz Fibre 300 | 4 | [CATALOGUE TARGET] "Listed by Accel for multi-site businesses." [YOU TOLD US] 4 sites. On the quote, the owner can switch to Biz Fibre 100 (₹550 less per site per month; "listed for micro and professional businesses") | 1,649 | 6,596 | 0 | 0 | 12 m | 5 d |
| P09 | Backup 4G/5G Failover | 4 | [SEGMENT DEFAULT] "Most multi-outlet businesses add a backup link (57%)." Catalogue: "automatic failover … for when the main link is down." | 549 | 2,196 | 1,500 | 6,000 | 12 m | 3 d |
| P10 | Managed SD-WAN | 4 | [YOU TOLD US] "You want to manage all outlets centrally." Catalogue: "central management of links across sites" | 3,000 | 12,000 | 5,000 | 20,000 | 24 m | 14 d |
| P19 | Cloud POS & Billing | 4 | [YOU TOLD US] "Billing at each outlet." [QTY DEFAULT] 1 counter per site | 749 | 2,996 | 2,500 | 10,000 | 12 m | 3 d |
| P23 | Cloud CCTV | 8 | [YOU TOLD US] "You want CCTV." [QTY DEFAULT] 2 cameras per site; change it on the quote | 249 | 1,992 | 1,800 | 14,400 | 12 m | 4 d |
| P08 | Business Postpaid 599 | 4 | [SEGMENT DEFAULT] "Chosen by every multi-outlet business we've served." [QTY DEFAULT] 1 line per site | 699 | 2,796 | 0 | 0 | 1 m | 1 d |

| | Ex-tax | Tax (illustrative 18%) | Incl. tax |
|---|---|---|---|
| Monthly recurring | ₹28,576 | ₹5,144 | **₹33,720** |
| One-time | ₹50,400 | ₹9,072 | ₹59,472 |
| **First payment** | | | **₹93,192** |

If the owner switches to Biz Fibre 100 on all 4 sites: monthly ₹26,376 ex-tax / ₹31,124 incl. tax, first payment ₹90,596, with P01 flagged `INFO_OFF_TARGET`.

**Fibre choice history:** round 4 switched this line to P01, because 52% of activated multi-site customers bought P01 vs 48% for P02. Round 5 reverts it:
- The catalogue's `target_segments` lists P02 for multi-site and P01 only for micro and professional, and defaults must be on-target (POLICIES §6 step 0).
- The 52/48 split is **not a preference signal**: it comes from 83 multi-site customers (43 P01, 40 P02, none bought both), and the difference of 3.6 points has an approximate 95% interval of ±15 points.
- Outcomes were similar and the samples tiny: churn 9.3% for P01 buyers vs 12.5% for P02 buyers, NPS 7.05 vs 6.32. Descriptive only.

Those 43 P01 purchases are the **only** off-target product lines among all 1,651 lines in the activated bundles.

Slowest item about 14 days (SD-WAN, indicative); the pilot sets no install-speed target. The historical multi-site median is ₹28,080/month.

## Negative cases (must be refused or reworked by the engine)

| Case | Profile | Asked for | Engine result |
|---|---|---|---|
| N1 | Tier 2, 12 staff, GSTIN active | P03 Biz Fibre 1G | `EXCL_TIER` → suggests P02 300 Mbps, owner confirms |
| N2 | Tier 2, 3 staff, no GSTIN | P15 WhatsApp API + P01 | `EXCL_GSTIN_UNKNOWN` on P15 → P01 alone, with "add your GSTIN to unlock WhatsApp" |
| N3 | Tier 1, 3 staff | P23 CCTV × 2 alone | `requires_one_of` unmet → the engine proposes a connectivity product chosen by need (P01 for a 1-site shop) and asks; it doesn't silently add one |
