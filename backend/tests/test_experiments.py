"""
Phase 5 — commit 1: ExperimentRun schema, metadata, and git helper.

Synthetic metadata only; no file I/O; no network; no model training.
"""

import inspect
import re
from datetime import date

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.experiments import ExperimentError, ExperimentRun, best_effort_git_commit
from app.ml_signal import (
    MlEvaluationResult,
    ModelSpec,
    ModelType,
    TaskType,
    ThresholdRule,
    TrainedModel,
)


def _run(**over) -> ExperimentRun:
    base = dict(
        train_run_hash="t" * 64,
        continuous_config_hash="c" * 64,
        feature_config_hash="f" * 64,
        label_config_hash="l" * 64,
        dataset_config_hash="d" * 64,
        model_config_hash="m" * 64,
        model_type="ridge_regression",
        feature_columns=("feature__return_20", "feature__moving_average_gap_10_50"),
        label_column="label__forward_return_1",
        task_type="regression",
        train_start=date(2024, 1, 1),
        train_end=date(2024, 6, 30),
        validation_start=date(2024, 7, 1),
        validation_end=date(2024, 12, 31),
        metrics={"r2": 0.1, "n_scored": 40},
        backtest_metrics={"sharpe": 1.2, "total_return": 0.05, "max_drawdown": -0.1, "turnover": 3.0},
        baseline_metrics={"no_trade": {"total_return": 0.0}, "momentum": {"total_return": 0.02}},
        created_at="2026-06-25T00:00:00+00:00",
        artifact_paths={"metadata": "metadata.json", "predictions": "predictions.csv"},
        n_oos_rows=50,
        n_scored_rows=40,
    )
    base.update(over)
    return ExperimentRun(**base)


def _model_spec() -> ModelSpec:
    return ModelSpec(
        model_name="x",
        model_type=ModelType.RIDGE_REGRESSION,
        task_type=TaskType.REGRESSION,
        feature_columns=("feature__return_20", "feature__moving_average_gap_10_50"),
        label_column="label__forward_return_1",
        train_start=date(2024, 1, 1),
        train_end=date(2024, 6, 30),
        validation_start=date(2024, 7, 1),
        validation_end=date(2024, 12, 31),
        prediction_horizon=1,
        random_seed=0,
        threshold_rule=ThresholdRule.RETURN_THRESHOLD,
    )


def _trained_stub(metadata_over=None) -> TrainedModel:
    md = {
        "continuous_config_hash": "c" * 64,
        "feature_config_hash": "f" * 64,
        "label_config_hash": "l" * 64,
        "dataset_config_hash": "d" * 64,
        "model_config_hash": "m" * 64,
        "train_run_hash": "t" * 64,
        "model_type": "ridge_regression",
        "task_type": "regression",
    }
    if metadata_over is not None:
        md = {**md, **metadata_over}
    spec = _model_spec()
    return TrainedModel(
        model=None,
        spec=spec,
        feature_columns=tuple(spec.feature_columns),
        label_column=spec.label_column,
        train_index=np.array([], dtype=int),
        fitted_params={},
        model_config_hash="m" * 64,
        dataset_config_hash="d" * 64,
        train_run_hash="t" * 64,
        metadata=md,
    )


def _eval_stub() -> MlEvaluationResult:
    return MlEvaluationResult(
        signals=pd.DataFrame(),
        ml_backtest=None,
        backtest_metrics={"sharpe": 1.0, "total_return": 0.03, "max_drawdown": -0.05,
                          "turnover": 2.0, "total_transaction_cost": 0.01, "final_equity": 10300.0},
        classification_metrics=None,
        regression_metrics={"r2": 0.2, "mse": 0.001, "information_coefficient": 0.15, "n_scored": 40},
        no_trade_baseline={"backtest_metrics": {"total_return": 0.0, "sharpe": 0.0}},
        momentum_baseline={"backtest_metrics": {"total_return": 0.01, "sharpe": 0.3}},
        metadata={"n_oos_rows": 50, "n_scored_rows": 40},
    )


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #


def test_valid_experiment_run_creation():
    run = _run()
    assert run.train_run_hash == "t" * 64
    assert run.model_type == "ridge_regression"
    assert run.feature_columns == ("feature__return_20", "feature__moving_average_gap_10_50")
    assert run.schema_version >= 1
    assert run.git_commit is None


def test_unknown_field_forbidden():
    with pytest.raises(ValidationError):
        _run(foo=1)


def test_empty_hash_rejected():
    with pytest.raises(ValidationError):
        _run(continuous_config_hash="")
    with pytest.raises(ValidationError):
        _run(train_run_hash="   ")


def test_feature_column_without_prefix_rejected():
    with pytest.raises(ValidationError):
        _run(feature_columns=("return_20",))


def test_empty_feature_columns_rejected():
    with pytest.raises(ValidationError):
        _run(feature_columns=())


def test_label_column_without_prefix_rejected():
    with pytest.raises(ValidationError):
        _run(label_column="forward_return_1")


def test_invalid_date_ordering_rejected():
    with pytest.raises(ValidationError):
        _run(validation_start=date(2024, 6, 1))   # not after train_end
    with pytest.raises(ValidationError):
        _run(train_start=date(2024, 1, 1), train_end=date(2023, 12, 31))


