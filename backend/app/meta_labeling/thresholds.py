"""
Decision-threshold analysis.

Acceptance rule (documented boundary): an observation is **accepted** when
``calibrated_probability >= threshold`` (greater-or-equal — a probability
exactly at the threshold is accepted).  An optional abstention band rejects
observations whose probability falls strictly inside ``(lower, upper)`` before
thresholding; ``lower > upper`` is invalid.

Grid rules: thresholds in [0, 1], deduplicated, stably sorted ascending,
bounded at 101 points.  Nothing is ever selected as a "best" threshold and no
financial recommendation is produced — the table reports neutral counts and
rates, with coverage prominent and undefined values null (never Infinity).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

MAX_THRESHOLDS = 101


class ThresholdError(ValueError):
    """Invalid threshold-grid or abstention configuration (HTTP 422)."""


def build_grid(config: Optional[Dict[str, Any]]) -> List[float]:
    """Build the threshold grid from {start, end, step} (defaults 0→1 by 0.05)."""
    config = config or {}
    start = config.get("start", 0.0)
    end = config.get("end", 1.0)
    step = config.get("step", 0.05)
    for name, v in (("start", start), ("end", end), ("step", step)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ThresholdError(f"threshold grid {name} must be a finite number")
    start, end, step = float(start), float(end), float(step)
    if not (0.0 <= start <= 1.0 and 0.0 <= end <= 1.0):
        raise ThresholdError("threshold grid bounds must be within [0, 1]")
    if end < start:
        raise ThresholdError("threshold grid end must not be below start")
    if step <= 0:
        raise ThresholdError("threshold grid step must be positive")
    count = int(round((end - start) / step)) + 1
    if count > MAX_THRESHOLDS:
        raise ThresholdError(
            f"threshold grid would contain {count} points (limit {MAX_THRESHOLDS}); "
            "increase the step"
        )
    grid = sorted({round(start + i * step, 10) for i in range(count) if start + i * step <= 1.0 + 1e-12})
    return [min(t, 1.0) for t in grid]


def validate_abstention(band: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    if not band:
        return None
    lower = band.get("lower")
    upper = band.get("upper")
    for name, v in (("lower", lower), ("upper", upper)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
            raise ThresholdError(f"abstention {name} must be a finite number")
        if not (0.0 <= float(v) <= 1.0):
            raise ThresholdError(f"abstention {name} must be within [0, 1]")
    if float(lower) > float(upper):
        raise ThresholdError("abstention lower bound must not exceed the upper bound")
    return {"lower": float(lower), "upper": float(upper)}


def _rate(num: int, den: int) -> Optional[float]:
    return round(num / den, 6) if den > 0 else None


def analyze_threshold(
    probs: Sequence[float],
    labels: Sequence[int],
    outcomes: Sequence[Optional[float]],
    threshold: float,
    abstention: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Confusion + coverage stats at one threshold (accept iff p >= threshold)."""
    total = len(probs)
    accepted_idx: List[int] = []
    band_abstained = 0
    for i, p in enumerate(probs):
        if abstention and abstention["lower"] < p < abstention["upper"]:
            band_abstained += 1
            continue
        if p >= threshold:
            accepted_idx.append(i)
    accepted = len(accepted_idx)
    rejected = total - accepted

    tp = sum(1 for i in accepted_idx if labels[i] == 1)
    fp = accepted - tp
    fn = sum(1 for i in range(total) if labels[i] == 1) - tp
    tn = rejected - fn

    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    specificity = _rate(tn, tn + fp)
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = round(2 * precision * recall / (precision + recall), 6)
    balanced = None
    if recall is not None and specificity is not None:
        balanced = round((recall + specificity) / 2, 6)

    row: Dict[str, Any] = {
        "threshold": round(threshold, 6),
        "accepted": accepted,
        "rejected": rejected,
        "band_abstained": band_abstained,
        "coverage": _rate(accepted, total),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "balanced_accuracy": balanced,
        "accepted_positive_rate": _rate(tp, accepted),
    }
    accepted_outcomes = [
        outcomes[i] for i in accepted_idx if outcomes[i] is not None
    ]
    if accepted_outcomes:
        mean_o = sum(accepted_outcomes) / len(accepted_outcomes)
        row["accepted_outcome_mean"] = round(mean_o, 6)
        row["accepted_outcome_sum"] = round(sum(accepted_outcomes), 6)
    else:
        row["accepted_outcome_mean"] = None
        row["accepted_outcome_sum"] = None
    return row


def threshold_table(
    probs: Sequence[float],
    labels: Sequence[int],
    outcomes: Sequence[Optional[float]],
    *,
    grid_config: Optional[Dict[str, Any]] = None,
    abstention: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    grid = build_grid(grid_config)
    band = validate_abstention(abstention)
    rows = [analyze_threshold(probs, labels, outcomes, t, band) for t in grid]
    return {"thresholds": rows, "abstention": band, "grid_size": len(grid)}


__all__ = [
    "MAX_THRESHOLDS", "ThresholdError", "build_grid", "validate_abstention",
    "analyze_threshold", "threshold_table",
]
