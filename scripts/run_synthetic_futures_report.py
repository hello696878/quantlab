"""
Synthetic futures mini-backtest/report (developer utility, NOT a backtest engine).

For each default root (ES, NQ) this script:

1. loads the instrument spec from the registry,
2. builds three synthetic daily bars for the June 2025 contract (symbol and
   expiry derived from the spec; prices are made up, whole-tick moves),
3. runs the tiny long-one-contract trade report from app.reports
   (entry = first close, exit = last close),
4. prints the linked metadata, trade arithmetic, and whether the direct
   (multiplier-based) P&L matches the tick-based P&L.

Exits 0 if every scenario validates and both P&L calculations agree,
nonzero otherwise.

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\run_synthetic_futures_report.py

Read-only, synthetic data only: no downloads, no writes.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

# Make `app.*` importable when run from the repo root (mirrors the
# pythonpath="." pytest setting in backend/pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.datastore import FuturesDailyBar  # noqa: E402
from app.instruments import get_instrument  # noqa: E402
from app.reports import long_trade_report  # noqa: E402

DEFAULT_ROOTS = ["ES", "NQ"]

# Synthetic close paths (index points, whole-tick moves); not market data.
SAMPLE_CLOSES = {
    "ES": [6000.00, 6004.25, 6010.50],     # +10.50 pts = 42 ticks
    "NQ": [21800.00, 21830.50, 21850.25],  # +50.25 pts = 201 ticks
}


def _synthetic_bars(root: str, spec) -> list[FuturesDailyBar]:
    """Daily bars for the June 2025 contract of ``root``, one per close."""
    if root not in SAMPLE_CLOSES:
        raise ValueError(
            f"no synthetic closes defined for {root!r}; add an entry to SAMPLE_CLOSES"
        )
    contract = spec.build_contract_symbol("M", 2025)
    expiry = spec.expiry_date("M", 2025)
    bars = []
    for day, close in enumerate(SAMPLE_CLOSES[root]):
        bars.append(
            FuturesDailyBar(
                timestamp=datetime.datetime(
                    2025, 6, 16 + day, 21, 0, tzinfo=datetime.timezone.utc
                ),
                open=close - 2.0,
                high=close + 3.0,
                low=close - 5.0,
                close=close,
                volume=100_000,
                open_interest=500_000.0,
                root_symbol=root,
                contract_symbol=contract,
                expiry=expiry,
                source="synthetic",
                timezone="America/Chicago",
            )
        )
    return bars


def check_one(root: str) -> bool:
    """Run one synthetic long-trade scenario and print the report."""
    try:
        spec = get_instrument(root)
        bars = _synthetic_bars(root, spec)
        report = long_trade_report(bars, contracts=1)
        if not report.pnl_matches:
            raise ValueError(
                f"direct pnl {report.pnl_usd} != tick pnl {report.tick_pnl_usd}"
            )
    except Exception as exc:
        print(f"[FAIL] {root}: {type(exc).__name__}: {exc}")
        return False

    r = report
    print(f"[OK] {r.root_symbol} / {r.contract_symbol} long {r.contracts} contract(s), {len(bars)} bars")
    print(f"    root_symbol:         {r.root_symbol}")
    print(f"    contract_symbol:     {r.contract_symbol}")
    print(f"    name:                {r.name}")
    print(f"    exchange:            {r.exchange}")
    print(f"    currency:            {r.currency}")
    print(f"    contract_multiplier: {r.contract_multiplier}")
    print(f"    tick_size:           {r.tick_size}")
    print(f"    tick_value:          {r.tick_value}")
    print(f"    entry_price:         {r.entry_price:.2f}")
    print(f"    exit_price:          {r.exit_price:.2f}")
    print(f"    price_move:          {r.price_move:.2f}")
    print(f"    tick_move:           {r.tick_move:.1f}")
    print(f"    contracts:           {r.contracts}")
    print(f"    pnl_usd:             {r.pnl_usd:.2f}")
    print(f"    tick_pnl_usd:        {r.tick_pnl_usd:.2f}")
    print("    pnl_check (direct == tick-based): OK")
    if r.warnings:
        print(f"    warnings ({len(r.warnings)}):")
        for w in r.warnings:
            print(f"      - {w}")
    return True


def main(roots: list[str] | None = None) -> int:
    roots = roots if roots is not None else DEFAULT_ROOTS
    if not roots:
        print("FAIL: no root symbols to run")
        return 1

    print(f"synthetic futures mini report: {len(roots)} scenario(s)")
    failures = sum(0 if check_one(root) else 1 for root in roots)
    if failures:
        print(f"RESULT: FAIL ({failures}/{len(roots)} scenario(s) failed)")
        return 1
    print(f"RESULT: OK ({len(roots)}/{len(roots)} scenarios passed, pnl checks agree)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
