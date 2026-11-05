# OCR spike, 05 Nov 2026 (DECISIONS.md D8)

**Question:** is local OCR (RapidOCR, CPU, pip-only) good enough for the KYC specimens, and what preprocessing does it need?

**Answer: yes, with the red channel, a blur gate and deskew.** RapidOCR is adopted; the Tesseract fallback isn't needed.

| Mode | What it does | Expected fields found (of 282) | GSTINs read and valid (of 12) | Udyam numbers read and valid (of 11) | Mean / max seconds per image |
|---|---|---|---|---|---|
| raw | Image as supplied | 210 | 2 | 0 | 2.62 / 4.83 |
| red | Red channel only (washes out the red watermark) | 274 | 8 | 10 | 2.37 / 4.78 |
| gated | Red channel + blur gate (refuse if sharpness < 100) + deskew if tilt > 0.5° | 274 | 8 | 10 | 2.83 / 6.65 |

The raw mode **misses the GSTIN entirely** on K01, because the watermark runs through it.

Of the 4 GSTINs that don't read as valid in gated mode, **none is an OCR failure we can't explain**:
- K01's GSTIN is valid and Cancelled.
- K02's and K08's are O→0 confusions, resolved by owner-confirmed repair candidates that match the registry.
- K04's is refused as blurry.
- K06's printed GSTIN is itself invalid.

The 11th Udyam number (K01's) is blank on the document.

Field counts hide alignment. In red mode K02's fields were all shifted one row because of a 7° tilt; in gated mode they are aligned.

Findings that changed the design:
- **Required preprocessing:** the red channel, a blur gate (K04 scores 0.9 vs ≥ 832 for every other image) and deskew (K02 is tilted 6.97°).
- **OCR text clean-up** (`backend/app/kyc/text.py`, tested): spaces dropped or inserted ("VindhyaTours&Travels", "75 2083"), watermark pieces inside values ("NOT A VALID DOCUM 22,425", "… 348176 IOT"), suffixes glued on ("StaysLLP").
- **Name rule tightened** (POLICIES §9): the "0.80–0.95 pass with a note" band would have passed K07's altered legal name (0.87).
- **Signatories** of LLPs and companies can't be checked against the mock registry: recorded as a note, not a review.
- **Timing:** about 3 s per image on this laptop CPU, so about 12 s for a 4-document applicant. That fits the specified worker pool (20 s per document).

Files:
- `results.json`: every parsed field per image and mode (synthetic data only).
- `report.md`: generated summary and per-image fields.
- `crosscheck.md`: registry and cross-document findings per applicant (gated mode).
- `answer_key_draft.md`: expected outcomes per applicant, with what is still unverified.

Reproduce from `backend/`:

```
.venv/Scripts/python scripts/ocr_spike.py --modes gated,red,raw
.venv/Scripts/python scripts/kyc_crosscheck.py
```
