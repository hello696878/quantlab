"""
Training workflow for the ML Signal Lab (Phase 4 — commit 2).

``train_model`` fits one estimator on the **train rows of a split only**, with
hard leakage guards: ``X`` is built strictly from ``feature__*`` columns (any
``label__`` is rejected), every train row must be ``is_trainable``, and NaN/inf
in ``X``/``y`` is rejected.  It returns a :class:`TrainedModel` carrying the
fitted model, the design selection, and the full Phase 1->4 provenance chain.

No prediction-to-signal, no backtest — those land in later commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import scipy

from app.ml_signal.models import BaseModel, build_model
from app.ml_signal.spec import (
    ClassWeight,
    MlSignalError,
    ModelSpec,
    SampleWeight,
    TaskType,
    dataset_config_hash,
    model_config_hash,
    train_run_hash,
)
from app.ml_signal.splits import Split

_POSITIVE_LABEL = 1.0


@dataclass
class TrainedModel:
    """A fitted model plus its design selection and full provenance chain."""

    model: BaseModel
    spec: ModelSpec
    feature_columns: tuple[str, ...]
    label_column: str
    train_index: np.ndarray
    fitted_params: dict
    model_config_hash: str
    dataset_config_hash: str
    train_run_hash: str
    metadata: dict


def select_design_matrix(
    frame: pd.DataFrame,
    feature_columns,
    label_column: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Build ``(X, y)`` from ``frame`` using ``feature_columns`` / ``label_column``.

    Rejects any feature column that is not ``feature__*`` (in particular any
    ``label__`` column) so labels can never leak into the design matrix.
    """
    for c in feature_columns:
        if c.startswith("label__"):
            raise MlSignalError(f"feature_columns must not contain a label column: {c!r}")
        if not c.startswith("feature__"):
            raise MlSignalError(f"feature column must start with 'feature__': {c!r}")
    missing = [c for c in (*feature_columns, label_column) if c not in frame.columns]
    if missing:
        raise MlSignalError(f"frame is missing required columns: {missing}")
    X = frame.loc[:, list(feature_columns)].to_numpy(dtype=float)
    y = frame.loc[:, label_column].to_numpy(dtype=float)
    return X, y


def _resolve_sample_weight(spec: ModelSpec, y: np.ndarray) -> Optional[np.ndarray]:
    if spec.sample_weight is SampleWeight.UNIQUENESS:
        raise MlSignalError(
            "sample_weight='uniqueness' is not wired into train_model in V1 (planned)"
        )
    if spec.class_weight is ClassWeight.BALANCED and spec.task_type is TaskType.CLASSIFICATION:
        y01 = (y == _POSITIVE_LABEL).astype(float)
        n = y01.size
        pos = float(y01.sum())
        neg = float(n - pos)
        return np.where(
            y01 == 1.0,
            (n / (2.0 * pos)) if pos > 0 else 0.0,
            (n / (2.0 * neg)) if neg > 0 else 0.0,
        )
    return None


def train_model(
    dataset_df: pd.DataFrame,
    model_spec: ModelSpec,
    split: Split,
    *,
    continuous_config_hash: str,
    feature_config_hash: str,
    label_config_hash: str,
    dataset_config_hash_value: Optional[str] = None,
) -> TrainedModel:
    """Fit ``model_spec`` on the train rows of ``split``.  ``dataset_df`` is never
    mutated.  Raises :class:`MlSignalError` on leakage / untrainable / NaN inputs."""
    if "is_trainable" not in dataset_df.columns:
        raise MlSignalError("dataset_df must contain an 'is_trainable' column")

    train_index = np.asarray(split.train_index, dtype=int)
    if train_index.size == 0:
        raise MlSignalError("the split has no train rows")

    # Read-only positional slice of the train rows (never mutate the input).
    train_rows = dataset_df.iloc[train_index]

    if not bool(train_rows["is_trainable"].astype(bool).all()):
        n_bad = int((~train_rows["is_trainable"].astype(bool)).sum())
        raise MlSignalError(
            f"{n_bad} train rows are not trainable (warmup / invalid-label); "
            "the split must contain only is_trainable rows"
        )

    X, y = select_design_matrix(train_rows, model_spec.feature_columns, model_spec.label_column)
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        raise MlSignalError(
            "NaN/inf found in training X or y; trainable rows must be complete"
        )

    sample_weight = _resolve_sample_weight(model_spec, y)
    model = build_model(model_spec)
    model.fit(X, y, sample_weight=sample_weight)

    mc_hash = model_config_hash(model_spec)
    ds_hash = dataset_config_hash_value or dataset_config_hash(
        label_config_hash=label_config_hash,
        feature_columns=model_spec.feature_columns,
        label_column=model_spec.label_column,
    )
    tr_hash = train_run_hash(
        continuous_config_hash=continuous_config_hash,
        feature_config_hash=feature_config_hash,
        label_config_hash=label_config_hash,
        dataset_config_hash=ds_hash,
        model_config_hash=mc_hash,
    )

    metadata = {
        "continuous_config_hash": continuous_config_hash,
        "feature_config_hash": feature_config_hash,
        "label_config_hash": label_config_hash,
        "dataset_config_hash": ds_hash,
        "model_config_hash": mc_hash,
        "train_run_hash": tr_hash,
        "model_type": model_spec.model_type.value,
        "task_type": model_spec.task_type.value,
        "random_seed": model_spec.random_seed,
        "train_start": model_spec.train_start.isoformat(),
        "train_end": model_spec.train_end.isoformat(),
        "n_train_rows": int(train_index.size),
        "n_features": len(model_spec.feature_columns),
        "library_versions": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pandas": pd.__version__,
        },
    }

    return TrainedModel(
        model=model,
        spec=model_spec,
        feature_columns=tuple(model_spec.feature_columns),
        label_column=model_spec.label_column,
        train_index=train_index,
        fitted_params=dict(model.params),
        model_config_hash=mc_hash,
        dataset_config_hash=ds_hash,
        train_run_hash=tr_hash,
        metadata=metadata,
    )
