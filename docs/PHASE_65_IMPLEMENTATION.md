# Phase 65 Implementation Report

Implementation completed, 2026-09-29. Ready for a separate independent review;
not a release, production certification, or independent-review verdict.

## Baseline

- Repository: `hello696878/quantlab`; clean `main` at
  `1591f89931f6534d523c96a87231bcd9d680080a` before work.
- Frozen tag `v4.82.0-strategy-return-stream-similarity-portfolio-ensemble-diagnostics-v1`
  resolves to that exact commit. User-supplied inherited CI `35739957842`
  succeeded in both jobs. No Phase 64 verification is rerun here.
- Created authorized branch `phase65-unified-ml-lifecycle-artifact-registry`
  from that commit. The first branch command was denied by the filesystem
  sandbox; the authorized retry succeeded. Index was empty; no work overwritten.
- No staging, commits, pushes, tags, providers, services, local builds or Phase 66.

## Source and Adapter Map (Before Implementation)

| Source | Actual persisted inputs / public interface | Destination / conversion | Missing information and verification limit |
|---|---|---|---|
| ExperimentStore | `ExperimentRun`, safe numeric `model_params`, metrics, CSV/Parquet prediction/signal/backtest frames; configuration hashes, ordered feature names and date ranges | Explicit operator import; preserve upstream hashes, physical bytes and normalized table identities | No feature matrix, exact training membership, calibrator, verified OOF mapping or historical environment by default. Legacy imports remain incomplete; no retraining on import. |
| Experiment catalog / audit / review | Public metadata catalog, structural artifact audit and evidence packs | Inspect existing conventions; add strict local containment before reading selected files | Existing configuration hashes and structural audit are not content authenticity or OOF proof. No scanning beyond the explicit source run. |
| Features / labels / local pipeline | Trailing feature builder, forward label builder, supervised dataset, `train_model`, `predict_model`, `prediction_to_signal`, cost-aware futures evaluation | Demo calls the existing numerical implementations; map full timestamp + instrument keys to retained split IDs | Prediction adapter is unshifted. Backtest alone owns execution lag. Labels mature after decisions; availability is recorded separately. |
| Dataset Registry | Existing version/content/manifest fingerprint, invalidation, schema and provenance | Require existing compatible version and pin its material content; demo explicitly owns its synthetic version | A declared source fingerprint is not proof of historical training provenance. Missing binding is refused. |
| Model Validation | `normalize_samples`, splitters, interval purge, embargo and independent `audit_split`; persisted split memberships | Exact sample IDs and closed information intervals; save genuine fold/model mappings | A leakage-clean audit alone does not prove predictions were produced OOF. |
| Meta-Labeling | Public Platt/isotonic fit/apply and probability diagnostics; explicit primary-side/outcome semantics | Frozen calibration fitted only to inner OOF predictions; held-out probability diagnostics as a separate record | Up-vs-rest probability becomes a meta-label probability only for an explicitly long primary side and matching outcome threshold. No outer-label calibration. |
| Feature Diagnostics | Actual feature vectors, binary targets, declared or validation-linked splits; diagnostic estimator refit | Pass the same ordered feature matrix and retained train/test membership | Refitted diagnostic model is separate from the stored ML estimator; never infer importance from prediction scores. |
| Cost Diagnostics | Gross trade/period inputs, explicit turnover and fee assumptions | Derived from actual held-out evaluation positions/returns; retain gross and net separately | Modeled cost reference is not a second deduction or a fill estimate. No turnover inferred from scores. |
| Signal Decay | Explicit entity/timestamp, signal availability, horizon and price/return target contracts | Held-out probabilities as a named signal with fixed direction/horizon and pinned cost context | No favorable horizon selection; descriptive diagnostics are not causal profit claims. |
| Strategy Ensemble / Experiment Registry | Immutable inputs, additive SQLite, pinned linked content, explicit actions | Reuse lifecycle, route, navigation and identity conventions | Strategy-stream export is optional; predictions are not strategy returns. General replay remains Phase 66. |

## Architecture and Delivered Scope

The new `app/ml_lifecycle` package owns canonical identities, safe local import,
snapshot validation, two additive SQLite tables, explicit service adapters and
one deterministic demo. Existing estimators, feature/label builders, splitters,
calibration, futures backtest and diagnostic calculations are reused unchanged.
Only the new table initializer and router are added to shared backend files.

