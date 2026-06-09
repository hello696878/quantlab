"""
Unit tests for app.backtest.run_backtest.
"""

import pandas as pd
import pytest

from app.backtest import run_backtest
from app.strategies import sma_crossover_signals

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAST, SLOW = 20, 50
INITIAL = 100_000.0


def make_close(values: list, start: str = "2018-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx, name="Close", dtype=float)


def uptrend_close(n: int = 400) -> pd.Series:
    return make_close([100.0 + i * 0.5 for i in range(n)])


def flat_position(close: pd.Series) -> pd.Series:
    return pd.Series(0.0, index=close.index, name="position")


def strategy_position(close: pd.Series) -> pd.Series:
    return sma_crossover_signals(close, FAST, SLOW)


# ---------------------------------------------------------------------------
# Equity curve shape
# ---------------------------------------------------------------------------

def test_equity_length_matches_close():
    close = uptrend_close()
    pos = strategy_position(close)
    strat_eq, bench_eq, _ = run_backtest(close, pos, initial_capital=INITIAL)
    assert len(strat_eq) == len(close)
    assert len(bench_eq) == len(close)


def test_equity_starts_at_initial_capital():
    close = uptrend_close()
    pos = strategy_position(close)
    strat_eq, bench_eq, _ = run_backtest(close, pos, initial_capital=INITIAL)
    # Day-0 return is 0, so equity should equal initial capital on day 0.
    assert strat_eq.iloc[0] == pytest.approx(INITIAL, rel=1e-6)
    assert bench_eq.iloc[0] == pytest.approx(INITIAL, rel=1e-6)


def test_no_negative_equity():
    close = uptrend_close()
    pos = strategy_position(close)
    strat_eq, bench_eq, _ = run_backtest(close, pos, initial_capital=INITIAL)
    assert (strat_eq > 0).all()
    assert (bench_eq > 0).all()


def test_index_matches_close():
    close = uptrend_close()
    pos = strategy_position(close)
    strat_eq, bench_eq, _ = run_backtest(close, pos, initial_capital=INITIAL)
    pd.testing.assert_index_equal(strat_eq.index, close.index)
    pd.testing.assert_index_equal(bench_eq.index, close.index)


# ---------------------------------------------------------------------------
# Transaction costs
# ---------------------------------------------------------------------------

def test_zero_cost_is_at_least_as_good_as_positive_cost():
    """Higher transaction cost must never produce a higher final equity."""
    close = uptrend_close()
    pos = strategy_position(close)
    eq_no_cost, _, _ = run_backtest(close, pos, transaction_cost_bps=0.0)
    eq_with_cost, _, _ = run_backtest(close, pos, transaction_cost_bps=50.0)
    assert eq_no_cost.iloc[-1] >= eq_with_cost.iloc[-1]


def test_cost_reduces_equity_when_trades_occur():
    """If there are any trades, 100 bps cost should noticeably reduce returns."""
    close = uptrend_close()
    pos = strategy_position(close)
    eq_low, _, trades = run_backtest(close, pos, transaction_cost_bps=1.0)
    eq_high, _, _ = run_backtest(close, pos, transaction_cost_bps=100.0)
    if len(trades) > 0:  # only meaningful when trades happened
        assert eq_low.iloc[-1] > eq_high.iloc[-1]


def test_entry_cost_is_paid_before_interval_return():
    """
    A position of 1 on day 1 is held over close[0] -> close[1].
    Entry cost is deducted before that interval's return is earned.
    """
    close = make_close([100.0, 110.0])
    pos = pd.Series([0.0, 1.0], index=close.index, name="position")

    strat_eq, _, trades = run_backtest(
        close,
        pos,
        transaction_cost_bps=100.0,
        initial_capital=INITIAL,
    )

    expected = INITIAL * (1.0 - 0.01) * (110.0 / 100.0)
    assert strat_eq.iloc[-1] == pytest.approx(expected)
    assert trades == [
        {
            "date": str(close.index[0].date()),
            "action": "BUY",
            "price": 100.0,
            "shares": 990.0,
            "cost": 1000.0,
        }
    ]


def test_exit_trade_logs_previous_close_execution_price():
    """
    If position drops to 0 on day 2, the sale happens at close[1].
    The strategy is then flat over close[1] -> close[2].
    """
    close = make_close([100.0, 110.0, 121.0])
    pos = pd.Series([0.0, 1.0, 0.0], index=close.index, name="position")

    strat_eq, _, trades = run_backtest(
        close,
        pos,
        transaction_cost_bps=0.0,
        initial_capital=INITIAL,
    )

    assert strat_eq.iloc[-1] == pytest.approx(110_000.0)
    assert trades[0]["date"] == str(close.index[0].date())
    assert trades[0]["price"] == 100.0
    assert trades[0]["shares"] == 1000.0
    assert trades[1]["date"] == str(close.index[1].date())
    assert trades[1]["price"] == 110.0
    assert trades[1]["shares"] == 1000.0


def test_fractional_exposure_cost_uses_effective_turnover():
    """A 50% allocation pays half-sized entry/exit costs and logs real trades."""
    close = make_close([100.0, 100.0, 100.0])
    pos = pd.Series([0.0, 0.5, 0.0], index=close.index, name="position")

    strat_eq, _, trades = run_backtest(
        close,
        pos,
        transaction_cost_bps=100.0,
        initial_capital=1000.0,
    )

    assert [t["action"] for t in trades] == ["BUY", "SELL"]
    assert trades[0]["cost"] == pytest.approx(5.0)
    assert trades[0]["shares"] == pytest.approx(4.975)
    assert trades[1]["cost"] == pytest.approx(4.975)
    assert strat_eq.iloc[1] == pytest.approx(995.0)
    assert strat_eq.iloc[2] == pytest.approx(990.025)


def test_fractional_long_short_flip_cost_uses_exposure_delta():
    close = make_close([100.0, 100.0, 100.0])
    pos = pd.Series([0.5, -0.5, 0.0], index=close.index, name="position")

    strat_eq, _, trades = run_backtest(
        close,
        pos,
        transaction_cost_bps=100.0,
        initial_capital=1000.0,
    )

    assert [t["action"] for t in trades] == ["BUY", "FLIP_TO_SHORT", "COVER"]
    assert trades[0]["cost"] == pytest.approx(5.0)
    assert trades[1]["cost"] == pytest.approx(9.95)
    assert trades[2]["cost"] == pytest.approx(4.9253)
    assert strat_eq.iloc[-1] == pytest.approx(980.12475)


def test_sparse_position_is_forward_filled():
    """Missing position dates mean keep the last known exposure, not go flat."""
    close = make_close([100.0, 110.0, 121.0])
    sparse_pos = pd.Series([1.0], index=[close.index[0]], name="position")

    strat_eq, _, _ = run_backtest(
        close,
        sparse_pos,
        transaction_cost_bps=0.0,
        initial_capital=INITIAL,
    )

    assert strat_eq.iloc[-1] == pytest.approx(121_000.0)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def test_benchmark_equals_buy_and_hold():
    """
    Benchmark equity must equal initial_capital × (close[-1] / close[0]).
    This follows from cumprod of pct_change with the first return filled to 0.
    """
    close = uptrend_close()
    pos = strategy_position(close)
    _, bench_eq, _ = run_backtest(close, pos, initial_capital=INITIAL)
    expected = INITIAL * float(close.iloc[-1] / close.iloc[0])
    assert bench_eq.iloc[-1] == pytest.approx(expected, rel=1e-6)


def test_benchmark_unaffected_by_position():
    """Benchmark should be the same regardless of the strategy position."""
    close = uptrend_close()
    pos_active = strategy_position(close)
    pos_flat = flat_position(close)

    _, bench_active, _ = run_backtest(close, pos_active, initial_capital=INITIAL)
    _, bench_flat, _ = run_backtest(close, pos_flat, initial_capital=INITIAL)

    pd.testing.assert_series_equal(bench_active, bench_flat)


# ---------------------------------------------------------------------------
# Flat position (always in cash)
# ---------------------------------------------------------------------------

def test_flat_position_produces_no_trades():
    close = uptrend_close()
    pos = flat_position(close)
    _, _, trades = run_backtest(close, pos, initial_capital=INITIAL)
    assert len(trades) == 0


def test_flat_position_equity_stays_at_initial():
    """If always flat, the strategy earns zero and equity stays at initial."""
    close = uptrend_close()
    pos = flat_position(close)
    strat_eq, _, _ = run_backtest(close, pos, initial_capital=INITIAL)
    # Use pandas element-wise tolerance rather than pytest.approx on the whole series.
    assert (strat_eq - INITIAL).abs().max() < 1e-6


# ---------------------------------------------------------------------------
# Trade log
# ---------------------------------------------------------------------------

def test_trade_actions_are_buy_or_sell():
    close = uptrend_close()
    pos = strategy_position(close)
    _, _, trades = run_backtest(close, pos, initial_capital=INITIAL)
    for t in trades:
        assert t["action"] in ("BUY", "SELL"), f"Unexpected action: {t['action']}"


def test_trades_are_chronological():
    close = uptrend_close()
    pos = strategy_position(close)
    _, _, trades = run_backtest(close, pos, initial_capital=INITIAL)
    dates = [t["date"] for t in trades]
    assert dates == sorted(dates)


def test_buy_before_sell():
    """Every SELL must be preceded by a BUY (trades alternate BUY/SELL)."""
    close = uptrend_close()
    pos = strategy_position(close)
    _, _, trades = run_backtest(close, pos, initial_capital=INITIAL)
    actions = [t["action"] for t in trades]
    for i, action in enumerate(actions):
        if action == "SELL":
            assert i > 0 and actions[i - 1] == "BUY"


def test_trade_prices_are_positive():
    close = uptrend_close()
    pos = strategy_position(close)
    _, _, trades = run_backtest(close, pos, initial_capital=INITIAL)
    for t in trades:
        assert t["price"] > 0


def test_trade_costs_non_negative():
    close = uptrend_close()
    pos = strategy_position(close)
    _, _, trades = run_backtest(close, pos, initial_capital=INITIAL)
    for t in trades:
        assert t["cost"] >= 0.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_too_few_bars_raises():
    close = make_close([100.0])
    pos = pd.Series([0.0], index=close.index)
    with pytest.raises(ValueError, match="at least 2"):
        run_backtest(close, pos)
