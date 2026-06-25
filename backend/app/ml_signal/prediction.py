"""
Prediction-to-signal adapter for the ML Signal Lab (Phase 4 — commit 3).

Turns a :class:`~app.ml_signal.training.TrainedModel` into an **out-of-sample**
``target_position`` signal, aligned at timestamp ``t`` and **never shifted** — the
Phase 3 backtest still owns execution timing
(``effective_position = target_position.shift(1)``).

* ``predict_model`` — features-only OOS predictions aligned to dataset rows.
* ``prediction_to_signal`` — applies the spec's threshold rule + optional Phase
  3-style warmup/trainable/roll/volatility filters to emit ``target_position`` and
  an explanatory ``signal_state``.

No PnL, no equity, no backtest call here.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from app.ml_signal.spec import MlSignalError, ModelSpec, SignalMode, ThresholdRule
from app.ml_signal.training import TrainedModel, select_features

_KEY_COLUMNS = ["timestamp", "root_symbol", "active_contract"]


class PredictionSignalConfig(BaseModel):
    """Strict, frozen filter config for ``prediction_to_signal``.

    Threshold rule / thresholds / mode come from the ``ModelSpec``; this config
    only governs the optional Phase 3-style row-``t`` gates (all causal)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate_warmup: bool = True
    require_trainable: bool = True
    enable_roll_filter: bool = False
    roll_avoidance_days: int = Field(default=0, ge=0)
    max_realized_vol: Optional[float] = None
    max_atr_pct: Optional[float] = None
    warmup_col: str = "is_warmup"
    trainable_col: str = "is_trainable"
    roll_flag_col: str = "feature__roll_flag"
    days_since_roll_col: str = "feature__days_since_roll"
    vol_col: str = "feature__realized_vol_20"
    atr_pct_col: str = "feature__ATR_14_pct"


def _require_key_columns(df: pd.DataFrame) -> None:
    missing = [c for c in _KEY_COLUMNS if c not in df.columns]
    if missing:
        raise MlSignalError(f"dataset_df is missing required columns: {missing}")


def _select_window(df: pd.DataFrame, start, end, time_col: str = "timestamp") -> pd.DataFrame:
    """Inclusive date-window slice preserving row order; never mutates ``df``."""
    if start is None and end is None:
        return df
    days = pd.to_datetime(df[time_col])
    if getattr(days.dt, "tz", None) is not None:
        days = days.dt.tz_convert("UTC").dt.tz_localize(None)
    days = days.dt.normalize()
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= days >= pd.Timestamp(start)
    if end is not None:
        mask &= days <= pd.Timestamp(end)
    return df.loc[mask]


def _predict_on_window(trained_model: TrainedModel, window: pd.DataFrame):
    X = select_features(window, trained_model.feature_columns)  # rejects label__ / missing
    model = trained_model.model
    pred = np.asarray(model.predict(X), dtype=float)
    proba = np.asarray(model.predict_proba(X), dtype=float) if model.is_classifier else None
    return pred, proba


def predict_model(
    trained_model: TrainedModel,
    dataset_df: pd.DataFrame,
    *,
    start=None,
    end=None,
) -> pd.DataFrame:
    """Out-of-sample predictions aligned to dataset rows (timestamp ``t``).

    Uses only ``trained_model.feature_columns``; never mutates ``dataset_df``;
    applies no shift and computes no PnL."""
    _require_key_columns(dataset_df)
    window = _select_window(dataset_df, start, end).reset_index(drop=True)
    pred, proba = _predict_on_window(trained_model, window)
    out = pd.DataFrame(
        {
            "timestamp": window["timestamp"].to_numpy(),
            "root_symbol": window["root_symbol"].to_numpy(),
            "active_contract": window["active_contract"].to_numpy(),
            "prediction": pred,
        }
    )
    if proba is not None:
        out["prediction_proba"] = proba
    return out


