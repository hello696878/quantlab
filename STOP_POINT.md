# STOP POINT - QuantLab

Date: 2026-09-08 (Phase 64 implementation: Strategy Return Stream,
Similarity and Portfolio Ensemble Diagnostics Lab v1)
Evidence finalized: 2026-09-10, using the user's existing full-run records.

This replaces the stale 2026-07-05 "local futures data path v0.1" stop
point, which no longer described the repository (the futures track later
gained ingestion, continuous contracts, a local backtest pipeline, an ML
signal loop and an experiment catalog; Phases 48–61 added the fourteen-lab
product-workflow diagnostics chain).

## Current repository goal

QuantLab is a **local-first, deterministic, educational** quant research
platform: 58 routed top-level view identifiers over a FastAPI + SQLite backend and a
Next.js 14 frontend, plus a local futures research pipeline (local CSV
only). Not investment advice; no live trading; no production
trading/risk/compliance certification.

## Current version and phase state

| Field | Value |
|---|---|
| VERSION | `4.82.0-dev` |
| Latest completed feature phase | 61.0 — Signal Ensemble, Redundancy & Combination Diagnostics Lab v1 |
| Phase 61 commits | `c0f256d` (Add) / `40ec1fd` (Review) |
| Latest tag | `v4.81.0-frontend-component-test-foundation-registry-drift-guards-v1` |
| Current phase | 64.0 (strategy return streams and fixed-weight diagnostics; locally implemented, uncommitted) |
| Current branch | `phase64-strategy-return-stream-ensemble` |
| Phase 62 implementation | `e50cca2` (`Add master blueprint reconciliation project status audit roadmap v1`) |
| Phase 62 review/tag state | Review `ceb5c41` and v4.80 tag exist |
| Phase 63 implementation | `0d1c903` |
| Phase 63 review/tag state | Review `0eceda6` and v4.81 tag verified in local history; historic security notes in `docs/PHASE_63_REVIEW.md` not re-audited here |
| Phase 64 verification | `docs/PHASE_64_IMPLEMENTATION.md`; combined backend snapshot: 4,359 passed, 3 platform skips, pytest process exit 0; outer runner exit not recorded; build/browser/CI/independent review pending |

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

1. Read `docs/PHASE_64_IMPLEMENTATION.md` and the Phase 64 runbook; inspect Git
   diff without overwriting the uncommitted implementation.
2. Read `docs/BACKEND_TEST_MAINTENANCE.md`: the four former safety failures and
   nine encoding failures now pass in the user's full run. No test rerun is
   needed for this evidence-only handoff. User performs isolated browser/build
   verification and requests independent review; final CI/security gates remain.
   Do not delete active data or unrelated evidence.
3. User alone creates commits/push/tag after reviewing gates. No Phase 65 work
   is authorized. Existing historical dependency-security notes remain relevant.

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
  phase sequence (Phase 70 plans and locally hardens a read-only demo mode; it does not deploy anything).
- No production trading/risk/compliance certification claims anywhere.
