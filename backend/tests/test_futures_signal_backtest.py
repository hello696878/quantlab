"""
Tests for the baseline futures signal generator (Phase 3 — commit 3).

Deterministic per-row position generation; no timing shift, no PnL. Synthetic
data only, no network.
"""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.instruments import get_instrument
from app.datastore.store import CONTINUOUS_COLUMNS
from app.features import build_feature_matrix
from app.labels import build_label_matrix, build_supervised_dataset
from app.signals import (
    BaselineSignalConfig,
    SignalError,
    SignalMode,
    momentum_baseline_signal,
)
from app.futures_backtest import FuturesBacktestError, run_futures_backtest

ES = get_instrument("ES")

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


# --------------------------------------------------------------------------- #
# Commit 4 — futures-aware vectorized backtest adapter
# --------------------------------------------------------------------------- #


def _cont(closes_adj, *, close_raw=None, open_raw=None, roll_flag=None, adjustment="ratio") -> pd.DataFrame:
    """Minimal ratio continuous frame with explicit adjusted / raw prices."""
    n = len(closes_adj)
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    ca = np.asarray(closes_adj, dtype=float)
    cr = np.asarray(close_raw, dtype=float) if close_raw is not None else ca.copy()
    oraw = np.asarray(open_raw, dtype=float) if open_raw is not None else cr.copy()
    rf = roll_flag if roll_flag is not None else [False] * n
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "open_raw": oraw,
            "high_raw": ca + 5.0,
            "low_raw": ca - 5.0,
            "close_raw": cr,
            "volume": 1000,
            "open_interest": 2000.0,
            "adjustment_method": adjustment,
            "adjustment_factor": 1.0,
            "open_adjusted": ca,
            "high_adjusted": ca + 5.0,
            "low_adjusted": ca - 5.0,
            "close_adjusted": ca,
            "roll_flag": rf,
            "roll_reason": "",
        }
    )
    return df[CONTINUOUS_COLUMNS]


def _signal(df: pd.DataFrame, positions) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": df["timestamp"].to_numpy(),
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "target_position": np.asarray(positions, dtype=float),
        }
    )


# --- timing ---


def test_first_effective_position_is_zero():
    res = run_futures_backtest(_cont([100, 101, 102, 103]), _signal(_cont([100, 101, 102, 103]), [1, 1, 1, 1]), ES, transaction_cost_bps=0)
    assert res.frame["effective_position"].iloc[0] == 0.0


def test_effective_position_is_target_shifted():
    df = _cont([100, 101, 102, 103, 104])
    res = run_futures_backtest(df, _signal(df, [0, 1, 1, 0, 1]), ES, transaction_cost_bps=0)
    expected = pd.Series([0, 1, 1, 0, 1], dtype=float).shift(1).fillna(0.0)
    np.testing.assert_array_equal(res.frame["effective_position"].to_numpy(), expected.to_numpy())


def test_no_same_bar_execution_leakage():
    df = _cont([100, 101, 102, 103, 104])
    res = run_futures_backtest(df, _signal(df, [0, 0, 1, 1, 1]), ES, transaction_cost_bps=0)
    assert res.frame["effective_position"].iloc[2] == 0.0  # target[2]=1 not used same bar
    assert res.frame["effective_position"].iloc[3] == 1.0  # = target[2]
    assert res.frame["strategy_return"].iloc[2] == 0.0


# --- return / PnL ---


def test_strategy_return_uses_close_adjusted_pct_change():
    df = _cont([100, 110, 121, 133.1])
    res = run_futures_backtest(df, _signal(df, [1, 1, 1, 1]), ES, transaction_cost_bps=0)
    ca = pd.Series([100, 110, 121, 133.1], dtype=float)
    eff = pd.Series([1, 1, 1, 1], dtype=float).shift(1).fillna(0.0)
    np.testing.assert_allclose(
        res.frame["strategy_return"].to_numpy(), (eff * ca.pct_change().fillna(0.0)).to_numpy()
    )


def test_raw_close_gap_does_not_create_fake_pnl():
    # close_adjusted is smooth; close_raw gaps at the roll bar; hold long across.
    df = _cont([100, 101, 102, 103], close_raw=[100, 101, 5102, 5103], roll_flag=[False, False, True, False])
    res = run_futures_backtest(df, _signal(df, [1, 1, 1, 1]), ES, transaction_cost_bps=0, include_roll_cost=False)
    assert res.frame["strategy_return"].iloc[2] == pytest.approx(102 / 101 - 1)  # adjusted, not raw gap
    assert abs(res.frame["strategy_return"].iloc[2]) < 0.05  # not a ~50x raw spike


def test_flat_position_zero_return_and_flat_equity():
    df = _cont([100, 110, 90, 105])
    res = run_futures_backtest(df, _signal(df, [0, 0, 0, 0]), ES)
    assert (res.frame["strategy_return"] == 0.0).all()
    assert (res.frame["net_strategy_return"] == 0.0).all()
    assert np.allclose(res.frame["equity"], 10_000.0)


# --- costs ---


def test_cost_only_on_position_change():
    df = _cont([100, 101, 102, 103, 104])
    res = run_futures_backtest(df, _signal(df, [1, 1, 1, 1, 1]), ES, transaction_cost_bps=10, include_roll_cost=False)
    tc = res.frame["transaction_cost"]
    assert tc.iloc[1] > 0  # entry 0->1
    assert tc.iloc[2] == pytest.approx(0.0)  # constant hold
    assert tc.iloc[3] == pytest.approx(0.0)
    assert tc.iloc[4] == pytest.approx(0.0)


