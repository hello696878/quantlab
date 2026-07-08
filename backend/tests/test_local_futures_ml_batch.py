"""
Phase 11 commit 1 — local experiment batch config + deterministic grid expansion.

Covers the *config layer only*: ``LocalExperimentBatchConfig``, ``expand_grid``,
and ``batch_item_id`` from ``app.batch_experiments``.  No Phase 9 experiments are
run, no ``ExperimentStore`` is written, and nothing touches the network — these
tests are pure and offline.  Later commits add the runner, CLI, and e2e tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.batch_experiments import (
    BatchError,
    LocalExperimentBatchConfig,
    batch_item_id,
    expand_grid,
)
from app.batch_experiments import config as batch_config_module
from app.local_pipeline import LocalExperimentConfig
from app.ml_signal import ModelType

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _base() -> LocalExperimentConfig:
    return LocalExperimentConfig(source="synthetic")


def _repo_snapshot() -> tuple[bool, bool, bool]:
    return (
        (_REPO_ROOT / "data").exists(),
        (_REPO_ROOT / "artifacts").exists(),
        (_BACKEND / "data").exists(),
    )


# --------------------------------------------------------------------------- #
# LocalExperimentBatchConfig construction
# --------------------------------------------------------------------------- #


def test_batch_config_accepts_valid_base_and_grid():
    cfg = LocalExperimentBatchConfig(base=_base(), grid={"random_seed": [0, 1]})
    assert cfg.base.source == "synthetic"
    assert cfg.grid == {"random_seed": [0, 1]}
    assert cfg.overwrite is False
    assert cfg.on_error == "continue"


def test_batch_config_accepts_stop_and_overwrite():
    cfg = LocalExperimentBatchConfig(
        base=_base(), grid={"random_seed": [0]}, on_error="stop", overwrite=True
    )
    assert cfg.on_error == "stop"
    assert cfg.overwrite is True


def test_batch_config_rejects_invalid_on_error():
    with pytest.raises(ValidationError):
        LocalExperimentBatchConfig(base=_base(), grid={"random_seed": [0]}, on_error="halt")


def test_batch_config_rejects_empty_grid():
    with pytest.raises(ValidationError):
        LocalExperimentBatchConfig(base=_base(), grid={})


def test_batch_config_rejects_unknown_grid_key():
    with pytest.raises(ValidationError):
        LocalExperimentBatchConfig(base=_base(), grid={"not_a_field": [1]})


def test_batch_config_rejects_empty_value_list():
    with pytest.raises(ValidationError):
        LocalExperimentBatchConfig(base=_base(), grid={"random_seed": []})


def test_batch_config_rejects_extra_field():
    with pytest.raises(ValidationError):
        LocalExperimentBatchConfig(base=_base(), grid={"random_seed": [0]}, bogus=1)


def test_batch_config_is_frozen():
    cfg = LocalExperimentBatchConfig(base=_base(), grid={"random_seed": [0]})
    with pytest.raises(ValidationError):
        cfg.on_error = "stop"


# --------------------------------------------------------------------------- #
# expand_grid — failure modes (BatchError)
# --------------------------------------------------------------------------- #


def test_expand_grid_empty_grid_raises_batch_error():
    with pytest.raises(BatchError):
        expand_grid(_base(), {})


def test_expand_grid_unknown_key_raises_batch_error():
    with pytest.raises(BatchError):
        expand_grid(_base(), {"nope": [1]})


def test_expand_grid_empty_value_list_raises_batch_error():
    with pytest.raises(BatchError):
        expand_grid(_base(), {"random_seed": []})


def test_expand_grid_scalar_value_raises_batch_error():
    # a bare scalar (not a list/tuple of candidates) is a spec error
    with pytest.raises(BatchError):
        expand_grid(_base(), {"random_seed": 3})


# --------------------------------------------------------------------------- #
# expand_grid — deterministic ordering + reconstruction
# --------------------------------------------------------------------------- #


def test_expand_grid_sorted_keys_and_value_order():
    # sorted keys => 'long_threshold' varies slowest, 'random_seed' fastest;
    # values preserve user-provided order within each key.
    configs = expand_grid(
        _base(), {"random_seed": [2, 5], "long_threshold": [0.0, 0.1]}
    )
    got = [(c.long_threshold, c.random_seed) for c in configs]
    assert got == [(0.0, 2), (0.0, 5), (0.1, 2), (0.1, 5)]


def test_expand_grid_single_key_preserves_value_order():
    configs = expand_grid(_base(), {"random_seed": [5, 0, 3]})
    assert [c.random_seed for c in configs] == [5, 0, 3]


def test_expand_grid_cartesian_size():
    configs = expand_grid(
        _base(), {"random_seed": [0, 1, 2], "long_threshold": [0.0, 0.5]}
    )
    assert len(configs) == 6


def test_expand_grid_model_type_override():
    configs = expand_grid(
        _base(), {"model_type": [ModelType.RIDGE_REGRESSION, ModelType.DUMMY_BASELINE]}
    )
    assert [c.model_type for c in configs] == [
        ModelType.RIDGE_REGRESSION,
        ModelType.DUMMY_BASELINE,
    ]


def test_expand_grid_reconstructs_and_reruns_validators():
    # a bad feature column must fail via LocalExperimentConfig validation on
    # reconstruction (proves each expanded config is re-validated, not copied).
    with pytest.raises(ValidationError):
        expand_grid(_base(), {"feature_columns": [("not_a_feature",)]})


def test_expand_grid_non_ratio_adjustment_fails():
    with pytest.raises(ValidationError):
        expand_grid(_base(), {"adjustment_method": ["backward"]})


def test_expand_grid_deterministic_across_calls():
    base = _base()
    grid = {"random_seed": [0, 1, 2], "long_threshold": [0.0, 0.5]}
    assert expand_grid(base, grid) == expand_grid(base, grid)


def test_expand_grid_does_not_mutate_base_or_grid():
    base = _base()
    before = base.model_dump()
    grid = {"random_seed": [7, 9]}
    expand_grid(base, grid)
    assert base.model_dump() == before
    assert base == _base()
    assert grid == {"random_seed": [7, 9]}


def test_batch_config_expand_matches_free_function():
    base = _base()
    grid = {"random_seed": [0, 1]}
    cfg = LocalExperimentBatchConfig(base=base, grid=grid)
    assert cfg.expand() == expand_grid(base, grid)


# --------------------------------------------------------------------------- #
# batch_item_id
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "index,expected",
    [(0, "item_0000"), (1, "item_0001"), (12, "item_0012"), (9999, "item_9999")],
)
def test_batch_item_id_stable(index, expected):
    assert batch_item_id(index) == expected


def test_batch_item_id_negative_raises_batch_error():
    with pytest.raises(BatchError):
        batch_item_id(-1)


# --------------------------------------------------------------------------- #
# guard rails — no forbidden imports, no hashing, no repo-root writes
# --------------------------------------------------------------------------- #


def test_config_module_has_no_forbidden_imports():
    src = Path(batch_config_module.__file__).read_text(encoding="utf-8")
    forbidden = [
        "run_local_futures_ml_experiment",
        "train_model",
        "build_feature_matrix",
        "build_label_matrix",
        "import requests",
        "urllib",
        "httpx",
        "aiohttp",
        "socket",
        "yfinance",
        "ibkr",
        "sklearn",
        "xgboost",
        "lightgbm",
        "torch",
        "tensorflow",
    ]
    for token in forbidden:
        assert token not in src, f"config.py must not reference {token!r}"


def test_config_module_defers_hashing():
    # batch_config_hash is deferred to a later commit — no hashing here.
    src = Path(batch_config_module.__file__).read_text(encoding="utf-8")
    assert "hashlib" not in src
    assert "sha256" not in src


def test_expand_grid_creates_no_repo_artifacts():
    before = _repo_snapshot()
    expand_grid(_base(), {"random_seed": [0, 1]})
    LocalExperimentBatchConfig(base=_base(), grid={"random_seed": [0]})
    assert _repo_snapshot() == before
