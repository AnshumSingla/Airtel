# KYC cross-check draft (gated OCR mode)

Rules applied as specified in POLICIES.md §9, with business_as_of = 2026-07-15. Name similarity ignores spacing and Pvt/Ltd/LLP/Prop. suffixes. This is a draft for the hand-built answer key, not a verdict.

## K01
- GSTIN status in registry: Cancelled
- Udyam certificate has no registration number

## K02
- GST certificate deskewed by 6.97 degrees
- GSTIN OCR repair proposed 19E0GXH4115Y1ZL -> 19EOGXH4115Y1ZL (owner must confirm)

## K03
- no findings

## K04
- GST certificate refused by quality gate: {'sharpness': 0.9, 'skew': 0.0, 'refused': 'TOO_BLURRY'}

## K05
- MISSING DOCUMENT: udyam_certificate
- NOTE ONLY: Limited Liability Partnership; the registry has no partner/director names, so signatory 'AnitaShah' (Owner) is not checkable

## K06
- GSTIN '08YKZXS8189L1Z0' fails format: ('CHECK_DIGIT',); no registry match

## K07
- GST Legal name 'Neha Banerjee (Prop. Shri Physio Clinic)' vs registry 'Neha Banerjee (Prop. Neelgiri Physio Clinic)' (sim 0.87)

## K08
- GSTIN OCR repair proposed 24X0RXG9365M1Z3 -> 24XORXG9365M1Z3 (owner must confirm)

## K09
- no findings

## K10
- NOTE ONLY: Limited Liability Partnership; the registry has no partner/director names, so signatory 'NishaArora' (Owner) is not checkable

## K11
- Address proof dated 2025-10-31, 257 days before 2026-07-15 (> 90)
- NOTE ONLY: Private Limited Company; the registry has no partner/director names, so signatory 'VikramPillai' (Owner) is not checkable

## K12
- no findings