def test_entry_and_exit_both_charge_cost():
    df = _cont([100, 101, 102, 103])
    res = run_futures_backtest(df, _signal(df, [1, 1, 0, 0]), ES, transaction_cost_bps=10, include_roll_cost=False)
    tc = res.frame["transaction_cost"]
    assert tc.iloc[1] > 0   # entry 0->1
    assert tc.iloc[2] == pytest.approx(0.0)  # hold
    assert tc.iloc[3] > 0   # exit 1->0


def test_higher_cost_bps_reduces_equity():
    df = _cont([100, 101, 100, 101, 100, 101])
    sig = _signal(df, [1, 0, 1, 0, 1, 0])  # frequent trades
    low = run_futures_backtest(df, sig, ES, transaction_cost_bps=0).metrics["final_equity"]
    high = run_futures_backtest(df, sig, ES, transaction_cost_bps=100).metrics["final_equity"]
    assert high < low


def test_roll_cost_only_when_held_and_enabled():
    df = _cont([100, 101, 102, 103], roll_flag=[False, False, True, False])
    sig = _signal(df, [1, 1, 1, 1])  # held across the roll bar (index 2)
    on = run_futures_backtest(df, sig, ES, transaction_cost_bps=50, include_roll_cost=True)
    off = run_futures_backtest(df, sig, ES, transaction_cost_bps=50, include_roll_cost=False)
    assert on.frame["transaction_cost"].iloc[2] > off.frame["transaction_cost"].iloc[2]
    assert off.frame["transaction_cost"].iloc[2] == pytest.approx(0.0)  # no change, no roll cost


def test_no_roll_cost_if_flat_across_roll():
    df = _cont([100, 101, 102, 103], roll_flag=[False, False, True, False])
    res = run_futures_backtest(df, _signal(df, [0, 0, 0, 0]), ES, transaction_cost_bps=50, include_roll_cost=True)
    assert res.frame["transaction_cost"].iloc[2] == pytest.approx(0.0)


def test_cost_metadata_documents_assumptions():
    df = _cont([100, 101])
    res = run_futures_backtest(df, _signal(df, [1, 1]), ES)  # derived from spec
    assert res.cost_metadata["source"] == "derived_from_commission_slippage"
    assert res.cost_metadata["effective_cost_bps"] > 0
    assert res.cost_metadata["zero_cost"] is False


# --- input safety ---


def test_continuous_and_signal_not_mutated():
    df = _cont([100, 101, 102])
    sig = _signal(df, [1, 1, 1])
    df_before = df.copy(deep=True)
    sig_before = sig.copy(deep=True)
    run_futures_backtest(df, sig, ES)
    pd.testing.assert_frame_equal(df, df_before)
    pd.testing.assert_frame_equal(sig, sig_before)


def test_missing_columns_raise():
    df = _cont([100, 101, 102])
    sig = _signal(df, [1, 1, 1])
    with pytest.raises(FuturesBacktestError):
        run_futures_backtest(df.drop(columns=["close_adjusted"]), sig, ES)
    with pytest.raises(FuturesBacktestError):
        run_futures_backtest(df, sig.drop(columns=["target_position"]), ES)


def test_panama_continuous_rejected():
    df = _cont([100, 101, 102], adjustment="panama")
    with pytest.raises(FuturesBacktestError):
        run_futures_backtest(df, _signal(df, [1, 1, 1]), ES)


def test_backtest_deterministic():
    df = _cont([100, 101, 100, 102])
    sig = _signal(df, [1, 0, 1, 1])
    r1 = run_futures_backtest(df, sig, ES, transaction_cost_bps=10)
    r2 = run_futures_backtest(df, sig, ES, transaction_cost_bps=10)
    pd.testing.assert_frame_equal(r1.frame, r2.frame)


def test_output_has_required_columns():
    df = _cont([100, 101, 102])
    res = run_futures_backtest(df, _signal(df, [1, 1, 1]), ES)
    required = {
        "timestamp", "root_symbol", "active_contract", "target_position",
        "effective_position", "close_adjusted", "strategy_return",
        "transaction_cost", "net_strategy_return", "equity", "roll_flag",
        "raw_execution_price",
    }
    assert required.issubset(res.frame.columns)


# --- integration: full pipeline, no labels/ML required by the backtest ---


def test_integration_with_baseline_signal_and_continuous():
    n = 80
    idx = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    closes = np.array([5000.0 + 2.0 * i + ((-1) ** i) * 3.0 for i in range(n)])
    df = pd.DataFrame(
        {
            "timestamp": idx, "root_symbol": "ES", "active_contract": "ESH24",
            "open_raw": closes, "high_raw": closes + 5.0, "low_raw": closes - 5.0, "close_raw": closes,
            "volume": np.array([1000 + 10 * i for i in range(n)]), "open_interest": 2000.0,
            "adjustment_method": "ratio", "adjustment_factor": 1.0,
            "open_adjusted": closes, "high_adjusted": closes + 5.0,
            "low_adjusted": closes - 5.0, "close_adjusted": closes,
            "roll_flag": False, "roll_reason": "",
        }
    )[CONTINUOUS_COLUMNS]
    feat = build_feature_matrix(df)
    lab = build_label_matrix(df, feature_df=feat)
    dataset = build_supervised_dataset(feat, lab)
    sig = momentum_baseline_signal(dataset, BaselineSignalConfig(mode="long_short"))
    res = run_futures_backtest(df, sig, ES)  # backtest needs no labels / no ML
    assert len(res.frame) == n
    assert {"equity", "net_strategy_return", "effective_position"}.issubset(res.frame.columns)
    assert res.frame["effective_position"].iloc[0] == 0.0
