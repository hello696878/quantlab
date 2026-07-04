# STOP POINT - QuantLab

Date: 2026-07-05 (local futures data path v0.1 stable)

## Project Goal

QuantLab is a long-term multi-market AI quant research platform.

The current direction is:

- futures-first
- preserve existing crypto QuantLab code
- upgrade in-place
- do not start a parallel repo

## Current Phase

QuantLab **local futures data path v0.1 — stable**. The local, synthetic-only
futures data foundation is complete end to end (committed through `3d320f6`).

## Supported Local Workflow (synthetic data only, no network)

```
local CSV
-> validate
-> normalize
-> processed CSV
-> metadata lookup
-> tiny futures report
```

## Current Known Completed Work

- Instruments supported: **ES, NQ, YM, RTY** (config-only additions after ES;
  procedure documented in docs/INSTRUMENTS_LAYER.md section 6).
- Instrument registry validation; specs are frozen/strict with a tick-value
  invariant.
- Per-record futures daily bar schema (backend/app/datastore/daily_bar.py)
  with registry-aware validation.
- Local CSV loader (backend/app/datastore/csv_fixtures.py); synthetic ES/NQ
  fixtures under backend/tests/fixtures/futures_csv/.
- Read-only local CSV workflow scripts:
  - scripts/check_instruments.py — registry smoke check
  - scripts/check_futures_metadata.py — metadata smoke report
  - scripts/run_synthetic_futures_report.py — synthetic mini trade report
  - scripts/check_local_futures_csv.py — validate local CSVs (read-only)
  - scripts/normalize_local_futures_csv.py — validate + one normalized CSV per root
  - scripts/report_local_futures_csv.py — per-root summary of normalized output
- All scripts read local files only; the smoke check and report write nothing,
  the normalizer writes once to its output dir and never mutates inputs; no
  network, no new dependencies.

## Verification Commands

```powershell
C:\quantlab\backend\venv\Scripts\python.exe scripts\check_instruments.py
C:\quantlab\backend\venv\Scripts\python.exe scripts\check_futures_metadata.py
C:\quantlab\backend\venv\Scripts\python.exe scripts\run_synthetic_futures_report.py
C:\quantlab\backend\venv\Scripts\python.exe scripts\check_local_futures_csv.py --path backend\tests\fixtures
C:\quantlab\backend\venv\Scripts\python.exe scripts\normalize_local_futures_csv.py --input backend\tests\fixtures --output-dir backend\tests\_tmp_normalized_futures
C:\quantlab\backend\venv\Scripts\python.exe scripts\report_local_futures_csv.py --input backend\tests\_tmp_normalized_futures
C:\quantlab\backend\venv\Scripts\python.exe -m pytest backend/tests -q
```

Latest results (2026-07-05): every smoke check / report exits 0; full suite
2469 passed. Remove the throwaway `backend\tests\_tmp_normalized_futures`
folder afterward (it is not committed).

## Important Rule

Do not implement these yet:

- ML
- CFDs
- options
- futures_continuous
- real data download (no yfinance, no IBKR)
- production trading
- major backtest engine rewrite

Proceed one tiny commit at a time.

## Next Safe Step

Pick ONE tiny step:

- Design a tiny strategy/report interface that consumes local normalized CSV
  only (no new data source) — specification / documentation first.
- Or: decide the real data source plan (provenance, licensing, adapter shape)
  before any ingestion implementation.

## Risks

- Jumping into ML before the data layer is proven beyond synthetic data.
- Downloading real data before the ingestion plan and provenance rules are settled.
- Rewriting existing crypto code instead of preserving and integrating it.
- Making the platform too broad too early.
