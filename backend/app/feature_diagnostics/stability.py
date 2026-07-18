"""
Rank-stability diagnostics across validation splits (research diagnostics
only — an unstable feature is not automatically "bad").

Transparent formulas (documented in docs/FEATURE_STABILITY_AND_DRIFT_POLICY.md):

* stability_score = 1 − min(1, rank_std / max_spread), where
  max_spread = (n_features − 1) / 2.  Requires ≥ 2 valid splits and
  ≥ 2 features; otherwise null → classification "unknown".
* classification: stable ≥ 0.75 > moderately_stable ≥ 0.50 > unstable.
* pairwise split correlations: Spearman and Kendall over the per-split
  mean-importance vectors (scipy, average-tie handling); undefined
  correlations (constant vectors, < 2 shared features) are null with a
  reason, never NaN.
* top-k overlap: |topk(A) ∩ topk(B)| / k with k = min(5, n_features),
  averaged over split pairs.

Pairwise matrices are bounded to the first MAX_PAIRWISE_SPLITS valid splits;
any truncation is disclosed in the summary.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as sp_stats

STABLE_THRESHOLD = 0.75
MODERATE_THRESHOLD = 0.50
TOP_K = 5
MAX_PAIRWISE_SPLITS = 12


def stability_score(rank_std: Optional[float], n_features: int,
                    valid_splits: int) -> Optional[float]:
    if rank_std is None or valid_splits < 2 or n_features < 2:
        return None
    max_spread = (n_features - 1) / 2.0
    if max_spread <= 0:
        return None
    return float(1.0 - min(1.0, rank_std / max_spread))


def classify_stability(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    if score >= STABLE_THRESHOLD:
        return "stable"
    if score >= MODERATE_THRESHOLD:
        return "moderately_stable"
    return "unstable"


def _corr(a: np.ndarray, b: np.ndarray, kind: str) -> Optional[float]:
    if len(a) < 2 or float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return None
    if kind == "spearman":
        value = sp_stats.spearmanr(a, b).statistic
    else:
        value = sp_stats.kendalltau(a, b).statistic
    return float(value) if value is not None and math.isfinite(value) else None


def _top_k(vector: Dict[str, Optional[float]], k: int) -> set:
    scored = [(name, v) for name, v in vector.items() if v is not None]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return {name for name, _ in scored[:k]}


def stability_summary(
    split_records: Sequence[Dict[str, Any]], feature_names: Sequence[str]
) -> Dict[str, Any]:
    valid = [s for s in split_records if s["status"] == "valid"]
    truncated = len(valid) > MAX_PAIRWISE_SPLITS
    used = valid[:MAX_PAIRWISE_SPLITS]
    k = min(TOP_K, len(feature_names))
    pairs: List[Dict[str, Any]] = []
    spearmans: List[float] = []
    kendalls: List[float] = []
    overlaps: List[float] = []
    for i in range(len(used)):
        for j in range(i + 1, len(used)):
            vec_i = {n: used[i]["features"][n]["mean_importance"] for n in feature_names}
            vec_j = {n: used[j]["features"][n]["mean_importance"] for n in feature_names}
            shared = [n for n in feature_names
                      if vec_i[n] is not None and vec_j[n] is not None]
            a = np.array([vec_i[n] for n in shared], dtype=np.float64)
            b = np.array([vec_j[n] for n in shared], dtype=np.float64)
            spearman = _corr(a, b, "spearman") if len(shared) >= 2 else None
            kendall = _corr(a, b, "kendall") if len(shared) >= 2 else None
            overlap = None
            if k > 0 and shared:
                inter = _top_k(vec_i, k) & _top_k(vec_j, k)
                overlap = len(inter) / k
            entry = {
                "split_a": used[i]["split_id"], "split_b": used[j]["split_id"],
                "spearman": spearman, "kendall": kendall,
                "top_k_overlap": overlap,
                "note": None if len(shared) >= 2
                else "fewer than 2 shared defined features",
            }
            pairs.append(entry)
            if spearman is not None:
                spearmans.append(spearman)
            if kendall is not None:
                kendalls.append(kendall)
            if overlap is not None:
                overlaps.append(overlap)
    return {
        "valid_split_count": len(valid),
        "pairwise_split_count": len(used),
        "truncated": truncated,
        "truncation_note": (
            f"pairwise matrix limited to the first {MAX_PAIRWISE_SPLITS} valid splits"
            if truncated else None
        ),
        "top_k": k,
        "pairs": pairs,
        "mean_spearman": float(np.mean(spearmans)) if spearmans else None,
        "min_spearman": float(np.min(spearmans)) if spearmans else None,
        "mean_kendall": float(np.mean(kendalls)) if kendalls else None,
        "mean_top_k_overlap": float(np.mean(overlaps)) if overlaps else None,
        "score_formula": "1 - min(1, rank_std / ((n_features - 1) / 2))",
        "thresholds": {"stable": STABLE_THRESHOLD,
                       "moderately_stable": MODERATE_THRESHOLD},
    }


def apply_stability(
    aggregates: List[Dict[str, Any]], n_features: int
) -> None:
    """Attach stability score/classification + sign consistency in place."""
    for entry in aggregates:
        score = stability_score(entry.get("rank_std"), n_features,
                                entry.get("valid_split_count", 0))
        entry["stability_score"] = score
        entry["stability_classification"] = classify_stability(score)
        pos = entry.get("positive_split_fraction")
        neg = entry.get("negative_split_fraction")
        entry["sign_consistency"] = (
            max(pos, neg) if pos is not None and neg is not None else None
        )
        entry["sign_changed_across_splits"] = (
            pos is not None and neg is not None and pos > 0 and neg > 0
        )


__all__ = [
    "STABLE_THRESHOLD", "MODERATE_THRESHOLD", "TOP_K", "MAX_PAIRWISE_SPLITS",
    "stability_score", "classify_stability", "stability_summary",
    "apply_stability",
]
