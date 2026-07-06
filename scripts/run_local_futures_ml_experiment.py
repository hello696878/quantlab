"""
Run the local continuous futures -> ML pipeline (Phase 9 — commit 2).

Thin argparse wrapper around
:func:`app.local_pipeline.run_local_futures_ml_experiment`: it reads
already-ingested raw futures from a ``RawFuturesStore``, builds the continuous
series (Phase 8), and runs the existing Phase 2-5 feature / label / ML /
experiment chain on **local/synthetic** data only.  Persistence is opt-in: a run
is saved **only** when ``--artifacts-dir`` is given (otherwise nothing is written).

The ML path requires ratio-adjusted continuous data, so ``--adjustment-method``
other than ``ratio`` fails loudly.  Local/store only; no network; no vendor; no
new ML dependency.

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\run_local_futures_ml_experiment.py \\
        --base-dir <raw-store> --root-symbol ES --source synthetic \\
        --train-start 2024-04-01 --train-end 2024-06-05 \\
        --validation-start 2024-06-06 --validation-end 2024-09-15 \\
        [--artifacts-dir <exp-store> --overwrite] [--model-type ridge_regression]

Exit code 0 on success; nonzero (RESULT: FAIL) on invalid config / missing data /
untrainable windows / duplicate-without-overwrite.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# Make `app.*` importable when run directly from the repo root (mirrors the other
# local-futures scripts and the pytest pythonpath="." setting).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pydantic import ValidationError  # noqa: E402

from app.datastore.continuous_build import ContinuousSourceError  # noqa: E402
from app.datastore.store import RawFuturesStore  # noqa: E402
from app.experiments import ExperimentError, ExperimentStore  # noqa: E402
from app.instruments import UnknownInstrumentError  # noqa: E402
from app.local_pipeline import (  # noqa: E402
    LocalExperimentConfig,
    run_local_futures_ml_experiment,
)
from app.ml_signal import MlSignalError  # noqa: E402

# Piped/redirected stdout on Windows uses the ANSI code page with strict errors;
# degrade non-ASCII to an escape sequence rather than crash mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")

_BANNER = "=== LOCAL/SYNTHETIC DEMO — not real market performance ==="

# Config / pipeline failures that map to a clean nonzero "RESULT: FAIL" exit
# (argparse handles unknown --model-type / --task-type / malformed dates itself).
_FAIL_ERRORS = (
    ValidationError,
    ContinuousSourceError,
    MlSignalError,
    ExperimentError,
    UnknownInstrumentError,
    ValueError,
    FileNotFoundError,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the local continuous futures -> ML pipeline on already-ingested "
            "RawFuturesStore data (local/synthetic only)."
        )
    )
    parser.add_argument("--base-dir", required=True, help="RawFuturesStore base dir (ingested raw)")
    parser.add_argument("--root-symbol", required=True, help="e.g. ES")
    parser.add_argument("--source", required=True, help="RawFuturesStore namespace, e.g. synthetic")
    parser.add_argument("--train-start", required=True, type=date.fromisoformat)
    parser.add_argument("--train-end", required=True, type=date.fromisoformat)
    parser.add_argument("--validation-start", required=True, type=date.fromisoformat)
    parser.add_argument("--validation-end", required=True, type=date.fromisoformat)
    parser.add_argument("--adjustment-method", default="ratio", help="ratio only (others fail)")
    parser.add_argument(
        "--model-type",
        default="ridge_regression",
        choices=["ridge_regression", "logistic_regression", "dummy_baseline"],
    )
    parser.add_argument(
        "--task-type", default="regression", choices=["regression", "classification"]
    )
    parser.add_argument("--label-column", default="label__forward_return_1")
    parser.add_argument(
        "--feature-columns",
        default="feature__return_20,feature__moving_average_gap_10_50",
        help="comma-separated feature__ columns",
    )
    parser.add_argument("--prediction-horizon", type=int, default=1)
    parser.add_argument("--long-threshold", type=float, default=0.0)
    parser.add_argument("--short-threshold", type=float, default=0.0)
    parser.add_argument("--transaction-cost-bps", type=float, default=1.0)
    parser.add_argument("--artifacts-dir", default=None, help="ExperimentStore base (save a run)")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-parquet", action="store_true", help="force the CSV storage fallback")
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--code-version", default=None)
    args = parser.parse_args(argv)

    try:
        config = LocalExperimentConfig(
            root_symbol=args.root_symbol,
            source=args.source,
            adjustment_method=args.adjustment_method,
            train_start=args.train_start,
            train_end=args.train_end,
            validation_start=args.validation_start,
            validation_end=args.validation_end,
            feature_columns=tuple(c.strip() for c in args.feature_columns.split(",") if c.strip()),
            label_column=args.label_column,
            model_type=args.model_type,
            task_type=args.task_type,
            prediction_horizon=args.prediction_horizon,
            long_threshold=args.long_threshold,
            short_threshold=args.short_threshold,
            transaction_cost_bps=args.transaction_cost_bps,
            overwrite=args.overwrite,
            created_at=args.created_at,
            code_version=args.code_version,
        )
        prefer_parquet = not args.no_parquet
        store = RawFuturesStore(args.base_dir, prefer_parquet=prefer_parquet)
        experiment_store = (
            ExperimentStore(args.artifacts_dir, prefer_parquet=prefer_parquet)
            if args.artifacts_dir
            else None
        )
        result = run_local_futures_ml_experiment(
            store, config=config, experiment_store=experiment_store
        )
    except _FAIL_ERRORS as exc:
        print(f"RESULT: FAIL ({type(exc).__name__}: {exc})")
        return 1

    print(_BANNER)
    print(f"root={result.root_symbol}")
    print(f"source={result.source}")
    print(f"adjustment={result.adjustment_method}")
    print(f"model={config.model_type.value}")
    print(f"task={config.task_type.value}")
    print(f"train={config.train_start} -> {config.train_end}")
    print(f"validation={config.validation_start} -> {config.validation_end}")
    print(f"contracts={','.join(result.contracts)}")
    print(f"train_run_hash={result.train_run_hash}")
    print(f"continuous_config_hash={result.continuous_config_hash}")
    print(f"feature_config_hash={result.feature_config_hash}")
    print(f"label_config_hash={result.label_config_hash}")
    print(f"dataset_config_hash={result.dataset_config_hash}")
    print(f"model_config_hash={result.model_config_hash}")
    print(f"artifact_dir={result.artifact_dir}")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
