"""
Read-only smoke check for the instrument registry (developer utility).

Lists every instrument in ``configs/instruments/``, loads each spec through
the registry, prints its identity/economics, and re-checks the tick-value
invariant.  Exits 0 if every instrument loads and passes, nonzero otherwise.

Usage (from the repo root):
    backend\\venv\\Scripts\\python.exe scripts\\check_instruments.py

Read-only: never writes or mutates anything.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Make `app.*` importable when run from the repo root (mirrors the
# pythonpath="." pytest setting in backend/pyproject.toml).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.instruments import get_instrument, list_instruments  # noqa: E402


def main() -> int:
    roots = list_instruments()
    if not roots:
        print("FAIL: no instrument specs found in configs/instruments/")
        return 1

    print(f"instrument registry smoke check: {len(roots)} spec(s) found")
    failures = 0
    for root in roots:
        try:
            spec = get_instrument(root)
        except Exception as exc:  # loading IS the validation; report and continue
            print(f"[FAIL] {root}: {type(exc).__name__}: {exc}")
            failures += 1
            continue

        expected = spec.contract_multiplier * spec.tick_size
        tick_ok = math.isclose(spec.tick_value, expected, rel_tol=1e-9, abs_tol=1e-9)
        if not tick_ok:
            failures += 1

        print(f"[{'OK' if tick_ok else 'FAIL'}] {spec.root_symbol}")
        print(f"    name:                {spec.name}")
        print(f"    exchange:            {spec.exchange}")
        print(f"    asset_class:         {spec.asset_class.value}")
        print(f"    currency:            {spec.currency}")
        print(f"    contract_multiplier: {spec.contract_multiplier}")
        print(f"    tick_size:           {spec.tick_size}")
        print(f"    tick_value:          {spec.tick_value}")
        print(
            f"    tick_value == contract_multiplier * tick_size: "
            f"{'OK' if tick_ok else f'FAIL (expected {expected})'}"
        )

    if failures:
        print(f"RESULT: FAIL ({failures}/{len(roots)} instrument(s) failed)")
        return 1
    print(f"RESULT: OK ({len(roots)}/{len(roots)} instruments passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
