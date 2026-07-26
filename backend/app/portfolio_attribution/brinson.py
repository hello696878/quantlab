"""
Single-period Brinson attribution (v1) — Brinson-Fachler by default.

Implemented conventions, per group g (documented exactly; nothing hidden):

  Brinson-Fachler (default)
      allocation_g  = (Wp_g − Wb_g) × (Rb_g − Rb_total)
      selection_g   =  Wb_g        × (Rp_g − Rb_g)
      interaction_g = (Wp_g − Wb_g) × (Rp_g − Rb_g)

  Brinson-Hood-Beebower (optional)
      allocation_g  = (Wp_g − Wb_g) ×  Rb_g
      selection_g   =  Wb_g        × (Rp_g − Rb_g)
      interaction_g = (Wp_g − Wb_g) × (Rp_g − Rb_g)

with Wp/Wb the portfolio/benchmark group weights, Rp/Rb the group returns
and Rb_total the total benchmark return.

Both variants decompose the SAME active return: for books whose weights
each sum to one, Σ_g (allocation + selection + interaction) = Rp − Rb
exactly.  The two variants differ only in how the allocation term is
benchmarked (BF measures a group's over/under-weight against the benchmark's
OWN average return, which is why BF allocation is zero when a group's
benchmark return equals the total benchmark return).

Residual policy: the residual is ``active_return − (allocation + selection
+ interaction)`` and is reported verbatim.  It is never silently set to
zero and never redistributed into the three effects.  A non-zero residual
is expected and disclosed when the portfolio or benchmark weights do not
sum to one (a cash residual or leverage sits outside the group
decomposition) — in that case the residual is exactly the un-decomposed
cash/leverage term, and its reason is stated.

Groups present in only one book are handled honestly: the missing side
contributes weight 0, and its group return is unavailable rather than
fabricated.  Where a group return is unavailable, the terms that need it
are reported as unavailable and their omission is folded into the visible
residual with a stated reason — never quietly dropped.

Nothing here measures skill: allocation, selection and interaction are
arithmetic decompositions of a measured difference under a stated
convention, not evidence about a manager.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

BRINSON_VARIANTS = ("brinson_fachler", "brinson_hood_beebower")


class BrinsonError(ValueError):
    """Raised for invalid Brinson inputs."""


def brinson_period(portfolio_groups: Dict[str, Dict[str, Any]],
                   benchmark_groups: Dict[str, Dict[str, Any]],
                   *, benchmark_total_return: float,
                   portfolio_return: float,
                   benchmark_return: float,
                   variant: str,
                   tolerance: float) -> Dict[str, Any]:
    """Single-period Brinson decomposition with an explicit residual."""
    if variant not in BRINSON_VARIANTS:
        raise BrinsonError(
            f"brinson variant must be one of {', '.join(BRINSON_VARIANTS)}")
    labels = sorted(set(portfolio_groups) | set(benchmark_groups))
    rows: List[Dict[str, Any]] = []
    alloc_total = sel_total = inter_total = 0.0
    unavailable_terms: List[str] = []

    for g in labels:
        p = portfolio_groups.get(g)
        b = benchmark_groups.get(g)
        wp = float(p["weight"]) if p else 0.0
        wb = float(b["weight"]) if b else 0.0
        rp = p.get("group_return") if p else None
        rb = b.get("group_return") if b else None
        presence = ("both" if p and b else
                    ("portfolio_only" if p else "benchmark_only"))

        # allocation needs the BENCHMARK group return
        if rb is None:
            allocation = None
            unavailable_terms.append(f"allocation[{g}]")
        elif variant == "brinson_fachler":
            allocation = (wp - wb) * (rb - benchmark_total_return)
        else:
            allocation = (wp - wb) * rb

        # selection and interaction need BOTH group returns
        if rp is None or rb is None:
            selection = None
            interaction = None
            unavailable_terms.append(f"selection[{g}]")
            unavailable_terms.append(f"interaction[{g}]")
        else:
            selection = wb * (rp - rb)
            interaction = (wp - wb) * (rp - rb)

        alloc_total += allocation or 0.0
        sel_total += selection or 0.0
        inter_total += interaction or 0.0
        rows.append({
            "group_id": g,
            "presence": presence,
            "portfolio_weight": wp,
            "benchmark_weight": wb,
            "portfolio_return": rp,
            "benchmark_return": rb,
            "allocation_effect": allocation,
            "selection_effect": selection,
            "interaction_effect": interaction,
            "return_state": (p or b or {}).get("return_state"),
        })

    active_return = portfolio_return - benchmark_return
    explained = alloc_total + sel_total + inter_total
    residual = active_return - explained
    within = abs(residual) <= tolerance

    reasons: List[str] = []
    p_weight_sum = sum(float(v["weight"]) for v in portfolio_groups.values())
    b_weight_sum = sum(float(v["weight"]) for v in benchmark_groups.values())
    if abs(p_weight_sum - 1.0) > tolerance:
        reasons.append(
            f"portfolio group weights sum to {p_weight_sum:.10g}, not 1 — the "
            "cash/leverage residual sits outside the group decomposition")
    if abs(b_weight_sum - 1.0) > tolerance:
        reasons.append(
            f"benchmark group weights sum to {b_weight_sum:.10g}, not 1 — the "
            "benchmark's own cash/leverage residual is outside the "
            "decomposition")
    if unavailable_terms:
        reasons.append(
            "some effects are unavailable because a group return does not "
            "exist (zero group weight or a one-sided group): "
            + ", ".join(sorted(set(unavailable_terms))))

    return {
        "variant": variant,
        "rows": rows,
        "allocation_effect": alloc_total,
        "selection_effect": sel_total,
        "interaction_effect": inter_total,
        "explained_effect": explained,
        "portfolio_return": portfolio_return,
        "benchmark_return": benchmark_return,
        "active_return": active_return,
        "residual": residual,
        "within_tolerance": within,
        "reconciliation_state": "reconciled" if within else "residual",
        "residual_reasons": reasons,
        "portfolio_weight_sum": p_weight_sum,
        "benchmark_weight_sum": b_weight_sum,
        "unavailable_terms": sorted(set(unavailable_terms)),
        "formula": (
            "allocation_g = (Wp_g - Wb_g) x (Rb_g - Rb_total); "
            "selection_g = Wb_g x (Rp_g - Rb_g); "
            "interaction_g = (Wp_g - Wb_g) x (Rp_g - Rb_g)"
            if variant == "brinson_fachler" else
            "allocation_g = (Wp_g - Wb_g) x Rb_g; "
            "selection_g = Wb_g x (Rp_g - Rb_g); "
            "interaction_g = (Wp_g - Wb_g) x (Rp_g - Rb_g)"),
        "note": ("an arithmetic decomposition of a measured return "
                 "difference under a stated convention — not evidence of "
                 "skill, alpha or a preferred portfolio"),
    }


def aggregate_brinson(period_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Arithmetic per-group totals across periods (see linking.py for the
    documented multi-period caveat)."""
    acc: Dict[str, Dict[str, Any]] = {}
    presences: Dict[str, set] = {}
    for period in period_rows:
        for row in period["rows"]:
            e = acc.setdefault(row["group_id"], {
                "group_id": row["group_id"],
                "allocation_effect": 0.0, "selection_effect": 0.0,
                "interaction_effect": 0.0, "periods": 0,
                "unavailable_periods": 0,
                "portfolio_weight_total": 0.0, "benchmark_weight_total": 0.0,
            })
            presences.setdefault(row["group_id"], set()).add(row["presence"])
            if row["allocation_effect"] is None or row["selection_effect"] is None:
                e["unavailable_periods"] += 1
            e["allocation_effect"] += row["allocation_effect"] or 0.0
            e["selection_effect"] += row["selection_effect"] or 0.0
            e["interaction_effect"] += row["interaction_effect"] or 0.0
            e["portfolio_weight_total"] += row["portfolio_weight"]
            e["benchmark_weight_total"] += row["benchmark_weight"]
            e["periods"] += 1
    out = []
    for g in sorted(acc):
        e = acc[g]
        n = e["periods"]
        e["average_portfolio_weight"] = e.pop("portfolio_weight_total") / n
        e["average_benchmark_weight"] = e.pop("benchmark_weight_total") / n
        e["total_effect"] = (e["allocation_effect"] + e["selection_effect"]
                             + e["interaction_effect"])
        # window-level presence: a single value when every period agrees,
        # otherwise 'mixed' rather than silently picking one period's label
        states = presences.get(g, set())
        e["presence"] = (states.pop() if len(states) == 1
                         else ("mixed" if states else None))
        out.append(e)
    return out


__all__ = ["BRINSON_VARIANTS", "BrinsonError", "brinson_period",
           "aggregate_brinson"]
