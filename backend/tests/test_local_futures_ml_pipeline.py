"""
Phase 9 commit 1 — local continuous futures -> ML pipeline.

Covers the store-backed pipeline (`run_local_futures_ml_experiment`) that reuses
the Phase 2-5 chain on already-ingested local raw futures.  Test data is the
proven synthetic ES generator (3 contracts x ~120 sessions) — enough rows for
feature warmup + a train/val split — written into a tmp `RawFuturesStore`
(**not** the tiny Phase 8 15-row ES M/U fixture).  Everything lives under
`tmp_path`; no network; nothing written outside `tmp_path`.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.datastore.continuous_build import ContinuousSourceError
from app.datastore.store import RawFuturesStore
from app.experiments import ExperimentStore, load_experiment_run
from app.local_pipeline import (
    LocalExperimentConfig,
    LocalExperimentResult,
    run_local_futures_ml_experiment,
)
from app.research_cli.config import ExperimentConfig
from app.research_cli.synthetic import generate_synthetic_es_raw

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _raw_store(tmp_path: Path, ec: ExperimentConfig | None = None) -> tuple[RawFuturesStore, Path]:
    """Generate synthetic ES raw (3 contracts), write it into a tmp RawFuturesStore
    under source='synthetic'. Returns (store, base_dir)."""
    ec = ec or ExperimentConfig()
    raw = generate_synthetic_es_raw(ec)  # source column == "synthetic"
    base = tmp_path / "store"
    store = RawFuturesStore(base, prefer_parquet=False)
    store.write_raw(raw)
    return store, base


def _repo_paths_snapshot() -> tuple[bool, bool, bool]:
    return (
        (_REPO_ROOT / "data").exists(),
        (_REPO_ROOT / "artifacts").exists(),
        (_BACKEND / "data").exists(),
    )


_CLI_PATH = _REPO_ROOT / "scripts" / "run_local_futures_ml_experiment.py"


def _load_cli():
    """Import the thin CLI module by path (executes its sys.path bootstrap)."""
    spec = importlib.util.spec_from_file_location("run_local_ml_cli", _CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cli_args(base: Path, *extra: str) -> list[str]:
    """Base CLI args with the default synthetic-ES windows; append per-test extras."""
    return [
        "--base-dir", str(base),
        "--root-symbol", "ES",
        "--source", "synthetic",
        "--train-start", "2024-04-01",
        "--train-end", "2024-06-05",
        "--validation-start", "2024-06-06",
        "--validation-end", "2024-09-15",
        *extra,
    ]


# --------------------------------------------------------------------------- #
# happy path + provenance
# --------------------------------------------------------------------------- #


def test_valid_run_returns_result(tmp_path):
    store, _ = _raw_store(tmp_path)
    cfg = LocalExperimentConfig(source="synthetic")
    result = run_local_futures_ml_experiment(store, config=cfg)
    assert isinstance(result, LocalExperimentResult)
    assert result.root_symbol == "ES" and result.source == "synthetic"
    assert result.adjustment_method == "ratio"


def test_full_hash_chain_is_populated(tmp_path):
    store, _ = _raw_store(tmp_path)
    result = run_local_futures_ml_experiment(store, config=LocalExperimentConfig(source="synthetic"))
    for h in (
        result.train_run_hash, result.continuous_config_hash, result.feature_config_hash,
        result.label_config_hash, result.dataset_config_hash, result.model_config_hash,
        result.raw_data_version_hash,
    ):
        assert isinstance(h, str) and h


def test_phase8_provenance_surfaced(tmp_path):
    store, _ = _raw_store(tmp_path)
    result = run_local_futures_ml_experiment(store, config=LocalExperimentConfig(source="synthetic"))
    assert len(result.contracts) >= 2          # ES generator makes >=2 in-cycle contracts
    assert set(result.contract_version_hashes) == set(result.contracts)
    assert all(isinstance(v, str) and v for v in result.contract_version_hashes.values())
    assert len(result.roll_events) >= 1
    ev = result.roll_events[0]
    assert {"from_contract", "to_contract", "roll_date"} <= set(ev)


def test_metrics_present(tmp_path):
    store, _ = _raw_store(tmp_path)
    result = run_local_futures_ml_experiment(store, config=LocalExperimentConfig(source="synthetic"))
    assert isinstance(result.ml_metrics, dict) and result.ml_metrics
    assert isinstance(result.backtest_metrics, dict) and result.backtest_metrics
    assert set(result.baseline_metrics) == {"no_trade", "momentum"}


# --------------------------------------------------------------------------- #
# persistence: with store vs without
# --------------------------------------------------------------------------- #


def test_with_experiment_store_saves_and_roundtrips(tmp_path):
    store, _ = _raw_store(tmp_path)
    exp = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    result = run_local_futures_ml_experiment(
        store, config=LocalExperimentConfig(source="synthetic"), experiment_store=exp
    )
    assert result.artifact_dir and str(result.artifact_dir).startswith(str(tmp_path))
    assert exp.run_dir(result.train_run_hash).exists()
    loaded = load_experiment_run(result.train_run_hash, store=exp)
    assert loaded is not None


def test_without_experiment_store_writes_nothing(tmp_path):
    store, base = _raw_store(tmp_path)
    before = {p for p in base.rglob("*") if p.is_file()}
    result = run_local_futures_ml_experiment(store, config=LocalExperimentConfig(source="synthetic"))
    assert result.artifact_dir == ""            # no persistence
    assert result.experiment_run is None
    after = {p for p in base.rglob("*") if p.is_file()}
    assert after == before                       # the raw store is untouched


# --------------------------------------------------------------------------- #
# Phase 6 cross-check: store origin must match synthetic origin, hash-for-hash
# --------------------------------------------------------------------------- #


def test_phase6_crosscheck_identical_hash_chain(tmp_path):
    from app.research_cli.pipeline import run_es_ml_experiment

    ec = ExperimentConfig()
    # synthetic origin (Phase 6)
    rc_store = ExperimentStore(tmp_path / "rc", prefer_parquet=False)
    rc = run_es_ml_experiment(ec, store=rc_store)

    # store origin (Phase 9): same synthetic raw, written to a RawFuturesStore
    raw_store, _ = _raw_store(tmp_path)
    p9_store = ExperimentStore(tmp_path / "p9", prefer_parquet=False)
    p9 = run_local_futures_ml_experiment(
        raw_store, config=LocalExperimentConfig(source="synthetic"), experiment_store=p9_store
    )

    assert p9.continuous_config_hash == rc.continuous_config_hash
    assert p9.feature_config_hash == rc.feature_config_hash
    assert p9.label_config_hash == rc.label_config_hash
    assert p9.dataset_config_hash == rc.dataset_config_hash
    assert p9.model_config_hash == rc.model_config_hash
    assert p9.train_run_hash == rc.train_run_hash   # the whole lineage matches


# --------------------------------------------------------------------------- #
# failure modes
# --------------------------------------------------------------------------- #


def test_non_ratio_adjustment_rejected(tmp_path):
    with pytest.raises(ValidationError):
        LocalExperimentConfig(source="synthetic", adjustment_method="panama")
    with pytest.raises(ValidationError):
        LocalExperimentConfig(source="synthetic", adjustment_method="none")


def test_missing_source_root_fails_clearly(tmp_path):
    store, _ = _raw_store(tmp_path)
    with pytest.raises(ContinuousSourceError):
        run_local_futures_ml_experiment(store, config=LocalExperimentConfig(source="nope"))
    with pytest.raises(ContinuousSourceError):
        run_local_futures_ml_experiment(
            store, config=LocalExperimentConfig(root_symbol="NQ", source="synthetic")
        )


def test_narrow_windows_fail_clearly_and_write_nothing(tmp_path):
    from datetime import date

    store, _ = _raw_store(tmp_path)
    exp = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    # windows far outside the synthetic data range -> no trainable rows
    cfg = LocalExperimentConfig(
        source="synthetic",
        train_start=date(2030, 1, 1), train_end=date(2030, 2, 1),
        validation_start=date(2030, 2, 2), validation_end=date(2030, 3, 1),
    )
    with pytest.raises(Exception):  # MlSignalError / split error — clear, not silent
        run_local_futures_ml_experiment(store, config=cfg, experiment_store=exp)
    # no partial experiment artifacts were written
    assert not any(p.is_dir() for p in (exp.base_dir.glob("*") if exp.base_dir.exists() else []))


# --------------------------------------------------------------------------- #
# safety: no repo-root artifacts, no forbidden imports, no new hash
# --------------------------------------------------------------------------- #


def test_no_repo_root_data_or_artifacts(tmp_path, monkeypatch):
    before = _repo_paths_snapshot()
    monkeypatch.chdir(tmp_path)
    store, _ = _raw_store(tmp_path)
    exp = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    run_local_futures_ml_experiment(
        store, config=LocalExperimentConfig(source="synthetic"), experiment_store=exp
    )
    assert all(str(p).startswith(str(tmp_path)) for p in (tmp_path / "exp").rglob("*") if p.is_file())
    assert _repo_paths_snapshot() == before


def test_local_pipeline_no_forbidden_imports():
    for name in ("config.py", "pipeline.py", "__init__.py"):
        src = (_BACKEND / "app" / "local_pipeline" / name).read_text(encoding="utf-8")
        assert not re.search(
            r"(?m)^\s*(from|import)\s+\S*\b(requests|urllib|httpx|aiohttp|socket)\b", src
        ), name
        assert not re.search(
            r"(?m)^\s*(from|import)\s+\S*"
            r"(yfinance|ibkr|sklearn|xgboost|lightgbm|torch|tensorflow)\b", src
        ), name


def test_local_pipeline_invents_no_new_hash():
    for name in ("config.py", "pipeline.py"):
        src = (_BACKEND / "app" / "local_pipeline" / name).read_text(encoding="utf-8")
        assert "hashlib" not in src and "sha256" not in src, name


# --------------------------------------------------------------------------- #
# Commit 2 — thin CLI
# --------------------------------------------------------------------------- #


def test_cli_valid_no_artifacts_returns_zero_and_writes_nothing(tmp_path, capsys):
    store, base = _raw_store(tmp_path)
    before = {p for p in base.rglob("*") if p.is_file()}
    cli = _load_cli()
    rc = cli.main(_cli_args(base))
    out = capsys.readouterr().out
    assert rc == 0
    assert "RESULT: OK" in out
    assert "train_run_hash=" in out and "continuous_config_hash=" in out
    assert "artifact_dir=\n" in out or out.rstrip().endswith("RESULT: OK")  # empty artifact_dir
    assert "root=ES" in out and "adjustment=ratio" in out
    # no experiment artifacts written (raw store untouched, no exp dir)
    assert {p for p in base.rglob("*") if p.is_file()} == before


def test_cli_with_artifacts_saves_under_tmp_path(tmp_path, capsys):
    store, base = _raw_store(tmp_path)
    exp = tmp_path / "exp"
    cli = _load_cli()
    rc = cli.main(_cli_args(base, "--artifacts-dir", str(exp)))
    out = capsys.readouterr().out
    assert rc == 0 and "RESULT: OK" in out
    # a run dir now exists under the tmp artifacts dir, and it's printed
    run_dirs = [p for p in exp.glob("*") if p.is_dir()]
    assert len(run_dirs) == 1
    assert f"artifact_dir={run_dirs[0]}" in out
    assert str(run_dirs[0]).startswith(str(tmp_path))


def test_cli_feature_columns_comma_list(tmp_path, capsys):
    store, base = _raw_store(tmp_path)
    cli = _load_cli()
    rc = cli.main(_cli_args(base, "--feature-columns", "feature__return_20"))
    out = capsys.readouterr().out
    assert rc == 0 and "RESULT: OK" in out


def test_cli_panama_or_none_fails(tmp_path, capsys):
    store, base = _raw_store(tmp_path)
    cli = _load_cli()
    for method in ("panama", "none"):
        rc = cli.main(_cli_args(base, "--adjustment-method", method))
        out = capsys.readouterr().out
        assert rc == 1 and "RESULT: FAIL" in out


def test_cli_missing_source_returns_nonzero(tmp_path, capsys):
    store, base = _raw_store(tmp_path)
    cli = _load_cli()
    args = _cli_args(base)
    args[args.index("--source") + 1] = "nope"
    rc = cli.main(args)
    out = capsys.readouterr().out
    assert rc == 1 and "RESULT: FAIL" in out


def test_cli_narrow_windows_return_nonzero(tmp_path, capsys):
    store, base = _raw_store(tmp_path)
    cli = _load_cli()
    rc = cli.main([
        "--base-dir", str(base), "--root-symbol", "ES", "--source", "synthetic",
        "--train-start", "2030-01-01", "--train-end", "2030-02-01",
        "--validation-start", "2030-02-02", "--validation-end", "2030-03-01",
    ])
    out = capsys.readouterr().out
    assert rc == 1 and "RESULT: FAIL" in out


def test_cli_duplicate_without_overwrite_nonzero_then_overwrite_ok(tmp_path, capsys):
    store, base = _raw_store(tmp_path)
    exp = tmp_path / "exp"
    cli = _load_cli()
    assert cli.main(_cli_args(base, "--artifacts-dir", str(exp))) == 0
    capsys.readouterr()
    # second identical run -> duplicate -> nonzero
    rc = cli.main(_cli_args(base, "--artifacts-dir", str(exp)))
    out = capsys.readouterr().out
    assert rc == 1 and "RESULT: FAIL" in out
    # ... with --overwrite it succeeds
    assert cli.main(_cli_args(base, "--artifacts-dir", str(exp), "--overwrite")) == 0


def test_cli_invalid_model_or_task_is_argparse_error(tmp_path):
    store, base = _raw_store(tmp_path)
    cli = _load_cli()
    with pytest.raises(SystemExit) as exc:
        cli.main(_cli_args(base, "--model-type", "bogus"))
    assert exc.value.code != 0
    with pytest.raises(SystemExit):
        cli.main(_cli_args(base, "--task-type", "bogus"))


def test_cli_no_parquet_works(tmp_path, capsys):
    store, base = _raw_store(tmp_path)
    exp = tmp_path / "exp"
    cli = _load_cli()
    rc = cli.main(_cli_args(base, "--no-parquet", "--artifacts-dir", str(exp)))
    assert rc == 0 and "RESULT: OK" in capsys.readouterr().out


def test_cli_no_repo_root_data_or_artifacts(tmp_path, monkeypatch):
    before = _repo_paths_snapshot()
    monkeypatch.chdir(tmp_path)
    store, base = _raw_store(tmp_path)
    exp = tmp_path / "exp"
    cli = _load_cli()
    assert cli.main(_cli_args(base, "--artifacts-dir", str(exp))) == 0
    assert all(str(p).startswith(str(tmp_path)) for p in exp.rglob("*") if p.is_file())
    assert _repo_paths_snapshot() == before


def test_cli_is_thin_and_clean():
    src = _CLI_PATH.read_text(encoding="utf-8")
    assert "run_local_futures_ml_experiment" in src
    # the CLI must not reach into the Phase 2-5 building blocks directly
    for token in ("build_feature_matrix", "build_label_matrix", "train_model",
                  "build_continuous_futures"):
        assert token not in src, token
    assert "hashlib" not in src and "sha256" not in src
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*\b(requests|urllib|httpx|aiohttp|socket)\b", src
    )
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*"
        r"(yfinance|ibkr|sklearn|xgboost|lightgbm|torch|tensorflow)\b", src
    )
