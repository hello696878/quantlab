"""
Core backtesting engine.

Design decisions
----------------
1. **Vectorised equity curve** — daily returns are computed with numpy/pandas
   broadcast operations, avoiding slow Python loops for the P&L calculation.

2. **Transaction cost model** — costs are charged as a fixed fraction of the
   portfolio value when the position changes.  For return interval *t*:
       equity[t] = equity[t-1]
                   * (1 - |Δposition[t]| * cost_rate)
                   * (1 + position[t] * asset_return[t])
   For a fully-invested long-only strategy (position ∈ {0, 1}) this is
   equivalent to paying *cost_rate* of NAV on each entry and each exit.

3. **Benchmark** — simple buy-and-hold with no transaction costs, invested
   from day 1 (first available close).

4. **Trade log** — a separate pass over position changes records BUY/SELL
   events with prices, shares and dollar costs.  A position used for
   close[t-1] -> close[t] returns is executed at close[t-1].
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd


def run_backtest(
    close: pd.Series,
    position: pd.Series,
    transaction_cost_bps: float = 10.0,
    initial_capital: float = 100_000.0,
) -> Tuple[pd.Series, pd.Series, List[Dict]]:
    """
    Run a long-only backtest and return equity curves plus a trade log.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices (DatetimeIndex, no NaN).
    position : pd.Series
        Pre-shifted position series (0 = flat, 1 = fully long).
        Must already account for lookahead-bias prevention.
    transaction_cost_bps : float
        One-way transaction cost in basis points.  Charged on both entry and
        exit (i.e. twice per round-trip).
    initial_capital : float
        Starting portfolio value in USD.

    Returns
    -------
    strategy_equity : pd.Series
        Daily portfolio value for the SMA strategy (DatetimeIndex).
    benchmark_equity : pd.Series
        Daily portfolio value for buy-and-hold (DatetimeIndex).
    trades : list of dict
        Each entry has keys: date, action, price, shares, cost.
    """
    if len(close) < 2:
        raise ValueError("Need at least 2 price observations to run a backtest.")
    if transaction_cost_bps < 0:
        raise ValueError("transaction_cost_bps must be non-negative.")
    if transaction_cost_bps >= 10_000:
        raise ValueError("transaction_cost_bps must be less than 10,000 bps.")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive.")
    if close.isna().any():
        raise ValueError("close must not contain NaN values.")
    if (close <= 0).any():
        raise ValueError("close prices must be positive.")
    if not close.index.is_monotonic_increasing:
        raise ValueError("close index must be sorted in increasing order.")

    cost_rate = transaction_cost_bps / 10_000.0

    # -----------------------------------------------------------------------
    # 1. Daily close-to-close returns
    # -----------------------------------------------------------------------
    daily_return: pd.Series = close.pct_change().fillna(0.0)

    # Align position to the close index (forward-fill gaps, default flat).
    position = position.reindex(close.index).ffill().fillna(0.0)
    if position.isna().any():
        raise ValueError("position must not contain NaN values after alignment.")
    if ((position < 0) | (position > 1)).any():
        raise ValueError("position must be between 0 and 1 for a long-only backtest.")

    # -----------------------------------------------------------------------
    # 2. Position changes  (+1 = enter long, −1 = exit long)
    # -----------------------------------------------------------------------
    # .diff() gives NaN for the first row; fill with position[0] so that a
    # hypothetical non-zero starting position would be costed correctly.
    pos_change: pd.Series = position.diff().fillna(position.iloc[0])

    # -----------------------------------------------------------------------
    # 3. Vectorised strategy return
    #    position[t] is the exposure held over close[t-1] -> close[t].
    #    Costs are paid before that interval's market return is earned.
    # -----------------------------------------------------------------------
    cost_multiplier: pd.Series = 1.0 - pos_change.abs() * cost_rate
    market_multiplier: pd.Series = 1.0 + position * daily_return
    strategy_return: pd.Series = cost_multiplier * market_multiplier - 1.0

    # -----------------------------------------------------------------------
    # 4. Equity curves
    # -----------------------------------------------------------------------
    strategy_equity: pd.Series = initial_capital * (1 + strategy_return).cumprod()
    benchmark_equity: pd.Series = initial_capital * (1 + daily_return).cumprod()

    # -----------------------------------------------------------------------
    # 5. Trade log
    # -----------------------------------------------------------------------
    trades: List[Dict] = []
    buy_shares: float = 0.0

    for i, (_, chg) in enumerate(pos_change.items()):
        if abs(chg) < 1e-9:
            continue  # no trade on this day

        execution_i = max(i - 1, 0)
        execution_date = close.index[execution_i]
        price = float(close.iloc[execution_i])
        date_str = (
            str(execution_date.date())
            if hasattr(execution_date, "date")
            else str(execution_date)
        )

        # Equity at the execution close, before the new trade cost is deducted.
        equity_before = float(strategy_equity.iloc[i - 1]) if i > 0 else initial_capital

        if chg > 0:
            # ---- BUY -------------------------------------------------------
            # Invest equity_before; cost is deducted from the invested amount.
            cost_usd = equity_before * abs(float(chg)) * cost_rate
            buy_shares = (equity_before - cost_usd) / price
            trades.append(
                {
                    "date": date_str,
                    "action": "BUY",
                    "price": round(price, 4),
                    "shares": round(buy_shares, 4),
                    "cost": round(cost_usd, 4),
                }
            )
        else:
            # ---- SELL ------------------------------------------------------
            sell_gross = buy_shares * price
            cost_usd = sell_gross * abs(float(chg)) * cost_rate
            trades.append(
                {
                    "date": date_str,
                    "action": "SELL",
                    "price": round(price, 4),
                    "shares": round(buy_shares, 4),
                    "cost": round(cost_usd, 4),
                }
            )
            buy_shares = 0.0

    return strategy_equity, benchmark_equity, trades
