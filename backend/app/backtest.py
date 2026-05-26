"""
Core backtesting engine.

Design decisions
----------------
1. **Vectorised equity curve** — daily returns are computed with numpy/pandas
   broadcast operations, avoiding slow Python loops for the P&L calculation.

2. **Transaction cost model** — costs are charged as a fixed fraction of the
   portfolio value on the day the position changes:
       strategy_return[t] = position[t] * asset_return[t]
                            - |Δposition[t]| * cost_rate
   For a fully-invested long-only strategy (position ∈ {0, 1}) this is
   equivalent to paying *cost_rate* of NAV on each entry and each exit.

3. **Benchmark** — simple buy-and-hold with no transaction costs, invested
   from day 1 (first available close).

4. **Trade log** — a separate pass over position changes records approximate
   BUY/SELL events with prices, shares and dollar costs.  Because the equity
   curve uses a percentage-based cost model the shares figures are approximate
   but internally consistent.
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

    cost_rate = transaction_cost_bps / 10_000.0

    # -----------------------------------------------------------------------
    # 1. Daily close-to-close returns
    # -----------------------------------------------------------------------
    daily_return: pd.Series = close.pct_change().fillna(0.0)

    # Align position to the close index (forward-fill gaps, default flat)
    position = position.reindex(close.index).fillna(0.0)

    # -----------------------------------------------------------------------
    # 2. Position changes  (+1 = enter long, −1 = exit long)
    # -----------------------------------------------------------------------
    # .diff() gives NaN for the first row; fill with position[0] so that a
    # hypothetical non-zero starting position would be costed correctly.
    pos_change: pd.Series = position.diff().fillna(position.iloc[0])

    # -----------------------------------------------------------------------
    # 3. Vectorised strategy return
    #    Hold return   : position[t] * r[t]
    #    Transaction   : |Δposition[t]| * cost_rate  (charged at trade day)
    # -----------------------------------------------------------------------
    strategy_return: pd.Series = position * daily_return - pos_change.abs() * cost_rate

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

    for i, (date, chg) in enumerate(pos_change.items()):
        if abs(chg) < 1e-9:
            continue  # no trade on this day

        price = float(close.iloc[i])
        date_str = str(date.date()) if hasattr(date, "date") else str(date)

        # Equity *before* today's return — this is the capital being deployed.
        equity_before = float(strategy_equity.iloc[i - 1]) if i > 0 else initial_capital

        if chg > 0:
            # ---- BUY -------------------------------------------------------
            # Invest equity_before; cost is deducted from the invested amount.
            cost_usd = equity_before * cost_rate
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
            cost_usd = sell_gross * cost_rate
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
