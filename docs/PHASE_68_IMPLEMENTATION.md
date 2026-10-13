# Phase 68 Implementation Handoff

Date: 2026-10-13. Implementation only; independent review is a later fresh session.

## Baseline and Scope

Started clean on main at **e23e828952c1dd1dcc320a225e75a0337aa1fd80**, empty
index/no nonignored untracked files. Verified annotated frozen tag
`v4.85.0-futures-point-in-time-contract-calendar-foundation-adapter-spec-v1`
resolves to that exact commit. Created the explicitly authorized branch
`phase68-cross-sectional-neutralisation-scanner-validation` from that baseline.
Phase 67 final-doc CI **38219121957**, both jobs success, is supplied historical
evidence, not retrieved/rerun. Frozen Phase 67 implementation/review reports,
platform evidence and screenshots remain unchanged. VERSION is **4.86.0-dev**.

Actual reuse/support map and numerical/timing/runbook contracts are in
[CROSS_SECTIONAL_NEUTRALISATION_AND_SCANNER_VALIDATION.md](CROSS_SECTIONAL_NEUTRALISATION_AND_SCANNER_VALIDATION.md).
No new signal, provider, broker, optimizer, database/schema, auth, replay registry
or Phase 69. Existing scanner generator/draw stream and omitted-options behavior
are preserved. No whole-tree backend run, services, browser execution or build.

## Delivered Boundaries

- Explicit versioned dollar/sector/beta policies, keyed availability-aware
  supplied declarations or trailing estimated beta, descriptive Phase 59 OLS.
- Separate residual-score basket and final selected-support joint SVD projection;
  gross/cap checks, zero-direction/infeasibility/refusal states, advanced cash
  fallback with actual turnover; no approximate ridge advertised exact neutral.
- Declared ex-ante fixed-weight sample-volatility reference, independent requested,
  estimated/scaled/capped/achieved and later realized values; one existing P&L lag.
- Real daily fixed-policy scanner selections linked to Phase 52 samples/purge/
  embargo/audit, with weights/full-precision outcomes. Learned beta/volatility
  OOS and non-daily carried-holdings adapter honestly unavailable, not relabelled.
- Entire declared candidate family and existing Phase 53 corrections; supplied
  p-values never promoted to verified, partial coverage explicit, PBO/DSR unavailable.
- Existing Scanner UI, explicit Run/Validate/prefill/download actions, stale-response
  rejection, editable string inputs, synthetic warnings and bounded stage/fold tables.
- Inline pinned full-resolution JSON evidence, no active DB/persistence migration,
  no automatic Phase 66 registration/restoration or research GET/page effect.

## Development Evidence (Retained, Not Final-Suite Claims)

External protection/evidence root:
**C:/Users/jimli/AppData/Local/Temp/quantlab-phase68-e77d11199a7a405b91fe6c7a8a168e77**.
Initial bounded protection manifest covers 47 active-data/frozen screenshot/report
files and the index. No package installation into user environments.

- First protected scanner run **lbptw9h_**: 57 passed / 1 failed, pytest 39.30s,
  pytest-process/outer exits 1, runner total 86.368003100s. Future-only fixture incorrectly recomputed historical returns, changing
  floating bits. Fixed only future rows; retained exact-equality assertion.
- Second new-policy/validation run **jr9ebnj_**: 24 passed / 8 failed / 8 teardown
  errors, pytest 18.57s, pytest-process/outer exits 1, runner total 32.517098100s. API tests used a TestClient lifespan context,
  causing guarded attempts to initialize a TEST-OWNED DB in db-free tests.
  Corrected to the existing scanner's non-lifespan pure-route client pattern;
  neither removed db-free guards nor opened the active DB.
- Initial TypeScript check exited 2: three new test locators incorrectly used
  Playwright's exact option in Testing Library. Removed that unsupported option;
  no application type failure or weakened assertion.
- Focused frontend: 13 passed / 2 files, 32.12s, exit 0, before final evidence/
  download-test strengthening. JSON/log/process metadata retained externally.

