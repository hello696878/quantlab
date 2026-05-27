"""
Unit tests for volatility breakout level computation and signal generation.

All tests use synthetic price series and make no network calls.
"""

import pandas as pd
import pytest

import app.strategies as strategies
from app.strategies import (
    compute_volatility_breakout_levels,
    volatility_breakout_signals,
)


LB_WIN = 3
EXIT_WIN = 2


def make_close(values: list[float], start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name="Close", dtype=float)


def breakout_close() -> pd.Series:
    return make_close([10.0, 11.0, 12.0, 15.0, 14.0, 13.0, 16.0, 12.0])


class TestComputeVolatilityBreakoutLevels:
    def test_output_length_matches_input(self):
        close = breakout_close()
        breakout, exit_level = compute_volatility_breakout_levels(close, LB_WIN, 0.5, EXIT_WIN)
        assert len(breakout) == len(close)
        assert len(exit_level) == len(close)

    def test_index_preserved(self):
        close = breakout_close()
        breakout, exit_level = compute_volatility_breakout_levels(close, LB_WIN, 0.5, EXIT_WIN)
        pd.testing.assert_index_equal(breakout.index, close.index)
        pd.testing.assert_index_equal(exit_level.index, close.index)

    def test_series_names(self):
        close = breakout_close()
        breakout, exit_level = compute_volatility_breakout_levels(close, LB_WIN, 0.5, EXIT_WIN)
        assert breakout.name == "breakout_level"
        assert exit_level.name == "exit_level"

    def test_known_breakout_and_exit_levels(self):
        """
        breakout_level[t] = rolling_high[t-1] + multiplier * range[t-1].
        exit_level[t] = rolling_mean(close, exit_window)[t].
        """
        close = make_close([10.0, 11.0, 12.0, 15.0, 14.0])
        breakout, exit_level = compute_volatility_breakout_levels(
            close,
            lookback_window=3,
            breakout_multiplier=0.5,
            exit_window=2,
        )

        rolling_high = close.rolling(3).max()
        rolling_low = close.rolling(3).min()
        expected_breakout = (
            rolling_high.shift(1) + 0.5 * (rolling_high - rolling_low).shift(1)
        ).rename("breakout_level")
        expected_exit = close.rolling(2).mean().rename("exit_level")

        pd.testing.assert_series_equal(breakout, expected_breakout)
        pd.testing.assert_series_equal(exit_level, expected_exit)

    def test_breakout_level_uses_prior_channel_not_today_close(self):
        close = make_close([10.0, 11.0, 12.0, 100.0])
        breakout, _ = compute_volatility_breakout_levels(close, 3, 1.0, 2)
        assert pd.isna(breakout.iloc[2])
        assert breakout.iloc[3] == pytest.approx(14.0)

    def test_invalid_lookback_window_raises(self):
        close = breakout_close()
        with pytest.raises(ValueError, match="lookback_window"):
            compute_volatility_breakout_levels(close, lookback_window=1)

    def test_invalid_multiplier_raises(self):
        close = breakout_close()
        with pytest.raises(ValueError, match="breakout_multiplier"):
            compute_volatility_breakout_levels(close, breakout_multiplier=0.0)

    def test_invalid_exit_window_raises(self):
        close = breakout_close()
        with pytest.raises(ValueError, match="exit_window"):
            compute_volatility_breakout_levels(close, exit_window=0)


