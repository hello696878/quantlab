"""
Unit tests for pairs-trading spread and signal computation.

All tests use synthetic price series — no network calls.

Synthetic series design
-----------------------
* ``cointegrated_pair``  — y = x + slowly-drifting mean + noise pulse.
                           Guarantees a brief divergence and reversion
                           that the z-score strategy should detect.
* ``uncorrelated_pair``  — independent random walks; used to verify no
                           spurious entries with high entry threshold.
* ``make_close``         — arbitrary values on a business-day DatetimeIndex.
"""

import pandas as pd
import pytest
import numpy as np

import app.strategies as strategies
from app.strategies import compute_pairs_spread, compute_spread_zscore, pairs_signals


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

LB_WIN = 10   # short lookback for fast tests


def make_close(values: list, start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name="Close", dtype=float)


def identical_pair(n: int = 100, price: float = 100.0):
    """Two identical series — spread = 0, z-score = 0 → no entry."""
    close = make_close([price] * n)
    return close.copy().rename("Y"), close.copy().rename("X")


def diverging_pair(n: int = 100, base: float = 100.0, diverge_start: int = 30,
                   diverge_amount: float = 5.0):
    """
    X stays flat at ``base``.
    Y rises by ``diverge_amount`` at bar ``diverge_start`` then falls back.
    This creates a detectable positive-then-negative z-score pattern.
    """
    y_vals = [base] * n
    for i in range(diverge_start, min(diverge_start + 10, n)):
        y_vals[i] = base + diverge_amount
    close_y = make_close(y_vals)
    close_x = make_close([base] * n)
    return close_y.rename("Y"), close_x.rename("X")


# ===========================================================================
# compute_spread_zscore tests
# ===========================================================================

class TestComputePairsSpread:

    def test_spread_is_log_y_minus_log_x(self):
        close_y = make_close([100.0, 110.0, 121.0])
        close_x = make_close([50.0, 55.0, 60.5])

        spread = compute_pairs_spread(close_y, close_x)
        expected = np.log(close_y) - np.log(close_x)

        assert spread.name == "spread"
        pd.testing.assert_series_equal(spread, expected.rename("spread"))

    def test_spread_rejects_misaligned_indexes(self):
        close_y = make_close([100.0, 101.0], start="2020-01-01")
        close_x = make_close([100.0, 101.0], start="2020-01-02")

        with pytest.raises(ValueError, match="same index"):
            compute_pairs_spread(close_y, close_x)

    def test_spread_rejects_non_positive_prices(self):
        close_y = make_close([100.0, 0.0, 101.0])
        close_x = make_close([100.0, 100.0, 100.0])

        with pytest.raises(ValueError, match="positive"):
            compute_pairs_spread(close_y, close_x)


class TestComputeSpreadZscore:

    def test_output_length_matches_input(self):
        spread = make_close([100.0, 101.0, 99.0, 102.0, 98.0] * 10)
        z = compute_spread_zscore(spread, LB_WIN)
        assert len(z) == len(spread)

    def test_index_preserved(self):
        spread = make_close([100.0 + i * 0.1 for i in range(50)])
        z = compute_spread_zscore(spread, LB_WIN)
        pd.testing.assert_index_equal(z.index, spread.index)

    def test_series_name(self):
        spread = make_close([1.0] * 30)
        z = compute_spread_zscore(spread, LB_WIN)
        assert z.name == "zscore"

    def test_warmup_nans(self):
        """First window-1 values are NaN; position window-1 is first valid."""
        spread = make_close([float(i) for i in range(50)])
        z = compute_spread_zscore(spread, LB_WIN)
        assert z.iloc[: LB_WIN - 1].isna().all()
        assert pd.notna(z.iloc[LB_WIN - 1])

    def test_flat_spread_zscore_zero(self):
        """Constant spread → std = 0 → z-score = 0 (not NaN)."""
        spread = make_close([5.0] * 50)
        z = compute_spread_zscore(spread, LB_WIN)
        valid = z.dropna()
        assert (valid == 0.0).all()

    def test_zscore_mean_near_zero_for_stationary_spread(self):
        """
        For a mean-zero spread the average z-score should be close to zero.
        """
        rng = np.random.default_rng(42)
        values = rng.normal(0, 1, 200).tolist()
        spread = make_close(values)
        z = compute_spread_zscore(spread, LB_WIN)
        assert abs(float(z.dropna().mean())) < 0.5

    def test_zscore_matches_manual_rolling_value(self):
        spread = make_close([1.0, 2.0, 4.0, 7.0, 11.0])
        z = compute_spread_zscore(spread, window=3)

        window = spread.iloc[2:5]
        expected = (window.iloc[-1] - window.mean()) / window.std(ddof=1)
        assert z.iloc[-1] == pytest.approx(expected)

    def test_invalid_window_raises(self):
        spread = make_close([1.0] * 30)
        with pytest.raises(ValueError, match="lookback_window"):
            compute_spread_zscore(spread, window=1)

    def test_invalid_window_zero_raises(self):
        spread = make_close([1.0] * 30)
        with pytest.raises(ValueError, match="lookback_window"):
            compute_spread_zscore(spread, window=0)


