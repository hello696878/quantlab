"""
Futures feature matrix builder (Phase 2 — commit 2).

Computes a leakage-safe, deterministic feature matrix from a Phase 1
**ratio-adjusted** continuous frame.  Commit 2 implements the basic price /
return / volatility / rolling features only:

    return_1, return_5, return_20, realized_vol_20,
    rolling_high_20, rolling_low_20,
    close_to_rolling_high_20, close_to_rolling_low_20

Transforms not yet implemented (RSI, ATR, MA gap, z-score, calendar, roll
metadata) are **skipped with a logged warning** — they land in later commits.

Discipline (Phase 2 plan §C.2):

* Trailing windows only (pandas ``.rolling`` / ``.pct_change``); a feature at
  ``t`` uses rows ``<= t`` only.
* Return/level features read ``*_adjusted`` and **require
  ``adjustment_method == "ratio"``** — Panama/raw inputs are rejected (ratio
  preserves held-contract % returns across roll seams).
* The input frame is never mutated (we work on a ``finalize_continuous`` copy).
* No fill / interpolation; NaNs occur only in warmup rows and are marked by
  ``is_warmup``.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd

from app.datastore.store import finalize_continuous
from app.features.spec import (
    DEFAULT_ES_FEATURES,
    FeatureError,
    FeatureSpec,
    TransformType,
    feature_config_hash,
)
from app.features.validation import validate_continuous_input, validate_feature_specs

logger = logging.getLogger(__name__)

_METADATA_FRONT = ["timestamp", "root_symbol", "active_contract"]
_METADATA_BACK = ["is_warmup", "source_adjustment_method", "feature_config_hash"]


# --------------------------------------------------------------------------- #
# Per-transform compute functions (pure; trailing only)
# --------------------------------------------------------------------------- #


def _f_return(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    n = spec.windows[0]
    return cdf[spec.input_columns[0]].pct_change(periods=n)


def _f_realized_vol(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    n = spec.windows[0]
    daily_returns = cdf[spec.input_columns[0]].pct_change(periods=1)
    vol = daily_returns.rolling(n).std()  # sample std (ddof=1)
    # Annualization is a convention, not a measured value (Phase 2 plan §C.5).
    if spec.params.get("annualize"):
        vol = vol * math.sqrt(spec.params.get("trading_days", 252))
    return vol


def _f_rolling_max(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    return cdf[spec.input_columns[0]].rolling(spec.windows[0]).max()


def _f_rolling_min(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    return cdf[spec.input_columns[0]].rolling(spec.windows[0]).min()


def _f_ratio_to_rolling_max(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    close = cdf[spec.input_columns[0]]
    rolling = cdf[spec.input_columns[1]].rolling(spec.windows[0]).max()
    return close / rolling - 1.0


def _f_ratio_to_rolling_min(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    close = cdf[spec.input_columns[0]]
    rolling = cdf[spec.input_columns[1]].rolling(spec.windows[0]).min()
    return close / rolling - 1.0


def _f_ma_gap(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    short, long = spec.windows[0], spec.windows[1]
    close = cdf[spec.input_columns[0]]
    ma_short = close.rolling(short).mean()
    ma_long = close.rolling(long).mean()
    return (ma_short - ma_long) / ma_long


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing (causal / trailing).

    Seed = simple mean of the first ``period`` *valid* values; thereafter
    ``avg_t = (avg_{t-1} * (period - 1) + value_t) / period``.  Leading NaNs
    (warmup) are preserved before the seed; only past values are ever used.
    """
    arr = values.to_numpy(dtype=float)
    n = len(arr)
    out = np.full(n, np.nan)
    run = 0
    seed = None
    for i in range(n):
        run = run + 1 if not np.isnan(arr[i]) else 0
        if run >= period:
            seed = i
            break
    if seed is None:
        return pd.Series(out, index=values.index)
    out[seed] = arr[seed - period + 1: seed + 1].mean()
    for t in range(seed + 1, n):
        out[t] = (out[t - 1] * (period - 1) + arr[t]) / period
    return pd.Series(out, index=values.index)