class TestVolatilityBreakoutSignals:
    def test_output_length_matches_input(self):
        close = breakout_close()
        pos = volatility_breakout_signals(close, LB_WIN, 0.5, EXIT_WIN)
        assert len(pos) == len(close)

    def test_output_has_no_nan(self):
        close = breakout_close()
        pos = volatility_breakout_signals(close, LB_WIN, 0.5, EXIT_WIN)
        assert not pos.isna().any()

    def test_output_is_binary(self):
        close = breakout_close()
        pos = volatility_breakout_signals(close, LB_WIN, 0.5, EXIT_WIN)
        assert set(pos.unique()).issubset({0, 1})

    def test_index_preserved(self):
        close = breakout_close()
        pos = volatility_breakout_signals(close, LB_WIN, 0.5, EXIT_WIN)
        pd.testing.assert_index_equal(pos.index, close.index)

    def test_first_position_always_zero(self):
        close = breakout_close()
        pos = volatility_breakout_signals(close, LB_WIN, 0.5, EXIT_WIN)
        assert pos.iloc[0] == 0

    def test_no_future_information(self):
        base = [10.0, 11.0, 12.0, 15.0, 14.0, 13.0, 16.0, 12.0]
        modified = base[:-1] + [9999.0]
        pos1 = volatility_breakout_signals(make_close(base), LB_WIN, 0.5, EXIT_WIN)
        pos2 = volatility_breakout_signals(make_close(modified), LB_WIN, 0.5, EXIT_WIN)
        assert (pos1.iloc[:-1].values == pos2.iloc[:-1].values).all()

    def test_warmup_period_always_flat(self):
        close = breakout_close()
        pos = volatility_breakout_signals(close, LB_WIN, 0.5, EXIT_WIN)
        assert (pos.iloc[: LB_WIN + 1] == 0).all()

    def test_enters_on_breakout_and_exits_below_exit_level(self, monkeypatch):
        close = make_close([10.0, 11.0, 12.0, 15.0, 14.0, 13.0, 16.0])
        index = close.index
        breakout = pd.Series(
            [None, None, None, 14.0, 20.0, 20.0, 20.0],
            index=index,
            name="breakout_level",
            dtype=float,
        )
        exit_level = pd.Series(
            [None, 10.5, 11.5, 13.5, 14.5, 13.5, 14.5],
            index=index,
            name="exit_level",
            dtype=float,
        )
        monkeypatch.setattr(
            strategies,
            "compute_volatility_breakout_levels",
            lambda close, lookback_window, breakout_multiplier, exit_window: (
                breakout,
                exit_level,
            ),
        )

        pos = strategies.volatility_breakout_signals(close, LB_WIN, 0.5, EXIT_WIN)

        expected = pd.Series([0, 0, 0, 0, 1, 0, 0], index=index, name="position")
        pd.testing.assert_series_equal(pos, expected)

    def test_flat_price_never_enters(self):
        close = make_close([100.0] * 80)
        pos = volatility_breakout_signals(close, LB_WIN, 1.0, EXIT_WIN)
        assert (pos == 0).all()

    def test_high_multiplier_no_entry(self):
        close = breakout_close()
        pos = volatility_breakout_signals(close, LB_WIN, 100.0, EXIT_WIN)
        assert (pos == 0).all()

    def test_lower_multiplier_gets_at_least_as_much_exposure(self):
        close = breakout_close()
        pos_low = volatility_breakout_signals(close, LB_WIN, 0.1, EXIT_WIN)
        pos_high = volatility_breakout_signals(close, LB_WIN, 10.0, EXIT_WIN)
        assert pos_low.sum() >= pos_high.sum()

    def test_zero_breakout_multiplier_raises(self):
        close = breakout_close()
        with pytest.raises(ValueError, match="breakout_multiplier"):
            volatility_breakout_signals(close, breakout_multiplier=0.0)

    def test_negative_breakout_multiplier_raises(self):
        close = breakout_close()
        with pytest.raises(ValueError, match="breakout_multiplier"):
            volatility_breakout_signals(close, breakout_multiplier=-1.0)

    def test_zero_exit_window_raises(self):
        close = breakout_close()
        with pytest.raises(ValueError, match="exit_window"):
            volatility_breakout_signals(close, exit_window=0)

    def test_invalid_lookback_window_raises(self):
        close = breakout_close()
        with pytest.raises(ValueError, match="lookback_window"):
            volatility_breakout_signals(close, lookback_window=1)
