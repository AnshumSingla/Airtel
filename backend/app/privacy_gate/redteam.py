"""Run the red-team fixture set through the gate and the real payload builder.

Used by the CI test, the start-up self-test (POLICIES.md §15 stop condition)
and scripts/privacy_gate_report.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.privacy_gate.gate import PrivacyGate, slot_extraction_payload

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "privacy_redteam.json"


@dataclass
class RedTeamResult:
    per_category: dict[str, dict] = field(default_factory=dict)
    leaks: list[dict] = field(default_factory=list)            # unexpected leaks (must be empty)
    residual: list[dict] = field(default_factory=list)         # documented, accepted leaks
    benign_total: int = 0
    benign_callable: int = 0

    @property
    def passed(self) -> bool:
        return not self.leaks


def _outbound(gate: PrivacyGate, text: str) -> str:
    """The exact JSON string that would be sent, or '' if the gate refuses the call."""
    g = gate.apply(text)
    if not g.may_call:
        return ""
    return json.dumps(slot_extraction_payload(g, {}, ["segment"], "en"), ensure_ascii=False).lower()


def run_redteam(gate: PrivacyGate, fixtures: Path = FIXTURES) -> RedTeamResult:
    data = json.loads(fixtures.read_text(encoding="utf-8"))
    out = RedTeamResult()
    for cat, cases in data["categories"].items():
        stats = {"messages": len(cases), "refused": 0, "leaked_tokens": 0}
        for case in cases:
            payload = _outbound(gate, case["text"])
            if not payload:
                stats["refused"] += 1
            for secret in case["secrets"]:
                if secret.lower() in payload:
                    stats["leaked_tokens"] += 1
                    out.leaks.append({"category": cat, "text": case["text"], "leaked": secret})
        out.per_category[cat] = stats
    for case in data["known_residual"]:
        payload = _outbound(gate, case["text"])
        out.residual.append({**case, "observed": [s for s in case["leaks"] if s in payload]})
    for text in data["benign"]:
        out.benign_total += 1
        out.benign_callable += int(gate.apply(text).may_call)
    return out