def _f_rsi(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    period = spec.params["period"]
    close = cdf[spec.input_columns[0]]
    change = close.diff()  # NaN on the first bar -> warmup propagates
    gain = change.clip(lower=0.0)
    loss = (-change).clip(lower=0.0)
    avg_gain = _wilder_smooth(gain, period)
    avg_loss = _wilder_smooth(loss, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        rsi = 100.0 - 100.0 / (1.0 + rs)
    # Zero-loss window (no down-moves) -> RSI 100; warmup rows (avg_loss NaN) stay NaN.
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    return rsi.where(avg_loss.notna())


def _f_atr(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    """Wilder ATR in adjusted price points. The first bar has no prior close, so
    it has no true range; ATR is Wilder-smoothed from the next bar onward.
    ``params['normalize'] == 'close'`` returns the scale-relative ATR/close.
    """
    period = spec.params["period"]
    high = cdf[spec.input_columns[0]]
    low = cdf[spec.input_columns[1]]
    close = cdf[spec.input_columns[2]]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    true_range = true_range.where(prev_close.notna())  # no prior close on the first bar
    atr = _wilder_smooth(true_range, period)
    if spec.params.get("normalize") == "close":
        return atr / close
    return atr


def _f_zscore(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    n = spec.windows[0]
    series = cdf[spec.input_columns[0]].astype(float)
    mean = series.rolling(n).mean()
    std = series.rolling(n).std()  # sample std (ddof=1)
    # Futures volume is contract-specific (NOT back-adjusted), so it can jump at
    # rolls; a window spanning a roll mixes two contracts' volume levels.
    with np.errstate(divide="ignore", invalid="ignore"):
        return (series - mean) / std


def _f_calendar_dow(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    # Weekday of the session timestamp: Monday=0 .. Friday=4. No one-hot encoding.
    return cdf[spec.input_columns[0]].dt.dayofweek.astype(float)


def _f_passthrough(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    # roll_flag carried through unchanged as 0.0/1.0; roll dates are NOT recomputed.
    return cdf[spec.input_columns[0]].astype(float)


def _f_days_since_flag(cdf: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    """Sessions since the most recent True flag at/before ``t`` (0 on flag rows).

    NaN before the first flag in the frame; resets to 0 at each flag, then
    increments by 1 each session.  Uses only past/current flags (causal).
    """
    flags = cdf[spec.input_columns[0]].astype(bool).to_numpy()
    n = len(flags)
    out = np.full(n, np.nan)
    last = None
    for i in range(n):
        if flags[i]:
            last = i
            out[i] = 0.0
        elif last is not None:
            out[i] = float(i - last)
    return pd.Series(out, index=cdf.index)


# Transforms implemented so far. Others are skipped (logged).
_COMPUTE = {
    TransformType.RETURN: _f_return,
    TransformType.REALIZED_VOL: _f_realized_vol,
    TransformType.ROLLING_MAX: _f_rolling_max,
    TransformType.ROLLING_MIN: _f_rolling_min,
    TransformType.RATIO_TO_ROLLING_MAX: _f_ratio_to_rolling_max,
    TransformType.RATIO_TO_ROLLING_MIN: _f_ratio_to_rolling_min,
    TransformType.MA_GAP: _f_ma_gap,
    TransformType.RSI: _f_rsi,
    TransformType.ATR: _f_atr,
    TransformType.ZSCORE: _f_zscore,
    TransformType.CALENDAR_DOW: _f_calendar_dow,
    TransformType.PASSTHROUGH: _f_passthrough,
    TransformType.DAYS_SINCE_FLAG: _f_days_since_flag,
}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def build_feature_matrix(
    continuous_df: pd.DataFrame,
    specs: list[FeatureSpec] = DEFAULT_ES_FEATURES,
    upstream_continuous_hash: Optional[str] = None,
    drop_warmup: bool = False,
) -> pd.DataFrame:
    """Build a deterministic, leakage-safe feature matrix.

    ``continuous_df`` must be a Phase 1 ratio-adjusted continuous frame.  Only the
    transforms implemented in this commit are computed; the rest are skipped with
    a warning.  The input is never mutated.
    """
    validate_continuous_input(continuous_df)
    validate_feature_specs(specs)

    # finalize_continuous returns a sorted, dtype-canonical *copy* (no mutation).
    cdf = finalize_continuous(continuous_df)

    adj_values = cdf["adjustment_method"].unique()
    if len(adj_values) != 1:
        raise FeatureError(
            f"continuous frame must have a single adjustment_method, got {list(adj_values)}"
        )
    frame_adjustment = str(adj_values[0])

    out = cdf.loc[:, _METADATA_FRONT].copy()
    feature_columns: list[str] = []
    warmup_columns: list[str] = []
    skipped: list[str] = []

    for spec in specs:
        compute = _COMPUTE.get(spec.transform)
        if compute is None:
            skipped.append(spec.name)
            continue
        if spec.required_adjustment is not None and frame_adjustment != spec.required_adjustment.value:
            raise FeatureError(
                f"feature {spec.name!r} requires {spec.required_adjustment.value!r} "
                f"adjustment but the continuous frame is {frame_adjustment!r}"
            )
        out[spec.output_name] = compute(cdf, spec)
        feature_columns.append(spec.output_name)
        # days_since_roll is NaN before the first roll *by design* — a documented
        # condition, not a trailing-window warmup — so it does not drive is_warmup.
        if spec.transform is not TransformType.DAYS_SINCE_FLAG:
            warmup_columns.append(spec.output_name)

    if skipped:
        logger.warning(
            "build_feature_matrix: %d transform(s) not implemented yet, skipped: %s",
            len(skipped),
            ", ".join(skipped),
        )

    if warmup_columns:
        out["is_warmup"] = out[warmup_columns].isna().any(axis=1)
    else:
        out["is_warmup"] = pd.Series(False, index=out.index, dtype=bool)
    out["source_adjustment_method"] = frame_adjustment
    out["feature_config_hash"] = feature_config_hash(
        specs, continuous_config_hash=upstream_continuous_hash
    )

    out = out[_METADATA_FRONT + feature_columns + _METADATA_BACK]
    if drop_warmup:
        out = out[~out["is_warmup"]]
    return out.reset_index(drop=True)
