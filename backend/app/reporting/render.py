"""
Experiment reporting — deterministic renderers / exports (Phase 10 — commit 1).

Turns an :class:`~app.reporting.summary.ExperimentRunSummary` (or a list of
:class:`~app.reporting.summary.ExperimentComparisonRow`) into a byte-stable
Markdown / CSV / JSON report.  Every report carries the standing disclaimers.

Determinism / strict output:

* JSON uses ``json.dumps(..., allow_nan=False, sort_keys=True)`` and pre-sanitizes
  non-finite floats (``NaN`` / ±``inf``) to ``null``;
* Markdown has a fixed section order and sorts metric keys;
* CSV has a fixed column order (base columns + sorted metric columns);
* floats are formatted with a stable precision.

No network, no training, no schema changes, no absolute paths (relative
``artifact_paths`` are echoed as stored).
"""

from __future__ import annotations

import csv
import io
import json
import math

from app.reporting.summary import (
    NOT_RECORDED,
    ExperimentComparisonRow,
    ExperimentRunSummary,
)

# Standing disclaimers — present in every rendered/exported report.
DISCLAIMERS: tuple[str, ...] = (
    "Synthetic / local-only artifacts — not real market data.",
    "Not investment advice.",
    "Not live trading.",
    "Not a performance guarantee.",
)

__all__ = [
    "DISCLAIMERS",
    "render_experiment_report_markdown",
    "export_experiment_report_json",
    "export_experiment_comparison_csv",
    "export_experiment_comparison_json",
]


# --------------------------------------------------------------------------- #
# strict-JSON + formatting helpers
# --------------------------------------------------------------------------- #


def _sanitize(obj):
    """Recursively map non-finite floats (NaN / ±inf) to ``None`` for strict JSON."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _json_dumps(obj) -> str:
    """Strict, sorted JSON: NaN/inf -> null; dates/paths -> strings."""
    return json.dumps(_sanitize(obj), allow_nan=False, sort_keys=True, default=str)


def _disp(value) -> str:
    """Stable display string for Markdown: None/NaN -> 'n/a'; floats -> .6g."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return "n/a" if not math.isfinite(value) else format(value, ".6g")
    return str(value)


def _csv_num(value) -> str:
    """Stable CSV cell: None/NaN -> ''; floats -> .12g; else str."""
    if value is None:
        return ""
    if isinstance(value, float):
        return "" if not math.isfinite(value) else format(value, ".12g")
    return str(value)


def _metrics_md(metrics: dict) -> list[str]:
    if not metrics:
        return ["- (none)"]
    return [f"- `{k}`: {_disp(metrics[k])}" for k in sorted(metrics)]


# --------------------------------------------------------------------------- #
# single-run report
# --------------------------------------------------------------------------- #


def _report_dict(
    summary: ExperimentRunSummary, *, include_provenance: bool, include_hash_chain: bool
) -> dict:
    """Plain, JSON-safe dict for one run (respecting the section toggles)."""
    out: dict = {
        "disclaimers": list(DISCLAIMERS),
        "run_identity": {
            "train_run_hash": summary.train_run_hash,
            "model_type": summary.model_type,
            "task_type": summary.task_type,
            "label_column": summary.label_column,
            "feature_columns": list(summary.feature_columns),
            "root_symbol": NOT_RECORDED,
            "source": NOT_RECORDED,
            "adjustment_method": NOT_RECORDED,
        },
        "windows": {
            "train_start": summary.train_start,
            "train_end": summary.train_end,
            "validation_start": summary.validation_start,
            "validation_end": summary.validation_end,
        },
        "headline": summary.headline,
        "ml_metrics": summary.ml_metrics,
        "backtest_metrics": summary.backtest_metrics,
        "baseline_metrics": summary.baseline_metrics,
        "unavailable_provenance": summary.unavailable_provenance,
    }
    if include_hash_chain:
        out["hash_chain"] = summary.hash_chain
    if include_provenance:
        out["provenance"] = {
            "artifact_paths": summary.artifact_paths,
            "created_at": summary.created_at,
            "git_commit": summary.git_commit,
            "code_version": summary.code_version,
            "n_oos_rows": summary.n_oos_rows,
            "n_scored_rows": summary.n_scored_rows,
        }
    return out


def export_experiment_report_json(
    summary: ExperimentRunSummary,
    *,
    include_provenance: bool = True,
    include_hash_chain: bool = True,
) -> str:
    """Strict-JSON single-run report (sorted keys, no NaN/Infinity)."""
    return _json_dumps(
        _report_dict(
            summary, include_provenance=include_provenance, include_hash_chain=include_hash_chain
        )
    )


