# Phase 65 Independent Adversarial Review

Date: 2026-09-30. Scope: Unified ML Research Lifecycle / Model Artifact Registry v1.

The reviewed implementation is safe to keep with the corrections below. The
pending changes are ready for a user review commit, subject to reviewing this
handoff and its limitations. This is not release readiness: final exact-commit
CI, the user production build and isolated browser execution remain pending.
No full backend regression was run during this review.

## 1. Exact target and authorization

- Repository: `C:\quantlab`; branch `main`, attached throughout.
- HEAD: `1449db23744f1d03743df189f5fa063df286802e`.
- Subject: `Add unified ml research lifecycle model artifact registry v1`.
- Parent: `1591f89931f6534d523c96a87231bcd9d680080a`.
- Frozen tag `v4.82.0-strategy-return-stream-similarity-portfolio-ensemble-diagnostics-v1`
  resolves to that parent.
- Initial index, unstaged changes and nonignored untracked set were all empty.
- VERSION remains `4.83.0-dev`. No branch switch, staging, commit, push, tag,
  PR, workflow trigger, deployment, service, Docker, local production build,
  actual browser execution or Phase 66 work occurred.
- Governing `AGENTS.md` and `CLAUDE.md`, implementation/registry/lifecycle
  contracts, forward roadmap, data provenance policy, runner/fixtures and
  frontend registry/browser guidance were read. The explicit Phase 65 request
  authorizes this bounded review despite older MVP-only roadmap wording.
  Governing files and frozen Phase 64 documentation were not rewritten.

The complete committed implementation diff was verified: **36 paths, 12 modified
and 24 added, 2,843 insertions and 9 deletions**. This inventory describes HEAD
relative to its parent, not the pending review changes:

```text
M README.md
M STOP_POINT.md
M TASKS.md
M VERSION
M backend/app/db.py
M backend/app/main.py
A backend/app/ml_lifecycle/__init__.py
A backend/app/ml_lifecycle/adapters.py
A backend/app/ml_lifecycle/demo.py
A backend/app/ml_lifecycle/identity.py
A backend/app/ml_lifecycle/importer.py
A backend/app/ml_lifecycle/models.py
A backend/app/ml_lifecycle/service.py
A backend/app/ml_lifecycle/store.py
A backend/app/ml_lifecycle/validation.py
A backend/app/ml_lifecycle_routes.py
A backend/tests/test_ml_lifecycle.py
A backend/tests/test_ml_lifecycle_import.py
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/ML_RESEARCH_LIFECYCLE.md
A docs/MODEL_ARTIFACT_REGISTRY.md
A docs/PHASE_65_IMPLEMENTATION.md
M docs/VERSION_MANIFEST.md
A frontend/e2e/ml-lifecycle.spec.ts
A frontend/e2e/mlLifecycleIsolation.ts
M frontend/src/app/page.tsx
M frontend/src/components/AppShell.tsx
A frontend/src/components/MLLifecyclePanel.test.tsx
A frontend/src/components/MLLifecyclePanel.tsx
M frontend/src/components/Sidebar.tsx
A frontend/src/lib/mlLifecycle.ts
A frontend/src/lib/mlLifecycleLink.ts
M frontend/src/lib/workspaceRegistry.ts
A frontend/src/test/mlLifecycleIsolation.test.ts
A scripts/import_ml_lifecycle.py
A scripts/ml_lifecycle_e2e.py
```

## 2. Confirmed findings and corrections

Original references in this table are line numbers at implementation HEAD.
Current references identify the correction or regression. P1 means a material
integrity failure; P2 means a functional or trust-boundary defect; P3 is a
coverage/reporting gap. These are confirmed source defects with targeted
regressions, not claims of observed exploitation against user data.

