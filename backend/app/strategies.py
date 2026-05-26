"""
Strategy signal generation.

Current strategies
------------------
* SMA crossover (long-only)

Lookahead-bias rule
-------------------
All signals are shifted forward by one bar before being returned.  This
means: the signal computed from day T's closing prices is applied as the
position for day T+1.  The strategy therefore never "knows" today's close
before deciding today's position.
"""

import pandas as pd


def sma_crossover_signals(
    close: pd.Series,
    fast_window: int = 50,
    slow_window: int = 200,
) -> pd.Series:
    """
    Generate a long-only, fully-invested position series from an SMA crossover.

    Rules
    -----
    * Position = 1 (100 % long) when fast SMA > slow SMA.
    * Position = 0 (flat / cash) when fast SMA <= slow SMA.
    * The raw signal is **shifted by one period** to prevent lookahead bias.
      Days before the slow SMA has enough history are treated as flat (0).

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    fast_window : int
        Fast SMA look-back period in trading days.
    slow_window : int
        Slow SMA look-back period in trading days (must be > fast_window).

    Returns
    -------
    pd.Series
        Integer position series (0 or 1) with the same index as *close*,
        named "position".  No NaN values.
    """
    sma_fast = close.rolling(window=fast_window, min_periods=fast_window).mean()
    sma_slow = close.rolling(window=slow_window, min_periods=slow_window).mean()

    # Raw signal: 1 = fast above slow, 0 = otherwise (includes NaN periods)
    raw_signal = (sma_fast > sma_slow).astype(int)

    # *** Shift by 1 to prevent lookahead bias ***
    # position[T] = raw_signal[T-1], held over close[T-1] -> close[T].
    position = raw_signal.shift(1).fillna(0).astype(int)

    return position.rename("position")