ExperimentStore remains the filesystem producer. The operator CLI previews one
explicit run without writes; registration requires an explicit destination DB
and an existing compatible Dataset Registry version. The browser/API never
accepts server paths. Legacy imports are stored snapshots, not executable models
or claims of complete training provenance. No provider, network data, automatic
retraining, model promotion, Phase 66 replay or new estimator family was added.

The API exposes bounded list/detail, explicit registration/link/demo actions,
strict JSON export and neutral comparison under `/ml-lifecycles`; the frontend
uses `/api/ml-lifecycles`. Read-only calls never execute downstream labs. The
workspace is registered in the existing View/component/Sidebar/Command Palette
system and supports `/?view=mllifecycle`, separate status dimensions, filters,
provenance tables, linked detail and export. Its only mutating UI action is the
explicit synthetic demo button. Comparison has no winner or promotion score.

## Identity, Persistence and Safety

- Schema-versioned SHA-256 identities distinguish source/configuration,
  dataset-version binding, ordered feature/label specs, split memberships, each
  fitted model, calibration, predictions, evaluation and source environment.
  Existing upstream configuration and `train_run_hash` values remain unchanged.
- Typed tables preserve ordered columns, scalar types and nulls, sort on full
  instrument/timestamp keys and reject duplicates, ambiguous times and nonfinite
  values. File-byte hashes are separate from semantic identities. Import time,
  temporary paths and DB row IDs are not semantic model content.
- Source-training environment is separate from inspection environment. Legacy
  training environment remains unknown. The allowlist excludes usernames,
  environment variables, tokens and unrestricted package inventories.
- Import accepts only bounded JSON and CSV/optional Parquet, with strict
  filenames, ancestry/reparse/hardlink checks, opened-file identity checks and
  repeat reads to detect mutation. No pickle, executable class deserialization,
  formula execution or artifact-controlled imports are present.
- Immutable snapshots and parameterized SQL use two additive, idempotently
  initialized tables. Dataset bindings and material downstream child rows are
  rechecked, not trusted solely because an advertised hash matches. Changed or
  invalidated provenance blocks strict export/comparison and adapter execution.
- Duplicate registration/demo loading is idempotent. A failed adapter retry
  reuses its owned destination. Multi-service work is not globally atomic;
  failures remain visible. A crash leaving `running` needs operator inspection,
  not a guessed automatic retry.

Detailed policies: [registry contract](MODEL_ARTIFACT_REGISTRY.md) and
[workflow/import runbook](ML_RESEARCH_LIFECYCLE.md).

## Actual Demo and Adapter Acceptance

The fixture uses seed 650, 220 synthetic ES daily bars, existing return(20) and
MA-gap(10,50) features in that order, and existing direction(1)/forward-return(1)
labels. Warmup and outcome-context handling leave 169 eligible samples. The
last 32 form the chronological outer holdout. All split memberships are fixed
before fitting, using existing closed-interval purge and two-day embargo rules.
Four inner logistic fits produce model-linked OOF predictions. Existing sigmoid
calibration fits those inner OOF probabilities only. One final logistic fit uses
retained outer training samples; calibration and threshold 0.5 stay frozen for
the outer holdout. Thus five distinct model artifacts are retained, not one
model falsely credited with every prediction. No profitability criterion exists.

| Required adapter | Implemented and exercised | Limit retained in metadata/UI |
|---|---|---|
| Model Validation | Same sample IDs and intervals; actual destination split membership checked against the final fit | Independent split audit does not itself prove OOF; per-fold generating-model evidence is retained separately |
| Meta-Labeling | Held-out frozen calibrated probabilities, explicit long primary side and zero outcome threshold; destination calibration `none` | Destination `raw_probability` is adapter input, not original raw model output; no held-out refit or false OOF label |
| Feature Diagnostics | Actual ordered X/y and retained outer split; existing permutation service | Separate diagnostic logistic refit, not importance manufactured from predictions or the original estimator's parameters |
| Cost Diagnostics | Actual gross period returns and effective-position turnover, explicit 10 bps / 10000 reference notional | Original net returns/compounded drag retained separately; modeled linear fees are not charged twice |
| Signal Decay | Actual held-out calibrated scores, full entity/time/availability keys, source prices, fixed horizon 1 / entry lag 1 and pinned cost link | One-entity descriptive diagnostics, no favorable horizon selection or cross-sectional-alpha claim |

