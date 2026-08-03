"""
Redundancy, matrix concentration and clustering (Phase 61, v1).

The correlation matrix used here is built ONLY from strict-intersection
observations, so every cell shares one universe; pairwise-complete rows
never enter a matrix.  From a complete, symmetric matrix the lab reports
matrix rank, condition number, eigenvalue concentration and

    effective_count = (sum eigenvalues)^2 / sum(eigenvalues^2)

— described everywhere as a MATRIX-CONCENTRATION diagnostic, never as the
true number of independent signals.  Negative numerical eigenvalues are
handled under an explicit tolerance; the matrix is never silently repaired.

Similarity distance:

    distance_ij = sqrt(0.5 * (1 - correlation_ij))

bounded in [0, 1] for correlations in [-1, 1]; an unavailable correlation
yields an unavailable distance, never a fabricated zero.  Hierarchical
clustering uses the already-approved scipy stack
(`scipy.cluster.hierarchy`, single/complete/average linkage) and runs only
when EVERY pairwise distance is available; the flat-cluster threshold is
explicit, no cluster count is selected automatically, and no representative
signal is chosen or removed.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.cluster import hierarchy as sp_hierarchy

EIGENVALUE_TOLERANCE = 1e-10
DISTANCE_NUMERICAL_TOLERANCE = 1e-12

LINKAGE_METHODS = ("single", "complete", "average")


class RedundancyError(ValueError):
    """Invalid redundancy configuration (HTTP 422)."""


def validate_clustering(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise RedundancyError("clustering settings must be an object")
    unknown = sorted(set(raw) - {"linkage", "threshold"})
    if unknown:
        raise RedundancyError(f"unknown clustering keys: {unknown}")
    linkage = raw.get("linkage", "average")
    if linkage not in LINKAGE_METHODS:
        raise RedundancyError(
            f"clustering linkage must be one of {list(LINKAGE_METHODS)}")
    threshold = raw.get("threshold")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) \
            or not (0.0 < float(threshold) <= 1.0):
        raise RedundancyError(
            "clustering threshold must be an explicit number in (0, 1] — "
            "no cluster count is ever selected automatically")
    return {"linkage": linkage, "threshold": float(threshold)}


def correlation_matrix(pair_rows: Sequence[Dict[str, Any]],
                       signal_ids: Sequence[str], *,
                       method: str) -> Dict[str, Any]:
    """Symmetric matrix (diagonal exactly 1.0) from strict-intersection rows.

    Cells whose pairwise correlation is unavailable are ``None`` and make
    the matrix incomplete; matrix-level diagnostics then become
    unavailable with that reason instead of silently imputing.
    """
    ordered = sorted(signal_ids)
    index = {signal_id: i for i, signal_id in enumerate(ordered)}
    n = len(ordered)
    cells: List[List[Optional[float]]] = \
        [[None] * n for _ in range(n)]
    for i in range(n):
        cells[i][i] = 1.0
    unavailable: List[Dict[str, Any]] = []
    for row in pair_rows:
        correlation = row["correlations"].get(method)
        i = index[row["signal_a"]]
        j = index[row["signal_b"]]
        if correlation and correlation["state"] == "available":
            value = float(correlation["statistic"])
            cells[i][j] = value
            cells[j][i] = value
        else:
            unavailable.append({
                "signal_a": row["signal_a"], "signal_b": row["signal_b"],
                "reason": (correlation or {}).get("reason")
                or "correlation unavailable",
            })
    return {"signal_ids": ordered, "method": method, "cells": cells,
            "unavailable_cells": unavailable,
            "complete": not unavailable}


def distance_matrix(matrix: Dict[str, Any]) -> Dict[str, Any]:
    """distance_ij = sqrt(0.5 * (1 - corr_ij)); unavailable stays None."""
    n = len(matrix["signal_ids"])
    cells: List[List[Optional[float]]] = [[None] * n for _ in range(n)]
    for i in range(n):
        cells[i][i] = 0.0
        for j in range(n):
            if i == j:
                continue
            correlation = matrix["cells"][i][j]
            if correlation is None:
                continue
            inner = 0.5 * (1.0 - float(correlation))
            if inner < 0:
                if inner < -DISTANCE_NUMERICAL_TOLERANCE:
                    # correlation above 1 beyond numerics — refuse silently
                    # clipping a real defect
                    continue
                inner = 0.0
            cells[i][j] = math.sqrt(inner)
    return {"signal_ids": matrix["signal_ids"],
            "formula": "sqrt(0.5 * (1 - correlation))",
            "correlation_method": matrix["method"],
            "cells": cells,
            "complete": all(cells[i][j] is not None
                            for i in range(n) for j in range(n)),
            "note": ("a correlation distance over this sample; it does not "
                     "measure true informational independence")}


def matrix_diagnostics(matrix: Dict[str, Any]) -> Dict[str, Any]:
    """Rank, condition number, eigenvalue concentration, effective count."""
    out: Dict[str, Any] = {
        "method": matrix["method"],
        "signal_count": len(matrix["signal_ids"]),
        "eigenvalues": None, "negative_eigenvalue_count": None,
        "matrix_rank": None, "condition_number": None,
        "condition_number_note": None,
        "eigenvalue_concentration_top": None,
        "effective_signal_count": None,
        "effective_signal_count_note": (
            "(sum eigenvalues)^2 / sum(eigenvalues^2) — a matrix-"
            "concentration diagnostic of THIS correlation matrix, not the "
            "true number of independent signals"),
        "psd_within_tolerance": None,
        "state": "unavailable", "reason": None,
        "warnings": [],
    }
    if not matrix["complete"]:
        out["reason"] = (f"{len(matrix['unavailable_cells'])} correlation "
                         f"cell(s) are unavailable, so matrix-level "
                         f"diagnostics are unavailable — nothing is imputed")
        return out
    array = np.asarray(
        [[float(v) for v in row] for row in matrix["cells"]],
        dtype=np.float64)
    if not np.allclose(array, array.T, atol=1e-12):
        out["reason"] = "the correlation matrix is not symmetric"
        return out
    eigenvalues = np.linalg.eigvalsh(array)
    out["eigenvalues"] = [float(v) for v in eigenvalues]
    negative = eigenvalues[eigenvalues < -EIGENVALUE_TOLERANCE]
    out["negative_eigenvalue_count"] = int(negative.size)
    out["psd_within_tolerance"] = bool(negative.size == 0)
    if negative.size:
        out["reason"] = (
            f"{negative.size} eigenvalue(s) are below the tolerance of "
            f"-{EIGENVALUE_TOLERANCE:g}; the matrix is not PSD and is NOT "
            f"silently repaired")
        return out
    clipped = np.clip(eigenvalues, 0.0, None)
    out["matrix_rank"] = int(np.sum(clipped > EIGENVALUE_TOLERANCE))
    if out["matrix_rank"] < len(matrix["signal_ids"]):
        out["warnings"].append(
            f"the correlation matrix is rank deficient (rank "
            f"{out['matrix_rank']} of {len(matrix['signal_ids'])})")
    smallest = float(clipped.min())
    largest = float(clipped.max())
    if smallest > EIGENVALUE_TOLERANCE:
        out["condition_number"] = largest / smallest
        if out["condition_number"] > 1e3:
            out["warnings"].append(
                "the correlation matrix is ill-conditioned (condition "
                f"number {out['condition_number']:.3g}) — a neutral "
                "numerical warning, not a universal rule")
    else:
        out["condition_number_note"] = (
            "unavailable: the smallest eigenvalue is zero within tolerance, "
            "so the condition number is undefined rather than infinite")
    total = float(clipped.sum())
    square_sum = float(np.sum(clipped ** 2))
    if square_sum > 0 and total > 0:
        out["effective_signal_count"] = total * total / square_sum
        out["eigenvalue_concentration_top"] = largest / total
        out["state"] = "available"
    else:
        out["reason"] = ("the eigenvalue sum is zero, so concentration is "
                         "undefined")
    return out


def redundancy_summary(pair_rows: Sequence[Dict[str, Any]],
                       agreement_rows: Sequence[Dict[str, Any]], *,
                       method: str,
                       signal_ids: Sequence[str]) -> Dict[str, Any]:
    """Descriptive scalar redundancy metrics over AVAILABLE pairs only."""
    absolutes: List[float] = []
    nearest: Dict[str, float] = {}
    available = 0
    for row in pair_rows:
        correlation = row["correlations"].get(method)
        if not correlation or correlation["state"] != "available":
            continue
        available += 1
        value = abs(float(correlation["statistic"]))
        absolutes.append(value)
        for signal_id in (row["signal_a"], row["signal_b"]):
            if value > nearest.get(signal_id, -1.0):
                nearest[signal_id] = value
    agreements = [row["exact_agreement_rate"] for row in agreement_rows
                  if row["state"] == "available"]
    signs = [row["sign_agreement_rate"] for row in pair_rows
             if row.get("sign_agreement_rate") is not None]
    out: Dict[str, Any] = {
        "method": method,
        "pair_count": len(pair_rows),
        "available_pair_count": available,
        "mean_absolute_correlation": None,
        "median_absolute_correlation": None,
        "max_absolute_correlation": None,
        "nearest_neighbour_similarity": [
            {"signal_id": signal_id,
             "max_absolute_correlation": nearest.get(signal_id)}
            for signal_id in sorted(signal_ids)],
        "average_exact_bucket_agreement": (
            float(np.mean(agreements)) if agreements else None),
        "average_sign_agreement": (
            float(np.mean(signs)) if signs else None),
        "note": ("descriptive similarity over this sample; no threshold "
                 "marks signals duplicates, and no level of correlation "
                 "proves shared or independent information"),
    }
    if absolutes:
        array = np.asarray(absolutes, dtype=np.float64)
        out["mean_absolute_correlation"] = float(np.mean(array))
        out["median_absolute_correlation"] = float(np.median(array))
        out["max_absolute_correlation"] = float(np.max(array))
    return out


def cluster(distance: Dict[str, Any],
            settings: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic hierarchical clustering; refuses incomplete matrices."""
    out: Dict[str, Any] = {
        "linkage": settings["linkage"],
        "threshold": settings["threshold"],
        "criterion": "distance",
        "merges": None, "clusters": None, "leaf_order": None,
        "cluster_count": None,
        "state": "unavailable", "reason": None,
        "note": ("clusters describe correlation distance under the "
                 "configured linkage and explicit threshold; no cluster "
                 "count is auto-selected, no representative signal is "
                 "chosen and no signal is removed"),
    }
    ids = distance["signal_ids"]
    n = len(ids)
    if not distance["complete"]:
        out["reason"] = ("at least one pairwise distance is unavailable; "
                         "clustering is refused rather than imputed")
        return out
    if n < 3:
        out["reason"] = "clustering needs at least 3 signals"
        return out
    condensed: List[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            condensed.append(float(distance["cells"][i][j]))
    linkage_matrix = sp_hierarchy.linkage(
        np.asarray(condensed, dtype=np.float64),
        method=settings["linkage"])
    flat = sp_hierarchy.fcluster(linkage_matrix,
                                 t=settings["threshold"],
                                 criterion="distance")
    leaves = sp_hierarchy.leaves_list(linkage_matrix)
    out["merges"] = [{
        "left": int(row[0]), "right": int(row[1]),
        "distance": float(row[2]), "size": int(row[3]),
    } for row in linkage_matrix]
    out["clusters"] = [{"signal_id": ids[i], "cluster": int(flat[i])}
                       for i in range(n)]
    out["leaf_order"] = [ids[int(i)] for i in leaves]
    out["cluster_count"] = int(len(set(int(c) for c in flat)))
    out["state"] = "available"
    return out


__all__ = [
    "EIGENVALUE_TOLERANCE", "DISTANCE_NUMERICAL_TOLERANCE",
    "LINKAGE_METHODS", "RedundancyError", "validate_clustering",
    "correlation_matrix", "distance_matrix", "matrix_diagnostics",
    "redundancy_summary", "cluster",
]
