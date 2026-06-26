"""
Compact rendering helpers for the Research CLI (Phase 6 — commit 3).

Each helper returns a single string: a short human-readable block, or (when
``as_json=True``) a ``json.loads``-parseable JSON string.  No color, no rich, no
extra dependencies.  The run summary always carries the SYNTHETIC DEMO banner.
"""

from __future__ import annotations

import json
import math

SYNTHETIC_BANNER = "SYNTHETIC DEMO — not real market performance"


def _json_sanitize(obj):
    """Recursively map non-finite floats (NaN / ±inf) to ``None`` so the output is
    strict JSON.  Other values are left for ``json.dumps(default=str)``."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_sanitize(v) for v in obj]
    return obj


def _json_dumps(obj) -> str:
    """Strict JSON: NaN/inf become ``null``; dates/paths serialize as strings."""
    return json.dumps(_json_sanitize(obj), default=str)


def _fmt(value) -> str:
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


def _compact(metrics: dict) -> str:
    return " ".join(f"{k}={_fmt(v)}" for k, v in metrics.items()) or "(none)"


def render_run_summary(result, as_json: bool = False) -> str:
    """Render a single experiment run (an ``ExperimentResult``)."""
    cfg = result.config
    payload = {
        "data_source": "synthetic",
        "train_run_hash": result.train_run_hash,
        "model_type": cfg.model_type.value,
        "task_type": cfg.task_type.value,
        "label_column": cfg.label_column,
        "train_start": cfg.train_start.isoformat(),
        "train_end": cfg.train_end.isoformat(),
        "validation_start": cfg.validation_start.isoformat(),
        "validation_end": cfg.validation_end.isoformat(),
        "train_window": [cfg.train_start.isoformat(), cfg.train_end.isoformat()],
        "validation_window": [cfg.validation_start.isoformat(), cfg.validation_end.isoformat()],
        "ml_metrics": result.ml_metrics,
        "backtest_metrics": result.backtest_metrics,
        "baseline_metrics": result.baseline_metrics,
        "artifact_dir": str(result.artifact_dir),
        "hashes": {
            "continuous_config_hash": result.continuous_config_hash,
            "feature_config_hash": result.feature_config_hash,
            "label_config_hash": result.label_config_hash,
            "dataset_config_hash": result.dataset_config_hash,
            "model_config_hash": result.model_config_hash,
            "train_run_hash": result.train_run_hash,
        },
    }
    if as_json:
        return _json_dumps(payload)

    reproduce = (
        f"python -m app.research_cli.cli run --seed {cfg.random_seed} "
        f"--model-type {cfg.model_type.value}"
    )
    if cfg.created_at:
        reproduce += f" --created-at {cfg.created_at}"
    return "\n".join(
        [
            f"=== {SYNTHETIC_BANNER} ===",
            f"train_run_hash: {result.train_run_hash}",
            f"model: {cfg.model_type.value} ({cfg.task_type.value})   label: {cfg.label_column}",
            f"train:      {cfg.train_start} -> {cfg.train_end}",
            f"validation: {cfg.validation_start} -> {cfg.validation_end}  (OOS)",
            f"ml_metrics:       {_compact(result.ml_metrics)}",
            f"backtest_metrics: {_compact(result.backtest_metrics)}",
            f"no_trade:         {_compact(result.baseline_metrics.get('no_trade', {}))}",
            f"momentum:         {_compact(result.baseline_metrics.get('momentum', {}))}",
            f"artifact_dir: {result.artifact_dir}",
            f"reproduce: {reproduce}",
        ]
    )


def render_experiment_table(runs, as_json: bool = False) -> str:
    """Render a list of ``ExperimentRun`` objects as a compact table."""
    records = [
        {
            "train_run_hash": r.train_run_hash,
            "model_type": r.model_type,
            "label_column": r.label_column,
            "validation_start": r.validation_start.isoformat(),
            "validation_end": r.validation_end.isoformat(),
            "sharpe": r.backtest_metrics.get("sharpe"),
            "total_return": r.backtest_metrics.get("total_return"),
        }
        for r in runs
    ]
    if as_json:
        return _json_dumps(records)
    if not records:
        return "(no experiments)"
    header = (f"{'hash':<14} {'model':<20} {'label':<28} "
              f"{'val_start':<12} {'val_end':<12} {'sharpe':>9} {'tot_ret':>9}")
    lines = [header]
    for r in records:
        lines.append(
            f"{r['train_run_hash'][:12]:<14} {r['model_type']:<20} {r['label_column']:<28} "
            f"{r['validation_start']:<12} {r['validation_end']:<12} "
            f"{_fmt(r['sharpe']):>9} {_fmt(r['total_return']):>9}"
        )
    return "\n".join(lines)


def render_compare_table(df, as_json: bool = False) -> str:
    """Render a ``compare_experiments`` DataFrame."""
    if as_json:
        return _json_dumps(df.to_dict(orient="records"))
    return df.to_string(index=False)


def render_best_experiment(run, metric: str, as_json: bool = False) -> str:
    """Render the winning ``ExperimentRun`` for a metric."""
    value = run.backtest_metrics.get(metric, run.metrics.get(metric))
    payload = {
        "train_run_hash": run.train_run_hash,
        "metric": metric,
        "value": value,
        "model_type": run.model_type,
        "validation_window": [run.validation_start.isoformat(), run.validation_end.isoformat()],
    }
    if as_json:
        return _json_dumps(payload)
    return "\n".join(
        [
            f"=== {SYNTHETIC_BANNER} ===",
            f"best by {metric}: {run.train_run_hash}",
            f"  {metric}={_fmt(value)}  model={run.model_type}  "
            f"val {run.validation_start} -> {run.validation_end}",
        ]
    )
