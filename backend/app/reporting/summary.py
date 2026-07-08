"""
Experiment reporting — structured summaries + comparison rows (Phase 10 — commit 1).

Thin wrappers over the existing Phase 5 experiment helpers — this module adds
**no** comparison/best logic and does **no** training:

* :func:`summarize_experiment_run` — reuses ``load_experiment_run`` (hash -> run)
  and ``summarize_experiment`` (compact headline).
* :func:`compare_experiment_runs` — reuses ``compare_experiments`` (keeps its
  same-OOS-window / label / dataset guard).
* :func:`best_experiment_run` — reuses ``get_best_experiment``.

The persisted :class:`~app.experiments.spec.ExperimentRun` does **not** carry the
Phase 8/9 local provenance (``root_symbol`` / ``source`` / ``adjustment_method`` /
``contracts`` / ``roll_events`` / ``raw_data_version_hash``), so those are reported
as **"not recorded"** (see :data:`UNAVAILABLE_PROVENANCE_FIELDS`).  No schema
change, no new metrics, no absolute paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.experiments import (
    ExperimentRun,
    ExperimentStore,
    compare_experiments,
    get_best_experiment,
    load_experiment_run,
    summarize_experiment,
)

# Fields the Phase 5 ExperimentRun schema does not persist (Phase 8/9 local
# provenance). Store-backed reports mark these "not recorded".
UNAVAILABLE_PROVENANCE_FIELDS: tuple[str, ...] = (
    "root_symbol",
    "source",
    "adjustment_method",
    "contracts",
    "roll_events",
    "raw_data_version_hash",
)
NOT_RECORDED = "not recorded"

# Columns of a ``compare_experiments`` frame that are not metric values.
_NON_METRIC_COLUMNS = frozenset(
    {"train_run_hash", "model_type", "label_column", "validation_start",
     "validation_end", "same_window"}
)

__all__ = [
    "UNAVAILABLE_PROVENANCE_FIELDS",
    "NOT_RECORDED",
    "ExperimentRunSummary",
    "ExperimentComparisonRow",
    "summarize_experiment_run",
    "compare_experiment_runs",
    "best_experiment_run",
]


@dataclass(frozen=True)
class ExperimentRunSummary:
    """A read-only, render-ready summary of one persisted ``ExperimentRun``."""

    train_run_hash: str
    model_type: str
    task_type: str
    feature_columns: list[str]
    label_column: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    ml_metrics: dict
    backtest_metrics: dict
    baseline_metrics: dict
    hash_chain: dict
    artifact_paths: dict
    created_at: str
    n_oos_rows: int
    n_scored_rows: int
    headline: dict                       # reused compact `summarize_experiment` output
    unavailable_provenance: dict         # field -> "not recorded"
    git_commit: Optional[str] = None
    code_version: Optional[str] = None


@dataclass(frozen=True)
class ExperimentComparisonRow:
    """One comparison row (metrics from ``compare_experiments``)."""

    train_run_hash: str
    model_type: str
    task_type: str
    label_column: str
    validation_start: str
    validation_end: str
    metrics: dict
    same_window: Optional[bool] = None


def _resolve_run(run_or_hash, store: Optional[ExperimentStore]) -> ExperimentRun:
    """An ``ExperimentRun`` from either a run object or a hash (reuses the loader)."""
    if isinstance(run_or_hash, ExperimentRun):
        return run_or_hash
    if isinstance(run_or_hash, str):
        if store is None:
            raise ValueError("a store is required to resolve a train_run_hash")
        return load_experiment_run(run_or_hash, store=store).run
    raise TypeError(f"expected ExperimentRun or hash str, got {type(run_or_hash).__name__}")


def summarize_experiment_run(
    run_or_hash, *, store: Optional[ExperimentStore] = None
) -> ExperimentRunSummary:
    """Summarize one run (given an ``ExperimentRun`` or a hash + store)."""
    run = _resolve_run(run_or_hash, store)
    return ExperimentRunSummary(
        train_run_hash=run.train_run_hash,
        model_type=run.model_type,
        task_type=run.task_type,
        feature_columns=list(run.feature_columns),
        label_column=run.label_column,
        train_start=run.train_start.isoformat(),
        train_end=run.train_end.isoformat(),
        validation_start=run.validation_start.isoformat(),
        validation_end=run.validation_end.isoformat(),
        ml_metrics=dict(run.metrics),
        backtest_metrics=dict(run.backtest_metrics),
        baseline_metrics=dict(run.baseline_metrics),
        hash_chain={
            "continuous_config_hash": run.continuous_config_hash,
            "feature_config_hash": run.feature_config_hash,
            "label_config_hash": run.label_config_hash,
            "dataset_config_hash": run.dataset_config_hash,
            "model_config_hash": run.model_config_hash,
            "train_run_hash": run.train_run_hash,
        },
        artifact_paths=dict(run.artifact_paths),  # relative, as stored
        created_at=run.created_at,
        git_commit=run.git_commit,
        code_version=run.code_version,
        n_oos_rows=run.n_oos_rows,
        n_scored_rows=run.n_scored_rows,
        headline=dict(summarize_experiment(run)),  # reuse the Phase 5 compact summary
        unavailable_provenance={f: NOT_RECORDED for f in UNAVAILABLE_PROVENANCE_FIELDS},
    )


def compare_experiment_runs(
    runs_or_hashes,
    *,
    store: ExperimentStore,
    metrics: tuple[str, ...] | None = None,
    allow_different_windows: bool = False,
) -> list[ExperimentComparisonRow]:
    """Compare runs into rows, reusing ``compare_experiments`` (and its guard).

    Resolves each item to an ``ExperimentRun`` first (so ``task_type`` — which the
    comparison frame does not carry — is available), then reads metrics + the
    optional ``same_window`` flag from the frame (row order is preserved).
    """
    runs = [_resolve_run(item, store) for item in runs_or_hashes]
    frame = compare_experiments(
        runs, store=store, metrics=metrics, allow_different_windows=allow_different_windows
    )
    metric_cols = [c for c in frame.columns if c not in _NON_METRIC_COLUMNS]

    rows: list[ExperimentComparisonRow] = []
    for run, (_, frow) in zip(runs, frame.iterrows()):
        row_metrics = {
            m: (None if pd.isna(frow[m]) else float(frow[m])) for m in metric_cols
        }
        same = bool(frow["same_window"]) if "same_window" in frame.columns else None
        rows.append(
            ExperimentComparisonRow(
                train_run_hash=run.train_run_hash,
                model_type=run.model_type,
                task_type=run.task_type,
                label_column=run.label_column,
                validation_start=run.validation_start.isoformat(),
                validation_end=run.validation_end.isoformat(),
                metrics=row_metrics,
                same_window=same,
            )
        )
    return rows


def best_experiment_run(
    *,
    store: ExperimentStore,
    metric: str = "sharpe",
    maximize: bool = True,
    allow_different_windows: bool = False,
) -> ExperimentRunSummary:
    """Summarize the best run by ``metric`` (reuses ``get_best_experiment``)."""
    run = get_best_experiment(
        store=store, metric=metric, maximize=maximize,
        allow_different_windows=allow_different_windows,
    )
    return summarize_experiment_run(run)
