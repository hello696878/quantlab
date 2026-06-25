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

from pathlib import Path

import types

from app.experiments import (
    ExperimentError,
    ExperimentRun,
    ExperimentStore,
    LoadedExperiment,
    best_effort_git_commit,
    compare_experiments,
    get_best_experiment,
    list_experiments,
    load_experiment_run,
    save_experiment_run,
    summarize_experiment,
)
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


# --------------------------------------------------------------------------- #
# Commit 2 — local artifact store (ExperimentStore)
# --------------------------------------------------------------------------- #

_H = "a" * 64  # a synthetic train_run_hash for store tests


def _frame(n: int = 5) -> pd.DataFrame:
    ts = pd.date_range("2024-07-01", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "prediction": np.arange(n, dtype=float),
            "target_position": np.array([1.0, 0.0, -1.0, 1.0, 0.0])[:n],
            "signal_state": "long",
        }
    )


def test_store_creates_run_dir_under_tmp(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _run()
    path = store.write_metadata(run)
    assert path == tmp_path / run.train_run_hash / "metadata.json"
    assert path.exists()
    assert path.is_relative_to(tmp_path)


def test_metadata_roundtrip(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _run()
    store.write_metadata(run)
    loaded = store.read_metadata(run.train_run_hash)
    assert isinstance(loaded, ExperimentRun)
    assert loaded.train_run_hash == run.train_run_hash
    assert loaded.to_canonical_json() == run.to_canonical_json()
    assert loaded.artifact_paths == run.artifact_paths


def test_read_metadata_rejects_dir_name_mismatch(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _run(train_run_hash="b" * 64)
    # write metadata for run b under directory "a"*64 by hand-placing it
    target = tmp_path / ("a" * 64)
    target.mkdir(parents=True)
    (target / "metadata.json").write_text(run.to_canonical_json(), encoding="utf-8")
    with pytest.raises(ExperimentError):
        store.read_metadata("a" * 64)


def test_model_params_roundtrip(tmp_path):
    store = ExperimentStore(tmp_path)
    params = {"coef_": [2.0, -1.0], "intercept_": 0.5, "alpha": 1.0}
    store.write_model_params(_H, params)
    loaded = store.read_model_params(_H)
    assert loaded["coef_"] == [2.0, -1.0]      # 2 == 2.0 in Python
    assert loaded["intercept_"] == 0.5
    assert loaded["alpha"] == 1.0


def test_metrics_roundtrip(tmp_path):
    store = ExperimentStore(tmp_path)
    metrics = {"backtest": {"sharpe": 1.2, "total_return": 0.05}, "regression": {"r2": 0.2}}
    store.write_metrics(_H, metrics)
    loaded = store.read_metrics(_H)
    assert loaded["backtest"]["sharpe"] == 1.2
    assert loaded["regression"]["r2"] == 0.2


def test_frame_roundtrip(tmp_path):
    store = ExperimentStore(tmp_path)
    df = _frame()
    for name in ("predictions", "signal", "backtest"):
        path = store.write_frame(_H, name, df)
        assert path.is_relative_to(tmp_path)
        back = store.read_frame(_H, name)
        assert list(back.columns) == list(df.columns)
        assert len(back) == len(df)
        assert back["prediction"].tolist() == df["prediction"].tolist()


def test_csv_fallback_when_parquet_unavailable(tmp_path):
    store = ExperimentStore(tmp_path, prefer_parquet=False)
    assert store.storage_format == "csv"
    path = store.write_frame(_H, "predictions", _frame())
    assert path.suffix == ".csv"
    back = store.read_frame(_H, "predictions")
    assert len(back) == 5


def test_missing_metadata_raises(tmp_path):
    store = ExperimentStore(tmp_path)
    with pytest.raises(ExperimentError):
        store.read_metadata("c" * 64)


def test_missing_frame_raises(tmp_path):
    store = ExperimentStore(tmp_path)
    with pytest.raises(ExperimentError):
        store.read_frame(_H, "predictions")          # never written
    with pytest.raises(ExperimentError):
        store.read_frame(_H, "bogus")                # unknown name


def test_no_writes_outside_base_dir(tmp_path):
    base = tmp_path / "artifacts" / "experiments"
    store = ExperimentStore(base)
    run = _run()
    written = [
        store.write_metadata(run),
        store.write_model_params(run.train_run_hash, {"coef_": [1.0]}),
        store.write_metrics(run.train_run_hash, {"sharpe": 1.0}),
        *[store.write_frame(run.train_run_hash, n, _frame()) for n in ("predictions", "signal", "backtest")],
    ]
    for path in written:
        assert path.is_relative_to(base)
    # every file anywhere under tmp_path lives under base
    all_files = [q for q in tmp_path.rglob("*") if q.is_file()]
    assert all_files and all(q.is_relative_to(base) for q in all_files)


def test_metadata_artifact_paths_remain_relative(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _run(artifact_paths={"metadata": "metadata.json", "predictions": "sub/predictions.csv"})
    store.write_metadata(run)
    loaded = store.read_metadata(run.train_run_hash)
    for value in loaded.artifact_paths.values():
        assert not value.startswith(("/", "\\"))
        assert not re.match(r"^[A-Za-z]:", value)


def test_deterministic_json_bytes(tmp_path):
    s1 = ExperimentStore(tmp_path / "a")
    s2 = ExperimentStore(tmp_path / "b")
    run = _run()
    assert s1.write_metadata(run).read_bytes() == s2.write_metadata(run).read_bytes()
    p = {"coef_": [2.0, -1.0], "intercept_": 0.5}
    assert (s1.write_model_params(_H, p).read_bytes()
            == s2.write_model_params(_H, p).read_bytes())
    m = {"sharpe": 1.0, "total_return": 0.03}
    assert s1.write_metrics(_H, m).read_bytes() == s2.write_metrics(_H, m).read_bytes()


def test_no_pickle_or_joblib_artifacts(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _run()
    store.write_metadata(run)
    store.write_model_params(run.train_run_hash, {"coef_": [1.0]})
    store.write_metrics(run.train_run_hash, {"sharpe": 1.0})
    for name in ("predictions", "signal", "backtest"):
        store.write_frame(run.train_run_hash, name, _frame())
    names = [q.name for q in tmp_path.rglob("*") if q.is_file()]
    assert names and not any(n.endswith((".pkl", ".pickle", ".joblib")) for n in names)

    import app.experiments.store as store_mod
    src = inspect.getsource(store_mod)
    assert not re.search(r"\b(import|from)\s+(pickle|joblib|cloudpickle)\b", src)
    assert not re.search(r"\b(import|from)\s+(requests|urllib|httpx|socket|aiohttp)\b", src)


def test_tests_create_no_repo_artifacts_dir(tmp_path):
    store = ExperimentStore(tmp_path)
    store.write_metadata(_run())
    backend_dir = Path(__file__).resolve().parents[1]   # backend/
    repo_root = backend_dir.parent                       # worktree root
    assert not (repo_root / "artifacts").exists()
    assert not (backend_dir / "artifacts").exists()


# --------------------------------------------------------------------------- #
# Commit 3 — registry (load / list / compare / best)
# --------------------------------------------------------------------------- #


def _reg_run(h, *, sharpe=1.0, cost=0.01, created_at="2026-06-25T00:00:00+00:00",
             artifact_paths=None, **over) -> ExperimentRun:
    return _run(
        train_run_hash=h,
        artifact_paths=artifact_paths if artifact_paths is not None else {"metadata": "metadata.json"},
        backtest_metrics={"sharpe": sharpe, "total_return": 0.05, "max_drawdown": -0.1,
                          "turnover": 3.0, "total_transaction_cost": cost},
        created_at=created_at,
        **over,
    )


def test_load_experiment_run_metadata_only(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _reg_run("a" * 64)
    store.write_metadata(run)
    loaded = load_experiment_run("a" * 64, store=store)
    assert isinstance(loaded, LoadedExperiment)
    assert loaded.run.train_run_hash == "a" * 64
    assert loaded.frames == {}


def test_load_experiment_run_with_frames(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _reg_run("a" * 64)
    store.write_metadata(run)
    for name in ("predictions", "signal", "backtest"):
        store.write_frame("a" * 64, name, _frame())
    loaded = load_experiment_run("a" * 64, store=store, load_frames=True)
    assert set(loaded.frames) == {"predictions", "signal", "backtest"}
    assert len(loaded.frames["predictions"]) == 5


def test_load_experiment_run_missing_artifact_raises(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _reg_run("a" * 64, artifact_paths={"metadata": "metadata.json", "predictions": "predictions.csv"})
    store.write_metadata(run)  # predictions.csv is referenced but never written
    with pytest.raises(ExperimentError):
        load_experiment_run("a" * 64, store=store)


def test_load_experiment_run_tampered_dir_name_raises(tmp_path):
    store = ExperimentStore(tmp_path)
    run = _reg_run("b" * 64)
    target = tmp_path / ("a" * 64)
    target.mkdir(parents=True)
    (target / "metadata.json").write_text(run.to_canonical_json(), encoding="utf-8")
    with pytest.raises(ExperimentError):
        load_experiment_run("a" * 64, store=store)


def test_list_experiments_sorted_and_skips_non_runs(tmp_path):
    store = ExperimentStore(tmp_path)
    store.write_metadata(_reg_run("a" * 64, created_at="2026-06-25T01:00:00+00:00"))
    store.write_metadata(_reg_run("b" * 64, created_at="2026-06-25T00:00:00+00:00"))
    store.write_metadata(_reg_run("c" * 64, created_at="2026-06-25T02:00:00+00:00"))
    (tmp_path / "not_a_run").mkdir()  # no metadata.json -> skipped
    runs = list_experiments(store=store)
    assert [r.train_run_hash for r in runs] == ["b" * 64, "a" * 64, "c" * 64]  # by created_at


def test_list_experiments_filters(tmp_path):
    store = ExperimentStore(tmp_path)
    store.write_metadata(_reg_run("a" * 64, model_type="ridge_regression"))
    store.write_metadata(_reg_run("b" * 64, model_type="logistic_regression",
                                  task_type="classification", label_column="label__direction_1"))
    only_ridge = list_experiments(store=store, filters={"model_type": "ridge_regression"})
    assert [r.train_run_hash for r in only_ridge] == ["a" * 64]
    only_dir = list_experiments(store=store, filters={"label_column": "label__direction_1"})
    assert [r.train_run_hash for r in only_dir] == ["b" * 64]
    with pytest.raises(ExperimentError):
        list_experiments(store=store, filters={"bogus": 1})


def test_compare_experiments_columns_and_values(tmp_path):
    store = ExperimentStore(tmp_path)
    a = _reg_run("a" * 64, sharpe=1.2)
    b = _reg_run("b" * 64, sharpe=0.8)
    store.write_metadata(a)
    store.write_metadata(b)
    df = compare_experiments(["a" * 64, "b" * 64], store=store)
    for col in ("train_run_hash", "model_type", "label_column",
                "validation_start", "validation_end", "sharpe", "total_return",
                "max_drawdown", "total_transaction_cost"):
        assert col in df.columns
    assert len(df) == 2
    sharpe_by_hash = dict(zip(df["train_run_hash"], df["sharpe"]))
    assert sharpe_by_hash["a" * 64] == 1.2 and sharpe_by_hash["b" * 64] == 0.8


def test_compare_experiments_same_window_guard(tmp_path):
    store = ExperimentStore(tmp_path)
    a = _reg_run("a" * 64)
    b = _reg_run("b" * 64, validation_end=date(2024, 11, 30))   # different OOS window
    store.write_metadata(a)
    store.write_metadata(b)
    with pytest.raises(ExperimentError):
        compare_experiments([a, b], store=store)


def test_compare_experiments_label_and_dataset_guard(tmp_path):
    store = ExperimentStore(tmp_path)
    a = _reg_run("a" * 64)
    b_label = _reg_run("b" * 64, label_column="label__direction_1")
    b_dataset = _reg_run("c" * 64, dataset_config_hash="z" * 64)
    for r in (a, b_label, b_dataset):
        store.write_metadata(r)
    with pytest.raises(ExperimentError):
        compare_experiments([a, b_label], store=store)
    with pytest.raises(ExperimentError):
        compare_experiments([a, b_dataset], store=store)


def test_compare_experiments_allow_different_windows(tmp_path):
    store = ExperimentStore(tmp_path)
    a = _reg_run("a" * 64)
    b = _reg_run("b" * 64, validation_end=date(2024, 11, 30))
    df = compare_experiments([a, b], store=store, allow_different_windows=True)
    assert "same_window" in df.columns
    flags = dict(zip(df["train_run_hash"], df["same_window"]))
    assert flags["a" * 64] is True or flags["a" * 64] == True   # reference matches itself
    assert not flags["b" * 64]


def test_get_best_experiment_maximize(tmp_path):
    store = ExperimentStore(tmp_path)
    store.write_metadata(_reg_run("a" * 64, sharpe=0.5))
    store.write_metadata(_reg_run("b" * 64, sharpe=2.0))
    store.write_metadata(_reg_run("c" * 64, sharpe=1.0))
    best = get_best_experiment(store=store, metric="sharpe", maximize=True)
    assert best.train_run_hash == "b" * 64


def test_get_best_experiment_minimize(tmp_path):
    store = ExperimentStore(tmp_path)
    store.write_metadata(_reg_run("a" * 64, cost=0.05))
    store.write_metadata(_reg_run("b" * 64, cost=0.01))
    store.write_metadata(_reg_run("c" * 64, cost=0.03))
    best = get_best_experiment(store=store, metric="total_transaction_cost", maximize=False)
    assert best.train_run_hash == "b" * 64


def test_get_best_experiment_deterministic_tie_break(tmp_path):
    store = ExperimentStore(tmp_path)
    store.write_metadata(_reg_run("b" * 64, sharpe=1.0))
    store.write_metadata(_reg_run("a" * 64, sharpe=1.0))   # tie -> smaller hash wins
    best = get_best_experiment(store=store, metric="sharpe", maximize=True)
    assert best.train_run_hash == "a" * 64


def test_get_best_experiment_no_runs_raises(tmp_path):
    store = ExperimentStore(tmp_path)
    with pytest.raises(ExperimentError):
        get_best_experiment(store=store, metric="sharpe")


def test_get_best_experiment_missing_metric_raises(tmp_path):
    store = ExperimentStore(tmp_path)
    store.write_metadata(_reg_run("a" * 64))
    with pytest.raises(ExperimentError):
        get_best_experiment(store=store, metric="does_not_exist")


def test_registry_module_no_network():
    import app.experiments.registry as registry_mod

    src = inspect.getsource(registry_mod)
    assert not re.search(r"\b(import|from)\s+(requests|urllib|httpx|socket|aiohttp)\b", src)
    assert not re.search(r"\b(import|from)\s+(pickle|joblib|cloudpickle)\b", src)


# --------------------------------------------------------------------------- #
# Commit 4 — save_experiment_run (Phase 4 evaluation -> persisted run)
# --------------------------------------------------------------------------- #


def _trained_full(h: str = "a" * 64) -> TrainedModel:
    spec = _model_spec()
    md = {
        "continuous_config_hash": "c" * 64,
        "feature_config_hash": "f" * 64,
        "label_config_hash": "l" * 64,
        "dataset_config_hash": "d" * 64,
        "model_config_hash": "m" * 64,
        "train_run_hash": h,
        "model_type": "ridge_regression",
        "task_type": "regression",
    }
    return TrainedModel(
        model=None,
        spec=spec,
        feature_columns=tuple(spec.feature_columns),
        label_column=spec.label_column,
        train_index=np.array([], dtype=int),
        fitted_params={"coef_": np.array([2.0, -1.0]), "intercept_": 0.5, "alpha": 1.0},
        model_config_hash="m" * 64,
        dataset_config_hash="d" * 64,
        train_run_hash=h,
        metadata=md,
    )


def _signals_df(n: int = 5) -> pd.DataFrame:
    ts = pd.date_range("2024-07-01", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "root_symbol": "ES",
            "active_contract": "ESH24",
            "prediction": np.arange(n, dtype=float),
            "prediction_proba": np.linspace(0.4, 0.6, n),
            "target_position": np.array([1.0, 0.0, -1.0, 1.0, 0.0])[:n],
            "signal_state": "long",
        }
    )


def _bt_frame(n: int = 5) -> pd.DataFrame:
    ts = pd.date_range("2024-07-01", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "target_position": np.array([0.0, 1.0, 1.0, -1.0, 0.0])[:n],
            "effective_position": np.array([0.0, 0.0, 1.0, 1.0, -1.0])[:n],
            "strategy_return": np.array([0.0, 0.0, 0.01, -0.005, 0.0])[:n],
            "net_strategy_return": np.array([0.0, 0.0, 0.009, -0.006, 0.0])[:n],
            "equity": np.array([10000.0, 10000.0, 10090.0, 10030.0, 10030.0])[:n],
            "roll_flag": False,
        }
    )


def _eval_full() -> MlEvaluationResult:
    return MlEvaluationResult(
        signals=_signals_df(),
        ml_backtest=types.SimpleNamespace(frame=_bt_frame()),
        backtest_metrics={"sharpe": 1.0, "total_return": 0.03, "max_drawdown": -0.05,
                          "turnover": 2.0, "total_transaction_cost": 0.01, "final_equity": 10030.0},
        classification_metrics=None,
        regression_metrics={"r2": 0.2, "mse": 0.001, "information_coefficient": 0.15, "n_scored": 4},
        no_trade_baseline={"backtest_metrics": {"total_return": 0.0, "sharpe": 0.0}},
        momentum_baseline={"backtest_metrics": {"total_return": 0.01, "sharpe": 0.3}},
        metadata={"n_oos_rows": 5, "n_scored_rows": 4},
    )


_AT = "2026-06-25T00:00:00+00:00"


def test_save_experiment_run_writes_all_files(tmp_path):
    store = ExperimentStore(tmp_path)
    run = save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    rd = tmp_path / ("a" * 64)
    for fn in ("metadata.json", "model_params.json", "metrics.json",
               "predictions.csv", "signal.csv", "backtest.csv"):
        assert (rd / fn).exists()
    assert isinstance(run, ExperimentRun)


def test_saved_metadata_artifact_paths_relative(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    loaded = load_experiment_run("a" * 64, store=store).run
    assert set(loaded.artifact_paths) >= {"metadata", "model_params", "metrics",
                                          "predictions", "signal", "backtest"}
    for value in loaded.artifact_paths.values():
        assert not value.startswith(("/", "\\"))
        assert not re.match(r"^[A-Za-z]:", value)


def test_saved_model_params_is_json_no_pickle(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    mp = store.read_model_params("a" * 64)
    assert mp["model_type"] == "ridge_regression"
    assert mp["feature_columns"] == ["feature__return_20", "feature__moving_average_gap_10_50"]
    assert mp["params"]["coef_"] == [2.0, -1.0]        # numpy array -> JSON list
    assert mp["params"]["intercept_"] == 0.5
    text = (tmp_path / ("a" * 64) / "model_params.json").read_text(encoding="utf-8")
    assert text.strip().startswith("{")
    names = [q.name for q in tmp_path.rglob("*") if q.is_file()]
    assert not any(n.endswith((".pkl", ".pickle", ".joblib")) for n in names)


def test_saved_metrics_contains_task_backtest_baseline(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    m = store.read_metrics("a" * 64)
    assert m["task_metrics"]["r2"] == 0.2
    assert m["backtest_metrics"]["sharpe"] == 1.0
    assert m["baseline_metrics"]["no_trade"]["total_return"] == 0.0
    assert m["baseline_metrics"]["momentum"]["sharpe"] == 0.3
    assert m["metadata"]["train_run_hash"] == "a" * 64
    assert m["metadata"]["model_config_hash"] == "m" * 64
    assert m["metadata"]["dataset_config_hash"] == "d" * 64
    assert m["metadata"]["n_oos_rows"] == 5 and m["metadata"]["n_scored_rows"] == 4


def test_save_then_load_roundtrips_frames(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    loaded = load_experiment_run("a" * 64, store=store, load_frames=True)
    assert set(loaded.frames) == {"predictions", "signal", "backtest"}
    assert "prediction" in loaded.frames["predictions"].columns
    assert "target_position" in loaded.frames["signal"].columns
    assert "equity" in loaded.frames["backtest"].columns
    assert len(loaded.frames["predictions"]) == 5


def test_overwrite_false_rejects_duplicate(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    with pytest.raises(ExperimentError):
        save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)


def test_overwrite_true_rewrites_deterministically(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    before = (tmp_path / ("a" * 64) / "metadata.json").read_bytes()
    run2 = save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store,
                               overwrite=True, created_at=_AT)
    after = (tmp_path / ("a" * 64) / "metadata.json").read_bytes()
    assert before == after        # deterministic for the same inputs + created_at
    assert isinstance(run2, ExperimentRun)


def test_save_writes_only_under_base_dir(tmp_path):
    base = tmp_path / "artifacts" / "experiments"
    store = ExperimentStore(base)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    files = [q for q in tmp_path.rglob("*") if q.is_file()]
    assert files and all(q.is_relative_to(base) for q in files)


def test_save_creates_no_repo_artifacts_dir(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    backend_dir = Path(__file__).resolve().parents[1]
    repo_root = backend_dir.parent
    assert not (repo_root / "artifacts").exists()
    assert not (backend_dir / "artifacts").exists()


def test_missing_artifact_after_save_raises(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    (tmp_path / ("a" * 64) / "predictions.csv").unlink()   # remove a referenced artifact
    with pytest.raises(ExperimentError):
        load_experiment_run("a" * 64, store=store)


def test_saved_metadata_hashes_match_trained_model(tmp_path):
    store = ExperimentStore(tmp_path)
    tm = _trained_full("a" * 64)
    run = save_experiment_run(tm, _eval_full(), store=store, created_at=_AT)
    assert run.train_run_hash == tm.train_run_hash
    assert run.model_config_hash == tm.model_config_hash
    assert run.dataset_config_hash == tm.dataset_config_hash
    assert run.continuous_config_hash == tm.metadata["continuous_config_hash"]
    assert run.feature_config_hash == tm.metadata["feature_config_hash"]
    assert run.label_config_hash == tm.metadata["label_config_hash"]


def test_no_absolute_paths_in_saved_metadata(tmp_path):
    store = ExperimentStore(tmp_path)
    save_experiment_run(_trained_full("a" * 64), _eval_full(), store=store, created_at=_AT)
    text = (tmp_path / ("a" * 64) / "metadata.json").read_text(encoding="utf-8")
    assert "C:\\quantlab" not in text
    assert "C:/quantlab" not in text
    assert str(tmp_path) not in text      # no absolute base path leaked into metadata


def test_summarize_experiment(tmp_path):
    run = _reg_run("a" * 64, sharpe=1.5)
    summary = summarize_experiment(run)
    assert summary["train_run_hash"] == "a" * 64
    assert summary["sharpe"] == 1.5
    text = summarize_experiment(run, as_text=True)
    assert isinstance(text, str) and "experiment" in text


def test_save_and_reports_modules_no_network():
    import app.experiments.registry as registry_mod
    import app.experiments.reports as reports_mod

    for mod in (registry_mod, reports_mod):
        src = inspect.getsource(mod)
        assert not re.search(r"\b(import|from)\s+(requests|urllib|httpx|socket|aiohttp)\b", src)
        assert not re.search(r"\b(import|from)\s+(pickle|joblib|cloudpickle)\b", src)
