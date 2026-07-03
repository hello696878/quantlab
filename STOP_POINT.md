# STOP POINT - QuantLab

Date: 2026-07-03

## Project Goal

QuantLab is a long-term multi-market AI quant research platform.

The current direction is:

- futures-first
- preserve existing crypto QuantLab code
- upgrade in-place
- do not start a parallel repo

## Current Phase

QuantLab v0.1 foundation (Phase 1: futures-first).

## Current Known Completed Work

- ES futures instrument layer reviewed.
- Instrument validation hardened (commit 35c3255).
- Relevant files:
  - backend/app/instruments/* (base.py, futures.py, registry.py)
  - configs/instruments/es.yaml
  - backend/tests/test_instruments_registry.py
- Latest test result:
  - test_instruments_registry.py: 22 passed.

## Important Rule

Do not implement these yet:

- ML
- CFDs
- options
- futures_continuous
- major backtest engine rewrite

Proceed one tiny commit at a time.

## Next Safe Step

Either of these tiny documentation-only steps:

- Write a short architecture note for the instruments layer.
- Add docs explaining how to add a new futures instrument later.

## Risks

- Jumping too quickly into ML before data/instrument layer is stable.
- Rewriting existing crypto code instead of preserving and integrating it.
- Making the platform too broad too early.
