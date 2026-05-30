"""
Custom Strategy Builder (v1) — safe, no-code rule evaluation.

A user-defined strategy is a set of *entry* and *exit* rules.  Each rule
compares two operands (close, a numeric constant, or a technical indicator)
with one of ``> >= < <=``.  Rules are combined with ``all`` (AND) or ``any``
(OR) logic.

Safety
------
There is **no code execution** here.  Operands are looked up in a fixed
dispatch table and indicators are computed with vectorised pandas operations.
No ``eval``/``exec``, no user-supplied Python/JS is ever run.

Indicators reuse the exact same math as the built-in strategies
(``compute_rsi`` / ``compute_bollinger_bands``) so results are consistent.
"""

from __future__ import annotations

from typing import Iterable, List

import operator as _operator

import pandas as pd

from app.strategies import compute_bollinger_bands, compute_rsi

# Allowed comparison operators (whitelisted — never parsed from a string into code).
_OPERATORS = {
    ">": _operator.gt,
    ">=": _operator.ge,
    "<": _operator.lt,
    "<=": _operator.le,
}


def _operand_series(close: pd.Series, operand) -> pd.Series:
    """
    Resolve an operand (Pydantic model) to a pandas Series aligned to *close*.

    Supported operand types: close, constant, indicator
    (sma, rsi, bb_upper, bb_middle, bb_lower, momentum).
    """
    otype = operand.type

    if otype == "close":
        return close

    if otype == "constant":
        return pd.Series(float(operand.value), index=close.index)

    if otype == "indicator":
        name = operand.name
        window = int(operand.params.window)

        if name == "sma":
            return close.rolling(window=window, min_periods=window).mean()

        if name == "rsi":
            return compute_rsi(close, window)

        if name == "momentum":
            # close[t] / close[t-window] - 1
            return close.pct_change(periods=window)

        if name in ("bb_upper", "bb_middle", "bb_lower"):
            num_std = float(operand.params.num_std) if operand.params.num_std is not None else 2.0
            middle, upper, lower = compute_bollinger_bands(close, window, num_std)
            return {"bb_middle": middle, "bb_upper": upper, "bb_lower": lower}[name]

        raise ValueError(f"Unknown indicator '{name}'.")

    raise ValueError(f"Unknown operand type '{otype}'.")


def _rule_boolean(close: pd.Series, rule) -> pd.Series:
    """Evaluate a single rule into a boolean Series (NaN/warm-up → False)."""
    left = _operand_series(close, rule.left)
    right = _operand_series(close, rule.right)
    op = _OPERATORS.get(rule.operator)
    if op is None:
        raise ValueError(f"Unsupported operator '{rule.operator}'.")
    result = op(left, right)
    # Any comparison involving NaN is already False in pandas; make it explicit.
    return result.fillna(False).astype(bool)


def _combine(bools: List[pd.Series], logic: str, index) -> pd.Series:
    """Combine boolean Series with 'all' (AND) or 'any' (OR)."""
    if logic not in ("all", "any"):
        raise ValueError(f"Unsupported rule logic '{logic}'.")
    if not bools:
        # No rules → condition is never satisfied.
        return pd.Series(False, index=index)
    combined = bools[0].copy()
    for b in bools[1:]:
        combined = (combined & b) if logic == "all" else (combined | b)
    return combined.astype(bool)


def required_window(rules: Iterable) -> int:
    """Largest indicator look-back window referenced by *rules* (min 1)."""
    longest = 1
    for rule in rules:
        for operand in (rule.left, rule.right):
            if getattr(operand, "type", None) == "indicator":
                longest = max(longest, int(operand.params.window))
    return longest


def custom_strategy_signals(
    close: pd.Series,
    entry_rules: List,
    entry_logic: str,
    exit_rules: List,
    exit_logic: str,
) -> pd.Series:
    """
    Generate a long-only (0/1) position series from custom entry/exit rules.

    State machine
    -------------
    * While flat: enter (1) when the combined entry condition is True.
    * While long: exit (0) when the combined exit condition is True.
    * Entry takes priority only when flat; exit only when long (same pattern as
      the built-in RSI / Bollinger strategies).

    The raw position is shifted one bar forward to prevent lookahead bias.
    """
    entry_bools = [_rule_boolean(close, r) for r in entry_rules]
    exit_bools = [_rule_boolean(close, r) for r in exit_rules]

    entry_signal = _combine(entry_bools, entry_logic, close.index)
    exit_signal = _combine(exit_bools, exit_logic, close.index)

    in_position = False
    raw: list[int] = []
    for enter, leave in zip(entry_signal.to_numpy(), exit_signal.to_numpy()):
        if not in_position and bool(enter):
            in_position = True
        elif in_position and bool(leave):
            in_position = False
        raw.append(1 if in_position else 0)

    position = pd.Series(raw, index=close.index, name="position")
    return position.shift(1).fillna(0).astype(int)
