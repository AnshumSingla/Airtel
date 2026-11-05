# KYC pipeline vs answer key

Commit `b6c2275` (working tree may differ). Production pipeline (`app.kyc`): bytes in memory -> quality gate -> deskew -> RapidOCR -> field extraction -> checks. Local run, not CI.

**Result: PASS**. 47 images, mean 4.2 s per image.

| Applicant | Expected | Got | After owner confirms GSTIN | Findings | Match |
|---|---|---|---|---|---|
| K01 | `owner_action_needed` | `owner_action_needed` |  | GSTIN_INACTIVE, UDYAM_NUMBER_MISSING, NO_VALID_BUSINESS_PROOF | yes |
| K02 | `owner_action_needed` | `owner_action_needed` | `checks_passed` | GSTIN_CONFIRM_READING | yes |
| K03 | `checks_passed` | `checks_passed` |  | none | yes |
| K04 | `owner_action_needed` | `owner_action_needed` |  | DOC_TOO_BLURRY | yes |
| K05 | `owner_action_needed` | `owner_action_needed` |  | UDYAM_REGISTERED_NOT_UPLOADED, SIGNATORY_NOT_CHECKABLE | yes |
| K06 | `manual_review` | `manual_review` |  | GSTIN_PRINTED_INVALID | yes |
| K07 | `manual_review` | `manual_review` |  | GST_NAME_MISMATCH | yes |
| K08 | `owner_action_needed` | `owner_action_needed` | `checks_passed` | GSTIN_CONFIRM_READING | yes |
| K09 | `checks_passed` | `checks_passed` |  | none | yes |
| K10 | `checks_passed` | `checks_passed` |  | SIGNATORY_NOT_CHECKABLE | yes |
| K11 | `owner_action_needed` | `owner_action_needed` |  | ADDRESS_PROOF_STALE, SIGNATORY_NOT_CHECKABLE | yes |
| K12 | `checks_passed` | `checks_passed` |  | none | yes |

False accepts: 0 
