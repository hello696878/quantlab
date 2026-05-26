"""
Unit tests for app.strategies.sma_crossover_signals.
"""

import pandas as pd
import pytest

from app.strategies import sma_crossover_signals

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAST, SLOW = 10, 50  # small windows so tests don't need huge series


def make_close(values: list, start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name="Close", dtype=float)


def uptrend(n: int = 300, start: float = 100.0, step: float = 0.5) -> pd.Series:
    return make_close([start + i * step for i in range(n)])


def downtrend(n: int = 300, start: float = 300.0, step: float = 0.5) -> pd.Series:
    return make_close([start - i * step for i in range(n)])


# ---------------------------------------------------------------------------
# Shape and type
# ---------------------------------------------------------------------------

def test_output_length_matches_input():
    close = uptrend(300)
    pos = sma_crossover_signals(close, FAST, SLOW)
    assert len(pos) == len(close)


def test_output_has_no_nan():
    close = uptrend(300)
    pos = sma_crossover_signals(close, FAST, SLOW)
    assert not pos.isna().any()


def test_output_is_binary():
    """Position must only take values 0 or 1."""
    close = uptrend(300)
    pos = sma_crossover_signals(close, FAST, SLOW)
    assert set(pos.unique()).issubset({0, 1})


def test_index_preserved():
    """Output index must match the input index."""
    close = uptrend(300)
    pos = sma_crossover_signals(close, FAST, SLOW)
    pd.testing.assert_index_equal(pos.index, close.index)


# ---------------------------------------------------------------------------
# Lookahead-bias prevention
# ---------------------------------------------------------------------------

def test_first_position_is_always_zero():
    """
    After shift(1), position[0] is filled with 0 regardless of the trend.
    This ensures we cannot trade on day 0 using day 0's price.
    """
    close = uptrend(300)
    pos = sma_crossover_signals(close, FAST, SLOW)
    assert pos.iloc[0] == 0


def test_no_future_information_used():
    """
    Changing tomorrow's price should not affect today's position.
    Build two close series identical except for the final bar, and confirm
    that all positions except the last are identical.
    """
    base = [100.0 + i * 0.5 for i in range(200)]
    s1 = make_close(base)
    s2 = make_close(base[:-1] + [999.0])  # last price wildly different

    p1 = sma_crossover_signals(s1, FAST, SLOW)
    p2 = sma_crossover_signals(s2, FAST, SLOW)

    # All positions except the last should be identical
    assert (p1.iloc[:-1].values == p2.iloc[:-1].values).all()


# ---------------------------------------------------------------------------
# Economic behaviour
# ---------------------------------------------------------------------------

def test_uptrend_ends_long():
    """In a persistent uptrend fast SMA > slow SMA → final position = 1."""
    close = uptrend(300)
    pos = sma_crossover_signals(close, FAST, SLOW)
    assert pos.iloc[-1] == 1


def test_downtrend_ends_flat():
    """In a persistent downtrend fast SMA < slow SMA → final position = 0."""
    close = downtrend(300)
    pos = sma_crossover_signals(close, FAST, SLOW)
    assert pos.iloc[-1] == 0


def test_flat_price_yields_zero_crossover():
    """Constant prices → both SMAs identical → no crossover → all flat."""
    close = make_close([100.0] * 300)
    pos = sma_crossover_signals(close, FAST, SLOW)
    # fast == slow (not strictly greater), so all positions should be 0
    assert (pos == 0).all()


def test_crossover_detected():
    """
    Price rises sharply after SLOW bars → fast SMA eventually crosses slow SMA
    and we see at least one entry.
    """
    # First 200 bars flat, then a strong rally for 200 bars
    flat_part = [100.0] * 200
    rally_part = [100.0 + i * 2.0 for i in range(200)]
    close = make_close(flat_part + rally_part)
    pos = sma_crossover_signals(close, FAST, SLOW)
    assert pos.sum() > 0  # at least one long day
