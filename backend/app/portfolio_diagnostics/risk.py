"""
Portfolio risk, risk-budget, concentration and diversification
diagnostics (v1).  Exact formulas (documented, per-period, never
annualized):

    portfolio_variance   = wᵀΣw
    portfolio_volatility = sqrt(portfolio_variance)
    MCR_i = (Σw)_i / portfolio_volatility     (marginal contribution)
    CCR_i = w_i × MCR_i                       (component contribution)
    PCR_i = CCR_i / portfolio_volatility      (percentage contribution)

Identities checked within RISK_IDENTITY_TOLERANCE when volatility is
positive: Σ CCR_i == portfolio_volatility and Σ PCR_i == 1.  A
zero-volatility portfolio returns unavailable contributions; negative
contributions in long-short portfolios stay visible (never forced to
zero); asset ordering is preserved throughout.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

RISK_IDENTITY_TOLERANCE = 1e-8
BUDGET_DEFAULT_TOLERANCE = 0.05


def portfolio_risk(weights: List[float], cov: np.ndarray) -> Dict[str, Any]:
    w = np.asarray(weights, dtype=float)
    variance = float(w @ cov @ w)
    variance = max(variance, 0.0)
    volatility = math.sqrt(variance)
    out: Dict[str, Any] = {"variance": variance, "volatility": volatility}
    if volatility <= 0:
        out.update({"mcr": None, "ccr": None, "pcr": None,
                    "identity_ok": None,
                    "note": "zero portfolio volatility; risk contributions "
                            "are unavailable"})
        return out
    sigma_w = cov @ w
    mcr = sigma_w / volatility
    ccr = w * mcr
    pcr = ccr / volatility
    identity_ok = (abs(float(ccr.sum()) - volatility) <=
                   RISK_IDENTITY_TOLERANCE * max(1.0, volatility)
                   and abs(float(pcr.sum()) - 1.0) <= RISK_IDENTITY_TOLERANCE * 10)
    out.update({
        "mcr": [float(v) for v in mcr],
        "ccr": [float(v) for v in ccr],
        "pcr": [float(v) for v in pcr],
        "identity_ok": bool(identity_ok),
        "note": None,
    })
    return out


def budget_diagnostics(asset_ids: List[str], pcr: Optional[List[float]],
                       budgets: Optional[Dict[str, float]],
                       *, tolerance: float = BUDGET_DEFAULT_TOLERANCE
                       ) -> Dict[str, Any]:
    """Target-vs-measured risk-budget comparison with neutral states."""
    rows: List[Dict[str, Any]] = []
    if budgets is None or pcr is None:
        for i, a in enumerate(asset_ids):
            rows.append({
                "asset_id": a,
                "target_budget": None,
                "measured_pcr": None if pcr is None else pcr[i],
                "abs_difference": None, "signed_difference": None,
                "relative_difference": None, "state": "unavailable",
            })
        return {"rows": rows, "max_abs_deviation": None,
                "mean_abs_deviation": None, "rms_deviation": None,
                "within_tolerance_count": None, "tolerance": tolerance,
                "target_sum": None, "measured_sum":
                    None if pcr is None else float(sum(pcr))}
    deviations = []
    within = 0
    for i, a in enumerate(asset_ids):
        target = budgets.get(a, 0.0)
        measured = pcr[i]
        signed = measured - target
        rel = signed / target if target != 0 else None
        state = ("within configured tolerance" if abs(signed) <= tolerance
                 else "outside configured tolerance")
        if abs(signed) <= tolerance:
            within += 1
        deviations.append(abs(signed))
        rows.append({
            "asset_id": a, "target_budget": target, "measured_pcr": measured,
            "abs_difference": abs(signed), "signed_difference": signed,
            "relative_difference": rel, "state": state,
        })
    dev = np.asarray(deviations)
    return {
        "rows": rows,
        "max_abs_deviation": float(dev.max()),
        "mean_abs_deviation": float(dev.mean()),
        "rms_deviation": float(np.sqrt(np.mean(dev ** 2))),
        "within_tolerance_count": within,
        "tolerance": tolerance,
        "target_sum": float(sum(budgets.get(a, 0.0) for a in asset_ids)),
        "measured_sum": float(sum(pcr)),
    }


def concentration_diagnostics(asset_ids: List[str], weights: List[float],
                              pcr: Optional[List[float]],
                              cov: np.ndarray) -> Dict[str, Any]:
    """Weight/risk concentration + correlation + diversification ratio.

    Weight concentration uses ABSOLUTE-weight shares (documented for
    long-short portfolios); risk-contribution concentration uses
    |CCR|-derived shares.  The diversification ratio is
    Σ_i |w_i| σ_i / portfolio_volatility — descriptive only; a higher
    value never guarantees diversification or safety.
    """
    w = np.asarray(weights, dtype=float)
    gross = float(np.abs(w).sum())
    out: Dict[str, Any] = {}
    if gross <= 0:
        out.update({"weight_hhi": None, "effective_positions": None,
                    "max_abs_weight": None, "top3_abs_weight_share": None})
    else:
        shares = np.abs(w) / gross
        hhi = float(np.sum(shares ** 2))
        out["weight_hhi"] = hhi
        out["effective_positions"] = 1.0 / hhi if hhi > 0 else None
        out["max_abs_weight"] = float(np.abs(w).max())
        out["top3_abs_weight_share"] = float(
            np.sort(shares)[::-1][:3].sum())
    if pcr is not None:
        # |PCR| shares equal |CCR| shares exactly (PCR = CCR / sigma, and
        # the constant cancels in the normalization)
        pcr_abs = np.abs(np.asarray(pcr, dtype=float))
        total = float(pcr_abs.sum())
        if total > 0:
            r_shares = pcr_abs / total
            r_hhi = float(np.sum(r_shares ** 2))
            out["risk_contribution_hhi"] = r_hhi
            out["effective_risk_contributors"] = 1.0 / r_hhi
        else:
            out["risk_contribution_hhi"] = None
            out["effective_risk_contributors"] = None
    else:
        out["risk_contribution_hhi"] = None
        out["effective_risk_contributors"] = None

    diag = np.diag(cov)
    n = len(asset_ids)
    if np.all(diag > 0) and n >= 2:
        std = np.sqrt(diag)
        # clip to [-1, 1] so fp noise on near-collinear assets can never
        # report a correlation above one
        corr = np.clip(cov / np.outer(std, std), -1.0, 1.0)
        off = corr[np.triu_indices(n, k=1)]
        out["avg_pairwise_correlation"] = float(np.mean(off))
        out["median_pairwise_correlation"] = float(np.median(off))
        out["max_pairwise_correlation"] = float(np.max(off))
        variance = float(w @ cov @ w)
        volatility = math.sqrt(max(variance, 0.0))
        weighted_vol = float(np.abs(w) @ std)
        out["diversification_ratio"] = (
            weighted_vol / volatility if volatility > 0 else None)
    else:
        out["avg_pairwise_correlation"] = None
        out["median_pairwise_correlation"] = None
        out["max_pairwise_correlation"] = None
        out["diversification_ratio"] = None
    return out
