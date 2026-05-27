"""
Strategy signal generation.

Current strategies
------------------
* SMA crossover (long-only)
* RSI mean reversion (long-only)
* Bollinger Band mean reversion (long-only)
* Time-series momentum (long-only)
* Volatility breakout (long-only)

Lookahead-bias rule
-------------------
All signals are shifted forward by one bar before being returned.  This
means: the signal computed from day T's closing prices is applied as the
position for day T+1.  The strategy therefore never "knows" today's close
before deciding today's position.
"""

import pandas as pd


# ===========================================================================
# SMA Crossover
# ===========================================================================

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


# ===========================================================================
# RSI helpers + mean reversion
# ===========================================================================

def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """
    Compute RSI (Relative Strength Index) using rolling average gains/losses.

    RSI ∈ [0, 100].  Traditionally, values below 30 signal oversold conditions
    and values above 70 signal overbought conditions.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices (no NaN).
    window : int
        Look-back period in trading days (default: 14).

    Returns
    -------
    pd.Series named "rsi".
        NaN for the first ``window`` bars (insufficient history).
        Values in [0, 100] thereafter.

    Notes
    -----
    Uses the simple rolling RSI definition:
    avg_gain = rolling mean of positive deltas, avg_loss = rolling mean of
    negative deltas over ``window`` bars.

    Edge cases
    ----------
    * Pure gains (avg_loss = 0, avg_gain > 0)  → RSI = 100.
    * Pure losses (avg_gain = 0, avg_loss > 0) → RSI = 0.
    * Both = 0 (perfectly flat price)           → RSI = 100.
    """
    if window < 2:
        raise ValueError(f"RSI window must be at least 2; got {window}.")

    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)

    avg_gain = gains.rolling(window=window, min_periods=window).mean()
    avg_loss = losses.rolling(window=window, min_periods=window).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.mask(avg_loss == 0.0, 100.0)
    rsi = rsi.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)

    return rsi.rename("rsi")


def rsi_mean_reversion_signals(
    close: pd.Series,
    rsi_window: int = 14,
    oversold_threshold: float = 30.0,
    exit_threshold: float = 50.0,
) -> pd.Series:
    """
    Generate long-only positions from a RSI mean-reversion rule.

    Rules
    -----
    * Enter long (1) when RSI falls **strictly below** ``oversold_threshold``.
    * Exit  flat (0) when RSI rises **above** ``exit_threshold``.
    * Hold the current position between entry and exit (state machine).
    * The raw signal is **shifted by one period** to prevent lookahead bias.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    rsi_window : int
        RSI look-back period in trading days (default: 14).
    oversold_threshold : float
        Enter long when RSI drops below this level (e.g. 30).
    exit_threshold : float
        Exit long when RSI rises above this level (e.g. 50).
        Must be strictly greater than ``oversold_threshold``.

    Returns
    -------
    pd.Series
        Integer position series (0 or 1) with the same index as *close*,
        named "position".  No NaN values.
    """
    if oversold_threshold >= exit_threshold:
        raise ValueError(
            f"oversold_threshold ({oversold_threshold}) must be less than "
            f"exit_threshold ({exit_threshold})."
        )

    rsi = compute_rsi(close, rsi_window)

    # Stateful signal loop — must run sequentially because each bar depends
    # on whether we were already in a position on the previous bar.
    in_position = False
    raw: list[int] = []

    for val in rsi:
        if pd.isna(val):
            # Warm-up period: RSI not yet computable → stay flat.
            raw.append(0)
            continue

        v = float(val)
        if not in_position and v < oversold_threshold:
            in_position = True    # RSI crossed below oversold → enter long
        elif in_position and v > exit_threshold:
            in_position = False   # RSI crossed above exit -> exit

        raw.append(1 if in_position else 0)

    # *** Shift by 1 to prevent lookahead bias ***
    position = pd.Series(raw, index=close.index, name="position")
    position = position.shift(1).fillna(0).astype(int)

    return position


# ===========================================================================
# Bollinger Band helpers + mean reversion
# ===========================================================================

