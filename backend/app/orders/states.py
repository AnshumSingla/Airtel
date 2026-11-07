"""Order and line-item state machines (POLICIES.md §10). [SIMULATED fulfilment]

Only the transitions listed here are allowed; anything else raises
IllegalTransition. Each allowed transition names who may trigger it.
"""

from __future__ import annotations

ORDER_STATES = {"ACCEPTED", "KYC_PENDING", "KYC_OK", "IN_FULFILMENT", "COMPLETED", "ON_HOLD", "CANCELLED"}
HOLD_REASONS = {"KYC_ACTION", "KYC_REVIEW", "BUNDLE_CHANGE_NEEDED", "CONSENT_WITHDRAWN", "FEASIBILITY_DECISION"}
LINE_STATES = {"PENDING", "FEASIBILITY_CHECK", "SCHEDULED", "RESCHEDULED", "INSTALLING", "ACTIVE",
               "EXCLUDED", "FEASIBILITY_FAILED", "INSTALL_FAILED", "CANCELLED"}

# (from, to) -> allowed actors
ORDER_TRANSITIONS: dict[tuple[str, str], set[str]] = {
    ("ACCEPTED", "KYC_PENDING"): {"owner"},
    ("KYC_PENDING", "KYC_OK"): {"system", "kyc_reviewer"},
    ("KYC_PENDING", "ON_HOLD"): {"system"},
    ("ON_HOLD", "KYC_PENDING"): {"owner"},            # documents fixed and resubmitted
    ("ON_HOLD", "KYC_OK"): {"owner", "kyc_reviewer"},  # bundle changed (KYC reused) or reviewer approved
    ("ON_HOLD", "IN_FULFILMENT"): {"owner", "system"},  # feasibility decision made
    ("KYC_OK", "IN_FULFILMENT"): {"system"},
    ("IN_FULFILMENT", "ON_HOLD"): {"system"},         # feasibility failed on a line
    ("IN_FULFILMENT", "COMPLETED"): {"system"},
    ("ACCEPTED", "CANCELLED"): {"owner", "ops"},
    ("KYC_PENDING", "CANCELLED"): {"owner", "ops"},
    ("KYC_OK", "CANCELLED"): {"owner", "ops"},
    ("ON_HOLD", "CANCELLED"): {"owner", "ops", "system"},
    ("IN_FULFILMENT", "CANCELLED"): {"owner", "ops"},
}

LINE_TRANSITIONS: dict[tuple[str, str], set[str]] = {
    ("PENDING", "FEASIBILITY_CHECK"): {"system"},
    ("PENDING", "ACTIVE"): {"system"},                 # no site install needed (mobile lines, cloud services)
    ("PENDING", "EXCLUDED"): {"system"},
    ("PENDING", "SCHEDULED"): {"system"},              # site visit without a feasibility check (POS, CCTV, ...)
    ("FEASIBILITY_CHECK", "SCHEDULED"): {"system", "ops"},
    ("FEASIBILITY_CHECK", "FEASIBILITY_FAILED"): {"system"},
    ("SCHEDULED", "RESCHEDULED"): {"owner", "ops"},
    ("RESCHEDULED", "SCHEDULED"): {"system", "ops"},
    ("SCHEDULED", "INSTALLING"): {"ops", "system"},
    ("INSTALLING", "ACTIVE"): {"ops", "system"},
    ("INSTALLING", "INSTALL_FAILED"): {"ops", "system"},
    ("INSTALL_FAILED", "SCHEDULED"): {"ops", "system"},
    **{(s, "CANCELLED"): {"owner", "ops", "system"}
       for s in ("PENDING", "FEASIBILITY_CHECK", "SCHEDULED", "RESCHEDULED", "FEASIBILITY_FAILED", "INSTALL_FAILED")},
}

TERMINAL_LINE = {"ACTIVE", "EXCLUDED", "CANCELLED"}


class IllegalTransition(ValueError):
    pass


def check_order(frm: str, to: str, actor: str) -> None:
    allowed = ORDER_TRANSITIONS.get((frm, to))
    if allowed is None:
        raise IllegalTransition(f"order {frm} -> {to} is not allowed")
    if actor not in allowed:
        raise IllegalTransition(f"order {frm} -> {to} can't be triggered by {actor}")


def check_line(frm: str, to: str, actor: str) -> None:
    allowed = LINE_TRANSITIONS.get((frm, to))
    if allowed is None:
        raise IllegalTransition(f"line {frm} -> {to} is not allowed")
    if actor not in allowed:
        raise IllegalTransition(f"line {frm} -> {to} can't be triggered by {actor}")
