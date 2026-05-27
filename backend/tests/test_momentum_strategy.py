"""
Unit tests for time-series momentum computation and signal generation.

All tests use synthetic price series — no network calls.

Design of synthetic price series
---------------------------------
* ``make_close``        — arbitrary values with a business-day DatetimeIndex.
* ``uptrend_close``     — monotonically rising; trailing return always positive
                          → strategy should be long after warm-up.
* ``downtrend_close``   — monotonically falling; trailing return always negative
                          → strategy should stay flat (never enters).
* ``zigzag_close``      — alternates between rising and falling runs; useful for
                          testing hysteresis and trade-count comparisons.
"""

import pandas as pd
import pytest

from app.strategies import compute_momentum, momentum_signals

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

MOM_WIN = 20  # short window for fast tests


def make_close(values: list, start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name="Close", dtype=float)


def uptrend_close(n: int = 200, step: float = 0.5) -> pd.Series:
    """Strict monotone uptrend: each bar is ``step`` higher than the previous."""
    return make_close([100.0 + i * step for i in range(n)])


def downtrend_close(n: int = 200, step: float = 0.5) -> pd.Series:
    """Strict monotone downtrend: each bar is ``step`` lower than the previous."""
    return make_close([200.0 - i * step for i in range(n)])


def zigzag_close(
    n_cycles: int = 5,
    run_len: int = 30,
    up_step: float = 1.0,
    dn_step: float = 1.0,
    start_price: float = 100.0,
) -> pd.Series:
    """
    Alternates between rising runs (up_step per bar) and falling runs
    (dn_step per bar).  Good for hysteresis / trade-count tests.
    """
    prices = []
    price = start_price
    for _ in range(n_cycles):
        for _ in range(run_len):
            price += up_step
            prices.append(price)
        for _ in range(run_len):
            price -= dn_step
            prices.append(price)
    return make_close(prices)


# ===========================================================================
# compute_momentum tests
# ===========================================================================

class TestComputeMomentum:

    # ── Shape ────────────────────────────────────────────────────────────────

    def test_output_length_matches_input(self):
        close = uptrend_close()
        mom = compute_momentum(close)
        assert len(mom) == len(close)

    def test_index_preserved(self):
        close = uptrend_close()
        mom = compute_momentum(close)
        pd.testing.assert_index_equal(mom.index, close.index)

    def test_series_name(self):
        close = uptrend_close()
        mom = compute_momentum(close, window=MOM_WIN)
        assert mom.name == "momentum"

    # ── Warm-up NaNs ─────────────────────────────────────────────────────────

    def test_warmup_nans_at_start(self):
        """
        pct_change(periods=W) requires W prior bars.
        Positions 0 … W-1 are NaN; position W is the first valid value.
        """
        close = uptrend_close(100)
        mom = compute_momentum(close, window=MOM_WIN)
        assert mom.iloc[:MOM_WIN].isna().all()
        assert pd.notna(mom.iloc[MOM_WIN])

    # ── Known values ─────────────────────────────────────────────────────────

    def test_known_value_exact(self):
        """
        momentum[W] = close[W] / close[0] - 1.
        With close = [100, 110, 121] and window=2:
          momentum[2] = 121/100 - 1 = 0.21
        """
        close = make_close([100.0, 110.0, 121.0])
        mom = compute_momentum(close, window=2)
        assert pd.isna(mom.iloc[0])
        assert pd.isna(mom.iloc[1])
        assert abs(float(mom.iloc[2]) - 0.21) < 1e-9

    def test_flat_price_zero_momentum(self):
        """Constant price → pct_change = 0 after warm-up."""
        close = make_close([100.0] * 50)
        mom = compute_momentum(close, window=MOM_WIN)
        valid = mom.dropna()
        assert (valid == 0.0).all()

    # ── Economic direction ────────────────────────────────────────────────────

    def test_uptrend_positive_momentum(self):
        """Monotonically rising prices → all post-warmup momentum values > 0."""
        close = uptrend_close(100)
        mom = compute_momentum(close, window=MOM_WIN)
        valid = mom.dropna()
        assert (valid > 0.0).all(), "Expected all positive momentum in an uptrend"

    def test_downtrend_negative_momentum(self):
        """Monotonically falling prices → all post-warmup momentum values < 0."""
        close = downtrend_close(100)
        mom = compute_momentum(close, window=MOM_WIN)
        valid = mom.dropna()
        assert (valid < 0.0).all(), "Expected all negative momentum in a downtrend"

    # ── Validation ───────────────────────────────────────────────────────────

    def test_invalid_window_zero_raises(self):
        close = uptrend_close(50)
        with pytest.raises(ValueError, match="momentum_window"):
            compute_momentum(close, window=0)

    def test_invalid_window_negative_raises(self):
        close = uptrend_close(50)
        with pytest.raises(ValueError, match="momentum_window"):
            compute_momentum(close, window=-5)


# ===========================================================================
# momentum_signals tests
# ===========================================================================

