"""
Futures label matrix builder (Phase 3 — commit 1).

Computes leakage-safe supervised labels from a Phase 1 **ratio-adjusted**
continuous frame.  Commit 1 implements the basic return-based labels:

    forward_return_1, forward_return_5, direction_1, direction_5,
    volatility_adjusted_return_5

Alignment (Phase 3 plan §D.4, ``L = execution_lag`` default 1):

    forward_return_h(t) = close_adjusted[t+L+h] / close_adjusted[t+L] - 1

so the label is exactly what acting on ``signal(t)`` earns when executed at
``t+1`` (``open_{t+1}``).  Labels are the only artifact allowed to read future
prices; the last ``L + h`` rows have no forward window and are left NaN.

* Return labels read ``*_adjusted`` and **require ``adjustment_method == "ratio"``**
  (Panama/raw frames are rejected) — ratio preserves held-contract returns across
  roll seams, so labels carry no fake roll PnL.
* The volatility denominator of ``vol_adjusted_return`` comes from the **trailing**
  feature at ``t`` (``feature_df``), never from the future.
* Input frames are never mutated.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from app.datastore.store import finalize_continuous
from app.features.validation import validate_continuous_input
from app.labels.spec import (
    DEFAULT_ES_LABELS,
    LabelError,
    LabelSpec,
    LabelType,
    ReturnType,
    label_config_hash,
)

_METADATA = ["timestamp", "root_symbol", "active_contract"]


def _forward_return(price: pd.Series, lag: int, horizon: int, return_type: ReturnType) -> pd.Series:
    """price[t+lag+horizon] / price[t+lag] - 1 (or log). Trailing-shift -> NaN tail."""
    forward = price.shift(-(lag + horizon))
    base = price.shift(-lag)
    if return_type is ReturnType.LOG:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.log(forward / base)
    return forward / base - 1.0


def _direction(forward_return: pd.Series, threshold: float) -> pd.Series:
    out = pd.Series(np.nan, index=forward_return.index, dtype=float)
    out = out.mask(forward_return > threshold, 1.0)
    out = out.mask(forward_return < -threshold, -1.0)
    out = out.mask((forward_return >= -threshold) & (forward_return <= threshold), 0.0)
    return out  # NaN where forward_return is NaN (no forward window)


def build_label_matrix(
    continuous_df: pd.DataFrame,
    specs: list[LabelSpec] = DEFAULT_ES_LABELS,
    feature_df: Optional[pd.DataFrame] = None,
    upstream_feature_hash: Optional[str] = None,
) -> pd.DataFrame:
    """Build a leakage-safe label matrix from a ratio-adjusted continuous frame.

    ``feature_df`` (the Phase 2 feature matrix) is required when any spec is a
    ``vol_adjusted_return`` (its trailing volatility denominator).  Inputs are
    never mutated.
    """
    validate_continuous_input(continuous_df)

    names = [s.name for s in specs]
    if len(names) != len(set(names)):
        raise LabelError(f"duplicate label names in specs: {names}")
    outputs = [s.output_column for s in specs]
    if len(outputs) != len(set(outputs)):
        raise LabelError(f"duplicate output_columns in specs: {outputs}")

    # finalize_continuous returns a sorted, dtype-canonical *copy* (no mutation).
    cont = finalize_continuous(continuous_df)

    adj_values = cont["adjustment_method"].unique()
    if len(adj_values) != 1:
        raise LabelError(
            f"continuous frame must have a single adjustment_method, got {list(adj_values)}"
        )
    frame_adjustment = str(adj_values[0])

    out = cont.loc[:, _METADATA].copy()

    for spec in specs:
        if spec.required_adjustment is not None and frame_adjustment != spec.required_adjustment.value:
            raise LabelError(
                f"label {spec.name!r} requires {spec.required_adjustment.value!r} "
                f"adjustment but the continuous frame is {frame_adjustment!r}"
            )
        price = cont[spec.input_column].astype(float)
        lag, horizon = spec.execution_lag, spec.horizon

        if spec.label_type is LabelType.FORWARD_RETURN:
            column = _forward_return(price, lag, horizon, spec.return_type)
        elif spec.label_type is LabelType.DIRECTION:
            simple = _forward_return(price, lag, horizon, ReturnType.SIMPLE)
            column = _direction(simple, spec.threshold)
        elif spec.label_type is LabelType.VOL_ADJUSTED_RETURN:
            if feature_df is None:
                raise LabelError(f"label {spec.name!r} requires feature_df (trailing volatility)")
            vol_column = spec.params["vol_column"]
            if vol_column not in feature_df.columns:
                raise LabelError(
                    f"label {spec.name!r} needs {vol_column!r} but it is not in feature_df"
                )
            # Align the trailing vol feature to the continuous timestamps (never future).
            vol = (
                feature_df.set_index("timestamp")[vol_column]
                .reindex(cont["timestamp"])
                .to_numpy()
            )
            simple = _forward_return(price, lag, horizon, ReturnType.SIMPLE)
            with np.errstate(divide="ignore", invalid="ignore"):
                column = simple / pd.Series(vol, index=cont.index)
        else:  # pragma: no cover - guarded by the enum
            raise LabelError(f"unsupported label_type {spec.label_type!r}")

        out[spec.output_column] = column

    out["label_config_hash"] = label_config_hash(specs, upstream_feature_hash=upstream_feature_hash)
    return out.reset_index(drop=True)
