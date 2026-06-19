"""
Synthetic close-price path for the AFML methodology demo.

Deterministic given a seed.  Geometric Brownian-ish daily log returns plus a
rolling daily-volatility estimate (used as the triple-barrier target).  No live
market data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def generate_synthetic_path(
    n_days: int,
    start_price: float,
    drift: float,
    volatility: float,
    seed: int = 42,
    volatility_window: int = 20,
) -> dict:
    """Return a deterministic synthetic price path.

    Keys: ``dates`` (ISO strings), ``close``, ``returns`` (simple, ``[0]=0``),
    ``rolling_vol`` (rolling sample std of returns, NaN-free).
    """
    rng = np.random.default_rng(seed)
    log_ret = rng.normal(drift, volatility, n_days)
    log_ret[0] = 0.0
    close = start_price * np.exp(np.cumsum(log_ret))

    returns = np.zeros(n_days)
    returns[1:] = close[1:] / close[:-1] - 1.0

    # Rolling sample std of the (real) returns; early points fall back to the
    # input volatility so there is always a finite target. Uses only information
    # available at each date.
    s = pd.Series(returns)
    rolling = s.rolling(window=volatility_window, min_periods=2).std(ddof=1)
    rolling_vol = np.array(rolling.to_numpy(), dtype=float)  # writable copy
    rolling_vol[~np.isfinite(rolling_vol)] = volatility
    rolling_vol[rolling_vol <= 0] = volatility

    dates = pd.bdate_range(start="2020-01-01", periods=n_days)
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in dates],
        "close": close,
        "returns": returns,
        "rolling_vol": rolling_vol,
    }
