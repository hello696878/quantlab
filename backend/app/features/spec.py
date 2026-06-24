"""
Feature specification + config hashing (Phase 2 — commit 1).

Scope is deliberately narrow: the *declarative config* for futures features and
its reproducibility hash.  **No feature math** lives here (that arrives in later
commits) — this module only defines what a feature is, validates the spec, and
hashes a spec set.

A :class:`FeatureSpec` is a frozen, strict (``extra="forbid"``) Pydantic model so
a malformed feature definition raises rather than silently loading — mirroring
the Phase 1 instrument-spec discipline.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.instruments import AdjustmentMethod


class TransformType(str, Enum):
    RETURN = "return"
    REALIZED_VOL = "realized_vol"
    ROLLING_MAX = "rolling_max"
    ROLLING_MIN = "rolling_min"
    RATIO_TO_ROLLING_MAX = "ratio_to_rolling_max"
    RATIO_TO_ROLLING_MIN = "ratio_to_rolling_min"
    MA_GAP = "ma_gap"
    RSI = "rsi"
    ATR = "atr"
    ZSCORE = "zscore"
    CALENDAR_DOW = "calendar_dow"
    PASSTHROUGH = "passthrough"
    DAYS_SINCE_FLAG = "days_since_flag"


class PriceSpace(str, Enum):
    ADJUSTED = "adjusted"   # ratio/Panama-adjusted continuous prices
    RAW = "raw"             # raw held-contract prices (execution reference)
    NONE = "none"           # non-price inputs (volume, calendar, roll metadata)


class FeatureError(ValueError):
    """Raised on invalid feature specs or invalid feature inputs."""


# Transforms that consume exactly one trailing window.
_SINGLE_WINDOW_TRANSFORMS = {
    TransformType.RETURN,
    TransformType.REALIZED_VOL,
    TransformType.ROLLING_MAX,
    TransformType.ROLLING_MIN,
    TransformType.RATIO_TO_ROLLING_MAX,
    TransformType.RATIO_TO_ROLLING_MIN,
    TransformType.ZSCORE,
}
# Pointwise transforms — no windows.
_POINTWISE_TRANSFORMS = {
    TransformType.CALENDAR_DOW,
    TransformType.PASSTHROUGH,
    TransformType.DAYS_SINCE_FLAG,
}
# Period-via-params transforms (Wilder smoothing).
_PERIOD_TRANSFORMS = {TransformType.RSI, TransformType.ATR}
# Transforms allowed to omit input_columns (derive from the frame).
_ALLOW_EMPTY_INPUTS = {TransformType.CALENDAR_DOW}


class FeatureSpec(BaseModel):
    """Declarative definition of a single feature (config only — no math)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    transform: TransformType
    input_columns: list[str] = Field(default_factory=list)
    windows: list[int] = Field(default_factory=list)
    price_space: PriceSpace
    required_adjustment: Optional[AdjustmentMethod] = None
    params: dict = Field(default_factory=dict)
    warmup: int = Field(default=0, ge=0)
    output_name: Optional[str] = None
    description: str = ""

    @model_validator(mode="before")
    @classmethod
    def _default_output_name(cls, data):
        if isinstance(data, dict) and not data.get("output_name") and data.get("name"):
            data = {**data, "output_name": data["name"]}
        return data

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must be non-empty")
        return v

    @field_validator("windows")
    @classmethod
    def _windows_positive(cls, v: list[int]) -> list[int]:
        if any(w <= 0 for w in v):
            raise ValueError("windows must be positive integers")
        return v

    @model_validator(mode="after")
    def _check_consistency(self) -> "FeatureSpec":
        # input_columns required unless the transform derives from the frame.
        if not self.input_columns and self.transform not in _ALLOW_EMPTY_INPUTS:
            raise ValueError(f"{self.transform.value} requires non-empty input_columns")

        # price_space <-> required_adjustment.
        if self.price_space is PriceSpace.ADJUSTED:
            if self.required_adjustment is None:
                raise ValueError("ADJUSTED price_space requires required_adjustment")
        elif self.required_adjustment is not None:
            raise ValueError(
                f"{self.price_space.value} price_space must not set required_adjustment"
            )

        # transform-specific window / param validation.
        t = self.transform
        if t in _SINGLE_WINDOW_TRANSFORMS:
            if len(self.windows) != 1:
                raise ValueError(f"{t.value} requires exactly one window")
        elif t is TransformType.MA_GAP:
            if len(self.windows) != 2:
                raise ValueError("ma_gap requires exactly two windows (short, long)")
            if self.windows[0] >= self.windows[1]:
                raise ValueError("ma_gap requires windows[0] < windows[1]")
        elif t in _PERIOD_TRANSFORMS:
            period = self.params.get("period")
            if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
                raise ValueError(f"{t.value} requires params['period'] as a positive int")
        elif t in _POINTWISE_TRANSFORMS:
            if self.windows:
                raise ValueError(f"{t.value} is pointwise and must have no windows")
        return self


# --------------------------------------------------------------------------- #
# Default ES feature registry (Phase 2 plan §C.5) — specs only, no math yet.
# --------------------------------------------------------------------------- #

