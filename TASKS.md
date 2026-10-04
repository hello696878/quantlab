# TASKS - QuantLab

## Current Phase 65 Platform Verification (2026-10-01)

Reviewed on `main` at implementation `1449db23744f1d03743df189f5fa063df286802e`, based on frozen Phase 64
`1591f89931f6534d523c96a87231bcd9d680080a`. The v4.82 tag exists at that commit;
exact documentation CI `35739957842` is inherited user-supplied passing evidence.
Review is committed at `291b0f424716ec336548b3b5648008e6a78a4613` on `main`.
VERSION remains `4.83.0-dev`; no v4.83 tag/release is created here.

- [x] Add immutable snapshots, safe importer, explicit diagnostic adapters and linked synthetic demo.
- [x] Add read-only lifecycle workspace, API, component tests and guarded browser specification.
- [x] Record exact verification in `docs/PHASE_65_IMPLEMENTATION.md`: full pre-final-importer-fix run 4502 passed / 5 skipped; post-fix importer 33 passed / 2 skipped, all protection checks pass.
- [x] Frontend: 178 unit tests, TypeScript and 276-test Chromium discovery pass (discovery is not browser execution).
- [x] Independent source review and verified-defect corrections; see `docs/PHASE_65_REVIEW.md` for current focused results and limits.
- [x] Exact-review-commit CI `36675720804`: both jobs succeeded; backend 4568 passed / 18 unspecified skips in 706.07s. Retained, not rerun.
- [x] User production build and one isolated Edge ML Lifecycle scenario passed; retained, not rerun or expanded into a 276-test execution claim.
- [x] Disposable Linux/Python 3.11.16/PyArrow 22.0.0 importer verification: 69 passed / 1 Windows-only junction skip, all exits 0; real codec and physical-link coverage executed. See the dated post-review section of `docs/PHASE_65_REVIEW.md`.
- [ ] User review, documentation-only commit/publication and verification; then user-only future v4.83 tag.
- Phase 66 remains unstarted. No staging, commit, push, tag, deployment, application services or user DB changes. Task-owned verification containers are separate from application services.

## Historical Phase 64 Handoff (Superseded)

The following handoff was updated for Phase 64 final release evidence (2026-09-20).
The Phase 62 audit, futures checkpoints and earlier Phase 64 evidence remain
historical. This documentation finalization reruns no tests or release checks.

### Phase 64 State at That Handoff

- Phase 64: Strategy Return Stream, Strategy Similarity and Portfolio Ensemble
  Diagnostics Lab v1. Branch `main`; implementation
  `1284b3115977f057f4690f643601dc329aac7797`, parent `0eceda6`.
  VERSION `4.82.0-dev`; independent review committed as
  `9d169edb4fbb66022d3643b31457fdecee3189e2`. Security patch, verified HEAD and
  origin/main: `36f70e6b72800f0ab585afa8c873f4b87c09aeff`.
- Phase 63 implementation `0d1c903`, review `0eceda6` and v4.81 tag exist.
- [x] Implement supplied return-stream contract, diagnostics, fixed weights,
  persistence, pinned links, API, frontend and deterministic demo/tests.
- [x] Recover completed full-suite output; preserve active DB and artifacts.
- [x] Add policies/runbook and record checks in `docs/PHASE_64_IMPLEMENTATION.md`.
- [x] Historical implementation evidence: repaired combined backend run, 4,359 passed + 3 platform
  skips = 4,362 tests, pytest process exit 0; all recorded protection checks pass.
  Outer runner final exit was not recorded. Historical failures remain history.
- [x] Reconcile exact snapshot hashes and collection IDs; prepare user-only
  combined commit commands without staging. See `docs/BACKEND_TEST_MAINTENANCE.md`.
- [x] Independent Codex review and verified-defect fixes: `docs/PHASE_64_REVIEW.md`.
- [x] Historical exact review-commit CI completed successfully (run `34814054179`, backend
  and frontend jobs); this does not cover the later dependency patch.
- [x] Bounded dependency remediation: strict-peer npm ci, 166 frontend tests,
  TypeScript, 275-test discovery and full/production audits completed. See
  `docs/PHASE_64_SECURITY_REMEDIATION.md` for advisory limits and exact evidence.
- [x] Historical 2026-09-16 targeted independent patch review and Node 24 CI/Docker alignment.
  Fresh Node 24.20.0/npm 11.17.0 checks: strict-peer install, 166 frontend tests,
  TypeScript, 275-test discovery, full/production audits (zero reported findings).
  The first unit command was sandbox-blocked before collection; permitted run passed.
- [x] User production build: Node 24.20.0/npm 11.17.0, Next.js 15.5.25,
  exit 0; frontend started on `127.0.0.1:3100`.
- [x] User isolated browser verification: actual Microsoft Edge (`msedge`
  channel, `chromium` project); 21 Strategy Ensemble + 12 frozen/responsive
  checks passed, zero failed/skipped, both exits 0. Disposable backend identity
  verified through the frontend proxy before both stages. Not all 275 discovered tests.
- [x] Exact security-patch CI run `35064846132`: Backend Tests and Frontend
  Tests & Build both completed/success at `36f70e6b72800f0ab585afa8c873f4b87c09aeff`.
  Frontend Node 24 LTS install, component tests, TypeScript and build succeeded.
- [x] Docker `quantlab-frontend:phase64-v482`: pull/build/image export and
  Next.js 15.5.25 runtime/root/proxy isolation verification passed using Node
  v24.21.0. This is not browser-suite execution inside Docker.
- [x] Independent final documentation review (2026-09-21); content-only checks
  and read-only retrieval of the existing exact-security-commit CI record.
- [ ] User documentation commit, publication and verification of that commit;
  the security-patch CI does not cover it. Suggested subject:
  `Finalize phase64 release evidence and documentation v1`.
- [ ] Only afterward, user creation of
  `v4.82.0-strategy-return-stream-similarity-portfolio-ensemble-diagnostics-v1`.
- Full evidence and limits:
  [final release verification](docs/PHASE_64_SECURITY_REMEDIATION.md#final-release-verification-2026-09-20).
  The completed gates do not call for another test/build/browser/Docker loop.
- Named inherited dependency findings were remediated in committed patch
  `36f70e6`; full/production audits reported zero findings at the recorded point.
  This is not security/trading certification, deployment or full browser coverage.
- The final review authorizes explicit staging of the approved documentation
  only; no commit, push, tag, services or test execution. Phase 65 has not
  started. Earlier findings remain dated historical evidence.

## Historical Phase 62 handoff

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

## Historical Phase 62 platform snapshot (evidence-audited)

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

## Historical Phase 62 tasks

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
   Guards v1 (implementation/review commits and tag exist).
2. **Phase 64** — Strategy Return Stream, Strategy Similarity and
   Portfolio Ensemble Diagnostics Lab v1 (implementation/review/security patch
   committed; final verification evidence recorded; documentation review/commit
   and verification precede the still-pending user tag).
3. **Phase 65** — Unified ML Research Lifecycle and Model Artifact
   Registry v1 (planned, not started).
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
