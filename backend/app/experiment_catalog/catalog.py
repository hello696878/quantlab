"""
Phase 12 (commit 1) — read-only experiment catalog: rows, discovery, filtering.

Turns persisted ``ExperimentStore`` runs into deterministic, JSON-safe
``ExperimentCatalogRow`` values and filters them safely.  Discovery **delegates
to the existing** ``list_experiments`` (sorted ``(created_at, train_run_hash)``,
non-run directories skipped, corrupt metadata raising via the store) — nothing
is re-implemented and nothing is executed or retrained.

This module is read-only and performs **no file writes**.  It deliberately
imports only the Phase 5 experiments package: no reporting / pipeline / batch
modules, no model-training or feature / label builders, no hashing of any kind,
no network, no vendor libraries.  Metric values are looked up with the same
precedence the existing experiments registry uses (backtest metrics first, then
task metrics) and are sanitized so every row is strict-JSON safe.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from app.experiments import ExperimentRun, ExperimentStore, list_experiments
from app.experiments.registry import DEFAULT_COMPARE_METRICS

__all__ = [
    "CatalogError",
    "ExperimentCatalogRow",
    "ExperimentCatalogFilter",
    "list_experiment_runs",
    "build_experiment_catalog",
    "filter_experiment_catalog",
]


class CatalogError(ValueError):
    """Catalog-specific failure — an empty store, an invalid filter combination,
    a metric threshold without an explicit metric, or a requested metric that is
    not among the catalog's selected metric keys.  Corrupt persisted runs keep
    raising through the existing store (``ExperimentError`` / validation errors);
    they are never swallowed here."""


def _json_safe_value(value: Any) -> Any:
    """Non-finite floats (NaN / +-inf) become None; everything else passes through."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _sanitize(obj: Any) -> Any:
    """Recursively JSON-safe copy of a metrics payload (NaN / Infinity -> None)."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return _json_safe_value(obj)


def _metric_value(run: ExperimentRun, key: str) -> Any:
    """Metric lookup with the existing registry precedence: ``backtest_metrics``
    first, then task ``metrics``; missing or non-finite -> None."""
    if key in run.backtest_metrics:
        return _json_safe_value(run.backtest_metrics[key])
    if key in run.metrics:
        return _json_safe_value(run.metrics[key])
    return None


def _iso(value: "str | date | None") -> Optional[str]:
    """Normalize a date-ish filter value to an ISO string (None passes through)."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, date):
        return value.isoformat()
    raise CatalogError(f"expected an ISO date string or datetime.date, got {type(value).__name__}")


@dataclass(frozen=True)
class ExperimentCatalogRow:
    """One stable, JSON-safe catalog row per persisted run.

    Field order is the deterministic column order.  Dates are ISO strings;
    ``artifact_dir`` is the run's directory name **relative to the store** (never
    absolute); ``metrics`` holds the selected metric keys (missing / non-finite
    -> None); unavailable ``git_commit`` / ``code_version`` stay None.  Fields the
    ``ExperimentRun`` schema does not persist (e.g. root symbol, raw source, raw
    data version) are **not invented** and therefore do not appear here."""

    train_run_hash: str
    created_at: str
    model_type: str
    task_type: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    feature_columns: tuple[str, ...]
    label_column: str
    n_oos_rows: int
    n_scored_rows: int
    metrics: dict
    baseline_metrics: dict
    artifact_dir: str
    git_commit: Optional[str]
    code_version: Optional[str]
    continuous_config_hash: str
    feature_config_hash: str
    label_config_hash: str
    dataset_config_hash: str
    model_config_hash: str


def _row_from_run(run: ExperimentRun, metric_keys: tuple[str, ...]) -> ExperimentCatalogRow:
    """Build one sanitized row from a persisted (or in-memory) ``ExperimentRun``."""
    return ExperimentCatalogRow(
        train_run_hash=run.train_run_hash,
        created_at=run.created_at,
        model_type=run.model_type,
        task_type=run.task_type,
        train_start=run.train_start.isoformat(),
        train_end=run.train_end.isoformat(),
        validation_start=run.validation_start.isoformat(),
        validation_end=run.validation_end.isoformat(),
        feature_columns=tuple(run.feature_columns),
        label_column=run.label_column,
        n_oos_rows=run.n_oos_rows,
        n_scored_rows=run.n_scored_rows,
        metrics={key: _metric_value(run, key) for key in metric_keys},
        baseline_metrics=_sanitize(dict(run.baseline_metrics)),
        artifact_dir=run.train_run_hash,  # the run dir name under the store base
        git_commit=run.git_commit,
        code_version=run.code_version,
        continuous_config_hash=run.continuous_config_hash,
        feature_config_hash=run.feature_config_hash,
        label_config_hash=run.label_config_hash,
        dataset_config_hash=run.dataset_config_hash,
        model_config_hash=run.model_config_hash,
    )


