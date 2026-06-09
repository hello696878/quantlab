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
    Run a single-asset backtest and return equity curves plus a trade log.

    Supports long, cash, short and fractional exposure: ``-1 ≤ position ≤ 1``.
    The return (``position[t] * asset_return[t]``) and cost (``|Δposition| *
    cost_rate``) math is the same for all exposures, so long-only callers
    (position ∈ {0, 1}) are completely unaffected.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices (DatetimeIndex, no NaN).
    position : pd.Series
        Pre-shifted position series (−1 = short, 0 = flat, +1 = long, with
        fractional values allowed for position sizing).
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
    # Single-asset exposure is bounded to no-leverage v1 behaviour.  Fractional
    # values are allowed so position sizing can reduce exposure without
    # duplicating P&L logic.
    if ((position < -1) | (position > 1)).any():
        raise ValueError("position must be between -1 (short) and 1 (long).")

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
    # Actions by transition (prev → new exposure):
    #   0 → +   BUY            + → 0  SELL
    #   0 → -   SHORT          - → 0  COVER
    #   - → +   FLIP_TO_LONG   + → -  FLIP_TO_SHORT
    # Same-sign fractional rebalances are logged as BUY/SELL/SHORT/COVER
    # depending on whether exposure increased or decreased.  Cost is always
    # based on effective turnover (|Δexposure|), matching the vectorised equity
    # math above.
    trades: List[Dict] = []
    # Absolute share count of the currently open position (long or short).
    open_shares: float = 0.0

    for i, (_, chg) in enumerate(pos_change.items()):
        if abs(float(chg)) < 1e-9:
            continue  # no trade on this day

        prev_pos = float(position.iloc[i - 1]) if i > 0 else 0.0
        new_pos = float(position.iloc[i])

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
        cost_usd = equity_before * abs(float(chg)) * cost_rate

        # Choose a familiar action label without collapsing fractional exposure
        # to an integer state.
        if abs(new_pos) < 1e-9:
            action = "SELL" if prev_pos > 0 else "COVER"
        elif abs(prev_pos) < 1e-9:
            action = "BUY" if new_pos > 0 else "SHORT"
        elif prev_pos <= 0 < new_pos:
            action = "FLIP_TO_LONG"
        elif prev_pos >= 0 > new_pos:
            action = "FLIP_TO_SHORT"
        elif new_pos > 0:
            action = "BUY" if new_pos > prev_pos else "SELL"
        else:
            action = "SHORT" if abs(new_pos) > abs(prev_pos) else "COVER"

        if abs(new_pos) < 1e-9:
            trade_shares = open_shares
            open_shares = 0.0
        else:
            new_open_shares = abs(new_pos) * max(equity_before - cost_usd, 0.0) / price
            if prev_pos * new_pos > 0:
                trade_shares = abs(new_open_shares - open_shares)
            elif prev_pos * new_pos < 0:
                trade_shares = open_shares + new_open_shares
            else:
                trade_shares = new_open_shares
            open_shares = new_open_shares

        trades.append(
            {
                "date": date_str,
                "action": action,
                "price": round(price, 4),
                "shares": round(trade_shares, 4),
                "cost": round(cost_usd, 4),
            }
        )

    return strategy_equity, benchmark_equity, trades


def compute_position_diagnostics(
    close: pd.Series,
    position: pd.Series,
    trades: List[Dict],
) -> Dict:
    """
    Direction / exposure diagnostics for a single-asset backtest.

    All figures are computed from the (already shifted) position series and the
    close-to-close returns — no extra assumptions, no fabricated data.  Long /
    short gross returns are *pre-cost* and decompose multiplicatively
    (cash bars contribute a factor of 1):

        (1 + total_gross) = (1 + gross_long) * (1 + gross_short)

    ``short_return_contribution`` is the incremental compound effect the short
    legs added to (or subtracted from) the total gross return relative to the
    long/cash bars alone:  ``gross_short * (1 + gross_long)``.

    Returns a dict matching :class:`schemas.BacktestDiagnostics`.
    """
    pos = position.reindex(close.index).ffill().fillna(0.0)
    daily_return = close.pct_change().fillna(0.0)
    n = len(pos)

    long_mask = pos > 0
    short_mask = pos < 0
    cash_mask = pos == 0

    pct_long = float(long_mask.mean()) if n else 0.0
    pct_short = float(short_mask.mean()) if n else 0.0
    pct_cash = float(cash_mask.mean()) if n else 0.0

    # Per-bar pre-cost strategy market return = position * asset_return.
    market = (pos * daily_return).to_numpy()
    long_factors = market[long_mask.to_numpy()]
    short_factors = market[short_mask.to_numpy()]
    gross_long = float(np.prod(1.0 + long_factors) - 1.0) if long_factors.size else 0.0
    gross_short = float(np.prod(1.0 + short_factors) - 1.0) if short_factors.size else 0.0
    short_contribution = gross_short * (1.0 + gross_long)

    # Turnover: total |Δposition| (open/close = 1, long↔short flip = 2),
    # including the initial move away from cash.
    if n:
        pos_change = pos.diff().fillna(pos.iloc[0])
        turnover = float(pos_change.abs().sum())
    else:
        turnover = 0.0

    if n:
        prev = pos.shift(1).fillna(0.0)
        long_entries = int(((prev <= 0) & (pos > 0)).sum())
        short_entries = int(((prev >= 0) & (pos < 0)).sum())
    else:
        long_entries = 0
        short_entries = 0

    return {
        "long_trade_count": long_entries,
        "short_trade_count": short_entries,
        "percent_time_long": round(pct_long, 6),
        "percent_time_short": round(pct_short, 6),
        "percent_time_cash": round(pct_cash, 6),
        "gross_long_return": round(gross_long, 6),
        "gross_short_return": round(gross_short, 6),
        "short_return_contribution": round(short_contribution, 6),
        "turnover_estimate": round(turnover, 4),
    }


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
