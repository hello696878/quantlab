"""
Unit tests for Bollinger Band computation and BB mean-reversion signal generation.

All tests use synthetic price series — no network calls.

Design of synthetic price series
---------------------------------
* ``make_close``         — arbitrary values with a business-day DatetimeIndex.
* ``spike_v_close``      — long stable period then a sudden large drop, then a
                           slow linear recovery.  Reliably triggers an entry
                           (price breaks below narrow bands during the stable
                           period → lower band ≈ SMA ≈ stable_price) and an
                           exit (price climbs back above the lagging SMA).
* ``uptrend_close``      — monotonically rising; price always above SMA and
                           lower band → no entry ever.
"""

import pandas as pd
import pytest

import app.strategies as strategies
from app.strategies import bollinger_band_signals, compute_bollinger_bands

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BB_WIN = 20
NUM_STD = 2.0


def make_close(values: list, start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name="Close", dtype=float)


def spike_v_close(
    n_stable: int = 30,
    stable_price: float = 100.0,
    spike_low: float = 75.0,
    n_recover: int = 60,
    recover_target: float = 110.0,
) -> pd.Series:
    """
    Flat stable price for ``n_stable`` bars, a one-day spike down to
    ``spike_low``, then a linear recovery to ``recover_target``.

    Why this reliably triggers entry and exit
    ------------------------------------------
    * During the stable period the rolling std → 0, so the bands collapse to
      the SMA ≈ stable_price.  The spike price is far below stable_price, so
      ``price < lower_band`` is always satisfied immediately.
    * As the recovery proceeds, the SMA is dragged down by the low prices in
      the window.  Once the rising recovery price overtakes the SMA (middle
      band) the exit condition ``price >= middle_band`` is met.
    """
    stable = [stable_price] * n_stable
    recovery = [
        spike_low + (recover_target - spike_low) * i / n_recover
        for i in range(n_recover)
    ]
    return make_close(stable + [spike_low] + recovery)


def uptrend_close(n: int = 100) -> pd.Series:
    return make_close([100.0 + i * 0.5 for i in range(n)])


# ===========================================================================
# compute_bollinger_bands tests
# ===========================================================================