def _threshold_to_target(spec: ModelSpec, is_classifier: bool, pred: np.ndarray,
                         proba: Optional[np.ndarray]):
    """Map predictions to ``target_position`` per the spec's threshold rule.

    Long takes precedence over short when thresholds overlap.  NaN scores compare
    False on both sides and therefore stay flat."""
    n = pred.shape[0]
    if spec.threshold_rule is ThresholdRule.PROB_THRESHOLD:
        if not is_classifier or proba is None:
            raise MlSignalError(
                "threshold_rule='prob_threshold' requires a classifier with predict_proba"
            )
        score = proba
        long_cond = score >= spec.long_threshold
        short_cond = score <= spec.short_threshold
    elif spec.threshold_rule is ThresholdRule.RETURN_THRESHOLD:
        score = pred
        long_cond = score >= spec.long_threshold
        short_cond = score <= -spec.short_threshold
    else:  # pragma: no cover - enum is exhaustive
        raise MlSignalError(f"unsupported threshold_rule: {spec.threshold_rule!r}")

    target = np.zeros(n, dtype=float)
    state = np.full(n, "flat", dtype=object)
    target[long_cond] = 1.0
    state[long_cond] = "long"
    if spec.signal_mode is SignalMode.LONG_SHORT:
        short_only = short_cond & ~long_cond
        target[short_only] = -1.0
        state[short_only] = "short"
    return target, state


def _apply_filters(cfg: PredictionSignalConfig, window: pd.DataFrame,
                   target: np.ndarray, state: np.ndarray):
    """Gate positions to flat using only row-``t`` information.  Priority (high to
    low): warmup, not_trainable, roll_avoidance, vol_filter, atr_filter."""
    n = target.shape[0]
    masks: list[np.ndarray] = []
    labels: list[str] = []

    if cfg.gate_warmup and cfg.warmup_col in window.columns:
        masks.append(window[cfg.warmup_col].fillna(False).astype(bool).to_numpy())
        labels.append("warmup")
    if cfg.require_trainable and cfg.trainable_col in window.columns:
        masks.append(~window[cfg.trainable_col].astype(bool).to_numpy())
        labels.append("not_trainable")
    if cfg.enable_roll_filter:
        for c in (cfg.roll_flag_col, cfg.days_since_roll_col):
            if c not in window.columns:
                raise MlSignalError(f"roll filter requires column {c!r}")
        roll_flag = window[cfg.roll_flag_col].fillna(False).astype(bool).to_numpy()
        dsr = window[cfg.days_since_roll_col].to_numpy(dtype=float)
        in_window = ~np.isnan(dsr) & (dsr <= cfg.roll_avoidance_days)
        masks.append(roll_flag | in_window)
        labels.append("roll_avoidance")
    if cfg.max_realized_vol is not None:
        if cfg.vol_col not in window.columns:
            raise MlSignalError(f"volatility filter requires column {cfg.vol_col!r}")
        vol = window[cfg.vol_col].to_numpy(dtype=float)
        masks.append(~(vol <= cfg.max_realized_vol))  # NaN -> blocked (conservative)
        labels.append("vol_filter")
    if cfg.max_atr_pct is not None:
        if cfg.atr_pct_col not in window.columns:
            raise MlSignalError(f"ATR filter requires column {cfg.atr_pct_col!r}")
        atr = window[cfg.atr_pct_col].to_numpy(dtype=float)
        masks.append(~(atr <= cfg.max_atr_pct))
        labels.append("atr_filter")

    if not masks:
        return target, state

    gate_any = np.zeros(n, dtype=bool)
    for m in masks:
        gate_any |= m
    target = target.copy()
    state = state.copy()
    target[gate_any] = 0.0
    # apply lowest-priority first so the highest-priority reason wins
    for m, label in reversed(list(zip(masks, labels))):
        state[m] = label
    return target, state


def prediction_to_signal(
    trained_model: TrainedModel,
    dataset_df: pd.DataFrame,
    *,
    start=None,
    end=None,
    config: Optional[PredictionSignalConfig] = None,
) -> pd.DataFrame:
    """Emit a ``target_position`` signal at timestamp ``t`` (unshifted).

    Threshold rule / thresholds / mode come from ``trained_model.spec``; ``config``
    governs the optional warmup/trainable/roll/volatility gates.  ``dataset_df`` is
    never mutated and no PnL/backtest is computed."""
    cfg = config or PredictionSignalConfig()
    _require_key_columns(dataset_df)
    window = _select_window(dataset_df, start, end).reset_index(drop=True)
    pred, proba = _predict_on_window(trained_model, window)

    target, state = _threshold_to_target(
        trained_model.spec, trained_model.model.is_classifier, pred, proba
    )
    target, state = _apply_filters(cfg, window, target, state)

    out = pd.DataFrame(
        {
            "timestamp": window["timestamp"].to_numpy(),
            "root_symbol": window["root_symbol"].to_numpy(),
            "active_contract": window["active_contract"].to_numpy(),
            "prediction": pred,
        }
    )
    if proba is not None:
        out["prediction_proba"] = proba
    out[trained_model.spec.output_signal_col] = target
    out["signal_state"] = state
    return out
