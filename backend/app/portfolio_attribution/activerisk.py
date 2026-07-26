"""
Active-risk diagnostics and contribution concentration (v1).

Conventions (all stated, none assumed):

* active_return_t = portfolio_return_t − benchmark_return_t, on identical
  periods and the identical return convention;
* the active-return standard deviation uses the SAMPLE convention
  (``ddof = 1``), so at least two active observations are required —
  one observation yields an unavailable deviation rather than zero;
* tracking error is that per-period sample deviation.  An ANNUALIZED
  tracking error is reported only when the caller declared a known return
  frequency; with ``unspecified`` frequency the annualized figure stays
  unavailable rather than assuming 252 periods;
* information ratio = mean active return ÷ tracking error, both per period.
  A zero (or numerically negligible) tracking error leaves the ratio
  unavailable with a stated reason — it is never reported as infinite,
  and it is never described as evidence of skill;
* the active drawdown compounds the active return series from 1.0 with a
  trailing-only running peak, exactly as the Phase 57 drawdown convention
  does, and is labelled a *relative* drawdown of a synthetic
  long-portfolio / short-benchmark series — not a realizable loss.

Concentration is measured on ABSOLUTE contributions (a signed total near
zero does not mean nothing happened) with the signed parts reported
separately.  A high concentration is a measurement, never evidence of poor
diversification or overfitting.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

TRACKING_ERROR_EPS = 1e-12
CONCENTRATION_EPS = 1e-12


def active_series(portfolio_returns: List[float],
                  benchmark_returns: List[float]) -> List[float]:
    return [p - b for p, b in zip(portfolio_returns, benchmark_returns)]


def active_risk(portfolio_returns: List[float],
                benchmark_returns: List[float],
                *, periods_per_year: Optional[int],
                frequency: str) -> Dict[str, Any]:
    """Tracking error, information ratio and hit rates with honest gaps."""
    n = len(portfolio_returns)
    active = active_series(portfolio_returns, benchmark_returns)
    out: Dict[str, Any] = {
        "observation_count": n,
        "mean_active_return": (sum(active) / n) if n else None,
        "arithmetic_active_return": sum(active) if n else None,
        "frequency": frequency,
        "periods_per_year": periods_per_year,
        "std_convention": "sample standard deviation (ddof = 1)",
        "note": ("measured benchmark-relative statistics under this "
                 "convention; a positive active return or information ratio "
                 "is not evidence of skill, alpha or future performance"),
    }
    if n < 2:
        out.update({
            "active_return_std": None, "tracking_error": None,
            "annualized_tracking_error": None, "information_ratio": None,
            "information_ratio_state": "unavailable",
            "information_ratio_reason": (
                "at least two active observations are required for a sample "
                "standard deviation"),
            "downside_active_deviation": None,
            "positive_active_rate": None, "negative_active_rate": None,
            "hit_rate": None,
        })
        return out

    mean = sum(active) / n
    variance = sum((a - mean) ** 2 for a in active) / (n - 1)
    std = math.sqrt(variance)
    downside = [a for a in active if a < 0]
    downside_dev = (math.sqrt(sum(a * a for a in downside) / len(downside))
                    if downside else None)
    positives = sum(1 for a in active if a > 0)
    negatives = sum(1 for a in active if a < 0)

    out.update({
        "active_return_std": std,
        "tracking_error": std,
        "annualized_tracking_error": (std * math.sqrt(periods_per_year)
                                      if periods_per_year else None),
        "annualization_note": (
            f"annualized with sqrt({periods_per_year}) periods per year"
            if periods_per_year else
            "annualized figures are unavailable because the return frequency "
            "was declared 'unspecified' — a periods-per-year factor is never "
            "assumed"),
        "downside_active_deviation": downside_dev,
        "positive_active_rate": positives / n,
        "negative_active_rate": negatives / n,
        "hit_rate": positives / n,
        "hit_rate_definition": ("fraction of periods whose active return is "
                                "strictly positive"),
    })
    if std <= TRACKING_ERROR_EPS:
        out.update({
            "information_ratio": None,
            "information_ratio_state": "unavailable",
            "information_ratio_reason": (
                "tracking error is zero (the portfolio tracked the benchmark "
                "exactly over these periods), so the information ratio is "
                "undefined — it is never reported as infinite"),
        })
    else:
        out.update({
            "information_ratio": mean / std,
            "information_ratio_state": "available",
            "information_ratio_reason": None,
            "information_ratio_definition": (
                "mean active return / tracking error, both per period "
                "(not annualized)"),
        })
    return out


def active_drawdown(active: List[float]) -> Dict[str, Any]:
    """Trailing-peak drawdown of the compounded active series."""
    if len(active) < 1:
        return {"available": False, "reason": "no active observations",
                "max_active_drawdown": None, "series": None}
    level = 1.0
    peak = 1.0
    wealth: List[float] = []
    drawdowns: List[float] = []
    for a in active:
        factor = 1.0 + a
        if factor <= 0 or not math.isfinite(factor):
            return {"available": False,
                    "reason": ("the compounded active series became "
                               "non-positive; the relative drawdown is "
                               "withheld"),
                    "max_active_drawdown": None, "series": None}
        level *= factor
        wealth.append(level)
        peak = max(peak, level)
        drawdowns.append(level / peak - 1.0)
    return {
        "available": True,
        "reason": None,
        "max_active_drawdown": min(drawdowns),
        "series": {"wealth": [round(v, 10) for v in wealth],
                   "drawdowns": [round(v, 10) for v in drawdowns]},
        "convention": ("a synthetic long-portfolio / short-benchmark series "
                       "compounded from 1.0 with a trailing-only peak — a "
                       "RELATIVE drawdown measurement, not a realizable loss"),
    }


def concentration(values: List[float], *, label: str) -> Dict[str, Any]:
    """Absolute-contribution concentration with the signed parts separate."""
    absolutes = [abs(v) for v in values]
    total = sum(absolutes)
    positives = [v for v in values if v > 0]
    negatives = [v for v in values if v < 0]
    if total <= CONCENTRATION_EPS:
        return {
            "label": label, "count": len(values),
            "herfindahl": None, "effective_contributors": None,
            "largest_absolute_share": None, "top3_absolute_share": None,
            "positive_total": sum(positives), "negative_total": sum(negatives),
            "state": "unavailable",
            "reason": ("total absolute contribution is zero, so no share can "
                       "be formed"),
            "note": CONCENTRATION_NOTE,
        }
    shares = sorted((a / total for a in absolutes), reverse=True)
    hhi = sum(s * s for s in shares)
    pos_total = sum(positives)
    neg_total = sum(negatives)
    pos_shares = [v / pos_total for v in positives] if pos_total > 0 else []
    neg_shares = [v / neg_total for v in negatives] if neg_total < 0 else []
    return {
        "label": label,
        "count": len(values),
        "herfindahl": hhi,
        "effective_contributors": (1.0 / hhi) if hhi > 0 else None,
        "largest_absolute_share": shares[0],
        "top3_absolute_share": sum(shares[:3]),
        "positive_total": pos_total,
        "negative_total": neg_total,
        "positive_concentration": (sum(s * s for s in pos_shares)
                                   if pos_shares else None),
        "negative_concentration": (sum(s * s for s in neg_shares)
                                   if neg_shares else None),
        "state": "available",
        "reason": None,
        "note": CONCENTRATION_NOTE,
    }


CONCENTRATION_NOTE = (
    "concentration is measured on ABSOLUTE contributions so that offsetting "
    "positive and negative contributions stay visible; a concentrated "
    "measurement is not evidence of poor diversification or overfitting")


__all__ = ["TRACKING_ERROR_EPS", "CONCENTRATION_EPS", "CONCENTRATION_NOTE",
           "active_series", "active_risk", "active_drawdown", "concentration"]
