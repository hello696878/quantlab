"""
Unit tests for app.custom_strategy (the safe rule evaluator).
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.custom_strategy import (
    _operand_series,
    _rule_boolean,
    custom_strategy_signals,
    required_window,
)
from app.schemas import (
    CustomCloseOperand,
    CustomConstantOperand,
    CustomIndicatorOperand,
    CustomIndicatorParams,
    CustomRule,
)
from app.strategies import compute_bollinger_bands, compute_rsi, sma_crossover_signals


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def make_close(n: int = 300, start: str = "2018-01-01") -> pd.Series:
    # Trend + sinusoid → guarantees multiple SMA crossovers.
    vals = [100.0 + 25.0 * math.sin(i / 25.0) + i * 0.1 for i in range(n)]
    idx = pd.date_range(start, periods=n, freq="B")
    return pd.Series(vals, index=idx, name="Close", dtype=float)


def ind(name: str, window: int, num_std: float | None = None) -> CustomIndicatorOperand:
    return CustomIndicatorOperand(
        name=name, params=CustomIndicatorParams(window=window, num_std=num_std)
    )


def const(v: float) -> CustomConstantOperand:
    return CustomConstantOperand(value=v)


def close_op() -> CustomCloseOperand:
    return CustomCloseOperand()


def rule(left, op, right) -> CustomRule:
    return CustomRule(left=left, operator=op, right=right)


# ---------------------------------------------------------------------------
# Operand resolution
# ---------------------------------------------------------------------------


def test_close_operand():
    close = make_close(50)
    s = _operand_series(close, close_op())
    pd.testing.assert_series_equal(s, close)


def test_constant_operand():
    close = make_close(50)
    s = _operand_series(close, const(42.5))
    assert (s == 42.5).all()
    assert len(s) == len(close)
    assert s.index.equals(close.index)


def test_sma_operand_matches_rolling_mean():
    close = make_close(100)
    s = _operand_series(close, ind("sma", 10))
    expected = close.rolling(window=10, min_periods=10).mean()
    pd.testing.assert_series_equal(s, expected)


def test_rsi_operand_matches_existing_rsi():
    close = make_close(100)
    s = _operand_series(close, ind("rsi", 14))
    expected = compute_rsi(close, 14)
    pd.testing.assert_series_equal(s, expected)


def test_momentum_operand_matches_pct_change():
    close = make_close(100)
    s = _operand_series(close, ind("momentum", 20))
    pd.testing.assert_series_equal(s, close.pct_change(periods=20))


def test_bollinger_operands_order():
    close = make_close(100)
    upper = _operand_series(close, ind("bb_upper", 20, num_std=2.0))
    middle = _operand_series(close, ind("bb_middle", 20))
    lower = _operand_series(close, ind("bb_lower", 20, num_std=2.0))
    # Where defined, upper > middle > lower.
    valid = upper.dropna().index.intersection(lower.dropna().index)
    assert (upper.loc[valid] > middle.loc[valid]).all()
    assert (middle.loc[valid] > lower.loc[valid]).all()


def test_bollinger_operands_match_existing_bands():
    close = make_close(100)
    middle, upper, lower = compute_bollinger_bands(close, 20, 2.0)

    pd.testing.assert_series_equal(
        _operand_series(close, ind("bb_middle", 20)), middle
    )
    pd.testing.assert_series_equal(
        _operand_series(close, ind("bb_upper", 20, num_std=2.0)), upper
    )
    pd.testing.assert_series_equal(
        _operand_series(close, ind("bb_lower", 20, num_std=2.0)), lower
    )


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "op,expected",
    [
        (">", [False, False, True]),
        (">=", [False, True, True]),
        ("<", [True, False, False]),
        ("<=", [True, True, False]),
    ],
)
def test_all_comparison_operators(op, expected):
    close = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.date_range("2020-01-01", periods=3),
        name="Close",
    )
    out = _rule_boolean(close, rule(close_op(), op, const(2.0)))
    assert out.tolist() == expected


def test_indicator_vs_constant_and_constant_vs_indicator():
    close = make_close(80)
    indicator_rule = rule(ind("sma", 10), ">", const(0.0))
    constant_rule = rule(const(1e12), ">", ind("sma", 10))

    assert _rule_boolean(close, indicator_rule).iloc[10:].all()
    constant_out = _rule_boolean(close, constant_rule)
    assert constant_out.iloc[:9].eq(False).all()
    assert constant_out.iloc[9:].all()


def test_warmup_nan_comparisons_are_false():
    close = make_close(80)
    entry = [rule(ind("sma", 10), ">", const(0.0))]
    pos = custom_strategy_signals(close, entry, "all", [], "any")

    # SMA(10) is first available on row 9; the shifted position starts on row 10.
    assert pos.iloc[:10].eq(0).all()
    assert pos.iloc[10] == 1


# ---------------------------------------------------------------------------
# required_window
# ---------------------------------------------------------------------------


def test_required_window():
    rules = [
        rule(ind("sma", 50), ">", ind("sma", 200)),
        rule(close_op(), ">", const(0)),
    ]
    assert required_window(rules) == 200


def test_required_window_no_indicators():
    rules = [rule(close_op(), ">", const(100))]
    assert required_window(rules) == 1


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------


def test_reproduces_builtin_sma_crossover():
    """A custom 'fast>slow' entry / 'fast<=slow' exit reproduces SMA crossover."""
    close = make_close(300)
    entry = [rule(ind("sma", 20), ">", ind("sma", 50))]
    exit_ = [rule(ind("sma", 20), "<=", ind("sma", 50))]

    custom_pos = custom_strategy_signals(close, entry, "all", exit_, "any")
    builtin_pos = sma_crossover_signals(close, fast_window=20, slow_window=50)

    pd.testing.assert_series_equal(
        custom_pos, builtin_pos, check_names=False
    )


def test_position_is_shifted_no_lookahead():
    close = make_close(50)
    entry = [rule(close_op(), ">", const(0))]  # always true
    pos = custom_strategy_signals(close, entry, "all", [], "any")
    # First bar is always 0 because of the one-day forward shift.
    assert pos.iloc[0] == 0
    # Always-true entry with no exit → long from the second bar onward.
    assert pos.iloc[1:].eq(1).all()


def test_never_enters_when_condition_impossible():
    close = make_close(50)
    entry = [rule(close_op(), ">", const(1e12))]
    pos = custom_strategy_signals(close, entry, "all", [], "any")
    assert pos.eq(0).all()


def test_empty_exit_rules_hold_position():
    close = make_close(60)
    entry = [rule(close_op(), ">", const(0))]
    pos = custom_strategy_signals(close, entry, "all", [], "any")
    # Once entered (bar 1), never exits.
    assert pos.iloc[-1] == 1


def test_entry_and_exit_both_true_alternates_after_shift():
    close = make_close(8)
    always = [rule(close_op(), ">", const(0))]
    pos = custom_strategy_signals(close, always, "all", always, "any")

    # Raw state enters while flat, exits while long. The returned position is shifted.
    assert pos.tolist() == [0, 1, 0, 1, 0, 1, 0, 1]


def test_entry_logic_all_vs_any_differ():
    close = make_close(120)
    # Rule A: close > sma(10)  | Rule B: close > sma(50)
    rule_a = rule(close_op(), ">", ind("sma", 10))
    rule_b = rule(close_op(), ">", ind("sma", 50))

    pos_all = custom_strategy_signals(close, [rule_a, rule_b], "all", [], "any")
    pos_any = custom_strategy_signals(close, [rule_a, rule_b], "any", [], "any")

    # "any" is looser → enters at least as early/often as "all".
    assert pos_any.sum() >= pos_all.sum()
    # On this data they should not be identical.
    assert not pos_any.equals(pos_all)


def test_exit_logic_any_exits_on_first_trigger():
    close = make_close(200)
    entry = [rule(ind("sma", 10), ">", ind("sma", 30))]
    exit_ = [
        rule(ind("sma", 10), "<", ind("sma", 30)),
        rule(close_op(), "<", const(0)),  # never true
    ]
    pos = custom_strategy_signals(close, entry, "all", exit_, "any")
    # Should produce both entries and exits (some 1s and some 0s after warmup).
    warm = pos.iloc[60:]
    assert warm.eq(1).any()
    assert warm.eq(0).any()
