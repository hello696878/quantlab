"""
Phase 11 commit 1 — local experiment batch config + deterministic grid expansion.

Covers the *config layer only*: ``LocalExperimentBatchConfig``, ``expand_grid``,
and ``batch_item_id`` from ``app.batch_experiments``.  No Phase 9 experiments are
run, no ``ExperimentStore`` is written, and nothing touches the network — these
tests are pure and offline.  Later commits add the runner, CLI, and e2e tests.
"""

from __future__ import annotations

import importlib.util
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


_BATCH_CLI_PATH = _REPO_ROOT / "scripts" / "run_local_futures_ml_batch.py"


def _load_batch_cli():
    """Import the thin batch CLI module by path (executes its sys.path bootstrap)."""
    spec = importlib.util.spec_from_file_location("run_local_ml_batch_cli", _BATCH_CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_spec(
    tmp_path: Path,
    *,
    base: dict | None = None,
    grid: dict | None = None,
    overwrite=None,
    on_error=None,
    name: str = "spec.json",
) -> Path:
    """Write a batch-spec JSON file and return its path."""
    spec: dict = {
        "base": base if base is not None else {"source": "synthetic"},
        "grid": grid if grid is not None else {"random_seed": [0, 1]},
    }
    if overwrite is not None:
        spec["overwrite"] = overwrite
    if on_error is not None:
        spec["on_error"] = on_error
    path = tmp_path / name
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


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


# --------------------------------------------------------------------------- #
# CLI — scripts/run_local_futures_ml_batch.py
# --------------------------------------------------------------------------- #


def _cli_base_args(tmp_path: Path, spec: Path, *extra: str) -> list[str]:
    return [
        "--base-dir", str(tmp_path / "store"),
        "--config-json", str(spec),
        "--no-parquet",
        *extra,
    ]


def test_cli_valid_run_ok_saves_runs(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"random_seed": [0, 1]})
    cli = _load_batch_cli()

    code = cli.main(_cli_base_args(tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp")))
    out = capsys.readouterr().out

    assert code == 0
    assert "RESULT: OK" in out
    assert out.count("] ok train_run_hash=") == 2
    assert "n_ok=2" in out and "batch_config_hash=" in out
    # two runs persisted under the experiment store
    assert len(list((tmp_path / "exp").iterdir())) == 2


def test_cli_dry_run_returns_ok_and_writes_nothing(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"random_seed": [0, 1]})
    cli = _load_batch_cli()

    code = cli.main(_cli_base_args(tmp_path, spec, "--dry-run"))
    out = capsys.readouterr().out

    assert code == 0
    assert "RESULT: OK" in out
    assert out.count("] skipped reason=") == 2
    assert not (tmp_path / "exp").exists()  # no experiment artifacts


def test_cli_report_json_strict(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"random_seed": [0, 1]})
    report = tmp_path / "out" / "batch.json"
    cli = _load_batch_cli()

    code = cli.main(
        _cli_base_args(
            tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"), "--report-json", str(report)
        )
    )
    out = capsys.readouterr().out

    assert code == 0
    assert f"[REPORT] path={report}" in out
    assert report.exists()
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["batch_config_hash"] and data["n_ok"] == 2
    assert [it["item_id"] for it in data["items"]] == ["item_0000", "item_0001"]
    # strict: reparse with allow_nan=False must succeed (no NaN/Infinity)
    json.loads(json.dumps(data, allow_nan=False))


def test_cli_comparison_csv(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"random_seed": [0, 1]})
    comp = tmp_path / "out" / "cmp.csv"
    cli = _load_batch_cli()

    code = cli.main(
        _cli_base_args(
            tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"),
            "--comparison-output", str(comp),
        )
    )
    out = capsys.readouterr().out

    assert code == 0
    assert f"[COMPARE] path={comp}" in out
    assert comp.exists()
    text = comp.read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("train_run_hash,")  # CSV header
    assert len(text.strip().splitlines()) == 3  # header + 2 runs


