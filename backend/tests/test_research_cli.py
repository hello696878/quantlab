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
from app.research_cli import (
    ExperimentConfig,
    SyntheticDataConfig,
    generate_synthetic_es_raw,
    resolve_artifact_base_dir,
)

_ES = get_instrument("ES")


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
