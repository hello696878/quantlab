"""
Phase 55 cost-model linkage (v1): descriptive rebalance-cost estimates.

A linked Cost Diagnostics run's STORED cost model drives estimates from
each rebalance's one-way turnover: a synthetic period observation
``{turnover, traded_notional = 2 × turnover × configured_notional}``
(one-way turnover covers a buy and a sell leg — documented) is fed to the
Phase 55 pure component functions on their period path.  Nothing in the
Phase 55 registry is mutated and its fingerprints are preserved — this is
a research calculation only, and generated weights are never submitted
anywhere.

Honesty rules: only turnover-proportional component models are applicable
to weight-space turnover (period path): commission ``bps_of_notional``,
spread ``fixed_bps`` (round-trip), slippage ``fixed_bps_per_side``,
impact ``fixed_bps``.  Monetary fixed fees (per order/trade/contract) and
liquidity-dependent square-root impact need trade sizes or ADV/volatility
this lab does not fabricate — those components are UNAVAILABLE with
explicit reasons, never silently zero, and the partial state stays
visible.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from app.cost_diagnostics import components as cost_components
from app.cost_diagnostics import impact as cost_impact
from app.cost_diagnostics.reconcile import reconcile_observation

PERIOD_APPLICABLE = {
    "commission": ("none", "bps_of_notional"),
    "spread": ("none", "fixed_bps"),
    "slippage": ("none", "fixed_bps_per_side"),
    "impact": ("none", "fixed_bps"),
}


def estimate_rebalance_cost(turnover: Optional[float],
                            cost_model: Dict[str, Any],
                            notional: Optional[float]) -> Dict[str, Any]:
    """Descriptive cost estimate for one rebalance's one-way turnover."""
    if turnover is None or not math.isfinite(turnover) or turnover < 0:
        return {"status": "unavailable",
                "reason": "turnover unavailable for this rebalance",
                "components": None, "total_cost_return": None,
                "total_cost_notional": None, "completeness": None}
    # both legs of the reweighting trade (a sale and a purchase) pay costs
    traded_fraction = 2.0 * turnover
    obs: Dict[str, Any] = {"turnover": traded_fraction,
                           "traded_notional": (traded_fraction * notional
                                               if notional else None),
                           "cost_inputs": {}}
    records: Dict[str, Dict[str, Any]] = {}
    for name in ("commission", "spread", "slippage", "impact"):
        cfg = cost_model.get(name) or {"model": "none"}
        model = cfg.get("model", "none")
        if model not in PERIOD_APPLICABLE[name]:
            records[name] = {
                "status": "unavailable", "amount": None,
                "reason": (f"linked cost model uses {model!r}, which needs "
                           "trade sizes or liquidity inputs this lab does "
                           "not fabricate from weight turnover")}
            continue
        # gate on the FULL stored config — trade-level fields the period
        # path would silently drop make the component unavailable instead
        if name == "commission" and model != "none" and any(
                cfg.get(f) not in (None, 1) for f in
                ("minimum", "maximum", "entry_orders", "exit_orders")):
            records[name] = {
                "status": "unavailable", "amount": None,
                "reason": ("linked commission carries monetary/order-level "
                           "fields (minimum/maximum/order counts) that do "
                           "not apply to weight turnover; not silently "
                           "ignored")}
            continue
        if name == "spread" and model != "none" \
                and cfg.get("sides") not in (None, "round_trip"):
            records[name] = {
                "status": "unavailable", "amount": None,
                "reason": ("linked spread applies to "
                           f"{cfg.get('sides')!r} only; weight turnover has "
                           "no side decomposition, so a one-sided model is "
                           "not silently costed round-trip")}
            continue
        if name == "commission":
            records[name] = cost_components.compute_commission(obs, cfg, "period")
        elif name == "spread":
            records[name] = cost_components.compute_spread_cost(
                obs, cfg, "period", None)
        elif name == "slippage":
            records[name] = cost_components.compute_slippage(
                obs, cfg, "period", None)
        else:
            records[name] = cost_impact.compute_impact(
                obs, cfg, "period", None, None,
                allow_supplied_adv=False, allow_supplied_vol=False)
    rec = reconcile_observation(0.0, records)
    total_return = rec["total_cost"]
    all_unconfigured = all(r.get("status") == "not_configured"
                           for r in records.values())
    return {
        "status": "available" if total_return is not None else "unavailable",
        "reason": None if total_return is not None else (
            "the linked cost model configures no components"
            if all_unconfigured else
            "no linked cost component is applicable to weight turnover"),
        "components": {n: (records[n].get("amount")
                           if records[n].get("status") == "available" else None)
                       for n in records},
        "component_reasons": {n: records[n].get("reason")
                              for n in records
                              if records[n].get("status") == "unavailable"},
        "total_cost_return": total_return,
        "total_cost_notional": (total_return * notional
                                if total_return is not None and notional
                                else None),
        "completeness": rec["completeness"],
        "traded_fraction_note": ("traded fraction = 2 × one-way turnover "
                                 "(both legs of the reweighting pay costs)"),
    }
