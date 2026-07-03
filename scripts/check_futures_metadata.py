"""
Read-only futures data metadata smoke report (developer utility).

For each root symbol (default: ES, NQ, YM, RTY) this script:

1. loads the instrument spec from the registry,
2. builds one synthetic daily bar for the June 2025 contract (symbol and
   expiry derived from the spec itself),
3. validates the bar through the FuturesDailyBar schema (which re-checks the
   registry link and root/contract match),
4. prints the linked metadata plus the dollar value of a 1.00-point move
   (contract_multiplier) and of a 1-tick move (tick_value).

Exits 0 if every sample validates and links correctly, nonzero otherwise.

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\check_futures_metadata.py

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

DEFAULT_ROOTS = ["ES", "NQ", "YM", "RTY"]

# Plausible synthetic price levels (index points); not market data.
SAMPLE_PRICE = {"ES": 6000.0, "NQ": 21800.0, "YM": 42500.0, "RTY": 2100.0}


def _synthetic_bar(root: str, spec) -> FuturesDailyBar:
    """One synthetic daily bar for the June 2025 contract of ``root``."""
    p = SAMPLE_PRICE.get(root, 100.0)
    contract = spec.build_contract_symbol("M", 2025)
    return FuturesDailyBar(
        timestamp=datetime.datetime(2025, 6, 17, 21, 0, tzinfo=datetime.timezone.utc),
        open=p,
        high=p + 5.0,
        low=p - 5.0,
        close=p + 2.0,
        volume=100_000,
        open_interest=500_000.0,
        root_symbol=root,
        contract_symbol=contract,
        expiry=spec.expiry_date("M", 2025),
        source="synthetic",
        timezone="America/Chicago",
    )


def check_one(root: str) -> bool:
    """Validate one synthetic bar and print its linked metadata."""
    try:
        spec = get_instrument(root)
        bar = _synthetic_bar(root, spec)
        expiry_links = bar.expiry == spec.expiry_for_symbol(bar.contract_symbol)
        if not expiry_links:
            raise ValueError(
                f"bar expiry {bar.expiry} != spec expiry "
                f"{spec.expiry_for_symbol(bar.contract_symbol)}"
            )
    except Exception as exc:
        print(f"[FAIL] {root}: {type(exc).__name__}: {exc}")
        return False

    print(f"[OK] {bar.root_symbol} / {bar.contract_symbol}")
    print(f"    root_symbol:         {bar.root_symbol}")
    print(f"    contract_symbol:     {bar.contract_symbol}")
    print(f"    name:                {spec.name}")
    print(f"    exchange:            {spec.exchange}")
    print(f"    currency:            {spec.currency}")
    print(f"    contract_multiplier: {spec.contract_multiplier}")
    print(f"    tick_size:           {spec.tick_size}")
    print(f"    tick_value:          {spec.tick_value}")
    print(f"    usd_per_1pt_move:    {spec.contract_multiplier * 1.0:.2f}")
    print(f"    usd_per_1tick_move:  {spec.tick_value:.2f}")
    print(f"    expiry link (bar == spec third-friday): OK ({bar.expiry})")
    return True


def main(roots: list[str] | None = None) -> int:
    roots = roots if roots is not None else DEFAULT_ROOTS
    if not roots:
        print("FAIL: no root symbols to check")
        return 1

    print(f"futures metadata smoke report: {len(roots)} synthetic sample(s)")
    failures = sum(0 if check_one(root) else 1 for root in roots)
    if failures:
        print(f"RESULT: FAIL ({failures}/{len(roots)} sample(s) failed)")
        return 1
    print(f"RESULT: OK ({len(roots)}/{len(roots)} samples validated and linked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
