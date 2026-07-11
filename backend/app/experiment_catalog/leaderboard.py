"""
Phase 12 (commit 2) — leaderboard, compatibility grouping, deterministic exporters.

Pure functions over ``ExperimentCatalogRow`` values: ``group_compatible_runs``
buckets rows by a compatibility key that is a **strict superset of the Phase 10
comparison guard** (validation window / label / dataset hash, plus the train
window and task type), ``rank_experiment_catalog`` sorts rows by one selected
metric with the **same ordering and tie-break as the existing
``get_best_experiment``** (metric direction, then ``train_run_hash``), and the
``export_catalog_*`` functions render deterministic CSV / JSON / Markdown
strings.  Everything here is **descriptive only** — a sorted table of historical
local metrics — and performs no writes, no store reads, no execution, no
retraining, and no hashing.

This exporter layer reuses the standing Phase 10 ``DISCLAIMERS`` so the
disclaimer text has exactly one source (JSON and Markdown carry them; CSV stays
a bare table, matching the existing Phase 10 export style).
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from typing import Optional, Sequence

from app.experiment_catalog.catalog import (
    CatalogError,
    ExperimentCatalogRow,
    _is_numeric,
)
from app.reporting import DISCLAIMERS

__all__ = [
    "ExperimentLeaderboardSpec",
    "ExperimentCompatibilityGroup",
    "group_compatible_runs",
    "rank_experiment_catalog",
    "export_catalog_csv",
    "export_catalog_json",
    "export_catalog_markdown",
]

_ON_MISSING_VALUES: tuple[str, ...] = ("exclude", "fail")

# Fixed identity columns for the tabular (CSV / Markdown) exports, in order.
# The JSON export carries the full row instead (every field, keys sorted).
_BASE_COLUMNS: tuple[str, ...] = (
    "train_run_hash",
    "created_at",
    "model_type",
    "task_type",
    "label_column",
    "train_start",
    "train_end",
    "validation_start",
    "validation_end",
    "feature_columns",
    "n_oos_rows",
    "n_scored_rows",
    "artifact_dir",
    "git_commit",
    "code_version",
    "dataset_config_hash",
)


@dataclass(frozen=True)
class ExperimentLeaderboardSpec:
    """How to rank catalog rows — descriptive sorting only, no selection advice.

    ``on_missing_metric='exclude'`` (default) drops rows without a numeric value
    for ``metric`` but fails clearly if **no** row has it; ``'fail'`` raises on
    the first missing value.  ``require_compatible`` refuses to rank rows that
    span multiple compatibility groups."""

    metric: str = "sharpe"
    maximize: bool = True
    top_n: Optional[int] = None
    on_missing_metric: str = "exclude"
    require_compatible: bool = False

    def __post_init__(self) -> None:
        if not self.metric or not self.metric.strip():
            raise CatalogError("metric must be a non-empty string")
        if self.on_missing_metric not in _ON_MISSING_VALUES:
            raise CatalogError(
                f"on_missing_metric must be one of {_ON_MISSING_VALUES}, "
                f"got {self.on_missing_metric!r}"
            )
        if self.top_n is not None and self.top_n < 1:
            raise CatalogError(f"top_n must be a positive integer, got {self.top_n}")


@dataclass(frozen=True)
class ExperimentCompatibilityGroup:
    """Rows that share the full compatibility key (persisted fields only).

    The key is a strict superset of the Phase 10 comparison guard
    (validation window / label / dataset hash), so every group's hashes pass
    that guard by construction.  Members keep their catalog row order."""

    group_id: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    label_column: str
    dataset_config_hash: str
    task_type: str
    rows: tuple[ExperimentCatalogRow, ...]

    @property
    def train_run_hashes(self) -> tuple[str, ...]:
        return tuple(row.train_run_hash for row in self.rows)


def _compat_key(row: ExperimentCatalogRow) -> tuple[str, ...]:
    return (
        row.train_start,
        row.train_end,
        row.validation_start,
        row.validation_end,
        row.label_column,
        row.dataset_config_hash,
        row.task_type,
    )


def group_compatible_runs(
    rows: Sequence[ExperimentCatalogRow],
) -> list[ExperimentCompatibilityGroup]:
    """Bucket rows into compatibility groups, deterministically.

    Groups are ordered by their sorted key and get index-based ids
    (``group_0000``, ...); members preserve the incoming row order.  An empty
    input yields an empty list (an empty filter result is valid)."""
    buckets: dict[tuple[str, ...], list[ExperimentCatalogRow]] = {}
    for row in rows:
        buckets.setdefault(_compat_key(row), []).append(row)
    groups: list[ExperimentCompatibilityGroup] = []
    for index, key in enumerate(sorted(buckets)):
        groups.append(
            ExperimentCompatibilityGroup(
                group_id=f"group_{index:04d}",
                train_start=key[0],
                train_end=key[1],
                validation_start=key[2],
                validation_end=key[3],
                label_column=key[4],
                dataset_config_hash=key[5],
                task_type=key[6],
                rows=tuple(buckets[key]),
            )
        )
    return groups


def rank_experiment_catalog(
    rows: Sequence[ExperimentCatalogRow], spec: ExperimentLeaderboardSpec
) -> list[ExperimentCatalogRow]:
    """Rank rows by ``spec.metric`` — pure, deterministic, descriptive only.

    Ordering matches the existing ``get_best_experiment``: metric value in the
    requested direction, then ``train_run_hash`` ascending as the tie-break, so
    the top-1 result agrees with it.  ``top_n`` is applied after ranking.
    Raises :class:`CatalogError` for an empty selection, a metric outside the
    catalog's selected keys, missing values under ``'fail'`` mode, a metric with
    no numeric value anywhere, or (with ``require_compatible``) rows spanning
    multiple compatibility groups."""
    rows = list(rows)
    if not rows:
        raise CatalogError("cannot rank an empty catalog selection")
    if spec.metric not in rows[0].metrics:
        raise CatalogError(
            f"metric {spec.metric!r} is not among the catalog's selected metrics "
            f"{sorted(rows[0].metrics)}; rebuild the catalog with it included"
        )
    if spec.require_compatible:
        groups = group_compatible_runs(rows)
        if len(groups) > 1:
            raise CatalogError(
                f"selected rows span {len(groups)} compatibility groups "
                f"({', '.join(g.group_id for g in groups)}); narrow the filters "
                "or drop require_compatible"
            )

    scored: list[tuple[float, ExperimentCatalogRow]] = []
    for row in rows:
        value = row.metrics.get(spec.metric)
        if _is_numeric(value):
            scored.append((float(value), row))
        elif spec.on_missing_metric == "fail":
            raise CatalogError(
                f"run {row.train_run_hash!r} has no numeric value for metric "
                f"{spec.metric!r} (on_missing_metric='fail')"
            )
    if not scored:
        raise CatalogError(f"metric {spec.metric!r} is unavailable for all selected rows")

    scored.sort(
        key=lambda pair: (-pair[0] if spec.maximize else pair[0], pair[1].train_run_hash)
    )
    ranked = [row for _, row in scored]
    return ranked[: spec.top_n] if spec.top_n is not None else ranked


# --------------------------------------------------------------------------- #
# deterministic exporters (strings only — the CLI writes files, not this module)
# --------------------------------------------------------------------------- #


def _cell(value) -> str:
    """Stable tabular cell: None -> '', floats -> .12g, sequences joined by ';'."""
    if value is None:
        return ""
    if isinstance(value, float):
        return format(value, ".12g")
    if isinstance(value, (list, tuple)):
        return ";".join(str(v) for v in value)
    return str(value)


def _metric_columns(rows: Sequence[ExperimentCatalogRow]) -> tuple[str, ...]:
    return tuple(sorted({key for row in rows for key in row.metrics}))


def _baseline_columns(rows: Sequence[ExperimentCatalogRow]) -> tuple[str, ...]:
    cols: set[str] = set()
    for row in rows:
        for group_name, metrics in row.baseline_metrics.items():
            if isinstance(metrics, dict):
                for key in metrics:
                    cols.add(f"baseline__{group_name}__{key}")
    return tuple(sorted(cols))


def _baseline_value(row: ExperimentCatalogRow, column: str):
    _, group_name, key = column.split("__", 2)
    metrics = row.baseline_metrics.get(group_name)
    return metrics.get(key) if isinstance(metrics, dict) else None


def _table(rows: Sequence[ExperimentCatalogRow]) -> tuple[list[str], list[list[str]]]:
    """Shared deterministic header + string cells for CSV / Markdown."""
    metric_cols = _metric_columns(rows)
    baseline_cols = _baseline_columns(rows)
    header = [*_BASE_COLUMNS, *metric_cols, *baseline_cols]
    body: list[list[str]] = []
    for row in rows:
        cells = [_cell(getattr(row, column)) for column in _BASE_COLUMNS]
        cells += [_cell(row.metrics.get(column)) for column in metric_cols]
        cells += [_cell(_baseline_value(row, column)) for column in baseline_cols]
        body.append(cells)
    return header, body


def export_catalog_csv(rows: Sequence[ExperimentCatalogRow]) -> str:
    """Deterministic CSV: fixed identity columns + sorted metric / baseline columns."""
    header, body = _table(rows)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(body)
    return buf.getvalue()


def export_catalog_json(rows: Sequence[ExperimentCatalogRow]) -> str:
    """Strict JSON (sorted keys, no NaN / Infinity): disclaimers + the full rows."""
    payload = {
        "disclaimers": list(DISCLAIMERS),
        "rows": [asdict(row) for row in rows],
    }
    return json.dumps(payload, allow_nan=False, sort_keys=True, default=str)


def export_catalog_markdown(rows: Sequence[ExperimentCatalogRow]) -> str:
    """Deterministic Markdown table with the standing disclaimers appended."""
    header, body = _table(rows)
    lines = ["# Experiment Catalog", ""]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for cells in body:
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Disclaimers", ""]
    lines += [f"- {text}" for text in DISCLAIMERS]
    return "\n".join(lines) + "\n"
