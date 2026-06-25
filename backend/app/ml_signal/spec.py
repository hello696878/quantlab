"""
ModelSpec + provenance hashes for the ML Signal Lab (Phase 4 — commit 1).

A strict, frozen model configuration plus three deterministic hashes that extend
the Phase 1->3 reproducibility chain:

    continuous_config_hash  (Phase 1)
      -> feature_config_hash (Phase 2)
        -> label_config_hash (Phase 3)
          -> dataset_config_hash (which supervised view feeds the model)
            -> model_config_hash (the ModelSpec)
              -> train_run_hash (the whole lineage; one id per trained artifact)

No model training happens here, and deliberately **no scikit-learn model types** —
``ModelType`` admits only numpy/scipy-implementable estimators.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.signals import SignalMode  # reuse Phase 3 long_flat / long_short

_MODEL_CONFIG_SCHEMA = 1
_DATASET_CONFIG_SCHEMA = 1
_TRAIN_RUN_SCHEMA = 1


class MlSignalError(ValueError):
    """Raised on invalid ML-signal configuration or split inputs."""


class ModelType(str, Enum):
    """Admitted estimators — all implementable with numpy/scipy (no sklearn)."""

    DUMMY_BASELINE = "dummy_baseline"
    LOGISTIC_REGRESSION = "logistic_regression"
    RIDGE_REGRESSION = "ridge_regression"


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"


class ThresholdRule(str, Enum):
    PROB_THRESHOLD = "prob_threshold"      # classification: long if P(up)  >= long_threshold
    RETURN_THRESHOLD = "return_threshold"  # regression:     long if r_hat  >= long_threshold


class ClassWeight(str, Enum):
    NONE = "none"
    BALANCED = "balanced"


class SampleWeight(str, Enum):
    NONE = "none"
    UNIQUENESS = "uniqueness"  # AFML average-uniqueness weights (app.finml.uniqueness)


class SplitType(str, Enum):
    CHRONOLOGICAL_HOLDOUT = "chronological_holdout"
    WALK_FORWARD = "walk_forward"
    PURGED_KFOLD = "purged_kfold"


def _canonical_json(obj: Any) -> str:
    """Canonical JSON identical to the Phase 1-3 hashers (sorted keys, compact)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ModelSpec(BaseModel):
    """Strict, frozen ML model configuration (no training performed here)."""

    # ``protected_namespaces=()`` allows the required ``model_name`` / ``model_type``
    # fields without Pydantic's reserved ``model_`` namespace warning.
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_name: str
    model_type: ModelType
    task_type: TaskType
    feature_columns: tuple[str, ...]
    label_column: str
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    prediction_horizon: int = Field(gt=0)
    random_seed: int = Field(default=0, ge=0)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    class_weight: ClassWeight = ClassWeight.NONE
    sample_weight: SampleWeight = SampleWeight.NONE
    threshold_rule: ThresholdRule = ThresholdRule.PROB_THRESHOLD
    long_threshold: float = 0.5
    short_threshold: float = 0.5
    signal_mode: SignalMode = SignalMode.LONG_FLAT
    output_signal_col: str = "target_position"
    schema_version: int = Field(default=_MODEL_CONFIG_SCHEMA, ge=1)

    @field_validator("model_name", "label_column", "output_signal_col")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("feature_columns")
    @classmethod
    def _validate_features(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("feature_columns must be non-empty")
        for c in v:
            if not isinstance(c, str) or not c.strip():
                raise ValueError("feature column names must be non-empty strings")
            if c.startswith("label__"):
                raise ValueError(f"feature_columns must not contain a label column: {c!r}")
            if not c.startswith("feature__"):
                raise ValueError(f"feature column must start with 'feature__': {c!r}")
        if len(set(v)) != len(v):
            raise ValueError("feature_columns must not contain duplicates")
        return v

    @field_validator("label_column")
    @classmethod
    def _validate_label(cls, v: str) -> str:
        if not v.startswith("label__"):
            raise ValueError("label_column must start with 'label__'")
        return v

    @model_validator(mode="after")
    def _validate_dates(self) -> "ModelSpec":
        if not (self.train_start < self.train_end < self.validation_start < self.validation_end):
            raise ValueError(
                "dates must satisfy train_start < train_end < validation_start < validation_end"
            )
        return self


def model_config_hash(spec: ModelSpec) -> str:
    """Deterministic SHA-256 over the full ModelSpec (sensitive to every field)."""
    payload = {
        "schema_version": _MODEL_CONFIG_SCHEMA,
        "model": spec.model_dump(mode="json"),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def dataset_config_hash(
    *,
    label_config_hash: str,
    feature_columns: tuple[str, ...] | list[str],
    label_column: str,
    drop_warmup: bool = False,
    trainable_only: bool = True,
    schema_version: int = _DATASET_CONFIG_SCHEMA,
) -> str:
    """Hash of *which* supervised view feeds the model, chaining the label hash.

    Order-insensitive on ``feature_columns`` (sorted before hashing) so column
    ordering never changes the identity of the dataset view.
    """
    payload = {
        "schema_version": schema_version,
        "upstream_label_config_hash": label_config_hash,
        "feature_columns": sorted(feature_columns),
        "label_column": label_column,
        "drop_warmup": bool(drop_warmup),
        "trainable_only": bool(trainable_only),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def train_run_hash(
    *,
    continuous_config_hash: str,
    feature_config_hash: str,
    label_config_hash: str,
    dataset_config_hash: str,
    model_config_hash: str,
    schema_version: int = _TRAIN_RUN_SCHEMA,
) -> str:
    """One id per trained artifact: chains the entire Phase 1->4 lineage."""
    payload = {
        "schema_version": schema_version,
        "continuous_config_hash": continuous_config_hash,
        "feature_config_hash": feature_config_hash,
        "label_config_hash": label_config_hash,
        "dataset_config_hash": dataset_config_hash,
        "model_config_hash": model_config_hash,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
