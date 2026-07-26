"""
Dependency-light, neutral fold-level metrics (no scikit-learn).

Every metric is computed only when its inputs are available and mathematically
valid; otherwise it is ``None`` with an explanation in ``reasons`` — undefined
metrics are never hidden, coerced to zero, or returned as Infinity.  Nothing
here ranks models or calls anything profitable.

Classification treats labels/predictions as discrete class values (binary
metrics require exactly the classes {0, 1}); ROC AUC uses the rank-based
Mann-Whitney formulation over ``score``; log loss requires probability scores
in [0, 1].  The "sharpe_like" return statistic is a simplified research
statistic (mean/std of the supplied per-sample returns), not an annualized or
cost-aware Sharpe ratio.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

Sample = Dict[str, Any]

_EPS = 1e-12


def _collect(samples: Sequence[Sample], positions: Sequence[int], field: str) -> List[float]:
    return [samples[p][field] for p in positions if samples[p][field] is not None]


def _pairs(samples: Sequence[Sample], positions: Sequence[int], a: str, b: str):
    return [
        (samples[p][a], samples[p][b])
        for p in positions
        if samples[p][a] is not None and samples[p][b] is not None
    ]


def split_metrics(samples: Sequence[Sample], test_pos: Sequence[int]) -> Dict[str, Any]:
    """Compute the metric block for one split's test samples."""
    metrics: Dict[str, Optional[float]] = {}
    reasons: Dict[str, str] = {}

    lp = _pairs(samples, test_pos, "label", "prediction")
    labels = [a for a, _ in lp]
    preds = [b for _, b in lp]
    classes = sorted({*labels, *preds}) if lp else []
    is_classlike = bool(lp) and all(float(v).is_integer() for v in labels + preds)
    is_binary = is_classlike and set(int(v) for v in labels) <= {0, 1} and set(
        int(v) for v in preds
    ) <= {0, 1}

    # -- classification ------------------------------------------------------
    if not lp:
        for m in ("accuracy", "balanced_accuracy", "precision", "recall", "f1"):
            metrics[m] = None
            reasons[m] = "requires labels and predictions on test samples"
    elif not is_classlike:
        for m in ("accuracy", "balanced_accuracy", "precision", "recall", "f1"):
            metrics[m] = None
            reasons[m] = "labels/predictions are not discrete classes"
    else:
        correct = sum(1 for a, b in lp if int(a) == int(b))
        metrics["accuracy"] = round(correct / len(lp), 6)
        recalls = []
        for c in sorted(set(int(v) for v in labels)):
            cls = [(a, b) for a, b in lp if int(a) == c]
            recalls.append(sum(1 for a, b in cls if int(a) == int(b)) / len(cls))
        metrics["balanced_accuracy"] = round(sum(recalls) / len(recalls), 6)
        if is_binary:
            tp = sum(1 for a, b in lp if int(a) == 1 and int(b) == 1)
            fp = sum(1 for a, b in lp if int(a) == 0 and int(b) == 1)
            fn = sum(1 for a, b in lp if int(a) == 1 and int(b) == 0)
            if tp + fp > 0:
                metrics["precision"] = round(tp / (tp + fp), 6)
            else:
                metrics["precision"] = None
                reasons["precision"] = "no positive predictions in this fold"
            if tp + fn > 0:
                metrics["recall"] = round(tp / (tp + fn), 6)
            else:
                metrics["recall"] = None
                reasons["recall"] = "no positive labels in this fold"
            p, r = metrics.get("precision"), metrics.get("recall")
            if p is not None and r is not None and (p + r) > 0:
                metrics["f1"] = round(2 * p * r / (p + r), 6)
            else:
                metrics["f1"] = None
                reasons["f1"] = "precision/recall unavailable or both zero"
        else:
            for m in ("precision", "recall", "f1"):
                metrics[m] = None
                reasons[m] = "requires binary {0,1} labels and predictions"

    # -- ROC AUC / log loss (need scores) ------------------------------------
    ls = _pairs(samples, test_pos, "label", "score")
    binary_scored = ls and all(float(a).is_integer() and int(a) in (0, 1) for a, _ in ls)
    pos = [s for a, s in ls if int(a) == 1] if binary_scored else []
    neg = [s for a, s in ls if int(a) == 0] if binary_scored else []
    if binary_scored and pos and neg:
        ranked = sorted((s, i) for i, (a, s) in enumerate(ls))
        # average ranks with tie handling
        rank_of: Dict[int, float] = {}
        i = 0
        while i < len(ranked):
            j = i
            while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for t in range(i, j + 1):
                rank_of[ranked[t][1]] = avg_rank
            i = j + 1
        pos_rank_sum = sum(rank_of[i] for i, (a, _) in enumerate(ls) if int(a) == 1)
        auc = (pos_rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
        metrics["roc_auc"] = round(auc, 6)
    else:
        metrics["roc_auc"] = None
        reasons["roc_auc"] = (
            "requires binary labels with scores and both classes present in the fold"
        )
    if binary_scored and all(0.0 <= s <= 1.0 for _, s in ls):
        clipped = [(int(a), min(max(s, _EPS), 1 - _EPS)) for a, s in ls]
        metrics["log_loss"] = round(
            -sum(a * math.log(s) + (1 - a) * math.log(1 - s) for a, s in clipped) / len(clipped), 6
        )
    else:
        metrics["log_loss"] = None
        reasons["log_loss"] = "requires binary labels and probability scores in [0, 1]"

    # -- regression -----------------------------------------------------------
    if lp and not is_classlike:
        errors = [a - b for a, b in lp]
        metrics["mae"] = round(sum(abs(e) for e in errors) / len(errors), 6)
        mse = sum(e * e for e in errors) / len(errors)
        metrics["mse"] = round(mse, 6)
        metrics["rmse"] = round(math.sqrt(mse), 6)
        mean_label = sum(labels) / len(labels)
        ss_tot = sum((a - mean_label) ** 2 for a in labels)
        if ss_tot > _EPS:
            metrics["r2"] = round(1 - sum(e * e for e in errors) / ss_tot, 6)
        else:
            metrics["r2"] = None
            reasons["r2"] = "label variance is zero in this fold"
    else:
        for m in ("mae", "mse", "rmse", "r2"):
            metrics[m] = None
            reasons[m] = "requires continuous labels and predictions"

    # -- supplied returns ------------------------------------------------------
    rets = _collect(samples, test_pos, "ret")
    if rets:
        mean_r = sum(rets) / len(rets)
        metrics["return_mean"] = round(mean_r, 6)
        metrics["return_cumulative"] = round(sum(rets), 6)
        metrics["hit_rate"] = round(sum(1 for r in rets if r > 0) / len(rets), 6)
        if len(rets) > 1:
            var = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
            std = math.sqrt(var)
            metrics["return_std"] = round(std, 6)
            if std > _EPS:
                metrics["sharpe_like"] = round(mean_r / std, 6)
            else:
                metrics["sharpe_like"] = None
                reasons["sharpe_like"] = "return standard deviation is zero"
        else:
            metrics["return_std"] = None
            metrics["sharpe_like"] = None
            reasons["return_std"] = reasons["sharpe_like"] = "needs at least 2 returns"
    else:
        for m in ("return_mean", "return_std", "hit_rate", "return_cumulative", "sharpe_like"):
            metrics[m] = None
            reasons[m] = "no supplied returns on test samples"

    return {"metrics": metrics, "reasons": reasons}


def aggregate_metrics(split_metric_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cross-fold aggregation: mean/median/std/min/max/valid-fold count per metric."""
    names: set[str] = set()
    for block in split_metric_blocks:
        names.update(block["metrics"].keys())
    out: Dict[str, Any] = {}
    for name in sorted(names):
        values = [
            b["metrics"][name]
            for b in split_metric_blocks
            if b["metrics"].get(name) is not None
        ]
        if not values:
            out[name] = {"valid_folds": 0}
            continue
        mean_v = sum(values) / len(values)
        std_v = (
            math.sqrt(sum((v - mean_v) ** 2 for v in values) / (len(values) - 1))
            if len(values) > 1
            else 0.0
        )
        out[name] = {
            "mean": round(mean_v, 6),
            "median": round(median(values), 6),
            "std": round(std_v, 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "valid_folds": len(values),
        }
    return out


__all__ = ["split_metrics", "aggregate_metrics"]
