# Phase 66 Implementation Handoff

Date: 2026-10-05. Implementation only; a separate fresh session must review.
VERSION: `4.84.0-dev`. Future user tag
`v4.84.0-reproducible-run-replay-environment-manifest-v1` does not exist.

## Baseline and Scope

Clean `main`, empty index and no pending nonignored files at
`c250d7e7de241e18ee8555af4af4c56cef1b4a73`. Frozen tag
`v4.83.0-unified-ml-lifecycle-model-artifact-registry-v1` resolves to that
commit. Authorized new branch: `phase66-run-replay-hash-environment-manifest`.
No existing work was overwritten. HEAD remains unchanged; no Git publication
action or Phase 67. Baseline CI `37208511643` (both jobs passed) is user-supplied
inherited evidence, not rerun and not Phase 66 verification.

Read instructions, existing canonical normalizer/save flow, Registry public
bindings, ML lifecycle read-only APIs and navigation/test isolation contracts.
No changes to strategy signals, PnL, risk, annualization, metric algorithms or
the legacy reproducibility module. No active database initialization/connection;
tests use protected snapshots and isolated owned databases.

## Implemented Boundary

See [support matrix and contracts](RUN_REPLAY_AND_ENVIRONMENT_MANIFEST.md).
SMA is the executable restore adapter. Provider prices are not retained; CSV
needs a verified reupload or retained owned demo snapshot. Other valid legacy
saved strategies are config-only; comparison and other labs are deferred.

Saved result and context insert atomically at explicit save. Context selection
is always explicit, full hashes are indexed nonuniquely, old prefixes/hashes
remain unchanged. Execution/save/inspection contexts are separate; original
wire JSON or labelled validated/defaulted request is retained when available.
Legacy original settings/diagnostics/environment remain unknown.

Read-only resolution/preflight/export do not run engines, train, follow locators,
fetch providers or create records. CSV Run is a separate explicit existing-engine
action. Confirmation, stale-response filtering and edit detachment protect form
state; canonical round-trip tests cover cost/sizing/risk/benchmark/mode/annualization
and diagnostics. Browser spec checks the real saved-run-to-destination flow behind
equal-database-identity proof; browser execution is pending.

## Verification Evidence

Evidence root:
`C:\Users\jimli\AppData\Local\Temp\quantlab-phase66-implementation-7543493451bc49abb7bead991b7a8d03`.
Baseline has hashes for 1094 tracked files and 24 protected data/screenshot files,
plus raw index identity. Existing runtimes/dependencies were discovered, not
installed/upgraded. Local Python 3.13.5 (Anaconda), pytest 9.0.3, FastAPI 0.136.3;
CI's Python 3.11 remains a separate later gate. Supported installed Node v24.21.0
was revalidated at execution; project engines require >=24.20.0 <25.

Development attempts are retained, not hidden:

- `quantlab-backend-focused-g39gci0h`: sandbox denied external evidence write,
  outer exit 1 before a test result; not a test pass.
- `quantlab-backend-focused-a54uks55`: replay/reproducibility/saved-backtests,
  79 passed / 4 failed, pytest 149.00s, process 154.23s, total 166.14s, both exits 1.
  Fixed local CSV helper argument order and SQLite REAL result-identity handling.
  Snapshot/source/data protection checks passed.
- `quantlab-backend-focused-h75mk40h`: 39 passed / 2 failed, pytest 11.15s,
  process 13.5282s, total 27.0835s, both exits 1. Fixture execution identity and test-only harness module lookup were
  corrected; no assertions relaxed or skips added.
- `quantlab-backend-focused-aheav_f0`: replay/reproducibility, 58 passed,
  pytest 12.77s, process 15.2039s, total 25.4730s, both exits 0. Later bounded save and additional regressions required
  a final focused run, recorded below.
- Frontend focused: 4 files / 43 tests passed, Vitest 15.80s, exit 0.
- Initial TypeScript-only check: exit 2, one test mock callback type error;
  corrected. This failure is retained separately from the final check.

Final stable-snapshot results and exact path inventory are appended below.
No full backend suite, baseline importer/container work, production/Docker
builds, services, audit/install, CI dispatch or browser execution in this task.

### Final Executed Checks

| Check | Actual outcome | Duration | Exit |
|---|---|---|---|
| Protected focused backend: replay, legacy reproducibility, saved backtests | 91 selected / 91 passed / 0 failed / 0 skipped | Pytest summary 117.62s; instrumented pytest wall 117.8281s; child process 120.4390s; total runner 144.4977s | Pytest 0; outer runner 0 |
| Final complete frontend unit suite | 22 files / 208 tests passed | Vitest 6.06s; process wall 6.7437s | 0 |
| Final TypeScript, no emit or incremental output | Passed | Process wall 16.0576s | 0 |
| Playwright discovery only | 277 tests in 21 files listed; no browser launched | Process wall 2.3538s | 0 |

