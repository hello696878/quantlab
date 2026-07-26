"""
Transaction-cost attribution over attribution periods (v1).

Source of truth: the STORED per-rebalance cost estimates already recorded on
the linked Phase 56 portfolio run.  Those estimates were produced from a
linked Phase 55 cost model at rebalance time; this lab reads them and never
recomputes, re-estimates or rewrites them, so every Phase 55 and Phase 56
fingerprint is preserved.

Mapping (exact, no fabrication): a rebalance's cost belongs to the period
that STARTS at that rebalance's decision timestamp — the period in which the
trade is assumed to occur.  A period with no rebalance has **no cost
observation**, which is reported as ``no_trade`` (a structural zero: no
trade happened, so no cost was incurred) and is distinct from
``unavailable`` (a trade happened but its cost could not be estimated).
Neither state is ever silently zero-filled into the totals.

Components are kept non-overlapping and separate — commission, spread,
slippage, impact — exactly as Phase 55 records them, and a component that
Phase 55 marked unavailable stays unavailable with its reason.

Gross-to-net reconciliation:

    net_return_t = market_return_t − total_cost_return_t

The costed subset is tracked explicitly: when some periods have unavailable
costs, the net total is formed over the SAME periods as its cost leg and
that basis is disclosed, so a gross figure covering more periods is never
netted against a narrower cost figure.

Stressed Phase 57 costs are never mixed in here: this lab reads realized /
base cost estimates only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

COST_COMPONENTS = ("commission", "spread", "slippage", "impact")
COST_STATES = ("available", "partial", "unavailable", "no_trade")


def period_costs(period_ids: List[int],
                 period_starts: List[str],
                 rebalances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-period cost rows mapped from stored rebalance cost estimates."""
    by_timestamp = {r["decision_timestamp"]: r for r in rebalances}
    rows: List[Dict[str, Any]] = []
    for pid, start in zip(period_ids, period_starts):
        rebalance = by_timestamp.get(start)
        if rebalance is None:
            rows.append({
                "period_id": pid, "period_start": start,
                "rebalance_id": None, "state": "no_trade",
                "total_cost_return": 0.0,
                "components": {c: None for c in COST_COMPONENTS},
                "component_reasons": {},
                "reason": ("no rebalance occurs in this period, so no "
                           "transaction cost is incurred (a structural zero, "
                           "not a missing measurement)"),
                "completeness": None,
            })
            continue
        cost = rebalance.get("cost")
        if not cost or cost.get("total_cost_return") is None:
            rows.append({
                "period_id": pid, "period_start": start,
                "rebalance_id": rebalance.get("rebalance_id"),
                "state": "unavailable",
                "total_cost_return": None,
                "components": {c: None for c in COST_COMPONENTS},
                "component_reasons": (cost or {}).get("component_reasons", {}),
                "reason": ((cost or {}).get("reason")
                           or "the linked portfolio run stored no cost "
                              "estimate for this rebalance"),
                "completeness": (cost or {}).get("completeness"),
            })
            continue
        components = cost.get("components") or {}
        rows.append({
            "period_id": pid, "period_start": start,
            "rebalance_id": rebalance.get("rebalance_id"),
            "state": ("partial" if cost.get("completeness") == "partial"
                      else "available"),
            "total_cost_return": float(cost["total_cost_return"]),
            "components": {c: components.get(c) for c in COST_COMPONENTS},
            "component_reasons": cost.get("component_reasons", {}) or {},
            "reason": None,
            "completeness": cost.get("completeness"),
        })
    return rows


def aggregate_costs(cost_rows: List[Dict[str, Any]],
                    market_returns_by_period: Dict[int, float]) -> Dict[str, Any]:
    """Gross-to-net reconciliation over an explicitly stated costed basis."""
    costed = [r for r in cost_rows if r["total_cost_return"] is not None]
    unavailable = [r for r in cost_rows if r["total_cost_return"] is None]
    traded = [r for r in costed if r["state"] != "no_trade"]

    total_cost = sum(r["total_cost_return"] for r in costed)
    component_totals: Dict[str, Optional[float]] = {}
    component_states: Dict[str, str] = {}
    for component in COST_COMPONENTS:
        values = [r["components"].get(component) for r in traded]
        available = [v for v in values if v is not None]
        if values and len(available) == len(values):
            component_totals[component] = sum(available)
            component_states[component] = "complete"
        else:
            component_totals[component] = None
            component_states[component] = (
                "partial" if available else "unavailable")

    gross_all = sum(market_returns_by_period.values())
    gross_costed = sum(market_returns_by_period[r["period_id"]]
                       for r in costed
                       if r["period_id"] in market_returns_by_period)
    completeness = ("complete" if not unavailable else
                    ("partial" if costed else "unavailable"))
    return {
        "total_cost_return": total_cost if costed else None,
        "component_totals": component_totals,
        "component_states": component_states,
        "gross_market_return_all_periods": gross_all,
        "gross_market_return_costed_periods": gross_costed,
        "net_return_costed_periods": (gross_costed - total_cost
                                      if costed else None),
        "costed_period_count": len(costed),
        "traded_period_count": len(traded),
        "unavailable_period_count": len(unavailable),
        "completeness": completeness,
        "basis_note": (
            "the net figure is formed over the SAME periods as its cost leg "
            "(the costed subset); a gross figure covering more periods is "
            "never netted against a narrower cost figure"),
        "source_note": (
            "costs are the stored per-rebalance estimates recorded on the "
            "linked portfolio run (from its linked Phase 55 model); nothing "
            "is recomputed and no Phase 55 or Phase 56 record is modified"),
        "stress_note": (
            "stressed Phase 57 cost scenarios are never mixed into these "
            "realized/base cost estimates"),
    }


__all__ = ["COST_COMPONENTS", "COST_STATES", "period_costs", "aggregate_costs"]
