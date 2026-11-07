"""Cross-document and registry checks on the OCR spike output (gated mode).

Produces a draft per-applicant finding list to build the hand-checked KYC
answer key from. Output: evidence/ocr_spike/crosscheck.md
"""

from __future__ import annotations

import csv
import json

import sys
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.kyc.text import clean_value, iso_date as parse_date, norm_name, pincode  # noqa: E402
from app.registry.identifiers import gstin_repair_candidates, validate_gstin, validate_udyam  # noqa: E402

AS_OF = date(2026, 7, 15)  # data pack "today"


def sim(a: str, b: str) -> float:
    a, b = norm_name(a), norm_name(b)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def main() -> None:
    results = json.loads((REPO / "evidence" / "ocr_spike" / "results.json").read_text(encoding="utf-8"))
    gst_reg = {r["gstin"]: r for r in csv.DictReader((REPO / "data/raw/mock_gstin_registry.csv").open(encoding="utf-8"))}
    udy_reg = {r["udyam_number"]: r for r in csv.DictReader((REPO / "data/raw/mock_udyam_registry.csv").open(encoding="utf-8"))}
    by_app: dict[str, dict] = defaultdict(dict)
    for r in results:
        if r["mode"] == "gated":
            r["fields"] = {k: clean_value(v) for k, v in r["fields"].items()}
            by_app[r["applicant"]][r["type"]] = r

    out = ["# KYC cross-check draft (gated OCR mode)", "",
           f"Rules applied as specified in POLICIES.md §9, with business_as_of = {AS_OF}. "
           "Name similarity ignores spacing and Pvt/Ltd/LLP/Prop. suffixes. "
           "This is a draft for the hand-built answer key, not a verdict.", ""]
    for app in sorted(by_app):
        docs = by_app[app]
        notes: list[str] = []
        gst = docs.get("gst_certificate")
        udy = docs.get("udyam_certificate")
        bill = docs.get("address_proof")
        sid = docs.get("signatory_id")
        for kind in ("gst_certificate", "udyam_certificate", "address_proof", "signatory_id"):
            if kind not in docs:
                notes.append(f"MISSING DOCUMENT: {kind}")
        reg_g = None
        if gst:
            if gst["quality"].get("refused"):
                notes.append(f"GST certificate refused by quality gate: {gst['quality']}")
            else:
                if gst["quality"].get("deskewed"):
                    notes.append(f"GST certificate deskewed by {gst['quality']['skew']} degrees")
                g = gst["fields"].get("GSTIN", "")
                v = validate_gstin(g)
                if v.ok:
                    reg_g = gst_reg.get(v.value)
                else:
                    cands = [c for c in gstin_repair_candidates(g) if c in gst_reg]
                    if cands:
                        notes.append(f"GSTIN OCR repair proposed {g} -> {cands[0]} (owner must confirm)")
                        reg_g = gst_reg[cands[0]]
                    else:
                        notes.append(f"GSTIN {g!r} fails format: {v.problems}; no registry match")
                if reg_g:
                    if reg_g["status"] != "Active":
                        notes.append(f"GSTIN status in registry: {reg_g['status']}")
                    for f_doc, f_reg in (("Legal name", "legal_name"), ("Trade name", "trade_name")):
                        s = sim(gst["fields"].get(f_doc, ""), reg_g[f_reg])
                        if s < 0.95:
                            notes.append(f"GST {f_doc} {gst['fields'].get(f_doc)!r} vs registry {reg_g[f_reg]!r} (sim {s:.2f})")
                    if pincode(gst["fields"].get("Address of principal", "")) != pincode(reg_g["principal_place_of_business"]):
                        notes.append("GST address pincode differs from registry")
        if udy:
            u = udy["fields"].get("Udyam reg. number", "")
            vu = validate_udyam(u) if u else None
            if not u:
                notes.append("Udyam certificate has no registration number")
            elif not vu.ok:
                notes.append(f"Udyam number {u!r} fails format")
            elif vu.value not in udy_reg:
                notes.append(f"Udyam number {vu.value} not in registry")
            else:
                ru = udy_reg[vu.value]
                s = sim(udy["fields"].get("Enterprise name", ""), ru["enterprise_name"])
                if s < 0.95:
                    notes.append(f"Udyam name {udy['fields'].get('Enterprise name')!r} vs registry {ru['enterprise_name']!r} (sim {s:.2f})")
            if reg_g:
                s = sim(udy["fields"].get("Enterprise name", ""), reg_g["trade_name"])
                if s < 0.95:
                    notes.append(f"Udyam name vs GST trade name (sim {s:.2f})")
        if bill:
            d = parse_date(bill["fields"].get("Bill date", ""))
            if d is None:
                notes.append("Bill date not read")
            elif (AS_OF - d).days > 90:
                notes.append(f"Address proof dated {d}, {(AS_OF - d).days} days before {AS_OF} (> 90)")
            if reg_g:
                s = sim(bill["fields"].get("Billed to", ""), reg_g["trade_name"])
                if s < 0.95:
                    notes.append(f"Bill 'Billed to' {bill['fields'].get('Billed to')!r} vs trade name (sim {s:.2f})")
                if pincode(bill["fields"].get("Supply address", "")) != pincode(reg_g["principal_place_of_business"]):
                    notes.append(f"Bill pincode {pincode(bill['fields'].get('Supply address', ''))} vs GST {pincode(reg_g['principal_place_of_business'])}")
        if sid:
            vt = parse_date(sid["fields"].get("Valid till", ""))
            if vt is None:
                notes.append("Signatory ID validity not read")
            elif vt < AS_OF:
                notes.append(f"Signatory ID expired {vt}")
            if reg_g:
                s_b = sim(sid["fields"].get("For business", ""), reg_g["trade_name"])
                if s_b < 0.95:
                    notes.append(f"ID 'For business' {sid['fields'].get('For business')!r} vs trade name (sim {s_b:.2f})")
                legal = reg_g["legal_name"]
                person = legal.split(" (Prop.")[0] if "(Prop." in legal else None
                if person and sim(sid["fields"].get("Name", ""), person) < 0.95:
                    notes.append(f"ID name {sid['fields'].get('Name')!r} vs proprietor {person!r}")
                if not person:
                    notes.append(f"NOTE ONLY: {reg_g['constitution']}; the registry has no partner/director names, "
                                 f"so signatory {sid['fields'].get('Name')!r} ({sid['fields'].get('Designation')}) is not checkable")
        out.append(f"## {app}")
        out += [f"- {n}" for n in notes] or ["- no findings"]
        out.append("")
    (REPO / "evidence" / "ocr_spike" / "crosscheck.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
