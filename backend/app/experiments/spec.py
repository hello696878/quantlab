"""
ExperimentRun metadata schema for the QuantLab experiment registry (Phase 5 — commit 1).

A strict, frozen record of one Phase 4 ML run, keyed by its ``train_run_hash``.
It carries the full Phase 1->4 hash lineage, the OOS window, metrics, baseline
metrics, and **relative** artifact filenames — enough to make a run reproducible,
comparable, and auditable.  This module performs **no file I/O** (the artifact
store lands in commit 2); it only validates and canonicalizes metadata.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date, datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.reproducibility import canonical_json

_SCHEMA_VERSION = 1

# Absolute path = a drive prefix (C:\ / C:/) or a leading slash/backslash (POSIX / UNC).
_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]|^[\\/]")

_HASH_FIELDS = (
    "train_run_hash",
    "continuous_config_hash",
    "feature_config_hash",
    "label_config_hash",
    "dataset_config_hash",
    "model_config_hash",
)


class ExperimentError(Exception):
    """Raised on invalid experiment metadata, missing artifacts, or registry errors."""


def best_effort_git_commit(cwd: Optional[str] = None) -> Optional[str]:
    """Return the current git commit SHA, or ``None`` if unavailable.

    Best-effort and local only: runs ``git rev-parse HEAD`` with a short timeout,
    never raises, and never touches the network."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


class ExperimentRun(BaseModel):
    """Strict, frozen metadata for one persisted ML experiment run."""

    # ``protected_namespaces=()`` allows the ``model_type`` / ``model_config_hash``
    # fields without Pydantic's reserved ``model_`` namespace warning.
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    train_run_hash: str
    continuous_config_hash: str
    feature_config_hash: str
    label_config_hash: str
    dataset_config_hash: str
    model_config_hash: str
    model_type: str
    feature_columns: tuple[str, ...]
    label_column: str
    task_type: str
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    metrics: dict[str, Any] = Field(default_factory=dict)
    backtest_metrics: dict[str, Any] = Field(default_factory=dict)
    baseline_metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    git_commit: Optional[str] = None
    code_version: Optional[str] = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    schema_version: int = Field(default=_SCHEMA_VERSION, ge=1)
    n_oos_rows: int = Field(default=0, ge=0)
    n_scored_rows: int = Field(default=0, ge=0)

    @field_validator(*_HASH_FIELDS)
    @classmethod
    def _nonempty_hash(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("hash fields must be non-empty strings")
        return v

    @field_validator("model_type", "task_type", "created_at")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
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

    @field_validator("artifact_paths")
    @classmethod
    def _validate_relative_paths(cls, v: dict[str, str]) -> dict[str, str]:
        for key, value in v.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"artifact path for {key!r} must be a non-empty string")
            if _ABSOLUTE_PATH.search(value):
                raise ValueError(
                    f"artifact path must be relative (no drive/UNC/leading slash): {value!r}"
                )
            if ".." in re.split(r"[\\/]", value):
                raise ValueError(f"artifact path must not contain '..': {value!r}")
        return v

    @model_validator(mode="after")
    def _validate_dates(self) -> "ExperimentRun":
        if not (self.train_start < self.train_end < self.validation_start < self.validation_end):
            raise ValueError(
                "dates must satisfy train_start < train_end < validation_start < validation_end"
            )
        return self

    def to_canonical_json(self) -> str:
        """Deterministic canonical JSON of this run (sorted keys, stable bytes)."""
        return canonical_json(self.model_dump(mode="json"))

    @classmethod
    def from_evaluation(
        cls,
        trained_model,
        evaluation_result,
        *,
        artifact_paths: dict[str, str],
        git_commit: Optional[str] = None,
        code_version: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> "ExperimentRun":
        """Build an ``ExperimentRun`` from Phase 4 outputs without writing files.

        Hashes come from ``trained_model`` (its ``metadata`` + hash attributes),
        metrics from ``evaluation_result``.  ``artifact_paths`` must be relative."""
        md = dict(getattr(trained_model, "metadata", {}) or {})
        spec = trained_model.spec

        upstream = {
            "continuous_config_hash": md.get("continuous_config_hash"),
            "feature_config_hash": md.get("feature_config_hash"),
            "label_config_hash": md.get("label_config_hash"),
        }
        missing = [k for k, val in upstream.items() if not val]
        if missing:
            raise ExperimentError(
                f"trained_model.metadata is missing upstream hashes: {missing}"
            )

        task_metrics = (
            evaluation_result.classification_metrics
            or evaluation_result.regression_metrics
            or {}
        )
        baselines: dict[str, Any] = {}
        if getattr(evaluation_result, "no_trade_baseline", None) is not None:
            baselines["no_trade"] = dict(
                evaluation_result.no_trade_baseline.get("backtest_metrics", {})
            )
        if getattr(evaluation_result, "momentum_baseline", None) is not None:
            baselines["momentum"] = dict(
                evaluation_result.momentum_baseline.get("backtest_metrics", {})
            )
        eval_md = dict(getattr(evaluation_result, "metadata", {}) or {})

        return cls(
            train_run_hash=trained_model.train_run_hash,
            continuous_config_hash=upstream["continuous_config_hash"],
            feature_config_hash=upstream["feature_config_hash"],
            label_config_hash=upstream["label_config_hash"],
            dataset_config_hash=trained_model.dataset_config_hash,
            model_config_hash=trained_model.model_config_hash,
            model_type=spec.model_type.value,
            feature_columns=tuple(spec.feature_columns),
            label_column=spec.label_column,
            task_type=spec.task_type.value,
            train_start=spec.train_start,
            train_end=spec.train_end,
            validation_start=spec.validation_start,
            validation_end=spec.validation_end,
            metrics=dict(task_metrics),
            backtest_metrics=dict(evaluation_result.backtest_metrics),
            baseline_metrics=baselines,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
            git_commit=git_commit,
            code_version=code_version,
            artifact_paths=dict(artifact_paths),
            n_oos_rows=int(eval_md.get("n_oos_rows", 0)),
            n_scored_rows=int(eval_md.get("n_scored_rows", 0)),
        )
