"""
Candidate-dependence diagnostics (bounded, pre-checked, conservative).

Candidate trials are usually correlated, which weakens multiple-testing and
expected-maximum-Sharpe assumptions.  This module reports a Pearson
correlation matrix over candidate returns (constant candidates are detected
BEFORE any scipy/numpy correlation call — no ConstantInputWarning is ever
raised or suppressed), highly-correlated pairs above a validated threshold,
deterministic union-find clusters, and an **approximate** effective trial
count:

    K_eff = 1 + (K_defined − 1) · (1 − mean_abs_correlation)

a documented conservative interpolation between fully-dependent (K_eff = 1)
and independent (K_eff = K) trials.  It is an approximation, never exact, and
the lab never claims correlated trials are independent.  Nothing is collapsed
or deleted automatically.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

MIN_DEPENDENCE_THRESHOLD = 0.1
MAX_DEPENDENCE_THRESHOLD = 0.999
DEFAULT_DEPENDENCE_THRESHOLD = 0.7


class DependenceError(ValueError):
    """Invalid dependence configuration (HTTP 422)."""


def validate_dependence_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    config = config or {}
    threshold = config.get("threshold", DEFAULT_DEPENDENCE_THRESHOLD)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) \
            or not math.isfinite(threshold) \
            or not (MIN_DEPENDENCE_THRESHOLD <= float(threshold) <= MAX_DEPENDENCE_THRESHOLD):
        raise DependenceError(
            "dependence threshold must be a finite number in "
            f"[{MIN_DEPENDENCE_THRESHOLD}, {MAX_DEPENDENCE_THRESHOLD}]"
        )
    return {"threshold": float(threshold)}


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            if ri < rj:
                self.parent[rj] = ri
            else:
                self.parent[ri] = rj


CONSTANT_STD_EPS = 1e-12


def is_constant_series(column: np.ndarray) -> bool:
    """True for constant (ptp == 0 exactly — scale-free) or numerically
    quasi-constant columns.  A truly constant series can carry a tiny non-zero
    float std (e.g. [0.1]*24 → std ≈ 2.8e-17), so exact ``std == 0`` is NOT a
    safe predicate; this check runs before any correlation call so no numpy/
    scipy warning can ever be emitted for a constant candidate.

    Shared across the package (CSCV aggregate correlations reuse it) so every
    correlation entry point applies the same proven predicate.
    """
    return float(np.ptp(column)) == 0.0 or float(column.std()) <= CONSTANT_STD_EPS


# Backwards-compatible private alias.
_is_constant = is_constant_series


def dependence_diagnostics(
    matrix: np.ndarray, candidate_ids: Sequence[str], threshold: float
) -> Dict[str, Any]:
    ids = list(candidate_ids)
    constant_mask = [_is_constant(matrix[:, j]) for j in range(len(ids))]
    constant = [ids[j] for j in range(len(ids)) if constant_mask[j]]
    active = [j for j in range(len(ids)) if not constant_mask[j]]
    pairs: List[Dict[str, Any]] = []
    abs_values: List[float] = []
    if len(active) >= 2:
        corr = np.corrcoef(matrix[:, active], rowvar=False)
        for a in range(len(active)):
            for b in range(a + 1, len(active)):
                r = float(corr[a, b])
                if not math.isfinite(r):
                    continue
                abs_values.append(abs(r))
                if abs(r) >= threshold:
                    pairs.append({
                        "candidate_a": ids[active[a]],
                        "candidate_b": ids[active[b]],
                        "correlation": round(r, 6),
                        "abs_correlation": round(abs(r), 6),
                    })
    uf = _UnionFind(len(ids))
    index = {cid: i for i, cid in enumerate(ids)}
    for p in pairs:
        uf.union(index[p["candidate_a"]], index[p["candidate_b"]])
    roots: Dict[int, List[str]] = {}
    for i, cid in enumerate(ids):
        roots.setdefault(uf.find(i), []).append(cid)
    clusters = [{"cluster_id": f"cluster-{k + 1}", "candidates": members,
                 "size": len(members)}
                for k, members in enumerate(
                    roots[r] for r in sorted(roots) if len(roots[r]) >= 2)]
    mean_abs = float(np.mean(abs_values)) if abs_values else None
    median_abs = float(np.median(abs_values)) if abs_values else None
    k_defined = len(active)
    if k_defined >= 2 and mean_abs is not None:
        effective = 1.0 + (k_defined - 1) * (1.0 - mean_abs)
        effective = float(min(float(k_defined), max(1.0, effective)))
        effective_note = (
            "approximate: K_eff = 1 + (K − 1)·(1 − mean|ρ|) over candidates "
            "with non-constant returns — a conservative interpolation, not an "
            "exact count"
        )
    else:
        effective = None
        effective_note = "needs at least 2 non-constant candidates"
    return {
        "threshold": threshold,
        "candidate_count": len(ids),
        "defined_candidate_count": k_defined,
        "constant_candidates": constant,
        "constant_note": ("constant-return candidates have undefined correlation "
                          "and are excluded" if constant else None),
        "mean_abs_correlation": mean_abs,
        "median_abs_correlation": median_abs,
        "high_correlation_pairs": pairs,
        "clusters": clusters,
        "effective_trials_estimate": effective,
        "effective_trials_note": effective_note,
    }


__all__ = [
    "MIN_DEPENDENCE_THRESHOLD", "MAX_DEPENDENCE_THRESHOLD",
    "DEFAULT_DEPENDENCE_THRESHOLD", "CONSTANT_STD_EPS", "DependenceError",
    "is_constant_series", "validate_dependence_config", "dependence_diagnostics",
]