Runtime discovery: Program Files Node **24.15.0** and current primary runtime
**24.19.0** do not meet package engines and were not used for tests. Bounded
discovery found actual existing
`C:/Users/jimli/AppData/Local/OpenAI/Codex/runtimes/cua_node/cfb32733c877621e/bin/node.exe`,
**24.21.0** (supported >=24.20.0 <25); npm **11.17.0** meets >=11 <12.
No stale historical hashed path reused, no dependency reinstall or runtime upgrade.
Existing Windows Python **3.11.9** has no pytest; no package borrowing/install.
Protected runtime is existing **C:/quantlab/.venv/Scripts/python.exe**, Python
**3.13.5** Anaconda/MSC AMD64. Python 3.11 syntax checking is separate from
runtime tests; exact-commit Python 3.11 CI remains pending. No Phase 67 platform
tests, container task, CLI acceptance or Docker application build repeated.

## Stable Verification and Final Hygiene

Broad serial protected regression snapshot (before the final selected-support
rank strengthening recorded below), external evidence:
**C:/Users/jimli/AppData/Local/Temp/quantlab-backend-focused-85bis2c9**.
Manifest SHA-256:
**c5de9feed386651ff084f0b1ff661524691aeff205c19dcc9b21ae4c4ee7c373**.
No source/docs edits occurred during any protected execution. Exact invocation:

~~~powershell
& C:\quantlab\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused `
  --test backend/tests/test_scanner_advanced.py `
  --test backend/tests/test_scanner_validation.py `
  --test backend/tests/test_scanner.py `
  --test backend/tests/test_factor_diagnostics.py `
  --test backend/tests/test_model_validation_engine.py `
  --test backend/tests/test_model_validation_api.py `
  --test backend/tests/test_overfitting_diagnostics.py
~~~

**250 collected/selected, 0 deselected; 250 passed / 0 skipped / 0 failed /
0 errors.** No skip reasons apply. All 250 setup and teardown phases passed.
New tests: scanner policy **21**, scanner validation **12** (33 total).
Existing: scanner **40**, factor **98**, split engine **35**, model API **15**,
overfitting **29** (217 total). These are one actual focused run, not an invented
whole-tree result. New cases exercise hand-computable final weights/exposures,
perfect-sector no-signal, selected-support/rank/near-constant-beta refusal,
availability/unknown inputs, caps/zero variance/cash costs, exact fixed-history
future perturbation, real API/sample-linked held-out outcomes, split audits,
declared/partial p families and retained-content tamper detection.

- Printed pytest summary **387.93s (0:06:27)**.
- Machine pytest wall **388.111081200s**, startup/collection **7.711929900s**.
- Snapshot setup **6.804111400s**, test-process wall **390.907499000s**,
  total runner **409.681073800s**.
- Machine pytest exit **0**, pytest process exit **0**, outer runner/tool exit
  **0**, retained separately. child_evidence_complete is true.
- worktree_bytes_unchanged, snapshot_bytes_unchanged and active_db_unchanged are
  **true**; sqlite-violations.json is **[]**. Both failed development snapshots
  also report those byte/active-DB protections true, without relabelling their failures.
- Actual Windows 11 build 26100 / Python **3.13.5**, numpy **2.4.6**, pandas
  **3.0.3**, scipy **1.17.1**, pydantic **2.13.4**, pytest **9.0.3**, fastapi
  **0.136.3**, httpx **0.28.1**, PyYAML **6.0.3**. Full metadata/environment,
  per-node/phase outcomes, durations, logs, selection, JUnit, SQLite audit,
  source/diff manifest and process/protection results are retained by the runner.

### Final Selected-Support Rank Strengthening

Final mathematical inspection identified a distinct numerical boundary: a
well-conditioned full cross-section can select just two nearly equal-beta names.
Their constraint matrix is full rank, so no nonzero nullspace exists; relying
only on the small residual norm could let numerical cancellation survive.
Added an explicit support-rank exhaustion refusal before normalization, plus a
hand-specified regression with scores [3,-3e-10,3e-10,-3] and betas
[1,4,5,1+1e-10]. No assertions were weakened or portfolio forced.

Only scanner/advanced.py, its new policy test module and the policy runbook
changed after the broad run. Phase 59/52/53 modules and frontend source remain
the broad/previously verified bytes. Final affected-scope invocation:

~~~powershell
& C:\quantlab\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused `
  --test backend/tests/test_scanner_advanced.py `
  --test backend/tests/test_scanner_validation.py `
  --test backend/tests/test_scanner.py
