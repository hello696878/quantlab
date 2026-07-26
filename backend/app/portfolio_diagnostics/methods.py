"""
Portfolio-construction methods (v1).

Implemented: ``user_supplied``, ``equal_weight``, ``inverse_volatility``,
``erc`` (equal/targeted risk contribution via the log-barrier convex
formulation), ``min_variance`` (scipy SLSQP).  Deferred honestly:
``maximum diversification`` (no coherent v1 formulation without a second
solver pass under the current constraint model) and mean-variance
expected-return optimization (no robust explicit expected-return model
exists in this repository).  No placeholder methods exist.

Every solver is deterministic (fixed initialization, bounded iterations,
explicit tolerances), reports its convergence status and residual, and is
followed by an INDEPENDENT constraint re-check in the service layer.  A
failed solve returns a failed status with weights unavailable — never a
silently degraded portfolio.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.optimize import minimize

METHODS = ("user_supplied", "equal_weight", "inverse_volatility", "erc",
           "min_variance")
DEFERRED_METHODS = {
    "max_diversification": "deferred in v1: no coherent formulation under "
                           "the current constraint model without a second "
                           "solver pass",
    "mean_variance": "not implemented in v1: no robust explicit "
                     "expected-return model exists in this repository",
}
NORMALIZATION_POLICIES = ("sum_to_one", "net_target", "gross_target",
                          "cash_residual", "none")

ERC_MAX_ITERATIONS = 2000
ERC_DEFAULT_TOLERANCE = 1e-6
MINVAR_MAX_ITERATIONS = 500
MINVAR_FTOL = 1e-12
DEFAULT_VOLATILITY_FLOOR = None  # explicit opt-in only


class MethodError(ValueError):
    """Raised for invalid method configuration."""


def normalize_weights(raw: Dict[str, float], policy: str,
                      *, net_target: float = 1.0,
                      gross_target: float = 1.0) -> Dict[str, Any]:
    """Apply the EXPLICIT normalization policy (§ weight normalization).

    Returns ``{"weights", "raw_weights", "policy", "residual", "status",
    "reason"}`` — raw weights are always preserved, nothing is silently
    converted (a long-short input under ``sum_to_one`` with a non-positive
    raw sum is unavailable, never flipped long-only).
    """
    if policy not in NORMALIZATION_POLICIES:
        raise MethodError(
            f"normalization policy must be one of "
            f"{', '.join(NORMALIZATION_POLICIES)}")
    raw_out = dict(raw)
    if policy == "none":
        return {"weights": dict(raw), "raw_weights": raw_out,
                "policy": policy, "residual": None, "status": "available",
                "reason": None}
    total = sum(raw.values())
    gross = sum(abs(v) for v in raw.values())
    if policy == "sum_to_one":
        if total <= 0:
            return {"weights": None, "raw_weights": raw_out, "policy": policy,
                    "residual": None, "status": "unavailable",
                    "reason": "sum_to_one requires a positive raw weight sum "
                              "(long-short inputs are never silently "
                              "converted to long-only)"}
        return {"weights": {k: v / total for k, v in raw.items()},
                "raw_weights": raw_out, "policy": policy, "residual": 0.0,
                "status": "available", "reason": None}
    if policy == "net_target":
        if abs(total) < 1e-12:
            return {"weights": None, "raw_weights": raw_out, "policy": policy,
                    "residual": None, "status": "unavailable",
                    "reason": "net_target normalization needs a non-zero raw "
                              "net exposure"}
        scale = net_target / total
        return {"weights": {k: v * scale for k, v in raw.items()},
                "raw_weights": raw_out, "policy": policy, "residual": 0.0,
                "status": "available", "reason": None}
    if policy == "gross_target":
        if gross <= 0:
            return {"weights": None, "raw_weights": raw_out, "policy": policy,
                    "residual": None, "status": "unavailable",
                    "reason": "gross_target normalization needs a positive "
                              "raw gross exposure"}
        scale = gross_target / gross
        return {"weights": {k: v * scale for k, v in raw.items()},
                "raw_weights": raw_out, "policy": policy, "residual": 0.0,
                "status": "available", "reason": None}
    # cash_residual: no scaling; the un-invested remainder is explicit.
    # BOTH net and gross are bounded by 1 so the "no hidden leverage"
    # promise holds for long-short inputs too.
    residual = 1.0 - total
    if residual < -1e-9 or gross > 1.0 + 1e-9:
        return {"weights": None, "raw_weights": raw_out, "policy": policy,
                "residual": residual, "status": "unavailable",
                "reason": "cash_residual requires net AND gross exposure of "
                          "at most 1 (no hidden leverage)"}
    return {"weights": dict(raw), "raw_weights": raw_out, "policy": policy,
            "residual": residual, "status": "available", "reason": None}


def equal_weight(asset_ids: List[str], excluded: List[str],
                 *, target_sum: float = 1.0) -> Dict[str, Any]:
    """1/N over eligible assets (long-only reference; excluded assets 0)."""
    eligible = [a for a in asset_ids if a not in excluded]
    if not eligible:
        return {"weights": None, "solver": {"status": "failed",
                "reason": "zero eligible assets"}}
    w = target_sum / len(eligible)
    weights = {a: (w if a in eligible else 0.0) for a in asset_ids}
    return {"weights": weights,
            "solver": {"status": "closed_form", "iterations": 0,
                       "residual": 0.0, "reason": None}}


def inverse_volatility(asset_ids: List[str], vols: Dict[str, float],
                       excluded: List[str], *,
                       volatility_floor: Optional[float] = None,
                       target_sum: float = 1.0) -> Dict[str, Any]:
    """w_i ∝ 1/σ_i over eligible assets with a VISIBLE optional floor.

    A zero/near-zero volatility without a configured floor makes that
    asset unavailable (reported); with a floor, σ is clamped upward at the
    floor and the clamp is recorded — never hidden.
    """
    raw: Dict[str, float] = {}
    unavailable: List[Dict[str, str]] = []
    floored: List[str] = []
    for a in asset_ids:
        if a in excluded:
            continue
        sigma = vols.get(a)
        if sigma is None or not math.isfinite(sigma):
            unavailable.append({"asset_id": a,
                                "reason": "volatility unavailable"})
            continue
        if sigma <= 0 or (volatility_floor is not None
                          and sigma < volatility_floor):
            if volatility_floor is None:
                unavailable.append({
                    "asset_id": a,
                    "reason": "zero or negative volatility with no "
                              "configured floor"})
                continue
            sigma = volatility_floor
            floored.append(a)
        inv = 1.0 / sigma
        if not math.isfinite(inv):  # subnormal sigma would overflow 1/sigma
            unavailable.append({"asset_id": a,
                                "reason": "volatility too small; inverse "
                                          "overflows"})
            continue
        raw[a] = inv
    if not raw:
        return {"weights": None, "unavailable_assets": unavailable,
                "floored_assets": floored,
                "solver": {"status": "failed",
                           "reason": "no asset has a usable volatility"}}
    total = sum(raw.values())
    weights = {a: (raw.get(a, 0.0) / total * target_sum) for a in asset_ids}
    return {"weights": weights, "unavailable_assets": unavailable,
            "floored_assets": floored,
            "solver": {"status": "closed_form", "iterations": 0,
                       "residual": 0.0, "reason": None}}


def erc(cov: np.ndarray, asset_ids: List[str],
        budgets: Optional[Dict[str, float]] = None, *,
        tolerance: float = ERC_DEFAULT_TOLERANCE,
        max_iterations: int = ERC_MAX_ITERATIONS) -> Dict[str, Any]:
    """Risk budgeting via the log-barrier convex formulation (long-only).

    Solves ``min 0.5 wᵀΣw − Σ b_i ln(w_i)`` (deterministic L-BFGS-B with
    the analytic gradient ``Σw − b/w``, equal-weight initialization,
    bounded iterations) and normalizes to sum 1: at the optimum the
    percentage risk contributions equal the budgets.  Requires a PSD
    covariance and positive budgets summing to one.  Failure returns a
    failed status with weights unavailable; the residual
    ``max_i |PCR_i − b_i|`` is always reported.
    """
    n = len(asset_ids)
    if budgets is None:
        b = np.full(n, 1.0 / n)
    else:
        b = np.array([budgets.get(a, 0.0) for a in asset_ids], dtype=float)
        if np.any(~np.isfinite(b)) or np.any(b <= 0):
            raise MethodError("ERC risk budgets must be finite and positive")
        if abs(float(b.sum()) - 1.0) > 1e-6:
            raise MethodError("ERC risk budgets must sum to one")
    diag = np.diag(cov)
    if np.any(diag <= 0):
        return {"weights": None,
                "solver": {"status": "failed", "iterations": 0,
                           "residual": None,
                           "reason": "an asset has zero variance; the "
                                     "log-barrier problem is unbounded"}}

    def objective(w: np.ndarray):
        return 0.5 * float(w @ cov @ w) - float(b @ np.log(w)), cov @ w - b / w

    x0 = np.full(n, 1.0 / n)
    result = minimize(objective, x0, jac=True, method="L-BFGS-B",
                      bounds=[(1e-9, None)] * n,
                      options={"maxiter": max_iterations, "ftol": 1e-15,
                               "gtol": 1e-12})
    w = result.x / result.x.sum()
    sigma_p = math.sqrt(max(float(w @ cov @ w), 0.0))
    if sigma_p <= 0:
        return {"weights": None,
                "solver": {"status": "failed",
                           "iterations": int(result.nit),
                           "residual": None,
                           "reason": "zero portfolio volatility"}}
    pcr = (w * (cov @ w)) / (sigma_p ** 2)
    residual = float(np.max(np.abs(pcr - b)))
    # the convergence claim is the RESIDUAL, not the optimizer flag alone;
    # the loose band is capped absolutely so it can never become vacuous
    loose_band = min(max(tolerance, 1e-8) * 100, 1e-3)
    converged = bool(result.success) and residual <= loose_band
    status = "converged" if (residual <= tolerance) else (
        "converged_loose" if converged else "failed")
    if status == "failed":
        return {"weights": None,
                "solver": {"status": "failed", "iterations": int(result.nit),
                           "residual": residual,
                           "reason": "risk-contribution residual "
                                     f"{residual:.2e} above tolerance"}}
    return {"weights": {a: float(w[i]) for i, a in enumerate(asset_ids)},
            "solver": {"status": status, "iterations": int(result.nit),
                       "residual": residual, "tolerance": tolerance,
                       "reason": None}}


def min_variance(cov: np.ndarray, asset_ids: List[str],
                 constraints: Dict[str, Any], *,
                 asset_groups: Optional[Dict[str, Optional[str]]] = None,
                 max_iterations: int = MINVAR_MAX_ITERATIONS) -> Dict[str, Any]:
    """Minimize wᵀΣw under the configured bounds (deterministic SLSQP).

    Equal-weight initialization, explicit maxiter/ftol, sum-to-target
    equality, per-asset bounds incl. frozen (fixed) and excluded (zero)
    assets, and long-only group caps as inequalities.  Gross-exposure
    limits for long-short configurations are validated post-solve (the
    non-smooth |w| term is not given to SLSQP — documented).  The solver
    flag is reported; constraints are independently re-checked by the
    caller regardless.
    """
    n = len(asset_ids)
    target = constraints.get("net_exposure_target")
    if target is None:
        target = 1.0
    bounds = []
    for a in asset_ids:
        if a in constraints["excluded_assets"]:
            bounds.append((0.0, 0.0))
        elif a in constraints["frozen_weights"]:
            fw = constraints["frozen_weights"][a]
            bounds.append((fw, fw))
        else:
            lo = constraints["min_weight"]
            hi = constraints["max_weight"]
            if constraints["long_only"]:
                lo = max(lo, 0.0)
            bounds.append((lo, hi))
    cons: List[Dict[str, Any]] = [
        {"type": "eq", "fun": lambda w: float(np.sum(w)) - target}]
    if constraints["long_only"] and asset_groups:
        # long-only: group |w| exposure equals the plain sum, so caps and
        # minimums are smooth linear inequalities.  Long-short group caps
        # involve |w| and are validated post-solve instead (documented).
        for g, cap in constraints["group_caps"].items():
            idx = [i for i, a in enumerate(asset_ids)
                   if asset_groups.get(a) == g]
            if idx:
                cons.append({"type": "ineq",
                             "fun": lambda w, idx=idx, cap=cap:
                                 cap - float(np.sum(w[idx]))})
        for g, mn in constraints["group_minimums"].items():
            idx = [i for i, a in enumerate(asset_ids)
                   if asset_groups.get(a) == g]
            if idx:
                cons.append({"type": "ineq",
                             "fun": lambda w, idx=idx, mn=mn:
                                 float(np.sum(w[idx])) - mn})
    result = minimize(lambda w: float(w @ cov @ w), np.full(n, 1.0 / n),
                      method="SLSQP", bounds=bounds, constraints=cons,
                      options={"maxiter": max_iterations, "ftol": MINVAR_FTOL})
    if not result.success or np.any(~np.isfinite(result.x)):
        return {"weights": None,
                "solver": {"status": "failed", "iterations": int(result.nit),
                           "residual": None,
                           "reason": f"SLSQP did not converge: {result.message}"}}
    # residual = the sum-to-target equality slack (NOT the objective — the
    # minimized variance is reported separately as objective_value)
    return {"weights": {a: float(result.x[i]) for i, a in enumerate(asset_ids)},
            "solver": {"status": "converged", "iterations": int(result.nit),
                       "residual": abs(float(np.sum(result.x)) - target),
                       "objective_value": float(result.fun), "reason": None}}