_RATIO = AdjustmentMethod.RATIO


def _ret(name: str, window: int) -> FeatureSpec:
    return FeatureSpec(
        name=name,
        transform=TransformType.RETURN,
        input_columns=["close_adjusted"],
        windows=[window],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        warmup=window,
        description=f"{window}-session close-to-close return (ratio-adjusted).",
    )


DEFAULT_ES_FEATURES: list[FeatureSpec] = [
    _ret("return_1", 1),
    _ret("return_5", 5),
    _ret("return_20", 20),
    FeatureSpec(
        name="realized_vol_20",
        transform=TransformType.REALIZED_VOL,
        input_columns=["close_adjusted"],
        windows=[20],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        params={"annualize": True, "trading_days": 252},
        warmup=20,
        description="Annualized (x sqrt(252)) std of daily returns over 20 sessions.",
    ),
    FeatureSpec(
        name="rolling_high_20",
        transform=TransformType.ROLLING_MAX,
        input_columns=["high_adjusted"],
        windows=[20],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        warmup=19,
        description="20-session rolling high (adjusted; absolute level back-adjusted).",
    ),
    FeatureSpec(
        name="rolling_low_20",
        transform=TransformType.ROLLING_MIN,
        input_columns=["low_adjusted"],
        windows=[20],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        warmup=19,
        description="20-session rolling low (adjusted; absolute level back-adjusted).",
    ),
    FeatureSpec(
        name="close_to_rolling_high_20",
        transform=TransformType.RATIO_TO_ROLLING_MAX,
        input_columns=["close_adjusted", "high_adjusted"],
        windows=[20],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        warmup=19,
        description="close / rolling_high_20 - 1 (scale-invariant).",
    ),
    FeatureSpec(
        name="close_to_rolling_low_20",
        transform=TransformType.RATIO_TO_ROLLING_MIN,
        input_columns=["close_adjusted", "low_adjusted"],
        windows=[20],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        warmup=19,
        description="close / rolling_low_20 - 1 (scale-invariant).",
    ),
    FeatureSpec(
        name="moving_average_gap_10_50",
        transform=TransformType.MA_GAP,
        input_columns=["close_adjusted"],
        windows=[10, 50],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        warmup=49,
        description="(MA10 - MA50) / MA50 (relative, scale-invariant).",
    ),
    FeatureSpec(
        name="RSI_14",
        transform=TransformType.RSI,
        input_columns=["close_adjusted"],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        params={"period": 14},
        warmup=14,
        description="Wilder RSI(14) of adjusted close (scale-invariant).",
    ),
    FeatureSpec(
        name="ATR_14",
        transform=TransformType.ATR,
        input_columns=["high_adjusted", "low_adjusted", "close_adjusted"],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        params={"period": 14},
        warmup=14,
        description="Wilder ATR(14) in adjusted points.",
    ),
    FeatureSpec(
        name="ATR_14_pct",
        transform=TransformType.ATR,
        input_columns=["high_adjusted", "low_adjusted", "close_adjusted"],
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        params={"period": 14, "normalize": "close"},
        warmup=14,
        description="ATR(14) / close — scale-relative; preferred over ATR_14 for ML.",
    ),
    FeatureSpec(
        name="volume_zscore_20",
        transform=TransformType.ZSCORE,
        input_columns=["volume"],
        windows=[20],
        price_space=PriceSpace.NONE,
        warmup=20,
        description="20-session z-score of volume (contract discontinuity at rolls).",
    ),
    FeatureSpec(
        name="day_of_week",
        transform=TransformType.CALENDAR_DOW,
        input_columns=["timestamp"],
        price_space=PriceSpace.NONE,
        warmup=0,
        description="Session weekday 0-4 (Mon-Fri).",
    ),
    FeatureSpec(
        name="roll_flag",
        transform=TransformType.PASSTHROUGH,
        input_columns=["roll_flag"],
        price_space=PriceSpace.NONE,
        warmup=0,
        description="Continuous roll_flag passthrough (known at t).",
    ),
    FeatureSpec(
        name="days_since_roll",
        transform=TransformType.DAYS_SINCE_FLAG,
        input_columns=["roll_flag"],
        price_space=PriceSpace.NONE,
        warmup=0,
        description="Sessions since last roll_flag<=t (NaN before the first roll).",
    ),
]


# --------------------------------------------------------------------------- #
# Reproducibility — feature config hash
# --------------------------------------------------------------------------- #

_FEATURE_CONFIG_SCHEMA = "feature_config_v1"


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def feature_config_hash(
    specs: list[FeatureSpec],
    continuous_config_hash: Optional[str] = None,
) -> str:
    """Deterministic SHA-256 over a feature spec set.

    Order-stable (specs sorted by name), sensitive to any spec change, and
    optionally chained with the upstream Phase 1 ``continuous_config_hash`` so the
    full raw -> continuous -> features provenance is captured.
    """
    features = sorted(
        (s.model_dump(mode="json") for s in specs),
        key=lambda d: d["name"],
    )
    payload = {
        "schema_version": _FEATURE_CONFIG_SCHEMA,
        "continuous_config_hash": continuous_config_hash,
        "features": features,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
