"""
Phase 10 commit 1 — experiment reporting module.

Covers the reporting layer (`app.reporting`) over persisted `ExperimentRun`
artifacts.  Test **setup** creates real saved runs via the Phase 9 pipeline
(fixtures need persisted runs), but the reporting module itself does no training.
Everything lives under `tmp_path`; no network; nothing written outside `tmp_path`.
"""

from __future__ import annotations

import importlib.util
import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.datastore.store import RawFuturesStore
from app.experiments import ExperimentError, ExperimentStore
from app.local_pipeline import LocalExperimentConfig, run_local_futures_ml_experiment
from app.reporting import (
    DISCLAIMERS,
    ExperimentComparisonRow,
    ExperimentRunSummary,
    best_experiment_run,
    compare_experiment_runs,
    export_experiment_comparison_csv,
    export_experiment_comparison_json,
    export_experiment_report_json,
    render_experiment_report_markdown,
    summarize_experiment_run,
)
from app.research_cli.config import ExperimentConfig
from app.research_cli.synthetic import generate_synthetic_es_raw

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _store_with_runs(tmp_path: Path, seeds=(0, 1)) -> tuple[ExperimentStore, list[str]]:
    """Create saved runs (varying random_seed -> distinct train_run_hash) under one
    tmp ExperimentStore. Returns (exp_store, [train_run_hash, ...])."""
    raw = generate_synthetic_es_raw(ExperimentConfig())
    raw_store = RawFuturesStore(tmp_path / "store", prefer_parquet=False)
    raw_store.write_raw(raw)
    exp = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    hashes = []
    for seed in seeds:
        cfg = LocalExperimentConfig(source="synthetic", random_seed=seed)
        result = run_local_futures_ml_experiment(raw_store, config=cfg, experiment_store=exp)
        hashes.append(result.train_run_hash)
    return exp, hashes


def _repo_paths_snapshot() -> tuple[bool, bool, bool]:
    return (
        (_REPO_ROOT / "data").exists(),
        (_REPO_ROOT / "artifacts").exists(),
        (_BACKEND / "data").exists(),
    )


_CLI_PATH = _REPO_ROOT / "scripts" / "report_local_futures_experiments.py"


