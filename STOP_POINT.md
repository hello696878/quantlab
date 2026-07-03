# STOP POINT - QuantLab

Date: 2026-07-03 (foundation stable)

## Project Goal

QuantLab is a long-term multi-market AI quant research platform.

The current direction is:

- futures-first
- preserve existing crypto QuantLab code
- upgrade in-place
- do not start a parallel repo

## Current Phase

QuantLab foundation — **stable**. The foundation optimization round is
complete (committed through `72d9c82`).

## Current Known Completed Work

- Instruments supported: **ES, NQ, YM, RTY** (config-only additions after ES;
  procedure documented in docs/INSTRUMENTS_LAYER.md section 6).
- Instrument validation hardened; specs are frozen/strict with a tick-value
  invariant.
- Per-record futures daily bar schema (backend/app/datastore/daily_bar.py)
  with registry-aware validation, synthetic tests only.
- Read-only smoke checks: scripts/check_instruments.py and
  scripts/check_futures_metadata.py.
- Relevant files:
  - backend/app/instruments/* (base.py, futures.py, registry.py)
  - configs/instruments/ (es.yaml, nq.yaml, ym.yaml, rty.yaml)
  - backend/app/datastore/daily_bar.py
  - backend/tests/test_instruments_registry.py (31 passed)
  - backend/tests/test_futures_daily_bar.py (11 passed)
  - docs/INSTRUMENTS_LAYER.md

## Verification Commands

```powershell
C:\quantlab\backend\venv\Scripts\python.exe scripts\check_instruments.py
C:\quantlab\backend\venv\Scripts\python.exe scripts\check_futures_metadata.py
C:\quantlab\backend\venv\Scripts\python.exe -m pytest backend/tests -q
```

Latest results (2026-07-03): both smoke checks exit 0; full suite 2416 passed.

## Important Rule

Do not implement these yet:

- ML
- CFDs
- options
- futures_continuous
- real data download
- major backtest engine rewrite

Proceed one tiny commit at a time.

## Next Safe Step

Pick ONE of these tiny steps:

- Connect synthetic futures data into a tiny backtest/report path.
- Or: design the futures data ingestion plan (documentation only) before
  touching real data.

## Risks

- Jumping too quickly into ML before the data layer is proven on synthetic data.
- Downloading real data before the ingestion plan and provenance rules exist.
- Rewriting existing crypto code instead of preserving and integrating it.
- Making the platform too broad too early.