| Priority | Finding and original evidence | Correction and regression evidence |
|---|---|---|
| P1 | Dataset binding trusted stored `content_fingerprint`/`manifest_fingerprint`, even if actual schema, statistics or provenance changed without updating them (`service.py:30,39,55`). | `backend/app/ml_lifecycle/service.py:20` hashes actual dataset/version metadata and rejects an inactive parent; `store.py:22` adds a nullable material pin. `backend/tests/test_ml_lifecycle_review.py:35` mutates five real stored fields while retaining advertised hashes and verifies strict export/compare refusal. Missing pins fail closed; existing rows are preserved. |
| P1 | Child integrity omitted actual Feature Diagnostics samples (`adapters.py:42`), cost observations beyond the default 25 (`:45`), and calibration observations beyond the destination's capped page (`:39`). Recursive removal of `id`/`created_at` also hid nested scientific metadata, while runtime `started_at` contaminated the hash. | `backend/app/ml_lifecycle/adapters.py:47,57` pins actual samples, all observations/pages and remaining Decay result tables. Only known database envelopes lose incidental fields. `backend/tests/test_ml_lifecycle_quant_review.py:223` changes a real feature target and the final cost child; additional tests cover 201 calibration and 101 cost rows plus meaningful nested event fields. |
| P2 | Every explicit CLI write assigned a string to a Path-valued database override (`scripts/import_ml_lifecycle.py:35`); initialization uses `.parent`. The override was never restored and destination safety checked only the leaf symlink. | Current script `:34-47` retains a Path, restores the prior override on success/failure and checks destination ancestry, file identity and hardlinks. `backend/tests/test_ml_lifecycle_import_review.py:219,243` exercise successful registration and failure against owned databases. |
| P2 | Numeric CSV/Parquet roles coerced Booleans to numbers and oversized integers lost precision (`importer.py:108-113`); metadata and `Literal[1]` accepted coercible schema/count values (`importer.py:139`, `models.py:15`). HTTP JSON duplicates could be discarded before model validation (`ml_lifecycle_routes.py:31`). | Strict role/schema/count/column/nullability checks precede coercion; numbers outside exact binary64 integer range are refused. `StrictJSONRoute` at current route file `:12` rejects duplicate/nonfinite/bounded JSON before actions. Root review tests cover self-rehashed malformed legacy metadata, duplicate HTTP keys, schema scalars and invalid table declarations. |
| P2 | Parquet metadata limits did not bound decoded dictionary expansion before `source.read()` and full `to_pylist()` (`importer.py:77-80`). | Current `importer.py:135` uses bounded metadata and incremental one-row decoding with expanded byte limits. Real PyArrow tests cover dictionary expansion, row/column/nesting bounds, duplicate columns, truncated bytes and nullable/nonfinite values. |
| P2 | Source ancestry was checked by name without retaining directory identity across file reads (`importer.py:125-127`). | Current `importer.py:70,108` retains directory handles, checks named/held identities before open, before reading and afterward; POSIX file opens are descriptor-relative. Controlled file and parent replacements are refused. Windows rename blocking is not promised; see the recorded failing test assumption and remaining portable-write limit below. |
| P2 | A failed demo retry could leave the prior successful run/detail visible (`MLLifecyclePanel.tsx:66-69`). | Current `frontend/src/components/MLLifecyclePanel.tsx:68` clears old run, linked detail, comparison/list and selection before the explicit mutation. Failure and stale-response regressions pass. |
| P2 | The second browser-isolation proof checked kind/token/verified status but did not compare the actual database identity with the first proof (`mlLifecycleIsolation.ts:7-12`). | Current `frontend/e2e/mlLifecycleIsolation.ts:7-15` requires equal validated database identities; the shared Phase 64 helper returns its validated identity. Unit tests reject malformed/mismatched proofs. Nine new in-process harness cases check actual owned SQLite identity and refusal before seed mutation. |
| P3 | One discovered browser scenario did not itself prove the reported history/palette/provenance/parsed-export coverage. | The same single scenario now contains explicit sidebar, palette, back/forward, provenance, parsed download, refusal and list/detail checks at 1440/1024/768. Discovery stays 276; none of these browser assertions has been executed in this review. |

No additional confirmed numerical bug was found in the demo's one-shift trading
integration. No global label, feature, estimator or backtest math was changed.

## 3. Identity, trust, persistence and import conclusions