def list_experiment_runs(store: ExperimentStore) -> list[ExperimentRun]:
    """All persisted runs, deterministically ordered — a thin delegation to the
    existing ``list_experiments`` (no re-implemented filesystem discovery)."""
    return list_experiments(store=store)


def build_experiment_catalog(
    store: ExperimentStore, *, metrics: Optional[Sequence[str]] = None
) -> list[ExperimentCatalogRow]:
    """Build catalog rows for every persisted run, in discovery order.

    ``metrics`` selects the metric keys per row; ``None`` uses the existing
    ``DEFAULT_COMPARE_METRICS`` from the experiments registry.  Raises
    :class:`CatalogError` for an empty store or an empty metric selection."""
    metric_keys = DEFAULT_COMPARE_METRICS if metrics is None else tuple(metrics)
    if not metric_keys:
        raise CatalogError("metrics selection must not be empty (or pass None for defaults)")
    runs = list_experiment_runs(store)
    if not runs:
        raise CatalogError(f"no experiment runs found under the store: {store.base_dir.name!r}")
    return [_row_from_run(run, metric_keys) for run in runs]


@dataclass(frozen=True)
class ExperimentCatalogFilter:
    """Optional, safe row constraints (``None`` = no constraint).

    Exact matches only for identity / window fields (no range or overlap
    semantics); ``feature_columns`` matches in order unless ``features_as_set``;
    ``metric_min`` / ``metric_max`` bound the ``require_metric`` value (inclusive);
    ``created_after`` / ``created_before`` are inclusive bounds compared
    lexicographically against the persisted ISO ``created_at``."""

    model_type: Optional[str] = None
    task_type: Optional[str] = None
    label_column: Optional[str] = None
    train_start: Optional[str] = None
    train_end: Optional[str] = None
    validation_start: Optional[str] = None
    validation_end: Optional[str] = None
    feature_columns: Optional[tuple[str, ...]] = None
    features_as_set: bool = False
    require_metric: Optional[str] = None
    metric_min: Optional[float] = None
    metric_max: Optional[float] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None

    def __post_init__(self) -> None:
        if (self.metric_min is not None or self.metric_max is not None) and (
            self.require_metric is None
        ):
            raise CatalogError("metric_min / metric_max require an explicit require_metric")
        if (
            self.metric_min is not None
            and self.metric_max is not None
            and self.metric_min > self.metric_max
        ):
            raise CatalogError("metric_min must not exceed metric_max")
        if self.features_as_set and self.feature_columns is None:
            raise CatalogError("features_as_set requires feature_columns")
        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise CatalogError("created_after must not be later than created_before")
        # normalize inputs: lists -> tuples, dates -> ISO strings (frozen-safe)
        if self.feature_columns is not None:
            object.__setattr__(self, "feature_columns", tuple(self.feature_columns))
        for field_name in ("train_start", "train_end", "validation_start", "validation_end"):
            object.__setattr__(self, field_name, _iso(getattr(self, field_name)))


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _row_matches(row: ExperimentCatalogRow, flt: ExperimentCatalogFilter) -> bool:
    for field_name in (
        "model_type",
        "task_type",
        "label_column",
        "train_start",
        "train_end",
        "validation_start",
        "validation_end",
    ):
        wanted = getattr(flt, field_name)
        if wanted is not None and getattr(row, field_name) != wanted:
            return False

    if flt.feature_columns is not None:
        if flt.features_as_set:
            if set(row.feature_columns) != set(flt.feature_columns):
                return False
        elif tuple(row.feature_columns) != flt.feature_columns:
            return False

    if flt.require_metric is not None:
        value = row.metrics.get(flt.require_metric)
        if not _is_numeric(value):
            return False
        if flt.metric_min is not None and value < flt.metric_min:
            return False
        if flt.metric_max is not None and value > flt.metric_max:
            return False

    if flt.created_after is not None and row.created_at < flt.created_after:
        return False
    if flt.created_before is not None and row.created_at > flt.created_before:
        return False
    return True


def filter_experiment_catalog(
    rows: Sequence[ExperimentCatalogRow], flt: ExperimentCatalogFilter
) -> list[ExperimentCatalogRow]:
    """Pure, order-preserving filtering of catalog rows.

    An empty result is a valid outcome.  Raises :class:`CatalogError` when
    ``require_metric`` names a metric that is not among the rows' selected metric
    keys — rebuilding the catalog with that key included is the fix; a silent
    empty result would hide the mistake."""
    rows = list(rows)
    if flt.require_metric is not None and rows:
        if flt.require_metric not in rows[0].metrics:
            raise CatalogError(
                f"metric {flt.require_metric!r} is not among the catalog's selected metrics "
                f"{sorted(rows[0].metrics)}; rebuild the catalog with it included"
            )
    return [row for row in rows if _row_matches(row, flt)]
