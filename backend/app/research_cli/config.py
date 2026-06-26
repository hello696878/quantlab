"""
Research CLI configuration (Phase 6 — commit 1).

Two strict, frozen configs plus the single mapping to a Phase 4 ``ModelSpec`` and
the artifact-directory resolver:

* ``SyntheticDataConfig`` — deterministic synthetic ES raw-futures parameters.
* ``ExperimentConfig`` — a full, reproducible synthetic ES ML experiment.
* ``ExperimentConfig.to_model_spec()`` — the one source of truth for the Phase 4
  ``ModelSpec`` (so config can't drift from the spec).
* ``resolve_artifact_base_dir(config)`` — explicit dir > ``QUANTLAB_ARTIFACTS_DIR``
  env > default ``artifacts/experiments`` (does **not** create the directory).

No file I/O, no network, and no new model types — ``ModelType`` admits only the
numpy/scipy Phase 4 estimators.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ml_signal import (
    ModelSpec,
    ModelType,
    SignalMode,
    TaskType,
    ThresholdRule,
)

_DEFAULT_ARTIFACT_SUBDIR = Path("artifacts") / "experiments"
_ARTIFACTS_ENV_VAR = "QUANTLAB_ARTIFACTS_DIR"


class SyntheticDataConfig(BaseModel):
    """Deterministic synthetic ES raw-futures parameters (no I/O, no network)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_symbol: str = "ES"
    n_contracts: int = Field(default=3, ge=2)
    start_date: date = date(2024, 1, 2)
    sessions_per_contract: int = Field(default=120, ge=64)  # > one quarter so contracts overlap & roll
    contract_gap: float = Field(default=100.0, ge=0.0)      # inter-contract price step (raw seam gap)
    base_price: float = Field(default=5000.0, gt=0.0)
    daily_drift: float = 0.3
    noise_scale: float = Field(default=0.0, ge=0.0)
    volume: int = Field(default=1000, ge=0)
    random_seed: int = Field(default=0, ge=0)

    @field_validator("root_symbol")
    @classmethod
    def _nonempty_root(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("root_symbol must be a non-empty string")
        return v


class ExperimentConfig(BaseModel):
    """A full, reproducible synthetic ES ML experiment configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    root_symbol: str = "ES"
    synthetic: SyntheticDataConfig = Field(default_factory=SyntheticDataConfig)

    train_start: date = date(2024, 4, 1)
    train_end: date = date(2024, 6, 5)
    validation_start: date = date(2024, 6, 6)
    validation_end: date = date(2024, 9, 15)

    feature_columns: tuple[str, ...] = ("feature__return_20", "feature__moving_average_gap_10_50")
    label_column: str = "label__forward_return_1"
    model_type: ModelType = ModelType.RIDGE_REGRESSION
    task_type: TaskType = TaskType.REGRESSION
    prediction_horizon: int = Field(default=1, gt=0)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)

    # Defaults pair with the default ridge-regression model: a return-threshold
    # long/short rule, so a bare ``ExperimentConfig()`` is a runnable regression demo.
    threshold_rule: ThresholdRule = ThresholdRule.RETURN_THRESHOLD
    long_threshold: float = 0.0
    short_threshold: float = 0.0
    signal_mode: SignalMode = SignalMode.LONG_SHORT

    transaction_cost_bps: float = Field(default=1.0, ge=0.0)
    adjustment_method: str = "ratio"

    artifact_base_dir: Optional[str] = None
    overwrite: bool = False
    random_seed: int = Field(default=0, ge=0)
    created_at: Optional[str] = None
    code_version: Optional[str] = None

    @field_validator("feature_columns")
    @classmethod
    def _validate_features(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not v:
            raise ValueError("feature_columns must be non-empty")
        for c in v:
            if not isinstance(c, str) or not c.startswith("feature__"):
                raise ValueError(f"feature column must start with 'feature__': {c!r}")
        return v

    @field_validator("label_column")
    @classmethod
    def _validate_label(cls, v: str) -> str:
        if not v.startswith("label__"):
            raise ValueError("label_column must start with 'label__'")
        return v

    @field_validator("adjustment_method")
    @classmethod
    def _validate_adjustment(cls, v: str) -> str:
        if v != "ratio":
            raise ValueError("adjustment_method must be 'ratio' for V1")
        return v

    @model_validator(mode="after")
    def _validate_after(self) -> "ExperimentConfig":
        if not (self.train_start < self.train_end < self.validation_start < self.validation_end):
            raise ValueError(
                "dates must satisfy train_start < train_end < validation_start < validation_end"
            )
        if self.root_symbol != self.synthetic.root_symbol:
            raise ValueError(
                f"root_symbol {self.root_symbol!r} must match synthetic.root_symbol "
                f"{self.synthetic.root_symbol!r}"
            )
        return self

    def to_model_spec(self) -> ModelSpec:
        """Map this config to a Phase 4 ``ModelSpec`` (the single source of truth)."""
        return ModelSpec(
            model_name=f"{self.root_symbol.lower()}_{self.model_type.value}",
            model_type=self.model_type,
            task_type=self.task_type,
            feature_columns=self.feature_columns,
            label_column=self.label_column,
            train_start=self.train_start,
            train_end=self.train_end,
            validation_start=self.validation_start,
            validation_end=self.validation_end,
            prediction_horizon=self.prediction_horizon,
            random_seed=self.random_seed,
            hyperparameters=dict(self.hyperparameters),
            threshold_rule=self.threshold_rule,
            long_threshold=self.long_threshold,
            short_threshold=self.short_threshold,
            signal_mode=self.signal_mode,
        )


def resolve_artifact_base_dir(config: ExperimentConfig) -> Path:
    """Resolve the artifact base directory **without creating it**.

    Precedence: explicit ``config.artifact_base_dir`` > ``QUANTLAB_ARTIFACTS_DIR``
    env var > default ``artifacts/experiments`` (relative to the working dir)."""
    if config.artifact_base_dir:
        return Path(config.artifact_base_dir)
    env_value = os.environ.get(_ARTIFACTS_ENV_VAR)
    if env_value:
        return Path(env_value)
    return Path(_DEFAULT_ARTIFACT_SUBDIR)
