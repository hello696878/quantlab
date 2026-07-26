"""
Direct asset-price shocks, precedence resolution, contribution
attribution and post-shock drifted weights (v1).

Static linear approximation (documented; exact for one-period simple
returns on a fixed book, ignoring intra-scenario compounding):

    scenario_contribution_i   = weight_i × asset_shock_i
    portfolio_scenario_return = Σ_i scenario_contribution_i
    scenario_pnl              = portfolio_notional × portfolio_scenario_return

The notional is always explicit — never fabricated.  Long and short
weights flow through signed arithmetic unchanged; nothing is normalized
silently and no leverage is implied.  Contributions are MEASURED under
this scenario — never described as having caused anything.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.portfolio_stress.scenario import ScenarioError


def resolve_shocks(scenario: Dict[str, Any], asset_ids: List[str],
                   asset_groups: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """Per-asset shock (return space) via the documented precedence."""
    resolved: Dict[str, Optional[float]] = {}
    sources: Dict[str, str] = {}
    for aid in asset_ids:
        if aid in scenario["asset_shocks"]:
            resolved[aid] = scenario["asset_shocks"][aid]["as_return"]
            sources[aid] = "asset"
        elif asset_groups.get(aid) and asset_groups[aid] in scenario["group_shocks"]:
            resolved[aid] = scenario["group_shocks"][asset_groups[aid]]["as_return"]
            sources[aid] = "group"
        elif scenario["global_shock"] is not None:
            resolved[aid] = scenario["global_shock"]["as_return"]
            sources[aid] = "global"
        elif scenario["missing_shock_policy"] == "zero":
            resolved[aid] = 0.0
            sources[aid] = "policy_zero"
        else:
            resolved[aid] = None
            sources[aid] = "unavailable"
    return {"shocks": resolved, "sources": sources}


def direct_contributions(weights: Dict[str, float],
                         shocks: Dict[str, Optional[float]],
                         asset_ids: List[str],
                         asset_groups: Dict[str, Optional[str]],
                         notional: Optional[float]) -> Dict[str, Any]:
    """Contribution attribution reconciling to the portfolio result."""
    rows: List[Dict[str, Any]] = []
    total = 0.0
    unavailable = 0
    for aid in asset_ids:
        w = weights.get(aid, 0.0)
        s = shocks.get(aid)
        if s is None:
            rows.append({"asset_id": aid, "weight": w, "shock": None,
                         "contribution": None, "group": asset_groups.get(aid)})
            unavailable += 1
            continue
        contribution = w * s
        total += contribution
        rows.append({"asset_id": aid, "weight": w, "shock": s,
                     "contribution": contribution,
                     "group": asset_groups.get(aid)})
    available_rows = [r for r in rows if r["contribution"] is not None]
    portfolio_return = total if available_rows else None
    completeness = ("complete" if unavailable == 0
                    else ("partial" if available_rows else "unavailable"))

    group_totals: Dict[str, float] = {}
    for r in available_rows:
        g = r.get("group") or "ungrouped"
        group_totals[g] = group_totals.get(g, 0.0) + r["contribution"]

    abs_total = sum(abs(r["contribution"]) for r in available_rows)
    for r in rows:
        r["abs_share"] = (abs(r["contribution"]) / abs_total
                          if r["contribution"] is not None and abs_total > 0
                          else None)
    positives = [r for r in available_rows if r["contribution"] > 0]
    negatives = [r for r in available_rows if r["contribution"] < 0]
    shares = sorted((abs(r["contribution"]) for r in available_rows),
                    reverse=True)
    concentration = {
        "positive_total": float(sum(r["contribution"] for r in positives)),
        "negative_total": float(sum(r["contribution"] for r in negatives)),
        "largest_negative_contributor": (
            min(available_rows, key=lambda r: r["contribution"])["asset_id"]
            if negatives else None),
        "largest_positive_contributor": (
            max(available_rows, key=lambda r: r["contribution"])["asset_id"]
            if positives else None),
        "top3_abs_share": (sum(shares[:3]) / abs_total
                           if abs_total > 0 else None),
        "abs_hhi": (sum((v / abs_total) ** 2 for v in shares)
                    if abs_total > 0 else None),
        "note": ("signed and absolute shares are separate; a zero signed "
                 "total does not mean zero activity"),
    }
    pnl = (portfolio_return * notional
           if portfolio_return is not None and notional else None)
    return {
        "rows": rows,
        "portfolio_scenario_return": portfolio_return,
        "scenario_pnl": pnl,
        "group_contributions": group_totals,
        "concentration": concentration,
        "completeness": completeness,
        "unavailable_assets": unavailable,
        "formula": ("scenario_contribution_i = weight_i x asset_shock_i; "
                    "portfolio_scenario_return = sum_i contributions "
                    "(static linear approximation on the fixed stored book)"),
    }


def drifted_weights(weights: Dict[str, float],
                    shocks: Dict[str, Optional[float]],
                    asset_ids: List[str]) -> Dict[str, Any]:
    """Post-shock market-value weights (original weights retained).

    ``post_value_i = w_i × (1 + r_i)``; drifted = post_value / Σ post_value.
    Cash is the SIGNED residual ``1 − Σw`` (negative for a levered book —
    borrowed cash stays borrowed, matching the Phase 56 wealth convention)
    and is carried unshocked, so the denominator equals ``1 + Σ w_i·r_i``.
    A return equal to −100% zeroes the position value; a return below
    −100% is outside simple-return support and returns unavailable.  A
    non-positive or non-finite denominator returns
    unavailable — never a fabricated book.  No automatic rebalancing
    occurs.
    """
    if any(shocks.get(a) is None for a in asset_ids):
        return {"weights": None,
                "reason": "drifted weights need a shock for every asset "
                          "(missing-shock policy 'unavailable')"}
    post: Dict[str, float] = {}
    if any(shocks[a] is not None and shocks[a] < -1.0 for a in asset_ids):
        return {"weights": None,
                "reason": "a shock below -100% is outside the simple-return "
                          "drift convention"}
    for a in asset_ids:
        w = weights.get(a, 0.0)
        r = shocks[a]
        post[a] = w * (1.0 + r)
    net = sum(weights.get(a, 0.0) for a in asset_ids)
    cash = 1.0 - net  # signed residual: negative = borrowed, never clamped
    denominator = sum(post.values()) + cash
    if not math.isfinite(denominator) or denominator <= 0:
        return {"weights": None,
                "reason": "post-shock book value is non-positive; drifted "
                          "weights are unavailable (long-short books can "
                          "be wiped out by adverse shocks)"}
    return {"weights": {a: post[a] / denominator for a in asset_ids},
            "cash_weight": cash / denominator,
            "denominator": denominator,
            "reason": None,
            "note": ("pure mathematical drift of the stored book — no "
                     "automatic rebalancing")}
