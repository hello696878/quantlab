"""
Run a local futures ML **experiment batch / sweep** (Phase 11 — commit 3).

Thin argparse wrapper around ``app.batch_experiments``: it reads a JSON batch spec
(a base :class:`LocalExperimentConfig` + a sweep ``grid`` + policy), expands it into
a deterministic list of configs, and runs them **sequentially** through the existing
Phase 9 pipeline — saving successful runs through an ``ExperimentStore`` (Phase 5).
It adds no ML: the batch orchestrates existing runs, no more.

Optionally it writes a strict batch report JSON (``--report-json``) and a Phase 10
comparison over the *successful* runs (``--comparison-output``, ``.csv`` / ``.json``).
The Phase 10 reporting layer is used **only here in the CLI**, never in the runner.

Local / synthetic data only; sequential (no parallelism); no network; no vendor; no
new ML dependency; not investment advice.

Config JSON shape::

    {
      "base": {"root_symbol": "ES", "source": "synthetic", ...},
      "grid": {"model_type": ["ridge_regression", "dummy_baseline"], "random_seed": [0, 1]},
      "overwrite": false,
      "on_error": "continue"
    }

Usage (from the repo root)::

    backend\\venv\\Scripts\\python.exe scripts\\run_local_futures_ml_batch.py \\
        --base-dir <raw-store> --artifacts-dir <exp-store> --config-json <spec.json> \\
        [--overwrite] [--stop-on-error | --continue-on-error] \\
        [--report-json <path>] [--comparison-output <path.csv|.json>] [--dry-run] [--no-parquet]

Exit code 0 on success; nonzero (``RESULT: FAIL``) on invalid spec / missing paths /
all items failing / stop-on-error / comparison requiring >= 2 successful runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `app.*` importable when run directly from the repo root (mirrors the other
# local-futures scripts and the pytest pythonpath="." setting).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pydantic import ValidationError  # noqa: E402

from app.batch_experiments import (  # noqa: E402
    BatchError,
    LocalExperimentBatchConfig,
    run_local_experiment_batch,
    summarize_batch_result,
)
from app.datastore.store import RawFuturesStore  # noqa: E402
from app.experiments import ExperimentError, ExperimentStore  # noqa: E402
from app.local_pipeline import LocalExperimentConfig  # noqa: E402

# Phase 10 reporting is wired in **only** at the CLI layer (never in the runner).
from app.reporting import (  # noqa: E402
    compare_experiment_runs,
    export_experiment_comparison_csv,
    export_experiment_comparison_json,
)

# Piped/redirected stdout on Windows uses the ANSI code page with strict errors;
# degrade non-ASCII to an escape sequence rather than crash mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")

_BANNER = "=== LOCAL/SYNTHETIC BATCH — not real market performance; not investment advice ==="

# Setup / expansion / run failures that map to a clean nonzero "RESULT: FAIL".
_FAIL_ERRORS = (
    ValidationError,
    BatchError,
    ExperimentError,
    ValueError,          # incl. json.JSONDecodeError, BatchError
    KeyError,
    TypeError,
    FileNotFoundError,
    OSError,
)

_COMPARISON_WRITERS = {
    ".csv": export_experiment_comparison_csv,
    ".json": export_experiment_comparison_json,
}


def _write_text(path_str: str, text: str) -> None:
    """Write ``text`` to ``path_str``, creating the parent directory if needed."""
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local futures ML experiment batch/sweep over already-ingested "
            "RawFuturesStore data (local/synthetic only; sequential; no network)."
        )
    )
    parser.add_argument("--base-dir", required=True, help="RawFuturesStore base dir (ingested raw)")
    parser.add_argument("--config-json", required=True, help="batch spec JSON (base + grid + policy)")
    parser.add_argument(
        "--artifacts-dir", default=None, help="ExperimentStore base (required unless --dry-run)"
    )
    parser.add_argument("--dry-run", action="store_true", help="expand/plan only; write nothing")
    parser.add_argument(
        "--overwrite", action="store_true", help="force overwrite of existing runs (all configs)"
    )
    error_policy = parser.add_mutually_exclusive_group()
    error_policy.add_argument("--stop-on-error", action="store_true", help="halt after the first failure")
    error_policy.add_argument(
        "--continue-on-error", action="store_true", help="record failures and continue (default)"
    )
    parser.add_argument("--report-json", default=None, help="write the batch manifest JSON to this path")
    parser.add_argument(
        "--comparison-output",
        default=None,
        help="write a Phase 10 comparison of successful runs (.csv or .json)",
    )
    parser.add_argument("--no-parquet", action="store_true", help="force the CSV storage fallback")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    print(_BANNER)

    # --- early, cheap validation (fail before running anything) --------------- #
    if not args.dry_run and not args.artifacts_dir:
        print("RESULT: FAIL (--artifacts-dir is required unless --dry-run)")
        return 1

    comparison_writer = None
    if args.comparison_output:
        ext = Path(args.comparison_output).suffix.lower()
        comparison_writer = _COMPARISON_WRITERS.get(ext)
        if comparison_writer is None:
            print(
                f"RESULT: FAIL (unsupported --comparison-output extension {ext!r}; use .csv or .json)"
            )
            return 1

    cli_on_error = "stop" if args.stop_on_error else "continue" if args.continue_on_error else None

    # --- load spec, build configs, run the batch ------------------------------ #
    try:
        spec = json.loads(Path(args.config_json).read_text(encoding="utf-8"))
        if not isinstance(spec, dict) or "base" not in spec:
            raise ValueError("config JSON must be an object with a 'base' key")

        base_dict = dict(spec["base"])
        grid = spec.get("grid", {})
        json_overwrite = bool(spec.get("overwrite", False))
        json_on_error = spec.get("on_error", "continue")

        effective_overwrite = bool(args.overwrite or json_overwrite)
        effective_on_error = cli_on_error or json_on_error

        base_config = LocalExperimentConfig(**{**base_dict, "overwrite": effective_overwrite})
        batch_config = LocalExperimentBatchConfig(
            base=base_config,
            grid=grid,
            overwrite=effective_overwrite,
            on_error=effective_on_error,
        )
        configs = batch_config.expand()

        prefer_parquet = not args.no_parquet
        raw_store = RawFuturesStore(args.base_dir, prefer_parquet=prefer_parquet)
        experiment_store = (
            None
            if args.dry_run
            else ExperimentStore(args.artifacts_dir, prefer_parquet=prefer_parquet)
        )
        result = run_local_experiment_batch(
            raw_store,
            configs,
            experiment_store=experiment_store,
            on_error=effective_on_error,
            dry_run=args.dry_run,
        )
    except _FAIL_ERRORS as exc:
        print(f"RESULT: FAIL ({type(exc).__name__}: {exc})")
        return 1

    # --- per-item lines + summary -------------------------------------------- #
    for item in result.items:
        if item.status == "ok":
            print(f"[{item.item_id}] ok train_run_hash={item.train_run_hash}")
        elif item.status == "failed":
            print(f"[{item.item_id}] failed error={item.error}")
        else:
            print(f"[{item.item_id}] skipped reason={item.error}")

    print(f"batch_config_hash={result.batch_config_hash}")
    print(f"n_total={result.n_total}")
    print(f"n_ok={result.n_ok}")
    print(f"n_failed={result.n_failed}")
    print(f"n_skipped={result.n_skipped}")

    fail_reason: str | None = None
    if not args.dry_run and result.n_ok == 0:
        fail_reason = "all items failed"
    if fail_reason is None and effective_on_error == "stop" and result.n_failed > 0:
        fail_reason = "stopped after a failing item (--stop-on-error)"

    # --- optional strict batch report JSON ----------------------------------- #
    if args.report_json:
        try:
            _write_text(
                args.report_json,
                json.dumps(summarize_batch_result(result), allow_nan=False, sort_keys=True),
            )
            print(f"[REPORT] path={args.report_json}")
        except OSError as exc:
            fail_reason = fail_reason or f"failed to write --report-json ({type(exc).__name__}: {exc})"

    # --- optional Phase 10 comparison over the successful runs (CLI-only) ----- #
    if args.comparison_output:
        hashes = result.train_run_hashes
        if len(hashes) < 2:
            fail_reason = fail_reason or (
                f"--comparison-output needs at least 2 successful runs, got {len(hashes)}"
            )
        else:
            try:
                rows = compare_experiment_runs(hashes, store=experiment_store)
                _write_text(args.comparison_output, comparison_writer(rows))
                print(f"[COMPARE] path={args.comparison_output}")
            except (ExperimentError, ValueError, OSError) as exc:
                fail_reason = fail_reason or f"comparison failed ({type(exc).__name__}: {exc})"

    if fail_reason is not None:
        print(f"RESULT: FAIL ({fail_reason})")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
