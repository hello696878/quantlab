"""
Decay-curve diagnostics (v1).

A decay curve is the SEQUENCE of per-horizon measurements — nothing more.
The descriptive summary statistics here locate features of that sequence
(first sign change, first drop below a caller-configured threshold, the
largest absolute value and its horizon, the ratio to the first horizon)
without ever calling any horizon optimal, best or recommended.

Exponential fit and half-life
-----------------------------
An optional exponential fit ``|stat_h| ~ A · exp(b·h)`` is estimated by
ordinary least squares on ``ln|stat_h|`` and is offered ONLY when it is
mathematically coherent on this data:

* at least 3 horizons carry an available statistic,
* every fitted statistic is non-zero and shares one sign,
* the fitted slope ``b`` is finite.

``half_life = -ln(2) / b`` is reported only when additionally ``b < 0``
(the magnitude actually shrinks).  Otherwise half-life is **null with a
reason** — never extrapolated, never clamped.  The fit is labelled
descriptive: it assumes a single exponential shape that nothing here
verifies.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


class DecayError(ValueError):
    """Invalid decay configuration (HTTP 422)."""


def validate_decay_config(raw: Any) -> Dict[str, Any]:
    cfg = dict(raw or {})
    unknown = sorted(set(cfg) - {"absolute_threshold"})
    if unknown:
        raise DecayError(f"unknown decay keys: {unknown}")
    threshold = cfg.get("absolute_threshold")
    if threshold is not None:
        if isinstance(threshold, bool) \
                or not isinstance(threshold, (int, float)) \
                or not math.isfinite(float(threshold)) \
                or not (0.0 < float(threshold) < 1.0):
            raise DecayError(
                "absolute_threshold must be a finite number in (0, 1)")
        threshold = float(threshold)
    return {"absolute_threshold": threshold}


def decay_summary(horizon_rows: Sequence[Dict[str, Any]], *,
                  statistic_key: str,
                  absolute_threshold: Optional[float]) -> Dict[str, Any]:
    """Descriptive summary over per-horizon rows ordered by horizon."""
    series: List[Dict[str, Any]] = []
    for row in horizon_rows:
        value = row.get(statistic_key)
        if isinstance(row.get("horizon"), int) and value is not None \
                and math.isfinite(float(value)):
            series.append({"horizon": row["horizon"], "value": float(value)})
    series.sort(key=lambda r: r["horizon"])

    out: Dict[str, Any] = {
        "statistic": statistic_key,
        "horizons_available": len(series),
        "first_sign_change_horizon": None,
        "first_below_threshold_horizon": None,
        "absolute_threshold": absolute_threshold,
        "max_absolute_statistic": None,
        "max_absolute_horizon": None,
        "ratio_to_first_horizon": {},
        "note": ("descriptive features of the measured sequence; the horizon "
                 "with the largest statistic is a location in this sample, "
                 "never an optimal or recommended horizon"),
    }
    if not series:
        return out

    first_sign = math.copysign(1.0, series[0]["value"]) \
        if series[0]["value"] != 0 else 0.0
    for row in series[1:]:
        if row["value"] == 0:
            continue
        if first_sign != 0 and math.copysign(1.0, row["value"]) != first_sign:
            out["first_sign_change_horizon"] = row["horizon"]
            break

    if absolute_threshold is not None:
        for row in series:
            if abs(row["value"]) < absolute_threshold:
                out["first_below_threshold_horizon"] = row["horizon"]
                break

    peak = max(series, key=lambda r: abs(r["value"]))
    out["max_absolute_statistic"] = abs(peak["value"])
    out["max_absolute_horizon"] = peak["horizon"]

    first_value = series[0]["value"]
    if first_value != 0:
        out["ratio_to_first_horizon"] = {
            str(row["horizon"]): float(row["value"] / first_value)
            for row in series}

    out["exponential_fit"] = _exponential_fit(series)
    return out


def _exponential_fit(series: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "state": "unavailable", "reason": None,
        "log_slope": None, "log_intercept": None, "half_life": None,
        "half_life_unit": "horizon units",
        "convention": ("OLS on ln|stat_h| against h; half_life = -ln(2)/b "
                       "only when the fitted slope b is negative and finite; "
                       "DESCRIPTIVE — assumes a single exponential shape "
                       "that nothing here verifies"),
    }
    if len(series) < 3:
        out["reason"] = "fewer than 3 available horizons"
        return out
    values = [row["value"] for row in series]
    if any(v == 0 for v in values):
        out["reason"] = ("a zero statistic makes ln|stat| undefined; the fit "
                         "is withheld rather than patched")
        return out
    signs = {math.copysign(1.0, v) for v in values}
    if len(signs) > 1:
        out["reason"] = ("the statistic changes sign across horizons, so a "
                         "single exponential magnitude model is incoherent "
                         "on this data")
        return out
    x = np.asarray([row["horizon"] for row in series], dtype=np.float64)
    y = np.log(np.abs(np.asarray(values, dtype=np.float64)))
    design = np.column_stack([np.ones(x.size), x])
    coef, _res, _rank, _sv = np.linalg.lstsq(design, y, rcond=None)
    intercept, slope = float(coef[0]), float(coef[1])
    if not (math.isfinite(intercept) and math.isfinite(slope)):
        out["reason"] = "the fitted coefficients are not finite"
        return out
    out.update({"state": "available", "log_intercept": intercept,
                "log_slope": slope})
    if slope < 0:
        out["half_life"] = float(-math.log(2.0) / slope)
    else:
        out["reason"] = ("the fitted slope is non-negative (the magnitude "
                         "does not shrink), so no half-life is defined")
    return out


__all__ = ["DecayError", "validate_decay_config", "decay_summary"]