The end-to-end fresh-schema test creates the actual owned dataset/version and
all five diagnostic records, verifies completeness/integrity, reloads without
duplicate links, and exports/compares the stored lifecycle. Legacy snapshots
cannot execute these adapters because feature matrices, exact memberships and
calibration evidence are absent. The optional Phase 64 strategy-stream link is
not implemented; predictions are not mislabeled strategy returns.

### Timing and Validation Limits

Existing label semantics are `close[t+2] / close[t+1] - 1`. Existing backtest
semantics are `position[t] = target[t-1]` applied to `close[t] / close[t-1] - 1`.
These differ and are explicitly documented, not silently conflated or changed.
The prediction target is unshifted; only the engine applies execution lag.
Probability quality refers to the declared label horizon, not every PnL period.

Tests verify held-out-label mutation leaves fitted models, calibration parameters
and threshold unchanged; trailing features are prefix invariant. Negative cases
cover missing/mismatched/invalidated dataset versions, missing features, feature
order, false OOF, invalid availability, duplicate predictions, changed membership,
outer samples in calibration, source mutation and linked-child-row tampering.
Full completion is reserved for the internally generated linked demo in v1;
external legacy registration remains explicitly incomplete/unverified.

## Newly Executed Verification

No Phase 64 CI/build/browser/security evidence is counted as Phase 65 execution.
The inherited CI result in Baseline is supplied history, not a fresh check.

Backend runtime: `C:\quantlab\backend\venv\Scripts\python.exe`, Python 3.13.5
(Anaconda), pytest 9.0.3, numpy 2.4.6, pandas 3.0.3, scipy 1.17.1, Pydantic 2.13.4.
The protected runner uses independent snapshot/test-owned databases, with real
schema initialization exercised by the fresh-schema test. Pure checks are
`db_free`. No active application database was initialized or migrated.

Commands executed from the repository root:

```powershell
.\scripts\run_backend_tests.ps1 -Scope focused -Tests backend/tests/test_ml_lifecycle.py,backend/tests/test_ml_lifecycle_import.py
.\scripts\run_backend_tests.ps1 -Scope full
.\scripts\run_backend_tests.ps1 -Scope focused -Tests backend/tests/test_ml_lifecycle_import.py
```

Exactly one full regression was run, after the main implementation stabilized,
because shared schema initialization and router registration changed. It was not
concurrent with another suite/build/browser. The user interrupted the conversation
while it ran; the existing process completed and its evidence was recovered on
resume. It was not restarted.

