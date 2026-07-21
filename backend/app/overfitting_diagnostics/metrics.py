"""
Performance-metric policy for candidate ranking (documented, bounded).

CSCV ranking metrics (all higher-is-better, all per-period,
**non-annualized**): ``mean_return``, ``median_return``, ``sharpe_like``.
``cumulative_return`` is descriptive only and is never used for ranking.
Downside-adjusted ratios are deliberately omitted in v1 (no correct existing
implementation to reuse — documented rather than half-built).

Sharpe convention (matches the Model Validation Lab's registry-era
``sharpe_like``): ``mean(returns) / std(returns, ddof=1)`` — per-period
excess return over an implicit risk-free rate of zero, **sample** standard
deviation, no annualization anywhere in the ranking layer.  The caller may
declare ``periods_per_year`` for display/calendar conversion only; nothing
is silently annualized.  Undefined metrics (too few observations, zero
volatility) return None with a note — never zero, never NaN/Infinity.
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import numpy as np

RANKING_METRICS = ("mean_return", "median_return", "sharpe_like")
MIN_METRIC_OBSERVATIONS = 2
ZERO_STD_EPS = 1e-12

SHARPE_CONVENTION = (
    "per-period mean(returns) / std(returns, ddof=1); risk-free assumed 0; "
    "sample standard deviation; NOT annualized"
)


class MetricError(ValueError):
    """Unsupported metric configuration (HTTP 422)."""


def validate_metric(metric: str) -> str:
    if metric not in RANKING_METRICS:
        raise MetricError(f"metric must be one of {RANKING_METRICS}")
    return metric


def metric_value(metric: str, returns: np.ndarray) -> Tuple[Optional[float], Optional[str]]:
    """(value, unavailable_reason) — exactly one of the two is None."""
    r = np.asarray(returns, dtype=np.float64)
    if len(r) < MIN_METRIC_OBSERVATIONS:
        return None, f"needs at least {MIN_METRIC_OBSERVATIONS} observations"
    # Element-level validation guarantees finite INPUTS, but not finite
    # aggregates: extreme magnitudes can overflow a sum/variance to ±inf or
    # NaN.  The documented contract is "never zero, never NaN/Infinity", so
    # every aggregate is checked before it leaves this module.
    if metric == "mean_return":
        return _finite_or_unavailable(float(r.mean()), "mean")
    if metric == "median_return":
        return _finite_or_unavailable(float(np.median(r)), "median")
    if metric == "sharpe_like":
        std = float(r.std(ddof=1))
        if not math.isfinite(std):
            return None, "return standard deviation is not finite (extreme magnitudes)"
        if std <= ZERO_STD_EPS:
            return None, "return standard deviation is zero (constant returns)"
        return _finite_or_unavailable(float(r.mean() / std), "sharpe_like")
    raise MetricError(f"metric must be one of {RANKING_METRICS}")


def _finite_or_unavailable(value: float, label: str) -> Tuple[Optional[float], Optional[str]]:
    if not math.isfinite(value):
        return None, (
            f"the {label} of these returns is not finite (numeric overflow from "
            "extreme return magnitudes)"
        )
    return value, None


def cumulative_return(returns: np.ndarray) -> Optional[float]:
    """Descriptive compound return, or None when it is not finite.

    ``prod(1 + r)`` compounds, so a long series of large returns overflows to
    ±inf even though every input element is finite (2000 periods of +100%
    gives 2**2000).  Returning None keeps the documented "never NaN/Infinity"
    guarantee — an Infinity here would be persisted and then serialised as the
    non-standard JSON literal ``Infinity``, breaking strict JSON consumers.
    """
    value = float(np.prod(1.0 + np.asarray(returns, dtype=np.float64)) - 1.0)
    return value if math.isfinite(value) else None


def matrix_metrics(metric: str, matrix: np.ndarray) -> Tuple[np.ndarray, Dict[int, str]]:
    """Per-column metric over a (T × N) matrix; NaN marks unavailable columns
    internally (never exposed) with reasons keyed by column index."""
    values = np.full(matrix.shape[1], np.nan)
    reasons: Dict[int, str] = {}
    for j in range(matrix.shape[1]):
        value, reason = metric_value(metric, matrix[:, j])
        if value is None:
            reasons[j] = reason or "unavailable"
        else:
            values[j] = value
    return values, reasons


__all__ = [
    "RANKING_METRICS", "MIN_METRIC_OBSERVATIONS", "ZERO_STD_EPS",
    "SHARPE_CONVENTION", "MetricError", "validate_metric", "metric_value",
    "cumulative_return", "matrix_metrics",
]
