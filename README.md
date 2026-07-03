# QuantLab

QuantLab is a long-term multi-market AI quant research platform, being upgraded
in-place: futures-first, while preserving the existing crypto code.

## Current Phase

QuantLab v0.1 foundation (Phase 1: futures-first).

## Status (2026-07-03)

**QuantLab foundation is stable.** The futures foundation round is complete:

- Instruments supported: **ES, NQ, YM, RTY** (validated, immutable YAML specs).
- Instrument validation hardened; registry test suite passes (31 tests).
- Per-record futures daily bar schema with synthetic tests (11 tests).
- Read-only smoke checks pass: instrument registry and futures metadata.
- Full backend suite green: 2416 passed.

Key files for the foundation:

- `backend/app/instruments/` — spec, futures contract, and registry code
- `configs/instruments/` — `es.yaml`, `nq.yaml`, `ym.yaml`, `rty.yaml`
- `backend/app/datastore/daily_bar.py` — per-record futures daily bar schema
- `backend/tests/test_instruments_registry.py` — registry test suite
- `backend/tests/test_futures_daily_bar.py` — daily bar schema tests
- `docs/INSTRUMENTS_LAYER.md` — instruments layer architecture note

## Not Allowed Yet

Deliberately out of scope for now:

- ML
- CFDs
- options
- futures_continuous
- real data download
- major backtest engine rewrite

## Verification

```powershell
backend\venv\Scripts\python.exe scripts\check_instruments.py
backend\venv\Scripts\python.exe scripts\check_futures_metadata.py
backend\venv\Scripts\python.exe -m pytest backend/tests -q
```

## Project Docs

- [TASKS.md](TASKS.md) — current task list
- [LOG.md](LOG.md) — work log
- [STOP_POINT.md](STOP_POINT.md) — latest checkpoint and next safe step

## Workflow

One tiny, tested commit at a time. Inspect first, change the smallest safe
thing, run the relevant tests, then record the result here and in LOG.md.
