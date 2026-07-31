"""
Transaction-cost mapping for the neutral signal-sorted reference (v1).

A linked Phase 55 cost model is read READ-ONLY (fingerprint pinned) and
mapped onto the reference's per-rebalance turnover at an EXPLICIT reference
notional.  Only the notional-proportional components can be computed
without per-observation inputs:

* commission ``bps_of_notional``  — per side, both sides of a rebalance
* spread ``fixed_bps``            — configured fraction of the quoted
                                    spread per marketable execution
* slippage ``fixed_bps_per_side`` — per side

Every other configured model (monetary per-order/per-contract commissions,
price-based spreads, supplied slippage, and every impact model) needs
per-observation inputs — order counts, tick sizes, ADV, volatility — that a
bucket reference does not hold, so those components are **unavailable with
that reason**.  A missing input is never treated as zero, there is no
zero-cost fallback, fixed and scalable components are labelled, and gross
and cost-adjusted results stay separate.  Nothing is submitted back to the
Cost Diagnostics lab.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

MIN_REFERENCE_NOTIONAL = 1_000.0
MAX_REFERENCE_NOTIONAL = 1_000_000_000.0

COST_COMPONENTS = ("commission", "spread", "slippage", "impact")


class CostError(ValueError):
    """Invalid cost configuration (HTTP 422)."""


def validate_reference_notional(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(float(value)) \
            or not (MIN_REFERENCE_NOTIONAL <= float(value)
                    <= MAX_REFERENCE_NOTIONAL):
        raise CostError(
            f"reference_notional must be a finite number in "
            f"[{MIN_REFERENCE_NOTIONAL:g}, {MAX_REFERENCE_NOTIONAL:g}]")
    return float(value)


def _component_bps(model: Dict[str, Any],
                   component: str) -> Dict[str, Any]:
    """Per-side basis points for a computable component, or unavailable."""
    cfg = model.get(component) or {}
    kind = cfg.get("model")
    out: Dict[str, Any] = {"component": component, "model": kind,
                           "per_side_bps": None, "scalable": True,
                           "state": "unavailable", "reason": None}
    if kind in (None, "none"):
        out.update({"per_side_bps": 0.0, "state": "available",
                    "reason": None, "model": kind or "none",
                    "note": "explicitly configured as none (a declared zero, "
                            "not a fallback)"})
        return out
    if component == "commission":
        if kind == "bps_of_notional":
            out.update({"per_side_bps": float(cfg.get("value", 0.0)),
                        "state": "available"})
            if cfg.get("minimum") or cfg.get("maximum"):
                out["state"] = "unavailable"
                out["per_side_bps"] = None
                out["reason"] = ("a commission minimum/maximum needs per-order "
                                 "notionals, which a bucket reference does "
                                 "not hold")
        else:
            out["scalable"] = False
            out["reason"] = (f"commission model '{kind}' is monetary "
                             f"per-order/per-unit and needs order or "
                             f"contract counts the reference does not hold")
    elif component == "spread":
        if kind == "fixed_bps":
            fraction = cfg.get("fraction")
            value = cfg.get("value")
            if fraction is None or value is None:
                out["reason"] = "spread fraction or value is missing"
            else:
                out.update({"per_side_bps": float(value) * float(fraction),
                            "state": "available"})
        else:
            out["reason"] = (f"spread model '{kind}' needs per-observation "
                             f"prices or ticks the reference does not hold")
    elif component == "slippage":
        if kind == "fixed_bps_per_side":
            value = cfg.get("value")
            if value is None:
                out["reason"] = "slippage value is missing"
            else:
                out.update({"per_side_bps": float(value),
                            "state": "available"})
        else:
            out["reason"] = (f"slippage model '{kind}' needs supplied or "
                             f"tick-based inputs the reference does not hold")
    elif component == "impact":
        out["reason"] = (f"impact model '{kind}' needs ADV / participation "
                         f"inputs the reference does not hold; impact is "
                         f"unavailable, never zero")
    return out


def cost_estimate(model: Dict[str, Any], *,
                  turnover_rows: List[Dict[str, Any]],
                  reference_notional: float) -> Dict[str, Any]:
    """Per-rebalance and total descriptive cost estimate.

    Turnover τ is already measured from the signed gross-2 reference weights
    (long top, short bottom): τ = 0.5 * sum(abs(delta weight)).  Total traded
    notional is therefore 2·τ·N.  The two legs are not multiplied again.
    """
    components = [_component_bps(model, c) for c in COST_COMPONENTS]
    computable = [c for c in components if c["state"] == "available"]
    unavailable = [c for c in components if c["state"] != "available"]
    per_side_bps = sum(c["per_side_bps"] for c in computable)

    rows: List[Dict[str, Any]] = []
    total_cost = 0.0
    costed = 0
    skipped = 0
    for row in turnover_rows:
        turnover = row.get("one_way_turnover")
        entry: Dict[str, Any] = {
            "timestamp": row["timestamp"],
            "one_way_turnover": turnover,
            "traded_notional_per_side": None,
            "traded_notional_total": None,
            "cost": None, "cost_return": None, "state": "unavailable",
            "reason": None,
        }
        if turnover is None:
            entry["reason"] = ("turnover is unavailable at this rebalance "
                               "(no prior book), so its cost is unavailable")
            skipped += 1
        else:
            traded_total = 2.0 * float(turnover) * reference_notional
            per_side = traded_total / 2.0
            cost = per_side_bps / 1e4 * traded_total
            entry.update({
                "traded_notional_per_side": per_side,
                "traded_notional_total": traded_total,
                "cost": cost,
                "cost_return": cost / reference_notional,
                "state": ("available" if not unavailable
                          else "partial"),
            })
            total_cost += cost
            costed += 1
        rows.append(entry)

    completeness = "unavailable" if costed == 0 else (
        "partial" if unavailable or skipped else "complete")
    return {
        "reference_notional": reference_notional,
        "model_fingerprint": model.get("fingerprint"),
        "per_side_bps_computable": per_side_bps,
        "components": components,
        "unavailable_components": [c["component"] for c in unavailable],
        "rows": rows,
        "total_cost": total_cost if costed else None,
        "total_cost_return": (total_cost / reference_notional
                              if costed else None),
        "costed_rebalances": costed,
        "skipped_rebalances": skipped,
        "completeness": completeness,
        "convention": (
            "one-way turnover τ is computed from signed gross-2 reference "
            "weights; total traded notional is 2·τ·N and per-side traded "
            "notional is τ·N. The long and short legs are already included "
            "in τ and are not doubled again. Computed "
            "components are the notional-proportional ones only; everything "
            "else is unavailable with its reason. Gross results never "
            "include costs; cost-adjusted results are shown separately."),
    }


__all__ = [
    "MIN_REFERENCE_NOTIONAL", "MAX_REFERENCE_NOTIONAL", "COST_COMPONENTS",
    "CostError", "validate_reference_notional", "cost_estimate",
]
