"""
Unit tests for volatility-based signal computation and breakout signal generation.

All tests use synthetic price series — no network calls.

Design of synthetic price series
---------------------------------
* ``steady_close``   — small constant daily step; post-warmup daily return is
                       constant and equal to the rolling std (because all returns
                       are the same → std = 0 after 2+ identical returns, but
                       we choose a size that triggers breakout when multiplier<1).
* ``spike_close``    — stable baseline with a single large daily jump, ensuring
                       exactly one breakout entry.
* ``flat_close``     — constant prices; returns = 0 and std = 0 → no breakout.
* ``uptrend_close``  — linearly rising; small constant returns → controllable
                       volatility and return level.
"""

import pandas as pd
import pytest

from app.strategies import compute_volatility, volatility_breakout_signals

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

LB_WIN = 10   # short lookback for fast tests
EXIT_WIN = 5  # short exit window for fast tests


def make_close(values: list, start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name="Close", dtype=float)


def flat_close(n: int = 60, price: float = 100.0) -> pd.Series:
    """Constant price — daily return = 0, std = 0."""
    return make_close([price] * n)


def steady_rise_close(n: int = 100, step: float = 0.5) -> pd.Series:
    """Small constant daily step — all post-warmup returns are identical."""
    return make_close([100.0 + i * step for i in range(n)])


def spike_close(
    n_stable: int = 30,
    stable_price: float = 100.0,
    spike_return: float = 0.10,
    n_after: int = 30,
) -> pd.Series:
    """
    Stable run followed by one large positive return, then stable again.
    spike_return (e.g. 0.10 = 10 %) is designed to be many σ above the
    near-zero volatility of the flat stable period.
    """
    spike_price = stable_price * (1 + spike_return)
    values = (
        [stable_price] * n_stable
        + [spike_price]
        + [spike_price] * n_after
    )
    return make_close(values)


# ===========================================================================
# compute_volatility tests
# ===========================================================================

class TestComputeVolatility:

    def test_output_length_matches_input(self):
        close = steady_rise_close()
        vol = compute_volatility(close, LB_WIN)
        assert len(vol) == len(close)

    def test_index_preserved(self):
        close = steady_rise_close()
        vol = compute_volatility(close, LB_WIN)
        pd.testing.assert_index_equal(vol.index, close.index)

    def test_series_name(self):
        close = steady_rise_close()
        vol = compute_volatility(close, LB_WIN)
        assert vol.name == "volatility"

    def test_warmup_nans_at_start(self):
        """
        pct_change() produces NaN at index 0.
        rolling(window=W).std() needs W values → NaN through index W.
        First valid reading is at index W (0-based), i.e. positions 0..W-1 are NaN.
        """
        close = steady_rise_close(100)
        vol = compute_volatility(close, LB_WIN)
        assert vol.iloc[:LB_WIN].isna().all()
        assert pd.notna(vol.iloc[LB_WIN])

    def test_flat_price_zero_volatility(self):
        """Constant price → all daily returns = 0 → std = 0."""
        close = flat_close(60)
        vol = compute_volatility(close, LB_WIN)
        valid = vol.dropna()
        assert (valid == 0.0).all()

    def test_output_non_negative(self):
        """Volatility (std) is always ≥ 0."""
        close = steady_rise_close(100)
        vol = compute_volatility(close, LB_WIN)
        assert (vol.dropna() >= 0.0).all()

    def test_known_value(self):
        """
        For a series whose daily returns are all 0.01 (1 %), the rolling
        std is 0 because every observation in the window is identical.
        """
        prices = [100.0 * (1.01 ** i) for i in range(50)]
        close = make_close(prices)
        vol = compute_volatility(close, LB_WIN)
        valid = vol.dropna()
        # All returns equal → std = 0.
        assert (valid.abs() < 1e-12).all()

    def test_invalid_window_one_raises(self):
        close = steady_rise_close(50)
        with pytest.raises(ValueError, match="lookback_window"):
            compute_volatility(close, window=1)

    def test_invalid_window_zero_raises(self):
        close = steady_rise_close(50)
        with pytest.raises(ValueError, match="lookback_window"):
            compute_volatility(close, window=0)


# ===========================================================================
# volatility_breakout_signals tests
# ===========================================================================

