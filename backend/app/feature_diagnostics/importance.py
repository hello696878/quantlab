"""
Held-out permutation importance (primary method) and split-level aggregation.

Per valid split: the model is fitted on the split's training samples only,
the baseline metric is evaluated on the held-out samples, then exactly one
feature column is permuted within the held-out set (target and all other
columns untouched) with a deterministic seed per (seed, split, feature,
repeat).  The metric change is direction-normalized by
``metrics.importance_from_scores`` so positive importance always means the
permutation worsened held-out performance.

Reference methods (model-native impurity, coefficient magnitude) reuse the
same record shape with ``permutation_repeats = 0`` — they are training-data
derived and clearly caveated by the service layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as sp_stats

from app.feature_diagnostics import estimators
from app.feature_diagnostics.metrics import (
    MetricUnavailable, importance_from_scores, score,
)

MIN_REPEATS = 1
MAX_REPEATS = 20
DEFAULT_REPEATS = 5
DEFAULT_SEED = 7
MAX_SEED = 2**31 - 1


def _rank_desc(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    """Average-tie ranks with rank 1 = highest value; None stays None."""
    idx = [i for i, v in enumerate(values) if v is not None]
    ranks: List[Optional[float]] = [None] * len(values)
    if idx:
        arr = np.array([values[i] for i in idx], dtype=np.float64)
        ranked = sp_stats.rankdata(-arr, method="average")
        for pos, i in enumerate(idx):
            ranks[i] = float(ranked[pos])
    return ranks


def _feature_stats(deltas: List[float], repeats: int) -> Dict[str, Any]:
    if not deltas:
        return {
            "mean_importance": None, "median_importance": None,
            "std_importance": None, "min_importance": None,
            "max_importance": None, "positive_repeats": 0,
            "negative_repeats": 0, "valid_repeats": 0,
            "permutation_repeats": repeats, "status": "unavailable",
            "warning": "metric was undefined on every permutation repeat",
        }
    arr = np.array(deltas, dtype=np.float64)
    return {
        "mean_importance": float(arr.mean()),
        "median_importance": float(np.median(arr)),
        "std_importance": float(arr.std()) if len(arr) > 1 else 0.0,
        "min_importance": float(arr.min()),
        "max_importance": float(arr.max()),
        "positive_repeats": int((arr > 0).sum()),
        "negative_repeats": int((arr < 0).sum()),
        "valid_repeats": int(len(arr)),
        "permutation_repeats": repeats,
        "status": "ok",
        "warning": None if len(arr) == repeats
        else f"{repeats - len(arr)} repeat(s) had an undefined metric and were excluded",
    }


def permutation_split_result(
    model: Dict[str, Any],
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: Sequence[str],
    metric: str,
    direction: str,
    seed: int,
    split_index: int,
    repeats: int,
    split_id: str,
) -> Dict[str, Any]:
    """One split's permutation record; raises MetricUnavailable if the
    baseline itself is undefined (the caller records the split as failed)."""
    baseline = score(metric, y_test, estimators.predict(model, X_test))
    features: Dict[str, Dict[str, Any]] = {}
    for j, name in enumerate(feature_names):
        deltas: List[float] = []
        for r in range(repeats):
            rng = np.random.default_rng([seed, split_index, j, r])
            Xp = X_test.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            try:
                permuted = score(metric, y_test, estimators.predict(model, Xp))
            except MetricUnavailable:
                continue
            deltas.append(importance_from_scores(direction, baseline, permuted))
        features[name] = _feature_stats(deltas, repeats)
    _assign_split_ranks(features, feature_names)
    return {
        "split_id": split_id, "split_index": split_index, "status": "valid",
        "baseline_score": float(baseline), "evaluated_count": int(len(y_test)),
        "features": features, "warning": None,
    }


def reference_split_result(
    values_by_feature: Dict[str, float],
    feature_names: Sequence[str],
    baseline: Optional[float],
    split_index: int,
    split_id: str,
    evaluated_count: int,
    warning: Optional[str],
) -> Dict[str, Any]:
    """Native/coefficient value as a degenerate one-value record (repeats=0)."""
    features: Dict[str, Dict[str, Any]] = {}
    for name in feature_names:
        v = values_by_feature.get(name)
        stats = _feature_stats([v] if v is not None else [], 0)
        stats["permutation_repeats"] = 0
        stats["valid_repeats"] = 0 if v is None else 1
        stats["warning"] = None if v is not None else "no reference value available"
        features[name] = stats
    _assign_split_ranks(features, feature_names)
    return {
        "split_id": split_id, "split_index": split_index, "status": "valid",
        "baseline_score": baseline, "evaluated_count": evaluated_count,
        "features": features, "warning": warning,
    }


def _assign_split_ranks(
    features: Dict[str, Dict[str, Any]], feature_names: Sequence[str]
) -> None:
    means = [features[n]["mean_importance"] for n in feature_names]
    for name, rank in zip(feature_names, _rank_desc(means)):
        features[name]["rank"] = rank


def aggregate_features(
    split_records: Sequence[Dict[str, Any]], feature_names: Sequence[str]
) -> List[Dict[str, Any]]:
    """Cross-split aggregates; quantile intervals only with ≥ 4 valid splits
    (never fabricated from fewer)."""
    valid = [s for s in split_records if s["status"] == "valid"]
    out: List[Dict[str, Any]] = []
    for name in feature_names:
        means = [s["features"][name]["mean_importance"] for s in valid
                 if s["features"][name]["mean_importance"] is not None]
        ranks = [s["features"][name]["rank"] for s in valid
                 if s["features"][name]["rank"] is not None]
        pos = sum(1 for m in means if m > 0)
        neg = sum(1 for m in means if m < 0)
        entry: Dict[str, Any] = {
            "feature_name": name,
            "valid_split_count": len(means),
            "positive_split_fraction": pos / len(means) if means else None,
            "negative_split_fraction": neg / len(means) if means else None,
        }
        if means:
            arr = np.array(means, dtype=np.float64)
            entry.update({
                "mean_importance": float(arr.mean()),
                "median_importance": float(np.median(arr)),
                "std_importance": float(arr.std()) if len(arr) > 1 else None,
                "min_importance": float(arr.min()),
                "max_importance": float(arr.max()),
            })
            if len(arr) >= 4:
                entry["quantile_interval"] = {
                    "q25": float(np.quantile(arr, 0.25)),
                    "q75": float(np.quantile(arr, 0.75)),
                }
            else:
                entry["quantile_interval"] = None
        else:
            entry.update({
                "mean_importance": None, "median_importance": None,
                "std_importance": None, "min_importance": None,
                "max_importance": None, "quantile_interval": None,
            })
        if ranks:
            rarr = np.array(ranks, dtype=np.float64)
            entry.update({
                "mean_rank": float(rarr.mean()),
                "median_rank": float(np.median(rarr)),
                "rank_std": float(rarr.std()) if len(rarr) > 1 else None,
                "rank_range": float(rarr.max() - rarr.min()),
            })
        else:
            entry.update({"mean_rank": None, "median_rank": None,
                          "rank_std": None, "rank_range": None})
        out.append(entry)
    # aggregate rank: rank 1 = highest mean importance under the method
    agg_ranks = _rank_desc([e["mean_importance"] for e in out])
    for e, r in zip(out, agg_ranks):
        e["rank"] = r
    return out


__all__ = [
    "MIN_REPEATS", "MAX_REPEATS", "DEFAULT_REPEATS", "DEFAULT_SEED", "MAX_SEED",
    "permutation_split_result", "reference_split_result", "aggregate_features",
]