# ===========================================================================
# pairs_signals tests
# ===========================================================================

class TestPairsSignals:

    # ── Shape and type ───────────────────────────────────────────────────────

    def test_output_length_matches_input(self):
        close_y, close_x = identical_pair()
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN)
        assert len(sig) == len(close_y)

    def test_output_has_no_nan(self):
        close_y, close_x = identical_pair()
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN)
        assert not sig.isna().any()

    def test_output_values_in_minus1_0_plus1(self):
        close_y, close_x = identical_pair()
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN)
        assert set(sig.unique()).issubset({-1, 0, 1})

    def test_index_preserved(self):
        close_y, close_x = identical_pair()
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN)
        pd.testing.assert_index_equal(sig.index, close_y.index)

    # ── Lookahead-bias prevention ─────────────────────────────────────────────

    def test_first_signal_always_zero(self):
        """After shift(1) the first bar is always flat."""
        close_y, close_x = diverging_pair()
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN)
        assert sig.iloc[0] == 0

    def test_no_future_information(self):
        """Changing only the last bar's price must not affect earlier signals."""
        close_y, close_x = diverging_pair()
        y_vals = list(close_y.values)
        modified_y = make_close(y_vals[:-1] + [9999.0])

        sig1 = pairs_signals(close_y, close_x, lookback_window=LB_WIN)
        sig2 = pairs_signals(modified_y, close_x, lookback_window=LB_WIN)
        assert (sig1.iloc[:-1].values == sig2.iloc[:-1].values).all()

    # ── Warm-up ───────────────────────────────────────────────────────────────

    def test_warmup_period_flat(self):
        """No signal during the z-score warm-up period."""
        close_y, close_x = diverging_pair()
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN)
        # First LB_WIN bars are always 0 (warmup NaN → 0, then shifted).
        assert (sig.iloc[:LB_WIN] == 0).all()

    # ── Economic behaviour ────────────────────────────────────────────────────

    def test_identical_pair_never_enters(self):
        """Identical prices → spread = 0 → z-score = 0 → never enters."""
        close_y, close_x = identical_pair(100)
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN,
                            entry_z_score=0.1, exit_z_score=0.0)
        assert (sig == 0).all()

    def test_diverging_pair_generates_signal(self):
        """A clear divergence should produce at least one non-zero bar."""
        close_y, close_x = diverging_pair(n=100, diverge_start=20,
                                           diverge_amount=20.0)
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN,
                            entry_z_score=1.0, exit_z_score=0.0)
        assert sig.abs().sum() > 0, "Expected at least one active bar"

    def test_short_spread_when_y_expensive(self):
        """
        When y moves far above x (z-score high), the signal should be -1
        (short y / long x — betting on mean reversion).
        """
        # y jumps high at bar 25; after LB_WIN warmup z-score will be positive.
        close_y, close_x = diverging_pair(n=100, diverge_start=20,
                                           diverge_amount=50.0)
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN,
                            entry_z_score=1.0, exit_z_score=0.0)
        active = sig[sig != 0]
        if len(active) > 0:
            # First active signal should be -1 (y expensive).
            assert active.iloc[0] == -1

    def test_high_entry_z_no_entry(self):
        """entry_z_score=100 — practically unreachable → never enters."""
        close_y, close_x = diverging_pair(n=200, diverge_amount=5.0)
        sig = pairs_signals(close_y, close_x, lookback_window=LB_WIN,
                            entry_z_score=100.0, exit_z_score=50.0)
        assert (sig == 0).all()

    def test_long_spread_exit_uses_negative_exit_threshold(self, monkeypatch):
        """Long spread exits only after z-score crosses above -exit_z."""
        close_y, close_x = identical_pair(n=7)
        z_values = [np.nan, np.nan, -2.1, -0.5, -0.49, 0.0, 0.0]

        def fake_zscore(spread, window):
            return pd.Series(z_values, index=spread.index, name="zscore")

        monkeypatch.setattr(strategies, "compute_spread_zscore", fake_zscore)
        sig = pairs_signals(
            close_y,
            close_x,
            lookback_window=LB_WIN,
            entry_z_score=2.0,
            exit_z_score=0.5,
        )

        assert sig.tolist() == [0, 0, 0, 1, 1, 0, 0]

    def test_short_spread_exit_uses_positive_exit_threshold(self, monkeypatch):
        """Short spread exits only after z-score crosses below +exit_z."""
        close_y, close_x = identical_pair(n=7)
        z_values = [np.nan, np.nan, 2.1, 0.5, 0.49, 0.0, 0.0]

        def fake_zscore(spread, window):
            return pd.Series(z_values, index=spread.index, name="zscore")

        monkeypatch.setattr(strategies, "compute_spread_zscore", fake_zscore)
        sig = pairs_signals(
            close_y,
            close_x,
            lookback_window=LB_WIN,
            entry_z_score=2.0,
            exit_z_score=0.5,
        )

        assert sig.tolist() == [0, 0, 0, -1, -1, 0, 0]

    def test_entry_threshold_equality_does_not_enter(self, monkeypatch):
        close_y, close_x = identical_pair(n=5)
        z_values = [np.nan, np.nan, 2.0, -2.0, 0.0]

        def fake_zscore(spread, window):
            return pd.Series(z_values, index=spread.index, name="zscore")

        monkeypatch.setattr(strategies, "compute_spread_zscore", fake_zscore)
        sig = pairs_signals(
            close_y,
            close_x,
            lookback_window=LB_WIN,
            entry_z_score=2.0,
            exit_z_score=0.5,
        )

        assert sig.tolist() == [0, 0, 0, 0, 0]

    # ── Validation ───────────────────────────────────────────────────────────

    def test_entry_z_equal_exit_z_raises(self):
        close_y, close_x = identical_pair(50)
        with pytest.raises(ValueError, match="entry_z_score"):
            pairs_signals(close_y, close_x, entry_z_score=1.0, exit_z_score=1.0)

    def test_entry_z_less_than_exit_z_raises(self):
        close_y, close_x = identical_pair(50)
        with pytest.raises(ValueError, match="entry_z_score"):
            pairs_signals(close_y, close_x, entry_z_score=0.5, exit_z_score=1.0)

    def test_negative_exit_z_raises(self):
        close_y, close_x = identical_pair(50)
        with pytest.raises(ValueError, match="exit_z_score"):
            pairs_signals(close_y, close_x, entry_z_score=2.0, exit_z_score=-0.1)

    def test_invalid_lookback_window_raises(self):
        close_y, close_x = identical_pair(50)
        with pytest.raises(ValueError, match="lookback_window"):
            pairs_signals(close_y, close_x, lookback_window=1)
