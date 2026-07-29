"""
Quantile/bucket diagnostics, top-minus-bottom reference and monotonicity
(v1).

Buckets are DETERMINISTIC equal-count rank buckets over the configured
score orientation.  Ties are broken by the declared tie policy: under
``average`` tied values receive their average rank and a tie that straddles
a boundary is assigned by the deterministic secondary key (entity id, then
timestamp) — that split is documented here rather than silent.  Under
``first`` the ordering is fully ordinal on (value, entity id, timestamp).

Bucket 1 is the LOWEST configured score, bucket ``n`` the highest.  Nothing
here selects a bucket, allocates capital or recommends anything: the
top-minus-bottom spread is a neutral EQUAL-WEIGHT descriptive reference
(long the top bucket, short the bottom bucket, gross exposure 2.0 per unit
of reference capital), and monotonic bucket means are a description of this
sample — not proof of predictability.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats as sp_stats

MIN_BUCKETS = 2
MAX_BUCKETS = 10

BUCKET_SCOPES = ("global", "per_timestamp")


class BucketError(ValueError):
    """Invalid bucket configuration (HTTP 422)."""


def validate_bucket_config(raw: Any) -> Dict[str, Any]:
    cfg = dict(raw or {})
    unknown = sorted(set(cfg) - {"bucket_count", "scope",
                                 "minimum_per_bucket"})
    if unknown:
        raise BucketError(f"unknown bucket keys: {unknown}")
    count = cfg.get("bucket_count", 5)
    if isinstance(count, bool) or not isinstance(count, int) \
            or not (MIN_BUCKETS <= count <= MAX_BUCKETS):
        raise BucketError(
            f"bucket_count must be an integer in [{MIN_BUCKETS}, "
            f"{MAX_BUCKETS}]")
    scope = cfg.get("scope", "global")
    if scope not in BUCKET_SCOPES:
        raise BucketError(f"bucket scope must be one of {list(BUCKET_SCOPES)}")
    minimum = cfg.get("minimum_per_bucket", 2)
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        raise BucketError("minimum_per_bucket must be an integer >= 1")
    return {"bucket_count": count, "scope": scope,
            "minimum_per_bucket": minimum,
            "scheme": "equal_count_rank",
            "ordering": ("bucket 1 = lowest configured score; ties ordered by "
                         "the declared tie policy with (entity_id, timestamp) "
                         "as the deterministic secondary key")}


def _ordinal_order(pairs: Sequence[Dict[str, Any]],
                   scores: Sequence[float]) -> List[int]:
    """Deterministic total order: score, then entity, then timestamp."""
    return sorted(range(len(pairs)),
                  key=lambda i: (scores[i], pairs[i]["entity_id"],
                                 pairs[i]["signal_timestamp"]))


def assign_buckets(pairs: List[Dict[str, Any]],
                   scores: Sequence[float], *,
                   bucket_count: int, scope: str,
                   frozen_thresholds: Optional[List[float]] = None
                   ) -> Tuple[List[int], Optional[List[float]],
                              List[Dict[str, Any]]]:
    """Bucket index (1-based) per pair, thresholds, and boundary rows.

    ``frozen_thresholds`` (train-derived, under a linked validation split)
    bucket by VALUE against fixed boundaries instead of re-ranking, so
    held-out observations cannot move the boundaries.
    """
    n = len(pairs)
    assignments = [0] * n
    if frozen_thresholds is not None:
        for i, score in enumerate(scores):
            bucket = 1
            for threshold in frozen_thresholds:
                if score > threshold:
                    bucket += 1
            assignments[i] = min(bucket, bucket_count)
        boundaries = _boundary_rows(pairs, scores, assignments, bucket_count)
        return assignments, list(frozen_thresholds), boundaries

    if scope == "global":
        order = _ordinal_order(pairs, list(scores))
        for position, index in enumerate(order):
            assignments[index] = min(bucket_count,
                                     position * bucket_count // n + 1)
        thresholds = _thresholds_from_order(list(scores), order, bucket_count)
    else:
        by_stamp: Dict[str, List[int]] = {}
        for i, pair in enumerate(pairs):
            by_stamp.setdefault(pair["signal_timestamp"], []).append(i)
        for stamp in sorted(by_stamp):
            members = by_stamp[stamp]
            local_pairs = [pairs[i] for i in members]
            local_scores = [scores[i] for i in members]
            order = _ordinal_order(local_pairs, local_scores)
            m = len(members)
            for position, local_index in enumerate(order):
                assignments[members[local_index]] = min(
                    bucket_count, position * bucket_count // m + 1)
        thresholds = None  # per-timestamp boundaries differ per stamp
    boundaries = _boundary_rows(pairs, scores, assignments, bucket_count)
    return assignments, thresholds, boundaries


def _thresholds_from_order(scores: List[float], order: List[int],
                           bucket_count: int) -> List[float]:
    """Upper score boundary of buckets 1..n-1 (global scope)."""
    n = len(order)
    thresholds: List[float] = []
    for bucket in range(1, bucket_count):
        cut = (bucket * n) // bucket_count - 1
        cut = max(0, min(cut, n - 1))
        thresholds.append(float(scores[order[cut]]))
    return thresholds


def _boundary_rows(pairs: Sequence[Dict[str, Any]], scores: Sequence[float],
                   assignments: Sequence[int],
                   bucket_count: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for bucket in range(1, bucket_count + 1):
        values = [scores[i] for i in range(len(pairs))
                  if assignments[i] == bucket]
        rows.append({
            "bucket": bucket,
            "count": len(values),
            "score_minimum": float(min(values)) if values else None,
            "score_maximum": float(max(values)) if values else None,
        })
    return rows


def bucket_outcomes(pairs: List[Dict[str, Any]],
                    assignments: Sequence[int], *,
                    bucket_count: int,
                    minimum_per_bucket: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for bucket in range(1, bucket_count + 1):
        outcomes = [pairs[i]["outcome_value"] for i in range(len(pairs))
                    if assignments[i] == bucket
                    and pairs[i]["outcome_value"] is not None]
        entry: Dict[str, Any] = {
            "bucket": bucket, "observations": len(outcomes),
            "mean_outcome": None, "median_outcome": None,
            "std_outcome": None, "positive_rate": None,
            "state": "unavailable", "reason": None,
        }
        if not outcomes:
            entry["reason"] = "empty bucket (visible, never hidden)"
        elif len(outcomes) < minimum_per_bucket:
            entry["reason"] = (f"{len(outcomes)} observation(s) are below the "
                               f"bucket minimum of {minimum_per_bucket}")
        else:
            array = np.asarray(outcomes, dtype=np.float64)
            entry.update({
                "mean_outcome": float(np.mean(array)),
                "median_outcome": float(np.median(array)),
                "std_outcome": (float(np.std(array, ddof=1))
                                if array.size >= 2 else None),
                "positive_rate": float(np.mean(array > 0)),
                "state": "available",
            })
        rows.append(entry)
    return rows


def top_minus_bottom(bucket_rows: List[Dict[str, Any]],
                     *, bucket_count: int) -> Dict[str, Any]:
    """Neutral equal-weight descriptive reference: mean(top) − mean(bottom)."""
    top = next((r for r in bucket_rows if r["bucket"] == bucket_count), None)
    bottom = next((r for r in bucket_rows if r["bucket"] == 1), None)
    out: Dict[str, Any] = {
        "convention": ("equal-weight long the top bucket, equal-weight short "
                       "the bottom bucket; gross exposure 2.0 per unit of "
                       "reference capital; a neutral descriptive reference, "
                       "not a strategy and not a recommendation"),
        "top_bucket": bucket_count, "bottom_bucket": 1,
        "top_mean": None, "bottom_mean": None, "spread": None,
        "gross_exposure": 2.0,
        "state": "unavailable", "reason": None,
    }
    if top is None or bottom is None \
            or top["state"] != "available" or bottom["state"] != "available":
        missing = []
        if top is None or top["state"] != "available":
            missing.append("top")
        if bottom is None or bottom["state"] != "available":
            missing.append("bottom")
        out["reason"] = (f"the {' and '.join(missing)} bucket(s) are "
                         f"unavailable, so the spread is unavailable — a "
                         f"missing side is never substituted")
        return out
    out.update({
        "top_mean": top["mean_outcome"],
        "bottom_mean": bottom["mean_outcome"],
        "spread": float(top["mean_outcome"] - bottom["mean_outcome"]),
        "state": "available",
    })
    return out


def monotonicity(bucket_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Descriptive bucket-order diagnostics — no p-values, no verdict."""
    usable = [(r["bucket"], r["mean_outcome"]) for r in bucket_rows
              if r["state"] == "available"]
    out: Dict[str, Any] = {
        "buckets_available": len(usable),
        "buckets_total": len(bucket_rows),
        "spearman_bucket_vs_mean": None,
        "adjacent_consistent": None, "adjacent_violations": None,
        "reason": None,
        "note": ("descriptive ordering of bucket means over this sample; "
                 "no p-value is defined for bucket means, and monotonic "
                 "buckets do not prove predictability"),
    }
    if len(usable) < 3:
        out["reason"] = "fewer than 3 available buckets"
        return out
    ordinals = [b for b, _ in usable]
    means = [m for _, m in usable]
    if len(set(means)) < 2:
        out["reason"] = "bucket means are tied across all available buckets"
        out["adjacent_consistent"] = 0
        out["adjacent_violations"] = 0
        return out
    result = sp_stats.spearmanr(ordinals, means)
    statistic = float(result.statistic)
    out["spearman_bucket_vs_mean"] = (statistic if math.isfinite(statistic)
                                      else None)
    differences = [means[i + 1] - means[i] for i in range(len(means) - 1)]
    non_zero = [d for d in differences if d != 0]
    if non_zero:
        dominant = 1.0 if sum(1 for d in non_zero if d > 0) * 2 >= len(non_zero) \
            else -1.0
        consistent = sum(1 for d in non_zero if math.copysign(1, d) == dominant)
        out["adjacent_consistent"] = consistent
        out["adjacent_violations"] = len(non_zero) - consistent
    else:
        out["adjacent_consistent"] = 0
        out["adjacent_violations"] = 0
    return out


__all__ = [
    "MIN_BUCKETS", "MAX_BUCKETS", "BUCKET_SCOPES", "BucketError",
    "validate_bucket_config", "assign_buckets", "bucket_outcomes",
    "top_minus_bottom", "monotonicity",
]
