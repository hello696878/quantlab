# STOP POINT - QuantLab

Date: 2026-08-05 (Phase 62.0 — Master Blueprint Reconciliation, Project
Status Audit and Forward Roadmap v1)

This replaces the stale 2026-07-05 "local futures data path v0.1" stop
point, which no longer described the repository (the futures track later
gained ingestion, continuous contracts, a local backtest pipeline, an ML
signal loop and an experiment catalog; Phases 48–61 added the fourteen-lab
product-workflow diagnostics chain).

## Current repository goal

QuantLab is a **local-first, deterministic, educational** quant research
platform: ~40 interactive workspaces over a FastAPI + SQLite backend and a
Next.js 14 frontend, plus a local futures research pipeline (local CSV
only). Not investment advice; no live trading; no production
trading/risk/compliance certification.

## Current version and phase state

| Field | Value |
|---|---|
| VERSION | `4.80.0-dev` |
| Latest completed feature phase | 61.0 — Signal Ensemble, Redundancy & Combination Diagnostics Lab v1 |
| Phase 61 commits | `c0f256d` (Add) / `40ec1fd` (Review, = `main` HEAD) |
| Latest tag | `v4.79.0-signal-ensemble-redundancy-combination-diagnostics-v1` |
| Current phase | 62.0 (documentation/status audit — this phase) |
| Current branch | `phase62-blueprint-reconciliation-roadmap-audit` |
| Phase 62 review/tag state | implementation not yet committed; review pending; expected tag `v4.80.0-master-blueprint-reconciliation-project-status-roadmap-v1` (user-created after review, never automatic) |

## Protected frozen release baseline

`v4.60.0-public-release-candidate-demo-freeze-v1` (demo freeze) and the
post-release baseline `v4.64.0-public-github-release-launch-v1`
(`docs/POST_RELEASE_BASELINE_v4.64.md`): the frozen demo route, the five
`docs/screenshots/release_*.png`, the Scenario Studio severe-stress
outputs (severity 100.0/100, 8/8 modules), the KO/PEP pairs fixture
(119 trade events, −23.0% vs +112.7%), the checksum manifests and the
Browser E2E guard. Frozen tags are never moved; fixture outputs never
change silently.

## Known documentation/tag gaps (recorded, not repaired)

- Phase 58's expected tag `v4.76.0-portfolio-performance-attribution-benchmark-diagnostics-v1`
  was never created (commits `e354d76`/`ad8679e` are on `main`).
- The v4.69 meta-labeling tag was never created (work is inside the
  `v4.70.0` tag's history). Both are recorded convention deviations;
  history is not rewritten and tags are not created retroactively.
- Full audit: `docs/BLUEPRINT_RECONCILIATION_REPORT.md` §tag-audit.

## Next safe step

1. User reviews and commits this phase
   (`Add master blueprint reconciliation project status audit roadmap v1`),
   then runs the Codex review pass, then creates the v4.80 tag manually.
2. The selected next implementation phase is **Phase 63 — Strategy
   Return Stream, Strategy Similarity and Portfolio Ensemble Diagnostics
   Lab v1** (`docs/FORWARD_ROADMAP_PHASES_63_70.md`). Do not begin it
   inside Phase 62.

## Exact restart commands

```powershell
cd C:\quantlab
git status -sb
git log -10 --oneline --decorate

# Backend dev server
cd C:\quantlab\backend
venv\Scripts\uvicorn app.main:app --reload --port 8000

# Frontend dev server (user-run)
cd C:\quantlab\frontend
npm run dev

# Full backend suite (backend venv carries pytest)
cd C:\quantlab
backend\venv\Scripts\python.exe -m pytest backend\tests -q

# Frontend typecheck
cd C:\quantlab\frontend
npx tsc --noEmit
```

## Explicit non-goals (standing)

- No live trading, broker/exchange/wallet integration, or real-money
  execution — deliberate non-goal by positioning.
- No automatic investment recommendations, strategy/signal selection or
  position sizing.
- No paid providers / API-key management beyond the existing opt-in,
  fail-closed, disabled-by-default adapters.
- No authentication, multi-user hosting or cloud sync in the current
  phase sequence (Phase 70 plans a read-only hosted demo SPEC only).
- No production trading/risk/compliance certification claims anywhere.