def test_cli_comparison_json(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"random_seed": [0, 1]})
    comp = tmp_path / "out" / "cmp.json"
    cli = _load_batch_cli()

    code = cli.main(
        _cli_base_args(
            tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"),
            "--comparison-output", str(comp),
        )
    )
    assert code == 0
    payload = json.loads(comp.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 2
    assert "disclaimers" in payload


def test_cli_comparison_unsupported_extension_fails(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path)
    cli = _load_batch_cli()

    code = cli.main(
        _cli_base_args(
            tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"),
            "--comparison-output", str(tmp_path / "cmp.txt"),
        )
    )
    assert code != 0
    assert "RESULT: FAIL" in capsys.readouterr().out


def test_cli_comparison_insufficient_runs_fails(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"random_seed": [0]})  # only one config -> one success
    comp = tmp_path / "cmp.json"
    cli = _load_batch_cli()

    code = cli.main(
        _cli_base_args(
            tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"),
            "--comparison-output", str(comp),
        )
    )
    assert code != 0
    assert "RESULT: FAIL" in capsys.readouterr().out
    assert not comp.exists()


def test_cli_stop_on_error_returns_nonzero_and_skips_remaining(tmp_path, capsys):
    _raw_store(tmp_path)
    # item_0000 synthetic (ok), item_0001 missing (fail -> stop), item_0002 skipped
    spec = _write_spec(tmp_path, grid={"source": ["synthetic", "missing", "synthetic"]})
    cli = _load_batch_cli()

    code = cli.main(
        _cli_base_args(tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"), "--stop-on-error")
    )
    out = capsys.readouterr().out

    assert code != 0
    assert "RESULT: FAIL" in out
    assert "[item_0000] ok" in out
    assert "[item_0001] failed" in out
    assert "[item_0002] skipped" in out


def test_cli_continue_on_error_returns_ok_with_a_failure(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"source": ["synthetic", "missing"]})
    cli = _load_batch_cli()

    code = cli.main(
        _cli_base_args(tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"), "--continue-on-error")
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "RESULT: OK" in out
    assert "n_ok=1" in out and "n_failed=1" in out
    assert "[item_0001] failed" in out


def test_cli_all_items_fail_returns_nonzero(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, base={"source": "missing"}, grid={"random_seed": [0, 1]})
    cli = _load_batch_cli()

    code = cli.main(_cli_base_args(tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp")))
    out = capsys.readouterr().out

    assert code != 0
    assert "RESULT: FAIL" in out and "n_ok=0" in out


def test_cli_overwrite_allows_duplicate_rerun(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"random_seed": [0]})
    args = _cli_base_args(tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"), "--overwrite")
    cli = _load_batch_cli()

    assert cli.main(args) == 0
    capsys.readouterr()
    assert cli.main(args) == 0  # re-run with overwrite succeeds
    out = capsys.readouterr().out
    assert "RESULT: OK" in out and "n_ok=1" in out


def test_cli_duplicate_without_overwrite_fails(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path, grid={"random_seed": [0]})
    args = _cli_base_args(tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"))
    cli = _load_batch_cli()

    assert cli.main(args) == 0
    capsys.readouterr()
    code = cli.main(args)  # duplicate run, no overwrite -> the only item fails
    out = capsys.readouterr().out
    assert code != 0
    assert "RESULT: FAIL" in out and "n_ok=0" in out


def test_cli_invalid_json_fails(tmp_path, capsys):
    _raw_store(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not valid json", encoding="utf-8")
    cli = _load_batch_cli()

    code = cli.main(_cli_base_args(tmp_path, bad, "--artifacts-dir", str(tmp_path / "exp")))
    assert code != 0
    assert "RESULT: FAIL" in capsys.readouterr().out


def test_cli_invalid_config_fails(tmp_path, capsys):
    _raw_store(tmp_path)
    # non-ratio adjustment_method is rejected by LocalExperimentConfig validation
    spec = _write_spec(
        tmp_path, base={"source": "synthetic", "adjustment_method": "backward"},
        grid={"random_seed": [0]},
    )
    cli = _load_batch_cli()

    code = cli.main(_cli_base_args(tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp")))
    assert code != 0
    assert "RESULT: FAIL" in capsys.readouterr().out


def test_cli_missing_artifacts_dir_without_dry_run_fails(tmp_path, capsys):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path)
    cli = _load_batch_cli()

    code = cli.main(_cli_base_args(tmp_path, spec))  # no --artifacts-dir, no --dry-run
    assert code != 0
    assert "RESULT: FAIL" in capsys.readouterr().out


def test_cli_mutually_exclusive_error_flags(tmp_path):
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path)
    cli = _load_batch_cli()
    with pytest.raises(SystemExit):
        cli.main(
            _cli_base_args(
                tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp"),
                "--stop-on-error", "--continue-on-error",
            )
        )


def test_cli_creates_no_repo_artifacts(tmp_path):
    before = _repo_snapshot()
    _raw_store(tmp_path)
    spec = _write_spec(tmp_path)
    cli = _load_batch_cli()
    cli.main(_cli_base_args(tmp_path, spec, "--artifacts-dir", str(tmp_path / "exp")))
    assert _repo_snapshot() == before


def test_cli_module_has_no_forbidden_imports():
    src = Path(_BATCH_CLI_PATH).read_text(encoding="utf-8")
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
        assert token not in src, f"CLI must not reference {token!r}"


def test_cli_module_has_no_ml_internals_or_hashing():
    src = Path(_BATCH_CLI_PATH).read_text(encoding="utf-8")
    for token in ("train_model", "build_feature_matrix", "build_label_matrix"):
        assert token not in src, f"CLI must not touch ML internal {token!r}"
    assert "hashlib" not in src
    assert "sha256" not in src


def test_cli_imports_reporting_but_runner_does_not():
    cli_src = Path(_BATCH_CLI_PATH).read_text(encoding="utf-8")
    assert "app.reporting" in cli_src  # Phase 10 comparison is wired at the CLI layer
    from app.batch_experiments import runner as runner_module

    runner_src = Path(runner_module.__file__).read_text(encoding="utf-8")
    assert "app.reporting" not in runner_src  # ... and never in the runner


# --------------------------------------------------------------------------- #
# integrated end-to-end: raw store -> batch CLI -> ExperimentStore -> report + comparison
# --------------------------------------------------------------------------- #

_HASH_CHAIN_KEYS = {
    "raw_data_version_hash",
    "continuous_config_hash",
    "feature_config_hash",
    "label_config_hash",
    "dataset_config_hash",
    "model_config_hash",
    "train_run_hash",
}


def test_e2e_local_futures_batch_cli(tmp_path, capsys):
    """Full Phase 11 path: synthetic ES raw store -> 3-config batch spec -> batch CLI
    -> Phase 9 runs saved in an ExperimentStore -> strict batch manifest JSON ->
    Phase 10 comparison. Everything under `tmp_path`; no network; no repo writes."""
    before = _repo_snapshot()

    _raw_store(tmp_path)  # synthetic ES raw (3 contracts) under tmp_path/store
    spec = _write_spec(tmp_path, grid={"random_seed": [0, 1, 2]})  # 3 configs
    exp_dir = tmp_path / "exp"
    report = tmp_path / "reports" / "batch_manifest.json"
    comparison = tmp_path / "reports" / "batch_comparison.json"

    cli = _load_batch_cli()
    code = cli.main(
        _cli_base_args(
            tmp_path, spec,
            "--artifacts-dir", str(exp_dir),
            "--report-json", str(report),
            "--comparison-output", str(comparison),
        )
    )
    out = capsys.readouterr().out

    # --- CLI outcome + per-item lines ---------------------------------------- #
    assert code == 0
    assert "RESULT: OK" in out
    for item_id in ("item_0000", "item_0001", "item_0002"):
        assert f"[{item_id}] ok train_run_hash=" in out
    assert f"[REPORT] path={report}" in out
    assert f"[COMPARE] path={comparison}" in out

    # --- Phase 9 runs persisted under tmp_path (>= 2 successful) -------------- #
    run_dirs = sorted(p.name for p in exp_dir.iterdir() if p.is_dir())
    assert len(run_dirs) >= 2
    for run_hash in run_dirs:
        assert (exp_dir / run_hash / "metadata.json").exists()

    # --- strict batch manifest JSON ------------------------------------------ #
    report_text = report.read_text(encoding="utf-8")
    assert "NaN" not in report_text and "Infinity" not in report_text
    manifest = json.loads(report_text)
    json.dumps(manifest, allow_nan=False)  # strict re-serialization

    assert manifest["n_total"] == 3
    assert manifest["n_ok"] == 3
    assert manifest["n_failed"] == 0
    assert manifest["n_skipped"] == 0

    # ordered successful hashes, matching item order and the saved run dirs
    hashes = manifest["train_run_hashes"]
    assert len(hashes) == 3 and len(set(hashes)) == 3
    assert hashes == [it["train_run_hash"] for it in manifest["items"] if it["status"] == "ok"]
    assert sorted(hashes) == run_dirs

    # item statuses + full Phase 9 hash chain per successful item
    assert [it["item_id"] for it in manifest["items"]] == ["item_0000", "item_0001", "item_0002"]
    for item in manifest["items"]:
        assert item["status"] == "ok"
        assert set(item["hash_chain"]) == _HASH_CHAIN_KEYS
        assert item["hash_chain"]["train_run_hash"] == item["train_run_hash"]
        assert item["artifact_dir"] == item["train_run_hash"]  # store-relative, not absolute

    # --- batch_config_hash: manifest fingerprint only, never ML lineage ------- #
    batch_hash = manifest["batch_config_hash"]
    assert batch_hash and f"batch_config_hash={batch_hash}" in out
    assert batch_hash not in hashes
    for item in manifest["items"]:
        assert batch_hash not in item["hash_chain"].values()

    # --- Phase 10 comparison, only at the explicit output path ---------------- #
    assert comparison.exists()
    comparison_text = comparison.read_text(encoding="utf-8")
    payload = json.loads(comparison_text)
    assert sorted(row["train_run_hash"] for row in payload["rows"]) == run_dirs
    assert "disclaimers" in payload
    assert sorted(p.name for p in (tmp_path / "reports").iterdir()) == [
        "batch_comparison.json",
        "batch_manifest.json",
    ]

    # --- no absolute local paths leak into either artifact -------------------- #
    for text in (report_text, comparison_text):
        assert ":\\" not in text  # no Windows drive-letter path (JSON-escaped form)
        assert tmp_path.name not in text

    # --- everything stayed under tmp_path; repo root untouched ---------------- #
    assert _repo_snapshot() == before

    # --- layer guards: orchestration only, no new ML, no new hash chain ------- #
    from app.batch_experiments import config as config_module
    from app.batch_experiments import runner as runner_module

    config_src = Path(config_module.__file__).read_text(encoding="utf-8")
    runner_src = Path(runner_module.__file__).read_text(encoding="utf-8")
    cli_src = Path(_BATCH_CLI_PATH).read_text(encoding="utf-8")

    forbidden = (
        "import requests", "urllib", "httpx", "aiohttp", "socket",
        "yfinance", "ibkr", "sklearn", "xgboost", "lightgbm", "torch", "tensorflow",
    )
    ml_internals = ("train_model", "build_feature_matrix", "build_label_matrix")
    for name, src in (("config.py", config_src), ("runner.py", runner_src), ("CLI", cli_src)):
        for token in forbidden:
            assert token not in src, f"{name} must not reference {token!r}"
        for token in ml_internals:
            assert token not in src, f"{name} must not touch ML internal {token!r}"
        # no new hash chain: nothing hashes on its own
        assert "hashlib" not in src and "sha256" not in src, f"{name} must not hash directly"

    assert "compute_config_hash" in runner_src  # reuses the existing reproducibility helper
    assert "app.reporting" not in runner_src  # runner stays decoupled from Phase 10
    assert "app.reporting" in cli_src  # Phase 10 used only at the CLI, for --comparison-output
