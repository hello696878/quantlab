# TASKS - QuantLab

## Current Phase 70 Independent Review (2026-10-18)

Attached `main`, implementation `8860ce7bdfb20367debdaf9e36b9ea3900dea0f9`,
tree `614027cba879ec6abfda3fc1ef48ceab411973b6`, single parent/frozen Phase 69
tag target `1062ec48b4128af867ab5a3329951511ebff285c`. VERSION stays `4.88.0-dev`.
Review began clean. Phase 69 CI/evidence remains inherited, not Phase 70 acceptance.

- [x] Strict operator factory, six-route early refusal, offline synthetic corpus and capability-gated existing UI implemented; hosting remains a plan.
- [x] Independently inspect all 39 implementation paths and shared startup/storage/provider/runner/container contracts; correct seven verified defects.
- [x] New 51 backend regressions; final affected protected scope 219 passed/zero skips, pytest/child/outer exits 0/0/0. Inherited 357/168 snapshots remain separate.
- [x] Add six stale-state frontend cases: 283 passed/28 files; TypeScript passed; discovery 1/280, no browser execution. Preserve the initial esbuild setup failure.
- [x] Single review handoff: 16 intended paths, unstaged; current docs finalized after executable verification.
- [ ] Later user staging/commit decision, exact-review-commit Python 3.11 whole-tree CI.
- [ ] User production build and private BACKEND_URL route-manifest verification.
- [ ] One isolated prepared-corpus browser acceptance; discovery is not execution.
- [ ] Hardened image/non-root/read-only mounts/resource/ingress runtime verification before any hosting.

See [review findings/inventory](docs/PHASE_70_REVIEW.md), historical
[implementation evidence](docs/PHASE_70_IMPLEMENTATION.md) and
[operations/limits](docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md).
No staging, commit, push, tag, PR, deployment, service or Phase 71 is authorized.

## Historical Phase 69 Final Evidence (2026-10-18, Frozen at 1062ec48)

Verified frozen Phase 68 main/base `2cd8f2585816fda0dc389f5a721ab02b0a3d71d8`,
tree `2c3dfde47bfb4c6924e7ab807727fc3d104de8ab` and annotated v4.86 tag.
Implementation branch was `phase69-deterministic-evidence-grounded-research-explainer`;
implementation is `ff7a288baa56ba61cb58d0de3aba524ec7a441cf`; review is committed
on `main` at `4c59abd1c0cc655f7efe78a7bae423acdef4b0a8`.
VERSION remains `4.87.0-dev`. Supplied successful final-doc CI `38533560143` is inherited.

- [x] Map actual saved-result, replay and lifecycle read contracts and units.
- [x] Implement bounded read-only stored-SMA acquisition and recorded-integrity checks; no backfill or research on read.
- [x] Add closed versioned facts/wording/policy, independent binding validation and deterministic identity/hash.
- [x] Integrate explicit explanation, references, changed/legacy/unavailable states and pinned export into Saved detail.
- [x] Real engine/save/read fixture and adversarial tests: earlier broad330 / final affected73 passes on separate snapshots; 251 frontend passes, TypeScript passed, browser discovery1/279 only.
- [x] Preserve development failures, frozen evidence/tag, active data and empty index; no installations/builds/services/browser execution.
- [x] Independent review and verified fixes; final focused backend 410 passed/zero skips, frontend 258 passed, TypeScript passed, discovery1/279 only. Failed/inherited snapshots remain distinct.
- [x] Implementation and independent review committed; earlier local checkpoints above remain historical.
- [x] Existing exact-review CI `39017836732` succeeded in both jobs: Python 3.11.17, backend 5144 passed /18 unidentified skips; not rerun or reclassified.
- [x] User production build exit 0 and one isolated Edge Explainer scenario passed; retained JUnit has 1 case, no failures/errors/skips. Earlier no-listener preflight remains separate.
- [x] Separate verified Linux/Python 3.11.17 execution: five authorized physical-link nodes passed once, zero skips/failures/errors; earlier Docker/archive setup stops retained.
- [x] Resolve inherited security wording against historical Phase 64 remediation; preserve current support/security limitations, no new audit.
- [ ] User documentation commit/publication/verification and user-created v4.87 milestone tag.

