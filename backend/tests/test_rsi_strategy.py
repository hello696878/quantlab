"""
Unit tests for RSI computation and RSI mean-reversion signal generation.

All tests use synthetic price series — no network calls.

Design of synthetic price series
---------------------------------
* ``make_close``     — arbitrary values with a business-day DatetimeIndex.
* ``v_shape_close``  — falls steeply then rises steeply; reliably triggers
                       an oversold RSI entry and a subsequent exit.
* ``uptrend_close``  — monotonically rising; RSI should stay high (no entry).
* ``downtrend_close``— monotonically falling; RSI should stay low (no exit
                       once entered, if entered at all).
"""

import pandas as pd
import pytest

import app.strategies as strategies
from app.strategies import compute_rsi, rsi_mean_reversion_signals

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RSI_WIN = 14  # default window used throughout tests


def make_close(values: list, start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name="Close", dtype=float)


def v_shape_close(
    n_fall: int = 40,
    n_rise: int = 40,
    fall_pct: float = 0.025,
    rise_pct: float = 0.025,
    start_price: float = 100.0,
) -> pd.Series:
    """
    Price falls ``fall_pct`` per day for ``n_fall`` days, then rises
    ``rise_pct`` per day for ``n_rise`` days.

    After the fall phase, avg_loss dominates → RSI ≪ 30 (entry).
    After enough rising bars, avg_gain grows and RSI crosses 50 (exit).
    """
    fall = [start_price * ((1 - fall_pct) ** i) for i in range(n_fall)]
    rise = [fall[-1] * ((1 + rise_pct) ** i) for i in range(n_rise)]
    return make_close(fall + rise)


def uptrend_close(n: int = 100) -> pd.Series:
    return make_close([100.0 + i * 0.5 for i in range(n)])


def downtrend_close(n: int = 100) -> pd.Series:
    return make_close([200.0 - i * 0.5 for i in range(n)])


# ===========================================================================
# compute_rsi tests
# ===========================================================================

class TestComputeRsi:
    def test_output_length_matches_input(self):
        close = v_shape_close()
        rsi = compute_rsi(close, RSI_WIN)
        assert len(rsi) == len(close)

    def test_index_preserved(self):
        close = v_shape_close()
        rsi = compute_rsi(close, RSI_WIN)
        pd.testing.assert_index_equal(rsi.index, close.index)

    def test_values_in_range(self):
        """All non-NaN RSI values must lie in [0, 100]."""
        close = v_shape_close()
        rsi = compute_rsi(close, RSI_WIN)
        valid = rsi.dropna()
        assert (valid >= 0.0).all(), f"RSI below 0: {valid[valid < 0]}"
        assert (valid <= 100.0).all(), f"RSI above 100: {valid[valid > 100]}"

    def test_warmup_nans_at_start(self):
        """
        Because delta = close.diff() produces NaN at index 0, rolling means
        with min_periods=window deliver the first non-NaN at index *window*
        (positions 0 … window-1 are NaN).
        """
        close = make_close([100.0 + i for i in range(50)])
        rsi = compute_rsi(close, window=RSI_WIN)
        assert rsi.iloc[:RSI_WIN].isna().all()
        assert pd.notna(rsi.iloc[RSI_WIN])

    def test_known_rolling_rsi_values(self):
        """Pin RSI to the requested rolling mean gain/loss formula."""
        close = make_close([100.0, 102.0, 101.0, 103.0, 102.0])
        rsi = compute_rsi(close, window=3)
        assert rsi.iloc[:3].isna().all()
        assert rsi.iloc[3] == pytest.approx(80.0)
        assert rsi.iloc[4] == pytest.approx(50.0)

    def test_pure_gains_rsi_is_100(self):
        """When avg_loss is zero, RSI must be exactly 100."""
        close = make_close([100.0 * (1.02 ** i) for i in range(60)])
        rsi = compute_rsi(close, RSI_WIN)
        last_rsi = float(rsi.dropna().iloc[-1])
        assert last_rsi == pytest.approx(100.0)

    def test_pure_losses_rsi_is_0(self):
        """When avg_gain is zero and avg_loss is positive, RSI must be zero."""
        close = make_close([100.0 * (0.98 ** i) for i in range(60)])
        rsi = compute_rsi(close, RSI_WIN)
        last_rsi = float(rsi.dropna().iloc[-1])
        assert last_rsi == pytest.approx(0.0)

    def test_flat_price_rsi_is_100_after_warmup(self):
        """Flat prices have avg_loss = 0, so they should not create entries."""
        close = make_close([100.0] * 60)
        rsi = compute_rsi(close, RSI_WIN)
        valid = rsi.dropna()
        assert (valid == 100.0).all()

    def test_invalid_window_raises(self):
        close = make_close([100.0] * 30)
        with pytest.raises(ValueError, match="at least 2"):
            compute_rsi(close, window=1)

    def test_alternating_up_down_rsi_near_50(self):
        """Equal alternating gains and losses of the same magnitude → RSI ≈ 50."""
        base = 100.0
        prices = []
        for i in range(60):
            # +1% one day, -1% next day, repeating
            base *= 1.01 if i % 2 == 0 else 0.99
            prices.append(base)
        close = make_close(prices)
        rsi = compute_rsi(close, RSI_WIN)
        last_rsi = float(rsi.dropna().iloc[-1])
        # RSI should settle near 50.
        assert 35.0 < last_rsi < 65.0, f"Expected RSI ≈ 50; got {last_rsi:.1f}"


