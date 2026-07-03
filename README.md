# QuantLab

QuantLab is a long-term multi-market AI quant research platform, being upgraded
in-place: futures-first, while preserving the existing crypto code.

## Current Phase

QuantLab v0.1 foundation (Phase 1: futures-first).

## Status (2026-07-03)

- ES futures instrument spec layer reviewed.
- Instrument validation hardened.
- `backend/tests/test_instruments_registry.py`: 22 tests passed.

Key files for the instruments layer:

- `backend/app/instruments/` — spec, futures contract, and registry code
- `configs/instruments/es.yaml` — ES instrument definition
- `backend/tests/test_instruments_registry.py` — registry test suite

## Not Allowed Yet

Deliberately out of scope for now:

- ML
- CFDs
- options
- futures_continuous
- major backtest engine rewrite

## Running Tests

```powershell
backend\venv\Scripts\python.exe -m pytest backend\tests\test_instruments_registry.py
```

## Project Docs

- [TASKS.md](TASKS.md) — current task list
- [LOG.md](LOG.md) — work log
- [STOP_POINT.md](STOP_POINT.md) — latest checkpoint and next safe step

## Workflow

One tiny, tested commit at a time. Inspect first, change the smallest safe
thing, run the relevant tests, then record the result here and in LOG.md.
