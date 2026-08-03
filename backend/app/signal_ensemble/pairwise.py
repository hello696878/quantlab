"""
Pairwise similarity diagnostics (Phase 61, v1).

Every signal pair is compared over an EXPLICIT overlap (strict-intersection
keys or the pair's own overlap under ``pairwise_complete``) with its sample
count on the row.  Correlations reuse the reviewed Phase 60 machinery
(`app.signal_decay.statistics.correlation`): real scipy p-values only,
constants and thin overlap honestly unavailable, Kendall as tie-adjusted
tau-b.  No correlation threshold ever marks two signals duplicates, and no
similarity number is called proof of shared or independent information.

Also here: rank/bucket agreement (top/bottom overlap, Jaccard, exact and
adjacent agreement), sign agreement with zero-sign counts, and tail
co-occurrence at an explicit quantile threshold — all descriptive counts.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.signal_decay import statistics as sd_statistics

Key = Tuple[str, str]

MIN_PAIR_OVERLAP = 4
DEFAULT_TAIL_QUANTILE = 0.2
MIN_TAIL_OBSERVATIONS = 10
DEFAULT_AGREEMENT_BUCKETS = 3


class PairwiseError(ValueError):
    """Invalid pairwise configuration (HTTP 422)."""


def validate_similarity_policy(raw: Any) -> Dict[str, Any]:
    policy = dict(raw or {})
    unknown = sorted(set(policy) - {
        "correlation_methods", "matrix_method", "minimum_pair_overlap",
        "tail_quantile", "agreement_bucket_count", "distance_formula",
        "clustering"})
    if unknown:
        raise PairwiseError(f"unknown similarity policy keys: {unknown}")
    methods = tuple(policy.get("correlation_methods")
                    or ("pearson", "spearman"))
    for method in methods:
        if method not in sd_statistics.CORRELATION_METHODS:
            raise PairwiseError(
                f"correlation method {method!r} must be one of "
                f"{list(sd_statistics.CORRELATION_METHODS)}")
    matrix_method = policy.get("matrix_method", "spearman")
    if matrix_method not in ("pearson", "spearman"):
        raise PairwiseError(
            "matrix_method must be 'pearson' or 'spearman'")
    if matrix_method not in methods:
        raise PairwiseError(
            f"matrix_method {matrix_method!r} must be one of the configured "
            f"correlation_methods {list(methods)}")
    minimum = policy.get("minimum_pair_overlap", MIN_PAIR_OVERLAP)
    if not isinstance(minimum, int) or isinstance(minimum, bool) \
            or minimum < 3:
        raise PairwiseError("minimum_pair_overlap must be an integer >= 3")
    tail = policy.get("tail_quantile", DEFAULT_TAIL_QUANTILE)
    if not isinstance(tail, (int, float)) or isinstance(tail, bool) \
            or not (0.0 < float(tail) <= 0.5):
        raise PairwiseError("tail_quantile must lie in (0, 0.5]")
    buckets = policy.get("agreement_bucket_count", DEFAULT_AGREEMENT_BUCKETS)
    if not isinstance(buckets, int) or isinstance(buckets, bool) \
            or not (2 <= buckets <= 10):
        raise PairwiseError("agreement_bucket_count must be an integer in "
                            "[2, 10]")
    distance_formula = policy.get("distance_formula", "sqrt_half_one_minus_corr")
    if distance_formula != "sqrt_half_one_minus_corr":
        raise PairwiseError(
            "distance_formula must be 'sqrt_half_one_minus_corr' "
            "(sqrt(0.5 * (1 - corr))) — the only documented v1 formula")
    return {
        "correlation_methods": list(methods),
        "matrix_method": matrix_method,
        "minimum_pair_overlap": minimum,
        "tail_quantile": float(tail),
        "agreement_bucket_count": buckets,
        "distance_formula": distance_formula,
        "clustering": policy.get("clustering"),
    }


def pair_order(signal_ids: Sequence[str]) -> List[Tuple[str, str]]:
    """Deterministic canonical pair ordering (sorted, i < j)."""
    ordered = sorted(signal_ids)
    return [(ordered[i], ordered[j])
            for i in range(len(ordered))
            for j in range(i + 1, len(ordered))]


def _aligned(values_a: Dict[Key, Optional[float]],
             values_b: Dict[Key, Optional[float]],
             keys: Sequence[Key]) -> Tuple[List[float], List[float],
                                           List[Key]]:
    xs: List[float] = []
    ys: List[float] = []
    used: List[Key] = []
    for key in keys:
        a = values_a.get(key)
        b = values_b.get(key)
        if a is None or b is None:
            continue
        xs.append(float(a))
        ys.append(float(b))
        used.append(key)
    return xs, ys, used


def pair_row(signal_a: str, signal_b: str, *,
             values_a: Dict[Key, Optional[float]],
             values_b: Dict[Key, Optional[float]],
             keys: Sequence[Key],
             stored_a: int, stored_b: int,
             policy: Dict[str, Any],
             alignment_mode: str,
             comparable_scale: bool) -> Dict[str, Any]:
    """One pairwise diagnostics row over the given key universe."""
    xs, ys, used = _aligned(values_a, values_b, keys)
    n = len(xs)
    row: Dict[str, Any] = {
        "signal_a": signal_a, "signal_b": signal_b,
        "alignment_mode": alignment_mode,
        "overlap_count": n,
        "coverage_a": (n / stored_a) if stored_a else None,
        "coverage_b": (n / stored_b) if stored_b else None,
        "mean_absolute_difference": None,
        "mean_absolute_difference_note": None,
        "sign_agreement_rate": None,
        "zero_sign_count": None,
        "state": "unavailable", "reason": None,
    }
    correlations = {
        method: sd_statistics.correlation(
            xs, ys, method=method,
            minimum_observations=policy["minimum_pair_overlap"],
            overlapping=False)
        for method in policy["correlation_methods"]}
    row["correlations"] = correlations
    if n < policy["minimum_pair_overlap"]:
        row["reason"] = (f"{n} overlapping observation(s) are below the "
                         f"minimum of {policy['minimum_pair_overlap']}")
        return row
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    if comparable_scale:
        row["mean_absolute_difference"] = float(np.mean(np.abs(x - y)))
    else:
        row["mean_absolute_difference_note"] = (
            "unavailable: the two signals are not on a comparable "
            "normalised scale, and nothing is rescaled silently")
    row["zero_sign_count"] = int(np.sum(np.sign(x) == 0)
                                 + np.sum(np.sign(y) == 0))
    row["sign_agreement_rate"] = float(np.mean(np.sign(x) == np.sign(y)))
    row["state"] = ("available"
                    if any(c["state"] == "available"
                           for c in correlations.values())
                    else "unavailable")
    if row["state"] == "unavailable":
        first = next(iter(correlations.values()))
        row["reason"] = first["reason"]
    return row


# ---------------------------------------------------------------------------
# Rank / bucket agreement
# ---------------------------------------------------------------------------

def _timestamp_buckets(values: Dict[Key, Optional[float]],
                       keys: Sequence[Key], *, bucket_count: int
                       ) -> Dict[Key, int]:
    """Per-timestamp equal-count buckets (1..n) over the shared keys."""
    by_stamp: Dict[str, List[Key]] = {}
    for key in keys:
        if values.get(key) is not None:
            by_stamp.setdefault(key[1], []).append(key)
    out: Dict[Key, int] = {}
    for stamp in sorted(by_stamp):
        members = by_stamp[stamp]
        order = sorted(range(len(members)),
                       key=lambda i: (values[members[i]], members[i][0]))
        m = len(members)
        for position, index in enumerate(order):
            out[members[index]] = min(bucket_count,
                                      position * bucket_count // m + 1)
    return out


def bucket_agreement(signal_a: str, signal_b: str, *,
                     values_a: Dict[Key, Optional[float]],
                     values_b: Dict[Key, Optional[float]],
                     keys: Sequence[Key],
                     bucket_count: int,
                     minimum_per_timestamp: int = 3) -> Dict[str, Any]:
    """Bucket/tail-free agreement over the SHARED eligible universe.

    Both signals are bucketed per timestamp over the same shared keys and
    with the same bucket policy, so bucket agreement compares like with
    like.  Timestamps with fewer than ``minimum_per_timestamp`` shared
    entities are excluded and counted.
    """
    shared = [key for key in keys
              if values_a.get(key) is not None
              and values_b.get(key) is not None]
    by_stamp: Dict[str, List[Key]] = {}
    for key in shared:
        by_stamp.setdefault(key[1], []).append(key)
    eligible_keys: List[Key] = []
    skipped_timestamps = 0
    for stamp in sorted(by_stamp):
        members = by_stamp[stamp]
        if len(members) < minimum_per_timestamp:
            skipped_timestamps += 1
            continue
        eligible_keys.extend(members)
    out: Dict[str, Any] = {
        "signal_a": signal_a, "signal_b": signal_b,
        "bucket_count": bucket_count,
        "observations": len(eligible_keys),
        "skipped_timestamps": skipped_timestamps,
        "exact_agreement_rate": None,
        "adjacent_agreement_rate": None,
        "top_bucket_jaccard": None,
        "bottom_bucket_jaccard": None,
        "directional_disagreement_count": None,
        "state": "unavailable", "reason": None,
    }
    if not eligible_keys:
        out["reason"] = ("no timestamp has enough shared entities for "
                         "bucket agreement")
        return out
    buckets_a = _timestamp_buckets(values_a, eligible_keys,
                                   bucket_count=bucket_count)
    buckets_b = _timestamp_buckets(values_b, eligible_keys,
                                   bucket_count=bucket_count)
    exact = 0
    adjacent = 0
    disagreement = 0
    top_a: set = set()
    top_b: set = set()
    bottom_a: set = set()
    bottom_b: set = set()
    for key in eligible_keys:
        a = buckets_a[key]
        b = buckets_b[key]
        if a == b:
            exact += 1
        if abs(a - b) <= 1:
            adjacent += 1
        sign_a = 1 if a > (bucket_count + 1) / 2 else \
            (-1 if a < (bucket_count + 1) / 2 else 0)
        sign_b = 1 if b > (bucket_count + 1) / 2 else \
            (-1 if b < (bucket_count + 1) / 2 else 0)
        if sign_a * sign_b < 0:
            disagreement += 1
        if a == bucket_count:
            top_a.add(key)
        if b == bucket_count:
            top_b.add(key)
        if a == 1:
            bottom_a.add(key)
        if b == 1:
            bottom_b.add(key)
    n = len(eligible_keys)
    out["exact_agreement_rate"] = exact / n
    out["adjacent_agreement_rate"] = adjacent / n
    out["directional_disagreement_count"] = disagreement
    top_union = top_a | top_b
    bottom_union = bottom_a | bottom_b
    out["top_bucket_jaccard"] = (len(top_a & top_b) / len(top_union)
                                 if top_union else None)
    out["bottom_bucket_jaccard"] = (len(bottom_a & bottom_b)
                                    / len(bottom_union)
                                    if bottom_union else None)
    out["state"] = "available"
    return out


# ---------------------------------------------------------------------------
# Tail co-occurrence
# ---------------------------------------------------------------------------

def tail_cooccurrence(signal_a: str, signal_b: str, *,
                      values_a: Dict[Key, Optional[float]],
                      values_b: Dict[Key, Optional[float]],
                      keys: Sequence[Key],
                      quantile: float,
                      outcomes: Optional[Dict[Key, float]] = None
                      ) -> Dict[str, Any]:
    """Descriptive tail co-occurrence at an explicit quantile threshold.

    Tail membership is by rank position: the lowest ``floor(q*n)`` shared
    observations form the lower tail (ties broken deterministically by
    (value, entity, timestamp)), symmetrically for the upper tail.  With a
    compatible outcome map, negative- and positive-outcome co-exceedance
    counts are added.  Counts only — no synthetic p-value, no causal
    reading, no downside-protection claim.
    """
    xs, ys, used = _aligned(values_a, values_b, keys)
    n = len(xs)
    out: Dict[str, Any] = {
        "signal_a": signal_a, "signal_b": signal_b,
        "quantile": quantile, "observations": n,
        "tail_size": None,
        "both_lower_count": None, "both_upper_count": None,
        "opposite_tail_count": None,
        "lower_conditional_overlap": None,
        "upper_conditional_overlap": None,
        "negative_outcome_coexceedance": None,
        "positive_outcome_coexceedance": None,
        "state": "unavailable", "reason": None,
    }
    if n < MIN_TAIL_OBSERVATIONS:
        out["reason"] = (f"{n} shared observation(s) are below the tail "
                         f"minimum of {MIN_TAIL_OBSERVATIONS}")
        return out
    tail = int(math.floor(quantile * n))
    if tail < 1:
        out["reason"] = ("the quantile leaves an empty tail at this sample "
                         "size")
        return out

    def tail_sets(values: List[float]) -> Tuple[set, set]:
        order = sorted(range(n),
                       key=lambda i: (values[i], used[i][0], used[i][1]))
        lower = {used[i] for i in order[:tail]}
        upper = {used[i] for i in order[n - tail:]}
        return lower, upper

    lower_a, upper_a = tail_sets(xs)
    lower_b, upper_b = tail_sets(ys)
    both_lower = lower_a & lower_b
    both_upper = upper_a & upper_b
    opposite = (lower_a & upper_b) | (upper_a & lower_b)
    out.update({
        "tail_size": tail,
        "both_lower_count": len(both_lower),
        "both_upper_count": len(both_upper),
        "opposite_tail_count": len(opposite),
        "lower_conditional_overlap": len(both_lower) / tail,
        "upper_conditional_overlap": len(both_upper) / tail,
        "state": "available",
    })
    if outcomes is not None:
        negative = sum(1 for key in both_upper
                       if outcomes.get(key) is not None
                       and outcomes[key] < 0)
        positive = sum(1 for key in both_upper
                       if outcomes.get(key) is not None
                       and outcomes[key] > 0)
        out["negative_outcome_coexceedance"] = negative
        out["positive_outcome_coexceedance"] = positive
    return out


__all__ = [
    "MIN_PAIR_OVERLAP", "DEFAULT_TAIL_QUANTILE", "MIN_TAIL_OBSERVATIONS",
    "DEFAULT_AGREEMENT_BUCKETS", "PairwiseError",
    "validate_similarity_policy", "pair_order", "pair_row",
    "bucket_agreement", "tail_cooccurrence",
]
