"""
Multi-asset portfolio backtesting (v1).

Equal-weight, long-only, fully-invested portfolio with optional periodic
rebalancing.  Pure computation only — price fetching and HTTP concerns live in
the API layer (``main.py``); metrics reuse ``app.metrics.compute_metrics``.

This is intentionally simple: no optimisation, no shorting, no leverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd

REBALANCE_FREQUENCIES = ("none", "monthly", "quarterly", "yearly")


def _date_str(ts) -> str:
    return str(ts.date()) if hasattr(ts, "date") else str(ts)


def _period_key(ts: pd.Timestamp, freq: str):
    """Calendar bucket for a timestamp; rebalancing fires when this changes."""
    if freq == "monthly":
        return (ts.year, ts.month)
    if freq == "quarterly":
        return (ts.year, (ts.month - 1) // 3)
    if freq == "yearly":
        return (ts.year,)
    return None  # "none" → never rebalance


def align_prices(frames: Dict[str, pd.Series]) -> pd.DataFrame:
    """
    Combine per-ticker close series into one frame on their COMMON dates.

    Columns preserve the insertion order of *frames* (i.e. request ticker
    order).  Any date where at least one asset is missing is dropped.
    """
    cleaned = {}
    for ticker, series in frames.items():
        # Keep the last observation for duplicate dates and enforce chronological
        # order before return calculation.
        s = series.copy()
        s.index = pd.to_datetime(s.index)
        s = s.sort_index()
        s = s.groupby(level=0).last()
        cleaned[ticker] = s

    df = pd.DataFrame(cleaned)  # union index, NaN where an asset is missing
    df = df.dropna(how="any")   # keep only fully-populated (common) dates
    return df


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Running peak-to-trough drawdown as a fraction (≤ 0)."""
    peak = equity.cummax()
    return (equity - peak) / peak


@dataclass
class PortfolioResult:
    equity: pd.Series                       # portfolio value per date
    weights: List[dict] = field(default_factory=list)            # [{date, weights}]
    rebalance_events: List[dict] = field(default_factory=list)   # [{date, turnover, cost}]


def run_equal_weight_portfolio(
    prices: pd.DataFrame,
    *,
    initial_capital: float = 100_000.0,
    rebalance_frequency: str = "none",
    transaction_cost_bps: float = 10.0,
) -> PortfolioResult:
    """
    Simulate an equal-weight, long-only, fully-invested portfolio.

    Convention
    ----------
    * Day 0: capital is split equally across the N assets (``equity[0] ==
      initial_capital``; no initial transaction cost is charged).
    * Each subsequent day, holdings drift with each asset's daily return.
    * ``rebalance_frequency`` of monthly/quarterly/yearly resets the holdings to
      equal weight on the FIRST trading day of each new period.  The cost of a
      rebalance is turnover-based:

          turnover = sum_i | target_weight_i - drifted_weight_i |
          cost     = equity_before * turnover * (transaction_cost_bps / 10000)

      and is deducted from portfolio value that day.
    * ``"none"`` never rebalances — weights drift for the whole period.

    Returns daily equity, per-day weights, and the list of rebalance events.
    """
    tickers = list(prices.columns)
    n = len(tickers)
    if n == 0:
        raise ValueError("prices must contain at least one ticker column.")
    if len(prices) < 2:
        raise ValueError("prices must contain at least two common dates.")
    if prices.isna().any().any():
        raise ValueError("prices must not contain missing values.")
    if (prices <= 0).any().any():
        raise ValueError("prices must be strictly positive.")

    dates = prices.index
    returns = prices.pct_change()
    cost_rate = transaction_cost_bps / 10_000.0
    target_w = 1.0 / n

    # Dollar holdings per asset — drift naturally captures weight changes.
    holdings: Dict[str, float] = {t: initial_capital / n for t in tickers}

    equity_vals: List[float] = [float(sum(holdings.values()))]  # == initial_capital
    weights: List[dict] = [
        {"date": _date_str(dates[0]), "weights": {t: round(target_w, 6) for t in tickers}}
    ]
    rebalance_events: List[dict] = []

    last_key = _period_key(dates[0], rebalance_frequency)

    for i in range(1, len(dates)):
        ts = dates[i]

        # 1) Drift holdings by today's asset returns.
        for t in tickers:
            r = returns[t].iloc[i]
            holdings[t] *= 1.0 + (0.0 if pd.isna(r) else float(r))

        equity_before = float(sum(holdings.values()))

        # 2) Rebalance on the first trading day of a new period.
        do_rebalance = False
        if rebalance_frequency != "none":
            key = _period_key(ts, rebalance_frequency)
            if key != last_key:
                do_rebalance = True
                last_key = key

        if do_rebalance and equity_before > 0:
            old_w = {t: holdings[t] / equity_before for t in tickers}
            turnover = float(sum(abs(target_w - old_w[t]) for t in tickers))
            cost = equity_before * turnover * cost_rate
            equity_after = equity_before - cost
            for t in tickers:
                holdings[t] = equity_after / n
            rebalance_events.append(
                {
                    "date": _date_str(ts),
                    "turnover": round(turnover, 6),
                    "cost": round(cost, 2),
                }
            )
            equity_vals.append(equity_after)
            weights.append(
                {"date": _date_str(ts), "weights": {t: round(target_w, 6) for t in tickers}}
            )
        else:
            equity_vals.append(equity_before)
            if equity_before > 0:
                wdict = {t: round(holdings[t] / equity_before, 6) for t in tickers}
            else:
                wdict = {t: 0.0 for t in tickers}
            weights.append({"date": _date_str(ts), "weights": wdict})

    equity = pd.Series(equity_vals, index=dates, name="portfolio")
    return PortfolioResult(
        equity=equity, weights=weights, rebalance_events=rebalance_events
    )