~~~

Final source snapshot:
**C:/Users/jimli/AppData/Local/Temp/quantlab-backend-focused-6cjf48oi**.
Manifest SHA-256:
**d1eea1b44acf2414a16ca205d2f43b777d5a0efbdffc0286bea676c411535c5c**.
**74 selected/passed, zero skips/failures/errors** (22 new policy + 12 new
validation + 40 existing scanner nodes), all setup/teardown phases passed.
Printed pytest **14.43s**; machine pytest **14.928109100s**; snapshot setup
**10.542118600s**, process wall **18.280113600s**, outer runner **36.840026900s**.
Machine pytest, test-process and outer runner/tool exits all **0**. Worktree,
snapshot and active-DB protections and child_evidence_complete all true;
SQLite audit violations empty. This is NOT combined with 250 into a fictional
324-case suite. Both actual snapshots and development failures remain retained.

### Frontend and Compatibility Commands

`$node` was the newly discovered/existence-checked **24.21.0** executable above,
not either unsupported default runtime. Commands ran in frontend/ with external
logs/JSON/process timers under the Phase 68 evidence root:

~~~powershell
& $node node_modules/typescript/bin/tsc --noEmit --incremental false
& $node node_modules/vitest/vitest.mjs run --reporter=verbose --reporter=json --outputFile=<external-evidence>/frontend-unit-final.json
& $node node_modules/@playwright/test/cli.js test e2e/scanner-neutralisation.spec.ts --project=chromium --list --reporter=list
& $node node_modules/@playwright/test/cli.js test --project=chromium --list --reporter=list
~~~

| Check | Actual result | Printed / host duration | Process exit |
| --- | --- | --- | --- |
| TypeScript final | no diagnostics; incremental cache disabled | host 16.2509173s | 0 |
| Frontend unit suite | 241 passed, 0 failed/pending; 24 files | printed 6.73s / host 7.4317306s | 0 |
| Focused browser discovery | 1 test / 1 file | host 2.2633041s | 0 |
| Overall browser discovery | 278 tests / 22 files | host 1.6326054s | 0 |

Of the 241 frontend passes, 14 are new Scanner component/utility cases. Actual
controls/actions, default compatibility, fixture-only prefills, declared input
validation, editable empty fields, duplicate/stale-response guards, unavailable
rows/audit displays, errors and JSON download material/immutability are tested.
Vitest **4.1.11** logs retain the existing setupIsolation console-error sentinel;
it is an intentional passing assertion, not an unreported application failure.
No tests were silently skipped. Discovery did not launch a browser or execute
the new viewport/navigation/download spec. Positive disposable-backend proof
through the actual frontend proxy is required when the user later executes it.

Installed Python **3.11.9** parsed all **15** scanner/route/schema/main/new-test
Python files with ast.parse, `-B`, no imports/bytecode: exit **0**, both early
and at final source. This is syntax-only evidence, not Python 3.11 runtime tests.
No user Python/Node package installation, dependency/runtime upgrade, service,
production/Docker build, browser execution, audit or old Phase 67 checks occurred.

### Final Protection and Decision

All 47 baseline protected data/screenshot/historical-report paths retain exact
SHA-256, sizes and mtime; index bytes match the initial manifest and staged set
is empty. Tests used private snapshots/test-owned databases, never the active DB.
The legacy generator and Phase 59/52/53 modules are unchanged; new policies use
their actual contracts rather than changing deferred product statuses.

