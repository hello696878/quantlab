"""
Small, read-only experiment summaries (Phase 5 — commit 4).

A single helper that renders an :class:`ExperimentRun` as a compact dict or a
short text block.  Deliberately minimal — no plotting, no frontend, no I/O.
"""

from __future__ import annotations

from app.experiments.spec import ExperimentRun


def summarize_experiment(run: ExperimentRun, *, as_text: bool = False):
    """Return a compact summary of ``run`` as a dict (default) or a short string."""
    summary = {
        "train_run_hash": run.train_run_hash,
        "model_type": run.model_type,
        "task_type": run.task_type,
        "label_column": run.label_column,
        "validation_start": run.validation_start.isoformat(),
        "validation_end": run.validation_end.isoformat(),
        "sharpe": run.backtest_metrics.get("sharpe"),
        "total_return": run.backtest_metrics.get("total_return"),
        "max_drawdown": run.backtest_metrics.get("max_drawdown"),
        "total_transaction_cost": run.backtest_metrics.get("total_transaction_cost"),
        "n_scored_rows": run.n_scored_rows,
    }
    if not as_text:
        return summary
    return "\n".join(
        [
            f"experiment {run.train_run_hash[:12]} ({run.model_type}, {run.task_type})",
            f"  OOS {run.validation_start} -> {run.validation_end}  label={run.label_column}",
            f"  sharpe={summary['sharpe']}  total_return={summary['total_return']}  "
            f"max_drawdown={summary['max_drawdown']}  cost={summary['total_transaction_cost']}",
        ]
    )
