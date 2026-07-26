"""
Asset and group contribution to return, with exact reconciliation (v1).

Single period, simple returns, beginning-of-period weights:

    contribution_i,t          = w_i,t × r_i,t
    portfolio_market_return_t = Σ_i contribution_i,t
    portfolio_net_return_t    = portfolio_market_return_t − cost_return_t

Contributions are MEASURED under this convention — they never "caused" a
result.  Signed and absolute shares are kept separate: a zero signed total
does not mean zero activity.

Cash is the explicit residual ``1 − Σ_i w_i`` and earns zero in v1, exactly
as in Phase 56; it is reported (never hidden), so a book whose weights do
not sum to one is visibly partially in cash or levered.

Group aggregation uses the linked portfolio's EXPLICIT stored group labels
(Phase 56 validates them; unlabelled assets fall into a visible
``unclassified`` group).  Groups never overlap in v1 — each asset belongs to
exactly one — so group totals sum to the asset totals with no double
counting.

Group return (only where the group weight is non-zero):

    R_g = Σ_{i∈g} contribution_i / W_g          with W_g = Σ_{i∈g} w_i

A zero group weight leaves the group RETURN unavailable — a group with no
capital has no weighted return, and one is never fabricated from the
constituent asset returns.  A negative group weight (long-short book) makes
the ratio sign-unstable, so it is reported with an explicit
``negative_weight`` state rather than silently divided.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

GROUP_WEIGHT_EPS = 1e-12


class ContributionError(ValueError):
    """Raised for invalid contribution inputs."""


def period_contributions(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per-asset contributions and the reconstructed portfolio return."""
    contributions: List[Dict[str, Any]] = []
    total = 0.0
    weight_sum = 0.0
    for row in rows:
        w = float(row["portfolio_beginning_weight"])
        r = float(row["asset_return"])
        if not math.isfinite(w) or not math.isfinite(r):
            raise ContributionError(
                f"non-finite weight or return for asset {row['asset_id']!r}")
        c = w * r
        total += c
        weight_sum += w
        contributions.append({
            "asset_id": row["asset_id"],
            "group_id": row["group_id"],
            "weight": w,
            "asset_return": r,
            "contribution": c,
        })
    cash_weight = 1.0 - weight_sum
    return {
        "rows": contributions,
        "portfolio_market_return": total,
        "weight_sum": weight_sum,
        "cash_weight": cash_weight,
        "cash_note": ("cash is the explicit residual 1 - sum(weights) and "
                      "earns zero in v1; it is disclosed, never hidden"),
    }


def reconcile_portfolio_return(reconstructed: float,
                               supplied: Optional[float],
                               tolerance: float) -> Dict[str, Any]:
    """Compare a supplied portfolio return with the reconstructed one.

    The supplied value is NEVER forced to match; the residual and its
    tolerance status are recorded so a disagreement stays visible.
    """
    if supplied is None:
        return {"supplied_return": None, "reconstructed_return": reconstructed,
                "residual": None, "within_tolerance": None,
                "state": "not_supplied",
                "note": ("no independently supplied portfolio return to "
                         "reconcile against")}
    residual = supplied - reconstructed
    within = abs(residual) <= tolerance
    return {
        "supplied_return": supplied,
        "reconstructed_return": reconstructed,
        "residual": residual,
        "within_tolerance": within,
        "state": "reconciled" if within else "mismatch",
        "note": ("the supplied return is reported as given; it is never "
                 "adjusted to match the reconstruction"),
    }


def group_aggregate(contribution_rows: List[Dict[str, Any]]
                    ) -> Dict[str, Dict[str, Any]]:
    """Aggregate per-asset contributions into their explicit groups."""
    groups: Dict[str, Dict[str, Any]] = {}
    for row in contribution_rows:
        g = row["group_id"]
        entry = groups.setdefault(g, {
            "group_id": g, "weight": 0.0, "contribution": 0.0,
            "asset_ids": [],
        })
        entry["weight"] += row["weight"]
        entry["contribution"] += row["contribution"]
        entry["asset_ids"].append(row["asset_id"])
    for entry in groups.values():
        entry["asset_ids"].sort()
        w = entry["weight"]
        if abs(w) <= GROUP_WEIGHT_EPS:
            entry["group_return"] = None
            entry["return_state"] = "zero_weight"
            entry["return_reason"] = (
                "the group carries no capital in this period, so it has no "
                "weighted return; one is never fabricated from constituent "
                "asset returns")
        elif w < 0:
            entry["group_return"] = entry["contribution"] / w
            entry["return_state"] = "negative_weight"
            entry["return_reason"] = (
                "the group's net weight is negative (short exposure); the "
                "weighted-return ratio is reported but its sign is not "
                "directly comparable with a long group's return")
        else:
            entry["group_return"] = entry["contribution"] / w
            entry["return_state"] = "available"
            entry["return_reason"] = None
    return groups


