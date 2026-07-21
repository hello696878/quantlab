"""
Multiple-testing corrections (deterministic, bounded, neutral).

* **Bonferroni** — ``min(1, p · m)``; controls family-wise error rate (FWER).
* **Holm step-down** — order the m raw p-values ascending (stable on ties);
  adjusted p_(i) = max over j ≤ i of min(1, (m − j + 1) · p_(j)) — enforced
  monotone non-decreasing in the ordering; controls FWER.
* **Benjamini–Hochberg** — q_(i) = min over j ≥ i of min(1, m/j · p_(j)) —
  enforced monotone via a reverse cumulative minimum; controls the false
  discovery rate (FDR) under the stated independence/PRDS assumptions.
  BH does NOT control family-wise error.

Policy: ``m`` is the number of candidates that actually supplied a p-value
(documented); candidates without one stay ``unavailable`` and never shrink
or grow anyone else's correction.  Output preserves the original candidate
order.  Threshold states at the configured alpha are neutral —
``below_threshold`` / ``above_threshold`` / ``unavailable`` — nothing is
ever approved, validated, accepted, or rejected automatically.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

MAX_HYPOTHESES = 64
MIN_ALPHA = 0.001
MAX_ALPHA = 0.5

PROVENANCE_STATUSES = ("verified_from_supported_test", "declared", "unavailable", "invalid")


class MultipleTestingError(ValueError):
    """Invalid multiple-testing configuration (HTTP 422)."""


def validate_alpha(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value) or not (MIN_ALPHA <= float(value) <= MAX_ALPHA):
        raise MultipleTestingError(
            f"alpha must be a finite number in [{MIN_ALPHA}, {MAX_ALPHA}]"
        )
    return float(value)


def provenance_status(p_value: Optional[float], provenance: Optional[Dict[str, Any]]) -> str:
    """v1 accepts caller-supplied p-values only, so nothing is ever
    'verified_from_supported_test' — a supplied value is 'declared'."""
    if p_value is None:
        return "unavailable"
    if not (0.0 <= p_value <= 1.0) or not math.isfinite(p_value):
        return "invalid"
    return "declared"


def adjust_p_values(
    entries: Sequence[Dict[str, Any]], alpha: float
) -> List[Dict[str, Any]]:
    """entries: [{candidate_id, raw_p (float|None), provenance (dict|None)}] in
    candidate order → same order with Bonferroni/Holm/BH + neutral states."""
    if len(entries) > MAX_HYPOTHESES:
        raise MultipleTestingError(f"at most {MAX_HYPOTHESES} hypotheses are supported")
    # Only VALID p-values (finite, in [0,1]) enter the corrections: an invalid
    # value must neither inflate m nor contaminate anyone's Holm/BH value —
    # it stays 'invalid'/'unavailable' in the output.  (The API layer already
    # rejects invalid p-values at creation; this keeps the module safe alone.)
    supplied = [
        (i, float(e["raw_p"])) for i, e in enumerate(entries)
        if e["raw_p"] is not None and math.isfinite(e["raw_p"])
        and 0.0 <= float(e["raw_p"]) <= 1.0
    ]
    m = len(supplied)
    results: List[Dict[str, Any]] = []
    for e in entries:
        results.append({
            "candidate_id": e["candidate_id"],
            "raw_p_value": e["raw_p"],
            "bonferroni": None, "holm": None, "bh": None,
            "provenance_status": provenance_status(e["raw_p"], e.get("provenance")),
            "provenance": e.get("provenance"),
            "state_raw": "unavailable", "state_bonferroni": "unavailable",
            "state_holm": "unavailable", "state_bh": "unavailable",
        })
    if m == 0:
        return results

    # Stable ascending order (ties keep original candidate order).
    order = sorted(range(m), key=lambda k: (supplied[k][1], k))
    sorted_p = [supplied[order[k]][1] for k in range(m)]

    holm_sorted: List[float] = []
    running_max = 0.0
    for j, p in enumerate(sorted_p):  # j is 0-based; multiplier m - j
        value = min(1.0, (m - j) * p)
        running_max = max(running_max, value)
        holm_sorted.append(running_max)

    bh_sorted: List[float] = [0.0] * m
    running_min = 1.0
    for j in range(m - 1, -1, -1):  # reverse cumulative minimum
        value = min(1.0, m / (j + 1) * sorted_p[j])
        running_min = min(running_min, value)
        bh_sorted[j] = running_min

    for k in range(m):
        original_index = supplied[order[k]][0]
        row = results[original_index]
        p = sorted_p[k]
        row["bonferroni"] = min(1.0, p * m)
        row["holm"] = holm_sorted[k]
        row["bh"] = bh_sorted[k]
        row["state_raw"] = "below_threshold" if p < alpha else "above_threshold"
        row["state_bonferroni"] = ("below_threshold" if row["bonferroni"] < alpha
                                   else "above_threshold")
        row["state_holm"] = "below_threshold" if row["holm"] < alpha else "above_threshold"
        row["state_bh"] = "below_threshold" if row["bh"] < alpha else "above_threshold"
    return results


__all__ = [
    "MAX_HYPOTHESES", "MIN_ALPHA", "MAX_ALPHA", "PROVENANCE_STATUSES",
    "MultipleTestingError", "validate_alpha", "provenance_status",
    "adjust_p_values",
]
