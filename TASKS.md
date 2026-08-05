# TASKS - QuantLab

Reconciled at Phase 62.0 (2026-08-05). The sections below reflect the
repository's ACTUAL state; the historical futures-checkpoint records are
preserved at the bottom because they document real completed work.

## Current phase

- **Phase 62.0 — Master Blueprint Reconciliation, Project Status Audit
  and Forward Roadmap v1** (documentation/status phase; no product code
  changes).
- Current branch: `main`.
- Implementation commit: `e50cca2` —
  `Add master blueprint reconciliation project status audit roadmap v1`.
- Expected review commit:
  `Review master blueprint reconciliation project status audit roadmap v1`.
- Expected tag (user-created after review, never automatic):
  `v4.80.0-master-blueprint-reconciliation-project-status-roadmap-v1`.
- VERSION: `4.80.0-dev`.

## Where the platform actually stands (evidence-audited)

- Latest completed feature phase: **61.0 — Signal Ensemble, Redundancy &
  Combination Diagnostics Lab v1** (commits `c0f256d` / `40ec1fd`, tag
  `v4.79.0-signal-ensemble-redundancy-combination-diagnostics-v1`).
- The Phase 48–61 product-workflow chain (Experiment Registry → Dataset
  Lineage → Model Validation → Meta-Labeling → Feature → Overfitting →
  Regime → Cost → Portfolio → Stress → Attribution → Factor → Signal
  Decay → Signal Ensemble) is built, routed, tested and documented.
- The LOCAL FUTURES RESEARCH TRACK went far beyond the old "v0.1"
  checkpoint recorded here previously: instruments registry, datastore
  with ingestion + continuous-contract building (`futures_continuous`),
  a local futures backtest + pipeline, a feature/label/ML-signal loop,
  and an experiment catalog/audit/review + evidence-pack CLI all exist
  (see `docs/BLUEPRINT_STATUS_MATRIX.md` for file-level evidence). The
  old "Do not implement ML / futures_continuous" rules were superseded
  by those phases and are recorded as history, not current policy.

## Now (Phase 62 tasks)

- [x] Read governing docs and inspect repository reality (git log/tags/
      branches, backend modules, frontend workspaces, e2e specs).
- [x] Evidence audit of the 20 blueprint phase-order areas and 12 model
      categories (no status without file-level evidence).
- [x] Create `docs/BLUEPRINT_STATUS_MATRIX.md`,
      `docs/BLUEPRINT_RECONCILIATION_REPORT.md`,
      `docs/FORWARD_ROADMAP_PHASES_63_70.md`.
- [x] Reconcile `TASKS.md` (this file), `STOP_POINT.md`, `LOG.md`,
      `docs/MASTER_BLUEPRINT_V3.md`, `docs/ROADMAP.md`,
      `docs/PROJECT_SNAPSHOT.md`, `docs/VERSION_MANIFEST.md`,
      `CHANGELOG.md`, `VERSION`.
- [x] Implementation verification recorded: 4,268 passed, 4 environment-
      sensitive failures, 3 skipped; typecheck clean; Playwright discovery only.
- [x] Codex review corrections and verification: unsupported counts and
      status claims corrected; focused environment-failure classification,
      TypeScript check and Playwright discovery recorded. The attempted
      current-workspace full backend rerun exceeded the 65-minute command
      timeout and is not claimed green.
- [ ] User: create the review commit, complete final local/CI verification,
      and only then create the v4.80 tag manually.

## Next (selected Phase 63–70 roadmap)

See `docs/FORWARD_ROADMAP_PHASES_63_70.md` for full scope, dependencies,
acceptance criteria and non-scope. Sequence:

1. **Phase 63** — Frontend Component Test Foundation and Registry Drift
   Guards v1 (selected next phase).
2. **Phase 64** — Strategy Return Stream, Strategy Similarity and
   Portfolio Ensemble Diagnostics Lab v1.
3. **Phase 65** — Unified ML Research Lifecycle and Model Artifact
   Registry v1.
4. **Phase 66** — Reproducible Run Replay by Hash and Environment
   Manifest v1.
5. **Phase 67** — Futures Point-in-Time Data Contract, Calendar
   Foundation and Adapter Specification v1.
6. **Phase 68** — Advanced Cross-Sectional Neutralisation and Scanner
   Validation v1.
7. **Phase 69** — Deterministic Evidence-Grounded Research Explainer v1.
8. **Phase 70** — Read-Only Hosted Demo and Deployment Hardening Plan v1.

## Deliberate non-goals (standing)

- No live trading, broker/exchange/wallet integration, or real-money
  order execution — ever, by positioning.
- No automatic investment recommendations, signal/strategy selection, or
  position sizing.
- No paid data providers or API-key management outside the explicit
  opt-in, fail-closed adapters that already exist (disabled by default).
- No authentication / multi-user hosting in the current phase sequence
  (Phase 70 PLANS a read-only hosted demo; auth and multi-user isolation
  remain deferred and are not silently added).
- No production trading/risk/compliance certification claims.

---

## Historical record (real completed work; wording preserved)

### Done (2026-07-03, foundation stable)

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

### Done (2026-07-04)

- [x] Design the futures data ingestion plan before touching real data
      (docs/FUTURES_DATA_INGESTION_PLAN.md — design only, no code).
- [x] Ingestion Phase 1 (I1), commit 1: synthetic CSV fixture loader
      (backend/app/datastore/csv_fixtures.py, incl. plan-§6 registry
      cross-checks) + ES/NQ fixtures (backend/tests/fixtures/futures_csv/)
      + 14 tests. Full suite: 2441 passed.

### Done (2026-07-05, local futures data path v0.1 stable)

- [x] Local CSV smoke check (scripts/check_local_futures_csv.py).
- [x] Local CSV normalizer (scripts/normalize_local_futures_csv.py).
- [x] Local futures CSV report (scripts/report_local_futures_csv.py)
      + backend/tests/test_report_local_futures_csv.py (10 tests).
      Full suite: 2469 passed.
- [x] Mark the local futures data path v0.1 stable (README, STOP_POINT, LOG).

### Done (after 2026-07-05; recorded here at Phase 62 for accuracy)

- [x] Futures ingestion + RawFuturesStore (backend/app/datastore/ingest.py,
      store.py) and continuous-contract building
      (backend/app/datastore/futures_continuous.py, continuous_build.py;
      scripts/build_local_continuous_futures.py).
- [x] Local futures backtest + pipeline (backend/app/futures_backtest,
      backend/app/local_pipeline) and buy/hold report script.
- [x] Feature/label/ML-signal loop over local futures data
      (backend/app/features, labels, ml_signal, signals;
      scripts/run_local_futures_ml_experiment.py, run_local_futures_ml_batch.py).
- [x] Experiment catalog/audit/review + evidence packs
      (backend/app/experiments, experiment_catalog, experiment_audit,
      experiment_review, batch_experiments, research_cli;
      scripts/build_experiment_evidence_pack.py).
- [x] Phases 48–61 product-workflow diagnostics chain (see docs/ROADMAP.md).
