"""
Local experiment reporting / comparison CLI (Phase 10 — commit 2).

Thin argparse wrapper around the ``app.reporting`` package: it reads saved
``ExperimentRun`` artifacts from a local ``ExperimentStore`` and prints / exports
deterministic reports.  **Read-only by default** — only the ``export-*``
subcommands write, and only to an explicit ``--output-path``.  Local files only;
no network; no training; no ``ExperimentRun`` schema change.

Subcommands:
    summary         print one run's report
    compare         print a comparison CSV for 2+ runs
    best            print the best run by a metric
    export-markdown write a Markdown report to --output-path
    export-json     write a strict-JSON report to --output-path
    export-csv      write a comparison CSV to --output-path

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\report_local_futures_experiments.py \\
        summary --artifacts-dir artifacts\\experiments --train-run-hash <hash>

Exit code 0 on success; nonzero (RESULT: FAIL) on missing store / unknown hash /
missing metric / incompatible windows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when run directly from the repo root (mirrors the other
# local-futures scripts and the pytest pythonpath="." setting).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.experiments import ExperimentError, ExperimentStore  # noqa: E402
from app.reporting import (  # noqa: E402
    best_experiment_run,
    compare_experiment_runs,
    export_experiment_comparison_csv,
    export_experiment_report_json,
    render_experiment_report_markdown,
    summarize_experiment_run,
)

# Piped/redirected stdout on Windows uses the ANSI code page with strict errors;
# degrade non-ASCII to an escape sequence rather than crash mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")

_FAIL_ERRORS = (ExperimentError, ValueError, TypeError, FileNotFoundError, OSError)


def _metrics(metric_args) -> tuple[str, ...] | None:
    """Flatten repeated / comma-separated ``--metric`` values into a tuple (or None)."""
    if not metric_args:
        return None
    out: list[str] = []
    for item in metric_args:
        out.extend(part.strip() for part in item.split(",") if part.strip())
    return tuple(out) or None


def _require_two(hashes) -> None:
    if len(hashes) < 2:
        raise ValueError("this subcommand requires two or more train_run_hash arguments")


def _write(output_path: str, text: str) -> None:
    """Write ``text`` to ``output_path`` (parent created if missing)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report on / compare local ExperimentStore runs (read-only by default)."
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--artifacts-dir", required=True, help="ExperimentStore base dir (read)")
    common.add_argument("--no-parquet", action="store_true", help="force the CSV storage fallback")

    sections = argparse.ArgumentParser(add_help=False)
    sections.add_argument(
        "--include-provenance", action=argparse.BooleanOptionalAction, default=True
    )
    sections.add_argument(
        "--include-hash-chain", action=argparse.BooleanOptionalAction, default=True
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_summary = sub.add_parser("summary", parents=[common, sections])
    p_summary.add_argument("--train-run-hash", required=True)

    p_compare = sub.add_parser("compare", parents=[common])
    p_compare.add_argument("train_run_hashes", nargs="+")
    p_compare.add_argument("--metric", action="append", help="repeatable / comma-separated")
    p_compare.add_argument("--allow-different-windows", action="store_true")

    p_best = sub.add_parser("best", parents=[common, sections])
    p_best.add_argument("--metric", default="sharpe")
    grp = p_best.add_mutually_exclusive_group()
    grp.add_argument("--maximize", action="store_true")
    grp.add_argument("--minimize", action="store_true")
    p_best.add_argument("--allow-different-windows", action="store_true")

    p_md = sub.add_parser("export-markdown", parents=[common, sections])
    p_md.add_argument("--train-run-hash", required=True)
    p_md.add_argument("--output-path", required=True)

    p_json = sub.add_parser("export-json", parents=[common, sections])
    p_json.add_argument("--train-run-hash", required=True)
    p_json.add_argument("--output-path", required=True)

    p_csv = sub.add_parser("export-csv", parents=[common])
    p_csv.add_argument("train_run_hashes", nargs="+")
    p_csv.add_argument("--output-path", required=True)
    p_csv.add_argument("--metric", action="append", help="repeatable / comma-separated")
    p_csv.add_argument("--allow-different-windows", action="store_true")

    return parser


def _handle(args) -> int:
    store = ExperimentStore(args.artifacts_dir, prefer_parquet=not args.no_parquet)
    cmd = args.command

    if cmd == "summary":
        summary = summarize_experiment_run(args.train_run_hash, store=store)
        print(
            render_experiment_report_markdown(
                summary,
                include_provenance=args.include_provenance,
                include_hash_chain=args.include_hash_chain,
            )
        )

    elif cmd == "compare":
        _require_two(args.train_run_hashes)
        rows = compare_experiment_runs(
            args.train_run_hashes, store=store, metrics=_metrics(args.metric),
            allow_different_windows=args.allow_different_windows,
        )
        print(export_experiment_comparison_csv(rows), end="")

    elif cmd == "best":
        summary = best_experiment_run(
            store=store, metric=args.metric, maximize=not args.minimize,
            allow_different_windows=args.allow_different_windows,
        )
        print(f"best_by={args.metric} train_run_hash={summary.train_run_hash}")
        print(
            render_experiment_report_markdown(
                summary,
                include_provenance=args.include_provenance,
                include_hash_chain=args.include_hash_chain,
            )
        )

    elif cmd == "export-markdown":
        summary = summarize_experiment_run(args.train_run_hash, store=store)
        text = render_experiment_report_markdown(
            summary,
            include_provenance=args.include_provenance,
            include_hash_chain=args.include_hash_chain,
        )
        _write(args.output_path, text)
        print(f"[WRITE] path={args.output_path}")

    elif cmd == "export-json":
        summary = summarize_experiment_run(args.train_run_hash, store=store)
        text = export_experiment_report_json(
            summary,
            include_provenance=args.include_provenance,
            include_hash_chain=args.include_hash_chain,
        )
        _write(args.output_path, text)
        print(f"[WRITE] path={args.output_path}")

    elif cmd == "export-csv":
        _require_two(args.train_run_hashes)
        rows = compare_experiment_runs(
            args.train_run_hashes, store=store, metrics=_metrics(args.metric),
            allow_different_windows=args.allow_different_windows,
        )
        _write(args.output_path, export_experiment_comparison_csv(rows))
        print(f"[WRITE] path={args.output_path}")

    print("RESULT: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return _handle(args)
    except _FAIL_ERRORS as exc:
        print(f"RESULT: FAIL ({type(exc).__name__}: {exc})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
