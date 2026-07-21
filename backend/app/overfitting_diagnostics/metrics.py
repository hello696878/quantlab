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
    if metric == "mean_return":
        return float(r.mean()), None
    if metric == "median_return":
        return float(np.median(r)), None
    if metric == "sharpe_like":
        std = float(r.std(ddof=1))
        if std <= ZERO_STD_EPS:
            return None, "return standard deviation is zero (constant returns)"
        return float(r.mean() / std), None
    raise MetricError(f"metric must be one of {RANKING_METRICS}")


def cumulative_return(returns: np.ndarray) -> float:
    """Descriptive compound return (never a ranking metric)."""
    return float(np.prod(1.0 + np.asarray(returns, dtype=np.float64)) - 1.0)


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
