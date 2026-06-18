"""
Synthetic sample universe for the Cross-Sectional Scanner Engine.

Deterministic given a seed.  Generates a panel of synthetic tickers across a few
sectors with a market factor, sector factors, and an idiosyncratic component that
carries a **mild short-term reversal** (a disclosed, realistic property — *not*
evidence any strategy works on real markets).  No live market data.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

SECTORS = ["Tech", "Healthcare", "Financials", "Industrials", "Energy"]

# Mild idiosyncratic short-term reversal (AR(1) coefficient) — disclosed in the
# diagnostics so the demo is transparent, not a fabricated profitable backtest.
_IDIO_REVERSAL_PHI = -0.07
_IDIO_VOL = 0.015
_MARKET_DRIFT = 0.0003
_MARKET_VOL = 0.010
_SECTOR_VOL = 0.006


def generate_sample_universe(
    n_assets: int,
    start_date: str,
    end_date: str,
    seed: int = 42,
) -> dict:
    """Return a deterministic synthetic universe panel.

    Keys: ``tickers``, ``sectors``, ``dates`` (ISO strings), ``date_index``
    (pandas), ``prices`` / ``returns`` (n_dates × n_assets), ``liquidity``.
    """
    rng = np.random.default_rng(seed)
    date_index = pd.bdate_range(start=start_date, end=end_date)
    n_dates = len(date_index)
    if n_dates < 2:
        raise ValueError("date range produces fewer than two business days.")

    tickers = [f"STK{i + 1:03d}" for i in range(n_assets)]
    sector_idx = np.array([i % len(SECTORS) for i in range(n_assets)])
    sectors = [SECTORS[i] for i in sector_idx]

    betas = rng.uniform(0.7, 1.3, n_assets)
    size = rng.lognormal(mean=0.0, sigma=1.0, size=n_assets)
    liquidity = size / size.max()  # relative liquidity score in (0, 1]

    market = rng.normal(_MARKET_DRIFT, _MARKET_VOL, n_dates)
    sector_factor = rng.normal(0.0, _SECTOR_VOL, (n_dates, len(SECTORS)))

    eps = rng.normal(0.0, _IDIO_VOL, (n_dates, n_assets))
    idio = np.empty((n_dates, n_assets))
    idio[0] = eps[0]
    for t in range(1, n_dates):
        idio[t] = _IDIO_REVERSAL_PHI * idio[t - 1] + eps[t]

    log_ret = market[:, None] * betas[None, :] + sector_factor[:, sector_idx] + idio
    log_ret[0] = 0.0
    prices = 100.0 * np.exp(np.cumsum(log_ret, axis=0))

    returns = np.zeros((n_dates, n_assets))
    returns[1:] = prices[1:] / prices[:-1] - 1.0

    return {
        "tickers": tickers,
        "sectors": sectors,
        "dates": [d.strftime("%Y-%m-%d") for d in date_index],
        "date_index": date_index,
        "prices": prices,
        "returns": returns,
        "liquidity": liquidity,
    }
