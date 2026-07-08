# QuantLab

QuantLab is a long-term multi-market AI quant research platform, being upgraded
in-place: futures-first, while preserving the existing crypto code.

## Current Phase

QuantLab v0.1 foundation (Phase 1: futures-first).

## Status (2026-07-05)

**QuantLab local futures data path v0.1 is stable.** The local, synthetic-only
futures data foundation is complete end to end:

- Instruments supported: **ES, NQ, YM, RTY** (validated, immutable YAML specs).
- Per-record futures daily bar schema with registry-aware validation.
- A read-only local CSV workflow, synthetic data only, no network:

  ```
  local CSV -> validate -> normalize -> processed CSV -> metadata lookup -> tiny futures report
  ```

- Read-only smoke checks and reports all exit 0; full backend suite green
  (2469 passed).

Key files for the local futures data path:

- `backend/app/instruments/` — spec, futures contract, and registry code
- `configs/instruments/` — `es.yaml`, `nq.yaml`, `ym.yaml`, `rty.yaml`
- `backend/app/datastore/daily_bar.py` — per-record futures daily bar schema
- `backend/app/datastore/csv_fixtures.py` — local CSV loader (`load_futures_bars_csv`)
- `scripts/check_instruments.py`, `scripts/check_futures_metadata.py` — registry / metadata smoke checks
- `scripts/check_local_futures_csv.py` — validate local CSVs, read-only
- `scripts/normalize_local_futures_csv.py` — validate + write one normalized CSV per root
- `scripts/report_local_futures_csv.py` — per-root summary of normalized CSV output
- `scripts/run_synthetic_futures_report.py` — synthetic mini trade report
- `docs/INSTRUMENTS_LAYER.md` — instruments layer architecture note
- `docs/FUTURES_DATA_INGESTION_PLAN.md` — how real futures data will enter later (design only)

## Not Allowed Yet

Deliberately out of scope for now:

- ML
- CFDs
- options
- futures_continuous
- real data download (no yfinance, no IBKR)
- production trading
- major backtest engine rewrite

## Verification

```powershell
backend\venv\Scripts\python.exe scripts\check_instruments.py
backend\venv\Scripts\python.exe scripts\check_futures_metadata.py
backend\venv\Scripts\python.exe scripts\run_synthetic_futures_report.py
backend\venv\Scripts\python.exe scripts\check_local_futures_csv.py --path backend\tests\fixtures
backend\venv\Scripts\python.exe scripts\normalize_local_futures_csv.py --input backend\tests\fixtures --output-dir backend\tests\_tmp_normalized_futures
backend\venv\Scripts\python.exe scripts\report_local_futures_csv.py --input backend\tests\_tmp_normalized_futures
backend\venv\Scripts\python.exe -m pytest backend/tests -q
```

The two CSV commands write only to `backend\tests\_tmp_normalized_futures`, a
throwaway folder that is not committed; delete it afterward
(`Remove-Item -Recurse -Force backend\tests\_tmp_normalized_futures`).

## Research CLI Quickstart

Run the synthetic ES ML experiment demo from Windows PowerShell. **This is a
synthetic ES demo, not real market performance.** It runs the full Phase 1→6
pipeline — raw synthetic futures → continuous futures → features → labels → ML
evaluation → experiment registry — and prints `train_run_hash`, metrics,
`artifact_dir`, and a reproduce command.

```powershell
cd C:\quantlab\backend

.\venv\Scripts\python.exe -m app.research_cli.cli run --artifacts-dir ..\artifacts\experiments --overwrite
.\venv\Scripts\python.exe -m app.research_cli.cli list --artifacts-dir ..\artifacts\experiments
.\venv\Scripts\python.exe -m app.research_cli.cli best --artifacts-dir ..\artifacts\experiments --metric sharpe
```

The `run` and `list` subcommands have equivalent direct wrapper scripts:

```powershell
.\venv\Scripts\python.exe .\scripts\run_es_ml_experiment.py --artifacts-dir ..\artifacts\experiments --overwrite
.\venv\Scripts\python.exe .\scripts\list_experiments.py --artifacts-dir ..\artifacts\experiments
```

Artifacts are written under `artifacts/experiments/` and are gitignored. To
compare runs, pass real `train_run_hash` values taken from the `list` output:

```powershell
.\venv\Scripts\python.exe -m app.research_cli.cli compare <train_run_hash_a> <train_run_hash_b> --artifacts-dir ..\artifacts\experiments
```

## Web App Labs

The Next.js frontend (`frontend/`) ships a set of educational research labs on
deterministic static sample data (see `docs/PROJECT_OVERVIEW.md` and
`docs/LIMITATIONS.md`). The five recent labs — Crypto Derivatives, DeFi Risk,
Tokenomics, On-Chain Analytics, and Alternative Data — include **interactive
scenario-shock sliders, horizon selectors, and local recharts panels** (31.5):
every control is a deterministic client-side transform of the static sample
re-sent to the existing analyze endpoints — no live data, no trading, not
investment advice.

The **Unified Scenario Studio & Cross-Lab Report Builder** (32.0) connects the
recent labs through a documented deterministic impact-scoring layer: ten
scenario templates, global shock sliders, module impact charts, a scenario
heatmap, a regime read, and a copy-friendly generated Markdown report — all
static sample data, educational summaries only, no live data, not investment,
trading, or allocation advice, and not a production risk report.

The **Research Workspace, Saved Presets & Experiment Journal** (33.0) organizes
deterministic sample lab runs into six saved research packs: an experiment
journal with staged runs, baseline-vs-stressed comparisons, severity /
coverage / reproducibility scores, a workflow timeline, a methodology
checklist, and copy-friendly Markdown/JSON exports, plus optional
browser-local drafts (localStorage only — no login, no cloud sync, no
database). Hand-written static samples, educational summaries only — not
production research or compliance records, not investment or trading advice.

The **Product Demo Center, Guided Walkthroughs & Module Health Dashboard**
(34.0) is a product-UX layer for showcasing the platform: eight guided demo
paths with per-step deep links, an audience/time-budget-aware demo script
builder (copyable Markdown/JSON), a 21-module health dashboard with status
and data-mode badges, and a capability matrix with readiness / coverage /
complexity scores. Hand-written static demo metadata — no telemetry, no
login, no cloud sync, no live data, generated scripts are educational
summaries, not investment or trading advice, and no module is a production
trading system.

The **Data Mode Registry, Offline Fixtures & API Reliability Center** (35.0)
explains how every module sources data: a 20-module data-mode registry, a
provider registry (the optional yfinance/FRED/delayed-quote paths are
disabled by default, fail closed, and are never relied on in tests), an
offline fixture registry (including the KO/PEP pairs-demo fallback that keeps
the built-in pairs demo network-free), documented reliability rates and
score, and a copyable Markdown/JSON reliability report. Hand-maintained
static metadata — tests never depend on live providers, default demos have
deterministic fallbacks, external availability is never guaranteed, and it is
not a production data governance system.

## Project Docs

- [TASKS.md](TASKS.md) — current task list
- [LOG.md](LOG.md) — work log
- [STOP_POINT.md](STOP_POINT.md) — latest checkpoint and next safe step

## Workflow

One tiny, tested commit at a time. Inspect first, change the smallest safe
thing, run the relevant tests, then record the result here and in LOG.md.