class TestComputeBollingerBands:

    # ── Shape ────────────────────────────────────────────────────────────────

    def test_output_length_matches_input(self):
        close = spike_v_close()
        middle, upper, lower = compute_bollinger_bands(close)
        for band in (middle, upper, lower):
            assert len(band) == len(close)

    def test_index_preserved(self):
        close = spike_v_close()
        middle, upper, lower = compute_bollinger_bands(close)
        for band in (middle, upper, lower):
            pd.testing.assert_index_equal(band.index, close.index)

    def test_series_names(self):
        close = spike_v_close()
        middle, upper, lower = compute_bollinger_bands(close)
        assert middle.name == "bb_middle"
        assert upper.name == "bb_upper"
        assert lower.name == "bb_lower"

    # ── Band ordering ────────────────────────────────────────────────────────

    def test_upper_gt_middle_gt_lower_after_warmup(self):
        """After the warm-up all three bands must satisfy upper > middle > lower."""
        close = spike_v_close()
        middle, upper, lower = compute_bollinger_bands(close, window=BB_WIN)
        # Drop rows where std == 0 (flat section): upper == lower == middle there.
        # Use rows where std > 0 (spike + recovery section).
        valid = middle.dropna().index
        rolling_std = close.rolling(window=BB_WIN, min_periods=BB_WIN).std(ddof=1)
        nonzero_std_idx = rolling_std[rolling_std > 1e-9].index
        check_idx = valid.intersection(nonzero_std_idx)
        assert (upper.loc[check_idx] > middle.loc[check_idx]).all()
        assert (middle.loc[check_idx] > lower.loc[check_idx]).all()

    def test_bands_symmetric_around_middle(self):
        """upper − middle == middle − lower for all non-NaN rows."""
        close = spike_v_close()
        middle, upper, lower = compute_bollinger_bands(close)
        valid = middle.dropna().index
        spread_up = upper.loc[valid] - middle.loc[valid]
        spread_dn = middle.loc[valid] - lower.loc[valid]
        pd.testing.assert_series_equal(spread_up, spread_dn, check_names=False)

    def test_flat_price_zero_bandwidth(self):
        """Constant price → rolling std = 0 → bands collapse to the middle."""
        close = make_close([100.0] * 50)
        middle, upper, lower = compute_bollinger_bands(close, window=BB_WIN)
        valid = middle.dropna().index
        assert (upper.loc[valid] == middle.loc[valid]).all()
        assert (lower.loc[valid] == middle.loc[valid]).all()

    def test_known_rolling_band_values(self):
        """Pin bands to rolling mean ± num_std × rolling std."""
        close = make_close([1.0, 2.0, 3.0, 4.0, 5.0])
        middle, upper, lower = compute_bollinger_bands(close, window=3, num_std=2.0)

        expected_middle = close.rolling(3).mean()
        expected_std = close.rolling(3).std()
        expected_upper = expected_middle + 2.0 * expected_std
        expected_lower = expected_middle - 2.0 * expected_std

        pd.testing.assert_series_equal(middle, expected_middle.rename("bb_middle"))
        pd.testing.assert_series_equal(upper, expected_upper.rename("bb_upper"))
        pd.testing.assert_series_equal(lower, expected_lower.rename("bb_lower"))

    # ── Warm-up NaNs ─────────────────────────────────────────────────────────

    def test_warmup_nans_at_start(self):
        """
        rolling(window=W, min_periods=W) requires exactly W values.
        Positions 0 … W-2 are NaN; position W-1 is the first valid value.
        """
        close = make_close([100.0 + i for i in range(60)])
        middle, upper, lower = compute_bollinger_bands(close, window=BB_WIN)
        for band in (middle, upper, lower):
            assert band.iloc[: BB_WIN - 1].isna().all()
            assert pd.notna(band.iloc[BB_WIN - 1])

    # ── Validation ───────────────────────────────────────────────────────────

    def test_invalid_window_raises(self):
        close = make_close([100.0] * 30)
        with pytest.raises(ValueError, match="bb_window"):
            compute_bollinger_bands(close, window=1)

    def test_zero_num_std_raises(self):
        close = make_close([100.0] * 30)
        with pytest.raises(ValueError, match="num_std"):
            compute_bollinger_bands(close, num_std=0.0)

    def test_negative_num_std_raises(self):
        close = make_close([100.0] * 30)
        with pytest.raises(ValueError, match="num_std"):
            compute_bollinger_bands(close, num_std=-2.0)


# ===========================================================================
# bollinger_band_signals tests
# ===========================================================================