The final backend evidence directory is
`C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-plvoqbj1`.
Snapshot setup took 5.6781s. `child_evidence_complete`, `active_db_unchanged`,
`snapshot_bytes_unchanged` and `worktree_bytes_unchanged` are all true.
The manifest identifies HEAD `c250d7e7de241e18ee8555af4af4c56cef1b4a73` plus
the actual uncommitted implementation, including new files; it is not a claim
that Phase 66 is committed. `snapshot-manifest.json` SHA-256 is
`f7b185c42345c3ca3d9da5b5e40a88222128d049cd61d5f3197116aed3e918a2`.
Machine-readable collection, phase outcomes, runtime, JUnit and runner results,
the captured working diff and complete pytest log remain in that directory.

The snapshot's backend, browser harness and replay spec/helper match the final
working bytes (575 checked entries). Frontend URL cleanup/download lifetime
changes followed that backend run, without changing backend/harness/spec bytes;
the final 208-test frontend run and TypeScript check include those changes.
Only documentation is updated after these final code checks.

Earlier complete frontend run: 22 files / 207 tests passed, Vitest 12.69s,
process wall 13.4168s, exit 0; earlier corrected TypeScript passed in 25.8515s,
exit 0. Those remain separate intermediate results, not the final frontend
count. The focused frontend process wall was 28.1365s. No successful check was
repeated solely to collect another summary.

Actual runtime evidence:

- Windows 11, repository `.venv` Python 3.13.5 packaged by Anaconda, pytest 9.0.3,
  one backend worker. FastAPI 0.136.3, numpy 2.4.6, pandas 3.0.3, Pydantic 2.13.4,
  scipy 1.17.1, Starlette 1.1.0, yfinance 1.4.0. Python 3.11 CI is not covered by
  this local focused run. No runtime was installed or changed.
- Node executable actually discovered and revalidated:
  `C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\45309f9050f7314b\bin\node.exe`,
  v24.21.0. The application contains no workstation-specific runtime path.
  Installed frontend manifests: Next 15.5.25, React 19.2.8, Vitest 4.1.11,
  TypeScript 5.9.3, Playwright 1.61.1. npm was not executed; its declared
  packageManager version is not an observed runtime version.

Recorded backend child command (generated by the protected runner, not an
instruction to repeat the completed run):

```powershell
& C:\quantlab\.venv\Scripts\python.exe -u C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-plvoqbj1\source\scripts\backend_test_runner.py --execute C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-plvoqbj1\run-config.json
```

That retained config selected exactly:

```text
backend/tests/test_run_replay.py backend/tests/test_reproducibility.py backend/tests/test_saved_backtests.py -q -ra -p no:cacheprovider --durations=0 --durations-min=0 --basetemp C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-plvoqbj1\pytest-tmp --junitxml C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-plvoqbj1\junit.xml
```

Frontend commands actually executed from `C:\quantlab\frontend` using that
validated Node executable, not npm, a production build or browser execution:

```powershell
& $node node_modules/vitest/vitest.mjs run
& $node node_modules/typescript/bin/tsc --noEmit --incremental false
& $node node_modules/@playwright/test/cli.js test --list --reporter=list
```

`$node` above refers to the discovered, existence-checked v24.21.0 executable.
For future user-owned checks, rediscover a current supported executable or
explicitly validate both its existence and version; do not assume this hashed
runtime directory is permanent. Discovery used the default Chromium project
without an Edge channel override and is not acceptance execution.

### Protection and Hygiene

`baseline.json`, `pre-handoff-protection.json` and `final-protection.json` are in
the external Phase 66 evidence root. The first protection-helper attempt exited
1 before completing checks because PowerShell single-result indexing extracted
a character instead of the branch string. Direct Git reads confirmed the actual
expected branch/HEAD/tag; correcting that evidence helper allowed the complete
checks to pass. This was not a source defect or an unexpected checkout change.
Its failure is recorded separately, not relabelled as a passing attempt.

- Exactly 38 pending paths: 19 modified tracked and 19 new files; full membership
  checked, not just the count. Zero staged paths. No extra nonignored artifacts.
- HEAD and frozen v4.83 tag remain `c250d7e7de241e18ee8555af4af4c56cef1b4a73`.
  VERSION is `4.84.0-dev`; the proposed v4.84 tag remains absent.
- Raw index SHA-256 remains
  `b957e20a7f2ae2aa7120cdc06a5b57f049aa38a4b9a683697cd5b06903947734`.
- All 24 protected files retain bytes, size, UTC modification ticks and exact
  inventory. No added SQLite sidecars. Active DB remains 8015872 bytes with
  SHA-256 `3b26e4b910194ecf0c01fe42c353f591b26b103e06c3f065ed9c0df8eb76f2f5`,
  UTC modification ticks `639213676779732459`; hash inspection did not connect
  to or initialize it.
