"""
Experiment registry APIs on top of :class:`ExperimentStore` (Phase 5 — commit 3).

Read-side registry: load a single run (metadata + optional frames, with artifact
existence checks), list all runs under a store, compare runs **on the same OOS
window**, and pick the best run by a metric.  No saving / Phase 4 integration here
(that lands in commit 4); no network; synthetic data only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.experiments.spec import ExperimentError, ExperimentRun
from app.experiments.store import ExperimentStore, _FRAME_NAMES

# Default columns for compare_experiments: backtest metrics + task metrics
# (only those present per run are filled; the rest are NaN).
DEFAULT_COMPARE_METRICS = (
    "total_return",
    "sharpe",
    "max_drawdown",
    "total_transaction_cost",
    "accuracy",
    "f1",
    "mse",
    "mae",
    "r2",
    "information_coefficient",
)

_FILTERABLE_FIELDS = frozenset(
    {"model_type", "label_column", "task_type", "dataset_config_hash",
     "validation_start", "validation_end"}
)

# The (window, label, dataset) tuple that must match for a fair comparison.
def _window_key(run: ExperimentRun):
    return (run.validation_start, run.validation_end, run.label_column, run.dataset_config_hash)


@dataclass
class LoadedExperiment:
    """A loaded run: validated metadata plus any frames requested."""

    run: ExperimentRun
    frames: dict = field(default_factory=dict)


def load_experiment_run(
    train_run_hash: str,
    *,
    store: ExperimentStore,
    load_frames: bool = False,
) -> LoadedExperiment:
    """Load one run's metadata (and optionally its frames).

    Verifies the directory name matches ``metadata.train_run_hash`` (via the
    store) and that every ``artifact_paths`` entry exists on disk.  Raises
    :class:`ExperimentError` with a clear message on any missing artifact."""
    run = store.read_metadata(train_run_hash)
    run_dir = store.run_dir(run.train_run_hash)
    for key, rel in run.artifact_paths.items():
        if not (run_dir / rel).exists():
            raise ExperimentError(
                f"artifact {key!r} referenced by metadata is missing: {run_dir / rel}"
            )
    frames: dict = {}
    if load_frames:
        for name in _FRAME_NAMES:
            try:
                frames[name] = store.read_frame(run.train_run_hash, name)
            except ExperimentError:
                continue  # this run simply has no such frame
    return LoadedExperiment(run=run, frames=frames)


def _matches_filters(run: ExperimentRun, filters: dict) -> bool:
    for key, value in filters.items():
        if key not in _FILTERABLE_FIELDS:
            raise ExperimentError(
                f"unknown filter key {key!r}; allowed: {sorted(_FILTERABLE_FIELDS)}"
            )
        if getattr(run, key) != value:
            return False
    return True


def list_experiments(*, store: ExperimentStore, filters: dict | None = None) -> list[ExperimentRun]:
    """List all runs under ``store.base_dir``, deterministically sorted.

    Directories without a ``metadata.json`` are skipped (not experiment runs);
    a directory **with** an invalid/tampered ``metadata.json`` raises via the
    store.  Sorted by ``(created_at, train_run_hash)``."""
    runs: list[ExperimentRun] = []
    base = store.base_dir
    if base.exists():
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            if not (child / "metadata.json").exists():
                continue  # not an experiment run
            runs.append(store.read_metadata(child.name))
    if filters:
        runs = [r for r in runs if _matches_filters(r, filters)]
    runs.sort(key=lambda r: (r.created_at, r.train_run_hash))
    return runs


def _resolve(item, store: ExperimentStore) -> ExperimentRun:
    if isinstance(item, ExperimentRun):
        return item
    if isinstance(item, str):
        return store.read_metadata(item)
    raise ExperimentError(
        f"expected an ExperimentRun or a train_run_hash str, got {type(item).__name__}"
    )


def _metric_value(run: ExperimentRun, metric: str):
    if metric in run.backtest_metrics:
        return run.backtest_metrics[metric]
    if metric in run.metrics:
        return run.metrics[metric]
    return float("nan")


def compare_experiments(
    runs_or_hashes,
    *,
    store: ExperimentStore,
    metrics: tuple[str, ...] | None = None,
    allow_different_windows: bool = False,
) -> pd.DataFrame:
    """Compare runs as one row each.  By default requires all runs to share the
    same ``(validation_start, validation_end, label_column, dataset_config_hash)``
    and raises :class:`ExperimentError` otherwise.  With
    ``allow_different_windows=True`` the comparison proceeds and a ``same_window``
    flag column marks runs that match the first run's window/label/dataset."""
    runs = [_resolve(item, store) for item in runs_or_hashes]
    if not runs:
        raise ExperimentError("no experiments to compare")

    metric_cols = tuple(metrics) if metrics else DEFAULT_COMPARE_METRICS
    reference = _window_key(runs[0])
    same_window = [_window_key(r) == reference for r in runs]

    if not allow_different_windows and not all(same_window):
        raise ExperimentError(
            "experiments do not share the same OOS window / label / dataset; "
            "pass allow_different_windows=True to compare anyway"
        )

    rows: list[dict] = []
    for run, same in zip(runs, same_window):
        row = {
            "train_run_hash": run.train_run_hash,
            "model_type": run.model_type,
            "label_column": run.label_column,
            "validation_start": run.validation_start,
            "validation_end": run.validation_end,
        }
        if allow_different_windows:
            row["same_window"] = same
        for metric in metric_cols:
            row[metric] = _metric_value(run, metric)
        rows.append(row)
    return pd.DataFrame(rows)


def get_best_experiment(
    *,
    store: ExperimentStore,
    metric: str = "sharpe",
    maximize: bool = True,
    allow_different_windows: bool = False,
) -> ExperimentRun:
    """Return the best run by ``metric`` (deterministic tie-break by
    ``train_run_hash``).  Raises if there are no runs or the metric is absent
    everywhere; enforces the same-OOS-window guard unless overridden."""
    runs = list_experiments(store=store)
    if not runs:
        raise ExperimentError("no experiments found under the store")

    table = compare_experiments(
        runs, store=store, metrics=(metric,), allow_different_windows=allow_different_windows
    )
    if metric not in table.columns:
        raise ExperimentError(f"metric {metric!r} is not a comparable column")
    values = pd.to_numeric(table[metric], errors="coerce")
    if values.isna().all():
        raise ExperimentError(f"metric {metric!r} is unavailable for all experiments")

    ranked = (
        table.assign(_metric=values)
        .sort_values(
            by=["_metric", "train_run_hash"],
            ascending=[not maximize, True],
            na_position="last",
        )
        .reset_index(drop=True)
    )
    best_hash = ranked.iloc[0]["train_run_hash"]
    return next(r for r in runs if r.train_run_hash == best_hash)
