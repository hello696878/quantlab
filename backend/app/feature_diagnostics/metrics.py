"""
Evaluation metrics with explicit direction, used for held-out permutation
importance.  Importance normalization (documented):

* ``higher_is_better`` metrics: importance = baseline_score − permuted_score
* ``lower_is_better``  metrics: importance = permuted_score − baseline_score

so positive importance always means permuting the feature made held-out
performance worse under the selected metric.  Positive importance is a
measured sensitivity — never a profitability or causality claim.

Undefined metrics (e.g. ROC AUC on a one-class fold) raise
``MetricUnavailable`` with a reason; nothing is silently substituted.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

EPS = 1e-12
CLASSIFICATION_THRESHOLD = 0.5  # for f1 / balanced_accuracy on probabilities

METRICS: Dict[str, Dict[str, str]] = {
    # binary classification (predictions are probabilities of class 1)
    "log_loss": {"task": "binary_classification", "direction": "lower_is_better"},
    "brier": {"task": "binary_classification", "direction": "lower_is_better"},
    "roc_auc": {"task": "binary_classification", "direction": "higher_is_better"},
    "pr_auc": {"task": "binary_classification", "direction": "higher_is_better"},
    "balanced_accuracy": {"task": "binary_classification", "direction": "higher_is_better"},
    "f1": {"task": "binary_classification", "direction": "higher_is_better"},
    # regression
    "mae": {"task": "regression", "direction": "lower_is_better"},
    "mse": {"task": "regression", "direction": "lower_is_better"},
    "rmse": {"task": "regression", "direction": "lower_is_better"},
    "r2": {"task": "regression", "direction": "higher_is_better"},
}


class MetricUnavailable(ValueError):
    """The metric is undefined on this data (reported honestly, never zeroed)."""


def metric_direction(metric: str) -> str:
    if metric not in METRICS:
        raise MetricUnavailable(f"unsupported metric {metric!r}")
    return METRICS[metric]["direction"]


def _roc_auc(y: np.ndarray, p: np.ndarray) -> float:
    pos, neg = int(y.sum()), int(len(y) - y.sum())
    if pos == 0 or neg == 0:
        raise MetricUnavailable("roc_auc is undefined when only one class is present")
    order = np.argsort(p, kind="stable")
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    # average ranks for ties
    sorted_p = p[order]
    i = 0
    while i < len(sorted_p):
        j = i
        while j + 1 < len(sorted_p) and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def _pr_auc(y: np.ndarray, p: np.ndarray) -> float:
    pos = int(y.sum())
    if pos == 0:
        raise MetricUnavailable("pr_auc is undefined with no positive samples")
    order = np.argsort(-p, kind="stable")
    ys = y[order]
    ps = p[order]
    # Average precision with TIE GROUPING: every row sharing a score forms one
    # recall/precision step, so the result depends only on the (label, score)
    # multiset and never on the incoming row order.  Without grouping, a stable
    # sort breaks ties by original index and a constant predictor would score
    # above its base rate.  Mirrors _roc_auc's tie handling above.
    ap = 0.0
    tp = 0
    i = 0
    n = len(ys)
    while i < n:
        j = i
        while j + 1 < n and ps[j + 1] == ps[i]:
            j += 1
        group_tp = int(ys[i:j + 1].sum())
        tp += group_tp
        if group_tp:
            ap += group_tp * (tp / (j + 1))
        i = j + 1
    return float(ap / pos)


def score(metric: str, y: np.ndarray, pred: np.ndarray) -> float:
    """Single metric value; raises MetricUnavailable when undefined."""
    if metric not in METRICS:
        raise MetricUnavailable(f"unsupported metric {metric!r}")
    if len(y) == 0:
        raise MetricUnavailable("empty evaluation set")
    y = np.asarray(y, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    if metric == "log_loss":
        p = np.clip(pred, EPS, 1.0 - EPS)
        return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    if metric == "brier":
        return float(((pred - y) ** 2).mean())
    if metric == "roc_auc":
        return _roc_auc(y, pred)
    if metric == "pr_auc":
        return _pr_auc(y, pred)
    if metric in ("balanced_accuracy", "f1"):
        hard = (pred >= CLASSIFICATION_THRESHOLD).astype(np.float64)
        tp = float(((hard == 1) & (y == 1)).sum())
        tn = float(((hard == 0) & (y == 0)).sum())
        fp = float(((hard == 1) & (y == 0)).sum())
        fn = float(((hard == 0) & (y == 1)).sum())
        if metric == "balanced_accuracy":
            if tp + fn == 0 or tn + fp == 0:
                raise MetricUnavailable(
                    "balanced_accuracy is undefined when only one class is present"
                )
            return float((tp / (tp + fn) + tn / (tn + fp)) / 2.0)
        denom = 2 * tp + fp + fn
        if denom == 0:
            raise MetricUnavailable("f1 is undefined with no positives predicted or present")
        return float(2 * tp / denom)
    if metric == "mae":
        return float(np.abs(pred - y).mean())
    if metric == "mse":
        return float(((pred - y) ** 2).mean())
    if metric == "rmse":
        return float(np.sqrt(((pred - y) ** 2).mean()))
    # r2
    ss_tot = float(((y - y.mean()) ** 2).sum())
    if ss_tot == 0.0:
        raise MetricUnavailable("r2 is undefined when the target is constant")
    return float(1.0 - ((pred - y) ** 2).sum() / ss_tot)


def importance_from_scores(direction: str, baseline: float, permuted: float) -> float:
    """Normalize so positive importance = permutation worsened performance."""
    if direction == "higher_is_better":
        return baseline - permuted
    return permuted - baseline


__all__ = [
    "EPS", "CLASSIFICATION_THRESHOLD", "METRICS", "MetricUnavailable",
    "metric_direction", "score", "importance_from_scores",
]
