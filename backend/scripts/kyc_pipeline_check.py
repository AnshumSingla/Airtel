"""Run the production KYC pipeline on all 47 specimens and compare with the answer key.

Writes evidence/kyc_pipeline/report.md. Run from backend/:
    .venv/Scripts/python scripts/kyc_pipeline_check.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from _commit import run_kind, short_commit  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.data.seed import make_engine, seed  # noqa: E402
from app.kyc.checks import evaluate  # noqa: E402
from app.kyc.pipeline import read_document  # noqa: E402
from app.kyc.registry import DbRegistry  # noqa: E402
from tests.test_kyc_checks import AFTER_CONFIRM, ANSWER_KEY  # noqa: E402

DOCS = REPO / "data" / "raw" / "kyc_documents"


def main() -> int:
    db = Path(tempfile.mkdtemp()) / "kyc.db"
    engine = make_engine(f"sqlite:///{db.as_posix()}")
    seed(engine, load_settings().data_dir)
    reg = DbRegistry(engine)
    rows, ok_all, total_s, n = [], True, 0.0, 0
    for applicant, (expected, must_have) in ANSWER_KEY.items():
        docs = {}
        for path in sorted(DOCS.glob(f"{applicant}_*.png")):
            kind = path.stem.split("_", 1)[1]
            print(f"{path.name} ...", end=" ", flush=True)
            t0 = time.perf_counter()
            docs[kind], _ = read_document(path.read_bytes(), kind)
            dt = time.perf_counter() - t0
            total_s, n = total_s + dt, n + 1
            print(f"{dt:.1f}s", flush=True)
        res = evaluate(docs, reg, date(2026, 7, 15))
        after = None
        if applicant in AFTER_CONFIRM and res.repair_proposals:
            after = evaluate(docs, reg, date(2026, 7, 15), confirmed={"gstin": res.repair_proposals[0]["candidate"]}).outcome
        match = res.outcome == expected and must_have <= set(res.codes()) and \
            (applicant not in AFTER_CONFIRM or after == AFTER_CONFIRM[applicant])
        ok_all &= match
        rows.append((applicant, expected, res.outcome, after, ", ".join(f.code for f in res.findings) or "none", match))
    commit = short_commit(REPO)
    lines = ["# KYC pipeline vs answer key", "",
             f"Commit `{commit}` (working tree may differ). Production pipeline (`app.kyc`): bytes in memory -> "
             f"quality gate -> deskew -> RapidOCR -> field extraction -> checks. **{run_kind()}**.", "",
             f"**Result: {'PASS' if ok_all else 'FAIL'}**. {n} images, mean {total_s / n:.1f} s per image.", "",
             "| Applicant | Expected | Got | After owner confirms GSTIN | Findings | Match |", "|---|---|---|---|---|---|"]
    lines += [f"| {a} | `{e}` | `{g}` | {f'`{x}`' if x else ''} | {fs} | {'yes' if m else '**NO**'} |"
              for a, e, g, x, fs, m in rows]
    false_accepts = [a for a, e, g, *_ in rows if g == "checks_passed" and e != "checks_passed"]
    lines += ["", f"False accepts: {len(false_accepts)} {false_accepts or ''}"]
    out = REPO / "evidence" / "kyc_pipeline" / "report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
