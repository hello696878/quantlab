"""
Phase 6 — commit 1: Research CLI config + synthetic ES raw-data generator.

Synthetic data only; no file I/O; no network; no model training.
"""

import inspect
import re
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from app.datastore.store import REQUIRED_COLUMNS, validate_raw_futures
from app.datastore.futures_continuous import compute_roll_schedule
from app.instruments import get_instrument
from app.ml_signal import ModelSpec, ModelType, SignalMode, TaskType, ThresholdRule, model_config_hash
from app.experiments import (
    ExperimentError,
    ExperimentStore,
    compare_experiments,
    get_best_experiment,
    list_experiments,
    load_experiment_run,
)
from app.research_cli import (
    ExperimentConfig,
    ExperimentResult,
    SyntheticDataConfig,
    generate_synthetic_es_raw,
    resolve_artifact_base_dir,
    run_es_ml_experiment,
)

_ES = get_instrument("ES")
_AT = "2026-06-25T00:00:00+00:00"


def _exp_config(**over) -> ExperimentConfig:
    return ExperimentConfig(**over)


# --------------------------------------------------------------------------- #
# SyntheticDataConfig
# --------------------------------------------------------------------------- #


def test_valid_synthetic_data_config():
    cfg = SyntheticDataConfig()
    assert cfg.root_symbol == "ES"
    assert cfg.n_contracts == 3
    assert cfg.sessions_per_contract >= 64


def test_invalid_n_contracts_rejected():
    with pytest.raises(ValidationError):
        SyntheticDataConfig(n_contracts=1)


def test_synthetic_unknown_field_forbidden():
    with pytest.raises(ValidationError):
        SyntheticDataConfig(foo=1)


# --------------------------------------------------------------------------- #
# ExperimentConfig
# --------------------------------------------------------------------------- #


def test_valid_experiment_config():
    cfg = _exp_config()
    assert cfg.root_symbol == "ES"
    assert cfg.model_type is ModelType.RIDGE_REGRESSION
    assert cfg.adjustment_method == "ratio"
    assert cfg.feature_columns[0].startswith("feature__")


def test_invalid_feature_column_rejected():
    with pytest.raises(ValidationError):
        _exp_config(feature_columns=("return_20",))


def test_invalid_label_column_rejected():
    with pytest.raises(ValidationError):
        _exp_config(label_column="forward_return_1")


def test_invalid_date_ordering_rejected():
    with pytest.raises(ValidationError):
        _exp_config(validation_start=date(2024, 5, 1))   # not after train_end


def test_non_ratio_adjustment_rejected():
    with pytest.raises(ValidationError):
        _exp_config(adjustment_method="panama")


def test_sklearn_model_type_rejected():
    for bad in ("random_forest", "gradient_boosting", "xgboost"):
        with pytest.raises(ValidationError):
            _exp_config(model_type=bad)


def test_root_symbol_mismatch_rejected():
    with pytest.raises(ValidationError):
        _exp_config(root_symbol="ES", synthetic=SyntheticDataConfig(root_symbol="NQ"))


def test_experiment_config_unknown_field_forbidden():
    with pytest.raises(ValidationError):
        _exp_config(foo=1)


# --------------------------------------------------------------------------- #
# to_model_spec
# --------------------------------------------------------------------------- #


def test_to_model_spec_maps_key_fields():
    cfg = _exp_config(
        model_type=ModelType.RIDGE_REGRESSION,
        task_type=TaskType.REGRESSION,
        feature_columns=("feature__return_20", "feature__moving_average_gap_10_50"),
        label_column="label__forward_return_1",
        prediction_horizon=1,
        random_seed=7,
        hyperparameters={"alpha": 0.5},
        threshold_rule=ThresholdRule.RETURN_THRESHOLD,
        long_threshold=0.0,
        short_threshold=0.0,
        signal_mode=SignalMode.LONG_SHORT,
    )
    spec = cfg.to_model_spec()
    assert isinstance(spec, ModelSpec)
    assert spec.model_type is ModelType.RIDGE_REGRESSION
    assert spec.task_type is TaskType.REGRESSION
    assert spec.feature_columns == cfg.feature_columns
    assert spec.label_column == cfg.label_column
    assert (spec.train_start, spec.train_end) == (cfg.train_start, cfg.train_end)
    assert (spec.validation_start, spec.validation_end) == (cfg.validation_start, cfg.validation_end)
    assert spec.prediction_horizon == 1
    assert spec.random_seed == 7
    assert spec.hyperparameters == {"alpha": 0.5}
    assert spec.threshold_rule is ThresholdRule.RETURN_THRESHOLD
    assert spec.long_threshold == 0.0 and spec.short_threshold == 0.0
    assert spec.signal_mode is SignalMode.LONG_SHORT


def test_to_model_spec_model_config_hash_stable():
    a = _exp_config(random_seed=3).to_model_spec()
    b = _exp_config(random_seed=3).to_model_spec()
    assert model_config_hash(a) == model_config_hash(b)
    c = _exp_config(random_seed=4).to_model_spec()
    assert model_config_hash(a) != model_config_hash(c)