Only README, STOP_POINT, TASKS, roadmap and this implementation ledger were
updated AFTER the final 74-node snapshot to record current evidence/status.
The other 22 pending paths (scientific source/tests, frontend code/tests, runbook
and VERSION included) match that snapshot's exact bytes. Final hygiene passed:
27 exact paths / 13 modified / 14 new, tracked diff check exit 0, no new-file
trailing whitespace or extra EOF blank lines, 12 relative links valid, frozen
screenshot diff empty, 47 protected files and index bytes unchanged. Existing
LF/CRLF warnings do not trigger renormalization or Git configuration changes.
No blanket artifact/cache/evidence cleanup. Raw pending-file hashes and checks
are in external final-hygiene.json; the earlier pre-strengthening hygiene snapshot
is retained separately, not relabelled as evidence for the final source.

**Safe to keep: yes, as bounded synthetic research. Ready for fresh independent
review: yes.** Not a release, financial/statistical certification or completed
build/browser/CI gate. Remaining: independent review, user production build and
actual isolated browser acceptance, then exact-commit Python 3.11 CI/publication
and user-created milestone tag. No current task is authorized to start Phase 69.

## Exact Pending Inventory and Later User-Only Git Plan

**27 paths: 13 modified / 14 new**, no staged paths. This is the implementation
inventory, not a future independent-review inventory. Recheck current bytes,
classifications and amendments before any later authorized Git action; do not
substitute the frozen Phase 67 list or force a count.

~~~powershell
$phase68Paths = @(
  # Modified (13)
  'CHANGELOG.md',
  'README.md',
  'STOP_POINT.md',
  'TASKS.md',
  'VERSION',
  'backend/app/main.py',
  'backend/app/scanner/cross_sectional.py',
  'backend/app/schemas.py',
  'docs/FORWARD_ROADMAP_PHASES_63_70.md',
  'docs/VERSION_MANIFEST.md',
  'frontend/src/components/ScannerLabPanel.tsx',
  'frontend/src/lib/api.ts',
  'frontend/src/lib/types.ts',
  # New (14)
  'backend/app/scanner/advanced.py',
  'backend/app/scanner/pnl.py',
  'backend/app/scanner/policies.py',
  'backend/app/scanner/validation.py',
  'backend/app/scanner_validation_routes.py',
  'backend/tests/test_scanner_advanced.py',
  'backend/tests/test_scanner_validation.py',
  'docs/CROSS_SECTIONAL_NEUTRALISATION_AND_SCANNER_VALIDATION.md',
  'docs/PHASE_68_IMPLEMENTATION.md',
  'frontend/e2e/scanner-neutralisation.spec.ts',
  'frontend/src/components/ScannerLabPanel.test.tsx',
  'frontend/src/components/ScannerResearchResults.tsx',
  'frontend/src/lib/scannerAdvanced.test.ts',
  'frontend/src/lib/scannerAdvanced.ts'
)
# Later USER action only, not executed in this implementation task:
git --literal-pathspecs add -- @phase68Paths
git diff --cached --check
~~~

Do not execute this Markdown as a script. No staging has occurred. Later user
implementation commit subject is listed below; a fresh independent review and
separate review commit remain required. Update the explicit inventory if that
review changes scope. No user database, credentials, log, evidence, dependency,
runtime binary, cache, build/browser output or frozen screenshot belongs in it.

## Publication Boundary

No staging, commit, push, tag, PR, workflow trigger, deployment or Phase 69.
After the implementation handoff, a separate fresh session independently reviews
the exact diff. User build/browser acceptance and exact-commit CI are later gates.
Expected later user subjects:

- `Add advanced cross sectional neutralisation scanner validation v1`
- `Review advanced cross sectional neutralisation scanner validation v1`

Future user tag (not created):
`v4.86.0-cross-sectional-neutralisation-scanner-validation-v1`.