def test_run_is_frozen():
    run = _run()
    with pytest.raises(ValidationError):
        run.train_run_hash = "z" * 64


# --------------------------------------------------------------------------- #
# Relative-path enforcement
# --------------------------------------------------------------------------- #


def test_absolute_posix_artifact_path_rejected():
    with pytest.raises(ValidationError):
        _run(artifact_paths={"x": "/etc/passwd"})


def test_windows_quantlab_artifact_path_rejected():
    for bad in ("C:\\quantlab\\artifacts\\metadata.json", "C:/quantlab/artifacts/metadata.json"):
        with pytest.raises(ValidationError):
            _run(artifact_paths={"x": bad})


def test_unc_artifact_path_rejected():
    with pytest.raises(ValidationError):
        _run(artifact_paths={"x": "\\\\server\\share\\metadata.json"})


def test_dotdot_artifact_path_rejected():
    with pytest.raises(ValidationError):
        _run(artifact_paths={"x": "../escape.json"})


def test_relative_artifact_paths_accepted():
    run = _run(artifact_paths={"a": "metadata.json", "b": "sub/predictions.csv"})
    assert run.artifact_paths["b"] == "sub/predictions.csv"


# --------------------------------------------------------------------------- #
# Canonical metadata determinism
# --------------------------------------------------------------------------- #


def test_canonical_metadata_stable_and_sensitive():
    a, b = _run(), _run()
    assert a.to_canonical_json() == b.to_canonical_json()          # stable across instances
    assert a.to_canonical_json() == a.to_canonical_json()          # stable across calls
    assert isinstance(a.to_canonical_json(), str)
    assert a.to_canonical_json() != _run(train_run_hash="z" * 64).to_canonical_json()


# --------------------------------------------------------------------------- #
# git helper
# --------------------------------------------------------------------------- #


def test_best_effort_git_commit_returns_str_or_none():
    result = best_effort_git_commit()
    assert result is None or (isinstance(result, str) and len(result) >= 7)


def test_best_effort_git_commit_in_non_git_dir_is_none(tmp_path):
    assert best_effort_git_commit(cwd=str(tmp_path)) is None


# --------------------------------------------------------------------------- #
# from_evaluation
# --------------------------------------------------------------------------- #


def test_from_evaluation_builds_valid_run():
    run = ExperimentRun.from_evaluation(
        _trained_stub(), _eval_stub(),
        artifact_paths={"metadata": "metadata.json", "predictions": "predictions.csv"},
        git_commit=None, code_version="v1", created_at="2026-06-25T00:00:00+00:00",
    )
    assert isinstance(run, ExperimentRun)
    assert run.train_run_hash == "t" * 64
    assert run.continuous_config_hash == "c" * 64
    assert run.model_type == "ridge_regression"
    assert run.task_type == "regression"
    assert run.metrics["r2"] == 0.2                               # regression metrics
    assert run.backtest_metrics["sharpe"] == 1.0
    assert run.baseline_metrics["no_trade"]["total_return"] == 0.0
    assert run.baseline_metrics["momentum"]["sharpe"] == 0.3
    assert run.n_oos_rows == 50 and run.n_scored_rows == 40
    assert run.artifact_paths == {"metadata": "metadata.json", "predictions": "predictions.csv"}
    assert isinstance(run.to_canonical_json(), str)


def test_from_evaluation_missing_hash_raises_experiment_error():
    tm = _trained_stub(metadata_over={"continuous_config_hash": ""})  # falsy -> missing
    with pytest.raises(ExperimentError):
        ExperimentRun.from_evaluation(
            tm, _eval_stub(), artifact_paths={"metadata": "metadata.json"},
        )


def test_from_evaluation_rejects_absolute_artifact_path():
    with pytest.raises(ValidationError):
        ExperimentRun.from_evaluation(
            _trained_stub(), _eval_stub(),
            artifact_paths={"metadata": "C:\\quantlab\\metadata.json"},
            created_at="2026-06-25T00:00:00+00:00",
        )


# --------------------------------------------------------------------------- #
# Commit-1 discipline: no file I/O, no network
# --------------------------------------------------------------------------- #


def test_commit1_writes_no_files(tmp_path):
    # building runs + canonical json + from_evaluation must not write anything
    _run().to_canonical_json()
    ExperimentRun.from_evaluation(
        _trained_stub(), _eval_stub(), artifact_paths={"metadata": "metadata.json"},
        created_at="2026-06-25T00:00:00+00:00",
    )
    assert list(tmp_path.iterdir()) == []


def test_experiment_error_is_exception():
    assert issubclass(ExperimentError, Exception)


def test_spec_module_does_no_io_or_network():
    import app.experiments.spec as spec_mod

    src = inspect.getsource(spec_mod)
    # no file-writing / directory-creating APIs
    assert not re.search(r"\.(to_csv|to_parquet|write_text|write_bytes)\(", src)
    assert not re.search(r"\bopen\(", src)
    assert not re.search(r"\b(os\.mkdir|os\.makedirs|makedirs)\b", src)
    assert not re.search(r"\.mkdir\(", src)
    # no network client imports (subprocess for local git is allowed)
    assert not re.search(r"\b(import|from)\s+(requests|urllib|httpx|socket|aiohttp)\b", src)