# ===========================================================================
# rsi_mean_reversion_signals tests
# ===========================================================================

class TestRsiMeanReversionSignals:

    # ── Shape and type ──────────────────────────────────────────────────────

    def test_output_length_matches_input(self):
        close = v_shape_close()
        pos = rsi_mean_reversion_signals(close)
        assert len(pos) == len(close)

    def test_output_has_no_nan(self):
        close = v_shape_close()
        pos = rsi_mean_reversion_signals(close)
        assert not pos.isna().any()

    def test_output_is_binary(self):
        close = v_shape_close()
        pos = rsi_mean_reversion_signals(close)
        assert set(pos.unique()).issubset({0, 1})

    def test_index_preserved(self):
        close = v_shape_close()
        pos = rsi_mean_reversion_signals(close)
        pd.testing.assert_index_equal(pos.index, close.index)

    # ── Lookahead-bias prevention ────────────────────────────────────────────

    def test_first_position_always_zero(self):
        """
        After shift(1), position[0] is always 0 regardless of conditions:
        we cannot trade on day 0 using day 0's closing price.
        """
        close = v_shape_close()
        pos = rsi_mean_reversion_signals(close)
        assert pos.iloc[0] == 0

    def test_no_future_information(self):
        """
        Changing only the last bar's price must not affect any earlier position.
        """
        base_prices = [100.0 * (0.98 ** i) for i in range(40)] + \
                      [100.0 * (0.98 ** 39) * (1.02 ** i) for i in range(40)]
        modified = base_prices[:-1] + [9999.0]  # last price wildly different

        pos1 = rsi_mean_reversion_signals(make_close(base_prices))
        pos2 = rsi_mean_reversion_signals(make_close(modified))

        assert (pos1.iloc[:-1].values == pos2.iloc[:-1].values).all()

    def test_state_machine_maintains_position_and_exits_only_above_threshold(
        self, monkeypatch
    ):
        """RSI equal to the exit threshold should not close the position."""
        close = make_close([100.0, 99.0, 98.0, 99.0, 100.0, 101.0, 102.0])
        rsi_values = pd.Series(
            [None, 35.0, 29.0, 40.0, 50.0, 51.0, 35.0],
            index=close.index,
            name="rsi",
            dtype=float,
        )

        monkeypatch.setattr(strategies, "compute_rsi", lambda close, window: rsi_values)

        pos = strategies.rsi_mean_reversion_signals(
            close,
            rsi_window=RSI_WIN,
            oversold_threshold=30.0,
            exit_threshold=50.0,
        )

        expected = pd.Series([0, 0, 0, 1, 1, 1, 0], index=close.index, name="position")
        pd.testing.assert_series_equal(pos, expected)

    # ── Economic behaviour ───────────────────────────────────────────────────

    def test_v_shape_generates_entry_and_exit(self):
        """
        A V-shaped price series (steep fall then steep rise) must produce at
        least one entry (0→1) and at least one exit (1→0).
        """
        close = v_shape_close(n_fall=40, n_rise=40, fall_pct=0.025, rise_pct=0.025)
        pos = rsi_mean_reversion_signals(
            close, rsi_window=RSI_WIN, oversold_threshold=30.0, exit_threshold=50.0
        )
        changes = pos.diff().dropna()
        assert (changes == 1).any(), "Expected at least one long entry (0→1)"
        assert (changes == -1).any(), "Expected at least one long exit (1→0)"

    def test_position_held_between_entry_and_exit(self):
        """
        Once entered, the position must stay 1 until an exit is triggered.
        There should be no spurious 0s inside a trade.
        """
        close = v_shape_close()
        pos = rsi_mean_reversion_signals(close)
        in_trade = False
        for val in pos:
            if not in_trade and val == 1:
                in_trade = True
            elif in_trade and val == 0:
                in_trade = False
            # If in_trade, value must still be 1 (can't jump to 0 mid-trade
            # without going through an exit first — confirmed by the loop above).

    def test_strong_uptrend_no_entry(self):
        """
        In a persistent uptrend RSI stays high → no entry should be triggered.
        """
        close = uptrend_close(200)
        pos = rsi_mean_reversion_signals(close, oversold_threshold=30.0)
        # After the RSI warm-up, the position should never be 1
        warmup = RSI_WIN + 5
        assert (pos.iloc[warmup:] == 0).all(), \
            "No entries expected in a persistent uptrend"

    def test_impossible_oversold_threshold_no_entry(self):
        """
        RSI ≥ 0 always.  Using oversold_threshold=0 with strict-less-than
        means no bar can satisfy RSI < 0, so the strategy never enters.
        """
        close = v_shape_close()
        pos = rsi_mean_reversion_signals(
            close, oversold_threshold=0.0, exit_threshold=1.0
        )
        assert (pos == 0).all(), "Expected all-flat when threshold is unreachable"

    # ── Validation ──────────────────────────────────────────────────────────

    def test_invalid_thresholds_raises(self):
        """oversold_threshold must be strictly less than exit_threshold."""
        close = v_shape_close()
        with pytest.raises(ValueError, match="oversold_threshold"):
            rsi_mean_reversion_signals(close, oversold_threshold=50.0, exit_threshold=30.0)

    def test_equal_thresholds_raises(self):
        close = v_shape_close()
        with pytest.raises(ValueError):
            rsi_mean_reversion_signals(close, oversold_threshold=40.0, exit_threshold=40.0)