def compute_bollinger_bands(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> tuple:
    """
    Compute Bollinger Bands for a price series.

    Bollinger Bands place an upper and lower envelope around a simple moving
    average at a distance of ``num_std`` standard deviations.  Approximately
    95 % of prices fall within ±2σ bands under the normality assumption.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices (no NaN).
    window : int
        Rolling look-back period in trading days (default: 20).
    num_std : float
        Number of standard deviations for the envelope width (default: 2.0).

    Returns
    -------
    (middle, upper, lower) : tuple of three pd.Series
        All three series share the same index as *close*.
        The first ``window - 1`` values are NaN (insufficient history).
        Series are named "bb_middle", "bb_upper", "bb_lower".

    Notes
    -----
    * Uses sample standard deviation (``ddof=1``), which is conventional.
    * The bands are perfectly symmetric around the middle band.
    """
    if window < 2:
        raise ValueError(f"bb_window must be at least 2; got {window}.")
    if num_std <= 0.0:
        raise ValueError(f"num_std must be positive; got {num_std}.")

    middle = close.rolling(window=window, min_periods=window).mean()
    rolling_std = close.rolling(window=window, min_periods=window).std(ddof=1)
    upper = middle + num_std * rolling_std
    lower = middle - num_std * rolling_std

    return (
        middle.rename("bb_middle"),
        upper.rename("bb_upper"),
        lower.rename("bb_lower"),
    )


def bollinger_band_signals(
    close: pd.Series,
    bb_window: int = 20,
    num_std: float = 2.0,
    exit_band: str = "middle",
) -> pd.Series:
    """
    Generate long-only positions from a Bollinger Band mean-reversion rule.

    Rules
    -----
    * Enter long (1) when close falls **strictly below** the lower Bollinger Band.
    * Exit  flat (0) when close rises **to or above** the selected exit band:
        - ``exit_band="middle"`` → exit when close ≥ middle band (default).
        - ``exit_band="upper"``  → exit when close ≥ upper band (holds longer).
    * Hold the current position between entry and exit (stateful loop).
    * The raw signal is **shifted by one period** to prevent lookahead bias.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    bb_window : int
        Bollinger Band look-back period in trading days (default: 20).
    num_std : float
        Width of the bands in standard deviations (default: 2.0).
    exit_band : str
        Which band to use as the exit target: ``"middle"`` or ``"upper"``.

    Returns
    -------
    pd.Series
        Integer position series (0 or 1) with the same index as *close*,
        named "position".  No NaN values.
    """
    if exit_band not in ("middle", "upper"):
        raise ValueError(
            f"exit_band must be 'middle' or 'upper'; got {exit_band!r}."
        )

    middle, upper, lower = compute_bollinger_bands(close, bb_window, num_std)

    in_position = False
    raw: list = []

    for i in range(len(close)):
        lb = lower.iloc[i]

        if pd.isna(lb):
            # Warm-up period: bands not yet computable → stay flat.
            raw.append(0)
            continue

        p = float(close.iloc[i])

        if not in_position and p < float(lb):
            in_position = True    # Price breached lower band → enter long
        elif in_position:
            exit_level = (
                float(middle.iloc[i]) if exit_band == "middle"
                else float(upper.iloc[i])
            )
            if p >= exit_level:
                in_position = False  # Price recovered to exit band → exit

        raw.append(1 if in_position else 0)

    # *** Shift by 1 to prevent lookahead bias ***
    # position[T] = raw_signal[T-1], held over close[T-1] -> close[T].
    position = pd.Series(raw, index=close.index, name="position")
    position = position.shift(1).fillna(0).astype(int)

    return position


# ===========================================================================
# Time-series momentum
# ===========================================================================

def compute_momentum(close: pd.Series, window: int = 126) -> pd.Series:
    """
    Compute the trailing N-day simple return (time-series momentum signal).

    Defined as  ``close[t] / close[t - window] - 1``,  which equals the
    percentage price change over the look-back period expressed as a decimal
    (e.g. 0.05 = 5 %).

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    window : int
        Look-back period in trading days (default: 126 ≈ 6 months).
        Must be ≥ 1.

    Returns
    -------
    pd.Series named "momentum".
        NaN for the first ``window`` bars (insufficient history).
        Decimal returns (not percentages) thereafter.
    """
    if window < 1:
        raise ValueError(f"momentum_window must be at least 1; got {window}.")

    return close.pct_change(periods=window).rename("momentum")


def momentum_signals(
    close: pd.Series,
    momentum_window: int = 126,
    entry_threshold: float = 0.0,
    exit_threshold: float = 0.0,
) -> pd.Series:
    """
    Generate long-only positions from a time-series momentum rule.

    Rules
    -----
    * Enter long (1) when the trailing return rises **strictly above**
      ``entry_threshold``.
    * Exit  flat (0) when the trailing return falls **to or below**
      ``exit_threshold``.
    * Hold the current position between the two thresholds (hysteresis).
    * The raw signal is **shifted by one period** to prevent lookahead bias.

    Default parameters (both thresholds = 0.0)
    -------------------------------------------
    Enter when any positive trailing return is observed.
    Exit immediately when the trailing return turns flat or negative.
    This is the classical binary time-series momentum rule.

    Hysteresis band (``entry_threshold > exit_threshold``)
    -------------------------------------------------------
    Example: entry=0.05, exit=-0.02.
    Only enter on 5 %+ momentum; hold until momentum falls below −2 %.
    Reduces turn-over in choppy markets at the cost of slower entries.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    momentum_window : int
        Trailing return look-back period in trading days (default: 126).
    entry_threshold : float
        Enter long when momentum **strictly exceeds** this decimal return
        (default: 0.0 → any positive momentum triggers entry).
    exit_threshold : float
        Exit long when momentum **falls to or below** this decimal return
        (default: 0.0 → zero or negative momentum triggers exit).
        Must be ≤ ``entry_threshold``.

    Returns
    -------
    pd.Series
        Integer position series (0 or 1) with the same index as *close*,
        named "position".  No NaN values.
    """
    if entry_threshold < exit_threshold:
        raise ValueError(
            f"entry_threshold ({entry_threshold}) must be >= exit_threshold "
            f"({exit_threshold}).  Set entry >= exit to form a valid "
            "hysteresis band (equal values → no gap, i.e. enter above "
            "threshold and exit at-or-below the same threshold)."
        )

    momentum = compute_momentum(close, momentum_window)

    in_position = False
    raw: list = []

    for val in momentum:
        if pd.isna(val):
            # Warm-up period: not enough history → stay flat.
            raw.append(0)
            continue

        v = float(val)
        if not in_position and v > entry_threshold:
            in_position = True     # Momentum crossed above entry threshold
        elif in_position and v <= exit_threshold:
            in_position = False    # Momentum fell to or below exit threshold

        raw.append(1 if in_position else 0)

    # *** Shift by 1 to prevent lookahead bias ***
    # position[T] = raw_signal[T-1], held over close[T-1] -> close[T].
    position = pd.Series(raw, index=close.index, name="position")
    position = position.shift(1).fillna(0).astype(int)

    return position


# ===========================================================================
# Volatility Breakout
# ===========================================================================

def compute_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    """
    Compute rolling close-to-close volatility as the standard deviation of
    daily percentage returns over ``window`` bars.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    window : int
        Rolling look-back period in trading days (default: 20).
        Must be ≥ 2 (need at least two return observations).

    Returns
    -------
    pd.Series named "volatility".
        NaN for the first ``window`` bars (insufficient history).
        Positive decimal values thereafter (e.g. 0.01 = 1 % daily std).

    Notes
    -----
    Uses sample standard deviation (ddof=1).  The first pct_change value is
    always NaN, so the earliest valid reading appears at index ``window``
    (requiring ``window + 1`` total price observations).
    """
    if window < 2:
        raise ValueError(f"lookback_window must be at least 2; got {window}.")

    daily_ret = close.pct_change()
    return (
        daily_ret.rolling(window=window, min_periods=window)
        .std(ddof=1)
        .rename("volatility")
    )


def volatility_breakout_signals(
    close: pd.Series,
    lookback_window: int = 20,
    breakout_multiplier: float = 1.0,
    exit_window: int = 10,
) -> pd.Series:
    """
    Generate long-only positions from a volatility breakout rule.

    Rules
    -----
    * Compute the rolling standard deviation of daily returns over
      ``lookback_window`` bars as the volatility estimate.
    * A **breakout** fires on bar T when::

          daily_return[T] > breakout_multiplier × volatility[T]

      i.e., today's move is an unusually large positive return relative
      to recent typical daily swings.
    * Enter long (1) immediately on a breakout.
    * **Time-based exit**: exit flat (0) after holding ``exit_window`` bars.
    * If a fresh breakout fires while already in a position, the exit timer
      is **reset** — the position extends for another ``exit_window`` bars
      from the new signal.
    * The raw signal is **shifted by one period** to prevent lookahead bias.

    Default parameters
    ------------------
    ``lookback_window=20, breakout_multiplier=1.0, exit_window=10``

    With these defaults the strategy enters whenever a daily gain exceeds one
    rolling standard deviation and holds for two trading weeks.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    lookback_window : int
        Rolling window for the volatility estimate in trading days (≥ 2).
    breakout_multiplier : float
        Threshold multiplier on volatility for the breakout condition (> 0).
        Higher values require a larger move to trigger entry (fewer trades).
    exit_window : int
        Number of bars to hold the position before exiting (≥ 1).

    Returns
    -------
    pd.Series
        Integer position series (0 or 1) with the same index as *close*,
        named "position".  No NaN values.
    """
    if breakout_multiplier <= 0.0:
        raise ValueError(
            f"breakout_multiplier must be > 0; got {breakout_multiplier}."
        )
    if exit_window < 1:
        raise ValueError(f"exit_window must be at least 1; got {exit_window}.")

    volatility = compute_volatility(close, lookback_window)
    daily_ret = close.pct_change()

    in_position = False
    bars_held = 0
    raw: list[int] = []

    for i in range(len(close)):
        vol = volatility.iloc[i]
        ret = daily_ret.iloc[i]

        if pd.isna(vol) or pd.isna(ret):
            # Warm-up period: not enough history → stay flat.
            raw.append(0)
            continue

        if in_position:
            bars_held += 1
            if bars_held >= exit_window:
                # Time-based exit: held long enough, return to flat.
                in_position = False
                bars_held = 0
            elif float(ret) > float(vol) * breakout_multiplier:
                # New breakout while in position — reset the exit timer.
                bars_held = 0
        else:
            if float(ret) > float(vol) * breakout_multiplier:
                in_position = True
                bars_held = 0  # bars_held counts bars *after* the entry bar

        raw.append(1 if in_position else 0)

    # *** Shift by 1 to prevent lookahead bias ***
    # position[T] = raw_signal[T-1], held over close[T-1] -> close[T].
    position = pd.Series(raw, index=close.index, name="position")
    position = position.shift(1).fillna(0).astype(int)

    return position