class TestMomentumSignals:

    # ── Shape and type ───────────────────────────────────────────────────────

    def test_output_length_matches_input(self):
        close = uptrend_close()
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        assert len(pos) == len(close)

    def test_output_has_no_nan(self):
        close = uptrend_close()
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        assert not pos.isna().any()

    def test_output_is_binary(self):
        close = uptrend_close()
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        assert set(pos.unique()).issubset({0, 1})

    def test_index_preserved(self):
        close = uptrend_close()
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        pd.testing.assert_index_equal(pos.index, close.index)

    # ── Lookahead-bias prevention ─────────────────────────────────────────────

    def test_first_position_always_zero(self):
        """
        After shift(1), position[0] is always 0 regardless of the momentum
        signal: we cannot trade on day 0 using day 0's closing price.
        """
        close = uptrend_close()
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        assert pos.iloc[0] == 0

    def test_no_future_information(self):
        """
        Changing only the last bar's price must not affect any earlier position.
        """
        base = [100.0 + i * 0.5 for i in range(100)]
        modified = base[:-1] + [9999.0]

        pos1 = momentum_signals(make_close(base), momentum_window=MOM_WIN)
        pos2 = momentum_signals(make_close(modified), momentum_window=MOM_WIN)
        assert (pos1.iloc[:-1].values == pos2.iloc[:-1].values).all()

    # ── Warm-up ───────────────────────────────────────────────────────────────

    def test_warmup_period_always_flat(self):
        """
        The first momentum_window positions are NaN (no signal), so after
        shift(1) the strategy must be flat for the first momentum_window bars.
        """
        close = uptrend_close(200)
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        # After shift, indices 0..MOM_WIN are flat (NaN → 0 and first raw = 0).
        assert (pos.iloc[: MOM_WIN] == 0).all()

    # ── Economic behaviour ────────────────────────────────────────────────────

    def test_uptrend_is_long_after_warmup(self):
        """
        A persistent uptrend has positive trailing return on every bar after
        warmup → the default-threshold strategy should be long.
        """
        close = uptrend_close(200)
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        # Allow a couple of extra bars for the shift to propagate.
        check_start = MOM_WIN + 2
        assert (pos.iloc[check_start:] == 1).all(), (
            "Expected all-long after warm-up in a monotone uptrend"
        )

    def test_downtrend_stays_flat(self):
        """
        A persistent downtrend has negative trailing return on every bar →
        the strategy never enters.
        """
        close = downtrend_close(200)
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        check_start = MOM_WIN + 2
        assert (pos.iloc[check_start:] == 0).all(), (
            "Expected all-flat in a persistent downtrend"
        )

    def test_entry_triggers_on_first_positive_momentum(self):
        """
        After warm-up, the strategy must enter on the first bar where trailing
        return > entry_threshold (default 0.0).  For an uptrend that is the
        first post-warm-up bar.
        """
        close = uptrend_close(100)
        pos = momentum_signals(close, momentum_window=MOM_WIN)
        changes = pos.diff().dropna()
        # There must be exactly one entry (0→1 transition).
        assert (changes == 1).sum() == 1

    def test_hysteresis_reduces_trade_count(self):
        """
        Wide entry/exit band → strategy trades less often than narrow band.

        Zigzag price oscillates such that with thresholds = 0 the position
        flips every run.  With a high entry threshold that the momentum never
        reaches, the strategy never enters at all.
        """
        close = zigzag_close(n_cycles=4, run_len=30)

        # Default thresholds: position flips with each run.
        pos_narrow = momentum_signals(
            close, momentum_window=MOM_WIN,
            entry_threshold=0.0, exit_threshold=0.0,
        )
        # Very high entry threshold: momentum never exceeds 5 (100 %), never enters.
        pos_wide = momentum_signals(
            close, momentum_window=MOM_WIN,
            entry_threshold=5.0, exit_threshold=0.0,
        )

        narrow_trades = int(pos_narrow.diff().abs().sum())
        wide_trades = int(pos_wide.diff().abs().sum())
        assert wide_trades <= narrow_trades, (
            f"Wide-band trades ({wide_trades}) should be ≤ narrow-band "
            f"trades ({narrow_trades})"
        )

    def test_high_entry_threshold_no_entry(self):
        """
        With entry_threshold=5.0 (500 % required trailing return), no realistic
        synthetic series will ever trigger entry.
        """
        close = uptrend_close(200)
        pos = momentum_signals(close, momentum_window=MOM_WIN, entry_threshold=5.0)
        assert (pos == 0).all(), (
            "Expected all-flat when entry threshold is unreachably high"
        )

    def test_negative_entry_threshold_enters_even_on_small_loss(self):
        """
        entry_threshold=-0.5, exit_threshold=-1.0: a mild downtrend with
        trailing return > -50 % should still trigger an entry.
        """
        # Slow downtrend: after MOM_WIN bars, return ≈ -MOM_WIN*0.5/100 ≈ -10%,
        # which is > -50%, so the strategy should enter.
        close = downtrend_close(200, step=0.1)
        pos = momentum_signals(
            close, momentum_window=MOM_WIN,
            entry_threshold=-0.5,
            exit_threshold=-1.0,
        )
        # Should have at least one entry.
        assert pos.sum() > 0, "Expected at least one long bar with a lenient entry threshold"

    # ── Validation ───────────────────────────────────────────────────────────

    def test_inverted_thresholds_raises(self):
        """entry_threshold < exit_threshold is invalid."""
        close = uptrend_close(100)
        with pytest.raises(ValueError, match="entry_threshold"):
            momentum_signals(
                close, entry_threshold=-0.1, exit_threshold=0.1
            )

    def test_equal_thresholds_valid(self):
        """entry_threshold == exit_threshold is allowed (no hysteresis gap)."""
        close = uptrend_close(100)
        pos = momentum_signals(
            close, entry_threshold=0.0, exit_threshold=0.0
        )
        assert set(pos.unique()).issubset({0, 1})

    def test_invalid_momentum_window_raises(self):
        """momentum_window < 1 is delegated to compute_momentum."""
        close = uptrend_close(100)
        with pytest.raises(ValueError, match="momentum_window"):
            momentum_signals(close, momentum_window=0)
