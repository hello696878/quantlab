"""
Local futures daily-bar CSV normalizer (read-only in, write-once out).

Reads **local** CSV files only (no network, no downloads), validates every
input file through the existing loader
(:func:`app.datastore.load_futures_bars_csv` - header check, strict ISO
dates, per-record ``FuturesDailyBar`` validation, registry cross-checks),
and only if ALL inputs validate writes one normalized CSV per root symbol
(e.g. ``ES_daily.csv``) into the output folder.

Normalization contract:

* columns: the canonical 12 (``app.datastore.REQUIRED_COLUMNS`` order):
  timestamp, open, high, low, close, volume, open_interest, root_symbol,
  contract_symbol, expiry, source, timezone;
* rows sorted by (root_symbol, contract_symbol, timestamp);
* timestamps ISO UTC, expiry ISO date, blank cell for missing open interest;
* duplicate (contract_symbol, timestamp) pairs ACROSS input files are
  rejected (the loader already rejects them within one file);
* the output re-validates through the same loader (round-trip invariant).

Inputs are never modified.  Output files are overwritten deterministically
on re-run.  Nothing is written unless every input file validates.  The
output folder must not sit inside the input folder (a re-run would read
its own output back as input), and a planned output file must never be one
of the input files (it would be truncated in place).

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\normalize_local_futures_csv.py --input <csv-file-or-folder>
    backend\\venv\\Scripts\\python.exe scripts\\normalize_local_futures_csv.py --input <path> --output-dir <folder>

Without ``--output-dir`` it writes to ``data\\processed\\futures_daily\\``
under the repo root (gitignored).  Exits 0 if all files validate and write,
nonzero otherwise.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Make `app.*` importable when run from the repo root (mirrors the
# pythonpath="." pytest setting in backend/pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.datastore import REQUIRED_COLUMNS, load_futures_bars_csv  # noqa: E402
from app.datastore.daily_bar import FuturesDailyBar  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "processed" / "futures_daily"

# Piped/redirected stdout on Windows uses the ANSI code page with strict
# errors; a non-ASCII path or CSV cell echoed in a message must degrade to
# an escape sequence, never crash the report mid-run.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")


def _collect_csv_files(target: Path) -> list[Path]:
    """One explicit file, or every *.csv file under a folder (recursive, sorted).

    Filtered to files: a *directory* named ``*.csv`` must not be treated as
    a candidate file.
    """
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*.csv") if p.is_file())


def _bar_to_row(bar: FuturesDailyBar) -> list[str]:
    """Serialize one validated bar into canonical-column CSV cells."""
    return [
        bar.timestamp.isoformat(),
        str(bar.open),
        str(bar.high),
        str(bar.low),
        str(bar.close),
        str(bar.volume),
        "" if bar.open_interest is None else str(bar.open_interest),
        bar.root_symbol,
        bar.contract_symbol,
        bar.expiry.isoformat(),
        bar.source,
        bar.timezone,
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate local futures daily-bar CSVs and write one normalized "
            "CSV per root symbol (local files only, inputs never modified)."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="CSV file or folder to normalize (folders are searched recursively)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"folder for the normalized per-root CSVs; default: {DEFAULT_OUTPUT_DIR}",
    )
    args = parser.parse_args(argv)
    if not args.input.strip():
        # Path("") normalizes to "." and would silently scan the whole cwd.
        print("FAIL: --input must not be empty")
        return 1
    if args.output_dir is not None and not args.output_dir.strip():
        print("FAIL: --output-dir must not be empty")
        return 1

    source = Path(args.input)
    out_dir = Path(args.output_dir) if args.output_dir is not None else DEFAULT_OUTPUT_DIR

    if not source.exists():
        print(f"FAIL: input path not found: {source}")
        return 1
    if source.is_dir():
        try:
            out_dir.resolve().relative_to(source.resolve())
        except ValueError:
            pass
        else:
            print(
                f"FAIL: output dir {out_dir} is inside input folder {source}; "
                f"a re-run would read its own output back as input"
            )
            return 1

    files = _collect_csv_files(source)
    if not files:
        print(f"FAIL: no CSV files found under: {source}")
        return 1

    print(f"local futures CSV normalize: {len(files)} input file(s) under {source}")

    # Validate everything first; write nothing unless every file passes.
    bars: list[FuturesDailyBar] = []
    failures = 0
    for path in files:
        try:
            file_bars = load_futures_bars_csv(path)
        except Exception as exc:  # loader wraps failures; report and keep going
            print(f"[FAIL] {path}: {type(exc).__name__}: {exc}")
            failures += 1
            continue
        print(f"[OK] {path} ({len(file_bars)} row(s))")
        bars.extend(file_bars)
    if failures:
        print(f"RESULT: FAIL ({failures}/{len(files)} input file(s) failed; nothing written)")
        return 1

    # The loader rejects duplicates within a file; re-check across files.
    seen: set[tuple[str, str]] = set()
    for bar in bars:
        key = (bar.contract_symbol, bar.timestamp.isoformat())
        if key in seen:
            print(
                f"FAIL: duplicate (contract_symbol, timestamp) = {key} across "
                f"input files; nothing written"
            )
            return 1
        seen.add(key)

    bars.sort(key=lambda b: (b.root_symbol, b.contract_symbol, b.timestamp))
    roots = sorted({b.root_symbol for b in bars})

    # A planned output path must never be one of the input files: with a
    # single-file --input the folder guard above never runs, and opening an
    # input with mode "w" would truncate it in place.
    input_paths = {p.resolve() for p in files}
    colliding = [
        out_dir / f"{root}_daily.csv"
        for root in roots
        if (out_dir / f"{root}_daily.csv").resolve() in input_paths
    ]
    if colliding:
        print(
            f"FAIL: planned output file {colliding[0]} is also an input file; "
            f"nothing written"
        )
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[tuple[Path, int]] = []
    for root in roots:
        root_bars = [b for b in bars if b.root_symbol == root]
        out_path = out_dir / f"{root}_daily.csv"
        with out_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(REQUIRED_COLUMNS)
            writer.writerows(_bar_to_row(b) for b in root_bars)
        written.append((out_path, len(root_bars)))
        print(f"[WRITE] {out_path} ({len(root_bars)} row(s))")

    print(f"    symbols:     {', '.join(roots)}")
    print(f"    input rows:  {len(bars)} across {len(files)} file(s)")
    print(f"    output rows: {sum(n for _, n in written)} across {len(written)} file(s)")
    print(f"RESULT: OK ({len(files)} input file(s) -> {len(written)} output file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
