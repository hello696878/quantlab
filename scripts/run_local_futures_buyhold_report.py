"""
Local futures buy-and-hold report (read-only; one contract, per contract).

The smallest research path on top of the stable local futures data layer:

    processed local CSV -> load bars -> attach instrument metadata
    -> one-contract buy-and-hold report per contract -> print

Reads **local** normalized futures daily-bar CSVs only (no network, no
downloads, no writes), validates every file through the existing loader
(:func:`app.datastore.load_futures_bars_csv`), groups the validated bars by
``(root_symbol, contract_symbol)``, and for each contract runs the tiny
audited long-one-contract report from
:func:`app.reports.long_trade_report` -- buy the first bar's close, sell the
last bar's close -- printing the entry/exit, the price/tick move, the linked
instrument economics, and the P&L computed two independent ways
(``price_move * contract_multiplier`` and ``tick_move * tick_value``) which
agree exactly when the spec's tick-value invariant holds.

This is a developer research utility, NOT a production backtest engine: no
positions over time, no costs, no slippage, no continuous-futures stitching
(each contract is reported on its own, unadjusted).

Meant to run on the output of ``scripts/normalize_local_futures_csv.py``
(e.g. ``ES_daily.csv``), but any valid futures daily-bar CSV works.

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\run_local_futures_buyhold_report.py --input <csv-file-or-folder>

A folder is searched recursively for ``*.csv``.  Exits 0 if every file
validates, every contract's metadata resolves, and every P&L check agrees;
nonzero otherwise (including: path missing, no CSV files found).

Read-only: inputs are opened read-only and never modified; nothing is written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when run from the repo root (mirrors the
# pythonpath="." pytest setting in backend/pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.datastore import FuturesDailyBar, load_futures_bars_csv  # noqa: E402
from app.reports import long_trade_report  # noqa: E402

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


def report_contract(root: str, contract: str, bars: list[FuturesDailyBar]) -> bool:
    """Print the one-contract buy-and-hold summary; return the P&L-check result.

    ``bars`` are all the loaded bars for one ``(root, contract)`` group (>= 1).
    The economics come from the audited ``long_trade_report``; only the
    entry/exit timestamps are taken here (it does not expose them).
    """
    ordered = sorted(bars, key=lambda b: b.timestamp)
    try:
        r = long_trade_report(ordered, contracts=1)
    except Exception as exc:  # metadata/report failure -> hard failure
        print(f"[FAIL] {root} / {contract}: {type(exc).__name__}: {exc}")
        return False

    entry_ts = ordered[0].timestamp
    exit_ts = ordered[-1].timestamp
    ok = r.pnl_matches

    def p(label: str, value: object) -> None:
        print(f"    {label + ':':<21}{value}")

    print(
        f"[{'OK' if ok else 'FAIL'}] {root} / {contract} "
        f"buy-and-hold 1 contract, {len(ordered)} bar(s)"
    )
    p("root_symbol", r.root_symbol)
    p("contract_symbol", r.contract_symbol)
    p("name", r.name)
    p("exchange", r.exchange)
    p("currency", r.currency)
    p("entry_timestamp", entry_ts.isoformat())
    p("exit_timestamp", exit_ts.isoformat())
    p("entry_close", f"{r.entry_price:.2f}")
    p("exit_close", f"{r.exit_price:.2f}")
    p("price_move", f"{r.price_move:.2f}")
    p("tick_move", f"{r.tick_move:.1f}")
    p("contract_multiplier", r.contract_multiplier)
    p("tick_size", r.tick_size)
    p("tick_value", r.tick_value)
    p("pnl_by_multiplier", f"{r.pnl_usd:.2f}")
    p("pnl_by_ticks", f"{r.tick_pnl_usd:.2f}")
    if ok:
        print("    pnl_check (multiplier == ticks): OK")
    else:
        print(
            f"    pnl_check (multiplier == ticks): FAIL "
            f"(mult {r.pnl_usd:.4f} != ticks {r.tick_pnl_usd:.4f})"
        )
    # The instrument yamls ask these to be surfaced in every report (the
    # audited helper carries them for exactly this; mirror the sibling
    # scripts/run_synthetic_futures_report.py).
    if r.warnings:
        print(f"    warnings ({len(r.warnings)}):")
        for w in r.warnings:
            print(f"      - {w}")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "One-contract buy-and-hold report over normalized local futures "
            "daily-bar CSVs (read-only; inputs never modified)."
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

    print(f"local futures buy-and-hold report: {len(files)} input file(s) under {source}")

    # Validate every file first; a report over partial data would mislead.
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

    groups: dict[tuple[str, str], list[FuturesDailyBar]] = {}
    for b in bars:
        groups.setdefault((b.root_symbol, b.contract_symbol), []).append(b)
    keys = sorted(groups)

    print("=== per-contract buy-and-hold summary (long 1 contract, first close -> last close) ===")
    group_failures = 0
    for root, contract in keys:
        if not report_contract(root, contract, groups[(root, contract)]):
            group_failures += 1

    print(
        f"overall: {len(keys)} contract(s) across {len(bars)} row(s) in {len(files)} file(s)"
    )
    if group_failures:
        print(f"RESULT: FAIL ({group_failures}/{len(keys)} contract(s) failed the P&L check)")
        return 1
    print(f"RESULT: OK ({len(files)} file(s) -> {len(keys)} contract(s) reported)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
