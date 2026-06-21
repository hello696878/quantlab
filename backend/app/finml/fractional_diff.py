"""
Fractional differentiation (López de Prado, AFML ch. 5).

Ordinary first differencing makes a price series stationary but erases almost all
*memory* (the differenced series barely correlates with the level).  **Fractional
differentiation** with ``0 < d < 1`` removes enough non-stationarity to be usable
while preserving more memory.  This module implements the recursive weights and a
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


def get_fracdiff_weights(d: float, max_size: int, threshold: float) -> List[float]:
    """Recursive fractional-difference weights ``w[0]=1``, ``w[k] = -w[k-1]·(d-k+1)/k``.

    Generation stops once ``|w[k]| < threshold`` (that weight is not kept) or
    ``max_size`` weights have been produced. ``weights[k]`` applies to lag ``k``.
    """
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


def frac_diff_fixed_width(series: np.ndarray, weights: List[float]) -> Tuple[np.ndarray, int]:
    """Fixed-width fractional difference. Returns ``(fracdiff, warmup)``.

    ``fracdiff[t] = Σ_k weights[k]·series[t-k]`` for ``t >= warmup`` (= width-1);
    earlier entries are NaN.
    """
    n = series.shape[0]
    w = np.asarray(weights, dtype=float)
    width = w.shape[0]
    warmup = width - 1
    fd = np.full(n, np.nan)
    for t in range(warmup, n):
        window = series[t - width + 1 : t + 1][::-1]  # window[k] = series[t-k]
        fd[t] = float(np.dot(w, window))
    return fd, warmup


def first_difference(series: np.ndarray) -> np.ndarray:
    """Ordinary first difference; ``[0]`` is NaN (no prior observation)."""
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
    slope = float(np.polyfit(x, s, 1)[0])
    return slope if math.isfinite(slope) else None


def _lag1_autocorr(series: np.ndarray) -> Optional[float]:
    s = series[np.isfinite(series)]
    if s.size < 3:
        return None
    return _safe_corr(s[:-1], s[1:])


def compute_memory_retention(original: np.ndarray, fracdiff: np.ndarray, firstdiff: np.ndarray, warmup: int) -> dict:
    """Correlation of the level series with the fractional / first differences."""
    n = original.shape[0]
    frac_aligned = fracdiff[warmup:]
    orig_for_frac = original[warmup:]
    fd_mask = np.isfinite(frac_aligned)
    frac_corr = _safe_corr(orig_for_frac[fd_mask], frac_aligned[fd_mask]) if fd_mask.any() else None

    fdiff = firstdiff[1:]
    orig_for_first = original[1:]
    first_corr = _safe_corr(orig_for_first, fdiff)

    usable = int(np.isfinite(fracdiff).sum())
    return {
        "fracdiff_correlation": _clean(frac_corr),
        "firstdiff_correlation": _clean(first_corr),
        "usable_observations": usable,
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
        "diagnostic_note": (
            "These diagnostics are heuristic (trend slope + lag-1 autocorrelation) and are NOT a "
            "formal stationarity test (e.g. ADF). A lower lag-1 autocorrelation and a flatter trend "
            "suggest a more stationary series."
        ),
    }


# ---------------------------------------------------------------------------
# Validation + orchestrator
# ---------------------------------------------------------------------------


def validate_fracdiff_inputs(d: float, weight_threshold: float, max_weights: int) -> None:
    if not math.isfinite(d) or d < 0 or d > 2:
        raise FinmlInputError("d must be between 0 and 2.")
    if not math.isfinite(weight_threshold) or weight_threshold <= 0 or weight_threshold >= 1:
        raise FinmlInputError("weight_threshold must be between 0 and 1 (exclusive).")
    if not isinstance(max_weights, int) or isinstance(max_weights, bool) or max_weights < 2 or max_weights > _MAX_WEIGHTS_CAP:
        raise FinmlInputError(f"max_weights must be an integer between 2 and {_MAX_WEIGHTS_CAP}.")


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
    if max_weights >= n_days:
        raise FinmlInputError("max_weights must be smaller than n_days.")

    path = generate_synthetic_path(
        n_days, start_price, drift, volatility, seed if seed is not None else 42, 20
    )
    dates = path["dates"]
    close = path["close"]

    weights = get_fracdiff_weights(d, max_weights, weight_threshold)
    fracdiff, warmup = frac_diff_fixed_width(close, weights)
    firstdiff = first_difference(close)

    if not np.all(np.isfinite(fracdiff[warmup:])):
        raise FinmlInputError("Fractional difference produced non-finite values; adjust d / threshold.")

    memory = compute_memory_retention(close, fracdiff, firstdiff, warmup)
    stationarity = compute_stationarity_diagnostics(close, fracdiff, firstdiff)

    idx = _downsample(n_days, _SERIES_CAP)
    original_series = [{"date": dates[i], "value": _clean(float(close[i]), 4)} for i in idx]
    first_series = [
        {"date": dates[i], "value": _clean(float(firstdiff[i]))} for i in idx if math.isfinite(firstdiff[i])
    ]
    frac_series = [
        {"date": dates[i], "value": _clean(float(fracdiff[i]))} for i in idx if math.isfinite(fracdiff[i])
    ]

    warnings = [
        "Synthetic demo data — not live market data.",
        "Fractional differentiation is preprocessing, NOT a trading signal. It can transform a "
        "non-stationary series while preserving more memory than first differencing, but the choice "
        "of d, the threshold, and proper validation are critical.",
        "Stationarity-style diagnostics are heuristic — not a formal stationarity test (no ADF).",
    ]

    return {
        "summary": {
            "d": _clean(d),
            "weight_count": len(weights),
            "warmup_period": int(warmup),
            "usable_observations": memory["usable_observations"],
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
