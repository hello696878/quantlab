"""
Multi-period linking of single-period attribution effects (v1).

Two methods, both fully documented and tested:

``arithmetic``
    Sum the single-period effects.  This is a REFERENCE view only: a simple
    arithmetic sum of single-period effects does **not** generally reconcile
    with the compounded active return, because the compounded portfolio and
    benchmark returns each involve cross-period products the sum omits.  The
    gap is reported as ``linking_residual`` and never hidden.

``carino``
    Carinó (1999) logarithmic smoothing.  With compounded returns

        Rp = Π_t (1 + rp_t) − 1        Rb = Π_t (1 + rb_t) − 1

    the total scaling factor and the per-period factors are

        k     = (ln(1+Rp) − ln(1+Rb)) / (Rp − Rb)
        k_t   = (ln(1+rp_t) − ln(1+rb_t)) / (rp_t − rb_t)
        linked_effect = Σ_t (k_t / k) × effect_t

    which satisfies Σ_t (k_t/k)(rp_t − rb_t) = Rp − Rb exactly, so the
    linked effects reconcile with the **geometric** active return
    ``Rp − Rb`` within numerical tolerance.

    Degenerate cases are handled analytically rather than by an epsilon
    fudge, using the limit of ``(ln(1+x) − ln(1+y))/(x − y)`` as ``y → x``:

        x = y  ⇒  factor = 1 / (1 + x)

    which is exact, not an approximation.  A period (or total) with a
    return ≤ −100% makes the logarithm undefined; that period is reported
    as unavailable and linking is withheld with a stated reason — no
    fabricated factor is substituted.

Neither method is claimed to be GIPS compliant, and neither is evidence of
skill: both are arithmetic restatements of measured single-period effects.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

LINKING_METHODS = ("arithmetic", "carino")
EFFECT_KEYS = ("allocation_effect", "selection_effect", "interaction_effect")


class LinkingError(ValueError):
    """Raised for invalid linking inputs."""


def compound(returns: List[float]) -> Optional[float]:
    """Π(1+r) − 1, or None when a return ≤ −100% breaks compounding."""
    level = 1.0
    for r in returns:
        factor = 1.0 + r
        if factor <= 0 or not math.isfinite(factor):
            return None
        level *= factor
        if not math.isfinite(level):
            return None
    return level - 1.0


def _carino_factor(x: float, y: float) -> Optional[float]:
    """(ln(1+x) − ln(1+y)) / (x − y), with the exact x→y limit 1/(1+x)."""
    if 1.0 + x <= 0 or 1.0 + y <= 0:
        return None
    if x == y:
        return 1.0 / (1.0 + x)
    denominator = x - y
    value = (math.log1p(x) - math.log1p(y)) / denominator
    return value if math.isfinite(value) else None


def link_effects(period_effects: List[Dict[str, Any]],
                 portfolio_returns: List[float],
                 benchmark_returns: List[float],
                 method: str,
                 tolerance: float) -> Dict[str, Any]:
    """Link single-period effects into multi-period totals."""
    if method not in LINKING_METHODS:
        raise LinkingError(
            f"linking method must be one of {', '.join(LINKING_METHODS)}")
    n = len(period_effects)
    if n != len(portfolio_returns) or n != len(benchmark_returns):
        raise LinkingError("period counts must align for linking")

    arithmetic_active = sum(p - b for p, b in
                            zip(portfolio_returns, benchmark_returns))
    compounded_portfolio = compound(portfolio_returns)
    compounded_benchmark = compound(benchmark_returns)
    geometric_active = (
        compounded_portfolio - compounded_benchmark
        if compounded_portfolio is not None and compounded_benchmark is not None
        else None)

    arithmetic_totals = {k: sum(p.get(k) or 0.0 for p in period_effects)
                         for k in EFFECT_KEYS}
    arithmetic_explained = sum(arithmetic_totals.values())
    arithmetic_residual = sum(p.get("residual") or 0.0 for p in period_effects)

    result: Dict[str, Any] = {
        "method": method,
        "period_count": n,
        "arithmetic_active_return": arithmetic_active,
        "compounded_portfolio_return": compounded_portfolio,
        "compounded_benchmark_return": compounded_benchmark,
        "geometric_active_return": geometric_active,
        "arithmetic_effects": arithmetic_totals,
        "arithmetic_explained": arithmetic_explained,
        "arithmetic_period_residual": arithmetic_residual,
        "arithmetic_vs_geometric_gap": (
            arithmetic_active - geometric_active
            if geometric_active is not None else None),
        "arithmetic_caveat": (
            "a simple arithmetic sum of single-period effects does not "
            "generally reconcile with the compounded (geometric) active "
            "return; the gap is reported, not hidden"),
    }

    if method == "arithmetic":
        # the arithmetic method targets the SUMMED active return, so its
        # residual is exactly the summed single-period residual
        linking_residual = arithmetic_active - arithmetic_explained
        result.update({
            "linked_effects": dict(arithmetic_totals),
            "linked_explained": arithmetic_explained,
            "linked_target": arithmetic_active,
            "linking_residual": linking_residual,
            "within_tolerance": abs(linking_residual) <= tolerance,
            "smoothing_factors": None,
            "available": True,
            "reason": None,
        })
        return result

    # --- Carinó ---------------------------------------------------------
    if compounded_portfolio is None or compounded_benchmark is None:
        result.update({
            "linked_effects": None, "linked_explained": None,
            "linked_target": None, "linking_residual": None,
            "smoothing_factors": None, "available": False,
            "within_tolerance": None,
            "reason": ("a period return of -100% or worse makes the "
                       "compounded return non-positive, so the Carino "
                       "logarithm is undefined; linked effects are withheld "
                       "rather than approximated"),
        })
        return result
    k_total = _carino_factor(compounded_portfolio, compounded_benchmark)
    if k_total is None or k_total == 0:
        result.update({
            "linked_effects": None, "linked_explained": None,
            "linked_target": None, "linking_residual": None,
            "smoothing_factors": None, "available": False,
            "within_tolerance": None,
            "reason": ("the total Carino scaling factor is undefined for "
                       "these compounded returns; linked effects are "
                       "withheld"),
        })
        return result

    factors: List[Optional[float]] = []
    linked = {k: 0.0 for k in EFFECT_KEYS}
    linked_residual_term = 0.0
    unavailable_periods: List[int] = []
    for t in range(n):
        k_t = _carino_factor(portfolio_returns[t], benchmark_returns[t])
        if k_t is None:
            factors.append(None)
            unavailable_periods.append(t)
            continue
        scale = k_t / k_total
        factors.append(scale)
        for key in EFFECT_KEYS:
            linked[key] += scale * (period_effects[t].get(key) or 0.0)
        linked_residual_term += scale * (period_effects[t].get("residual") or 0.0)

    if unavailable_periods:
        result.update({
            "linked_effects": None, "linked_explained": None,
            "linked_target": geometric_active, "linking_residual": None,
            "smoothing_factors": None, "available": False,
            "within_tolerance": None,
            "reason": ("periods "
                       + ", ".join(str(i) for i in unavailable_periods)
                       + " have an undefined Carino factor (a return of "
                         "-100% or worse); linked effects are withheld"),
        })
        return result

    linked_explained = sum(linked.values())
    linking_residual = geometric_active - linked_explained
    # closure identity: the linked EFFECTS plus the linked single-period
    # RESIDUALS reproduce the geometric active return exactly, so a non-zero
    # linking residual is always exactly the scaled single-period residual —
    # never an unexplained gap
    linked_total_including_residual = linked_explained + linked_residual_term
    result.update({
        "linked_effects": linked,
        "linked_explained": linked_explained,
        "linked_residual_term": linked_residual_term,
        "linked_total_including_residual": linked_total_including_residual,
        "closure_residual": geometric_active - linked_total_including_residual,
        "closure_note": (
            "linked effects + linked single-period residuals reconcile with "
            "the geometric active return; when the single-period effects "
            "already close, the linking residual is zero"),
        "linked_target": geometric_active,
        "linking_residual": linking_residual,
        "within_tolerance": abs(linking_residual) <= tolerance,
        "smoothing_factors": [round(f, 12) for f in factors],  # exportable
        "total_scaling_factor": k_total,
        "available": True,
        "reason": None,
        "carino_note": (
            "linked effects reconcile with the GEOMETRIC active return "
            "(compounded portfolio minus compounded benchmark); the exact "
            "x=y limit 1/(1+x) is used instead of an epsilon guard"),
    })
    return result


def time_weighted_return(returns: List[float],
                         *, supports_twr: bool) -> Dict[str, Any]:
    """TWR = Π(1+r) − 1 over cash-flow-neutral subperiod returns.

    ``supports_twr`` must be asserted by the caller from the actual input
    provenance: the stored Phase 56 series is a weight-driven return series
    with no external cash flows, which is exactly what TWR requires.  When
    that cannot be asserted the result is withheld — a compounded number is
    never LABELLED time-weighted when the inputs do not support it, and no
    money-weighted/IRR placeholder is offered.
    """
    if not supports_twr:
        return {"available": False, "value": None,
                "reason": ("the observation set does not establish "
                           "cash-flow-neutral subperiods, so no result is "
                           "labelled a time-weighted return"),
                "convention": None}
    value = compound(returns)
    if value is None:
        return {"available": False, "value": None,
                "reason": ("a period return of -100% or worse makes the "
                           "compounded wealth non-positive"),
                "convention": None}
    return {
        "available": True,
        "value": value,
        "reason": None,
        "convention": ("TWR = product over periods of (1 + r_t) - 1 on "
                       "cash-flow-neutral subperiod simple returns; no "
                       "external cash flows exist in the stored series, and "
                       "no money-weighted (IRR) figure is implied"),
    }


__all__ = ["LINKING_METHODS", "EFFECT_KEYS", "LinkingError", "compound",
           "link_effects", "time_weighted_return"]
