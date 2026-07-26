"""
Probability calibration (dependency-light — scikit-learn is not a project
dependency, so both methods are small deterministic implementations) and
probability-quality metrics.

Methods:

* ``none``     — calibrated == raw.
* ``sigmoid``  — Platt scaling: fit ``p' = 1 / (1 + exp(A·z + B))`` on the
  calibration set where ``z = logit(raw)``, via Newton–Raphson on the
  regularized log-loss (Platt's target smoothing), fixed 100-iteration cap,
  deterministic.  Stored parameters: the two floats A and B (no model files).
* ``isotonic`` — isotonic regression via the pool-adjacent-violators (PAV)
  algorithm on (raw, label) pairs; prediction is stepwise-constant with linear
  interpolation between block centers, clamped to [eps, 1-eps].  Stored
  parameters: the block boundary arrays (plain floats).

Rules: calibrators fit on the training subset only; minimum-sample and
class-diversity requirements enforced (one-class data → unavailable);
probabilities clipped only by the documented epsilon ``EPS = 1e-6``; raw and
calibrated probabilities are both preserved; no pickle/joblib anywhere.

Metrics: Brier score, log loss, rank-based ROC AUC, average precision (PR
AUC), reliability bins (equal-width or equal-frequency), ECE
(sample-count-weighted mean absolute gap) and MCE (maximum absolute gap over
non-empty bins).  Undefined metrics return None plus an explanation — never
zero-substitution, NaN, or Infinity.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

EPS = 1e-6
MIN_CALIBRATION_SAMPLES = 8
MAX_BINS = 30
CALIBRATION_METHODS = ("none", "sigmoid", "isotonic")


class CalibrationError(ValueError):
    """Calibration cannot proceed (insufficient/one-class data, bad config)."""


def _clip(p: float) -> float:
    return min(max(p, EPS), 1.0 - EPS)


def _logit(p: float) -> float:
    p = _clip(p)
    return math.log(p / (1.0 - p))


# ---------------------------------------------------------------------------
# Sigmoid (Platt) calibration
# ---------------------------------------------------------------------------


def fit_sigmoid(probs: Sequence[float], labels: Sequence[int]) -> Dict[str, float]:
    """Fit Platt scaling A, B by Newton–Raphson (deterministic, bounded)."""
    _require_fitable(probs, labels)
    z = [_logit(p) for p in probs]
    n_pos = sum(1 for y in labels if y == 1)
    n_neg = len(labels) - n_pos
    # Platt's smoothed targets guard against overfitting tiny calibration sets.
    t_pos = (n_pos + 1.0) / (n_pos + 2.0)
    t_neg = 1.0 / (n_neg + 2.0)
    t = [t_pos if y == 1 else t_neg for y in labels]

    a, b = 0.0, math.log((n_neg + 1.0) / (n_pos + 1.0))
    for _ in range(100):
        g_a = g_b = h_aa = h_ab = h_bb = 0.0
        for zi, ti in zip(z, t):
            f = a * zi + b
            p = 1.0 / (1.0 + math.exp(-f)) if f > -35 else 0.0
            d = p - ti
            w = max(p * (1.0 - p), 1e-12)
            g_a += d * zi
            g_b += d
            h_aa += w * zi * zi
            h_ab += w * zi
            h_bb += w
        h_aa += 1e-10
        h_bb += 1e-10
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-18:
            break
        da = (g_a * h_bb - g_b * h_ab) / det
        db = (g_b * h_aa - g_a * h_ab) / det
        a -= da
        b -= db
        if abs(da) < 1e-10 and abs(db) < 1e-10:
            break
    return {"a": a, "b": b}


def apply_sigmoid(params: Dict[str, float], probs: Sequence[float]) -> List[float]:
    a, b = params["a"], params["b"]
    out = []
    for p in probs:
        f = a * _logit(p) + b
        out.append(_clip(1.0 / (1.0 + math.exp(-f)) if f > -35 else 0.0))
    return out


# ---------------------------------------------------------------------------
# Isotonic calibration (PAV)
# ---------------------------------------------------------------------------


def fit_isotonic(probs: Sequence[float], labels: Sequence[int]) -> Dict[str, List[float]]:
    """Pool-adjacent-violators over (raw prob → label) pairs (deterministic)."""
    _require_fitable(probs, labels)
    pairs = sorted(zip(probs, labels), key=lambda t: (t[0], t[1]))
    # Blocks: [sum, count, x_min, x_max]
    blocks: List[List[float]] = []
    for x, y in pairs:
        blocks.append([float(y), 1.0, x, x])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] >= blocks[-1][0] / blocks[-1][1]:
            s2, c2, lo2, hi2 = blocks.pop()
            s1, c1, lo1, hi1 = blocks.pop()
            blocks.append([s1 + s2, c1 + c2, lo1, hi2])
    xs = [(b[2] + b[3]) / 2.0 for b in blocks]
    ys = [_clip(b[0] / b[1]) for b in blocks]
    return {"x": xs, "y": ys}


def apply_isotonic(params: Dict[str, List[float]], probs: Sequence[float]) -> List[float]:
    xs, ys = params["x"], params["y"]
    out = []
    for p in probs:
        if not xs:
            out.append(_clip(p))
            continue
        if p <= xs[0]:
            out.append(ys[0])
            continue
        if p >= xs[-1]:
            out.append(ys[-1])
            continue
        # Linear interpolation between adjacent block centers.
        lo, hi = 0, len(xs) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= p:
                lo = mid
            else:
                hi = mid
        span = xs[hi] - xs[lo]
        frac = (p - xs[lo]) / span if span > 0 else 0.0
        out.append(_clip(ys[lo] + frac * (ys[hi] - ys[lo])))
    return out


def _require_fitable(probs: Sequence[float], labels: Sequence[int]) -> None:
    if len(probs) < MIN_CALIBRATION_SAMPLES:
        raise CalibrationError(
            f"calibration requires at least {MIN_CALIBRATION_SAMPLES} labeled samples "
            f"(got {len(probs)})"
        )
    classes = set(labels)
    if classes != {0, 1}:
        raise CalibrationError(
            "calibration requires both classes (0 and 1) in the fitting data — "
            "one-class data is unavailable for calibration"
        )


FITTERS = {"sigmoid": fit_sigmoid, "isotonic": fit_isotonic}
APPLIERS = {"sigmoid": apply_sigmoid, "isotonic": apply_isotonic}


# ---------------------------------------------------------------------------
# Probability-quality metrics
# ---------------------------------------------------------------------------


def probability_metrics(probs: Sequence[float], labels: Sequence[int]) -> Dict[str, Any]:
    """Brier / log loss / ROC AUC / average precision, with null+reason."""
    metrics: Dict[str, Optional[float]] = {}
    reasons: Dict[str, str] = {}
    n = len(probs)
    if n == 0:
        for m in ("brier", "log_loss", "roc_auc", "pr_auc"):
            metrics[m] = None
            reasons[m] = "no labeled observations with probabilities"
        return {"metrics": metrics, "reasons": reasons,
                "positive_prevalence": None, "valid_count": 0}

    pos = sum(1 for y in labels if y == 1)
    neg = n - pos
    metrics["brier"] = round(sum((p - y) ** 2 for p, y in zip(probs, labels)) / n, 6)
    metrics["log_loss"] = round(
        -sum(y * math.log(_clip(p)) + (1 - y) * math.log(_clip(1 - p))
             for p, y in zip(probs, labels)) / n, 6)

    if pos and neg:
        ranked = sorted((p, i) for i, p in enumerate(probs))
        rank_of: Dict[int, float] = {}
        i = 0
        while i < len(ranked):
            j = i
            while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
                j += 1
            for t in range(i, j + 1):
                rank_of[ranked[t][1]] = (i + j) / 2 + 1
            i = j + 1
        pos_rank_sum = sum(rank_of[i] for i, y in enumerate(labels) if y == 1)
        metrics["roc_auc"] = round((pos_rank_sum - pos * (pos + 1) / 2) / (pos * neg), 6)
        # Average precision: sum over positives of precision at each positive,
        # scanning thresholds in descending probability (ties grouped).
        order = sorted(range(n), key=lambda i: (-probs[i], i))
        tp = fp = 0
        ap = 0.0
        k = 0
        while k < len(order):
            j = k
            group_tp = group_fp = 0
            while j < len(order) and probs[order[j]] == probs[order[k]]:
                if labels[order[j]] == 1:
                    group_tp += 1
                else:
                    group_fp += 1
                j += 1
            tp += group_tp
            fp += group_fp
            if group_tp:
                ap += group_tp * (tp / (tp + fp))
            k = j
        metrics["pr_auc"] = round(ap / pos, 6)
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
        reasons["roc_auc"] = reasons["pr_auc"] = "requires both classes among labeled observations"

    return {
        "metrics": metrics,
        "reasons": reasons,
        "positive_prevalence": round(pos / n, 6),
        "valid_count": n,
    }


def reliability_bins(
    probs: Sequence[float],
    labels: Sequence[int],
    *,
    n_bins: int = 10,
    binning: str = "equal_width",
) -> List[Dict[str, Any]]:
    """Reliability bins.  Equal-width partitions [0,1]; equal-frequency sorts
    by probability and slices into (near-)equal-count groups.  Empty bins are
    returned with count 0 and null statistics — never dropped silently."""
    if isinstance(n_bins, bool) or not isinstance(n_bins, int) or not (2 <= n_bins <= MAX_BINS):
        raise CalibrationError(f"n_bins must be an integer between 2 and {MAX_BINS}")
    if binning not in ("equal_width", "equal_frequency"):
        raise CalibrationError("binning must be 'equal_width' or 'equal_frequency'")

    bins: List[Dict[str, Any]] = []
    if binning == "equal_width":
        edges = [i / n_bins for i in range(n_bins + 1)]
        members: List[List[int]] = [[] for _ in range(n_bins)]
        for i, p in enumerate(probs):
            idx = min(int(p * n_bins), n_bins - 1)
            members[idx].append(i)
        for b in range(n_bins):
            bins.append(_bin_row(b, edges[b], edges[b + 1], members[b], probs, labels))
    else:
        order = sorted(range(len(probs)), key=lambda i: (probs[i], i))
        size, extra = divmod(len(order), n_bins)
        start = 0
        for b in range(n_bins):
            count = size + (1 if b < extra else 0)
            group = order[start:start + count]
            start += count
            lo = probs[group[0]] if group else None
            hi = probs[group[-1]] if group else None
            bins.append(_bin_row(b, lo, hi, group, probs, labels))
    return bins


def _bin_row(index, lo, hi, members, probs, labels) -> Dict[str, Any]:
    if not members:
        return {"bin_index": index, "lower_bound": lo, "upper_bound": hi,
                "sample_count": 0, "mean_probability": None,
                "observed_frequency": None, "calibration_gap": None}
    mean_p = sum(probs[i] for i in members) / len(members)
    freq = sum(1 for i in members if labels[i] == 1) / len(members)
    return {
        "bin_index": index,
        "lower_bound": None if lo is None else round(lo, 6),
        "upper_bound": None if hi is None else round(hi, 6),
        "sample_count": len(members),
        "mean_probability": round(mean_p, 6),
        "observed_frequency": round(freq, 6),
        "calibration_gap": round(abs(mean_p - freq), 6),
    }


def calibration_errors(bins: List[Dict[str, Any]], total: int) -> Dict[str, Optional[float]]:
    """ECE = Σ (bin_count / total) · |gap| over non-empty bins (count-weighted);
    MCE = max |gap| over non-empty bins.  Null when no non-empty bins."""
    filled = [b for b in bins if b["sample_count"] > 0]
    if not filled or total <= 0:
        return {"ece": None, "mce": None}
    ece = sum(b["sample_count"] / total * b["calibration_gap"] for b in filled)
    mce = max(b["calibration_gap"] for b in filled)
    return {"ece": round(ece, 6), "mce": round(mce, 6)}


__all__ = [
    "EPS", "MIN_CALIBRATION_SAMPLES", "MAX_BINS", "CALIBRATION_METHODS",
    "CalibrationError", "fit_sigmoid", "apply_sigmoid", "fit_isotonic",
    "apply_isotonic", "FITTERS", "APPLIERS", "probability_metrics",
    "reliability_bins", "calibration_errors",
]
