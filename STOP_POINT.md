# STOP POINT - QuantLab

Date: 2026-09-08 (Phase 64 implementation: Strategy Return Stream,
Similarity and Portfolio Ensemble Diagnostics Lab v1)
Evidence finalized: 2026-09-10, using the user's existing full-run records.
Independent review handoff: 2026-09-13; see `docs/PHASE_64_REVIEW.md`.
Security patch handoff: 2026-09-15; see `docs/PHASE_64_SECURITY_REMEDIATION.md`.
Independent security/runtime review: 2026-09-16; use the appended handoff in that report.

This replaces the stale 2026-07-05 "local futures data path v0.1" stop
point, which no longer described the repository (the futures track later
gained ingestion, continuous contracts, a local backtest pipeline, an ML
signal loop and an experiment catalog; Phases 48–61 added the fourteen-lab
product-workflow diagnostics chain).

## Current repository goal

QuantLab is a **local-first, deterministic, educational** quant research
platform: 58 routed top-level view identifiers over a FastAPI + SQLite backend and a
Next.js 15 frontend (security patch), plus a local futures research pipeline (local CSV
only). Not investment advice; no live trading; no production
trading/risk/compliance certification.

## Current version and phase state

| Field | Value |
|---|---|
| VERSION | `4.82.0-dev` |
| Latest completed feature phase | 61.0 — Signal Ensemble, Redundancy & Combination Diagnostics Lab v1 |
| Phase 61 commits | `c0f256d` (Add) / `40ec1fd` (Review) |
| Latest tag | `v4.81.0-frontend-component-test-foundation-registry-drift-guards-v1` |
| Current phase | 64.0; implementation `1284b3115977f057f4690f643601dc329aac7797`, review `9d169edb4fbb66022d3643b31457fdecee3189e2`; security patch uncommitted |
| Current branch | `main` |
| Phase 62 implementation | `e50cca2` (`Add master blueprint reconciliation project status audit roadmap v1`) |
| Phase 62 review/tag state | Review `ceb5c41` and v4.80 tag exist |
| Phase 63 implementation | `0d1c903` |
| Phase 63 review/tag state | Review `0eceda6` and v4.81 tag exist; inherited security findings remain in `docs/PHASE_64_REVIEW.md` |
| Phase 64 verification | Base review SHA CI backend/frontend success, not this patch. Fresh Node 24.20.0/npm 11.17.0 strict install, 166 frontend tests, TypeScript, 275-test discovery and zero-finding full/production audits passed. Node 24 runtime/action declarations aligned; user build/browser, Docker verification and final-patch CI remain. Historical full 4,359 / 3 skips remains separate. |

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

1. Read `docs/PHASE_64_SECURITY_REMEDIATION.md` for the current patch's exact
   changed paths, supported-runtime follow-up and user-only build/browser commands.
   The earlier review commit exists; preserve the uncommitted security patch and index.
2. Targeted patch review/runtime alignment is complete. Run the user-owned
   production build, token-verified disposable browser checks, Docker verification
   and final-patch CI before release. Preserve active data and prior evidence; do not rerun
   a full backend suite or start another evidence-finalization loop for this patch.
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
