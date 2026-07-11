"""
Catalog / leaderboard CLI over local ExperimentStore runs (Phase 12 — commit 3).

Thin argparse wrapper around ``app.experiment_catalog``: discover saved runs,
filter them with safe exact-match / threshold flags, optionally rank by one
metric, and print or export the result — **read-only by default** (only the
``export-*`` subcommands write, and only to the explicit ``--output-path``).

Subcommands: ``list`` (catalog table), ``leaderboard`` (ranked rows),
``groups`` (compatibility groups), ``hashes`` (selected train_run_hashes, one
per line — pipe-friendly for the Phase 10 report CLI), and
``export-csv`` / ``export-json`` / ``export-markdown``.

Ranking: ``leaderboard`` always ranks (default metric ``sharpe``, maximize);
``hashes`` / ``export-*`` keep catalog discovery order unless a ranking flag
(``--metric`` / ``--top-n`` / ``--minimize`` / ``--maximize`` /
``--require-compatible`` / ``--on-missing-metric``) is given.

Everything is descriptive output over historical local artifacts: no network,
no retraining, no experiment execution, no new hash identities, not investment
advice.  Local files only.

Usage (from the repo root)::

    backend\\venv\\Scripts\\python.exe scripts\\catalog_local_futures_experiments.py \\
        leaderboard --artifacts-dir <exp-store> --metric sharpe --top-n 5

Exit code 0 on success; nonzero (``RESULT: FAIL``) on an empty store, no rows
after filtering, an unavailable metric, an incompatible --require-compatible
selection, or corrupt store metadata.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when run directly from the repo root (mirrors the other
# local-futures scripts and the pytest pythonpath="." setting).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pydantic import ValidationError  # noqa: E402

from app.experiment_catalog import (  # noqa: E402
    CatalogError,
    ExperimentCatalogFilter,
    ExperimentLeaderboardSpec,
    build_experiment_catalog,
    export_catalog_csv,
    export_catalog_json,
    export_catalog_markdown,
    filter_experiment_catalog,
    group_compatible_runs,
    rank_experiment_catalog,
)
from app.experiments import ExperimentError, ExperimentStore  # noqa: E402

# Piped/redirected stdout on Windows uses the ANSI code page with strict errors;
# degrade non-ASCII to an escape sequence rather than crash mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")

_BANNER = (
    "=== LOCAL/SYNTHETIC EXPERIMENT CATALOG — descriptive listing only; "
    "not investment advice ==="
)

# Expected failures that map to a clean nonzero "RESULT: FAIL" (no stack trace).
_FAIL_ERRORS = (
    ValidationError,
    CatalogError,
    ExperimentError,
    ValueError,
    KeyError,
    TypeError,
    FileNotFoundError,
    OSError,
)

_EXPORTERS = {
    "export-csv": export_catalog_csv,
    "export-json": export_catalog_json,
    "export-markdown": export_catalog_markdown,
}

_RANKED_COMMANDS = ("leaderboard", "hashes", "export-csv", "export-json", "export-markdown")


def _write_text(path_str: str, text: str) -> None:
    """Write ``text`` to ``path_str``, creating the parent directory if needed."""
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Catalog / leaderboard over local ExperimentStore runs "
            "(read-only by default; local files only; no network)."
        )
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--artifacts-dir", required=True, help="ExperimentStore base dir (read)")
    common.add_argument("--model-type", default=None)
    common.add_argument("--task-type", default=None)
    common.add_argument("--label-column", default=None)
    common.add_argument("--train-start", default=None, help="exact ISO date match")
    common.add_argument("--train-end", default=None, help="exact ISO date match")
    common.add_argument("--validation-start", default=None, help="exact ISO date match")
    common.add_argument("--validation-end", default=None, help="exact ISO date match")
    common.add_argument(
        "--feature-columns",
        default=None,
        help="comma-separated feature__ columns (exact order unless --features-as-set)",
    )
    common.add_argument(
        "--features-as-set", action="store_true", help="order-insensitive feature set match"
    )
    common.add_argument("--require-metric", default=None, help="keep rows with a numeric value")
    common.add_argument("--metric-min", type=float, default=None)
    common.add_argument("--metric-max", type=float, default=None)
    common.add_argument("--created-after", default=None, help="inclusive ISO lower bound")
    common.add_argument("--created-before", default=None, help="inclusive ISO upper bound")
    common.add_argument("--no-parquet", action="store_true", help="force the CSV storage fallback")

    ranking = argparse.ArgumentParser(add_help=False)
    ranking.add_argument("--metric", default=None, help="ranking metric (default sharpe)")
    direction = ranking.add_mutually_exclusive_group()
    direction.add_argument("--maximize", action="store_true", help="rank descending (default)")
    direction.add_argument("--minimize", action="store_true", help="rank ascending")
    ranking.add_argument("--top-n", type=int, default=None)
    ranking.add_argument(
        "--require-compatible",
        action="store_true",
        help="fail if the selected rows span multiple compatibility groups",
    )
    ranking.add_argument("--on-missing-metric", choices=("exclude", "fail"), default=None)

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", parents=[common])
    sub.add_parser("leaderboard", parents=[common, ranking])
    sub.add_parser("groups", parents=[common])
    sub.add_parser("hashes", parents=[common, ranking])
    for name in ("export-csv", "export-json", "export-markdown"):
        p_export = sub.add_parser(name, parents=[common, ranking])
        p_export.add_argument("--output-path", required=True, help="explicit output file path")
    return parser


def _build_filter(args) -> ExperimentCatalogFilter:
    feature_columns = None
    if args.feature_columns:
        feature_columns = tuple(c.strip() for c in args.feature_columns.split(",") if c.strip())
    return ExperimentCatalogFilter(
        model_type=args.model_type,
        task_type=args.task_type,
        label_column=args.label_column,
        train_start=args.train_start,
        train_end=args.train_end,
        validation_start=args.validation_start,
        validation_end=args.validation_end,
        feature_columns=feature_columns,
        features_as_set=args.features_as_set,
        require_metric=args.require_metric,
        metric_min=args.metric_min,
        metric_max=args.metric_max,
        created_after=args.created_after,
        created_before=args.created_before,
    )


def _ranking_spec(args) -> ExperimentLeaderboardSpec | None:
    """Ranking spec for this invocation, or None to keep catalog order.

    ``leaderboard`` always ranks; ``hashes`` / ``export-*`` rank only when a
    ranking flag was explicitly provided."""
    if args.command not in _RANKED_COMMANDS:
        return None
    requested = any(
        (
            args.metric is not None,
            args.top_n is not None,
            args.maximize,
            args.minimize,
            args.require_compatible,
            args.on_missing_metric is not None,
        )
    )
    if args.command != "leaderboard" and not requested:
        return None
    return ExperimentLeaderboardSpec(
        metric=args.metric or "sharpe",
        maximize=not args.minimize,
        top_n=args.top_n,
        on_missing_metric=args.on_missing_metric or "exclude",
        require_compatible=args.require_compatible,
    )


def _print_list(rows) -> None:
    for row in rows:
        sharpe = row.metrics.get("sharpe")
        print(
            f"[{row.train_run_hash}] model={row.model_type} task={row.task_type} "
            f"label={row.label_column} "
            f"validation={row.validation_start}->{row.validation_end} sharpe={sharpe}"
        )
    print(f"n_rows={len(rows)}")


def _print_leaderboard(rows, spec: ExperimentLeaderboardSpec) -> None:
    for position, row in enumerate(rows, start=1):
        print(
            f"#{position} train_run_hash={row.train_run_hash} "
            f"{spec.metric}={row.metrics.get(spec.metric)}"
        )
    print(f"metric={spec.metric} maximize={spec.maximize} n_ranked={len(rows)}")


def _print_groups(rows) -> None:
    groups = group_compatible_runs(rows)
    for group in groups:
        members = ",".join(group.train_run_hashes)
        print(
            f"[{group.group_id}] task={group.task_type} label={group.label_column} "
            f"train={group.train_start}->{group.train_end} "
            f"validation={group.validation_start}->{group.validation_end} "
            f"dataset={group.dataset_config_hash} members={members}"
        )
    print(f"n_groups={len(groups)}")


def _handle(args) -> int:
    store = ExperimentStore(args.artifacts_dir, prefer_parquet=not args.no_parquet)
    rows = filter_experiment_catalog(build_experiment_catalog(store), _build_filter(args))
    if not rows:
        print("RESULT: FAIL (no rows after filtering; relax the filters)")
        return 1

    spec = _ranking_spec(args)
    if spec is not None:
        rows = rank_experiment_catalog(rows, spec)

    if args.command == "list":
        _print_list(rows)
    elif args.command == "leaderboard":
        _print_leaderboard(rows, spec)
    elif args.command == "groups":
        _print_groups(rows)
    elif args.command == "hashes":
        for row in rows:
            print(row.train_run_hash)
    else:  # export-csv / export-json / export-markdown
        _write_text(args.output_path, _EXPORTERS[args.command](rows))
        print(f"[EXPORT] path={args.output_path}")

    print("RESULT: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    print(_BANNER)
    try:
        return _handle(args)
    except _FAIL_ERRORS as exc:
        print(f"RESULT: FAIL ({type(exc).__name__}: {exc})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
