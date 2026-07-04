"""
Local futures daily-bar CSV report (read-only summary of normalized output).

Reads **local** CSV files only (no network, no downloads, no writes), sends
every file through the existing loader
(:func:`app.datastore.load_futures_bars_csv` - header check, strict ISO
dates, per-record ``FuturesDailyBar`` validation, registry cross-checks),
groups the validated bars by ``root_symbol``, loads the instrument spec for
each root, and prints a tiny per-root trade summary: a long-one-contract
"buy the first close, sell the last close" P&L computed two independent ways
(``price_move * contract_multiplier`` and ``tick_move * tick_value``) that
agree exactly when the spec's tick-value invariant holds.

This is the last read-only step of the local futures workflow from
docs/FUTURES_DATA_INGESTION_PLAN.md:

    raw local CSV -> validate -> normalize -> processed CSV -> report summary

It is meant to run on the normalized per-root output of
``scripts/normalize_local_futures_csv.py`` (e.g. ``ES_daily.csv``), but any
valid futures daily-bar CSV works.  The P&L is a naive first-close-to-last
-close move over whatever bars a root contains; when a root spans more than
one contract this is not roll-adjusted (continuous stitching is out of scope
in Phase 1) and the summary says so.

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\report_local_futures_csv.py --input <csv-file-or-folder>

A folder is searched recursively for ``*.csv``.  Exits 0 if every file
validates, every root's metadata resolves, and every P&L check agrees;
nonzero otherwise (including: path missing, no CSV files found).

Read-only: inputs are opened read-only and never modified; nothing is written.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

# Make `app.*` importable when run from the repo root (mirrors the
# pythonpath="." pytest setting in backend/pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.datastore import FuturesDailyBar, load_futures_bars_csv  # noqa: E402
from app.instruments import get_instrument  # noqa: E402

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


def report_root(root: str, bars: list[FuturesDailyBar]) -> bool:
    """Print the one-contract summary for one root; return the P&L-check result.

    ``bars`` are all the loaded bars for ``root`` (>= 1).  Metadata is looked
    up from the registry; the loader already guaranteed the link exists, so a
    failure here is defensive only and is reported as a hard failure.
    """
    try:
        spec = get_instrument(root)
    except Exception as exc:  # defensive: loader already cross-checked the link
        print(f"[FAIL] {root}: metadata lookup failed ({type(exc).__name__}: {exc})")
        return False

    ordered = sorted(bars, key=lambda b: b.timestamp)
    contracts = sorted({b.contract_symbol for b in ordered})
    ts_min = ordered[0].timestamp
    ts_max = ordered[-1].timestamp
    entry = ordered[0].close
    exit_ = ordered[-1].close
    move = exit_ - entry
    tick_move = move / spec.tick_size
    pnl = move * spec.contract_multiplier
    tick_pnl = tick_move * spec.tick_value
    pnl_matches = math.isclose(pnl, tick_pnl, rel_tol=1e-9, abs_tol=1e-9)

    print(f"[{'OK' if pnl_matches else 'FAIL'}] {root} ({len(ordered)} row(s))")
    print(f"    root_symbol:         {root}")
    print(f"    rows:                {len(ordered)}")
    print(f"    contracts:           {', '.join(contracts)}")
    print(f"    timestamps:          {ts_min.isoformat()} .. {ts_max.isoformat()}")
    print(f"    contract_multiplier: {spec.contract_multiplier}")
    print(f"    tick_size:           {spec.tick_size}")
    print(f"    tick_value:          {spec.tick_value}")
    print(f"    first_close:         {entry:.2f}")
    print(f"    last_close:          {exit_:.2f}")
    print(f"    price_move:          {move:.2f}")
    print(f"    tick_move:           {tick_move:.1f}")
    print(f"    pnl_usd (1 contract): {pnl:.2f}")
    print(f"    tick_pnl_usd:        {tick_pnl:.2f}")
    if pnl_matches:
        print("    pnl_check (direct == tick-based): OK")
    else:
        print(
            f"    pnl_check (direct == tick-based): FAIL "
            f"(direct {pnl:.4f} != tick {tick_pnl:.4f})"
        )
    if len(contracts) > 1:
        print(
            f"    note: first->last move spans {len(contracts)} contracts "
            f"(not roll-adjusted; continuous stitching is out of Phase 1 scope)"
        )
    return pnl_matches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize normalized local futures daily-bar CSVs per root symbol "
            "(read-only; inputs never modified)."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="processed CSV file or folder to report (folders searched recursively)",
    )
    args = parser.parse_args(argv)
    if not args.input.strip():
        # Path("") normalizes to "." and would silently scan the whole cwd.
        print("FAIL: --input must not be empty")
        return 1

    source = Path(args.input)
    if not source.exists():
        print(f"FAIL: input path not found: {source}")
        return 1

    files = _collect_csv_files(source)
    if not files:
        print(f"FAIL: no CSV files found under: {source}")
        return 1

    print(f"local futures CSV report: {len(files)} input file(s) under {source}")

    # Validate every file first; a report over partial data would be misleading.
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
        print(f"RESULT: FAIL ({failures}/{len(files)} input file(s) failed to validate)")
        return 1

    roots = sorted({b.root_symbol for b in bars})
    print(f"=== per-root summary (long 1 contract, first close -> last close) ===")
    root_failures = 0
    for root in roots:
        if not report_root(root, [b for b in bars if b.root_symbol == root]):
            root_failures += 1

    print(
        f"overall: {len(roots)} root(s), {len(bars)} row(s) across {len(files)} file(s)"
    )
    if root_failures:
        print(f"RESULT: FAIL ({root_failures}/{len(roots)} root(s) failed the P&L check)")
        return 1
    print(f"RESULT: OK ({len(files)} file(s) -> {len(roots)} root(s) reported)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
