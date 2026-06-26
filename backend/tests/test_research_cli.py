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
import json

from app.research_cli import (
    ExperimentConfig,
    ExperimentResult,
    SyntheticDataConfig,
    generate_synthetic_es_raw,
    resolve_artifact_base_dir,
    run_es_ml_experiment,
)
from app.research_cli.cli import main as cli_main

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


# --------------------------------------------------------------------------- #
# Commit 3 — argparse CLI (run / list / compare / best) + scripts
# --------------------------------------------------------------------------- #


def _saved_run(base, **over):
    return run_es_ml_experiment(_exp_config(created_at=_AT, artifact_base_dir=str(base), **over))


def test_cli_run_exits_zero_and_human_output(tmp_path, capsys):
    rc = cli_main(["run", "--artifacts-dir", str(tmp_path / "exp"), "--created-at", _AT])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SYNTHETIC DEMO" in out
    assert "train_run_hash:" in out
    assert str(tmp_path / "exp") in out          # artifact directory printed (console-only)


def test_cli_run_json_parses(tmp_path, capsys):
    rc = cli_main(["run", "--artifacts-dir", str(tmp_path / "exp"), "--created-at", _AT, "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_source"] == "synthetic"
    assert payload["train_run_hash"] and payload["artifact_dir"]


def test_cli_list_shows_run(tmp_path, capsys):
    base = tmp_path / "exp"
    result = _saved_run(base)
    rc = cli_main(["list", "--artifacts-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 0
    assert result.train_run_hash[:12] in out


def test_cli_list_json_parses(tmp_path, capsys):
    base = tmp_path / "exp"
    _saved_run(base)
    rc = cli_main(["list", "--artifacts-dir", str(base), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and len(payload) >= 1


def test_cli_compare_same_window(tmp_path, capsys):
    base = tmp_path / "exp"
    a = _saved_run(base, hyperparameters={"alpha": 1.0})
    b = _saved_run(base, hyperparameters={"alpha": 0.01})
    rc = cli_main(["compare", a.train_run_hash, b.train_run_hash, "--artifacts-dir", str(base)])
    out = capsys.readouterr().out
    assert rc == 0
    assert a.train_run_hash in out and b.train_run_hash in out


def test_cli_compare_json_parses(tmp_path, capsys):
    base = tmp_path / "exp"
    a = _saved_run(base, hyperparameters={"alpha": 1.0})
    b = _saved_run(base, hyperparameters={"alpha": 0.01})
    rc = cli_main(["compare", a.train_run_hash, b.train_run_hash,
                   "--artifacts-dir", str(base), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and len(payload) == 2


def test_cli_compare_rejects_different_window(tmp_path, capsys):
    base = tmp_path / "exp"
    a = _saved_run(base)
    b = _saved_run(base, validation_end=date(2024, 8, 30))   # different OOS window
    rc = cli_main(["compare", a.train_run_hash, b.train_run_hash, "--artifacts-dir", str(base)])
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_cli_best(tmp_path, capsys):
    base = tmp_path / "exp"
    _saved_run(base, hyperparameters={"alpha": 1.0})
    _saved_run(base, hyperparameters={"alpha": 0.01})
    rc = cli_main(["best", "--artifacts-dir", str(base), "--metric", "sharpe"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "sharpe" in out


def test_cli_best_json_parses(tmp_path, capsys):
    base = tmp_path / "exp"
    _saved_run(base, hyperparameters={"alpha": 1.0})
    _saved_run(base, hyperparameters={"alpha": 0.01})
    rc = cli_main(["best", "--artifacts-dir", str(base), "--metric", "sharpe", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["metric"] == "sharpe" and payload["train_run_hash"]


def test_wrapper_scripts_exist_and_are_thin():
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    mapping = {
        "run_es_ml_experiment.py": '"run"',
        "list_experiments.py": '"list"',
        "compare_experiments.py": '"compare"',
        "show_best_experiment.py": '"best"',
    }
    for filename, subcommand in mapping.items():
        path = scripts_dir / filename
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "from app.research_cli.cli import main" in text
        assert subcommand in text
        assert len(text.splitlines()) <= 15        # thin wrapper


def test_cli_creates_no_repo_artifacts_dir(tmp_path):
    cli_main(["run", "--artifacts-dir", str(tmp_path / "exp"), "--created-at", _AT])
    backend_dir = Path(__file__).resolve().parents[1]
    assert not (backend_dir.parent / "artifacts").exists()
    assert not (backend_dir / "artifacts").exists()


def test_cli_render_modules_no_forbidden_imports():
    import app.research_cli.cli as cli_mod
    import app.research_cli.render as render_mod

    for mod in (cli_mod, render_mod):
        src = inspect.getsource(mod)
        assert not re.search(
            r"\b(import|from)\s+(click|typer|rich|yaml|requests|urllib|httpx|socket|sklearn|xgboost)\b",
            src,
        )


# --------------------------------------------------------------------------- #
# Commit 4 — reproducibility / overwrite / compare-guard / output expansion
# --------------------------------------------------------------------------- #


def _cli_run_json(capsys, *extra) -> dict:
    rc = cli_main(["run", "--json", *extra])
    assert rc == 0
    return json.loads(capsys.readouterr().out)


# --- reproducibility ---


def test_full_config_reproducible_all_hashes(tmp_path):
    cfg = _exp_config(created_at=_AT, random_seed=7,
                      synthetic=SyntheticDataConfig(noise_scale=2.0, random_seed=7))
    a = run_es_ml_experiment(cfg, store=ExperimentStore(tmp_path / "a"))
    b = run_es_ml_experiment(cfg, store=ExperimentStore(tmp_path / "b"))
    for attr in ("continuous_config_hash", "feature_config_hash", "label_config_hash",
                 "dataset_config_hash", "model_config_hash", "train_run_hash"):
        assert getattr(a, attr) == getattr(b, attr)
    assert (a.artifact_dir / "metadata.json").read_bytes() == (b.artifact_dir / "metadata.json").read_bytes()


def test_synthetic_seed_changes_hash(tmp_path):
    a = run_es_ml_experiment(
        _exp_config(created_at=_AT, synthetic=SyntheticDataConfig(noise_scale=5.0, random_seed=1)),
        store=ExperimentStore(tmp_path / "a"),
    )
    b = run_es_ml_experiment(
        _exp_config(created_at=_AT, synthetic=SyntheticDataConfig(noise_scale=5.0, random_seed=2)),
        store=ExperimentStore(tmp_path / "b"),
    )
    assert a.dataset_config_hash != b.dataset_config_hash   # via the raw->continuous->label chain
    assert a.train_run_hash != b.train_run_hash


def test_alpha_changes_model_hash_only(tmp_path):
    a = run_es_ml_experiment(_exp_config(created_at=_AT, hyperparameters={"alpha": 1.0}),
                             store=ExperimentStore(tmp_path / "a"))
    b = run_es_ml_experiment(_exp_config(created_at=_AT, hyperparameters={"alpha": 0.01}),
                             store=ExperimentStore(tmp_path / "b"))
    assert a.model_config_hash != b.model_config_hash
    assert a.train_run_hash != b.train_run_hash
    assert a.continuous_config_hash == b.continuous_config_hash   # data unchanged
    assert a.dataset_config_hash == b.dataset_config_hash


def test_cli_run_overwrite_deterministic(tmp_path, capsys):
    args = ["--artifacts-dir", str(tmp_path / "exp"), "--created-at", _AT, "--overwrite"]
    p1 = _cli_run_json(capsys, *args)
    meta1 = (Path(p1["artifact_dir"]) / "metadata.json").read_bytes()
    p2 = _cli_run_json(capsys, *args)
    meta2 = (Path(p2["artifact_dir"]) / "metadata.json").read_bytes()
    assert p1["train_run_hash"] == p2["train_run_hash"]
    assert meta1 == meta2


# --- overwrite behavior via CLI ---


def test_cli_run_duplicate_rejected(tmp_path, capsys):
    args = ["--artifacts-dir", str(tmp_path / "exp"), "--created-at", _AT]
    assert cli_main(["run", *args]) == 0
    capsys.readouterr()
    rc = cli_main(["run", *args])   # duplicate, no --overwrite
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_cli_run_duplicate_with_overwrite_succeeds(tmp_path, capsys):
    args = ["--artifacts-dir", str(tmp_path / "exp"), "--created-at", _AT]
    assert cli_main(["run", *args]) == 0
    capsys.readouterr()
    assert cli_main(["run", *args, "--overwrite"]) == 0


def test_overwrite_removes_stale_artifacts(tmp_path):
    store = ExperimentStore(tmp_path / "exp")
    result = run_es_ml_experiment(_exp_config(created_at=_AT), store=store)
    stale = result.artifact_dir / "stale.txt"
    stale.write_text("leftover", encoding="utf-8")
    assert stale.exists()
    run_es_ml_experiment(_exp_config(created_at=_AT, overwrite=True), store=store)
    assert not stale.exists()
    names = sorted(p.name for p in result.artifact_dir.iterdir())
    assert names == sorted(
        ["metadata.json", "model_params.json", "metrics.json",
         "predictions.csv", "signal.csv", "backtest.csv"]
    )


# --- compare guard via CLI ---


def test_cli_compare_different_dataset_rejected(tmp_path, capsys):
    base = tmp_path / "exp"
    a = _saved_run(base, feature_columns=("feature__return_20", "feature__moving_average_gap_10_50"))
    b = _saved_run(base, feature_columns=("feature__return_20", "feature__realized_vol_20"))
    assert a.dataset_config_hash != b.dataset_config_hash
    rc = cli_main(["compare", a.train_run_hash, b.train_run_hash, "--artifacts-dir", str(base)])
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_cli_compare_different_label_rejected(tmp_path, capsys):
    base = tmp_path / "exp"
    a = _saved_run(base, label_column="label__forward_return_1")
    b = _saved_run(base, label_column="label__forward_return_5")
    rc = cli_main(["compare", a.train_run_hash, b.train_run_hash, "--artifacts-dir", str(base)])
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_cli_compare_allow_different_windows_json_marks_same_window(tmp_path, capsys):
    base = tmp_path / "exp"
    a = _saved_run(base)
    b = _saved_run(base, validation_end=date(2024, 8, 30))   # different OOS window
    rc = cli_main(["compare", a.train_run_hash, b.train_run_hash,
                   "--artifacts-dir", str(base), "--allow-different-windows", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and len(payload) == 2
    assert all("same_window" in record for record in payload)


# --- output behavior ---


def test_cli_run_human_output_sections(tmp_path, capsys):
    rc = cli_main(["run", "--artifacts-dir", str(tmp_path / "exp"), "--created-at", _AT])
    out = capsys.readouterr().out
    assert rc == 0
    for token in ("SYNTHETIC DEMO", "train_run_hash:", "artifact_dir:", "reproduce:"):
        assert token in out


def test_cli_run_json_full_fields(tmp_path, capsys):
    payload = _cli_run_json(capsys, "--artifacts-dir", str(tmp_path / "exp"), "--created-at", _AT)
    for key in ("data_source", "train_run_hash", "artifact_dir", "model_type",
                "label_column", "validation_start", "validation_end", "backtest_metrics"):
        assert key in payload
    assert payload["data_source"] == "synthetic"
    assert payload["model_type"] == "ridge_regression"
    assert payload["label_column"] == "label__forward_return_1"
    assert "sharpe" in payload["backtest_metrics"]


# --- safety: consolidated source scan over all research_cli modules ---


def test_all_research_cli_modules_no_forbidden_imports():
    import app.research_cli.config as config_mod
    import app.research_cli.synthetic as synthetic_mod
    import app.research_cli.pipeline as pipeline_mod
    import app.research_cli.cli as cli_mod
    import app.research_cli.render as render_mod

    for mod in (config_mod, synthetic_mod, pipeline_mod, cli_mod, render_mod):
        src = inspect.getsource(mod)
        assert not re.search(
            r"\b(import|from)\s+(pickle|joblib|cloudpickle|click|typer|rich|yaml|"
            r"requests|urllib|httpx|socket|aiohttp|sklearn|xgboost|lightgbm|torch|tensorflow)\b",
            src,
        )


# --------------------------------------------------------------------------- #
# Commit 5 — final one-command CLI end-to-end: run -> load -> list -> compare -> best
# --------------------------------------------------------------------------- #


def _cli_capture(capsys, args, expect_rc=0) -> str:
    rc = cli_main(args)
    assert rc == expect_rc
    return capsys.readouterr().out


def test_cli_end_to_end_run_load_list_compare_best(tmp_path, capsys):
    base = tmp_path / "exp"

    # two same-window runs via the actual CLI (different ridge alpha)
    p1 = json.loads(_cli_capture(
        capsys, ["run", "--artifacts-dir", str(base), "--created-at", _AT, "--alpha", "1.0", "--json"]))
    p2 = json.loads(_cli_capture(
        capsys, ["run", "--artifacts-dir", str(base), "--created-at", _AT, "--alpha", "0.01", "--json"]))
    for payload in (p1, p2):
        assert payload["data_source"] == "synthetic"
        assert payload["train_run_hash"] and payload["artifact_dir"]
    h1, h2 = p1["train_run_hash"], p2["train_run_hash"]
    assert h1 != h2

    # load both back through Phase 5 with frames; verify relative artifact paths
    store = ExperimentStore(base)
    for h in (h1, h2):
        loaded = load_experiment_run(h, store=store, load_frames=True)
        assert set(loaded.frames) == {"predictions", "signal", "backtest"}
        for value in loaded.run.artifact_paths.values():
            assert not value.startswith(("/", "\\")) and not re.match(r"^[A-Za-z]:", value)
        text = (base / h / "metadata.json").read_text(encoding="utf-8")
        assert "C:\\quantlab" not in text and "C:/quantlab" not in text and str(tmp_path) not in text

    # list --json shows both
    listed = json.loads(_cli_capture(capsys, ["list", "--artifacts-dir", str(base), "--json"]))
    assert {r["train_run_hash"] for r in listed} >= {h1, h2}

    # compare --json returns two rows (same-window guard satisfied)
    compared = json.loads(_cli_capture(
        capsys, ["compare", h1, h2, "--artifacts-dir", str(base), "--json"]))
    assert isinstance(compared, list) and len(compared) == 2

    # best --json returns one of the saved hashes
    best = json.loads(_cli_capture(
        capsys, ["best", "--artifacts-dir", str(base), "--metric", "sharpe", "--json"]))
    assert best["metric"] == "sharpe" and best["train_run_hash"] in {h1, h2}

    # every artifact under tmp_path; no pickle; no repo-root artifacts dir
    files = [q for q in tmp_path.rglob("*") if q.is_file()]
    assert files and all(q.is_relative_to(base) for q in files)
    assert not any(q.name.endswith((".pkl", ".pickle", ".joblib")) for q in files)
    backend_dir = Path(__file__).resolve().parents[1]
    assert not (backend_dir.parent / "artifacts").exists()
    assert not (backend_dir / "artifacts").exists()


def test_wrappers_have_no_business_logic():
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    for filename in ("run_es_ml_experiment.py", "list_experiments.py",
                     "compare_experiments.py", "show_best_experiment.py"):
        text = (scripts_dir / filename).read_text(encoding="utf-8")
        assert "from app.research_cli.cli import main" in text
        # no pipeline / registry / config business logic in the wrappers
        assert "run_es_ml_experiment(" not in text
        assert "ExperimentStore" not in text
        assert "ExperimentConfig" not in text
        assert "save_experiment_run" not in text