def aggregate_asset_results(period_results: List[Dict[str, Any]],
                            asset_ids: List[str],
                            groups: Dict[str, str]) -> List[Dict[str, Any]]:
    """Multi-period per-asset aggregation (arithmetic sums plus separated
    positive / negative / absolute parts)."""
    acc: Dict[str, Dict[str, Any]] = {
        a: {"asset_id": a, "group_id": groups.get(a), "arithmetic": 0.0,
            "positive": 0.0, "negative": 0.0, "absolute": 0.0,
            "weight_total": 0.0, "observations": 0}
        for a in asset_ids
    }
    for period in period_results:
        for row in period["contributions"]["rows"]:
            entry = acc[row["asset_id"]]
            c = row["contribution"]
            entry["arithmetic"] += c
            entry["absolute"] += abs(c)
            if c > 0:
                entry["positive"] += c
            elif c < 0:
                entry["negative"] += c
            entry["weight_total"] += row["weight"]
            entry["observations"] += 1
    abs_total = sum(e["absolute"] for e in acc.values())
    signed_total = sum(e["arithmetic"] for e in acc.values())
    rows = []
    for a in asset_ids:
        e = acc[a]
        n = e["observations"]
        rows.append({
            "asset_id": a,
            "group_id": e["group_id"],
            "average_weight": (e["weight_total"] / n) if n else None,
            "arithmetic_contribution": e["arithmetic"],
            "positive_contribution": e["positive"],
            "negative_contribution": e["negative"],
            "absolute_contribution": e["absolute"],
            "absolute_share": (e["absolute"] / abs_total
                               if abs_total > 0 else None),
            "signed_share": (e["arithmetic"] / signed_total
                             if abs(signed_total) > GROUP_WEIGHT_EPS else None),
            "observation_count": n,
        })
    return rows


def aggregate_group_results(asset_rows: List[Dict[str, Any]]
                            ) -> List[Dict[str, Any]]:
    """Group-level aggregation of the multi-period asset results (totals
    reconcile with the asset totals exactly — no double counting)."""
    acc: Dict[str, Dict[str, Any]] = {}
    for row in asset_rows:
        g = row["group_id"]
        entry = acc.setdefault(g, {
            "group_id": g, "arithmetic_contribution": 0.0,
            "positive_contribution": 0.0, "negative_contribution": 0.0,
            "absolute_contribution": 0.0, "asset_count": 0,
            "average_weight": 0.0, "linked_contribution": 0.0,
            "linked_available": True,
        })
        entry["arithmetic_contribution"] += row["arithmetic_contribution"]
        if row.get("linked_contribution") is None:
            entry["linked_available"] = False
        else:
            entry["linked_contribution"] += row["linked_contribution"]
        entry["positive_contribution"] += row["positive_contribution"]
        entry["negative_contribution"] += row["negative_contribution"]
        entry["absolute_contribution"] += row["absolute_contribution"]
        entry["asset_count"] += 1
        if row["average_weight"] is not None:
            entry["average_weight"] += row["average_weight"]
    abs_total = sum(e["absolute_contribution"] for e in acc.values())
    signed_total = sum(e["arithmetic_contribution"] for e in acc.values())
    out = []
    for g in sorted(acc):
        e = acc[g]
        e["absolute_share"] = (e["absolute_contribution"] / abs_total
                               if abs_total > 0 else None)
        e["signed_share"] = (
            e["arithmetic_contribution"] / signed_total
            if abs(signed_total) > GROUP_WEIGHT_EPS else None)
        if not e.pop("linked_available"):
            e["linked_contribution"] = None
        out.append(e)
    return out


__all__ = [
    "GROUP_WEIGHT_EPS", "ContributionError", "period_contributions",
    "reconcile_portfolio_return", "group_aggregate",
    "aggregate_asset_results", "aggregate_group_results",
]