Original configuration identities and `train_run_hash` values remain intact.
Fitted-model identities additionally include ordered features, fitted parameters,
training payload/membership and generating split. Prediction, calibration,
evaluation and physical file identities are separate. JSON distinguishes null,
Boolean, integer, float and string; table `number` deliberately normalizes finite
values to binary64. Full UTC timestamps and scientific event/availability times
remain material. Row IDs, import time and locations do not enter lifecycle
semantic identity. Destination integrity pins retain legacy advertised hashes,
which can themselves include legacy IDs: no cross-database semantic equivalence
is claimed for those pins.

A copied complete demo snapshot submitted to the real public registration route
is refused, including requests adding trust/status fields or relabeling its
origin. The private internal demo action is the only complete-lifecycle path.
Recomputed client checksums provide consistency, not historical authenticity.
Legacy imports remain incomplete/unverified with unknown training environment;
inspection-time package versions are separately labeled. All five adapters
refuse missing legacy feature/membership inputs. API, UI and exports preserve
that limitation. Read/list/detail/export do not train or execute adapters.

Dataset pins inspect actual stored metadata and the retained source snapshot;
ordinary reads never open a Dataset Registry storage locator. Additive migration
preserves old rows and leaves old material pins NULL. Those historical records
become changed/unverified and strict export/compare refuse them; no automatic
backfill, destructive rebuild or retroactive certification occurs. Existing
unpinned demos are not silently upgraded by resume. Operator adjudication or
explicit new version/registration is required; no general migration/replay was
added. The active user database was not migrated in this task.

Per-adapter claims are transactional; downstream failures clear successful
content state, preserve the owned destination and can be explicitly retried.
The complete-demo/idempotence and partial-failure tests passed. Multi-service
creation is not one atomic transaction. A crash leaving `running` requires
operator inspection, not automatic retry. Changed/deleted/invalidated child
content makes the lifecycle incomplete, and strict comparison/export rechecks
integrity. Unrelated records are not modified by repeated demo loading.

Importer scope is one explicitly selected local root and lowercase 64-hex run,
with six allowlisted files, exact full timestamp/instrument keys, no recursive
scan, and an explicit existing destination/version for writes. Preview writes
no DB or artifacts. JSON/CSV/Parquet bytes are parsed from the same retained
buffers that are hashed, then selected files/inventory are rechecked. Duplicate
JSON keys, alternate CSV/Parquet copies, ambiguous joins, unsupported schemas,
nonfinite values, traversal, UNC/drive-relative roots, reparse ancestry,
hardlinks and special files are refused. No pickle/joblib, formula evaluation,
artifact-driven imports, path-bearing API request or dynamic model execution
was introduced.

Filesystem checks are bounded local defenses, not a hostile same-user OS
sandbox. In particular, SQLite still opens the explicit destination by pathname;
portable prevention of malicious concurrent destination replacement is not
established, especially on POSIX. Directory identities and source read handles
are checked, but this is not a general atomic multi-file snapshot. Use an
operator-owned destination with exclusive filesystem control. POSIX behavior
remains an exact-revision Linux verification gate.

## 4. Independent quant and adapter checks

The deterministic seed-650 fixture retains 220 synthetic ES bars, 169 eligible
samples, 32 outer held-out decisions, four inner logistic fits and one final
fit. The new estimator spy checks the actual X/y passed into all five fits,
their exact membership and feature order, not just self-reported hashes. Each
prediction maps to its generating fold; training excludes that fold's test
and all outer held-out samples. Existing closed-interval purge/embargo and
independent audits remain in use. This demo uses causal walk-forward splits;
purged K-fold OOF in general is not necessarily chronological history.

The sigmoid calibrator consumes exactly inner OOF probabilities and binary
`direction_1 == +1` outcomes before final evaluation. Actual call order is four
fits, calibrator, final fit. Existing held-out-label mutation leaves all fitted
model and calibration artifacts unchanged; threshold is fixed at 0.5. Tests
also cover training-membership, feature-order and false-OOF mutations. Full-data
hashes/statistics are not required to stay invariant when data changes.

