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
import numpy as np


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


def run_pairs_backtest(
    close_y: pd.Series,
    close_x: pd.Series,
    signal: pd.Series,
    transaction_cost_bps: float = 10.0,
    initial_capital: float = 100_000.0,
) -> Tuple[pd.Series, pd.Series, List[Dict]]:
    """
    Run a dollar-neutral pairs backtest and return equity curves + trade log.

    Position model
    --------------
    Each leg receives 50 % of the portfolio capital:
    * signal = +1  : long  $cap/2 in Y, short $cap/2 in X
    * signal = -1  : short $cap/2 in Y, long  $cap/2 in X
    * signal =  0  : flat

    Daily P&L formula
    -----------------
    spread_return[T] = signal[T] * (ret_y[T] - ret_x[T]) / 2

    The signal already accounts for one-day lookahead prevention (shift(1)).

    Transaction cost model
    ----------------------
    Cost = |signal_change| * cost_rate * equity_before_trade

    A signal move of |1| (e.g. 0->+1) opens two legs at 50 % each, so the
    total cost is proportional to the full portfolio (same formula as the
    single-asset engine).  A reversal (|2|, e.g. +1->-1) closes and
    re-opens both legs, doubling the cost.

    Benchmark
    ---------
    Equal-weight benchmark return:
    benchmark_return[T] = 0.5 * ret_y[T] + 0.5 * ret_x[T]

    Parameters
    ----------
    close_y, close_x : pd.Series
        Adjusted daily close prices, aligned to the same DatetimeIndex.
    signal : pd.Series
        Pre-shifted signal series (-1, 0, +1), same index as close_y/close_x.
    transaction_cost_bps : float
        One-way cost per leg in bps.  Charged on both entry and exit.
    initial_capital : float
        Starting portfolio value in USD.

    Returns
    -------
    strategy_equity : pd.Series
    benchmark_equity : pd.Series
    trades : list of dict (date, action, price, shares, cost)
    """
    if len(close_y) < 2:
        raise ValueError("Need at least 2 price observations to run a backtest.")
    if not close_y.index.equals(close_x.index):
        raise ValueError("close_y and close_x must share the same index.")
    if transaction_cost_bps < 0:
        raise ValueError("transaction_cost_bps must be non-negative.")
    if transaction_cost_bps >= 10_000:
        raise ValueError("transaction_cost_bps must be less than 10,000 bps.")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive.")
    if close_y.isna().any() or close_x.isna().any():
        raise ValueError("pairs close series must not contain NaN values.")
    if (close_y <= 0).any() or (close_x <= 0).any():
        raise ValueError("pairs close prices must be positive.")
    if not close_y.index.is_monotonic_increasing:
        raise ValueError("pairs close index must be sorted in increasing order.")

    cost_rate = transaction_cost_bps / 10_000.0

    signal = signal.reindex(close_y.index).ffill().fillna(0.0)
    if signal.isna().any():
        raise ValueError("signal must not contain NaN values after alignment.")
    if not set(signal.unique()).issubset({-1, 0, 1}):
        raise ValueError("pairs signal must contain only -1, 0, or 1.")

    ret_y: pd.Series = close_y.pct_change().fillna(0.0)
    ret_x: pd.Series = close_x.pct_change().fillna(0.0)

    # Dollar-neutral spread return (50 % each leg).
    spread_return: pd.Series = signal * 0.5 * (ret_y - ret_x)

    # Transaction cost: proportional to magnitude of signal change.
    sig_change: pd.Series = signal.diff().fillna(signal.iloc[0])
    cost_mult: pd.Series = 1.0 - sig_change.abs() * cost_rate
    strategy_return: pd.Series = cost_mult * (1.0 + spread_return) - 1.0

    # Equity curves.
    strategy_equity: pd.Series = initial_capital * (1.0 + strategy_return).cumprod()
    bench_return: pd.Series = 0.5 * (ret_y + ret_x)
    benchmark_equity: pd.Series = initial_capital * (1.0 + bench_return).cumprod()

    # Trade log — one record per signal transition.
    trades: List[Dict] = []
    for i, (_, chg) in enumerate(sig_change.items()):
        if abs(float(chg)) < 0.5:   # no state change
            continue

        new_sig = int(signal.iloc[i])
        exec_i = max(i - 1, 0)
        exec_date = signal.index[exec_i]
        date_str = (
            str(exec_date.date()) if hasattr(exec_date, "date") else str(exec_date)
        )
        price_y = float(close_y.iloc[exec_i])
        equity_before = float(strategy_equity.iloc[i - 1]) if i > 0 else initial_capital
        cost_usd = equity_before * abs(float(chg)) * cost_rate

        if new_sig == 1:
            action = "LONG SPREAD"   # long Y / short X
        elif new_sig == -1:
            action = "SHORT SPREAD"  # short Y / long X
        else:
            action = "EXIT"

        # "Shares" approximated as the dollar amount of the Y leg divided by
        # the Y price — gives the user a concrete feel for position size.
        shares_y = (equity_before * 0.5) / price_y if price_y > 0 else 0.0

        trades.append(
            {
                "date": date_str,
                "action": action,
                "price": round(price_y, 4),
                "shares": round(shares_y, 4),
                "cost": round(cost_usd, 4),
            }
        )

    return strategy_equity, benchmark_equity, trades
