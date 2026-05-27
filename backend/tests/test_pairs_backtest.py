"""
Unit tests for the pairs-specific backtest engine.

All tests use synthetic aligned price series and pre-shifted signals.
"""

import pandas as pd
import pytest

from app.backtest import run_pairs_backtest


def make_series(values: list[float], start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, dtype=float)


def test_long_spread_profits_when_y_outperforms_x():
    close_y = make_series([100.0, 110.0])
    close_x = make_series([100.0, 100.0])
    signal = make_series([0.0, 1.0])

    strategy, _, _ = run_pairs_backtest(
        close_y,
        close_x,
        signal,
        transaction_cost_bps=0.0,
        initial_capital=100_000.0,
    )

    assert strategy.iloc[-1] == pytest.approx(105_000.0)


def test_short_spread_profits_when_x_outperforms_y():
    close_y = make_series([100.0, 100.0])
    close_x = make_series([100.0, 110.0])
    signal = make_series([0.0, -1.0])

    strategy, _, _ = run_pairs_backtest(
        close_y,
        close_x,
        signal,
        transaction_cost_bps=0.0,
        initial_capital=100_000.0,
    )

    assert strategy.iloc[-1] == pytest.approx(105_000.0)


def test_benchmark_is_equal_weight_buy_and_hold_on_same_dates():
    close_y = make_series([100.0, 110.0, 121.0])
    close_x = make_series([100.0, 90.0, 81.0])
    signal = make_series([0.0, 0.0, 0.0])

    strategy, benchmark, _ = run_pairs_backtest(
        close_y,
        close_x,
        signal,
        transaction_cost_bps=0.0,
        initial_capital=100_000.0,
    )

    pd.testing.assert_index_equal(strategy.index, benchmark.index)
    assert benchmark.iloc[1] == pytest.approx(100_000.0)
    assert benchmark.iloc[2] == pytest.approx(100_000.0)


def test_transaction_cost_charged_on_entry_and_exit_only():
    close_y = make_series([100.0, 100.0, 100.0, 100.0])
    close_x = make_series([100.0, 100.0, 100.0, 100.0])
    signal = make_series([0.0, 1.0, 1.0, 0.0])

    strategy, _, trades = run_pairs_backtest(
        close_y,
        close_x,
        signal,
        transaction_cost_bps=100.0,
        initial_capital=100_000.0,
    )

    assert strategy.tolist() == pytest.approx([100_000.0, 99_000.0, 99_000.0, 98_010.0])
    assert [trade["action"] for trade in trades] == ["LONG SPREAD", "EXIT"]
    assert [trade["cost"] for trade in trades] == pytest.approx([1_000.0, 990.0])


def test_flip_cost_is_double_turnover():
    close_y = make_series([100.0, 100.0, 100.0])
    close_x = make_series([100.0, 100.0, 100.0])
    signal = make_series([0.0, 1.0, -1.0])

    strategy, _, trades = run_pairs_backtest(
        close_y,
        close_x,
        signal,
        transaction_cost_bps=100.0,
        initial_capital=100_000.0,
    )

    assert strategy.tolist() == pytest.approx([100_000.0, 99_000.0, 97_020.0])
    assert [trade["action"] for trade in trades] == ["LONG SPREAD", "SHORT SPREAD"]
    assert trades[0]["cost"] == pytest.approx(1_000.0)
    assert trades[1]["cost"] == pytest.approx(1_980.0)


def test_invalid_pairs_signal_values_raise():
    close_y = make_series([100.0, 101.0])
    close_x = make_series([100.0, 100.0])
    signal = make_series([0.0, 2.0])

    with pytest.raises(ValueError, match="-1, 0, or 1"):
        run_pairs_backtest(close_y, close_x, signal)