Raw model probability, frozen calibrated probability, and destination adapter
input are distinct. Meta-Labeling receives the calibrated held-out score with
long primary side and explicit zero outcome threshold, so up-versus-rest agrees
with its success definition. Destination calibration is `none`; it does not
refit held-out outcomes or claim they are OOF. A separate formula check verifies
the frozen sigmoid outputs.

### Hand-computable timing and costs

The regression at `backend/tests/test_ml_lifecycle_quant_review.py:26` uses
prices `[100, 110, 99, 118.8, 118.8, 106.92]`. The label for decision t is the
return from t+1 to t+2. Target t earns the price return from t to t+1 after the
engine's single shift. They differ by one bar; this is not fixed by adding a
second target shift.

| t | Price | Target at t | Effective position at t | Label for decision t | Gross PnL at t | Net PnL at t |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 100 | 1 | 0 | -10% | 0 | 0 |
| 1 | 110 | 0 | 1 | +20% | +10% | +9.89% |
| 2 | 99 | 1 | 0 | 0 | 0 | -0.10% |
| 3 | 118.8 | 1 | 1 | -10% | +20% | +19.88% |
| 4 | 118.8 | 0 | 1 | unavailable | 0 | 0 |
| 5 | 106.92 | 1 | 0 | unavailable | 0 | -0.10% |

Turnover is `[0,1,1,1,0,1]`, derived from effective positions, initially flat.
Engine gross-minus-net drag is `[0,.0011,.001,.0012,0,.001]`; the 10-bps linear
reference fee is `[0,.001,.001,.001,0,.001]` in return units, or 10 currency units
per unit turnover on the fixed 10000 reference notional. The engine compounds
its path; Cost Diagnostics receives gross returns and retains actual net/drag
as metadata. No second cost deduction or substitution of linear reference fees
for compounded drag occurs. The final target has no subsequent observed return.

Snapshot policy/export explicitly names both intervals. The UI displays
separate raw/calibrated probabilities and the retained evaluation/cost policy;
comparison's metrics are backtest metrics, not label-probability metrics. No
lineage/adapter claim equating these horizons was found on source inspection.

All five adapters use the same lifecycle data and real public destination
contracts. Model Validation checks the final split against the actual stored
model membership. Feature Diagnostics receives actual X/y and split but fits a
separate diagnostic estimator, clearly labeled as such. Cost Diagnostics uses
gross period returns and actual turnover with explicit units. Signal Decay uses
calibrated held-out score, exact availability/entity/time and fixed horizon 1 /
entry lag 1, with no favorable horizon selection. Its grid uses signal-observation
steps: 32 scores yield **30 usable pairs and two structural end exclusions**;
the extra source price bars do not invent scores. Those 30 outcomes match the
declared label interval. The optional Phase 64 strategy-stream link and general
Phase 66 replay remain absent.

## 5. Frontend and browser isolation

Canonical registration/component mapping, sidebar/palette/permalink handling,
history cleanup, async cancellation and destination mapping were inspected.
List/detail tables are bounded, states remain separate, controls use dark
accessible styling, and export requests fresh backend validation before saving
JSON. There is no winner/promotion control. The explicit demo button is the sole
workspace mutation; reading/exporting does not run labs.

The guarded harness checks the token, owned marker, configured DB path, physical
identity and actual SQLite connection on requests. New tests use a real owned
SQLite proof with synthetic in-process routes, then alter the marker, override
or serving connection before both guarded seed routes. These are **not** browser
execution. The production harness required no modification.

The browser spec now has explicit assertions, no conditional missing-feature
skips, and six list/detail viewport checks. Its comparison is API self-comparison
of the single idempotent demo. Two-record UI comparison is component-tested;
it is not claimed as executed browser coverage. Discovery only checks that the
276 scenarios load; the later isolated user run must exercise the strengthened
Phase 65 scenario through both equal-identity proxy handshakes.

## 6. Executed verification and preserved evidence

Tests were serial, with all source edits frozen during each protected run.
Authoritative backend executable: `C:\quantlab\backend\venv\Scripts\python.exe`,
Python 3.13.5 / pytest 9.0.3 / NumPy 2.4.6 / pandas 3.0.3 / SciPy 1.17.1 /
Pydantic 2.13.4; optional PyArrow absent. The older root `.venv` was not used.

