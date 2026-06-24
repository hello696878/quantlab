"""
Tests for the baseline futures signal generator (Phase 3 — commit 3).

Deterministic per-row position generation; no timing shift, no PnL. Synthetic
data only, no network.
"""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.signals import (
    BaselineSignalConfig,
    SignalError,
    SignalMode,
    momentum_baseline_signal,
)

OUTPUT_COLUMNS = {
    "timestamp",
    "root_symbol",
    "active_contract",
    "signal",
    "target_position",
    "signal_state",
}


def _dataset(
    return_20,
    ma_gap,
    *,
    vol=None,
    atr=None,
    roll_flag=None,
    days_since_roll=None,
    is_warmup=None,
    is_trainable=None,
) -> pd.DataFrame:
    """Build a controlled supervised-style dataset (one ES contract)."""
    n = len(return_20)
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")

    def col(values, default):
        return values if values is not None else [default] * n

    return pd.DataFrame(
        {
            "timestamp": idx,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "feature__return_20": return_20,
            "feature__moving_average_gap_10_50": ma_gap,
            "feature__realized_vol_20": col(vol, 0.1),
            "feature__ATR_14_pct": col(atr, 0.01),
            "feature__roll_flag": col(roll_flag, 0.0),
            "feature__days_since_roll": col(days_since_roll, np.nan),
            "is_warmup": col(is_warmup, False),
            "is_trainable": col(is_trainable, True),
        }
    )


# --- config ---


def test_valid_config_creation():
    cfg = BaselineSignalConfig()
    assert cfg.mode is SignalMode.LONG_FLAT
    assert cfg.momentum_return_col == "feature__return_20"
    assert cfg.roll_avoidance_days == 0


def test_invalid_mode_raises():
    with pytest.raises(ValidationError):
        BaselineSignalConfig(mode="bogus")


def test_missing_required_columns_raises():
    df = _dataset([0.02], [0.01]).drop(columns=["feature__return_20"])
    with pytest.raises(SignalError):
        momentum_baseline_signal(df)


# --- output shape ---


def test_output_has_required_columns():
    out = momentum_baseline_signal(_dataset([0.02, -0.01], [0.01, -0.02]))
    assert OUTPUT_COLUMNS.issubset(out.columns)


def test_no_pnl_columns_produced():
    out = momentum_baseline_signal(_dataset([0.02], [0.01]))
    assert set(out.columns) == OUTPUT_COLUMNS  # exactly the signal columns, no PnL/equity


# --- long/flat and long/short rules ---


def test_long_flat_one_for_positive_momentum_else_zero():
    df = _dataset([0.02, -0.01, 0.0, 0.03], [0.01, -0.02, 0.0, 0.02])
    out = momentum_baseline_signal(df, BaselineSignalConfig(mode=SignalMode.LONG_FLAT))
    assert list(out["target_position"]) == [1, 0, 0, 1]
    assert list(out["signal"]) == [1, 0, 0, 1]


def test_long_short_plus_minus_zero():
    df = _dataset([0.02, -0.02, 0.0], [0.01, -0.01, 0.0])
    out = momentum_baseline_signal(df, BaselineSignalConfig(mode="long_short"))
    assert list(out["target_position"]) == [1, -1, 0]
    assert list(out["signal_state"]) == ["long", "short", "flat"]


# --- flat conditions ---


def test_warmup_rows_always_flat():
    df = _dataset([0.02, 0.02], [0.01, 0.01], is_warmup=[True, False])
    out = momentum_baseline_signal(df)
    assert out["target_position"].iloc[0] == 0
    assert out["signal_state"].iloc[0] == "warmup"
    assert out["target_position"].iloc[1] == 1


def test_non_trainable_rows_always_flat():
    df = _dataset([0.02, 0.02], [0.01, 0.01], is_trainable=[False, True])
    out = momentum_baseline_signal(df)
    assert out["target_position"].iloc[0] == 0
    assert out["signal_state"].iloc[0] == "not_trainable"
    assert out["target_position"].iloc[1] == 1


def test_volatility_filter_blocks_trades():
    cfg = BaselineSignalConfig(max_realized_vol=0.2)
    df = _dataset([0.02, 0.02], [0.01, 0.01], vol=[0.5, 0.1])
    out = momentum_baseline_signal(df, cfg)
    assert list(out["target_position"]) == [0, 1]


def test_atr_filter_blocks_trades():
    cfg = BaselineSignalConfig(max_atr_pct=0.02)
    df = _dataset([0.02, 0.02], [0.01, 0.01], atr=[0.05, 0.01])
    out = momentum_baseline_signal(df, cfg)
    assert list(out["target_position"]) == [0, 1]


def test_roll_flag_row_is_flat():
    df = _dataset([0.02, 0.02], [0.01, 0.01], roll_flag=[1.0, 0.0])
    out = momentum_baseline_signal(df)
    assert out["target_position"].iloc[0] == 0
    assert out["signal_state"].iloc[0] == "roll_avoidance"
    assert out["target_position"].iloc[1] == 1


def test_days_since_roll_within_window_is_flat():
    cfg = BaselineSignalConfig(roll_avoidance_days=3)
    df = _dataset([0.02] * 4, [0.01] * 4, days_since_roll=[0.0, 2.0, 3.0, 4.0])
    out = momentum_baseline_signal(df, cfg)
    assert list(out["target_position"]) == [0, 0, 0, 1]  # dsr<=3 flat, dsr=4 long


def test_days_since_roll_nan_uses_only_current_past():
    cfg = BaselineSignalConfig(roll_avoidance_days=3)
    df = _dataset([0.02, 0.02], [0.01, 0.01], days_since_roll=[np.nan, np.nan])
    out = momentum_baseline_signal(df, cfg)
    assert list(out["target_position"]) == [1, 1]  # NaN dsr -> not in window -> long


# --- timing / determinism / purity ---


def test_no_position_shift_applied():
    # only the middle row meets the long condition -> 1 on THAT row, not shifted.
    df = _dataset([0.0, 0.02, 0.0], [0.0, 0.01, 0.0])
    out = momentum_baseline_signal(df)
    assert list(out["target_position"]) == [0, 1, 0]


def test_does_not_mutate_input():
    df = _dataset([0.02, -0.01], [0.01, -0.02])
    before = df.copy(deep=True)
    momentum_baseline_signal(df)
    pd.testing.assert_frame_equal(df, before)


def test_deterministic_output():
    df = _dataset([0.02, -0.01, 0.0], [0.01, -0.02, 0.0])
    pd.testing.assert_frame_equal(
        momentum_baseline_signal(df), momentum_baseline_signal(df)
    )