def _load_cli():
    """Import the thin reporting CLI module by path (executes its sys.path bootstrap)."""
    spec = importlib.util.spec_from_file_location("report_cli", _CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# summary wrappers
# --------------------------------------------------------------------------- #


def test_summarize_returns_summary_with_fields(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    s = summarize_experiment_run(hashes[0], store=exp)
    assert isinstance(s, ExperimentRunSummary)
    assert s.train_run_hash == hashes[0]
    assert s.model_type and s.task_type and s.label_column
    assert s.feature_columns
    assert s.train_start and s.validation_end
    assert isinstance(s.ml_metrics, dict) and isinstance(s.backtest_metrics, dict)


def test_summary_includes_hash_chain(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    s = summarize_experiment_run(hashes[0], store=exp)
    for key in (
        "continuous_config_hash", "feature_config_hash", "label_config_hash",
        "dataset_config_hash", "model_config_hash", "train_run_hash",
    ):
        assert s.hash_chain[key]


def test_summary_notes_unavailable_provenance(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    s = summarize_experiment_run(hashes[0], store=exp)
    for field in ("root_symbol", "source", "adjustment_method",
                  "contracts", "roll_events", "raw_data_version_hash"):
        assert s.unavailable_provenance[field] == "not recorded"


def test_compare_returns_rows_and_reuses_window_guard(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    rows = compare_experiment_runs(hashes, store=exp)
    assert len(rows) == 2
    assert all(isinstance(r, ExperimentComparisonRow) for r in rows)
    assert {r.train_run_hash for r in rows} == set(hashes)
    assert all(r.task_type for r in rows)  # task_type enriched from the resolved runs


def test_best_returns_deterministic_summary(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    best1 = best_experiment_run(store=exp, metric="sharpe")
    best2 = best_experiment_run(store=exp, metric="sharpe")
    assert isinstance(best1, ExperimentRunSummary)
    assert best1.train_run_hash == best2.train_run_hash  # deterministic tie-break
    assert best1.train_run_hash in hashes


# --------------------------------------------------------------------------- #
# renderers / exports
# --------------------------------------------------------------------------- #


def test_markdown_has_sections_and_disclaimers(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    s = summarize_experiment_run(hashes[0], store=exp)
    md = render_experiment_report_markdown(s)
    for heading in ("## Disclaimers", "## Run identity", "## Windows",
                    "## ML metrics", "## Backtest metrics", "## Hash chain",
                    "## Provenance"):
        assert heading in md
    for disclaimer in DISCLAIMERS:
        assert disclaimer in md
    assert "not recorded" in md  # unavailable-provenance note


def test_json_export_parses_and_is_strict(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    s = summarize_experiment_run(hashes[0], store=exp)
    text = export_experiment_report_json(s)
    assert "NaN" not in text and "Infinity" not in text
    parsed = json.loads(text)
    assert parsed["run_identity"]["train_run_hash"] == hashes[0]
    assert parsed["disclaimers"] == list(DISCLAIMERS)
    assert set(parsed["hash_chain"]) >= {"continuous_config_hash", "train_run_hash"}


def test_csv_export_parses_with_deterministic_columns(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    rows = compare_experiment_runs(hashes, store=exp)
    text = export_experiment_comparison_csv(rows)
    lines = text.strip().splitlines()
    header = lines[0].split(",")
    assert header[:7] == ["train_run_hash", "model_type", "task_type", "label_column",
                          "validation_start", "validation_end", "same_window"]
    assert header[7:] == sorted(header[7:])  # metric columns sorted
    assert len(lines) == 1 + len(rows)


def test_comparison_json_strict_no_nan(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    rows = compare_experiment_runs(hashes, store=exp)
    text = export_experiment_comparison_json(rows)
    assert "NaN" not in text and "Infinity" not in text
    parsed = json.loads(text)
    assert len(parsed["rows"]) == 2
    # regression runs have no accuracy/f1 -> null, never NaN
    for row in parsed["rows"]:
        for k in ("accuracy", "f1"):
            if k in row["metrics"]:
                assert row["metrics"][k] is None


def test_render_is_deterministic(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    s = summarize_experiment_run(hashes[0], store=exp)
    assert render_experiment_report_markdown(s) == render_experiment_report_markdown(s)
    assert export_experiment_report_json(s) == export_experiment_report_json(s)
    rows = compare_experiment_runs(hashes, store=exp)
    assert export_experiment_comparison_csv(rows) == export_experiment_comparison_csv(rows)


def test_report_has_no_absolute_paths(tmp_path):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    s = summarize_experiment_run(hashes[0], store=exp)
    text = export_experiment_report_json(s)
    assert str(tmp_path) not in text          # no host/tmp path leaked
    assert not re.search(r"[A-Za-z]:[\\/]", text)  # no drive-letter absolute path


# --------------------------------------------------------------------------- #
# failure modes
# --------------------------------------------------------------------------- #


def test_missing_run_fails_clearly(tmp_path):
    exp, _ = _store_with_runs(tmp_path, seeds=(0,))
    with pytest.raises(ExperimentError):
        summarize_experiment_run("deadbeef" * 8, store=exp)


def test_missing_metric_fails_clearly(tmp_path):
    exp, _ = _store_with_runs(tmp_path, seeds=(0, 1))
    with pytest.raises(ExperimentError):
        best_experiment_run(store=exp, metric="not_a_metric")


def test_incompatible_windows_fail_unless_allowed(tmp_path):
    # two runs with different validation windows -> compare guard triggers
    raw = generate_synthetic_es_raw(ExperimentConfig())
    raw_store = RawFuturesStore(tmp_path / "store", prefer_parquet=False)
    raw_store.write_raw(raw)
    exp = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    r_a = run_local_futures_ml_experiment(
        raw_store, config=LocalExperimentConfig(source="synthetic"), experiment_store=exp
    )
    r_b = run_local_futures_ml_experiment(
        raw_store,
        config=LocalExperimentConfig(source="synthetic", validation_end=date(2024, 9, 10)),
        experiment_store=exp,
    )
    with pytest.raises(ExperimentError):
        compare_experiment_runs([r_a.train_run_hash, r_b.train_run_hash], store=exp)
    rows = compare_experiment_runs(
        [r_a.train_run_hash, r_b.train_run_hash], store=exp, allow_different_windows=True
    )
    assert len(rows) == 2 and rows[0].same_window is True


# --------------------------------------------------------------------------- #
# safety: no repo-root artifacts, no forbidden/training imports, no new hash
# --------------------------------------------------------------------------- #


def test_no_repo_root_data_or_artifacts(tmp_path, monkeypatch):
    before = _repo_paths_snapshot()
    monkeypatch.chdir(tmp_path)
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    s = summarize_experiment_run(hashes[0], store=exp)
    render_experiment_report_markdown(s)
    export_experiment_report_json(s)
    assert _repo_paths_snapshot() == before


def test_reporting_module_no_forbidden_or_training_imports():
    for name in ("__init__.py", "summary.py", "render.py"):
        src = (_BACKEND / "app" / "reporting" / name).read_text(encoding="utf-8")
        assert not re.search(
            r"(?m)^\s*(from|import)\s+\S*\b(requests|urllib|httpx|aiohttp|socket)\b", src
        ), name
        assert not re.search(
            r"(?m)^\s*(from|import)\s+\S*"
            r"(yfinance|ibkr|sklearn|xgboost|lightgbm|torch|tensorflow)\b", src
        ), name
        # reporting must not retrain or rebuild features/labels
        for token in ("train_model", "run_local_futures_ml_experiment",
                      "build_feature_matrix", "build_label_matrix"):
            assert token not in src, f"{name}:{token}"


def test_reporting_module_invents_no_new_hash():
    for name in ("summary.py", "render.py"):
        src = (_BACKEND / "app" / "reporting" / name).read_text(encoding="utf-8")
        assert "hashlib" not in src and "sha256" not in src, name


# --------------------------------------------------------------------------- #
# Commit 2 — thin CLI
# --------------------------------------------------------------------------- #


def _exp_files(exp: ExperimentStore) -> set[Path]:
    return {p for p in exp.base_dir.rglob("*") if p.is_file()}


def test_cli_summary_returns_zero(tmp_path, capsys):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    cli = _load_cli()
    rc = cli.main(["summary", "--artifacts-dir", str(exp.base_dir), "--train-run-hash", hashes[0]])
    out = capsys.readouterr().out
    assert rc == 0 and "RESULT: OK" in out
    assert hashes[0] in out and "## Disclaimers" in out


def test_cli_compare_returns_zero_and_deterministic(tmp_path, capsys):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    cli = _load_cli()
    args = ["compare", "--artifacts-dir", str(exp.base_dir), *hashes]
    rc1 = cli.main(args)
    out1 = capsys.readouterr().out
    rc2 = cli.main(args)
    out2 = capsys.readouterr().out
    assert rc1 == 0 and rc2 == 0
    assert "RESULT: OK" in out1
    assert out1 == out2                        # deterministic
    assert "train_run_hash,model_type,task_type" in out1  # CSV header


def test_cli_best_prints_selected_hash(tmp_path, capsys):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    cli = _load_cli()
    rc = cli.main(["best", "--artifacts-dir", str(exp.base_dir), "--metric", "sharpe"])
    out = capsys.readouterr().out
    assert rc == 0 and "RESULT: OK" in out
    assert "best_by=sharpe train_run_hash=" in out
    assert any(h in out for h in hashes)


def test_cli_export_markdown_writes_only_output_path(tmp_path, capsys):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    before = _exp_files(exp)
    out_md = tmp_path / "reports" / "run.md"
    cli = _load_cli()
    rc = cli.main([
        "export-markdown", "--artifacts-dir", str(exp.base_dir),
        "--train-run-hash", hashes[0], "--output-path", str(out_md),
    ])
    out = capsys.readouterr().out
    assert rc == 0 and f"[WRITE] path={out_md}" in out and "RESULT: OK" in out
    assert out_md.exists() and "## Disclaimers" in out_md.read_text(encoding="utf-8")
    assert _exp_files(exp) == before           # store untouched


def test_cli_export_json_strict(tmp_path, capsys):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    out_json = tmp_path / "run.json"
    cli = _load_cli()
    rc = cli.main([
        "export-json", "--artifacts-dir", str(exp.base_dir),
        "--train-run-hash", hashes[0], "--output-path", str(out_json),
    ])
    assert rc == 0 and "RESULT: OK" in capsys.readouterr().out
    raw = out_json.read_text(encoding="utf-8")
    assert "NaN" not in raw and "Infinity" not in raw
    assert json.loads(raw)["run_identity"]["train_run_hash"] == hashes[0]


def test_cli_export_csv_writes_output(tmp_path, capsys):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    out_csv = tmp_path / "cmp.csv"
    cli = _load_cli()
    rc = cli.main([
        "export-csv", "--artifacts-dir", str(exp.base_dir), *hashes,
        "--output-path", str(out_csv),
    ])
    assert rc == 0 and f"[WRITE] path={out_csv}" in capsys.readouterr().out
    lines = out_csv.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("train_run_hash,model_type,task_type")
    assert len(lines) == 1 + len(hashes)


def test_cli_read_only_subcommands_write_nothing(tmp_path, capsys):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    before = _exp_files(exp)
    cli = _load_cli()
    cli.main(["summary", "--artifacts-dir", str(exp.base_dir), "--train-run-hash", hashes[0]])
    cli.main(["compare", "--artifacts-dir", str(exp.base_dir), *hashes])
    cli.main(["best", "--artifacts-dir", str(exp.base_dir)])
    capsys.readouterr()
    assert _exp_files(exp) == before           # no new files anywhere in the store


def test_cli_missing_artifacts_dir_nonzero(tmp_path, capsys):
    cli = _load_cli()
    rc = cli.main([
        "summary", "--artifacts-dir", str(tmp_path / "nope"), "--train-run-hash", "abc123",
    ])
    assert rc == 1 and "RESULT: FAIL" in capsys.readouterr().out


def test_cli_unknown_hash_nonzero(tmp_path, capsys):
    exp, _ = _store_with_runs(tmp_path, seeds=(0,))
    cli = _load_cli()
    rc = cli.main([
        "summary", "--artifacts-dir", str(exp.base_dir), "--train-run-hash", "deadbeef" * 8,
    ])
    assert rc == 1 and "RESULT: FAIL" in capsys.readouterr().out


def test_cli_missing_metric_nonzero(tmp_path, capsys):
    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    cli = _load_cli()
    rc = cli.main(["best", "--artifacts-dir", str(exp.base_dir), "--metric", "not_a_metric"])
    assert rc == 1 and "RESULT: FAIL" in capsys.readouterr().out


def test_cli_incompatible_windows_fail_unless_allowed(tmp_path, capsys):
    raw = generate_synthetic_es_raw(ExperimentConfig())
    raw_store = RawFuturesStore(tmp_path / "store", prefer_parquet=False)
    raw_store.write_raw(raw)
    exp = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    r_a = run_local_futures_ml_experiment(
        raw_store, config=LocalExperimentConfig(source="synthetic"), experiment_store=exp
    )
    r_b = run_local_futures_ml_experiment(
        raw_store,
        config=LocalExperimentConfig(source="synthetic", validation_end=date(2024, 9, 10)),
        experiment_store=exp,
    )
    cli = _load_cli()
    hashes = [r_a.train_run_hash, r_b.train_run_hash]
    rc = cli.main(["compare", "--artifacts-dir", str(exp.base_dir), *hashes])
    assert rc == 1 and "RESULT: FAIL" in capsys.readouterr().out
    rc_ok = cli.main([
        "compare", "--artifacts-dir", str(exp.base_dir), *hashes, "--allow-different-windows",
    ])
    assert rc_ok == 0 and "RESULT: OK" in capsys.readouterr().out


def test_cli_no_repo_root_artifacts(tmp_path, monkeypatch):
    before = _repo_paths_snapshot()
    monkeypatch.chdir(tmp_path)
    exp, hashes = _store_with_runs(tmp_path, seeds=(0,))
    cli = _load_cli()
    assert cli.main([
        "export-json", "--artifacts-dir", str(exp.base_dir),
        "--train-run-hash", hashes[0], "--output-path", str(tmp_path / "r.json"),
    ]) == 0
    assert _repo_paths_snapshot() == before


def test_cli_is_thin_and_clean():
    src = _CLI_PATH.read_text(encoding="utf-8")
    # uses the reporting wrappers, not the raw registry compare/best helpers
    for token in ("summarize_experiment_run", "compare_experiment_runs", "best_experiment_run"):
        assert token in src, token
    for token in ("compare_experiments", "get_best_experiment", "app.local_pipeline",
                  "train_model", "build_feature_matrix", "build_label_matrix",
                  "hashlib", "sha256"):
        assert token not in src, token
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*\b(requests|urllib|httpx|aiohttp|socket)\b", src
    )
    assert not re.search(
        r"(?m)^\s*(from|import)\s+\S*"
        r"(yfinance|ibkr|sklearn|xgboost|lightgbm|torch|tensorflow)\b", src
    )


# --------------------------------------------------------------------------- #
# Commit 3 — integrated end-to-end (runs -> summarize -> compare -> best -> export)
# --------------------------------------------------------------------------- #


def test_e2e_reporting_full_path(tmp_path, monkeypatch):
    """Full reporting path under tmp_path: Phase 9 saved runs -> summarize ->
    compare -> best -> export Markdown / JSON / CSV, with every safety property."""
    before = _repo_paths_snapshot()
    monkeypatch.chdir(tmp_path)

    exp, hashes = _store_with_runs(tmp_path, seeds=(0, 1))
    assert len(hashes) >= 2
    run_dirs = [p for p in exp.base_dir.glob("*") if p.is_dir()]
    assert len(run_dirs) >= 2

    # --- module wrappers: summarize / compare / best ---
    s = summarize_experiment_run(hashes[0], store=exp)
    assert isinstance(s, ExperimentRunSummary) and s.train_run_hash == hashes[0]
    for key in ("continuous_config_hash", "feature_config_hash", "label_config_hash",
                "dataset_config_hash", "model_config_hash", "train_run_hash"):
        assert s.hash_chain[key]
    rows1 = compare_experiment_runs(hashes, store=exp)
    rows2 = compare_experiment_runs(hashes, store=exp)
    assert [r.train_run_hash for r in rows1] == [r.train_run_hash for r in rows2]  # deterministic
    assert {r.train_run_hash for r in rows1} == set(hashes)
    best = best_experiment_run(store=exp, metric="sharpe")
    assert best.train_run_hash in hashes

    # --- CLI exports (only to explicit output paths under tmp_path) ---
    out_md = tmp_path / "reports" / "run.md"
    out_json = tmp_path / "reports" / "run.json"
    out_csv = tmp_path / "reports" / "cmp.csv"
    cli = _load_cli()
    assert cli.main(["export-markdown", "--artifacts-dir", str(exp.base_dir),
                     "--train-run-hash", hashes[0], "--output-path", str(out_md)]) == 0
    assert cli.main(["export-json", "--artifacts-dir", str(exp.base_dir),
                     "--train-run-hash", hashes[0], "--output-path", str(out_json)]) == 0
    assert cli.main(["export-csv", "--artifacts-dir", str(exp.base_dir), *hashes,
                     "--output-path", str(out_csv)]) == 0

    # --- Markdown: disclaimers + identity + metrics + hash chain + unavailable note ---
    md = out_md.read_text(encoding="utf-8")
    for disclaimer in DISCLAIMERS:
        assert disclaimer in md
    for heading in ("## Run identity", "## ML metrics", "## Backtest metrics", "## Hash chain"):
        assert heading in md
    assert "not recorded" in md

    # --- JSON: strict, parses, no NaN/Infinity ---
    jtext = out_json.read_text(encoding="utf-8")
    assert "NaN" not in jtext and "Infinity" not in jtext
    assert json.loads(jtext)["run_identity"]["train_run_hash"] == hashes[0]

    # --- CSV: deterministic columns, one row per run ---
    clines = out_csv.read_text(encoding="utf-8").strip().splitlines()
    assert clines[0].startswith("train_run_hash,model_type,task_type")
    assert len(clines) == 1 + len(hashes)

    # --- no absolute local paths leak into the Markdown or JSON reports ---
    for text in (md, jtext):
        assert str(tmp_path) not in text
        assert not re.search(r"[A-Za-z]:[\\/]", text)

    # --- exports exist only at their explicit output paths; all under tmp_path ---
    assert out_md.exists() and out_json.exists() and out_csv.exists()
    assert all(str(p).startswith(str(tmp_path)) for p in (out_md, out_json, out_csv))
    assert all(str(p).startswith(str(tmp_path)) for p in exp.base_dir.rglob("*") if p.is_file())
    assert _repo_paths_snapshot() == before

    # --- ExperimentRun schema unchanged: local Phase 8/9 fields are not persisted ---
    from app.experiments.spec import ExperimentRun
    for field in ("root_symbol", "source", "adjustment_method",
                  "contracts", "roll_events", "raw_data_version_hash"):
        assert field not in ExperimentRun.model_fields

    # --- reporting module does not train / import training or ML frameworks ---
    for name in ("__init__.py", "summary.py", "render.py"):
        src = (_BACKEND / "app" / "reporting" / name).read_text(encoding="utf-8")
        for token in ("train_model", "run_local_futures_ml_experiment",
                      "build_feature_matrix", "build_label_matrix"):
            assert token not in src, f"{name}:{token}"
        assert not re.search(
            r"(?m)^\s*(from|import)\s+\S*"
            r"(requests|urllib|httpx|aiohttp|socket|yfinance|ibkr|sklearn|xgboost|lightgbm|torch|tensorflow)\b",
            src,
        ), name
