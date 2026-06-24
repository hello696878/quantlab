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


# Transforms implemented in this commit. Others are skipped (logged).
_COMPUTE = {
    TransformType.RETURN: _f_return,
    TransformType.REALIZED_VOL: _f_realized_vol,
    TransformType.ROLLING_MAX: _f_rolling_max,
    TransformType.ROLLING_MIN: _f_rolling_min,
    TransformType.RATIO_TO_ROLLING_MAX: _f_ratio_to_rolling_max,
    TransformType.RATIO_TO_ROLLING_MIN: _f_ratio_to_rolling_min,
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

    if skipped:
        logger.warning(
            "build_feature_matrix: %d transform(s) not implemented yet, skipped: %s",
            len(skipped),
            ", ".join(skipped),
        )

    if feature_columns:
        out["is_warmup"] = out[feature_columns].isna().any(axis=1)
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