- All 1094 baseline tracked hashes were checked; files outside the explicit
  19 modified paths remain byte-identical. Quant algorithms, the old canonical
  serializer, governing instructions, dependency files, workflows, Dockerfiles
  and frozen Phase 65 evidence remain unchanged.
- Working and cached `git diff --check` pass; new-file trailing whitespace check
  passes. Working and staged screenshot diffs are empty. Git's existing LF/CRLF
  warnings were retained; no line-ending configuration or renormalization change.
- No unintended database, credentials, logs, binaries, caches, build output,
  node_modules or browser artifacts in the pending set. All generated evidence
  is external. No installs, services, commits or remote publication occurred.

## Exact Path Inventory and Later User-Owned Git Plan

This is a proposed literal staging list, NOT authorization to execute it now.
After fresh independent review/fixes and the user's gate decisions, revalidate
the branch, HEAD, entire pending/index inventory and protected-file identities.
If the reviewed file set changes, update/reapprove that exact list before use.
No staging, commit or push was performed during this task.

From `C:\quantlab`, the later user-only staging command is:

```powershell
$approved = @(
  'CHANGELOG.md',
  'README.md',
  'STOP_POINT.md',
  'TASKS.md',
  'VERSION',
  'backend/app/db.py',
  'backend/app/main.py',
  'backend/app/saved_backtests.py',
  'backend/app/schemas.py',
  'backend/app/run_replay/__init__.py',
  'backend/app/run_replay/adapter.py',
  'backend/app/run_replay/environment.py',
  'backend/app/run_replay/identity.py',
  'backend/app/run_replay/routes.py',
  'backend/app/run_replay/service.py',
  'backend/app/run_replay/store.py',
  'backend/tests/test_run_replay.py',
  'docs/FORWARD_ROADMAP_PHASES_63_70.md',
  'docs/VERSION_MANIFEST.md',
  'docs/PHASE_66_IMPLEMENTATION.md',
  'docs/RUN_REPLAY_AND_ENVIRONMENT_MANIFEST.md',
  'frontend/src/app/page.tsx',
  'frontend/src/components/AppShell.tsx',
  'frontend/src/components/BacktestForm.tsx',
  'frontend/src/components/SaveBacktestModal.tsx',
  'frontend/src/components/SavedBacktestDetail.tsx',
  'frontend/src/components/Sidebar.tsx',
  'frontend/src/components/RunReplayPanel.tsx',
  'frontend/src/components/RunReplayPanel.test.tsx',
  'frontend/src/components/ReplayBacktestForm.test.tsx',
  'frontend/src/lib/types.ts',
  'frontend/src/lib/workspaceRegistry.ts',
  'frontend/src/lib/runReplay.ts',
  'frontend/src/lib/runReplay.test.ts',
  'frontend/src/lib/runReplayIsolation.test.ts',
  'frontend/e2e/run-replay.spec.ts',
  'frontend/e2e/runReplayIsolation.ts',
  'scripts/run_replay_e2e.py'
)
git --literal-pathspecs add -- $approved
```

Then the user must verify exact cached path membership, cached whitespace,
protected screenshot/data exclusions and no intended residual changes. Expected
later implementation subject:
`Add reproducible run replay by hash environment manifest v1`.
Separate fresh review subject:
`Review reproducible run replay by hash environment manifest v1`.
No commit/push/tag command was executed or implicitly authorized here.

## Limitations, Gate Decisions and Stop

- Safe to keep as a bounded local implementation; ready for a fresh independent
  review, not a released or independently approved milestone.
- SMA only for execution/restore. Other verified saved strategies are config-only;
  comparison/portfolio/other labs have no new adapter. Unsupported fields refuse
  exact restoration rather than silently losing meaning.
- Legacy execution/original diagnostics can remain unknown. Provider history is
  not retained. CSV needs exact-byte reselection unless bounded owned bytes are
  retained. Demo uses actual deterministic synthetic input, not fake results.
- Database-local saved/Registry IDs are not portable identities. Declared local
  save metadata are not cryptographically attested; matching hashes/environment
  fields do not guarantee authenticity, compatibility or bit-identical output.
- Optional Phase 65 references are read-only provenance, never a model-to-return
  adapter. No provider fallback, locator following, training or auto-execution.
- Pending: separate source review, user-owned production build, focused isolated
  browser acceptance, exact-implementation-commit whole-tree CI on Python 3.11.
  Browser discovery alone closes none of the execution/platform gates; no full
  backend pass or cross-platform Phase 66 execution is claimed.
- Baseline CI/build/browser/Linux importer evidence remains inherited Phase 65
  evidence. It was neither rerun nor relabelled as Phase 66 evidence.
- No staging, commit, push, tag, PR, workflow dispatch, deployment or Phase 67.
  Stop at this implementation handoff.
