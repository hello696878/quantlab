"""
Phase 12 commit 1 — read-only experiment catalog: rows, discovery, filtering.

Covers ``app.experiment_catalog`` (catalog core only): building deterministic,
JSON-safe rows from persisted ``ExperimentRun`` metadata and filtering them
safely.  Fixtures hand-construct tiny ``ExperimentRun`` objects and write them
through the existing ``ExperimentStore`` (fast — no ML pipeline needed; the
integrated e2e over real Phase 9/11 runs lands in a later commit).  Everything
lives under ``tmp_path``; no network; nothing written outside ``tmp_path``.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.experiment_catalog import (
    CatalogError,
    ExperimentCatalogFilter,
    ExperimentCatalogRow,
    ExperimentCompatibilityGroup,
    ExperimentLeaderboardSpec,
    build_experiment_catalog,
    export_catalog_csv,
    export_catalog_json,
    export_catalog_markdown,
    filter_experiment_catalog,
    group_compatible_runs,
    list_experiment_runs,
    rank_experiment_catalog,
)
from app.experiment_catalog import catalog as catalog_module
from app.experiment_catalog import leaderboard as leaderboard_module
from app.experiment_catalog.catalog import _row_from_run
from app.experiments import (
    ExperimentError,
    ExperimentRun,
    ExperimentStore,
    get_best_experiment,
)
from app.reporting import DISCLAIMERS

_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]

_FEATURES = ("feature__return_20", "feature__moving_average_gap_10_50")
_T0 = "2026-07-11T00:00:00+00:00"
_T1 = "2026-07-11T01:00:00+00:00"
_T2 = "2026-07-11T02:00:00+00:00"


def _repo_snapshot() -> tuple[bool, bool, bool]:
    return (
        (_REPO_ROOT / "data").exists(),
        (_REPO_ROOT / "artifacts").exists(),
        (_BACKEND / "data").exists(),
    )


def _mk_run(train_run_hash: str, **overrides) -> ExperimentRun:
    """A tiny valid ExperimentRun with per-test overrides."""
    base = dict(
        train_run_hash=train_run_hash,
        continuous_config_hash=f"cch_{train_run_hash}",
        feature_config_hash=f"fch_{train_run_hash}",
        label_config_hash=f"lch_{train_run_hash}",
        dataset_config_hash="dch_shared",
        model_config_hash=f"mch_{train_run_hash}",
        model_type="ridge_regression",
        task_type="regression",
        feature_columns=_FEATURES,
        label_column="label__forward_return_1",
        train_start=date(2024, 4, 1),
        train_end=date(2024, 6, 5),
        validation_start=date(2024, 6, 6),
        validation_end=date(2024, 9, 15),
        metrics={"mse": 0.10},
        backtest_metrics={"sharpe": 1.5, "total_return": 0.2},
        baseline_metrics={"no_trade": {"sharpe": 0.0, "total_return": 0.0}},
        created_at=_T1,
        git_commit="abc123",
        code_version="v1",
        n_oos_rows=70,
        n_scored_rows=68,
    )
    base.update(overrides)
    return ExperimentRun(**base)


def _store_with_three_runs(tmp_path: Path) -> ExperimentStore:
    """Three hand-built runs with variety for ordering / filter tests.

    Expected discovery order (by created_at): run_c (T0), run_a (T1), run_b (T2).
    """
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    run_a = _mk_run("run_a")  # ridge / regression / W1 / sharpe 1.5
    run_b = _mk_run(
        "run_b",
        model_type="dummy_baseline",
        label_column="label__forward_return_5",
        metrics={"mse": 0.30},
        backtest_metrics={"sharpe": 0.5, "total_return": -0.1},
        created_at=_T2,
        git_commit=None,
        code_version=None,
    )
    run_c = _mk_run(
        "run_c",
        model_type="logistic_regression",
        task_type="classification",
        validation_end=date(2024, 9, 30),
        feature_columns=tuple(reversed(_FEATURES)),
        metrics={"accuracy": 0.6},
        backtest_metrics={"sharpe": 0.9},
        created_at=_T0,
    )
    for run in (run_a, run_b, run_c):
        store.write_metadata(run)
    return store


# --------------------------------------------------------------------------- #
# discovery + row construction
# --------------------------------------------------------------------------- #


def test_build_catalog_discovers_runs_in_created_at_order(tmp_path):
    store = _store_with_three_runs(tmp_path)
    rows = build_experiment_catalog(store)
    assert [r.train_run_hash for r in rows] == ["run_c", "run_a", "run_b"]
    assert all(isinstance(r, ExperimentCatalogRow) for r in rows)
    # delegation: same runs, same order as the existing registry listing
    assert [r.train_run_hash for r in list_experiment_runs(store)] == ["run_c", "run_a", "run_b"]


def test_row_field_order_is_stable(tmp_path):
    expected = [
        "train_run_hash",
        "created_at",
        "model_type",
        "task_type",
        "train_start",
        "train_end",
        "validation_start",
        "validation_end",
        "feature_columns",
        "label_column",
        "n_oos_rows",
        "n_scored_rows",
        "metrics",
        "baseline_metrics",
        "artifact_dir",
        "git_commit",
        "code_version",
        "continuous_config_hash",
        "feature_config_hash",
        "label_config_hash",
        "dataset_config_hash",
        "model_config_hash",
    ]
    assert [f.name for f in dataclasses.fields(ExperimentCatalogRow)] == expected


def test_row_values_copied_from_run(tmp_path):
    store = _store_with_three_runs(tmp_path)
    row = next(r for r in build_experiment_catalog(store) if r.train_run_hash == "run_a")
    assert row.model_type == "ridge_regression" and row.task_type == "regression"
    assert row.train_start == "2024-04-01" and row.validation_end == "2024-09-15"
    assert row.feature_columns == _FEATURES and isinstance(row.feature_columns, tuple)
    assert row.label_column == "label__forward_return_1"
    assert (row.n_oos_rows, row.n_scored_rows) == (70, 68)
    assert row.git_commit == "abc123" and row.code_version == "v1"
    # hash chain copied verbatim from the persisted run
    assert row.continuous_config_hash == "cch_run_a"
    assert row.feature_config_hash == "fch_run_a"
    assert row.label_config_hash == "lch_run_a"
    assert row.dataset_config_hash == "dch_shared"
    assert row.model_config_hash == "mch_run_a"


def test_row_metrics_default_selection_and_precedence(tmp_path):
    store = ExperimentStore(tmp_path / "exp", prefer_parquet=False)
    # 'sharpe' present in BOTH dicts: the backtest value must win (existing precedence)
    store.write_metadata(
        _mk_run("run_p", metrics={"mse": 0.1, "sharpe": 99.0}, backtest_metrics={"sharpe": 1.5})
    )
    row = build_experiment_catalog(store)[0]
    assert set(row.metrics) == set(
        ("total_return", "sharpe", "max_drawdown", "total_transaction_cost",
         "accuracy", "f1", "mse", "mae", "r2", "information_coefficient")
    )
    assert row.metrics["sharpe"] == 1.5  # backtest_metrics wins
    assert row.metrics["mse"] == 0.1
    assert row.metrics["accuracy"] is None  # missing -> None, not invented


def test_build_catalog_custom_metric_selection(tmp_path):
    store = _store_with_three_runs(tmp_path)
    rows = build_experiment_catalog(store, metrics=("sharpe",))
    assert all(list(r.metrics) == ["sharpe"] for r in rows)
    with pytest.raises(CatalogError):
        build_experiment_catalog(store, metrics=())


def test_artifact_dir_relative_and_no_absolute_paths(tmp_path):
    store = _store_with_three_runs(tmp_path)
    for row in build_experiment_catalog(store):
        assert row.artifact_dir == row.train_run_hash
        dumped = json.dumps(dataclasses.asdict(row), allow_nan=False, sort_keys=True)
        assert ":\\" not in dumped and ":/" not in dumped  # no drive-letter paths
        assert tmp_path.name not in dumped  # no tmp dir leakage


def test_rows_are_strict_json_safe(tmp_path):
    store = _store_with_three_runs(tmp_path)
    for row in build_experiment_catalog(store):
        text = json.dumps(dataclasses.asdict(row), allow_nan=False, sort_keys=True)
        assert "NaN" not in text and "Infinity" not in text
        json.loads(text)


def test_nan_and_infinity_sanitized_to_none():
    # in-memory run (the store's canonical JSON would drop these keys at write
    # time; the row builder must sanitize regardless of how the run arrives)
    run = _mk_run(
        "run_nan",
        metrics={"mse": float("nan")},
        backtest_metrics={"sharpe": float("inf")},
        baseline_metrics={"no_trade": {"sharpe": float("nan"), "total_return": 0.25}},
    )
    row = _row_from_run(run, ("sharpe", "mse"))
    assert row.metrics == {"sharpe": None, "mse": None}
    assert row.baseline_metrics == {"no_trade": {"sharpe": None, "total_return": 0.25}}
    json.dumps(dataclasses.asdict(row), allow_nan=False)


def test_unavailable_git_commit_and_code_version_stay_none(tmp_path):
    store = _store_with_three_runs(tmp_path)
    row = next(r for r in build_experiment_catalog(store) if r.train_run_hash == "run_b")
    assert row.git_commit is None and row.code_version is None


def test_unpersisted_provenance_not_invented(tmp_path):
    store = _store_with_three_runs(tmp_path)
    row = build_experiment_catalog(store)[0]
    for absent in ("root_symbol", "source", "raw_data_version_hash"):
        assert not hasattr(row, absent)


# --------------------------------------------------------------------------- #
# store edge cases
# --------------------------------------------------------------------------- #


def test_empty_store_raises_catalog_error(tmp_path):
    store = ExperimentStore(tmp_path / "empty", prefer_parquet=False)
    with pytest.raises(CatalogError):
        build_experiment_catalog(store)


def test_non_run_directory_is_skipped(tmp_path):
    store = _store_with_three_runs(tmp_path)
    stray = store.base_dir / "not_a_run"
    stray.mkdir()
    (stray / "notes.txt").write_text("no metadata here", encoding="utf-8")
    rows = build_experiment_catalog(store)
    assert [r.train_run_hash for r in rows] == ["run_c", "run_a", "run_b"]


def test_corrupt_metadata_raises_clearly(tmp_path):
    store = _store_with_three_runs(tmp_path)
    bad = store.base_dir / "run_bad"
    bad.mkdir()
    (bad / "metadata.json").write_text("{ this is not valid json", encoding="utf-8")
    with pytest.raises((ExperimentError, ValidationError)):
        build_experiment_catalog(store)


# --------------------------------------------------------------------------- #
# filtering
# --------------------------------------------------------------------------- #


def _rows(tmp_path):
    return build_experiment_catalog(_store_with_three_runs(tmp_path))


def _hashes(rows):
    return [r.train_run_hash for r in rows]


def test_filter_by_model_type(tmp_path):
    rows = _rows(tmp_path)
    out = filter_experiment_catalog(rows, ExperimentCatalogFilter(model_type="ridge_regression"))
    assert _hashes(out) == ["run_a"]


def test_filter_by_task_type(tmp_path):
    rows = _rows(tmp_path)
    out = filter_experiment_catalog(rows, ExperimentCatalogFilter(task_type="classification"))
    assert _hashes(out) == ["run_c"]


def test_filter_by_label_column(tmp_path):
    rows = _rows(tmp_path)
    out = filter_experiment_catalog(
        rows, ExperimentCatalogFilter(label_column="label__forward_return_1")
    )
    assert _hashes(out) == ["run_c", "run_a"]  # run_b uses a different label


def test_filter_by_windows(tmp_path):
    rows = _rows(tmp_path)
    out = filter_experiment_catalog(rows, ExperimentCatalogFilter(validation_end="2024-09-15"))
    assert _hashes(out) == ["run_a", "run_b"]  # run_c has a shifted validation_end
    # date objects are accepted and normalized to ISO
    out2 = filter_experiment_catalog(
        rows, ExperimentCatalogFilter(validation_end=date(2024, 9, 15))
    )
    assert _hashes(out2) == ["run_a", "run_b"]
    # train window matches all three (identical train windows)
    out3 = filter_experiment_catalog(rows, ExperimentCatalogFilter(train_start="2024-04-01"))
    assert _hashes(out3) == ["run_c", "run_a", "run_b"]


def test_filter_feature_columns_exact_order(tmp_path):
    rows = _rows(tmp_path)
    out = filter_experiment_catalog(rows, ExperimentCatalogFilter(feature_columns=_FEATURES))
    assert _hashes(out) == ["run_a", "run_b"]  # run_c has the reversed order


def test_filter_feature_columns_as_set(tmp_path):
    rows = _rows(tmp_path)
    out = filter_experiment_catalog(
        rows,
        ExperimentCatalogFilter(feature_columns=tuple(reversed(_FEATURES)), features_as_set=True),
    )
    assert _hashes(out) == ["run_c", "run_a", "run_b"]  # same set, any order


def test_filter_require_metric(tmp_path):
    rows = _rows(tmp_path)
    out = filter_experiment_catalog(rows, ExperimentCatalogFilter(require_metric="accuracy"))
    assert _hashes(out) == ["run_c"]  # only run_c has a numeric accuracy


def test_filter_metric_min_max(tmp_path):
    rows = _rows(tmp_path)  # sharpe: run_c 0.9, run_a 1.5, run_b 0.5
    low = filter_experiment_catalog(
        rows, ExperimentCatalogFilter(require_metric="sharpe", metric_min=0.9)
    )
    assert _hashes(low) == ["run_c", "run_a"]
    high = filter_experiment_catalog(
        rows, ExperimentCatalogFilter(require_metric="sharpe", metric_max=0.9)
    )
    assert _hashes(high) == ["run_c", "run_b"]


def test_metric_threshold_without_require_metric_fails():
    with pytest.raises(CatalogError):
        ExperimentCatalogFilter(metric_min=1.0)
    with pytest.raises(CatalogError):
        ExperimentCatalogFilter(metric_max=1.0)


def test_invalid_filter_combinations_fail():
    with pytest.raises(CatalogError):
        ExperimentCatalogFilter(features_as_set=True)  # without feature_columns
    with pytest.raises(CatalogError):
        ExperimentCatalogFilter(require_metric="sharpe", metric_min=2.0, metric_max=1.0)
    with pytest.raises(CatalogError):
        ExperimentCatalogFilter(created_after=_T2, created_before=_T0)


def test_filter_require_metric_not_in_selection_fails(tmp_path):
    rows = build_experiment_catalog(_store_with_three_runs(tmp_path), metrics=("sharpe",))
    with pytest.raises(CatalogError):
        filter_experiment_catalog(rows, ExperimentCatalogFilter(require_metric="nonexistent"))


def test_filter_created_at_bounds(tmp_path):
    rows = _rows(tmp_path)
    after = filter_experiment_catalog(rows, ExperimentCatalogFilter(created_after=_T1))
    assert _hashes(after) == ["run_a", "run_b"]  # inclusive lower bound
    before = filter_experiment_catalog(rows, ExperimentCatalogFilter(created_before=_T1))
    assert _hashes(before) == ["run_c", "run_a"]  # inclusive upper bound


def test_filters_preserve_order_and_allow_empty_result(tmp_path):
    rows = _rows(tmp_path)
    out = filter_experiment_catalog(rows, ExperimentCatalogFilter(task_type="regression"))
    assert _hashes(out) == ["run_a", "run_b"]  # original relative order kept
    empty = filter_experiment_catalog(rows, ExperimentCatalogFilter(model_type="nonexistent"))
    assert empty == []  # empty result is valid, not an error


# --------------------------------------------------------------------------- #
# guard rails
# --------------------------------------------------------------------------- #


def test_catalog_module_has_no_forbidden_imports():
    src = Path(catalog_module.__file__).read_text(encoding="utf-8")
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
        assert token not in src, f"catalog.py must not reference {token!r}"


def test_catalog_module_respects_layer_boundaries():
    src = Path(catalog_module.__file__).read_text(encoding="utf-8")
    for token in (
        "app.reporting",
        "app.local_pipeline",
        "app.batch_experiments",
        "run_local_futures_ml_experiment",
        "train_model",
        "build_feature_matrix",
        "build_label_matrix",
    ):
        assert token not in src, f"catalog.py must not reference {token!r}"


def test_catalog_module_does_no_hashing():
    src = Path(catalog_module.__file__).read_text(encoding="utf-8")
    for token in ("hashlib", "sha256", "compute_config_hash"):
        assert token not in src, f"catalog.py must not reference {token!r}"


def test_catalog_creates_no_repo_artifacts(tmp_path):
    before = _repo_snapshot()
    rows = _rows(tmp_path)
    filter_experiment_catalog(rows, ExperimentCatalogFilter(model_type="ridge_regression"))
    assert _repo_snapshot() == before


# --------------------------------------------------------------------------- #
# hand-built rows for pure grouping / ranking / export tests
# --------------------------------------------------------------------------- #


def _mk_row(train_run_hash: str, *, sharpe=1.0, mse=None, **overrides) -> ExperimentCatalogRow:
    base = dict(
        train_run_hash=train_run_hash,
        created_at=_T1,
        model_type="ridge_regression",
        task_type="regression",
        train_start="2024-04-01",
        train_end="2024-06-05",
        validation_start="2024-06-06",
        validation_end="2024-09-15",
        feature_columns=_FEATURES,
        label_column="label__forward_return_1",
        n_oos_rows=70,
        n_scored_rows=68,
        metrics={"sharpe": sharpe, "mse": mse},
        baseline_metrics={"no_trade": {"sharpe": 0.0, "total_return": 0.0}},
        artifact_dir=train_run_hash,
        git_commit=None,
        code_version=None,
        continuous_config_hash="cch",
        feature_config_hash="fch",
        label_config_hash="lch",
        dataset_config_hash="dch",
        model_config_hash="mch",
    )
    base.update(overrides)
    return ExperimentCatalogRow(**base)


# --------------------------------------------------------------------------- #
# compatibility grouping
# --------------------------------------------------------------------------- #


def test_group_compatible_runs_deterministic_ids_and_member_order():
    r_zz = _mk_row("zz")
    r_aa = _mk_row("aa")
    r_shifted = _mk_row("mm", validation_end="2024-09-30")
    groups = group_compatible_runs([r_zz, r_aa, r_shifted])

    assert [g.group_id for g in groups] == ["group_0000", "group_0001"]
    # groups ordered by sorted key: 2024-09-15 window sorts before 2024-09-30
    assert groups[0].validation_end == "2024-09-15"
    assert groups[1].validation_end == "2024-09-30"
    # members preserve incoming row order (zz before aa), not hash order
    assert groups[0].train_run_hashes == ("zz", "aa")
    assert groups[1].train_run_hashes == ("mm",)
    # deterministic across calls
    assert group_compatible_runs([r_zz, r_aa, r_shifted]) == groups


def test_group_key_includes_task_type():
    r_reg = _mk_row("aa")
    r_cls = _mk_row("bb", task_type="classification")
    groups = group_compatible_runs([r_reg, r_cls])
    assert len(groups) == 2  # stricter than the Phase 10 guard key


def test_two_validation_windows_produce_two_groups(tmp_path):
    # store-backed rows: run_b differs by label, run_c by window/task -> 3 groups
    rows = _rows(tmp_path)
    groups = group_compatible_runs(rows)
    assert len(groups) == 3
    assert [g.group_id for g in groups] == ["group_0000", "group_0001", "group_0002"]


def test_group_uses_persisted_fields_only():
    group = group_compatible_runs([_mk_row("aa")])[0]
    assert isinstance(group, ExperimentCompatibilityGroup)
    for absent in ("root_symbol", "source", "raw_data_version_hash"):
        assert not hasattr(group, absent)


def test_group_empty_input_yields_empty_list():
    assert group_compatible_runs([]) == []


# --------------------------------------------------------------------------- #
# leaderboard spec + ranking
# --------------------------------------------------------------------------- #


def test_leaderboard_spec_validation():
    with pytest.raises(CatalogError):
        ExperimentLeaderboardSpec(metric="")
    with pytest.raises(CatalogError):
        ExperimentLeaderboardSpec(top_n=0)
    with pytest.raises(CatalogError):
        ExperimentLeaderboardSpec(top_n=-3)
    with pytest.raises(CatalogError):
        ExperimentLeaderboardSpec(on_missing_metric="drop")


def test_rank_maximize_and_minimize():
    rows = [_mk_row("aa", sharpe=0.5), _mk_row("bb", sharpe=1.5), _mk_row("cc", sharpe=0.9)]
    top = rank_experiment_catalog(rows, ExperimentLeaderboardSpec(metric="sharpe"))
    assert [r.train_run_hash for r in top] == ["bb", "cc", "aa"]
    low = rank_experiment_catalog(
        rows, ExperimentLeaderboardSpec(metric="sharpe", maximize=False)
    )
    assert [r.train_run_hash for r in low] == ["aa", "cc", "bb"]


def test_rank_top_n():
    rows = [_mk_row("aa", sharpe=0.5), _mk_row("bb", sharpe=1.5), _mk_row("cc", sharpe=0.9)]
    top2 = rank_experiment_catalog(rows, ExperimentLeaderboardSpec(metric="sharpe", top_n=2))
    assert [r.train_run_hash for r in top2] == ["bb", "cc"]


def test_rank_tie_break_by_train_run_hash():
    rows = [_mk_row("zz", sharpe=1.0), _mk_row("aa", sharpe=1.0)]
    for maximize in (True, False):
        ranked = rank_experiment_catalog(
            rows, ExperimentLeaderboardSpec(metric="sharpe", maximize=maximize)
        )
        assert [r.train_run_hash for r in ranked] == ["aa", "zz"]


def test_rank_missing_metric_exclude():
    rows = [_mk_row("aa", sharpe=None), _mk_row("bb", sharpe=1.5)]
    ranked = rank_experiment_catalog(rows, ExperimentLeaderboardSpec(metric="sharpe"))
    assert [r.train_run_hash for r in ranked] == ["bb"]  # aa dropped deterministically


def test_rank_metric_unavailable_for_all_fails():
    rows = [_mk_row("aa", sharpe=None), _mk_row("bb", sharpe=None)]
    with pytest.raises(CatalogError):
        rank_experiment_catalog(rows, ExperimentLeaderboardSpec(metric="sharpe"))


def test_rank_missing_metric_fail_mode():
    rows = [_mk_row("aa", sharpe=1.0), _mk_row("bb", sharpe=None)]
    with pytest.raises(CatalogError):
        rank_experiment_catalog(
            rows, ExperimentLeaderboardSpec(metric="sharpe", on_missing_metric="fail")
        )


def test_rank_metric_not_in_selection_fails():
    rows = [_mk_row("aa")]
    with pytest.raises(CatalogError):
        rank_experiment_catalog(rows, ExperimentLeaderboardSpec(metric="accuracy"))


def test_rank_require_compatible_single_group_ok():
    rows = [_mk_row("aa", sharpe=0.5), _mk_row("bb", sharpe=1.5)]
    ranked = rank_experiment_catalog(
        rows, ExperimentLeaderboardSpec(metric="sharpe", require_compatible=True)
    )
    assert [r.train_run_hash for r in ranked] == ["bb", "aa"]


def test_rank_require_compatible_mixed_groups_fails():
    rows = [_mk_row("aa"), _mk_row("bb", validation_end="2024-09-30")]
    with pytest.raises(CatalogError):
        rank_experiment_catalog(
            rows, ExperimentLeaderboardSpec(metric="sharpe", require_compatible=True)
        )


def test_rank_empty_input_fails():
    with pytest.raises(CatalogError):
        rank_experiment_catalog([], ExperimentLeaderboardSpec())


def test_rank_top1_parity_with_get_best_experiment(tmp_path):
    store = _store_with_three_runs(tmp_path)
    rows = build_experiment_catalog(store)
    for maximize in (True, False):
        best_run = get_best_experiment(
            store=store, metric="sharpe", maximize=maximize, allow_different_windows=True
        )
        ranked = rank_experiment_catalog(
            rows, ExperimentLeaderboardSpec(metric="sharpe", maximize=maximize, top_n=1)
        )
        assert ranked[0].train_run_hash == best_run.train_run_hash


# --------------------------------------------------------------------------- #
# exporters
# --------------------------------------------------------------------------- #


def test_export_csv_deterministic_and_stable_columns(tmp_path):
    rows = _rows(tmp_path)
    text = export_catalog_csv(rows)
    assert export_catalog_csv(rows) == text  # deterministic across calls
    header = text.splitlines()[0]
    assert header.startswith(
        "train_run_hash,created_at,model_type,task_type,label_column,"
        "train_start,train_end,validation_start,validation_end,feature_columns,"
        "n_oos_rows,n_scored_rows,artifact_dir,git_commit,code_version,"
        "dataset_config_hash"
    )
    # sorted metric columns + sorted flattened baseline columns
    assert "accuracy" in header and "sharpe" in header
    assert "baseline__no_trade__sharpe" in header
    assert len(text.strip().splitlines()) == 4  # header + 3 rows
    # unavailable values are empty cells (run_b has git_commit=None)
    row_b = next(line for line in text.splitlines() if line.startswith("run_b"))
    assert ",," in row_b


def test_export_json_deterministic_and_strict(tmp_path):
    rows = _rows(tmp_path)
    text = export_catalog_json(rows)
    assert export_catalog_json(rows) == text
    assert "NaN" not in text and "Infinity" not in text
    payload = json.loads(text)
    json.dumps(payload, allow_nan=False)  # strict re-serialization
    assert payload["disclaimers"] == list(DISCLAIMERS)
    assert [r["train_run_hash"] for r in payload["rows"]] == ["run_c", "run_a", "run_b"]
    assert isinstance(payload["rows"][0]["feature_columns"], list)
    # unavailable values are null in JSON
    row_b = next(r for r in payload["rows"] if r["train_run_hash"] == "run_b")
    assert row_b["git_commit"] is None


def test_export_markdown_deterministic_with_disclaimers(tmp_path):
    rows = _rows(tmp_path)
    text = export_catalog_markdown(rows)
    assert export_catalog_markdown(rows) == text
    assert text.startswith("# Experiment Catalog")
    assert "| train_run_hash |" in text
    assert "## Disclaimers" in text
    for line in DISCLAIMERS:
        assert line in text


def test_exporters_no_absolute_paths_or_advice_language(tmp_path):
    rows = _rows(tmp_path)
    for text in (
        export_catalog_csv(rows),
        export_catalog_json(rows),
        export_catalog_markdown(rows),
    ):
        assert ":\\" not in text and "C:/" not in text
        assert tmp_path.name not in text
        assert "NaN" not in text and "Infinity" not in text
        lowered = text.lower()
        for token in ("buy", "sell", "allocate", "deploy"):
            assert token not in lowered, f"advice-like token {token!r} leaked into export"


# --------------------------------------------------------------------------- #
# leaderboard module guard rails
# --------------------------------------------------------------------------- #


def test_leaderboard_module_has_no_forbidden_imports():
    src = Path(leaderboard_module.__file__).read_text(encoding="utf-8")
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
        assert token not in src, f"leaderboard.py must not reference {token!r}"


def test_leaderboard_module_respects_layer_boundaries():
    src = Path(leaderboard_module.__file__).read_text(encoding="utf-8")
    for token in (
        "app.local_pipeline",
        "app.batch_experiments",
        "run_local_futures_ml_experiment",
        "train_model",
        "build_feature_matrix",
        "build_label_matrix",
        "ExperimentStore",  # pure over rows: no store reads in this module
    ):
        assert token not in src, f"leaderboard.py must not reference {token!r}"
    for token in ("hashlib", "sha256", "compute_config_hash"):
        assert token not in src, f"leaderboard.py must not reference {token!r}"


def test_leaderboard_creates_no_repo_artifacts(tmp_path):
    before = _repo_snapshot()
    rows = _rows(tmp_path)
    groups = group_compatible_runs(rows)
    rank_experiment_catalog(rows, ExperimentLeaderboardSpec(metric="sharpe"))
    export_catalog_csv(rows), export_catalog_json(rows), export_catalog_markdown(rows)
    assert groups and _repo_snapshot() == before
