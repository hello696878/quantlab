"""
Read-only smoke check for local futures daily-bar CSV files (developer utility).

Reads **local** CSV files only (no network, no downloads, no writes), sends
every file through the existing synthetic-fixture loader
(:func:`app.datastore.load_futures_bars_csv` — header check, strict ISO
dates, per-record ``FuturesDailyBar`` validation, registry cross-checks:
month-in-cycle, spec-derived expiry, session timezone), then prints a small
per-file summary plus the linked instrument economics per root symbol.

This is the read-only precursor to ingestion phase I2 of
docs/FUTURES_DATA_INGESTION_PLAN.md: it proves files a human placed on disk
validate cleanly *before* any ingest/write path exists.

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\check_local_futures_csv.py
    backend\\venv\\Scripts\\python.exe scripts\\check_local_futures_csv.py --path <csv-file-or-folder>

Without ``--path`` it reads ``data\\raw\\futures_daily\\`` under the repo
root; a folder is searched recursively for ``*.csv``.  Exits 0 if every file
validates, nonzero otherwise (including: folder missing, no CSV files found).

Read-only: never writes or mutates anything.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when run from the repo root (mirrors the
# pythonpath="." pytest setting in backend/pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.datastore import REQUIRED_COLUMNS, load_futures_bars_csv  # noqa: E402
from app.instruments import get_instrument  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "raw" / "futures_daily"

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


def check_file(path: Path) -> bool:
    """Validate one CSV through the fixture loader and print its summary."""
    try:
        bars = load_futures_bars_csv(path)
    except Exception as exc:  # loader wraps failures; report and keep going
        print(f"[FAIL] {path}")
        print(f"    validation: FAIL ({type(exc).__name__}: {exc})")
        return False

    roots = sorted({b.root_symbol for b in bars})
    contracts = sorted({b.contract_symbol for b in bars})
    ts_min = min(b.timestamp for b in bars)
    ts_max = max(b.timestamp for b in bars)

    print(f"[OK] {path}")
    print(f"    rows:       {len(bars)}")
    print(f"    symbols:    {', '.join(roots)}")
    print(f"    contracts:  {', '.join(contracts)}")
    print(f"    timestamps: {ts_min.isoformat()} .. {ts_max.isoformat()}")
    print(
        f"    validation: OK ({len(bars)} bar(s) via FuturesDailyBar "
        f"+ registry cross-checks)"
    )
    # Post-validation the registry link is guaranteed, so this cannot fail.
    for root in roots:
        spec = get_instrument(root)
        print(
            f"    {root}: tick_size={spec.tick_size} "
            f"tick_value={spec.tick_value} "
            f"contract_multiplier={spec.contract_multiplier}"
        )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate local futures daily-bar CSV files (read-only)."
    )
    parser.add_argument(
        "--path",
        default=None,
        help=(
            "CSV file or folder to check (folders are searched recursively); "
            f"default: {DEFAULT_DATA_DIR}"
        ),
    )
    args = parser.parse_args(argv)
    if args.path is not None and not args.path.strip():
        # Path("") normalizes to "." and would silently scan the whole cwd.
        print("FAIL: --path must not be empty")
        return 1
    target = Path(args.path) if args.path is not None else DEFAULT_DATA_DIR

    if not target.exists():
        print(f"FAIL: path not found: {target}")
        if args.path is None:
            print("Create the default folder and drop daily-bar CSV files in it:")
            print(f"    New-Item -ItemType Directory -Force {DEFAULT_DATA_DIR}")
            print("Each CSV needs the canonical 12-column header:")
            print(f"    {','.join(REQUIRED_COLUMNS)}")
            print("(Or point at an existing file/folder with --path.)")
        return 1

    files = _collect_csv_files(target)
    if not files:
        print(f"FAIL: no CSV files found under: {target}")
        return 1

    print(f"local futures CSV smoke check: {len(files)} file(s) under {target}")
    failures = sum(0 if check_file(f) else 1 for f in files)
    if failures:
        print(f"RESULT: FAIL ({failures}/{len(files)} file(s) failed)")
        return 1
    print(f"RESULT: OK ({len(files)}/{len(files)} file(s) validated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