See [final evidence](docs/PHASE_69_REVIEW.md#final-release-evidence-and-platform-verification-2026-10-18),
[implementation inventory/evidence](docs/PHASE_69_IMPLEMENTATION.md) and
[support/runbook](docs/EVIDENCE_GROUNDED_RESEARCH_EXPLAINER.md).
Only existing allowlisted documentation staging is authorized; no commit, push,
tag, PR, deployment, workflow trigger or Phase 70.

## Historical Phase 68 Final Evidence (2026-10-14, Frozen at 2cd8f258)

Attached `main`, review HEAD `094d04263ecd713c3cc2f733b36969a513d21c3d`,
tree `5b767c968cc8b95b501f6f8a711a3cf3e4b55b99`; implementation
`5428eb20ae7c1dc33c2e875a1e33370e2423568b`, frozen Phase 67 baseline
`e23e828952c1dd1dcc320a225e75a0337aa1fd80`; verified annotated
v4.85 tag, supplied successful final-doc CI `38219121957`. VERSION `4.86.0-dev`.

- [x] Inspect real scanner, Phase 59 OLS, Phase 52 purge/audit and Phase 53 corrections.
- [x] Add explicit policies, keyed declarations, residualisation and final-weight checks.
- [x] Add bounded volatility/cash fallback and reuse the scanner's single P&L kernel.
- [x] Link actual fixed-policy selections to purged samples/folds and declared p-values.
- [x] Extend Scanner UI with explicit actions, stale-response guards and synthetic caveats.
- [x] Independent adversarial review and narrow verified-defect fixes; 70 new backend regressions are included in the review total.
- [x] Protected review: 321 passed / zero skips / 321 selected, all exits 0; 245 frontend unit passes, TypeScript exit 0 and browser discovery (1 focused / 278 overall). Earlier 250/74 implementation runs remain separate; no whole-tree backend or browser execution claim.
- [x] Review committed at `094d04263ecd713c3cc2f733b36969a513d21c3d`.
- [x] Exact-review CI `38496359420`, attempt 1: both jobs successful (user/coordinator-supplied, not retrieved here; no inferred counts/patch versions).
- [x] User production build exit 0 and one selected Edge Scanner scenario; retained JUnit confirms 1 passed, zero failures/errors/skips. Earlier DIRECT preflight failure remains separate, root cause unknown.
- [ ] User documentation commit/publication/verification and user-created v4.86 milestone tag; Phase 69 not started.

Only existing allowed documentation is staged in this finalization task;
no tests/builds/browser/API computations rerun, commit, push, tag, provider,
new database, services or Phase 69.
See [Phase 68 review](docs/PHASE_68_REVIEW.md) and preserved
[implementation handoff](docs/PHASE_68_IMPLEMENTATION.md).

## Historical Phase 67 Platform Evidence (2026-10-12, Closed at e23e8289)

Attached `main`, review HEAD `92498c531e2a2864b40eb6a0c669b39a4760311a`,
implementation `66aa3da7eb79ce6b1f07000e90d1dc930b65df41`,
parent/frozen baseline `008760c46564839500e6108db84d8ffebab3f875`;
VERSION `4.85.0-dev` unchanged.
Verified v4.84 tag at baseline; user-reported exact-doc CI `37482126828` is inherited.

- [x] Audit actual futures/local-ingest/store/continuous/registry/provider boundaries.
- [x] Implement bounded immutable contracts, revisions/as-of and declared calendar/DST.
- [x] Add explicit legacy-compatible calendar roll mode, diagnostics and local CLI.
- [x] Add invented acceptance corpus and independent focused backend assertions.
- [x] Independent adversarial review and narrow verified-defect fixes.
- [x] Protected review regression: 375 passed, 1 physical-symlink privilege skip, 376 selected, exits 0; protection checks passed. Implementation runs remain separate historical evidence.
- [x] User review commit `92498c53...`; supplied exact-commit CI `38208475431`, both jobs success; backend 4849 passed / 18 unidentified skips in 561.39s. Not rerun; skip identities remain unknown.
- [x] Separate disposable Linux/Python 3.11.17 five-node run: 5 passed, zero skips/failures/errors; actual physical symlink/importer refusal, real DST and timezone-provenance cases executed once.
- [ ] User documentation commit/publication and verification of that exact documentation revision.
- [ ] User-created v4.85 milestone tag after documentation publication; no Phase 68.

No provider, official calendar, frontend, application services, code/test/VERSION
change, commit/push/tag or Phase 68. Only the authorized documentation diff is staged.
See [Phase 67 review](docs/PHASE_67_REVIEW.md) and the preserved
[implementation handoff](docs/PHASE_67_IMPLEMENTATION.md).

## Historical Phase 66 Final Release Evidence (2026-10-06, Superseded)

Branch `main`, base HEAD `5760b3b37f92f4f0193498a0a6bb48da2c61d20b`;
VERSION remains `4.84.0-dev`. Implementation `b7bb0252...`, independent review
`9e0a0b5f...` and the acceptance-spec correction at base HEAD are committed.

- [x] Add separate replay-input/environment/saved-execution/result identities and indexed configuration hashes.
- [x] Add bounded read-only resolver, explicit legacy registration, safe SMA adapter and local-data demo.
- [x] Connect Saved Backtests, confirmation, explicit restoration, original/effective settings and guarded browser specification.
- [x] Add deterministic migration, persistence, API, mapping and component tests.
- [x] Preserve inherited implementation evidence: focused backend 91 passed / 0 skipped; frontend 208 tests, TypeScript and 277-test discovery passed (discovery only).
- [x] Independent source review, verified defect fixes and adversarial regressions; `docs/PHASE_66_REVIEW.md` records the exact inventory and limits.
- [x] Review executions: 203 focused backend passes, then 76 affected passes on the corrected snapshot; final frontend 227 tests, TypeScript and 277-test discovery passed. No new whole-tree backend or browser execution claim.
- [x] Inspect existing exact-implementation CI `37274152339` read-only: both jobs success, backend 4611 passed / 18 unspecified skips. This predates reviewer fixes.
- [x] Exact-patch CI `37417645417`: both jobs completed successfully at `5760b3b3...`; metadata independently retrieved read-only, no inferred full-suite count or skip reasons.
- [x] User-owned production build at `9e0a0b5f...`: exit 0; reused unchanged for the corrected browser spec, not rebuilt at the patch SHA.
- [x] User-owned isolated Microsoft Edge acceptance: one corrected scenario passed, exit 0; dual proxy proof passed and initial saved-row count was zero. Earlier failures preserved.
- [x] Finalize existing documentation and stage only its reviewed exact diff; no verification reruns.
- [ ] User documentation commit/publication, exact-documentation-commit verification and future user tagging.

See [final evidence and attribution](docs/PHASE_66_REVIEW.md#12-final-release-verification-2026-10-06).
The review's 25-path inventory and the implementation's 38-path inventory are
historical, not the current documentation staging list. SMA-only restore and
config-only/deferred module limits remain; no full-browser-suite claim.
No Phase 67, services, commit, push or tag is authorized by this handoff.

## Historical Phase 65 Platform Verification (2026-10-01, Superseded)

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