Supplementary codec executable: `C:\Users\jimli\anaconda3\python.exe`, Python
3.13.5 / pytest 8.3.4 / PyArrow 19.0.0 / NumPy 2.3.4 / pandas 2.2.3 /
SciPy 1.16.3 / Pydantic 2.10.3. It has no FastAPI; only codec/producer tests ran
there. No packages were installed or dependencies changed. Installed Python
3.11.9 has PyArrow 22.0.0 but no pytest; Python 3.12.10 lacks the needed stack.
Neither was used for application test execution. `.github/workflows/ci.yml`
declares Python 3.11 and Node 24; local Python 3.13 success is not 3.11 evidence.

Backend commands, from `C:\quantlab`:

```powershell
# B1: initial seven-module focused snapshot
.\scripts\run_backend_tests.ps1 -Scope focused -Python .\backend\venv\Scripts\python.exe -Tests @('backend/tests/test_ml_lifecycle.py','backend/tests/test_ml_lifecycle_import.py','backend/tests/test_ml_lifecycle_review.py','backend/tests/test_ml_lifecycle_import_review.py','backend/tests/test_ml_lifecycle_quant_review.py','backend/tests/test_ml_lifecycle_e2e_harness.py','backend/tests/test_strategy_ensemble_e2e_harness.py')

# B2: affected modules after directory-identity/test correction
.\scripts\run_backend_tests.ps1 -Scope focused -Python .\backend\venv\Scripts\python.exe -Tests @('backend/tests/test_ml_lifecycle_import.py','backend/tests/test_ml_lifecycle_import_review.py')

# B3: actual codec boundary and actual ExperimentStore CSV/Parquet round-trip
.\scripts\run_backend_tests.ps1 -Scope focused -Python C:\Users\jimli\anaconda3\python.exe -Tests @('backend/tests/test_ml_lifecycle_import_review.py::test_real_parquet_nullable_finite_boundary','backend/tests/test_ml_lifecycle_import_review.py::test_real_parquet_csv_semantics_with_offset_null_and_boolean','backend/tests/test_ml_lifecycle_import_review.py::test_real_parquet_rejects_lossy_role_coercion','backend/tests/test_ml_lifecycle_import_review.py::test_real_parquet_duplicate_columns_rejected','backend/tests/test_ml_lifecycle_import_review.py::test_real_parquet_metadata_and_format_bounds','backend/tests/test_ml_lifecycle_import_review.py::test_real_parquet_dictionary_expansion_is_bounded','backend/tests/test_ml_lifecycle_import.py::test_real_experiment_store_frame_roundtrip')
```

| Run | Collected / selected / deselected | Outcomes | Pytest / child / outer / shell exit | Pytest wall / total outer wall seconds |
|---|---|---|---|---|
| B1 | 134 / 134 / 0 | 115 passed, 18 skipped, 1 failed | 1 / 1 / 1 / 1 | 98.205 / 128.414 |
| B2 | 70 / 70 / 0 | 52 passed, 18 skipped | 0 / 0 / 0 / 0 | 9.976 / 29.974 |
| B3 | 18 / 18 / 0 | 18 passed, 0 skipped | 0 / 0 / 0 / 0 | 11.085 / 23.383 |

B1's failure was the new test's unconditional Windows rename-blocking
expectation: the importer detected replacement and raised `ValueError` instead.
The correction checks parent identity before reading and strengthens requested
handle access; the test now accepts only blocked-original or detected-refusal
outcomes. It never accepts replacement contents. B2 verifies the affected
importer modules, including successful explicit DB registration. No unaffected
demo tests were repeated merely to produce a green aggregate. B1 remains a
failed historical run; these snapshots are not merged into a claimed whole-tree
pass.

Before B1, one sandbox launch failed at the first evidence write with
`PermissionError` in `quantlab-backend-focused-8m3y5k13`, shell exit 1. No tests
started and no pytest count/exit is available for that attempt. Authorized
escalated execution then used a new directory; nothing was deleted.

Evidence roots below are under `C:\Users\jimli\AppData\Local\Temp`:

