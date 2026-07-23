"""
Aggregate and break-even diagnostics (v1).

Conventions (documented; nothing is silently zero-filled):

* Totals sum over all observations; per-component totals sum available
  component values only, with the unavailable count kept beside them.
* ``sharpe_like`` is mean / sample std (ddof=1) of per-observation values,
  never annualized, and requires n >= 2 with positive std.
* ``cost_fraction_of_gross`` divides total estimated cost by the magnitude
  of the gross total; a zero gross total makes it unavailable (no division
  by zero, no sign games).
* Neutral wording: observations that are gross-positive but net-nonpositive
  are counted as exactly that — they are not "failed trades".

Break-even diagnostics (exact formulas):

* aggregate break-even cost in bps of traded notional
  = gross_total / basis / 0.0001, where the basis is total traded notional
  (currency) for trade runs and total turnover for period runs (gross and
  cost are return fractions there, and return / turnover is exactly the
  per-traded-notional fraction); defined only when the gross total is
  positive and the basis is positive and covers every observation;
* mean break-even cost per trade = gross_total / n (gross_total > 0);
* maximum cost multiplier = gross_total / total_cost (both > 0) — the
  uniform scaling of all estimated costs at which the measured aggregate
  net result reaches zero;
* per-component break-even multiplier for component c with base cost > 0:
  (gross_total - (total_cost - cost_c)) / cost_c, unavailable when the
  other components meet or exceed the gross result (a break-even level
  at or below zero is never reported);
* break-even impact coefficient = configured coefficient x the impact
  break-even multiplier (the square-root model is linear in its
  coefficient).

Break-even values describe the measured sample under configured assumptions;
they are not claimed to be achievable in markets.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from app.cost_diagnostics.reconcile import COMPONENT_NAMES
from app.cost_diagnostics.units import BASIS_POINT


def _stats(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"mean": None, "median": None, "std": None,
                "sharpe_like": None, "positive_rate": None}
    arr = np.asarray(values, dtype=float)
    mean = float(np.mean(arr))
    median = float(np.median(arr))
    std = float(np.std(arr, ddof=1)) if arr.size >= 2 else None
    sharpe = None
    if std is not None and std > 0:
        sharpe = mean / std
    return {"mean": mean, "median": median, "std": std,
            "sharpe_like": sharpe,
            "positive_rate": float(np.mean(arr > 0))}


def aggregate_results(obs_results: List[Dict[str, Any]],
                      observation_type: str = "trade") -> Dict[str, Any]:
    """Aggregate per-observation reconciliation results (§ aggregates).

    ``total_cost`` and component totals are ``None`` (not 0.0) when no
    observation contributed a computed value — a missing cost is never
    presented as a zero cost.  For period runs the per-traded-notional
    ratios use total turnover as their denominator (cost and gross are
    return fractions there; return / turnover is exactly cost per unit of
    traded notional), and ratios are withheld when the denominator does not
    cover every observation.
    """
    n = len(obs_results)
    gross_values = [r["gross_value"] for r in obs_results]
    net_values = [r["net_value"] for r in obs_results if r["net_value"] is not None]
    gross_total = float(sum(gross_values)) if gross_values else 0.0
    net_total = float(sum(net_values)) if net_values else None
    cost_present = [r["total_cost"] for r in obs_results
                    if r["total_cost"] is not None]
    total_cost = float(sum(cost_present)) if cost_present else None
    component_totals: Dict[str, Optional[float]] = {}
    component_unavailable: Dict[str, int] = {}
    for name in COMPONENT_NAMES:
        present = [r["component_values"].get(name) for r in obs_results
                   if r["component_values"].get(name) is not None]
        component_totals[name] = float(sum(present)) if present else None
        component_unavailable[name] = sum(
            1 for r in obs_results if name in r.get("unavailable_components", []))

    notional_vals = [r.get("traded_notional") for r in obs_results
                     if r.get("traded_notional") is not None]
    total_notional = float(sum(notional_vals)) if notional_vals else None
    turnover_vals = [r.get("turnover") for r in obs_results
                     if r.get("turnover") is not None]
    total_turnover = float(sum(turnover_vals)) if turnover_vals else None

    # the denominator for "per unit of traded notional" ratios: currency
    # notional for trade runs; turnover for period runs (return space) —
    # only when it covers every observation, so partial coverage can never
    # silently inflate a ratio
    if observation_type == "period":
        basis_total = (total_turnover
                       if len(turnover_vals) == n and (total_turnover or 0) > 0
                       else None)
    else:
        basis_total = (total_notional
                       if len(notional_vals) == n and (total_notional or 0) > 0
                       else None)

    gp_nn = sum(1 for r in obs_results
                if r["gross_value"] > 0 and r["net_value"] is not None
                and r["net_value"] <= 0)
    unavailable_cost_count = sum(
        1 for r in obs_results if r.get("unavailable_components"))
    partial_count = sum(1 for r in obs_results
                        if r["completeness"] == "partial")
    gross_only_count = sum(1 for r in obs_results
                           if r["completeness"] == "gross_only")

    cost_fraction_of_gross = None
    if abs(gross_total) > 0 and total_cost is not None:
        cost_fraction_of_gross = total_cost / abs(gross_total)
    cost_fraction_of_notional = None
    if basis_total is not None and total_cost is not None:
        cost_fraction_of_notional = total_cost / basis_total

    return {
        "observation_count": n,
        "gross_total": gross_total,
        "net_total": net_total,
        "total_cost": total_cost,
        "component_totals": component_totals,
        "component_unavailable_counts": component_unavailable,
        "cost_fraction_of_gross_magnitude": cost_fraction_of_gross,
        "cost_fraction_of_traded_notional": cost_fraction_of_notional,
        "total_traded_notional": total_notional,
        "notional_observation_count": len(notional_vals),
        "total_turnover": total_turnover,
        "turnover_observation_count": len(turnover_vals),
        "notional_basis_total": basis_total,
        "gross_stats": _stats(gross_values),
        "net_stats": _stats(net_values),
        "net_observation_count": len(net_values),
        "gross_positive_net_nonpositive_count": gp_nn,
        "unavailable_cost_count": unavailable_cost_count,
        "partial_result_count": partial_count,
        "gross_only_count": gross_only_count,
    }


def breakeven_diagnostics(aggregates: Dict[str, Any],
                          impact_coefficient: Optional[float]
                          ) -> Dict[str, Any]:
    """Break-even diagnostics from run aggregates (formulas in module doc)."""
    gross_total = aggregates["gross_total"]
    total_cost = aggregates["total_cost"]
    # currency notional for trade runs, turnover for period runs; None when
    # the denominator does not cover every observation
    basis_total = aggregates.get("notional_basis_total")
    n = aggregates["observation_count"]
    out: Dict[str, Any] = {
        "note": ("break-even values describe the measured sample under "
                 "configured assumptions and are not claimed to be "
                 "achievable in markets"),
    }
    if gross_total <= 0:
        out["status"] = "unavailable"
        out["reason"] = ("gross result is non-positive; no positive cost "
                         "level reaches break-even")
        return out
    out["status"] = "available"
    out["mean_breakeven_cost_per_observation"] = gross_total / n
    if basis_total and basis_total > 0:
        out["aggregate_breakeven_bps_of_notional"] = (
            gross_total / basis_total / BASIS_POINT)
    else:
        out["aggregate_breakeven_bps_of_notional"] = None
        out["bps_reason"] = ("traded-notional basis missing, zero, or not "
                             "covering every observation")
    if total_cost and total_cost > 0:
        out["max_cost_multiplier"] = gross_total / total_cost
    else:
        out["max_cost_multiplier"] = None

    component_multipliers: Dict[str, Any] = {}
    totals = aggregates["component_totals"]
    for name in COMPONENT_NAMES:
        base = totals.get(name)
        if base is None or base <= 0:
            component_multipliers[name] = None
            continue
        others = sum(v for k, v in totals.items()
                     if k != name and v is not None)
        numerator = gross_total - others
        if numerator <= 0:
            component_multipliers[name] = {
                "multiplier": None,
                "reason": "other components meet or exceed the gross result",
            }
        else:
            m = numerator / base
            if not math.isfinite(m):
                component_multipliers[name] = {
                    "multiplier": None, "reason": "value is not finite"}
            else:
                component_multipliers[name] = {"multiplier": m, "reason": None}
    out["component_breakeven_multipliers"] = component_multipliers

    imp = component_multipliers.get("impact")
    if (impact_coefficient is not None and impact_coefficient > 0
            and isinstance(imp, dict) and imp.get("multiplier") is not None):
        out["breakeven_impact_coefficient"] = (
            impact_coefficient * imp["multiplier"])
    else:
        out["breakeven_impact_coefficient"] = None

    for key in ("mean_breakeven_cost_per_observation",
                "aggregate_breakeven_bps_of_notional", "max_cost_multiplier",
                "breakeven_impact_coefficient"):
        v = out.get(key)
        if v is not None and (not math.isfinite(v) or v < 0):
            out[key] = None
    return out
