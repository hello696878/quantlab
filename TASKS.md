# TASKS - QuantLab

## Done (2026-07-03, foundation stable)

- [x] Confirm current git status.
- [x] Confirm ES instrument spec layer is clean (reviewed).
- [x] Harden instrument validation.
- [x] Write short architecture note for the instruments layer
      (docs/INSTRUMENTS_LAYER.md, incl. how to add a new futures instrument).
- [x] Add NQ futures instrument config + tests.
- [x] Add YM futures instrument config + tests.
- [x] Add RTY futures instrument config + tests.
- [x] Add read-only instrument registry smoke check (scripts/check_instruments.py).
- [x] Add per-record futures daily bar schema + synthetic tests
      (backend/app/datastore/daily_bar.py).
- [x] Add read-only futures metadata smoke report (scripts/check_futures_metadata.py).
- [x] Confirm tests pass (registry: 31; daily bar: 11; full suite: 2416 passed).

## Done (2026-07-04)

- [x] Design the futures data ingestion plan before touching real data
      (docs/FUTURES_DATA_INGESTION_PLAN.md — design only, no code).
- [x] Ingestion Phase 1 (I1), commit 1: synthetic CSV fixture loader
      (backend/app/datastore/csv_fixtures.py, incl. plan-§6 registry
      cross-checks) + ES/NQ fixtures (backend/tests/fixtures/futures_csv/)
      + 14 tests. Full suite: 2441 passed.

## Done (2026-07-05, local futures data path v0.1 stable)

- [x] Local CSV smoke check (scripts/check_local_futures_csv.py) — validate
      local CSVs through the I1 loader; per-file + per-symbol summaries; writes
      nothing (I2 read-only precursor).
- [x] Local CSV normalizer (scripts/normalize_local_futures_csv.py) — validate
      all inputs, then write one canonical-column CSV per root (sorted,
      round-trips through the loader); inputs never modified.
- [x] Local futures CSV report (scripts/report_local_futures_csv.py) — read
      normalized per-root output, look up metadata, print a tiny one-contract
      first-close->last-close P&L per root (direct == tick-based); read-only.
      + backend/tests/test_report_local_futures_csv.py (10 tests).
      Full suite: 2469 passed.
- [x] Mark the local futures data path v0.1 stable (README, STOP_POINT, LOG).

## Now

- (local futures data path v0.1 stable — no task in flight)

## Next (pick one tiny step)

- [ ] Design a tiny strategy/report interface over local normalized CSV only
      (no new data source) — specification / documentation first.
- [ ] Or: decide the real data source plan (provenance, licensing, adapter
      shape) before any ingestion implementation.
- [ ] Or: I1 commit 2 — round-trip the fixture bars through RawFuturesStore
      (write_raw to a temp dir, read back, assert equality + stable version
      hash), plan §9.

## Later

- futures_continuous (CL/GC need an ExpiryRule extension first — see
  docs/INSTRUMENTS_LAYER.md section 6)
- synthetic ES experiment pipeline
- ML signal loop
- AI report
- dashboard polish

## Do Not Do Yet

- Do not implement ML.
- Do not implement CFDs.
- Do not implement options.
- Do not implement futures_continuous.
- Do not download real data (no yfinance, no IBKR).
- Do not start production trading.
- Do not rewrite the backtest engine.