# --------------------------------------------------------------------------- #
# Artifact directory resolution (no creation)
# --------------------------------------------------------------------------- #


def test_resolve_from_explicit_config(tmp_path):
    target = tmp_path / "artifacts" / "experiments"
    cfg = _exp_config(artifact_base_dir=str(target))
    resolved = resolve_artifact_base_dir(cfg)
    assert resolved == target
    assert not resolved.exists()        # resolution must not create the directory


def test_resolve_from_env_var(tmp_path, monkeypatch):
    env_dir = tmp_path / "env_artifacts"
    monkeypatch.setenv("QUANTLAB_ARTIFACTS_DIR", str(env_dir))
    resolved = resolve_artifact_base_dir(_exp_config())
    assert resolved == env_dir
    assert not resolved.exists()


def test_resolve_default(monkeypatch):
    monkeypatch.delenv("QUANTLAB_ARTIFACTS_DIR", raising=False)
    resolved = resolve_artifact_base_dir(_exp_config())
    assert resolved == Path("artifacts") / "experiments"


# --------------------------------------------------------------------------- #
# Synthetic generator
# --------------------------------------------------------------------------- #


def test_synthetic_deterministic_for_same_seed():
    cfg = SyntheticDataConfig(noise_scale=5.0, random_seed=11)
    pd.testing.assert_frame_equal(generate_synthetic_es_raw(cfg), generate_synthetic_es_raw(cfg))


def test_synthetic_changes_when_seed_changes():
    a = generate_synthetic_es_raw(SyntheticDataConfig(noise_scale=5.0, random_seed=1))
    b = generate_synthetic_es_raw(SyntheticDataConfig(noise_scale=5.0, random_seed=2))
    assert not a["close"].equals(b["close"])


def test_synthetic_required_columns_present():
    df = generate_synthetic_es_raw(SyntheticDataConfig())
    assert set(REQUIRED_COLUMNS).issubset(df.columns)


def test_synthetic_has_at_least_two_contracts():
    df = generate_synthetic_es_raw(SyntheticDataConfig(n_contracts=3))
    assert df["contract_symbol"].nunique() == 3


def test_synthetic_passes_validation_and_is_rollable():
    df = generate_synthetic_es_raw(SyntheticDataConfig(n_contracts=3))
    validate_raw_futures(df)                       # must not raise
    events = compute_roll_schedule(df, _ES)
    assert len(events) >= 1                         # at least one roll
    assert df["open_interest"].isna().all()         # None -> fallback roll path


def test_generate_accepts_experiment_config():
    df = generate_synthetic_es_raw(_exp_config())
    assert set(REQUIRED_COLUMNS).issubset(df.columns)
    assert df["root_symbol"].unique().tolist() == ["ES"]


def test_synthetic_seed_resolution_does_not_write(tmp_path):
    # generating + resolving must not create any file/dir under tmp_path
    generate_synthetic_es_raw(SyntheticDataConfig())
    resolve_artifact_base_dir(_exp_config(artifact_base_dir=str(tmp_path / "x")))
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- #
# Hygiene: no I/O, no network, synthetic only
# --------------------------------------------------------------------------- #


def test_config_and_synthetic_modules_no_io_or_network():
    import app.research_cli.config as config_mod
    import app.research_cli.synthetic as synthetic_mod

    for mod in (config_mod, synthetic_mod):
        src = inspect.getsource(mod)
        assert not re.search(r"\.(to_csv|to_parquet|write_text|write_bytes)\(", src)
        assert not re.search(r"\bopen\(", src)
        assert not re.search(r"\.mkdir\(|makedirs", src)
        assert not re.search(r"\b(import|from)\s+(requests|urllib|httpx|socket|aiohttp)\b", src)
        assert not re.search(r"\b(import|from)\s+(sklearn|xgboost|lightgbm|torch|tensorflow)\b", src)
        assert not re.search(r"read_csv|read_parquet", src)


# --------------------------------------------------------------------------- #
# Commit 2 — run_es_ml_experiment (full synthetic Phase 1->5 pipeline)
# --------------------------------------------------------------------------- #


def _store(tmp_path, name="experiments") -> ExperimentStore:
    return ExperimentStore(tmp_path / name)


def test_run_returns_valid_result(tmp_path):
    result = run_es_ml_experiment(_exp_config(created_at=_AT), store=_store(tmp_path))
    assert isinstance(result, ExperimentResult)
    assert (result.train_run_hash
            == result.experiment_run.train_run_hash
            == result.trained_model.train_run_hash)
    for h in (result.continuous_config_hash, result.feature_config_hash, result.label_config_hash,
              result.dataset_config_hash, result.model_config_hash, result.train_run_hash):
        assert h
    assert "sharpe" in result.backtest_metrics
    assert set(result.baseline_metrics) == {"no_trade", "momentum"}


def test_pipeline_writes_only_under_base_dir(tmp_path):
    base = tmp_path / "artifacts" / "experiments"
    run_es_ml_experiment(_exp_config(created_at=_AT), store=ExperimentStore(base))
    files = [q for q in tmp_path.rglob("*") if q.is_file()]
    assert files and all(q.is_relative_to(base) for q in files)


