"""
Research CLI (Phase 6 — commit 3): stdlib ``argparse`` only.

Canonical usage from the ``backend/`` directory:

    python -m app.research_cli.cli run    [flags]
    python -m app.research_cli.cli list   [flags]
    python -m app.research_cli.cli compare HASH HASH ... [flags]
    python -m app.research_cli.cli best   [flags]

``main(argv)`` returns 0 on success, non-zero with a clear stderr message on a
validation / ``ExperimentError``.  Default mode is the synthetic ES demo: no
network, no real data, every run prints a SYNTHETIC DEMO warning.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.experiments import (
    ExperimentError,
    ExperimentStore,
    compare_experiments,
    get_best_experiment,
    list_experiments,
)
from app.ml_signal import ModelType, TaskType
from app.research_cli.config import ExperimentConfig, resolve_artifact_base_dir
from app.research_cli.pipeline import run_es_ml_experiment
from app.research_cli.render import (
    render_best_experiment,
    render_compare_table,
    render_experiment_table,
    render_run_summary,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _resolve_store(artifacts_dir) -> ExperimentStore:
    cfg = ExperimentConfig(artifact_base_dir=artifacts_dir) if artifacts_dir else ExperimentConfig()
    return ExperimentStore(resolve_artifact_base_dir(cfg))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.research_cli.cli",
        description="QuantLab synthetic ES research CLI (synthetic demo only).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a synthetic ES ML experiment and save it")
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--model-type", choices=[m.value for m in ModelType],
                     default=ModelType.RIDGE_REGRESSION.value)
    run.add_argument("--task-type", choices=[t.value for t in TaskType], default=None)
    run.add_argument("--label-column", default=None)
    run.add_argument("--feature-columns", nargs="+", default=None)
    run.add_argument("--train-start", default=None)
    run.add_argument("--train-end", default=None)
    run.add_argument("--validation-start", default=None)
    run.add_argument("--validation-end", default=None)
    run.add_argument("--alpha", type=float, default=None)
    run.add_argument("--cost-bps", type=float, default=None)
    run.add_argument("--artifacts-dir", default=None)
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--created-at", default=None)
    run.add_argument("--code-version", default=None)
    run.add_argument("--json", action="store_true")

    lst = sub.add_parser("list", help="list saved experiments")
    lst.add_argument("--artifacts-dir", default=None)
    lst.add_argument("--model-type", default=None)
    lst.add_argument("--label-column", default=None)
    lst.add_argument("--json", action="store_true")

    cmp = sub.add_parser("compare", help="compare 2+ experiments (same OOS window by default)")
    cmp.add_argument("train_run_hash", nargs="+")
    cmp.add_argument("--artifacts-dir", default=None)
    cmp.add_argument("--metrics", nargs="+", default=None)
    cmp.add_argument("--allow-different-windows", action="store_true")
    cmp.add_argument("--json", action="store_true")

    best = sub.add_parser("best", help="select the best experiment by a metric")
    best.add_argument("--artifacts-dir", default=None)
    best.add_argument("--metric", default="sharpe")
    direction = best.add_mutually_exclusive_group()
    direction.add_argument("--maximize", action="store_true")
    direction.add_argument("--minimize", action="store_true")
    best.add_argument("--allow-different-windows", action="store_true")
    best.add_argument("--json", action="store_true")
    return parser


def _run_command(args) -> int:
    from app.research_cli.config import SyntheticDataConfig

    cfg_kwargs = {
        "random_seed": args.seed,
        "synthetic": SyntheticDataConfig(random_seed=args.seed),
        "model_type": ModelType(args.model_type),
        "overwrite": args.overwrite,
    }
    if args.task_type:
        cfg_kwargs["task_type"] = TaskType(args.task_type)
    if args.label_column:
        cfg_kwargs["label_column"] = args.label_column
    if args.feature_columns:
        cfg_kwargs["feature_columns"] = tuple(args.feature_columns)
    if args.train_start:
        cfg_kwargs["train_start"] = _parse_date(args.train_start)
    if args.train_end:
        cfg_kwargs["train_end"] = _parse_date(args.train_end)
    if args.validation_start:
        cfg_kwargs["validation_start"] = _parse_date(args.validation_start)
    if args.validation_end:
        cfg_kwargs["validation_end"] = _parse_date(args.validation_end)
    if args.alpha is not None:
        cfg_kwargs["hyperparameters"] = {"alpha": args.alpha}
    if args.cost_bps is not None:
        cfg_kwargs["transaction_cost_bps"] = args.cost_bps
    if args.artifacts_dir:
        cfg_kwargs["artifact_base_dir"] = args.artifacts_dir
    if args.created_at:
        cfg_kwargs["created_at"] = args.created_at
    if args.code_version:
        cfg_kwargs["code_version"] = args.code_version

    config = ExperimentConfig(**cfg_kwargs)
    result = run_es_ml_experiment(config)
    print(render_run_summary(result, as_json=args.json))
    return 0


def _list_command(args) -> int:
    store = _resolve_store(args.artifacts_dir)
    filters = {}
    if args.model_type:
        filters["model_type"] = args.model_type
    if args.label_column:
        filters["label_column"] = args.label_column
    runs = list_experiments(store=store, filters=filters or None)
    print(render_experiment_table(runs, as_json=args.json))
    return 0


def _compare_command(args) -> int:
    if len(args.train_run_hash) < 2:
        raise ExperimentError("compare requires at least two train_run_hash values")
    store = _resolve_store(args.artifacts_dir)
    metrics = tuple(args.metrics) if args.metrics else None
    df = compare_experiments(
        args.train_run_hash, store=store, metrics=metrics,
        allow_different_windows=args.allow_different_windows,
    )
    print(render_compare_table(df, as_json=args.json))
    return 0


def _best_command(args) -> int:
    store = _resolve_store(args.artifacts_dir)
    maximize = not args.minimize  # default is maximize
    run = get_best_experiment(
        store=store, metric=args.metric, maximize=maximize,
        allow_different_windows=args.allow_different_windows,
    )
    print(render_best_experiment(run, args.metric, as_json=args.json))
    return 0


_HANDLERS = {
    "run": _run_command,
    "list": _list_command,
    "compare": _compare_command,
    "best": _best_command,
}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _HANDLERS[args.command](args)
    except (ExperimentError, ValidationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