| Run | Directory | SHA-256 of existing snapshot-manifest.json |
|---|---|---|
| B1 | `quantlab-backend-focused-iehnfsen` | `23420f22c9245750600f665c225ccbc34d8e3175bc94a74ec5919473c78b6644` |
| B2 | `quantlab-backend-focused-04pjje2a` | `45752f7950f6e72c2e77d1f221c86aa89a6ce93b79f9af05c41955234387f5f5` |
| B3 | `quantlab-backend-focused-sg8nb1w7` | `45752f7950f6e72c2e77d1f221c86aa89a6ce93b79f9af05c41955234387f5f5` |

All three completed runs report worktree bytes, snapshot bytes and active DB
unchanged; SQLite violation arrays are empty. B2/B3 also report complete child
evidence. B1's failed result is retained as failed, not converted to success.

B2's 18 skips are 17 missing-PyArrow cases and one physical symlink capability
case (`winerror=1314, errno=22`). B3 executes the 16 new actual-codec cases plus
both real producer round-trips, covering nullable/finite values, NaN and both
infinities, offset timestamps, typed values, malformed/truncated data and bounds.
The existing decoder-stub checks remain separate. Real junction creation/refusal,
hardlink refusal, file replacement and parent replacement checks executed in
owned paths. Physical symlink refusal needs a privilege-enabled environment;
mocked/reparse and junction coverage is not relabeled as a symlink pass.

Frontend executable:
`C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\df473e5367fa2b42\bin\node.exe`
(verified v24.21.0). npm CLI at
`C:\Users\jimli\AppData\Roaming\npm\node_modules\npm\bin\npm-cli.js`
reports 11.17.0. Existing dependencies were used directly, from `C:\quantlab\frontend`:

```powershell
$node = 'C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\df473e5367fa2b42\bin\node.exe'
& $node .\node_modules\vitest\vitest.mjs run
& $node .\node_modules\typescript\bin\tsc --noEmit --incremental false
& $node .\node_modules\@playwright\test\cli.js test --project=chromium --list --reporter=list
```

| Check | Result | Exit | Measured command wall seconds |
|---|---|---:|---:|
| Vitest 4.1.11 | 197 passed, 18 files; Vitest internal duration 30.80s | 0 | 45.190 |
| TypeScript | passed; no emitted files or incremental-cache update | 0 | 21.237 |
| Chromium discovery, list reporter | 276 tests in 20 files; zero browser tests executed | 0 | 3.166 |

Logs and measured exit/duration JSON are retained in
`C:\Users\jimli\AppData\Local\Temp\quantlab-phase65-review-f669ce368e8f4ac9bcdd71090c14edd0`.
Runtime/version probes, source/diff/status reads and final whitespace/hash checks
are inspection evidence, not extra test suites, collection runs or audits.

## 7. Historical evidence and final gates

Existing records were read without rerunning them:

- `quantlab-backend-full-wa650chc`: **4502 passed / 5 skipped / 4507 selected /
  0 deselected**, pytest/child/outer exits 0; pytest wall 2489.702s, total
  2509.174s. Manifest SHA-256
  `9aa0264b9a2bfc8261bf731b2043744ae29156938f773b984dea921f283b1533`.
- `quantlab-backend-focused-h3073rlo`: **33 passed / 2 skipped / 35 selected /
  0 deselected**, exits 0; pytest wall 3.177s, total 16.361s. Manifest SHA-256
  `0614e86271c2a81edb993e9f5eb10ca49ee6df2bbc445b9b190e57cbde24392d`.
- Historical frontend 178/17, TypeScript pass and 276/20 discovery remain dated
  implementation evidence. Discovery was not browser execution.

The full backend snapshot precedes the implementation's final Parquet correction.
This review additionally changes importer, validation, dataset/child integrity,
route parsing and frontend behavior. Neither historical backend run nor the old
frontend numbers validate the final review tree. New focused results establish
bounded regression coverage; there is no final whole-tree/full-suite claim.

Required next gates, after user review/commit:

1. Exact-review-commit CI on declared Python 3.11 / Node 24, including full
   backend regression, frontend tests/typecheck and production build. No workflow
   was triggered here; prefer this over a duplicate local hour-long full run.
