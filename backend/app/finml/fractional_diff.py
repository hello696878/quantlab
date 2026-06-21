"""
Fractional differentiation (López de Prado, AFML ch. 5).

Ordinary first differencing can reduce persistence but also erases much of a
series' *memory* (the differenced series often correlates weakly with the level).
**Fractional differentiation** with ``0 < d < 1`` targets a trade-off between
reduced persistence and memory retention. This module implements recursive weights and a
**fixed-width** transform (weights truncated once they fall below a threshold, so
the window does not grow without bound).

Reuses the existing AFML synthetic path.  Educational methodology only —
preprocessing, **not** a trading signal; the diagnostics here are heuristic and
**not** a formal stationarity test.  Synthetic data, not investment advice.

Weight convention: ``weights[k]`` multiplies ``series[t-k]`` (k=0 is the current
bar, ``weights[0] = 1``); the transform window width is ``len(weights)`` and the
warmup period is ``len(weights) - 1``.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from app.finml.orchestrator import FinmlInputError, validate_finml_inputs
from app.finml.sample_data import generate_synthetic_path

_MIN_DAYS = 50
_MAX_DAYS = 5000
_MAX_WEIGHTS_CAP = 1000
_SERIES_CAP = 1200


def _clean(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    f = float(value)
    return round(f, digits) if math.isfinite(f) else None


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------


def _validate_weight_inputs(d: float, max_size: int, threshold: float) -> None:
    if not math.isfinite(d) or d < 0 or d > 2:
        raise FinmlInputError("d must be between 0 and 2.")
    if not math.isfinite(threshold) or threshold <= 0 or threshold >= 1:
        raise FinmlInputError("weight_threshold must be between 0 and 1 (exclusive).")
    if not isinstance(max_size, int) or isinstance(max_size, bool) or max_size < 2 or max_size > _MAX_WEIGHTS_CAP:
        raise FinmlInputError(f"max_weights must be an integer between 2 and {_MAX_WEIGHTS_CAP}.")


def get_fracdiff_weights(d: float, max_size: int, threshold: float) -> List[float]:
    """Recursive fractional-difference weights ``w[0]=1``, ``w[k] = -w[k-1]·(d-k+1)/k``.

    Generation stops once ``|w[k]| < threshold`` (that weight is not kept) or
    ``max_size`` weights have been produced. ``weights[k]`` applies to lag ``k``.
    """
    _validate_weight_inputs(d, max_size, threshold)
    weights = [1.0]
    for k in range(1, max_size):
        w_k = -weights[-1] * (d - k + 1) / k
        if not math.isfinite(w_k):
            break
        if abs(w_k) < threshold:
            break
        weights.append(w_k)
    return weights


# ---------------------------------------------------------------------------
# Fixed-width fractional differentiation
# ---------------------------------------------------------------------------


def _as_finite_series(series: np.ndarray) -> np.ndarray:
    values = np.asarray(series, dtype=float)
    if values.ndim != 1 or values.size < 1:
        raise FinmlInputError("series must be a non-empty one-dimensional array.")
    if not np.all(np.isfinite(values)):
        raise FinmlInputError("series must contain only finite values.")
    return values


def frac_diff_fixed_width(series: np.ndarray, weights: List[float]) -> Tuple[np.ndarray, int]:
    """Fixed-width fractional difference. Returns ``(fracdiff, warmup)``.

    ``fracdiff[t] = Σ_k weights[k]·series[t-k]`` for ``t >= warmup`` (= width-1);
    earlier entries are NaN.
    """
    series = _as_finite_series(series)
    n = series.shape[0]
    w = np.asarray(weights, dtype=float)
    if w.ndim != 1 or w.size < 1 or not np.all(np.isfinite(w)):
        raise FinmlInputError("weights must be a non-empty finite one-dimensional sequence.")
    width = w.shape[0]
    if width > n:
        raise FinmlInputError("weight count cannot exceed the series length.")
    warmup = width - 1
    fd = np.full(n, np.nan)
    for t in range(warmup, n):
        window = series[t - width + 1 : t + 1][::-1]  # window[k] = series[t-k]
        fd[t] = float(np.dot(w, window))
    return fd, warmup


def first_difference(series: np.ndarray) -> np.ndarray:
    """Ordinary close-price difference ``price[t] - price[t-1]``; ``[0]`` is NaN."""
    series = _as_finite_series(series)
    fd = np.full(series.shape[0], np.nan)
    fd[1:] = series[1:] - series[:-1]
    return fd


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def _safe_corr(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    if a.size < 2 or b.size < 2 or a.size != b.size:
        return None
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    c = float(np.corrcoef(a, b)[0, 1])
    return c if math.isfinite(c) else None


def _trend_slope(series: np.ndarray) -> Optional[float]:
    s = series[np.isfinite(series)]
    if s.size < 2:
        return None
    x = np.arange(s.size, dtype=float)
    slope = abs(float(np.polyfit(x, s, 1)[0]))
    return slope if math.isfinite(slope) else None


def _lag1_autocorr(series: np.ndarray) -> Optional[float]:
    s = series[np.isfinite(series)]
    if s.size < 3:
        return None
    return _safe_corr(s[:-1], s[1:])


def _rolling_windows(series: np.ndarray) -> Optional[np.ndarray]:
    values = series[np.isfinite(series)]
    if values.size < 4:
        return None
    window = min(20, max(3, values.size // 5))
    return np.lib.stride_tricks.sliding_window_view(values, window)


def _rolling_mean_variability(series: np.ndarray) -> Optional[float]:
    """Std of rolling means normalized by full-series std; lower is more stable."""
    windows = _rolling_windows(series)
    if windows is None:
        return None
    values = series[np.isfinite(series)]
    scale = float(np.std(values))
    if scale <= np.finfo(float).eps:
        return 0.0
    metric = float(np.std(np.mean(windows, axis=1)) / scale)
    return metric if math.isfinite(metric) else None


def _rolling_std_variability(series: np.ndarray) -> Optional[float]:
    """Coefficient of variation of rolling standard deviations; lower is more stable."""
    windows = _rolling_windows(series)
    if windows is None:
        return None
    rolling_std = np.std(windows, axis=1)
    mean_std = float(np.mean(rolling_std))
    if mean_std <= np.finfo(float).eps:
        return 0.0
    metric = float(np.std(rolling_std) / mean_std)
    return metric if math.isfinite(metric) else None


def _variance_ratio(series: np.ndarray) -> Optional[float]:
    """Second-half variance divided by first-half variance; values near 1 are more stable."""
    values = series[np.isfinite(series)]
    midpoint = values.size // 2
    if midpoint < 2 or values.size - midpoint < 2:
        return None
    first_variance = float(np.var(values[:midpoint]))
    second_variance = float(np.var(values[midpoint:]))
    if first_variance <= np.finfo(float).eps:
        return 1.0 if second_variance <= np.finfo(float).eps else None
    ratio = second_variance / first_variance
    return ratio if math.isfinite(ratio) else None


def compute_memory_retention(original: np.ndarray, fracdiff: np.ndarray, firstdiff: np.ndarray, warmup: int) -> dict:
    """Correlations on one common date sample for a fair memory comparison."""
    n = original.shape[0]
    common_mask = np.isfinite(original) & np.isfinite(fracdiff) & np.isfinite(firstdiff)
    frac_corr = _safe_corr(original[common_mask], fracdiff[common_mask]) if common_mask.any() else None
    first_corr = _safe_corr(original[common_mask], firstdiff[common_mask]) if common_mask.any() else None

    usable = int(np.isfinite(fracdiff).sum())
    return {
        "fracdiff_correlation": _clean(frac_corr),
        "firstdiff_correlation": _clean(first_corr),
        "usable_observations": usable,
        "comparison_observations": int(common_mask.sum()),
        "data_loss_pct": _clean(warmup / n) if n else 0.0,
    }


def compute_stationarity_diagnostics(original: np.ndarray, fracdiff: np.ndarray, firstdiff: np.ndarray) -> dict:
    return {
        "original_trend_slope": _clean(_trend_slope(original)),
        "fracdiff_trend_slope": _clean(_trend_slope(fracdiff)),
        "firstdiff_trend_slope": _clean(_trend_slope(firstdiff)),
        "original_lag1_autocorr": _clean(_lag1_autocorr(original)),
        "fracdiff_lag1_autocorr": _clean(_lag1_autocorr(fracdiff)),
        "firstdiff_lag1_autocorr": _clean(_lag1_autocorr(firstdiff)),
        "original_rolling_mean_variability": _clean(_rolling_mean_variability(original)),
        "fracdiff_rolling_mean_variability": _clean(_rolling_mean_variability(fracdiff)),
        "firstdiff_rolling_mean_variability": _clean(_rolling_mean_variability(firstdiff)),
        "original_rolling_std_variability": _clean(_rolling_std_variability(original)),
        "fracdiff_rolling_std_variability": _clean(_rolling_std_variability(fracdiff)),
        "firstdiff_rolling_std_variability": _clean(_rolling_std_variability(firstdiff)),
        "original_variance_ratio": _clean(_variance_ratio(original)),
        "fracdiff_variance_ratio": _clean(_variance_ratio(fracdiff)),
        "firstdiff_variance_ratio": _clean(_variance_ratio(firstdiff)),
        "diagnostic_note": (
            "These diagnostics are heuristic, not a formal stationarity test (for example ADF). "
            "Trend slope is absolute; lower lag-1 autocorrelation and rolling variability indicate "
            "less persistence/instability, while a variance ratio nearer 1 means the two half-sample "
            "variances are more similar. None proves stationarity or model usefulness."
        ),
    }


# ---------------------------------------------------------------------------
# Validation + orchestrator
# ---------------------------------------------------------------------------


def validate_fracdiff_inputs(d: float, weight_threshold: float, max_weights: int) -> None:
    _validate_weight_inputs(d, max_weights, weight_threshold)


def _downsample(n: int, cap: int) -> List[int]:
    if n <= cap:
        return list(range(n))
    return sorted({round(i * (n - 1) / (cap - 1)) for i in range(cap)})


def run_fractional_diff_demo(
    n_days: int = 500,
    start_price: float = 100.0,
    drift: float = 0.0002,
    volatility: float = 0.015,
    seed: Optional[int] = 42,
    d: float = 0.5,
    weight_threshold: float = 0.001,
    max_weights: int = 200,
) -> dict:
    """Run the fractional-differentiation demo on a synthetic price path (JSON-ready)."""
    # Reuse the shared AFML path validators for the price-path params (uses a fixed
    # placeholder cusum threshold / vol window — those stages are not used here).
    validate_finml_inputs(
        n_days, start_price, drift, volatility, seed, 0.02, "fixed", 20, 1.5, 1.0, 10
    )
    validate_fracdiff_inputs(d, weight_threshold, max_weights)
    path = generate_synthetic_path(
        n_days, start_price, drift, volatility, seed if seed is not None else 42, 20
    )
    dates = path["dates"]
    close = path["close"]

    effective_max_weights = min(max_weights, n_days - 1)
    weights = get_fracdiff_weights(d, effective_max_weights, weight_threshold)
    fracdiff, warmup = frac_diff_fixed_width(close, weights)
    firstdiff = first_difference(close)

    if not np.all(np.isfinite(fracdiff[warmup:])):
        raise FinmlInputError("Fractional difference produced non-finite values; adjust d / threshold.")

    memory = compute_memory_retention(close, fracdiff, firstdiff, warmup)
    stationarity = compute_stationarity_diagnostics(close, fracdiff, firstdiff)

    idx = _downsample(n_days, _SERIES_CAP)
    original_series = [{"date": dates[i], "value": _clean(float(close[i]), 4)} for i in idx]
    comparison_start = max(warmup, 1)
    comparison_idx = [comparison_start + i for i in _downsample(n_days - comparison_start, _SERIES_CAP)]
    first_series = [
        {"date": dates[i], "value": _clean(float(firstdiff[i]))} for i in comparison_idx
    ]
    frac_series = [
        {"date": dates[i], "value": _clean(float(fracdiff[i]))} for i in comparison_idx
    ]

    warnings = [
        "Synthetic demo data — not live market data.",
        "Fractional differentiation is preprocessing, NOT a trading signal. It can transform a "
        "non-stationary series while preserving more memory than first differencing, but the choice "
        "of d, the threshold, and proper validation are critical.",
        "Stationarity-style diagnostics are heuristic — not a formal stationarity test (no ADF).",
    ]
    if max_weights > effective_max_weights:
        warnings.append(
            f"max_weights was capped at {effective_max_weights} for the {n_days}-observation history "
            "so at least two transformed observations remain."
        )
    if len(weights) == effective_max_weights and abs(weights[-1]) >= weight_threshold:
        warnings.append(
            "The maximum fixed width was reached before the next weight fell below the threshold; "
            "the chosen width affects memory and data loss."
        )
    if memory["fracdiff_correlation"] is None or memory["firstdiff_correlation"] is None:
        warnings.append(
            "A memory correlation was unavailable because the aligned sample was too short or constant."
        )
    if d > 1:
        warnings.append("d above 1 is supported for study but is more aggressive than the usual 0–1 exploration range.")

    return {
        "summary": {
            "d": _clean(d),
            "weight_count": len(weights),
            "warmup_period": int(warmup),
            "usable_observations": memory["usable_observations"],
            "comparison_observations": memory["comparison_observations"],
            "data_loss_pct": memory["data_loss_pct"],
            "fracdiff_correlation": memory["fracdiff_correlation"],
            "firstdiff_correlation": memory["firstdiff_correlation"],
        },
        "series": {
            "original": original_series,
            "first_difference": first_series,
            "fractional_difference": frac_series,
        },
        "weights": [{"k": k, "weight": _clean(w)} for k, w in enumerate(weights)],
        "diagnostics": stationarity,
        "warnings": warnings,
    }
