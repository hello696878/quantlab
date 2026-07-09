"""
Phase 11 commit 1 — local experiment batch config + deterministic grid expansion.

Covers the *config layer only*: ``LocalExperimentBatchConfig``, ``expand_grid``,
and ``batch_item_id`` from ``app.batch_experiments``.  No Phase 9 experiments are
run, no ``ExperimentStore`` is written, and nothing touches the network — these
tests are pure and offline.  Later commits add the runner, CLI, and e2e tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.batch_experiments import (
    BatchError,
    LocalExperimentBatchConfig,
    LocalExperimentBatchItem,
    LocalExperimentBatchResult,
    batch_config_hash,
    batch_item_id,
    expand_grid,
    run_local_experiment_batch,
    summarize_batch_result,
)
from app.batch_experiments import config as batch_config_module
from app.datastore.store import RawFuturesStore
from app.experiments import ExperimentStore
from app.local_pipeline import LocalExperimentConfig
from app.ml_signal import ModelType
from app.research_cli.config import ExperimentConfig
from app.research_cli.synthetic import generate_synthetic_es_raw

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _base() -> LocalExperimentConfig:
    return LocalExperimentConfig(source="synthetic")


def _raw_store(tmp_path: Path) -> RawFuturesStore:
    """Synthetic ES raw (3 contracts) written into a tmp RawFuturesStore under
    source='synthetic' — the proven Phase 9 test fixture (enough rows for warmup
    + a train/val split)."""
    raw = generate_synthetic_es_raw(ExperimentConfig())
    store = RawFuturesStore(tmp_path / "store", prefer_parquet=False)
    store.write_raw(raw)
    return store


def _exp_store(tmp_path: Path) -> ExperimentStore:
    return ExperimentStore(tmp_path / "exp", prefer_parquet=False)


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


# --------------------------------------------------------------------------- #
# run_local_experiment_batch — happy path + provenance
# --------------------------------------------------------------------------- #


def test_run_batch_success_saves_each_run(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = expand_grid(_base(), {"random_seed": [0, 1, 2]})

    result = run_local_experiment_batch(raw, configs, experiment_store=exp)

    assert isinstance(result, LocalExperimentBatchResult)
    assert (result.n_total, result.n_ok, result.n_failed, result.n_skipped) == (3, 3, 0, 0)
    # every item ok, with a full hash chain and a store-relative artifact dir
    for it in result.items:
        assert isinstance(it, LocalExperimentBatchItem)
        assert it.status == "ok"
        assert it.train_run_hash
        assert it.hash_chain and it.hash_chain["train_run_hash"] == it.train_run_hash
        assert set(it.hash_chain) == {
            "raw_data_version_hash",
            "continuous_config_hash",
            "feature_config_hash",
            "label_config_hash",
            "dataset_config_hash",
            "model_config_hash",
            "train_run_hash",
        }
        # relative / safe: the run dir name == the hash, no drive/leading-slash
        assert it.artifact_dir == it.train_run_hash
        assert (exp.base_dir / it.artifact_dir / "metadata.json").exists()


def test_run_batch_train_run_hashes_in_execution_order(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = expand_grid(_base(), {"random_seed": [0, 1, 2]})

    result = run_local_experiment_batch(raw, configs, experiment_store=exp)

    ok_hashes = tuple(it.train_run_hash for it in result.items if it.status == "ok")
    assert result.train_run_hashes == ok_hashes
    # distinct configs (varying seed) -> distinct train_run_hashes
    assert len(set(result.train_run_hashes)) == 3


def test_run_batch_item_ids_stable_and_ordered(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = expand_grid(_base(), {"random_seed": [0, 1]})

    result = run_local_experiment_batch(raw, configs, experiment_store=exp)
    assert [it.item_id for it in result.items] == ["item_0000", "item_0001"]


# --------------------------------------------------------------------------- #
# run_local_experiment_batch — validation + dry-run
# --------------------------------------------------------------------------- #


def test_run_batch_empty_configs_raises_batch_error(tmp_path):
    exp = _exp_store(tmp_path)
    with pytest.raises(BatchError):
        run_local_experiment_batch(_raw_store(tmp_path), [], experiment_store=exp)


def test_run_batch_invalid_on_error_raises_batch_error(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    with pytest.raises(BatchError):
        run_local_experiment_batch(raw, [_base()], experiment_store=exp, on_error="halt")


def test_run_batch_dry_run_writes_nothing(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = expand_grid(_base(), {"random_seed": [0, 1]})

    result = run_local_experiment_batch(raw, configs, experiment_store=exp, dry_run=True)

    assert (result.n_total, result.n_ok, result.n_failed, result.n_skipped) == (2, 0, 0, 2)
    assert result.train_run_hashes == ()
    for it in result.items:
        assert it.status == "skipped"
        assert it.train_run_hash is None
        assert it.error  # a skip reason is recorded
    # nothing persisted under the experiment store
    assert not exp.base_dir.exists() or not any(exp.base_dir.iterdir())


# --------------------------------------------------------------------------- #
# run_local_experiment_batch — error policy
# --------------------------------------------------------------------------- #


def test_run_batch_continue_on_error_records_and_proceeds(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = [
        LocalExperimentConfig(source="synthetic", random_seed=0),
        LocalExperimentConfig(source="missing"),  # no such data -> Phase 9 run fails
        LocalExperimentConfig(source="synthetic", random_seed=1),
    ]

    result = run_local_experiment_batch(raw, configs, experiment_store=exp, on_error="continue")

    assert (result.n_total, result.n_ok, result.n_failed, result.n_skipped) == (3, 2, 1, 0)
    statuses = [it.status for it in result.items]
    assert statuses == ["ok", "failed", "ok"]
    assert result.items[1].error and ":" in result.items[1].error
    # only successful items contribute hashes, in order
    assert result.train_run_hashes == (result.items[0].train_run_hash, result.items[2].train_run_hash)


def test_run_batch_stop_on_error_skips_remaining(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = [
        LocalExperimentConfig(source="synthetic", random_seed=0),
        LocalExperimentConfig(source="missing"),  # fails -> stop
        LocalExperimentConfig(source="synthetic", random_seed=1),
    ]

    result = run_local_experiment_batch(raw, configs, experiment_store=exp, on_error="stop")

    assert (result.n_total, result.n_ok, result.n_failed, result.n_skipped) == (3, 1, 1, 1)
    assert [it.status for it in result.items] == ["ok", "failed", "skipped"]
    assert result.items[2].train_run_hash is None
    assert "stopped" in result.items[2].error


# --------------------------------------------------------------------------- #
# run_local_experiment_batch — duplicate / overwrite behavior
# --------------------------------------------------------------------------- #


def test_run_batch_duplicate_without_overwrite_fails(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    cfg = LocalExperimentConfig(source="synthetic")  # overwrite defaults to False

    first = run_local_experiment_batch(raw, [cfg], experiment_store=exp)
    assert first.n_ok == 1

    second = run_local_experiment_batch(raw, [cfg], experiment_store=exp)
    assert second.n_failed == 1
    assert "already exists" in second.items[0].error


def test_run_batch_duplicate_with_overwrite_succeeds(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    cfg = LocalExperimentConfig(source="synthetic", overwrite=True)

    first = run_local_experiment_batch(raw, [cfg], experiment_store=exp)
    second = run_local_experiment_batch(raw, [cfg], experiment_store=exp)
    assert first.n_ok == 1 and second.n_ok == 1
    assert first.train_run_hashes == second.train_run_hashes  # same identity, re-saved


# --------------------------------------------------------------------------- #
# batch_config_hash — manifest fingerprint (not ML lineage)
# --------------------------------------------------------------------------- #


def test_batch_config_hash_deterministic_and_sensitive():
    configs = expand_grid(_base(), {"random_seed": [0, 1]})
    h1 = batch_config_hash(configs, on_error="continue", dry_run=False)
    h2 = batch_config_hash(configs, on_error="continue", dry_run=False)
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 64  # full sha-256 hex

    # order-sensitive
    assert batch_config_hash(list(reversed(configs)), on_error="continue", dry_run=False) != h1
    # policy-sensitive
    assert batch_config_hash(configs, on_error="stop", dry_run=False) != h1
    assert batch_config_hash(configs, on_error="continue", dry_run=True) != h1


def test_batch_config_hash_is_not_train_run_hash(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = expand_grid(_base(), {"random_seed": [0, 1]})

    result = run_local_experiment_batch(raw, configs, experiment_store=exp)
    # the manifest fingerprint matches the standalone helper ...
    assert result.batch_config_hash == batch_config_hash(
        configs, on_error="continue", dry_run=False
    )
    # ... and is distinct from every per-run ML lineage hash
    assert result.batch_config_hash not in result.train_run_hashes


# --------------------------------------------------------------------------- #
# summarize_batch_result — deterministic + JSON-safe
# --------------------------------------------------------------------------- #


def test_summarize_batch_result_deterministic_and_json_safe(tmp_path):
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = expand_grid(_base(), {"random_seed": [0, 1]})
    result = run_local_experiment_batch(raw, configs, experiment_store=exp)

    summary = summarize_batch_result(result)
    assert summarize_batch_result(result) == summary  # deterministic

    # strict JSON round-trip (no NaN / Infinity), stable key order
    text = json.dumps(summary, allow_nan=False, sort_keys=True)
    assert json.loads(text)["batch_config_hash"] == result.batch_config_hash

    assert summary["n_ok"] == 2
    assert summary["train_run_hashes"] == list(result.train_run_hashes)
    assert [it["item_id"] for it in summary["items"]] == ["item_0000", "item_0001"]
    for it in summary["items"]:
        ad = it["artifact_dir"]
        assert ad is None or (":" not in ad and not ad.startswith("/"))  # no absolute paths


# --------------------------------------------------------------------------- #
# guard rails — no forbidden imports, no ML internals, no Phase 10, no repo writes
# --------------------------------------------------------------------------- #


def test_runner_module_has_no_forbidden_imports():
    from app.batch_experiments import runner as runner_module

    src = Path(runner_module.__file__).read_text(encoding="utf-8")
    forbidden = [
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
        assert token not in src, f"runner.py must not reference {token!r}"


def test_runner_module_has_no_ml_internals_or_phase10_reporting():
    from app.batch_experiments import runner as runner_module

    src = Path(runner_module.__file__).read_text(encoding="utf-8")
    for token in ("train_model", "build_feature_matrix", "build_label_matrix"):
        assert token not in src, f"runner.py must not touch ML internal {token!r}"
    assert "app.reporting" not in src
    assert "from app.reporting" not in src
    assert "import reporting" not in src


def test_runner_reuses_existing_hash_helper_no_new_chain():
    from app.batch_experiments import runner as runner_module

    src = Path(runner_module.__file__).read_text(encoding="utf-8")
    # reuses the existing reproducibility helper, not raw hashlib / a new chain
    assert "compute_config_hash" in src
    assert "hashlib" not in src
    assert "sha256" not in src


def test_run_batch_creates_no_repo_artifacts(tmp_path):
    before = _repo_snapshot()
    raw = _raw_store(tmp_path)
    exp = _exp_store(tmp_path)
    configs = expand_grid(_base(), {"random_seed": [0, 1]})
    run_local_experiment_batch(raw, configs, experiment_store=exp)
    assert _repo_snapshot() == before