Evidence roots below are under `C:\Users\jimli\AppData\Local\Temp\` and retained
outside Git. Durations in the table are instrumented pytest wall / total runner
wall seconds, not sums of test-phase timings.

| Run directory | Scope/result | Pytest / total seconds | Pytest / outer exit |
|---|---|---|---|
| `quantlab-backend-focused-dqzss7wx` | Final pre-full phase checks: 46 passed, 2 skipped; 48 selected | 50.393 / 71.504 | 0 / 0 |
| `quantlab-backend-full-wa650chc` | Full: 4502 passed, 5 skipped; 4507 selected across 144 files, 0 deselected | 2489.702 / 2509.174 | 0 / 0 |
| `quantlab-backend-focused-h3073rlo` | Post-full importer correction: 33 passed, 2 skipped; 35 selected | 3.177 / 16.361 | 0 / 0 |

All three report `completed`, complete child evidence, unchanged active DB,
unchanged source snapshot and unchanged worktree during execution. Snapshot
setup / test-process wall seconds respectively: 4.301 / 52.033; 6.993 / 2494.771;
4.930 / 4.516. Terminal pytest summaries were 50.20s, 2489.80s and 2.93s; those
are distinct from the runner's instrumented wall clocks above.

The focused pre-full and full runs have identical `snapshot-manifest.json`
SHA-256, covering 1088 files, no missing/omitted files, baseline HEAD `1591f899...`:

```text
9aa0264b9a2bfc8261bf731b2043744ae29156938f773b984dea921f283b1533
```

The post-fix importer snapshot-manifest SHA-256 is:

```text
0614e86271c2a81edb993e9f5eb10ca49ee6df2bbc445b9b190e57cbde24392d
```

The full run predates the final Parquet correction: pandas conversion could turn
NaN into null before validation. The importer now reads Arrow Python scalars
directly, preserving null versus nonfinite values. Five focused decoder-boundary
cases cover null, finite numbers, NaN and both infinities. Only `importer.py` and
`test_ml_lifecycle_import.py` differed from the full snapshot before final docs
updates, verified across its file hashes. **This is a full pre-fix pass plus a
post-fix targeted pass, not a second full run or a claimed full final-tree pass.**

The two phase skips are missing optional pyarrow and OS refusal to create a real
fixture symlink. Hardlink and simulated reparse-point refusals did execute. The
Parquet scalar-boundary test stubs the optional decoder; real Parquet parsing
remains unexecuted locally. Full regression also skipped three pre-existing
symlink cases in experiment audit/review. No skipped case is counted as passed.

### Earlier Development Attempts (Preserved, Not Acceptance Evidence)

All directories below share prefix `quantlab-backend-focused-` in the same temp
root. Their retained manifests identify each earlier source snapshot. Main means
`-Tests backend/tests/test_ml_lifecycle.py`; import means the importer file;
both means the comma-separated two-file command above.

| Suffix | Scope | Result | Pytest / total seconds | Pytest / outer exit | Cause/status |
|---|---|---|---|---|---|
| `e1ubgr_d` | main | 2 passed, 1 failed | 17.391 / 50.747 | 1 / 1 | Timezone-aware/naive conversion corrected |
| `3nvugmmh` | main | 2 passed, 1 failed | 2.304 / 23.373 | 1 / 1 | NumPy fitted parameters converted at trusted JSON boundary |
| `svksw9sd` | main | 2 passed, 2 failed | 9.141 / 27.586 | 1 / 1 | NumPy metrics converted at trusted JSON boundary |
| `ydtavsim` | main | 3 passed, 1 failed | 7.250 / 29.573 | 1 / 1 | Reused supported `fixture://` dataset locator |
| `t23b6rqf` | main | 4 passed | 22.802 / 45.178 | 0 / 0 | Interim narrower tests only |
| `5h6j80gm` | both | 38 passed, 3 failed | 60.544 / 89.932 | 1 / 1 | Windows lstat/fstat ctime mismatch investigated |
| `fcy37qas` | import | 21 passed, 4 failed | 2.486 / 29.270 | 1 / 1 | Same mismatch confirmed; handle ctime checked against itself |
| `w7_juouy` | import | 25 passed | 2.387 / 23.952 | 0 / 0 | Interim importer pass before later cases |
| `t3mzpct7` | both | 43 passed, 2 skipped | 55.355 / 78.359 | 0 / 2 | **Protection failed:** worktree edited during run; not a clean pass |

For `t3mzpct7`, active DB and snapshot remained unchanged; only the worktree
protection failed. Its PowerShell tool invocation reported nonzero (1), while
the retained outer runner records 2. The later stable run supersedes it for
acceptance, not history. Initial wrong relative test-path invocation was rejected
before collection (exit 1); the first sandbox attempt (`taer6cof`) hit a temp
permission error before tests (exit 1, incomplete evidence). Neither is a pass.

### Frontend Verification

Supported executable actually used:
`C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\df473e5367fa2b42\bin\node.exe`
**v24.21.0**. npm executable entry:
`C:\Users\jimli\AppData\Roaming\npm\node_modules\npm\bin\npm-cli.js`, **11.17.0**.
The older global Node was not used. PATH was changed only for child commands;
no runtime/dependency/workflow files were changed or packages installed.

From `frontend`, with `$node` bound to the executable above:

```powershell
& $node node_modules/typescript/bin/tsc --noEmit --incremental false
& $node node_modules/vitest/vitest.mjs run
& $node node_modules/@playwright/test/cli.js test --project=chromium --list
```

- TypeScript: exit 0, no diagnostics; precise total duration was not retained.
- Vitest: **17 files / 178 tests passed**, exit 0, reported duration **26.39s**.
  Includes 9 lifecycle component cases and 3 disposable-backend proof guards.
  Initial sandbox startup failed with `spawn EPERM` before collection; the
  authorized retry succeeded. That startup failure is not a test failure/pass.
- Chromium discovery: **276 tests / 20 files listed**, exit 0, tool wall **6.499s**.
  This is discovery only. The new spec was not executed in a browser.
- Frontend sources have not changed since these checks. No production build,
  dev server, actual browser test, Docker build, dependency audit or CI run was
  performed in this task. Frontend build was not run in Codex by instruction.
  Please run it locally.

## Remaining Gates and Bounded Readiness

Safe to keep as a bounded local research implementation and **ready for separate
independent review**, with the evidence limitations above. Not release-approved,
production model serving, security certification or proof of investment merit.

