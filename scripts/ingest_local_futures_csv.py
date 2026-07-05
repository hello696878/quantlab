"""
Store-backed local futures CSV ingest (Phase 7 — commit 2).

Thin argparse wrapper around
:func:`app.datastore.ingest.ingest_local_futures_csv`: it loads/validates local
CSV daily bars and writes them into the ``RawFuturesStore`` raw namespace under
``--base-dir`` (``raw/futures/<source>/<root>/<contract>``), reading each contract
back and verifying the round-trip.  Local files only; no network; no ingestion
log yet (that lands in commit 3).

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\ingest_local_futures_csv.py <csv...> --base-dir <dir>
    ... --source csv_local --overwrite --no-parquet

Exit code 0 on success; nonzero on invalid CSV / duplicate / validation error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when run directly from the repo root (mirrors the
# pythonpath="." pytest setting and the other local-futures scripts).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.datastore.csv_fixtures import FixtureFormatError  # noqa: E402
from app.datastore.ingest import (  # noqa: E402
    DuplicateIngestError,
    IngestVerificationError,
    ingest_local_futures_csv,
)
from app.datastore.store import RawSchemaError  # noqa: E402

# Piped/redirected stdout on Windows uses the ANSI code page with strict errors;
# degrade non-ASCII to an escape sequence rather than crash mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest local futures daily-bar CSV(s) into the RawFuturesStore raw "
            "namespace (local files only, inputs never modified)."
        )
    )
    parser.add_argument("paths", nargs="+", help="local CSV file(s) to ingest")
    parser.add_argument(
        "--base-dir", required=True, help="RawFuturesStore base dir (raw/ lands under it)"
    )
    parser.add_argument(
        "--source", default=None, help="override the source column / store namespace"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="replace existing contract files"
    )
    parser.add_argument(
        "--no-parquet", action="store_true", help="force the CSV storage fallback"
    )
    parser.add_argument(
        "--log-path",
        default=None,
        help="ingestion-log path (default: <base-dir>/logs/futures_ingest.jsonl)",
    )
    args = parser.parse_args(argv)

    try:
        report = ingest_local_futures_csv(
            args.paths,
            base_dir=args.base_dir,
            source=args.source,
            overwrite=args.overwrite,
            prefer_parquet=not args.no_parquet,
            log_path=args.log_path,
        )
    except (
        FixtureFormatError,
        RawSchemaError,
        DuplicateIngestError,
        IngestVerificationError,
        ValueError,
    ) as exc:
        print(f"RESULT: FAIL ({type(exc).__name__}: {exc})")
        return 1

    for c in report.contracts:
        print(
            f"[WRITE] {c.source}/{c.root_symbol}/{c.contract_symbol} "
            f"rows={c.rows} hash={c.version_hash}"
        )
    for w in report.warnings:
        print(f"[WARN] {w}")
    print(f"[LOG] path={report.log_path}")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
