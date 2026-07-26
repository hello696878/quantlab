"""
Multicollinearity and residual diagnostics (v1).

Nothing here removes, reorders or selects a factor: every diagnostic is a
neutral measurement the reader interprets.  Thresholds are flagged as
warnings with their value attached and are explicitly NOT presented as
universal rules.

Variance inflation factor
-------------------------
    VIF_k = 1 / (1 - R²_k),  R²_k from regressing factor k on the OTHER
    factors with an intercept.

Requires at least two factors, more observations than parameters, a
full-rank sub-design and R²_k < 1.  Any of those failing leaves that VIF
``unavailable`` with a reason — never a large sentinel value, never
infinity.

Residual moments use the same scipy conventions as the repository's Sharpe
diagnostics: ``scipy.stats.skew(bias=True)`` and, for EXCESS kurtosis,
``scipy.stats.kurtosis(fisher=True, bias=True)`` (normal = 0).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as sp_stats

from app.factor_diagnostics.regression import (CONSTANT_TOLERANCE,
                                               ZERO_VARIANCE_TOLERANCE,
                                               RegressionError, ols_fit)

MIN_VIF_OBSERVATIONS = 4
MIN_MOMENT_OBSERVATIONS = 4
MAX_LARGEST_RESIDUALS = 5
HIGH_VIF_WARNING = 10.0

SKEWNESS_CONVENTION = "scipy.stats.skew(bias=True) — population moment"
KURTOSIS_CONVENTION = (
    "EXCESS kurtosis: scipy.stats.kurtosis(fisher=True, bias=True); "
    "normal = 0")
RESIDUAL_DRAWDOWN_CONVENTION = (
    "maximum drawdown of the ADDITIVE cumulative residual sum against its "
    "trailing peak; residuals are not compounded and are not a tradable "
    "series")


def correlation_matrix(factor_values: Sequence[Sequence[float]],
                       names: Sequence[str]) -> Dict[str, Any]:
    """Pearson correlations in the declared factor order; constants stay null."""
    matrix = np.asarray(factor_values, dtype=np.float64)
    n, k = matrix.shape
    spreads = matrix.max(axis=0) - matrix.min(axis=0)
    constant = [bool(s <= CONSTANT_TOLERANCE) for s in spreads]
    rows: List[Dict[str, Any]] = []
    for i in range(k):
        values: List[Optional[float]] = []
        for j in range(k):
            if constant[i] or constant[j]:
                values.append(None)
            elif i == j:
                values.append(1.0)
            else:
                a = matrix[:, i] - matrix[:, i].mean()
                b = matrix[:, j] - matrix[:, j].mean()
                denominator = math.sqrt(float(np.sum(a ** 2))
                                        * float(np.sum(b ** 2)))
                if denominator <= ZERO_VARIANCE_TOLERANCE:
                    values.append(None)
                else:
                    value = float(np.sum(a * b) / denominator)
                    values.append(float(min(1.0, max(-1.0, value))))
        rows.append({"factor_id": names[i], "values": values})
    return {
        "factor_ids": list(names),
        "rows": rows,
        "constant_factors": [names[i] for i in range(k) if constant[i]],
        "note": ("Pearson correlation over the estimation sample; a constant "
                 "factor has no correlation and is reported as unavailable"),
    }


def variance_inflation(factor_values: Sequence[Sequence[float]],
                       names: Sequence[str]) -> List[Dict[str, Any]]:
    """VIF per factor with an explicit availability state."""
    matrix = np.asarray(factor_values, dtype=np.float64)
    n, k = matrix.shape
    out: List[Dict[str, Any]] = []
    for j, name in enumerate(names):
        entry: Dict[str, Any] = {
            "factor_id": name, "vif": None, "r_squared": None,
            "state": "unavailable", "reason": None, "warning": False,
        }
        if k < 2:
            entry["reason"] = ("a variance inflation factor needs at least two "
                               "factors")
            out.append(entry)
            continue
        if n < MIN_VIF_OBSERVATIONS or n <= k:
            entry["reason"] = (
                f"{n} observations cannot support a VIF regression on "
                f"{k - 1} other factor(s)")
            out.append(entry)
            continue
        others = np.delete(matrix, j, axis=1)
        other_names = [names[i] for i in range(k) if i != j]
        target = matrix[:, j]
        if float(target.max() - target.min()) <= CONSTANT_TOLERANCE:
            entry["reason"] = (
                "the factor is constant, so its variance inflation is "
                "undefined")
            out.append(entry)
            continue
        try:
            fit = ols_fit(target, others, other_names, intercept=True,
                          rank_policy="minimum_norm_descriptive")
        except RegressionError as exc:
            entry["reason"] = f"the VIF regression could not be fitted: {exc}"
            out.append(entry)
            continue
        r_squared = fit["r_squared"]
        if r_squared is None:
            entry["reason"] = fit["r_squared_note"]
            out.append(entry)
            continue
        entry["r_squared"] = float(r_squared)
        if r_squared >= 1.0 - 1e-12:
            entry["reason"] = (
                "the factor is an exact linear combination of the others, so "
                "its variance inflation is unbounded and is reported as "
                "unavailable rather than infinite")
            out.append(entry)
            continue
        vif = float(1.0 / (1.0 - r_squared))
        if not math.isfinite(vif):
            entry["reason"] = "the variance inflation factor is not finite"
            out.append(entry)
            continue
        entry.update({"vif": vif, "state": "available",
                      "warning": bool(vif > HIGH_VIF_WARNING)})
        out.append(entry)
    return out


def residual_diagnostics(residuals: Sequence[float],
                         period_stamps: Sequence[str]) -> Dict[str, Any]:
    """Descriptive residual diagnostics — never an alpha or a causal claim."""
    values = np.asarray(residuals, dtype=np.float64)
    n = int(values.size)
    out: Dict[str, Any] = {
        "observations": n,
        "mean": None, "std": None, "skewness": None, "excess_kurtosis": None,
        "lag1_autocorrelation": None, "largest_absolute": [],
        "concentration": None, "effective_periods": None,
        "cumulative_drawdown": None,
        "skewness_convention": SKEWNESS_CONVENTION,
        "kurtosis_convention": KURTOSIS_CONVENTION,
        "drawdown_convention": RESIDUAL_DRAWDOWN_CONVENTION,
        "small_sample_note": None,
        "note": ("residuals are what the declared specification did not "
                 "explain; they are not alpha, not skill and not evidence of "
                 "a missing factor"),
    }
    if n == 0:
        return out
    out["mean"] = float(np.mean(values))
    if n >= 2:
        out["std"] = float(np.std(values, ddof=1))
    if n < MIN_MOMENT_OBSERVATIONS:
        out["small_sample_note"] = (
            f"higher moments need at least {MIN_MOMENT_OBSERVATIONS} "
            f"observations; only {n} are available")
    else:
        spread = float(np.std(values, ddof=1))
        if spread > CONSTANT_TOLERANCE and math.isfinite(spread):
            skew = float(sp_stats.skew(values, bias=True))
            kurt = float(sp_stats.kurtosis(values, fisher=True, bias=True))
            out["skewness"] = skew if math.isfinite(skew) else None
            out["excess_kurtosis"] = kurt if math.isfinite(kurt) else None
        else:
            out["small_sample_note"] = (
                "the residual series is constant, so its shape moments are "
                "undefined")

    if n >= 3:
        centred = values - float(np.mean(values))
        denominator = float(np.sum(centred ** 2))
        if denominator > ZERO_VARIANCE_TOLERANCE:
            numerator = float(np.sum(centred[1:] * centred[:-1]))
            value = numerator / denominator
            if math.isfinite(value):
                out["lag1_autocorrelation"] = float(
                    min(1.0, max(-1.0, value)))

    order = sorted(range(n), key=lambda i: (-abs(float(values[i])), i))
    out["largest_absolute"] = [{
        "period_start": (period_stamps[i] if i < len(period_stamps) else None),
        "residual": float(values[i]),
        "absolute_residual": float(abs(values[i])),
    } for i in order[:MAX_LARGEST_RESIDUALS]]

    squared = values ** 2
    total = float(np.sum(squared))
    if total > ZERO_VARIANCE_TOLERANCE:
        shares = squared / total
        hhi = float(np.sum(shares ** 2))
        out["concentration"] = hhi
        out["effective_periods"] = float(1.0 / hhi) if hhi > 0 else None

    cumulative = np.cumsum(values)
    peak = -math.inf
    drawdown = 0.0
    for value in cumulative:
        peak = max(peak, float(value))
        drawdown = min(drawdown, float(value) - peak)
    out["cumulative_drawdown"] = float(drawdown)
    return out


def stability_metrics(rolling_rows: Sequence[Dict[str, Any]],
                      factor_ids: Sequence[str],
                      window_count: int) -> List[Dict[str, Any]]:
    """Window-to-window coefficient behaviour; never a stability verdict."""
    out: List[Dict[str, Any]] = []
    for factor_id in factor_ids:
        series: List[float] = []
        for row in rolling_rows:
            if row.get("status") != "estimated":
                continue
            value = (row.get("coefficients") or {}).get(factor_id)
            if value is None or not math.isfinite(float(value)):
                continue
            series.append(float(value))
        entry: Dict[str, Any] = {
            "factor_id": factor_id,
            "windows_available": len(series),
            "windows_total": int(window_count),
            "availability_rate": (float(len(series) / window_count)
                                  if window_count else None),
            "mean": None, "median": None, "std": None, "minimum": None,
            "maximum": None, "sign_changes": None, "max_absolute_change": None,
            "mean_absolute_change": None,
            "note": ("a stable measured coefficient is a property of this "
                     "sample and this specification, not a permanent "
                     "property of the factor"),
        }
        if series:
            array = np.asarray(series, dtype=np.float64)
            entry["mean"] = float(np.mean(array))
            entry["median"] = float(np.median(array))
            entry["minimum"] = float(np.min(array))
            entry["maximum"] = float(np.max(array))
            if len(series) >= 2:
                entry["std"] = float(np.std(array, ddof=1))
                changes = np.abs(np.diff(array))
                entry["max_absolute_change"] = float(np.max(changes))
                entry["mean_absolute_change"] = float(np.mean(changes))
                signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in series]
                non_zero = [s for s in signs if s != 0]
                entry["sign_changes"] = int(sum(
                    1 for a, b in zip(non_zero, non_zero[1:]) if a != b))
        out.append(entry)
    return out


__all__ = [
    "MIN_VIF_OBSERVATIONS", "MIN_MOMENT_OBSERVATIONS", "HIGH_VIF_WARNING",
    "SKEWNESS_CONVENTION", "KURTOSIS_CONVENTION",
    "RESIDUAL_DRAWDOWN_CONVENTION", "correlation_matrix",
    "variance_inflation", "residual_diagnostics", "stability_metrics",
]
