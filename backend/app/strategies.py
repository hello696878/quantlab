"""
Strategy signal generation.

Current strategies
------------------
* SMA crossover (long-only)
* RSI mean reversion (long-only)
* Bollinger Band mean reversion (long-only)
* Time-series momentum (long-only)
* Volatility breakout (long-only)
* Pairs trading / statistical arbitrage (long-short, two assets)

Lookahead-bias rule
-------------------
All signals are shifted forward by one bar before being returned.  This
means: the signal computed from day T's closing prices is applied as the
position for day T+1.  The strategy therefore never "knows" today's close
before deciding today's position.
"""

import numpy as np
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

def compute_volatility_breakout_levels(
    close: pd.Series,
    lookback_window: int = 20,
    breakout_multiplier: float = 1.0,
    exit_window: int = 10,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute price-channel breakout and rolling-mean exit levels.

    The breakout threshold for bar T is based only on information available
    through bar T-1:

        rolling_high[T-1] + breakout_multiplier * rolling_range[T-1]

    where rolling_range = rolling_high - rolling_low over ``lookback_window``.

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    lookback_window : int
        Rolling high/low look-back period in trading days (default: 20).
    breakout_multiplier : float
        Multiplier applied to the prior rolling high-low range.
    exit_window : int
        Rolling mean window for the exit level.

    Returns
    -------
    (breakout_level, exit_level) : tuple of pd.Series
        ``breakout_level`` is shifted by one bar to avoid using today's close
        in today's entry threshold. ``exit_level`` is the rolling mean ending
        at the current bar and must still be signal-shifted before trading.
    """
    if lookback_window < 2:
        raise ValueError(
            f"lookback_window must be at least 2; got {lookback_window}."
        )
    if breakout_multiplier <= 0.0:
        raise ValueError(
            f"breakout_multiplier must be > 0; got {breakout_multiplier}."
        )
    if exit_window < 1:
        raise ValueError(f"exit_window must be at least 1; got {exit_window}.")

    rolling_high = close.rolling(
        window=lookback_window, min_periods=lookback_window
    ).max()
    rolling_low = close.rolling(
        window=lookback_window, min_periods=lookback_window
    ).min()
    rolling_range = rolling_high - rolling_low

    breakout_level = (
        rolling_high.shift(1) + breakout_multiplier * rolling_range.shift(1)
    ).rename("breakout_level")
    exit_level = close.rolling(
        window=exit_window, min_periods=exit_window
    ).mean().rename("exit_level")

    return breakout_level, exit_level


def compute_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    """
    Backward-compatible alias for the breakout entry level.

    Prefer ``compute_volatility_breakout_levels`` for new code.
    """
    breakout_level, _ = compute_volatility_breakout_levels(
        close,
        lookback_window=window,
        breakout_multiplier=1.0,
        exit_window=1,
    )
    return breakout_level.rename("volatility")


def volatility_breakout_signals(
    close: pd.Series,
    lookback_window: int = 20,
    breakout_multiplier: float = 1.0,
    exit_window: int = 10,
) -> pd.Series:
    """
    Generate long-only positions from a price-channel volatility breakout rule.

    Rules
    -----
    * rolling_high[T] = max(close[T-lookback_window+1 : T])
    * rolling_low[T] = min(close[T-lookback_window+1 : T])
    * breakout_level[T] = rolling_high[T-1]
                          + breakout_multiplier * rolling_range[T-1]
    * exit_level[T] = rolling_mean(close, exit_window)[T]
    * Enter long (1) when close[T] is strictly above breakout_level[T].
    * Exit flat (0) when close[T] is strictly below exit_level[T].
    * Maintain the current position between entry and exit.
    * The raw signal is **shifted by one period** to prevent lookahead bias.

    Default parameters
    ------------------
    ``lookback_window=20, breakout_multiplier=1.0, exit_window=10``

    Parameters
    ----------
    close : pd.Series
        Adjusted daily closing prices with a DatetimeIndex.
    lookback_window : int
        Rolling high/low lookback window in trading days (≥ 2).
    breakout_multiplier : float
        Multiplier applied to the prior rolling high-low range (> 0).
    exit_window : int
        Rolling mean window for the exit level (≥ 1).

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

    breakout_level, exit_level = compute_volatility_breakout_levels(
        close,
        lookback_window=lookback_window,
        breakout_multiplier=breakout_multiplier,
        exit_window=exit_window,
    )

    in_position = False
    raw: list[int] = []

    for i in range(len(close)):
        entry_level = breakout_level.iloc[i]
        exit_ma = exit_level.iloc[i]
        price = float(close.iloc[i])

        if pd.isna(entry_level):
            # Warm-up period: not enough history for prior breakout channel.
            raw.append(0)
            continue

        if in_position:
            if not pd.isna(exit_ma) and price < float(exit_ma):
                in_position = False
            elif price > float(entry_level):
                in_position = True
        else:
            if price > float(entry_level):
                in_position = True

        raw.append(1 if in_position else 0)

    # *** Shift by 1 to prevent lookahead bias ***
    # position[T] = raw_signal[T-1], held over close[T-1] -> close[T].
    position = pd.Series(raw, index=close.index, name="position")
    position = position.shift(1).fillna(0).astype(int)

    return position


# ===========================================================================
# Pairs Trading / Statistical Arbitrage
# ===========================================================================

def compute_pairs_spread(close_y: pd.Series, close_x: pd.Series) -> pd.Series:
    """
    Compute the log-ratio spread for a two-asset pairs trade.

    spread[T] = log(close_y[T]) - log(close_x[T])
    """
    if not close_y.index.equals(close_x.index):
        raise ValueError("close_y and close_x must share the same index.")
    if close_y.isna().any() or close_x.isna().any():
        raise ValueError("pairs close series must not contain NaN values.")
    if (close_y <= 0).any() or (close_x <= 0).any():
        raise ValueError("pairs close prices must be positive.")

    return (np.log(close_y) - np.log(close_x)).rename("spread")


def compute_spread_zscore(spread: pd.Series, window: int) -> pd.Series:
    """
    Compute the rolling z-score of a spread series.

    z_score[T] = (spread[T] - rolling_mean[T]) / rolling_std[T]

    Parameters
    ----------
    spread : pd.Series
        Any spread series (e.g. log-price ratio of two assets).
    window : int
        Rolling look-back period (must be >= 2).

    Returns
    -------
    pd.Series named "zscore".
        NaN for the first ``window - 1`` bars (insufficient history).
        When the rolling std is zero (perfectly flat spread), z-score is 0.
    """
    if window < 2:
        raise ValueError(
            f"lookback_window must be at least 2; got {window}."
        )
    rolling = spread.rolling(window=window, min_periods=window)
    mean = rolling.mean()
    std = rolling.std(ddof=1)
    # raw_z is NaN both during warm-up (std is NaN) and when std == 0.
    # We want to preserve warm-up NaNs but replace std==0 with 0.0 (no signal).
    raw_z = (spread - mean) / std
    zscore = raw_z.where(std.isna() | (std > 0), 0.0)
    return zscore.rename("zscore")


def pairs_signals(
    close_y: pd.Series,
    close_x: pd.Series,
    lookback_window: int = 60,
    entry_z_score: float = 2.0,
    exit_z_score: float = 0.5,
) -> pd.Series:
    """
    Generate pairs-trading signals from the log-ratio spread of two assets.

    Spread definition
    -----------------
    spread[T] = log(close_y[T]) - log(close_x[T])

    This is the log-price ratio of the two assets.  A positive spread means
    *y* has become expensive relative to *x*; a negative spread means *y*
    is cheap relative to *x*.

    Signal rules
    ------------
    * z_score > +entry_z_score  -> signal = -1 (SHORT spread: short y, long x)
    * z_score < -entry_z_score  -> signal = +1 (LONG  spread: long  y, short x)
    * LONG exits when z_score > -exit_z_score.
    * SHORT exits when z_score < +exit_z_score.
    * Positions are maintained between entry and exit (hysteresis).
    * The raw signal is **shifted by one period** to prevent lookahead bias.

    Parameters
    ----------
    close_y : pd.Series
        Adjusted close prices for asset Y.
    close_x : pd.Series
        Adjusted close prices for asset X.
        Must share the same DatetimeIndex as *close_y* (already aligned).
    lookback_window : int
        Rolling window for the z-score in trading days (>= 2, default: 60).
    entry_z_score : float
        Enter a position when |z_score| exceeds this threshold (> 0).
        Must be strictly greater than ``exit_z_score``.
    exit_z_score : float
        Exit threshold around zero (>= 0).  Long-spread positions exit after
        z_score crosses above ``-exit_z_score``; short-spread positions exit
        after z_score crosses below ``+exit_z_score``.

    Returns
    -------
    pd.Series of int (-1, 0, +1) with the same index as *close_y*,
        named "signal".  No NaN values.
    """
    if entry_z_score <= exit_z_score:
        raise ValueError(
            f"entry_z_score ({entry_z_score}) must be strictly greater than "
            f"exit_z_score ({exit_z_score})."
        )
    if exit_z_score < 0.0:
        raise ValueError(
            f"exit_z_score must be >= 0; got {exit_z_score}."
        )

    spread = compute_pairs_spread(close_y, close_x)
    zscore = compute_spread_zscore(spread, lookback_window)

    in_position = 0   # 0 = flat, +1 = long spread, -1 = short spread
    raw: list[int] = []

    for z in zscore:
        if pd.isna(z):
            # Warm-up: not enough history for the z-score.
            raw.append(0)
            continue

        v = float(z)
        if in_position == 0:
            if v > entry_z_score:
                in_position = -1   # y expensive vs x -> short spread
            elif v < -entry_z_score:
                in_position = +1   # y cheap vs x -> long spread
        elif in_position == 1:
            if v > -exit_z_score:
                in_position = 0    # long spread mean-reverted -> exit
        elif in_position == -1:
            if v < exit_z_score:
                in_position = 0    # short spread mean-reverted -> exit

        raw.append(in_position)

    # *** Shift by 1 to prevent lookahead bias ***
    signal = pd.Series(raw, index=close_y.index, name="signal")
    signal = signal.shift(1).fillna(0).astype(int)

    return signal
