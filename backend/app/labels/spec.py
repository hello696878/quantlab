"""
Futures label specification + config hashing (Phase 3 — commit 1).

Declarative config for supervised labels built on the Phase 1 ratio-adjusted
continuous frame.  **No label math** lives here — this module defines what a
label is, validates the spec, and hashes a spec set.  Mirrors the Phase 1/2
spec discipline: frozen, strict (``extra="forbid"``) Pydantic models.

Labels are the *only* artifact allowed to read future prices.  A label at ``t``
is measured from the **execution bar** ``t + execution_lag`` (default 1), so it
captures exactly what acting on ``signal(t)`` earns when executed at ``t+1``.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.instruments import AdjustmentMethod


class LabelType(str, Enum):
    FORWARD_RETURN = "forward_return"
    DIRECTION = "direction"
    VOL_ADJUSTED_RETURN = "vol_adjusted_return"


class ReturnType(str, Enum):
    SIMPLE = "simple"
    LOG = "log"


class PriceSpace(str, Enum):
    ADJUSTED = "adjusted"   # ratio-adjusted continuous prices (return labels)
    RAW = "raw"             # raw held-contract prices (execution reference)


class LabelError(ValueError):
    """Raised on invalid label specs or invalid label inputs."""


class LabelSpec(BaseModel):
    """Declarative definition of a single supervised label (config only — no math)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    label_type: LabelType
    horizon: int = Field(gt=0)
    input_column: str
    price_space: PriceSpace
    required_adjustment: Optional[AdjustmentMethod] = None
    return_type: ReturnType = ReturnType.SIMPLE
    threshold: float = Field(default=0.0, ge=0.0)
    execution_lag: int = Field(default=1, ge=1)
    output_column: Optional[str] = None
    params: dict = Field(default_factory=dict)
    description: str = ""

    @model_validator(mode="before")
    @classmethod
    def _default_output_column(cls, data):
        if isinstance(data, dict) and not data.get("output_column") and data.get("name"):
            data = {**data, "output_column": data["name"]}
        return data

    @field_validator("name", "input_column")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must be non-empty")
        return v

    @model_validator(mode="after")
    def _check_consistency(self) -> "LabelSpec":
        # price_space <-> required_adjustment (mirrors FeatureSpec).
        if self.price_space is PriceSpace.ADJUSTED:
            if self.required_adjustment is None:
                raise ValueError("ADJUSTED price_space requires required_adjustment")
        elif self.required_adjustment is not None:
            raise ValueError(
                f"{self.price_space.value} price_space must not set required_adjustment"
            )
        # vol-adjusted labels need a trailing volatility column from the feature matrix.
        if self.label_type is LabelType.VOL_ADJUSTED_RETURN:
            vol_column = self.params.get("vol_column")
            if not isinstance(vol_column, str) or not vol_column.strip():
                raise ValueError(
                    "vol_adjusted_return requires params['vol_column'] (a non-empty string)"
                )
        return self


# --------------------------------------------------------------------------- #
# Default ES label registry (Phase 3 plan §D.4) — specs only, no math here.
# --------------------------------------------------------------------------- #

_RATIO = AdjustmentMethod.RATIO


def _forward_return_spec(name: str, horizon: int) -> LabelSpec:
    return LabelSpec(
        name=name,
        label_type=LabelType.FORWARD_RETURN,
        horizon=horizon,
        input_column="close_adjusted",
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        execution_lag=1,
        description=f"{horizon}-bar forward return measured from the execution bar (t+1).",
    )


def _direction_spec(name: str, horizon: int) -> LabelSpec:
    return LabelSpec(
        name=name,
        label_type=LabelType.DIRECTION,
        horizon=horizon,
        input_column="close_adjusted",
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        threshold=0.0,
        execution_lag=1,
        description=f"sign of the {horizon}-bar forward return (deadband = threshold).",
    )


DEFAULT_ES_LABELS: list[LabelSpec] = [
    _forward_return_spec("forward_return_1", 1),
    _forward_return_spec("forward_return_5", 5),
    _direction_spec("direction_1", 1),
    _direction_spec("direction_5", 5),
    LabelSpec(
        name="volatility_adjusted_return_5",
        label_type=LabelType.VOL_ADJUSTED_RETURN,
        horizon=5,
        input_column="close_adjusted",
        price_space=PriceSpace.ADJUSTED,
        required_adjustment=_RATIO,
        execution_lag=1,
        params={"vol_column": "realized_vol_20"},
        description="5-bar forward return scaled by the trailing realized_vol_20 at t.",
    ),
]


# --------------------------------------------------------------------------- #
# Reproducibility — label config hash (chains the upstream feature hash)
# --------------------------------------------------------------------------- #

_LABEL_CONFIG_SCHEMA = "label_config_v1"


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def label_config_hash(
    specs: list[LabelSpec],
    upstream_feature_hash: Optional[str] = None,
) -> str:
    """Deterministic SHA-256 over a label spec set.

    Order-stable (sorted by name), sensitive to any spec change, and **chained
    with the upstream Phase 2 ``feature_config_hash``** so the full
    raw -> continuous -> features -> labels provenance is captured.
    """
    labels = sorted(
        (s.model_dump(mode="json") for s in specs),
        key=lambda d: d["name"],
    )
    payload = {
        "schema_version": _LABEL_CONFIG_SCHEMA,
        "upstream_feature_hash": upstream_feature_hash,
        "labels": labels,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
