"""
Performance metrics computed from a daily equity curve.

All annualised metrics assume 252 trading days per year.
The risk-free rate defaults to 0 % (typical for US-equity strategy benchmarks).
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR: int = 252


def compute_metrics(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
) -> Dict[str, float | int]:
    """
    Compute a standard set of performance statistics from a daily equity curve.

    Parameters
    ----------
    equity_curve : pd.Series
        Daily portfolio values (first element = initial capital).  Must have
        at least 2 data points and no NaN values.
    risk_free_rate : float
        Annual risk-free rate as a decimal (default 0.0).

    Returns
    -------
    dict with keys:
        total_return, cagr, sharpe_ratio, sortino_ratio,
        max_drawdown, volatility, win_rate, num_days

    Raises
    ------
    ValueError
        If the equity curve has fewer than 2 data points.
    """
    if len(equity_curve) < 2:
        raise ValueError(
            f"Equity curve must have at least 2 data points; got {len(equity_curve)}."
        )

    # -----------------------------------------------------------------------
    # Daily returns (first return is NaN → drop it)
    # -----------------------------------------------------------------------
    daily_returns: pd.Series = equity_curve.pct_change().dropna()

    # -----------------------------------------------------------------------
    # Total return
    # -----------------------------------------------------------------------
    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0

    # -----------------------------------------------------------------------
    # CAGR
    # -----------------------------------------------------------------------
    n_days = len(equity_curve)  # observations, including the starting day
    n_return_periods = len(daily_returns)
    n_years = n_return_periods / TRADING_DAYS_PER_YEAR
    if n_years > 0 and equity_curve.iloc[0] > 0:
        cagr = float(equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1.0 / n_years) - 1.0
    else:
        cagr = 0.0

    # -----------------------------------------------------------------------
    # Annualised volatility (std of daily returns × √252)
    # -----------------------------------------------------------------------
    volatility = float(daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))

    # -----------------------------------------------------------------------
    # Sharpe ratio  (annualised, risk-free rate subtracted daily)
    # -----------------------------------------------------------------------
    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess_returns = daily_returns - daily_rf
    excess_std = float(excess_returns.std())

    if excess_std > 1e-12:
        sharpe_ratio = float(excess_returns.mean() / excess_std) * np.sqrt(TRADING_DAYS_PER_YEAR)
    else:
        sharpe_ratio = 0.0

    # -----------------------------------------------------------------------
    # Sortino ratio  (downside deviation only)
    # -----------------------------------------------------------------------
    downside_returns = excess_returns.clip(upper=0.0)
    downside_deviation = float(np.sqrt((downside_returns**2).mean()))
    if downside_deviation > 1e-12:
        sortino_ratio = float(excess_returns.mean() / downside_deviation) * np.sqrt(
            TRADING_DAYS_PER_YEAR
        )
    else:
        sortino_ratio = 0.0

    # -----------------------------------------------------------------------
    # Maximum drawdown  (peak-to-trough on the equity curve itself)
    # -----------------------------------------------------------------------
    rolling_peak = equity_curve.cummax()
    drawdown_series = (equity_curve - rolling_peak) / rolling_peak
    max_drawdown = float(drawdown_series.min())  # always <= 0

    # -----------------------------------------------------------------------
    # Win rate  (fraction of positive-return days)
    # -----------------------------------------------------------------------
    win_rate = float((daily_returns > 0).sum() / len(daily_returns)) if len(daily_returns) > 0 else 0.0

    return {
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "sortino_ratio": round(sortino_ratio, 4),
        "max_drawdown": round(max_drawdown, 6),
        "volatility": round(volatility, 6),
        "win_rate": round(win_rate, 4),
        "num_days": int(n_days),
    }