def render_experiment_report_markdown(
    summary: ExperimentRunSummary,
    *,
    include_provenance: bool = True,
    include_hash_chain: bool = True,
) -> str:
    """Deterministic Markdown single-run report (fixed section order)."""
    lines: list[str] = []
    lines.append(f"# Experiment report — {summary.train_run_hash[:12]}")
    lines.append("")
    lines.append("## Disclaimers")
    lines.extend(f"- {d}" for d in DISCLAIMERS)
    lines.append("")

    lines.append("## Run identity")
    lines.append(f"- train_run_hash: `{summary.train_run_hash}`")
    lines.append(f"- model_type: {summary.model_type}")
    lines.append(f"- task_type: {summary.task_type}")
    lines.append(f"- label_column: {summary.label_column}")
    lines.append(f"- feature_columns: {', '.join(summary.feature_columns)}")
    lines.append(f"- root_symbol: {NOT_RECORDED}")
    lines.append(f"- source: {NOT_RECORDED}")
    lines.append(f"- adjustment_method: {NOT_RECORDED}")
    lines.append("")

    lines.append("## Windows")
    lines.append(f"- train: {summary.train_start} -> {summary.train_end}")
    lines.append(f"- validation (OOS): {summary.validation_start} -> {summary.validation_end}")
    lines.append("")

    lines.append("## ML metrics")
    lines.extend(_metrics_md(summary.ml_metrics))
    lines.append("")
    lines.append("## Backtest metrics")
    lines.extend(_metrics_md(summary.backtest_metrics))
    lines.append("")
    lines.append("## Baseline metrics")
    for name in ("no_trade", "momentum"):
        base = summary.baseline_metrics.get(name)
        lines.append(f"### {name}")
        lines.extend(_metrics_md(base if isinstance(base, dict) else {}))
    lines.append("")

    if include_hash_chain:
        lines.append("## Hash chain")
        for key in (
            "continuous_config_hash", "feature_config_hash", "label_config_hash",
            "dataset_config_hash", "model_config_hash", "train_run_hash",
        ):
            lines.append(f"- {key}: `{summary.hash_chain.get(key, NOT_RECORDED)}`")
        lines.append(f"- raw_data_version_hash: {NOT_RECORDED}")
        lines.append("")

    if include_provenance:
        lines.append("## Provenance (from the persisted ExperimentRun)")
        lines.append(f"- created_at: {summary.created_at}")
        lines.append(f"- git_commit: {summary.git_commit if summary.git_commit else NOT_RECORDED}")
        lines.append(f"- code_version: {summary.code_version if summary.code_version else NOT_RECORDED}")
        lines.append(f"- n_oos_rows: {summary.n_oos_rows}")
        lines.append(f"- n_scored_rows: {summary.n_scored_rows}")
        lines.append("### Artifact paths (relative)")
        if summary.artifact_paths:
            for key in sorted(summary.artifact_paths):
                lines.append(f"- {key}: `{summary.artifact_paths[key]}`")
        else:
            lines.append("- (none)")
        lines.append("### Unavailable provenance (not persisted by ExperimentRun)")
        for key in sorted(summary.unavailable_provenance):
            lines.append(f"- {key}: {summary.unavailable_provenance[key]}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# comparison exports
# --------------------------------------------------------------------------- #


def _comparison_metric_keys(rows: list[ExperimentComparisonRow]) -> list[str]:
    return sorted({k for r in rows for k in r.metrics})


def export_experiment_comparison_csv(rows: list[ExperimentComparisonRow]) -> str:
    """Deterministic CSV: fixed base columns + sorted metric columns."""
    metric_keys = _comparison_metric_keys(rows)
    header = [
        "train_run_hash", "model_type", "task_type", "label_column",
        "validation_start", "validation_end", "same_window", *metric_keys,
    ]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    for r in rows:
        writer.writerow(
            [
                r.train_run_hash, r.model_type, r.task_type, r.label_column,
                r.validation_start, r.validation_end,
                "" if r.same_window is None else str(r.same_window),
                *[_csv_num(r.metrics.get(k)) for k in metric_keys],
            ]
        )
    return buf.getvalue()


def export_experiment_comparison_json(rows: list[ExperimentComparisonRow]) -> str:
    """Strict-JSON comparison (each row incl. disclaimers header)."""
    payload = {
        "disclaimers": list(DISCLAIMERS),
        "rows": [
            {
                "train_run_hash": r.train_run_hash,
                "model_type": r.model_type,
                "task_type": r.task_type,
                "label_column": r.label_column,
                "validation_start": r.validation_start,
                "validation_end": r.validation_end,
                "same_window": r.same_window,
                "metrics": r.metrics,
            }
            for r in rows
        ],
    }
    return _json_dumps(payload)