The independent session should review the actual diff, especially containment,
sample/membership identities, calibration class semantics, downstream pins and
the final Parquet correction. Actual optional-pyarrow roundtrip and physical
symlink tests need a suitable environment; none was installed/enabled here.
The final whole-tree full regression was not rerun after the importer patch.

User production build and real browser checks remain gates. The focused browser
spec covers navigation, explicit demo, provenance, linked detail, empty/refusal,
comparison/export and 1440/1024/768 overflow checks, but is **not an observed UI
pass**. The `scripts.ml_lifecycle_e2e:create_app` factory extends the existing
disposable backend, checking actual DB path/inode/token/SQLite connection on
every lifecycle request; both proxy handshakes precede mutation. See the
[manual runbook](ML_RESEARCH_LIFECYCLE.md#manual-verification-gates). Do not run
mutating browser checks against the ordinary application DB.

## Exact Changed-File Inventory

36 paths: 12 modified tracked files and 24 new files. No staged paths. This is
the explicit implementation scope, not authorization to execute this document.

```text
README.md
STOP_POINT.md
TASKS.md
VERSION
backend/app/db.py
backend/app/main.py
backend/app/ml_lifecycle/__init__.py
backend/app/ml_lifecycle/adapters.py
backend/app/ml_lifecycle/demo.py
backend/app/ml_lifecycle/identity.py
backend/app/ml_lifecycle/importer.py
backend/app/ml_lifecycle/models.py
backend/app/ml_lifecycle/service.py
backend/app/ml_lifecycle/store.py
backend/app/ml_lifecycle/validation.py
backend/app/ml_lifecycle_routes.py
backend/tests/test_ml_lifecycle.py
backend/tests/test_ml_lifecycle_import.py
docs/FORWARD_ROADMAP_PHASES_63_70.md
docs/ML_RESEARCH_LIFECYCLE.md
docs/MODEL_ARTIFACT_REGISTRY.md
docs/PHASE_65_IMPLEMENTATION.md
docs/VERSION_MANIFEST.md
frontend/e2e/ml-lifecycle.spec.ts
frontend/e2e/mlLifecycleIsolation.ts
frontend/src/app/page.tsx
frontend/src/components/AppShell.tsx
frontend/src/components/MLLifecyclePanel.test.tsx
frontend/src/components/MLLifecyclePanel.tsx
frontend/src/components/Sidebar.tsx
frontend/src/lib/mlLifecycle.ts
frontend/src/lib/mlLifecycleLink.ts
frontend/src/lib/workspaceRegistry.ts
frontend/src/test/mlLifecycleIsolation.test.ts
scripts/import_ml_lifecycle.py
scripts/ml_lifecycle_e2e.py
```

### User-Only Git Plan

Review these exact paths and any later independent-review changes before staging.
Use explicit literal paths, never blanket staging of data/artifacts. Future user
implementation commit: `Add unified ml research lifecycle model artifact registry v1`.
Separate review commit: `Review unified ml research lifecycle model artifact registry v1`.
Future user tag: `v4.83.0-unified-ml-lifecycle-model-artifact-registry-v1`.
No such commit/tag is created here. The index stays empty and HEAD stays at the
verified baseline; the frozen v4.82 tag is preserved. No push, PR, workflow,
release, deploy or Phase 66 action is authorized by this handoff.

Final read-only hygiene checks **passed**:

- Exact report inventory versus pending paths: 36/36, 12 modified and 24 new,
  with no missing/extra paths; no forbidden data/generated paths in that set.
- `git diff --check` and `git diff --cached --check`: exit 0. Each new file was
  also checked with `git diff --no-index --check -- NUL <path>`: no whitespace
  diagnostics (exit 1 for a new-file difference is expected, not a test failure).
- Staged count 0; branch and HEAD unchanged from Baseline. Frozen v4.82 tag still
  resolves to `1591f89931f6534d523c96a87231bcd9d680080a`.
- No screenshot, dependency, runtime, workflow or governing-file changes.
  Existing LF/CRLF warnings remain; Git line-ending configuration was not changed.
- File hashes versus the final focused snapshot differ only for `STOP_POINT.md`,
  `TASKS.md`, this report and `docs/FORWARD_ROADMAP_PHASES_63_70.md`. Executable code
  matches that tested snapshot. Documentation completion is not misrepresented
  as part of the earlier immutable test snapshots.

No staging, commit, push, tag, PR, service startup, release/deploy or Phase 66 work
occurred. No second evidence-finalization task is needed for this implementation
handoff; independent review and the explicitly unexecuted user gates remain.
