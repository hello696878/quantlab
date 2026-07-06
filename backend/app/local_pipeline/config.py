"""
Local pipeline configuration (Phase 9 — commit 1).

``LocalExperimentConfig`` mirrors ``research_cli.ExperimentConfig``'s ML / window
fields, **minus** the synthetic-data block and **plus** ``source`` (the
``RawFuturesStore`` namespace to read raw contracts from).  It shares the exact
``to_model_spec()`` mapping, so the same inputs yield the same Phase 4
``ModelSpec`` (hence the same ``model_config_hash`` / ``train_run_hash``) whether
an experiment is run through the synthetic Research CLI or this local pipeline.

The ML path **pins ``adjustment_method="ratio"``** — the existing feature / label
builders require a ratio-adjusted continuous frame (ratio preserves held-contract
percentage returns across roll seams).  No I/O, no network, no new model types.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ml_signal import ModelSpec, ModelType, SignalMode, TaskType, ThresholdRule

__all__ = ["LocalExperimentConfig"]


class LocalExperimentConfig(BaseModel):
    """A reproducible local (store-backed) futures ML experiment configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    root_symbol: str = "ES"
    source: str  # RawFuturesStore namespace (required; e.g. "synthetic" / "csv_fixture")
    adjustment_method: str = "ratio"

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

    # Defaults pair with the default ridge-regression model (return-threshold
    # long/short), so ``LocalExperimentConfig(source=...)`` is a runnable demo.
    threshold_rule: ThresholdRule = ThresholdRule.RETURN_THRESHOLD
    long_threshold: float = 0.0
    short_threshold: float = 0.0
    signal_mode: SignalMode = SignalMode.LONG_SHORT

    transaction_cost_bps: float = Field(default=1.0, ge=0.0)
    overwrite: bool = False
    random_seed: int = Field(default=0, ge=0)
    created_at: Optional[str] = None
    code_version: Optional[str] = None

    @field_validator("root_symbol", "source")
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
            raise ValueError(
                "adjustment_method must be 'ratio' for the ML path "
                "(features/labels require ratio-adjusted continuous data)"
            )
        return v

    @model_validator(mode="after")
    def _validate_after(self) -> "LocalExperimentConfig":
        if not (self.train_start < self.train_end < self.validation_start < self.validation_end):
            raise ValueError(
                "dates must satisfy train_start < train_end < validation_start < validation_end"
            )
        return self

    def to_model_spec(self) -> ModelSpec:
        """Map this config to a Phase 4 ``ModelSpec`` (identical mapping to
        ``research_cli.ExperimentConfig.to_model_spec``, so the hash chain agrees)."""
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
