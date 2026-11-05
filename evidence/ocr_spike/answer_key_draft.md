# KYC answer key: draft (12 applicants, 47 images)

Expected outcomes under [POLICIES.md §9](../../docs/POLICIES.md#9-kyc-outcomes), with `business_as_of` = 2026-07-15 (demo clock).

**How each row was established:** OCR spike output (`results.json`, gated mode), then `crosscheck.md` against the mock registries. Where a finding depended on what the document really says, we looked at the image itself; those rows are marked **seen**. Every other row still needs a visual check of all four documents before this becomes the final key. Third-party findings were not used.

| Applicant | Expected applicant result | Why | Basis |
|---|---|---|---|
| K01 | `owner_action_needed` (no valid business proof); GSTIN-only lines `excluded` | GSTIN **Cancelled** in the registry; Udyam certificate has an **empty registration number** and the business isn't in the Udyam registry | Registry + **seen** (Udyam certificate) |
| K02 | `checks_passed` after the owner confirms the GSTIN | GST certificate **tilted 6.97°** → deskewed; GSTIN read as `19E0GXH…` (O read as 0) → repair `19EOGXH4115Y1ZL` matches the registry by GSTIN and name; owner confirmation required | Spike + registry |
| K03 | `checks_passed` | No findings | Spike + registry |
| K04 | `owner_action_needed` (retake) | GST certificate **too blurry** (sharpness 0.9; every other image ≥ 832); refused before OCR | Spike quality gate |
| K05 | `owner_action_needed` (add Udyam) | **Udyam certificate missing**, but the registry shows Udyam `UDYAM-KL-00-5521886` for this business → upload it or accept the registry record (DigiLocker, simulated). LLP signatory: note only | Spike + leads/registry |
| K06 | `manual_review` | Printed GSTIN `08YKZXS8189L1Z0` **fails its own check digit** (should end `I`); no registry match. OCR read it correctly | **Seen** (GST certificate) |
| K07 | `manual_review` | Legal name **altered**: "Neha Banerjee (Prop. Shri Physio Clinic)" vs the trade name on the same certificate and the registry, "Neelgiri Physio Clinic" (similarity 0.87) | **Seen** (GST certificate) |
| K08 | `checks_passed` after the owner confirms the GSTIN | GSTIN read as `24X0RXG…` (O read as 0) → repair `24XORXG9365M1Z3` matches the registry | Spike + registry |
| K09 | `checks_passed` | No findings | Spike + registry |
| K10 | `checks_passed` | No findings (LLP signatory: note only) | Spike + registry |
| K11 | `owner_action_needed` (newer bill) | Electricity bill dated **2025-10-31**, 257 days before 2026-07-15 (> 90). Pvt Ltd signatory: note only | **Seen** (bill) |
| K12 | `checks_passed` | No findings | Spike + registry |

Summary: 6 `checks_passed` (2 of them after owner-confirmed GSTIN repairs), 4 `owner_action_needed`, 2 `manual_review`.

**Rule change this produced:** the original name-similarity band "0.80–0.95: pass with a note" would have passed K07 (0.87), a false accept. POLICIES §9 now sends anything below 0.95 to `manual_review`.

**Still to do before this is the final key:** look at all 47 images (so far only K01 Udyam, K06 GST, K07 GST and K11 bill have been inspected, plus K01 GST and its other documents earlier), record every expected field value per document, and turn the key into an automated per-field and per-applicant test once the KYC pipeline exists.
