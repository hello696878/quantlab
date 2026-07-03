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

## Now

- (foundation stable — no task in flight)

## Next (pick one tiny step)

- [ ] Connect synthetic futures data into a tiny backtest/report path.
- [ ] Or: design the futures data ingestion plan before touching real data.

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
- Do not download real data.
- Do not rewrite the backtest engine.
