"""
Phase 10 commit 1 — experiment reporting module.

Covers the reporting layer (`app.reporting`) over persisted `ExperimentRun`
artifacts.  Test **setup** creates real saved runs via the Phase 9 pipeline
(fixtures need persisted runs), but the reporting module itself does no training.
Everything lives under `tmp_path`; no network; nothing written outside `tmp_path`.
"""

from __future__ import annotations

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
