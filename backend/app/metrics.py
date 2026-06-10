"""
Performance metrics computed from a daily equity curve.

Annualized metrics use a configurable ``periods_per_year`` convention.  The
default remains 252 trading days per year for backward compatibility.
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
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
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
    periods_per_year : int
        Annualization convention — return periods per year (default 252 for
        equities; 365 for 24/7 crypto daily data).  Affects CAGR, volatility,
        Sharpe, Sortino, and Calmar only; it never changes total return,
        drawdown, or the equity curve.  The default keeps results identical to
        before.

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
    if periods_per_year <= 0:
        raise ValueError(f"periods_per_year must be positive; got {periods_per_year}.")

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
    n_years = n_return_periods / periods_per_year
    if n_years > 0 and equity_curve.iloc[0] > 0:
        cagr = float(equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1.0 / n_years) - 1.0
    else:
        cagr = 0.0

    # -----------------------------------------------------------------------
    # Annualised volatility (std of daily returns × √periods_per_year)
    # -----------------------------------------------------------------------
    daily_std = float(daily_returns.std())
    volatility = (
        float(daily_std * np.sqrt(periods_per_year))
        if np.isfinite(daily_std)
        else 0.0
    )

    # -----------------------------------------------------------------------
    # Sharpe ratio  (annualised, risk-free rate subtracted daily)
    # -----------------------------------------------------------------------
    daily_rf = risk_free_rate / periods_per_year
    excess_returns = daily_returns - daily_rf
    excess_std = float(excess_returns.std())

    if np.isfinite(excess_std) and excess_std > 1e-12:
        sharpe_ratio = float(excess_returns.mean() / excess_std) * np.sqrt(periods_per_year)
    else:
        sharpe_ratio = 0.0

    # -----------------------------------------------------------------------
    # Sortino ratio  (downside deviation only)
    # -----------------------------------------------------------------------
    downside_returns = excess_returns.clip(upper=0.0)
    downside_deviation = float(np.sqrt((downside_returns**2).mean()))
    if downside_deviation > 1e-12:
        sortino_ratio = float(excess_returns.mean() / downside_deviation) * np.sqrt(
            periods_per_year
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

    # -----------------------------------------------------------------------
    # Calmar ratio  (CAGR / |max_drawdown|)
    # 0.0 when there is no drawdown (undefined, use conservative default).
    # -----------------------------------------------------------------------
    calmar_ratio = round(cagr / abs(max_drawdown), 4) if abs(max_drawdown) > 1e-12 else 0.0

    return {
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "sortino_ratio": round(sortino_ratio, 4),
        "max_drawdown": round(max_drawdown, 6),
        "volatility": round(volatility, 6),
        "calmar_ratio": calmar_ratio,
        "win_rate": round(win_rate, 4),
        "num_days": int(n_days),
    }
