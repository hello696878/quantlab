"""
Cross-sectional signal/score matrices for the scanner engine.

Both signals use only information available **through date t** (a lookback window
ending at t); the engine then shifts weights forward one period before computing
P&L, so there is no lookahead.
"""

from __future__ import annotations

import warnings

import numpy as np


def lookback_return(prices: np.ndarray, lookback: int) -> np.ndarray:
    """``R[t] = prices[t]/prices[t-lookback] - 1``; NaN for ``t < lookback``."""
    n = prices.shape[0]
    out = np.full(prices.shape, np.nan)
    if lookback < n:
        out[lookback:] = prices[lookback:] / prices[:-lookback] - 1.0
    return out


def momentum_score(prices: np.ndarray, lookback: int) -> np.ndarray:
    """Cross-sectional momentum: the lookback return itself (long winners)."""
    return lookback_return(prices, lookback)


def reversal_score(prices: np.ndarray, lookback: int) -> np.ndarray:
    """Linear long-short reversal: ``score = -(R - cross-sectional mean(R))``.

    Underperformers (below the universe mean) get positive scores; outperformers
    get negative scores.
    """
    r = lookback_return(prices, lookback)
    # Early rows are all-NaN (insufficient history); nanmean warns on empty slices.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        row_mean = np.nanmean(r, axis=1, keepdims=True)
    return -(r - row_mean)