class TestBollingerBandSignals:

    # ── Shape and type ───────────────────────────────────────────────────────

    def test_output_length_matches_input(self):
        close = spike_v_close()
        pos = bollinger_band_signals(close)
        assert len(pos) == len(close)

    def test_output_has_no_nan(self):
        close = spike_v_close()
        pos = bollinger_band_signals(close)
        assert not pos.isna().any()

    def test_output_is_binary(self):
        close = spike_v_close()
        pos = bollinger_band_signals(close)
        assert set(pos.unique()).issubset({0, 1})

    def test_index_preserved(self):
        close = spike_v_close()
        pos = bollinger_band_signals(close)
        pd.testing.assert_index_equal(pos.index, close.index)

    # ── Lookahead-bias prevention ─────────────────────────────────────────────

    def test_first_position_always_zero(self):
        """
        After shift(1), position[0] is always 0 regardless of conditions:
        we cannot trade on day 0 using day 0's closing price.
        """
        close = spike_v_close()
        pos = bollinger_band_signals(close)
        assert pos.iloc[0] == 0

    def test_no_future_information(self):
        """
        Changing only the last bar's price must not affect any earlier position.
        """
        stable = [100.0] * 30
        drop = [75.0]
        recovery = [75.0 + 35.0 * i / 60 for i in range(60)]
        base_prices = stable + drop + recovery
        modified = base_prices[:-1] + [9999.0]

        pos1 = bollinger_band_signals(make_close(base_prices))
        pos2 = bollinger_band_signals(make_close(modified))
        assert (pos1.iloc[:-1].values == pos2.iloc[:-1].values).all()

    # ── Economic behaviour ────────────────────────────────────────────────────

    def test_spike_v_generates_entry_and_exit(self):
        """
        A spike-V price series must produce at least one entry (0→1) and at
        least one exit (1→0).
        """
        close = spike_v_close(
            n_stable=30,
            stable_price=100.0,
            spike_low=75.0,
            n_recover=60,
            recover_target=110.0,
        )
        pos = bollinger_band_signals(
            close, bb_window=BB_WIN, num_std=NUM_STD, exit_band="middle"
        )
        changes = pos.diff().dropna()
        assert (changes == 1).any(), "Expected at least one long entry (0→1)"
        assert (changes == -1).any(), "Expected at least one long exit (1→0)"

    def test_upper_exit_holds_at_least_as_long_as_middle_exit(self):
        """
        Exiting at the upper band requires price to recover further, so the
        position must be held for at least as many days as middle-band exit.
        """
        close = spike_v_close(
            n_stable=30, spike_low=75.0, n_recover=80, recover_target=120.0
        )
        pos_mid = bollinger_band_signals(close, exit_band="middle")
        pos_up = bollinger_band_signals(close, exit_band="upper")
        assert pos_up.sum() >= pos_mid.sum(), (
            f"Upper exit ({pos_up.sum()} long days) should be >= "
            f"middle exit ({pos_mid.sum()} long days)"
        )

    def test_uptrend_no_entry(self):
        """
        In a monotonic uptrend the price is always above the rolling SMA,
        so it can never fall below the lower band — no entry expected.
        """
        close = uptrend_close(200)
        pos = bollinger_band_signals(close)
        warmup = BB_WIN + 5
        assert (pos.iloc[warmup:] == 0).all(), (
            "No entries expected in a persistent uptrend"
        )

    def test_wide_bands_no_entry(self):
        """
        num_std=100 makes the lower band unreachably far below the price.
        The strategy should never enter.
        """
        close = spike_v_close()
        pos = bollinger_band_signals(close, num_std=100.0)
        assert (pos == 0).all(), (
            "Expected all-flat when bands are impossibly wide (num_std=100)"
        )

    def test_warmup_period_always_flat(self):
        """
        The first bb_window bars are NaN for the bands, so the strategy must
        remain flat during that period.
        """
        close = spike_v_close(n_stable=5, n_recover=80)
        pos = bollinger_band_signals(close, bb_window=BB_WIN)
        # After shift(1), warmup positions cover indices 0..BB_WIN-1.
        assert (pos.iloc[: BB_WIN] == 0).all()

    def test_state_machine_holds_until_selected_exit_band(self, monkeypatch):
        """
        Once entered, raw signal stays long until price reaches the selected
        exit band. Returned position is shifted by one bar.
        """
        close = make_close([100.0, 99.0, 98.0, 96.0, 95.0, 97.0, 98.0, 99.0])
        index = close.index
        middle = pd.Series(
            [None, None, 100.0, 100.0, 100.0, 97.0, 97.0, 97.0],
            index=index,
            name="bb_middle",
            dtype=float,
        )
        upper = pd.Series(
            [None, None, 105.0, 105.0, 105.0, 102.0, 102.0, 102.0],
            index=index,
            name="bb_upper",
            dtype=float,
        )
        lower = pd.Series(
            [None, None, 99.0, 94.0, 94.0, 94.0, 94.0, 94.0],
            index=index,
            name="bb_lower",
            dtype=float,
        )

        monkeypatch.setattr(
            strategies,
            "compute_bollinger_bands",
            lambda close, window, num_std: (middle, upper, lower),
        )

        pos = strategies.bollinger_band_signals(close, exit_band="middle")

        expected = pd.Series([0, 0, 0, 1, 1, 1, 0, 0], index=index, name="position")
        pd.testing.assert_series_equal(pos, expected)

    # ── Validation ───────────────────────────────────────────────────────────

    def test_invalid_exit_band_raises(self):
        """exit_band must be 'middle' or 'upper'."""
        close = spike_v_close()
        with pytest.raises(ValueError, match="exit_band"):
            bollinger_band_signals(close, exit_band="sma")

    def test_invalid_exit_band_empty_string_raises(self):
        close = spike_v_close()
        with pytest.raises(ValueError, match="exit_band"):
            bollinger_band_signals(close, exit_band="")

    def test_invalid_bb_window_raises(self):
        """window < 2 is delegated to compute_bollinger_bands."""
        close = spike_v_close()
        with pytest.raises(ValueError, match="bb_window"):
            bollinger_band_signals(close, bb_window=1)

    def test_invalid_num_std_raises(self):
        """num_std <= 0 is delegated to compute_bollinger_bands."""
        close = spike_v_close()
        with pytest.raises(ValueError, match="num_std"):
            bollinger_band_signals(close, num_std=0.0)
