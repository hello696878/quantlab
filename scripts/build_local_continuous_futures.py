"""
Build a local continuous futures series from RawFuturesStore raw data
(Phase 8 — commit 2).

Thin argparse wrapper around
:func:`app.datastore.continuous_build.build_continuous_from_store`: it reads the
already-ingested per-contract raw bars for one ``(source, root)`` and builds the
continuous series with the existing machinery.  **Report-only by default** — it
prints a summary and writes nothing.  Persistence is opt-in and explicit:

* ``--write-store`` — persist via ``RawFuturesStore.write_continuous`` into
  ``<base>/continuous/futures/<source>/<root>/<method>.<ext>``;
* ``--output-path`` — write the continuous frame to an explicit CSV instead.

The two are mutually exclusive.  Local files only; no network; no report JSON yet
(that lands in commit 3).

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\build_local_continuous_futures.py \\
        --base-dir <dir> --root-symbol ES --source csv_fixture
    ... --adjustment-method panama --write-store
    ... --output-path <file> --no-parquet

Exit code 0 on success; nonzero on invalid root/source/adjustment/build failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `app.*` importable when run directly from the repo root (mirrors the
# other local-futures scripts and the pytest pythonpath="." setting).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.datastore.continuous_build import (  # noqa: E402
    build_continuous_from_store,
    serialize_continuous_build_result,
)
from app.datastore.store import RawFuturesStore  # noqa: E402
from app.instruments import UnknownInstrumentError  # noqa: E402

# Piped/redirected stdout on Windows uses the ANSI code page with strict errors;
# degrade non-ASCII to an escape sequence rather than crash mid-report.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")


def _rel(base_dir: str | Path, path: Path) -> str:
    """Path relative to ``base_dir`` (POSIX) when possible, else the raw string."""
    try:
        return Path(path).relative_to(Path(base_dir)).as_posix()
    except ValueError:
        return str(path)


def _write_csv(df, path: Path) -> None:
    """Write the continuous frame to CSV (tz-aware timestamps -> ISO strings),
    mirroring the store's CSV serialization so the file round-trips."""
    out = df.copy()
    out["timestamp"] = out["timestamp"].map(lambda t: t.isoformat())
    out.to_csv(path, index=False, lineterminator="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a local continuous futures series from RawFuturesStore raw data "
            "(report-only by default; local files only)."
        )
    )
    parser.add_argument("--base-dir", required=True, help="RawFuturesStore base dir")
    parser.add_argument("--root-symbol", required=True, help="e.g. ES")
    parser.add_argument("--source", required=True, help="e.g. csv_fixture")
    parser.add_argument(
        "--adjustment-method",
        choices=["ratio", "panama", "none"],
        default="ratio",
        help="back-adjustment method (default: ratio)",
    )
    parser.add_argument(
        "--no-parquet", action="store_true", help="force the CSV storage fallback"
    )
    dest = parser.add_mutually_exclusive_group()
    dest.add_argument(
        "--write-store",
        action="store_true",
        help="persist via RawFuturesStore.write_continuous (store continuous namespace)",
    )
    dest.add_argument(
        "--output-path", default=None, help="write the continuous frame to this CSV path"
    )
    parser.add_argument(
        "--report-json",
        default=None,
        help="write a strict-JSON provenance report to this path (does not itself "
        "write continuous output)",
    )
    args = parser.parse_args(argv)

    store = RawFuturesStore(args.base_dir, prefer_parquet=not args.no_parquet)
    try:
        continuous, result = build_continuous_from_store(
            store,
            source=args.source,
            root=args.root_symbol,
            adjustment_method=args.adjustment_method,
        )
    except (ValueError, UnknownInstrumentError, FileNotFoundError) as exc:
        print(f"RESULT: FAIL ({type(exc).__name__}: {exc})")
        return 1

    written_path: str | None = None
    if args.write_store:
        path = store.write_continuous(continuous, args.source)
        written_path = _rel(args.base_dir, path)
    elif args.output_path:
        out = Path(args.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(continuous, out)
        written_path = str(out)

    # report_only reflects whether CONTINUOUS OUTPUT was written — a report is
    # metadata, not continuous output, so --report-json alone stays report-only.
    report_only = not (args.write_store or args.output_path)

    roll_desc = ""
    if result.roll_events:
        ev = result.roll_events[0]
        roll_desc = f" ({ev['from_contract']}->{ev['to_contract']} @ {ev['roll_date']})"
    print(f"root={result.root_symbol}")
    print(f"source={result.source}")
    print(f"adjustment={result.adjustment_method}")
    print(f"contracts={','.join(result.contracts)}")
    print(f"rows={result.rows}")
    print(f"range={result.start} -> {result.end}")
    print(f"rolls={len(result.roll_events)}{roll_desc}")
    print(f"continuous_config_hash={result.continuous_config_hash}")
    if written_path is not None:
        print(f"[WRITE] path={written_path}")

    if args.report_json:
        payload = serialize_continuous_build_result(
            result, output_path=written_path or "", report_only=report_only
        )
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, allow_nan=False) + "\n", encoding="utf-8")
        print(f"[REPORT] path={args.report_json}")

    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
