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

import numpy as np
import pandas as pd
from scipy.optimize import minimize

REBALANCE_FREQUENCIES = ("none", "monthly", "quarterly", "yearly")
OPTIMIZATION_OBJECTIVES = ("equal_weight", "min_volatility", "max_sharpe")
TRADING_DAYS_PER_YEAR = 252
_MIN_VOL = 1e-12


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


def _validate_price_frame(prices: pd.DataFrame) -> None:
    if len(prices.columns) == 0:
        raise ValueError("prices must contain at least one ticker column.")
    if len(prices) < 2:
        raise ValueError("prices must contain at least two common dates.")
    if prices.isna().any().any():
        raise ValueError("prices must not contain missing values.")
    if not np.isfinite(prices.to_numpy(dtype=float)).all():
        raise ValueError("prices must be finite.")
    if (prices <= 0).any().any():
        raise ValueError("prices must be strictly positive.")


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
    _validate_price_frame(prices)

    dates = prices.index
    returns = prices.pct_change(fill_method=None)
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


# ===========================================================================
# Portfolio optimization (v1, in-sample, long-only)
# ===========================================================================


def annualized_stats(prices: pd.DataFrame):
    """
    Compute annualised expected returns and the annualised covariance matrix
    from daily simple returns.

    Returns
    -------
    (expected_returns, covariance) : (pd.Series, pd.DataFrame)
        Both annualised with a 252-trading-day convention.
    """
    _validate_price_frame(prices)
    daily = prices.pct_change(fill_method=None).dropna(how="any")
    if len(daily) < 2:
        raise ValueError(
            "Need at least 2 daily returns (3 common dates) to estimate "
            "covariance."
        )
    if not np.isfinite(daily.to_numpy(dtype=float)).all():
        raise ValueError("daily returns must be finite.")
    expected_returns = daily.mean() * TRADING_DAYS_PER_YEAR
    covariance = daily.cov() * TRADING_DAYS_PER_YEAR
    if not np.isfinite(expected_returns.to_numpy(dtype=float)).all():
        raise ValueError("expected returns must be finite.")
    if not np.isfinite(covariance.to_numpy(dtype=float)).all():
        raise ValueError("covariance matrix must be finite.")
    return expected_returns, covariance


def portfolio_stats(weights: Dict[str, float], expected_returns: pd.Series, covariance: pd.DataFrame, risk_free_rate: float = 0.0):
    """Return (annual_return, annual_volatility, sharpe) for a weight vector."""
    tickers = list(expected_returns.index)
    w = np.array([weights[t] for t in tickers], dtype=float)
    mu = expected_returns.to_numpy()
    sigma = covariance.to_numpy()
    annual_return = float(w @ mu)
    annual_vol = float(np.sqrt(max(w @ sigma @ w, 0.0)))
    sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > _MIN_VOL else 0.0
    return annual_return, annual_vol, float(sharpe)


def optimize_weights(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    objective: str,
    risk_free_rate: float = 0.0,
) -> Dict[str, float]:
    """
    Solve for long-only weights (w_i >= 0, sum(w) = 1) under one objective.

    * ``equal_weight``    — 1/N (closed form).
    * ``min_volatility``  — minimise w'Σw (convex QP on the simplex).
    * ``max_sharpe``      — maximise (w'μ − rf) / sqrt(w'Σw).

    Uses SLSQP from an equal-weight start.  Tiny negative artefacts are clipped
    and the result is renormalised to sum to exactly 1.
    """
    if objective not in OPTIMIZATION_OBJECTIVES:
        raise ValueError(f"Unsupported objective: {objective!r}.")

    tickers = list(expected_returns.index)
    n = len(tickers)
    mu = expected_returns.to_numpy()
    sigma = covariance.to_numpy()
    if n == 0:
        raise ValueError("expected_returns must contain at least one asset.")
    if list(covariance.index) != tickers or list(covariance.columns) != tickers:
        raise ValueError("covariance matrix must align with expected_returns.")
    if not np.isfinite(mu).all() or not np.isfinite(sigma).all():
        raise ValueError("expected returns and covariance must be finite.")

    # Equal weight (and the trivial single-asset case) is closed-form.
    if objective == "equal_weight" or n == 1:
        return {t: 1.0 / n for t in tickers}

    equal_w = np.full(n, 1.0 / n)
    equal_vol = float(np.sqrt(max(equal_w @ sigma @ equal_w, 0.0)))
    if objective == "max_sharpe" and equal_vol <= _MIN_VOL:
        return {t: 1.0 / n for t in tickers}

    x0 = equal_w
    bounds = [(0.0, 1.0)] * n
    constraints = ({"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)},)

    if objective == "min_volatility":
        def cost(w):
            return float(w @ sigma @ w)  # variance is monotonic in volatility
    else:  # max_sharpe → minimise the negative Sharpe ratio
        def cost(w):
            vol = float(np.sqrt(max(w @ sigma @ w, 0.0)))
            if vol <= _MIN_VOL:
                return 1e6
            return -((w @ mu - risk_free_rate) / vol)

    result = minimize(
        cost,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    if not result.success:
        raise ValueError(f"Portfolio optimization failed: {result.message}")
    if not np.isfinite(result.x).all():
        raise ValueError("Portfolio optimization produced non-finite weights.")

    w = np.clip(np.asarray(result.x, dtype=float), 0.0, None)
    total = w.sum()
    if total <= _MIN_VOL:
        raise ValueError("Portfolio optimization produced zero total weight.")
    w = w / total
    # Full precision so the weights sum to 1 (rounding for display happens at
    # the API serialization boundary).
    return {t: float(wi) for t, wi in zip(tickers, w)}


def buy_and_hold_equity(
    prices: pd.DataFrame, weights: Dict[str, float], initial_capital: float
) -> pd.Series:
    """
    Buy-and-hold equity curve for a fixed starting weight vector.

    Capital is allocated to the target weights on day 0 and then left to drift
    (no rebalancing).  ``equity[0] == initial_capital`` because the weights sum
    to 1.
    """
    _validate_price_frame(prices)
    w = np.array([weights[t] for t in prices.columns], dtype=float)
    if not np.isfinite(w).all():
        raise ValueError("weights must be finite.")
    if (w < -1e-12).any():
        raise ValueError("weights must be non-negative.")
    if abs(float(w.sum()) - 1.0) > 1e-6:
        raise ValueError("weights must sum to 1.")
    normalized = prices.to_numpy() / prices.to_numpy()[0]
    equity = initial_capital * (normalized @ w)
    return pd.Series(equity, index=prices.index, name="portfolio")