class TestVolatilityBreakoutSignals:

    # ── Shape and type ───────────────────────────────────────────────────────

    def test_output_length_matches_input(self):
        close = steady_rise_close()
        pos = volatility_breakout_signals(close, lookback_window=LB_WIN, exit_window=EXIT_WIN)
        assert len(pos) == len(close)

    def test_output_has_no_nan(self):
        close = steady_rise_close()
        pos = volatility_breakout_signals(close, lookback_window=LB_WIN, exit_window=EXIT_WIN)
        assert not pos.isna().any()

    def test_output_is_binary(self):
        close = steady_rise_close()
        pos = volatility_breakout_signals(close, lookback_window=LB_WIN, exit_window=EXIT_WIN)
        assert set(pos.unique()).issubset({0, 1})

    def test_index_preserved(self):
        close = steady_rise_close()
        pos = volatility_breakout_signals(close, lookback_window=LB_WIN, exit_window=EXIT_WIN)
        pd.testing.assert_index_equal(pos.index, close.index)

    # ── Lookahead-bias prevention ─────────────────────────────────────────────

    def test_first_position_always_zero(self):
        """After shift(1), position[0] is always 0."""
        close = steady_rise_close()
        pos = volatility_breakout_signals(close, lookback_window=LB_WIN, exit_window=EXIT_WIN)
        assert pos.iloc[0] == 0

    def test_no_future_information(self):
        """
        Changing only the last bar's price must not affect any earlier position.
        """
        base = [100.0 + i * 0.5 for i in range(80)]
        modified = base[:-1] + [9999.0]

        pos1 = volatility_breakout_signals(
            make_close(base), lookback_window=LB_WIN, exit_window=EXIT_WIN
        )
        pos2 = volatility_breakout_signals(
            make_close(modified), lookback_window=LB_WIN, exit_window=EXIT_WIN
        )
        assert (pos1.iloc[:-1].values == pos2.iloc[:-1].values).all()

    # ── Warm-up ───────────────────────────────────────────────────────────────

    def test_warmup_period_always_flat(self):
        """
        Before the rolling volatility is computable (first LB_WIN bars) the
        strategy must be flat.  After the shift that means positions 0..LB_WIN
        are all 0.
        """
        close = steady_rise_close(200)
        pos = volatility_breakout_signals(close, lookback_window=LB_WIN, exit_window=EXIT_WIN)
        assert (pos.iloc[:LB_WIN] == 0).all()

    # ── Economic behaviour ────────────────────────────────────────────────────

    def test_flat_price_never_enters(self):
        """
        Constant price → daily return = 0, volatility = 0.
        Condition: 0 > multiplier * 0 = 0 is False → never enters.
        """
        close = flat_close(80)
        pos = volatility_breakout_signals(
            close, lookback_window=LB_WIN, exit_window=EXIT_WIN,
            breakout_multiplier=1.0,
        )
        assert (pos == 0).all(), "Should never enter on perfectly flat prices"

    def test_spike_generates_entry(self):
        """
        A single large positive return (10 %) on a near-flat baseline must
        trigger an entry (raw = 1), which appears shifted by one bar.
        """
        close = spike_close(n_stable=30, spike_return=0.10, n_after=30)
        pos = volatility_breakout_signals(
            close, lookback_window=LB_WIN, exit_window=EXIT_WIN,
            breakout_multiplier=1.0,
        )
        assert pos.sum() > 0, "Expected at least one long bar after a large spike"

    def test_time_based_exit_respected(self):
        """
        After a single entry the strategy must return to flat within
        exit_window + 1 bars (the +1 is for the shift).
        Once flat it should stay flat (no new breakout on stable prices).
        """
        close = spike_close(n_stable=30, spike_return=0.10, n_after=60)
        exit_w = 5
        pos = volatility_breakout_signals(
            close, lookback_window=LB_WIN, exit_window=exit_w,
            breakout_multiplier=1.0,
        )
        # Find where the position turns 1 for the first time.
        entry_idx = pos[pos == 1].index[0]
        entry_loc = pos.index.get_loc(entry_idx)
        # Positions after entry_loc + exit_w should be 0 (assuming no new breakout).
        check_start = entry_loc + exit_w + 2  # +2 for safety margin around shift
        if check_start < len(pos):
            assert (pos.iloc[check_start:] == 0).all(), (
                "Expected flat position after time-based exit"
            )

    def test_high_multiplier_no_entry(self):
        """
        breakout_multiplier=100 means the daily return must exceed 100 × vol —
        unreachable with normal prices → strategy never enters.
        """
        close = spike_close(n_stable=30, spike_return=0.10, n_after=30)
        pos = volatility_breakout_signals(
            close, lookback_window=LB_WIN, exit_window=EXIT_WIN,
            breakout_multiplier=100.0,
        )
        assert (pos == 0).all(), "Expected no entry with unreachably high multiplier"

    def test_lower_multiplier_more_trades(self):
        """
        A lower breakout_multiplier triggers more entries than a higher one
        on the same price series.
        """
        close = steady_rise_close(200, step=0.5)
        pos_low = volatility_breakout_signals(
            close, lookback_window=LB_WIN, exit_window=EXIT_WIN,
            breakout_multiplier=0.1,
        )
        pos_high = volatility_breakout_signals(
            close, lookback_window=LB_WIN, exit_window=EXIT_WIN,
            breakout_multiplier=10.0,
        )
        trades_low = int(pos_low.diff().abs().sum())
        trades_high = int(pos_high.diff().abs().sum())
        assert trades_low >= trades_high, (
            f"Lower multiplier ({trades_low} transitions) should have "
            f">= trades vs higher multiplier ({trades_high} transitions)"
        )

    # ── Validation ───────────────────────────────────────────────────────────

    def test_zero_breakout_multiplier_raises(self):
        close = steady_rise_close(50)
        with pytest.raises(ValueError, match="breakout_multiplier"):
            volatility_breakout_signals(close, breakout_multiplier=0.0)

    def test_negative_breakout_multiplier_raises(self):
        close = steady_rise_close(50)
        with pytest.raises(ValueError, match="breakout_multiplier"):
            volatility_breakout_signals(close, breakout_multiplier=-1.0)

    def test_zero_exit_window_raises(self):
        close = steady_rise_close(50)
        with pytest.raises(ValueError, match="exit_window"):
            volatility_breakout_signals(close, exit_window=0)

    def test_invalid_lookback_window_raises(self):
        """lookback_window < 2 is delegated to compute_volatility."""
        close = steady_rise_close(50)
        with pytest.raises(ValueError, match="lookback_window"):
            volatility_breakout_signals(close, lookback_window=1)
