"""
Volatility and correlation stress with PSD validation (v1).

The baseline covariance is ALWAYS retained; the stressed covariance is
rebuilt from stressed volatilities and a stated correlation matrix,
validated with the shared Phase 56 utilities, repaired only under the
scenario's explicit policy (never silently), and fingerprinted
separately.  Correlation stress modes (hand-computable):

* ``uniform_multiplier`` — off-diagonals × m, clamped to [−1, 1]
* ``additive``           — off-diagonals + a, clamped to [−1, 1]
* ``toward_one``         — rho + alpha × (1 − rho), alpha ∈ [0, 1]
* ``supplied``           — an explicit full matrix in asset order

The diagonal stays exactly one, symmetry is preserved, and any clamping
is disclosed.  Supplied matrices must already be symmetric with a unit
diagonal (scenario validation rejects anything else — the defensive
symmetrization below never fires on validated input).  After an explicit
repair the disclosed vols/correlation describe the FINAL matrix, with the
requested values kept under separate keys.  Nothing here predicts future
volatility or correlation.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from app.portfolio_diagnostics.covariance import (
    correlation_from_covariance,
    repair_matrix,
    validate_matrix,
)


def stressed_volatilities(base_vols: np.ndarray, asset_ids: List[str],
                          vol_stress: Optional[Dict[str, Any]]
                          ) -> Dict[str, Any]:
    """Apply the explicit volatility stress; baseline retained by caller."""
    if vol_stress is None:
        return {"vols": base_vols.copy(), "applied": False, "clamped": []}
    stressed = base_vols.copy()
    clamped: List[str] = []
    if vol_stress["mode"] == "multiplicative":
        uniform = vol_stress.get("multiplier")
        per_asset = vol_stress.get("multipliers") or {}
        for i, aid in enumerate(asset_ids):
            m = per_asset.get(aid, uniform)
            if m is not None:
                stressed[i] = base_vols[i] * m
    else:  # additive in per-period volatility units
        add = vol_stress["value"]
        for i, aid in enumerate(asset_ids):
            value = base_vols[i] + add
            if value < 0:
                value = 0.0
                clamped.append(aid)
            stressed[i] = value
    return {"vols": stressed, "applied": True, "clamped": clamped}


def stressed_correlation(base_corr: np.ndarray,
                         corr_stress: Optional[Dict[str, Any]]
                         ) -> Dict[str, Any]:
    """Apply the explicit correlation stress mode; diagonal stays one."""
    if corr_stress is None:
        return {"matrix": base_corr.copy(), "applied": False,
                "clamped": False}
    n = base_corr.shape[0]
    mode = corr_stress["mode"]
    if mode == "supplied":
        matrix = np.array(corr_stress["matrix"], dtype=float)
        matrix = 0.5 * (matrix + matrix.T)
        np.fill_diagonal(matrix, 1.0)
        return {"matrix": matrix, "applied": True, "clamped": False}
    off_mask = ~np.eye(n, dtype=bool)
    stressed = base_corr.copy()
    if mode == "uniform_multiplier":
        stressed[off_mask] = base_corr[off_mask] * corr_stress["value"]
    elif mode == "additive":
        stressed[off_mask] = base_corr[off_mask] + corr_stress["value"]
    else:  # toward_one: rho + alpha * (1 - rho)
        alpha = corr_stress["alpha"]
        stressed[off_mask] = (base_corr[off_mask]
                              + alpha * (1.0 - base_corr[off_mask]))
    clipped = np.clip(stressed, -1.0, 1.0)
    clamped = bool(np.any(clipped != stressed))
    clipped = 0.5 * (clipped + clipped.T)
    np.fill_diagonal(clipped, 1.0)
    return {"matrix": clipped, "applied": True, "clamped": clamped}


def build_stressed_covariance(base_cov: np.ndarray, asset_ids: List[str],
                              vol_stress: Optional[Dict[str, Any]],
                              corr_stress: Optional[Dict[str, Any]]
                              ) -> Dict[str, Any]:
    """Rebuild Σ_stressed = D(σ*) · R* · D(σ*); validate; explicit repair.

    Returns matrix (or None), the validation report before/after repair,
    the repair record, and disclosure flags.  A non-PSD stressed matrix
    under repair policy ``none`` yields matrix None with the honest
    reason — never a silent acceptance or repair.
    """
    base_corr = correlation_from_covariance(base_cov)
    if base_corr is None:
        return {"matrix": None, "report": None, "repair": None,
                "reason": "a zero-variance asset leaves the baseline "
                          "correlation undefined; volatility/correlation "
                          "stress is unavailable",
                "vol_result": None, "corr_result": None}
    base_vols = np.sqrt(np.diag(base_cov))
    vol_result = stressed_volatilities(base_vols, asset_ids, vol_stress)
    corr_result = stressed_correlation(base_corr, corr_stress)
    vols = vol_result["vols"]
    stressed = corr_result["matrix"] * np.outer(vols, vols)
    stressed = 0.5 * (stressed + stressed.T)
    report = validate_matrix(stressed)
    repair_policy = {"repair": "none"}
    if corr_stress is not None:
        repair_policy = {"repair": corr_stress.get("repair", "none"),
                         "eigenvalue_floor":
                             corr_stress.get("eigenvalue_floor", 1e-10)}
    repair = repair_matrix(stressed, repair_policy)
    if repair["repaired"]:
        stressed = repair["matrix"]
        report_after = validate_matrix(stressed)
    else:
        report_after = report
    if not report_after.get("psd", False):
        return {"matrix": None, "report": report, "report_after": report_after,
                "repair": {k: v for k, v in repair.items() if k != "matrix"},
                "reason": ("stressed covariance is not positive semidefinite "
                           f"and the repair policy is "
                           f"{repair_policy['repair']!r} — no silent repair"),
                "vol_result": {k: v for k, v in vol_result.items()
                               if k != "vols"},
                "corr_result": {k: v for k, v in corr_result.items()
                                if k != "matrix"}}
    # the DISCLOSED vols/correlation always describe the FINAL matrix (a
    # spectral repair rewrites both the diagonal and the off-diagonals, so
    # disclosing the requested values would misdescribe the risk inputs)
    effective_vols = np.sqrt(np.clip(np.diag(stressed), 0.0, None))
    effective_corr = correlation_from_covariance(stressed)
    return {"matrix": stressed, "report": report, "report_after": report_after,
            "repair": {k: v for k, v in repair.items() if k != "matrix"},
            "reason": None,
            "stressed_vols": [float(v) for v in effective_vols],
            "stressed_correlation": (
                [[round(float(v), 10) for v in row] for row in effective_corr]
                if effective_corr is not None else None),
            "requested_vols": [float(v) for v in vols],
            "requested_correlation": [[round(float(v), 10) for v in row]
                                      for row in corr_result["matrix"]],
            "vol_result": {k: v for k, v in vol_result.items() if k != "vols"},
            "corr_result": {k: v for k, v in corr_result.items()
                            if k != "matrix"}}
