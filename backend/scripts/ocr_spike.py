"""Day-1 OCR spike (DECISIONS.md D8): RapidOCR on all 47 KYC specimen images.

Runs two modes per image, ``raw`` and ``red`` (red channel only, which washes
out the red watermark), parses label/value fields per document type, checks
identifiers against the mock registries, and writes:

    evidence/ocr_spike/results.json   every field, per image and mode
    evidence/ocr_spike/report.md      summary tables

This is a measurement, not the production KYC pipeline. Usage (from backend/):

    .venv/Scripts/python scripts/ocr_spike.py [--modes red,raw]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.kyc.text import clean_value  # noqa: E402
from app.registry.identifiers import validate_gstin, validate_udyam  # noqa: E402

DOCS = REPO / "data" / "raw" / "kyc_documents"
OUT = REPO / "evidence" / "ocr_spike"

# Labels per document type, as printed on the specimens.
A4_LABELS = {
    "gst_certificate": ["GSTIN", "Legal name", "Trade name", "Constitution",
                        "Address of principal", "Date of liability", "Type of registration"],
    "udyam_certificate": ["Udyam reg. number", "Enterprise name", "Major activity", "City", "State",
                          "Date of registration"],
    "address_proof": ["Consumer no.", "Billed to", "Supply address", "Bill date", "Units consumed",
                      "Amount due (INR)"],
}
CARD_LABELS = ["Name", "Designation", "For business", "ID no.", "Valid till"]
LABEL_CONTINUATIONS = {"place of business"}  # second line of "Address of principal"
WATERMARK = "SYNTHETICSPECIMENNOTAVALIDDOCUMENT"
VALUE_X = 480  # value column starts around x=515 on the 1240 px A4 specimens


def squash(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", s).upper()


def is_noise(text: str) -> bool:
    t = squash(text)
    if not t:
        return True
    if "SPECIMEN" in t or t.startswith("ACCELYTL") or t.startswith("FORMATFOR") or t.startswith("FICTIONAL"):
        return True
    # Short all-caps fragments of the diagonal watermark ("CUM", "NOTA", "DOCUM").
    return len(t) <= 12 and t.isalpha() and t.isupper() and t in WATERMARK


BLUR_MIN_SHARPNESS = 100.0  # variance of Laplacian; specimens score >= 832, K04's GST certificate 0.9
SKEW_MIN_DEGREES = 0.5


def sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def skew_degrees(gray: np.ndarray) -> float:
    """Median angle of long near-horizontal lines (table rules, borders)."""
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 1800, 200, minLineLength=gray.shape[1] // 3, maxLineGap=10)
    if lines is None:
        return 0.0
    angles = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4)]
    angles = [a for a in angles if abs(a) < 20]
    return float(np.median(angles)) if angles else 0.0


def rotate(gray: np.ndarray, degrees: float) -> np.ndarray:
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)


def preprocess(img: np.ndarray, mode: str) -> tuple[np.ndarray | None, dict]:
    """Returns (image for OCR, quality info). None means the quality gate refused it."""
    if mode == "raw":
        return img, {}
    red = img[:, :, 2]
    if mode == "red":
        return cv2.cvtColor(red, cv2.COLOR_GRAY2BGR), {}
    if mode == "gated":
        info = {"sharpness": round(sharpness(red), 1), "skew": round(skew_degrees(red), 2)}
        if info["sharpness"] < BLUR_MIN_SHARPNESS:
            info["refused"] = "TOO_BLURRY"
            return None, info
        if abs(info["skew"]) > SKEW_MIN_DEGREES:
            red = rotate(red, info["skew"])
            info["deskewed"] = True
        return cv2.cvtColor(red, cv2.COLOR_GRAY2BGR), info
    raise ValueError(mode)


def label_match(text: str, labels: list[str]) -> str | None:
    t = squash(text)
    for lab in labels:
        if t == squash(lab):
            return lab
    return None


def join_lines(parts: list[str]) -> str:
    out = ""
    for p in parts:
        p = p.strip()
        if not out:
            out = p
        elif p[:1].islower() and out[-1:].isalpha():
            out += p  # a word split across lines: "...Visakhapatnam, A" + "ndhra Pradesh"
        else:
            out += " " + p
    return out


def parse_a4(boxes: list[tuple[float, float, str]], labels: list[str]) -> dict[str, str]:
    lab_rows = []  # (y, label)
    values = []  # (y, x, text)
    for x, y, text in boxes:
        lab = label_match(text, labels) if x < VALUE_X else None
        if lab:
            lab_rows.append((y, lab))
        elif x < VALUE_X and squash(text) in {squash(c) for c in LABEL_CONTINUATIONS}:
            continue
        elif x >= VALUE_X:
            values.append((y, x, text))
    lab_rows.sort()
    fields: dict[str, list[tuple[float, str]]] = {lab: [] for _, lab in lab_rows}
    for y, _x, text in sorted(values):
        owner = None
        for ly, lab in lab_rows:
            if ly - 25 <= y:
                owner = lab
        if owner:
            fields[owner].append((y, text))
    return {lab: clean_value(join_lines([t for _, t in sorted(v)])) for lab, v in fields.items()}


def parse_card(boxes: list[tuple[float, float, str]]) -> dict[str, str]:
    labs = []
    others = []
    for x, y, text in boxes:
        lab = label_match(text, CARD_LABELS)
        (labs if lab else others).append((x, y, lab or text))
    fields = {}
    for lx, ly, lab in labs:
        below = [(y, t) for x, y, t in others if abs(x - lx) < 40 and 10 < y - ly < 60]
        if below:
            fields[lab] = clean_value(sorted(below)[0][1])
    return fields


def doc_type(path: Path) -> str:
    return path.stem.split("_", 1)[1]


def load_registries():
    def rows(name):
        with (REPO / "data" / "raw" / name).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    gst = {r["gstin"]: r for r in rows("mock_gstin_registry.csv")}
    udy = {r["udyam_number"]: r for r in rows("mock_udyam_registry.csv")}
    return gst, udy


def run(modes: list[str]) -> None:
    engine = RapidOCR()
    gst_reg, udy_reg = load_registries()
    images = sorted(DOCS.glob("K*.png"))
    results = []
    for path in images:
        img = cv2.imread(str(path))
        kind = doc_type(path)
        for mode in modes:
            t0 = time.perf_counter()
            prepared, quality = preprocess(img, mode)
            res = engine(prepared)[0] if prepared is not None else []
            seconds = time.perf_counter() - t0
            boxes = [(float(b[0][0]), float(b[0][1]), t) for b, t, _s in (res or []) if not is_noise(t)]
            fields = parse_card(boxes) if kind == "signatory_id" else parse_a4(boxes, A4_LABELS[kind])
            check = {}
            if kind == "gst_certificate":
                g = fields.get("GSTIN", "")
                v = validate_gstin(g) if g else None
                check = {"gstin_read": bool(g), "gstin_valid": bool(v and v.ok),
                         "in_registry": bool(v and v.value in gst_reg),
                         "registry_status": gst_reg.get(v.value, {}).get("status") if v else None}
            elif kind == "udyam_certificate":
                u = fields.get("Udyam reg. number", "")
                v = validate_udyam(u) if u else None
                check = {"udyam_read": bool(u), "udyam_valid": bool(v and v.ok),
                         "in_registry": bool(v and v.value in udy_reg)}
            if kind == "gst_certificate" and check.get("gstin_read") and not check.get("gstin_valid"):
                from app.registry.identifiers import gstin_repair_candidates
                check["repair_candidates"] = gstin_repair_candidates(fields["GSTIN"])
                check["repair_in_registry"] = [c for c in check["repair_candidates"] if c in gst_reg]
            results.append({"image": path.name, "applicant": path.stem[:3], "type": kind, "mode": mode,
                            "seconds": round(seconds, 2), "quality": quality, "fields": fields, "check": check})
            print(f"{path.name:32} {mode:4} {seconds:5.2f}s fields={len(fields)}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(results, modes)


def write_report(results: list[dict], modes: list[str]) -> None:
    expected = {k: len(v) for k, v in A4_LABELS.items()} | {"signatory_id": len(CARD_LABELS)}
    lines = ["# OCR spike report (RapidOCR, CPU)", "",
             "Generated by `backend/scripts/ocr_spike.py`. Field values are raw OCR output, "
             "not yet checked against a hand-built answer key.", ""]
    lines += ["## Field coverage by mode", "", "| Mode | Images | Fields found / expected | Mean s per image | GSTINs read and valid | Udyam numbers read and valid |",
              "|---|---|---|---|---|---|"]
    for mode in modes:
        rs = [r for r in results if r["mode"] == mode]
        found = sum(len([v for v in r["fields"].values() if v]) for r in rs)
        exp = sum(expected[r["type"]] for r in rs)
        g = [r for r in rs if r["type"] == "gst_certificate"]
        u = [r for r in rs if r["type"] == "udyam_certificate"]
        lines.append(f"| {mode} | {len(rs)} | {found} / {exp} | {sum(r['seconds'] for r in rs) / len(rs):.2f} | "
                     f"{sum(r['check']['gstin_valid'] for r in g)} / {len(g)} | "
                     f"{sum(r['check']['udyam_valid'] for r in u)} / {len(u)} |")
    best = modes[0]
    lines += ["", f"## Extracted fields ({best} mode)", ""]
    for r in [r for r in results if r["mode"] == best]:
        lines.append(f"### {r['image']}")
        lines += [f"- **{k}**: {v}" for k, v in r["fields"].items()]
        missing = expected[r["type"]] - len([v for v in r["fields"].values() if v])
        if missing:
            lines.append(f"- _missing fields: {missing}_")
        if r.get("quality"):
            lines.append(f"- quality: `{json.dumps(r['quality'])}`")
        if r["check"]:
            lines.append(f"- check: `{json.dumps(r['check'])}`")
        lines.append("")
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="red,raw")
    run(ap.parse_args().modes.split(","))