def test_pipeline_saves_all_files_relative_no_pickle(tmp_path):
    result = run_es_ml_experiment(_exp_config(created_at=_AT), store=_store(tmp_path))
    rd = result.artifact_dir
    for fn in ("metadata.json", "model_params.json", "metrics.json",
               "predictions.csv", "signal.csv", "backtest.csv"):
        assert (rd / fn).exists()
    text = (rd / "metadata.json").read_text(encoding="utf-8")
    assert "C:\\quantlab" not in text and "C:/quantlab" not in text and str(tmp_path) not in text
    for value in result.experiment_run.artifact_paths.values():
        assert not value.startswith(("/", "\\")) and not re.match(r"^[A-Za-z]:", value)
    names = [q.name for q in tmp_path.rglob("*") if q.is_file()]
    assert not any(n.endswith((".pkl", ".pickle", ".joblib")) for n in names)


def test_pipeline_output_loadable_with_frames(tmp_path):
    store = _store(tmp_path)
    result = run_es_ml_experiment(_exp_config(created_at=_AT), store=store)
    loaded = load_experiment_run(result.train_run_hash, store=store, load_frames=True)
    assert set(loaded.frames) == {"predictions", "signal", "backtest"}
    assert loaded.run.train_run_hash == result.train_run_hash


def test_pipeline_deterministic_train_run_hash(tmp_path):
    cfg = _exp_config(created_at=_AT)
    r1 = run_es_ml_experiment(cfg, store=_store(tmp_path, "a"))
    r2 = run_es_ml_experiment(cfg, store=_store(tmp_path, "b"))
    assert r1.train_run_hash == r2.train_run_hash


def test_overwrite_false_rejects_duplicate(tmp_path):
    store = _store(tmp_path)
    cfg = _exp_config(created_at=_AT)
    run_es_ml_experiment(cfg, store=store)
    with pytest.raises(ExperimentError):
        run_es_ml_experiment(cfg, store=store)


def test_overwrite_true_deterministic_rewrite(tmp_path):
    store = _store(tmp_path)
    r1 = run_es_ml_experiment(_exp_config(created_at=_AT), store=store)
    before = (r1.artifact_dir / "metadata.json").read_bytes()
    r2 = run_es_ml_experiment(_exp_config(created_at=_AT, overwrite=True), store=store)
    after = (r2.artifact_dir / "metadata.json").read_bytes()
    assert r1.train_run_hash == r2.train_run_hash
    assert before == after


def test_hyperparameter_changes_hash(tmp_path):
    a = run_es_ml_experiment(_exp_config(created_at=_AT, hyperparameters={"alpha": 1.0}),
                             store=_store(tmp_path, "a"))
    b = run_es_ml_experiment(_exp_config(created_at=_AT, hyperparameters={"alpha": 0.01}),
                             store=_store(tmp_path, "b"))
    assert a.model_config_hash != b.model_config_hash
    assert a.train_run_hash != b.train_run_hash
    assert a.dataset_config_hash == b.dataset_config_hash   # same window / label / features


def test_compare_and_best_same_window(tmp_path):
    store = _store(tmp_path)
    a = run_es_ml_experiment(_exp_config(created_at=_AT, hyperparameters={"alpha": 1.0}), store=store)
    b = run_es_ml_experiment(_exp_config(created_at=_AT, hyperparameters={"alpha": 0.01}), store=store)
    listed = {r.train_run_hash for r in list_experiments(store=store)}
    assert {a.train_run_hash, b.train_run_hash} <= listed
    df = compare_experiments([a.train_run_hash, b.train_run_hash], store=store)
    assert len(df) == 2 and "sharpe" in df.columns
    best = get_best_experiment(store=store, metric="sharpe", maximize=True)
    assert best.train_run_hash in (a.train_run_hash, b.train_run_hash)


def test_missing_artifact_after_save_raises(tmp_path):
    store = _store(tmp_path)
    result = run_es_ml_experiment(_exp_config(created_at=_AT), store=store)
    (result.artifact_dir / "predictions.csv").unlink()
    with pytest.raises(ExperimentError):
        load_experiment_run(result.train_run_hash, store=store)


def test_pipeline_creates_no_repo_artifacts_dir(tmp_path):
    run_es_ml_experiment(_exp_config(created_at=_AT), store=_store(tmp_path))
    backend_dir = Path(__file__).resolve().parents[1]
    assert not (backend_dir.parent / "artifacts").exists()
    assert not (backend_dir / "artifacts").exists()


def test_pipeline_module_no_network():
    import app.research_cli.pipeline as pipeline_mod

    src = inspect.getsource(pipeline_mod)
    assert not re.search(r"\b(import|from)\s+(requests|urllib|httpx|socket|aiohttp)\b", src)
    assert not re.search(r"\b(import|from)\s+(sklearn|xgboost|lightgbm|torch|tensorflow)\b", src)
    assert not re.search(r"read_csv|read_parquet", src)
