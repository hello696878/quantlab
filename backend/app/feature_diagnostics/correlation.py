"""
Bounded correlated-feature diagnostics (correlation ≠ causation, and
correlated features are never removed automatically — groups are shown so
split/masked importance can be read honestly).

Pearson (numpy) or Spearman (scipy) over the documented sample subset (all
normalized samples, features only — the target is never included).  Constant
features have undefined correlation and are excluded with a warning.  Groups
are deterministic connected components of the |r| ≥ threshold graph, ordered
by declared feature order.  Bounded by MAX_FEATURES = 32 (≤ 496 pairs).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as sp_stats

CORRELATION_METHODS = ("pearson", "spearman")
MIN_CORRELATION_THRESHOLD = 0.1
MAX_CORRELATION_THRESHOLD = 0.999
DEFAULT_CORRELATION_THRESHOLD = 0.8


class CorrelationError(ValueError):
    """Invalid correlation configuration (HTTP 422)."""


def validate_correlation_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    config = config or {}
    method = config.get("method", "pearson")
    if method not in CORRELATION_METHODS:
        raise CorrelationError(f"correlation method must be one of {CORRELATION_METHODS}")
    threshold = config.get("threshold", DEFAULT_CORRELATION_THRESHOLD)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) \
            or not math.isfinite(threshold) \
            or not (MIN_CORRELATION_THRESHOLD <= float(threshold) <= MAX_CORRELATION_THRESHOLD):
        raise CorrelationError(
            "correlation threshold must be a finite number in "
            f"[{MIN_CORRELATION_THRESHOLD}, {MAX_CORRELATION_THRESHOLD}]"
        )
    return {"method": method, "threshold": float(threshold)}


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
            # deterministic: smaller index becomes root
            if ri < rj:
                self.parent[rj] = ri
            else:
                self.parent[ri] = rj


def correlation_diagnostics(
    X: np.ndarray,
    feature_names: Sequence[str],
    method: str,
    threshold: float,
    importance_by_feature: Optional[Dict[str, Optional[float]]] = None,
) -> Dict[str, Any]:
    names = list(feature_names)
    stds = X.std(axis=0)
    constant = [names[j] for j in range(len(names)) if float(stds[j]) == 0.0]
    active = [j for j in range(len(names)) if float(stds[j]) > 0.0]
    pairs: List[Dict[str, Any]] = []
    matrix: Optional[np.ndarray] = None
    if len(active) >= 2:
        sub = X[:, active]
        if method == "pearson":
            matrix = np.corrcoef(sub, rowvar=False)
        else:
            stat = np.asarray(sp_stats.spearmanr(sub).statistic)
            if stat.ndim == 0:  # scipy returns a scalar for exactly 2 columns
                r = float(stat)
                matrix = np.array([[1.0, r], [r, 1.0]])
            else:
                matrix = stat
        for a in range(len(active)):
            for b in range(a + 1, len(active)):
                r = float(matrix[a, b])
                if not math.isfinite(r):
                    continue
                if abs(r) >= threshold:
                    pairs.append({
                        "feature_a": names[active[a]],
                        "feature_b": names[active[b]],
                        "correlation": round(r, 6),
                        "abs_correlation": round(abs(r), 6),
                        "sign": 1 if r > 0 else -1,
                    })
    uf = _UnionFind(len(names))
    index = {n: i for i, n in enumerate(names)}
    for p in pairs:
        uf.union(index[p["feature_a"]], index[p["feature_b"]])
    roots: Dict[int, List[str]] = {}
    for i, n in enumerate(names):
        roots.setdefault(uf.find(i), []).append(n)
    groups: List[Dict[str, Any]] = []
    gid = 0
    for root in sorted(roots):
        members = roots[root]
        if len(members) < 2:
            continue
        gid += 1
        member_set = set(members)
        group_pairs = [p for p in pairs
                       if p["feature_a"] in member_set and p["feature_b"] in member_set]
        combined = None
        if importance_by_feature is not None:
            values = [importance_by_feature.get(m) for m in members]
            defined = [v for v in values if v is not None]
            combined = float(sum(defined)) if defined else None
        groups.append({
            "group_id": f"group-{gid}",
            "features": members,
            "size": len(members),
            "max_abs_correlation": max(p["abs_correlation"] for p in group_pairs),
            "pairs": group_pairs,
            "combined_mean_importance": combined,
        })
    return {
        "method": method,
        "threshold": threshold,
        "sample_basis": "all normalized samples (features only; target excluded)",
        "constant_features": constant,
        "constant_feature_warning": (
            "constant features have undefined correlation and were excluded"
            if constant else None
        ),
        "pair_count": len(pairs),
        "pairs": pairs,
        "groups": groups,
    }


__all__ = [
    "CORRELATION_METHODS", "MIN_CORRELATION_THRESHOLD",
    "MAX_CORRELATION_THRESHOLD", "DEFAULT_CORRELATION_THRESHOLD",
    "CorrelationError", "validate_correlation_config", "correlation_diagnostics",
]
