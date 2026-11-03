"""Regulatory rules as dated data, kept apart from application logic.

Each rule says WHICH threshold applies to WHICH customer type, FROM WHEN, on
WHOSE authority, and how well that has been checked. The engine picks the row
whose dates cover the assessment date. A missing row is a processing error,
never a silent default.

Verification levels:
  "primary"    - checked against the official Gazette / RBI text itself
  "secondary"  - checked against reputable law-firm summaries only
  "unverified" - not checked

As of 3 Nov 2026 every row below is "secondary". Before relying on this tool,
someone must check each row against the official notification.

Scope note: these are only the OWNERSHIP thresholds. A person can also be a
beneficial owner through control (e.g. a right to appoint most directors)
with no shareholding at all; the engine flags documented control rights for
the officer separately and never treats "below threshold" as "irrelevant".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

RULES_VERSION = "2026-11-03.1"

_SRC_2023_03 = ("PML (Maintenance of Records) Amendment Rules, 2023, notified 7 Mar 2023; "
                "RBI KYC Master Direction amended 28 Apr 2023. Checked via AZB & Partners "
                "(azbpartners.com/bank/amendment-to-pmla-rules) and AZB KYC MD note.")
_SRC_2023_09 = ("PML (Maintenance of Records) Second Amendment Rules, 2023, notified 4 Sep 2023 "
                "(partnership firms 15% -> 10%); RBI KYC MD aligned 17 Oct 2023. Checked via "
                "Cyril Amarchand Mangaldas blog and Vinod Kothari & Co.")
_SRC_OLD = "Pre-2023 PML Rule 9(3): companies >25%, partnership firms >15%, trusts >=15%. Secondary sources only."


@dataclass(frozen=True)
class Rule:
    rule_id: str
    jurisdiction: str
    customer_type: str          # company | trust | partnership
    threshold: float            # fraction; owner if stake is MORE THAN this
    valid_from: date
    valid_to: date | None       # exclusive
    source: str
    verification: str
    last_checked: date
    note: str = ""


RULES: list[Rule] = [
    Rule("IN-CO-2005", "IN", "company", 0.25, date(2005, 7, 1), date(2023, 3, 7), _SRC_OLD, "secondary", date(2026, 11, 3)),
    Rule("IN-CO-2023", "IN", "company", 0.10, date(2023, 3, 7), None, _SRC_2023_03, "secondary", date(2026, 11, 3)),
    Rule("IN-TR-2005", "IN", "trust", 0.15, date(2005, 7, 1), date(2023, 3, 7), _SRC_OLD, "secondary", date(2026, 11, 3),
         "Old trust test was 15% or more; modelled here as 'more than' 15%. Trust-specific roles (settlor, trustee, beneficiary) are NOT modelled."),
    Rule("IN-TR-2023", "IN", "trust", 0.10, date(2023, 3, 7), None, _SRC_2023_03, "secondary", date(2026, 11, 3),
         "Trust-specific roles (settlor, trustee, beneficiary) are NOT modelled."),
    Rule("IN-PF-2005", "IN", "partnership", 0.15, date(2005, 7, 1), date(2023, 9, 4), _SRC_OLD, "secondary", date(2026, 11, 3)),
    Rule("IN-PF-2023", "IN", "partnership", 0.10, date(2023, 9, 4), None, _SRC_2023_09, "secondary", date(2026, 11, 3),
         "Corrected 3 Nov 2026: the previous version used RBI's 17 Oct 2023 alignment date instead of the PML Rules date."),
]

# Customer types without a rule of their own, and the rule family used instead.
# This is an INTERPRETATION, shown in every report that relies on it.
TYPE_MAP = {"llp": ("partnership", "LLP assessed under the partnership-firm test (interpretation, not confirmed).")}

TERMINAL_TYPES = {"person", "listed"}   # the trail stops at these
NEAR_MISS_FRACTION = 0.8                # stakes from 80% of the threshold up to it are flagged


class RuleMissing(Exception):
    pass


def rule_for(customer_type: str, on: date, jurisdiction: str = "IN") -> tuple[Rule, str]:
    """Return the rule in force on `on` and any interpretation note used to pick it."""
    family, note = TYPE_MAP.get(customer_type, (customer_type, ""))
    for r in RULES:
        if r.jurisdiction == jurisdiction and r.customer_type == family and r.valid_from <= on and (r.valid_to is None or on < r.valid_to):
            return r, note
    raise RuleMissing(f"No {jurisdiction} rule for customer type '{customer_type}' on {on.isoformat()}")


def threshold_for(customer_type: str, on: date) -> tuple[float, str]:
    """Backwards-compatible wrapper used by older code."""
    r, _ = rule_for(customer_type, on)
    return r.threshold, f"rule {r.rule_id} valid from {r.valid_from.isoformat()}"