2. A disposable supported-Python environment with real PyArrow for the optional
   codec nodes, plus privilege-enabled physical symlink and Linux source-path
   checks. The ordinary local backend venv still lacks PyArrow; the supplementary
   Python 3.13 codec pass does not establish Python 3.11 compatibility.
3. User production build and actual isolated Phase 65 browser execution through
   both proxy identity proofs. No ordinary user services or DB may be used.
4. Retain historical Phase 64 security/release evidence as historical; no new
   broad audit, repeated remediation or security certification occurred.

Expected later user review subject:
`Review unified ml research lifecycle model artifact registry v1`.
Future user tag after the remaining gates:
`v4.83.0-unified-ml-lifecycle-model-artifact-registry-v1`.
No automatic release action or Phase 66 is authorized by this handoff.

## 8. Exact pending review inventory and preservation

**29 pending paths: 23 modified tracked and 6 new. Index remains empty.**
All are source, tests, a CLI or current documentation; no database, credentials,
logs, snapshots, caches, dependency outputs or browser artifacts are included.
This is an inventory, not a staging instruction.

```text
M README.md
M STOP_POINT.md
M TASKS.md
M backend/app/ml_lifecycle/adapters.py
M backend/app/ml_lifecycle/identity.py
M backend/app/ml_lifecycle/importer.py
M backend/app/ml_lifecycle/models.py
M backend/app/ml_lifecycle/service.py
M backend/app/ml_lifecycle/store.py
M backend/app/ml_lifecycle/validation.py
M backend/app/ml_lifecycle_routes.py
M backend/tests/test_ml_lifecycle_import.py
M docs/FORWARD_ROADMAP_PHASES_63_70.md
M docs/ML_RESEARCH_LIFECYCLE.md
M docs/MODEL_ARTIFACT_REGISTRY.md
M docs/VERSION_MANIFEST.md
M frontend/e2e/ml-lifecycle.spec.ts
M frontend/e2e/mlLifecycleIsolation.ts
M frontend/e2e/strategyEnsembleIsolation.ts
M frontend/src/components/MLLifecyclePanel.test.tsx
M frontend/src/components/MLLifecyclePanel.tsx
M frontend/src/test/mlLifecycleIsolation.test.ts
M scripts/import_ml_lifecycle.py
A backend/tests/test_ml_lifecycle_e2e_harness.py
A backend/tests/test_ml_lifecycle_import_review.py
A backend/tests/test_ml_lifecycle_quant_review.py
A backend/tests/test_ml_lifecycle_review.py
A docs/PHASE_65_REVIEW.md
A frontend/src/lib/mlLifecycleLink.test.ts
```

The current-document corrections point to this review, correct the current
branch/implementation SHA, distinguish the new material pin and scalar/import
contracts, record the Decay tail limit and retain dated historical evidence.
The implementation report and frozen Phase 64 reports remain unchanged.

The protected runner verified active-DB preservation in every completed run.
The byte-only before/after check also covers the active DB and every direct file
in `docs/screenshots`, including the frozen release images/checksum guidance.
Active DB SHA-256 remains
`3b26e4b910194ecf0c01fe42c353f591b26b103e06c3f065ed9c0df8eb76f2f5`,
size 8,015,872 bytes. No active SQLite connection was opened. Frozen screenshot,
fixture and browser-guard diffs are empty; no artifact/evidence cleanup occurred.
Ignored external evidence has no exhaustive whole-disk before/after inventory;
preservation of every ignored file is not newly certified.

**This report was written after backend verification and frontend checks.**
It was not part of their tested source snapshots. No executable code was changed
after B2/B3 or the frontend checks; final documentation is not relabeled tested.
Final whitespace, exact inventory and source-byte comparisons are inspection
checks only. They passed: the 29-path set matches this inventory exactly;
all 1,093 files in the final backend snapshot still match their recorded hashes;
the 23 protected DB/screenshot-directory files match their before-check bytes,
sizes and modification times. Only this new report postdates that snapshot.
Work stops at this single review handoff, with no staging or commit.
