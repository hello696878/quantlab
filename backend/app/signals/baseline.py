"""
Deterministic baseline futures signal generator (Phase 3 — commit 3).

A non-ML momentum baseline that consumes a Phase 3 supervised dataset (the
``build_supervised_dataset`` output, with ``feature__*`` columns + ``is_warmup`` /
``is_trainable``) and emits a per-row target position.

Discipline:

* Pure per-row function of features **at ``t``** — no shift, no rolling, no future
  information.  The ``t+1`` execution shift is applied later by the backtest, NOT
  here.
* Warmup and non-trainable rows are always flat (position 0).
* Roll avoidance uses only ``roll_flag`` / ``days_since_roll`` at ``t`` (both
  causal Phase 2 features); roll dates are never recomputed.
* Deterministic; the input dataframe is never mutated; no PnL is computed.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

_KEY_COLUMNS = ["timestamp", "root_symbol", "active_contract"]


class SignalMode(str, Enum):
    LONG_FLAT = "long_flat"
    LONG_SHORT = "long_short"


class SignalError(ValueError):
    """Raised on invalid signal config or missing required dataset columns."""


class BaselineSignalConfig(BaseModel):
    """Strict, frozen config for the momentum baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: SignalMode = SignalMode.LONG_FLAT
    momentum_return_col: str = "feature__return_20"
    ma_gap_col: str = "feature__moving_average_gap_10_50"
    vol_col: str = "feature__realized_vol_20"
    atr_pct_col: str = "feature__ATR_14_pct"
    roll_flag_col: str = "feature__roll_flag"
    days_since_roll_col: str = "feature__days_since_roll"
    min_return_threshold: float = Field(default=0.0, ge=0.0)
    min_ma_gap_threshold: float = Field(default=0.0, ge=0.0)
    max_realized_vol: Optional[float] = None
    max_atr_pct: Optional[float] = None
    roll_avoidance_days: int = Field(default=0, ge=0)
    warmup_col: str = "is_warmup"
    trainable_col: str = "is_trainable"

    @field_validator(
        "momentum_return_col", "ma_gap_col", "vol_col", "atr_pct_col",
        "roll_flag_col", "days_since_roll_col", "warmup_col", "trainable_col",
    )
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("column names must be non-empty")
        return v


def momentum_baseline_signal(
    dataset_df: pd.DataFrame,
    config: BaselineSignalConfig = BaselineSignalConfig(),
) -> pd.DataFrame:
    """Compute the deterministic baseline target position per row (no shift, no PnL)."""
    cfg = config

    required = list(_KEY_COLUMNS) + [
        cfg.momentum_return_col,
        cfg.ma_gap_col,
        cfg.roll_flag_col,
        cfg.days_since_roll_col,
        cfg.warmup_col,
        cfg.trainable_col,
    ]
    if cfg.max_realized_vol is not None:
        required.append(cfg.vol_col)
    if cfg.max_atr_pct is not None:
        required.append(cfg.atr_pct_col)
    missing = [c for c in required if c not in dataset_df.columns]
    if missing:
        raise SignalError(f"dataset is missing required columns: {missing}")

    df = dataset_df  # read-only; never mutated
    returns = df[cfg.momentum_return_col]
    ma_gap = df[cfg.ma_gap_col]
    is_warmup = df[cfg.warmup_col].astype(bool)
    is_trainable = df[cfg.trainable_col].astype(bool)

    # Filters (NaN comparisons are False -> they block, which is the safe default).
    vol_ok = pd.Series(True, index=df.index)
    if cfg.max_realized_vol is not None:
        vol_ok = df[cfg.vol_col] <= cfg.max_realized_vol
    atr_ok = pd.Series(True, index=df.index)
    if cfg.max_atr_pct is not None:
        atr_ok = df[cfg.atr_pct_col] <= cfg.max_atr_pct

    # Roll avoidance — only roll metadata at/before t (causal Phase 2 features).
    roll_flag = df[cfg.roll_flag_col].fillna(0.0) > 0
    days_since_roll = df[cfg.days_since_roll_col]
    in_roll_window = days_since_roll.notna() & (days_since_roll <= cfg.roll_avoidance_days)
    avoid = roll_flag | in_roll_window

    eligible = is_trainable & (~is_warmup) & (~avoid) & vol_ok & atr_ok
    long_condition = eligible & (returns > cfg.min_return_threshold) & (ma_gap > cfg.min_ma_gap_threshold)
    short_condition = eligible & (returns < -cfg.min_return_threshold) & (ma_gap < -cfg.min_ma_gap_threshold)

    target = pd.Series(0, index=df.index, dtype="int64")
    target = target.mask(long_condition, 1)
    if cfg.mode is SignalMode.LONG_SHORT:
        target = target.mask(short_condition, -1)

    # Explanatory state (priority high -> low).
    conditions = [is_warmup.to_numpy(), (~is_trainable).to_numpy(), avoid.to_numpy(),
                  long_condition.to_numpy()]
    choices = ["warmup", "not_trainable", "roll_avoidance", "long"]
    if cfg.mode is SignalMode.LONG_SHORT:
        conditions.append(short_condition.to_numpy())
        choices.append("short")
    signal_state = np.select(conditions, choices, default="flat")

    out = pd.DataFrame(
        {
            "timestamp": df["timestamp"].to_numpy(),
            "root_symbol": df["root_symbol"].to_numpy(),
            "active_contract": df["active_contract"].to_numpy(),
            "signal": target.to_numpy(),
            "target_position": target.to_numpy(),
            "signal_state": signal_state,
        }
    )
    return out.reset_index(drop=True)
