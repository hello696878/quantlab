# Backend Test Maintenance

This is test-infrastructure maintenance during Phase 64, not a new product phase
or a release certification. Existing implementation, production calculations,
numerical tolerances, frozen fixtures, and user data are unchanged.

## Verified Passing Full Run (2026-09-10 Evidence Review)

The user completed the repaired full run on 2026-09-09. Existing evidence at
`C:\Users\jimli\AppData\Local\Temp\quantlab-backend-full-9xsg6dkz` was inspected
read-only; no tests, collection, frontend checks, builds or servers were rerun
for this finalization. Retain that directory and the historical evidence below
outside Git under the existing unique-TEMP-directory convention. Nothing was
copied into the repository or deleted.

| Recorded evidence | Verified result |
| --- | --- |
| `pytest.log` complete summary | **4359 passed, 3 skipped in 3285.73s (0:54:45)** |
| `junit.xml` | 4,362 tests, 0 failures, 0 errors, 3 skips |
| `pytest-result.json` `exit_code` | **0**; 4,359 passing calls, 3 skipped calls; all 4,362 setups/teardowns passed |
| `runner-result.json` `pytest_process_exit_code` | **0** (child process, distinct from the outer runner) |
| Outer runner / PowerShell final exit code | **Not recorded; not directly verified** |
| Scope | `full`, `collect_only: false`, 1 worker; no hidden filter |
| Collection | 4,362 ordered collected = selected IDs; 0 deselected |
| Interpreter | `C:\quantlab\.venv\Scripts\python.exe`, Python 3.13.5 (Anaconda), pytest 9.0.3 |
| Encoding | `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` |
| Source HEAD | `0eceda6bc3458aa4583cb868a62a49765d2bad73` |
| Source identity | Uncommitted Phase 64 plus maintenance; 1,053 SHA-256 entries, no omitted listed files |
| Runner protections | `worktree_bytes_unchanged`, `snapshot_bytes_unchanged`, `active_db_unchanged`: all `true` |
| SQLite audit | `sqlite-violations.json` is `[]` |
| Process / total runner wall seconds | 3,289.31 / 3,295.77; not a controlled speedup comparison |

The outer runner writes no final-exit-code field. Inspection of its tested return
branch shows the recorded child code and all three true protection checks imply
a return of 0 **if final printing and process exit completed normally**. This is
code-path inference, not a captured shell exit status. Both final result and
after-DB files exist; the pytest summary alone is not used to establish runner
post-processing success. The original user-entered PowerShell invocation was
not recorded. The exact child command recorded in `runner-result.json` is:

```text
C:\quantlab\.venv\Scripts\python.exe -u C:\Users\jimli\AppData\Local\Temp\quantlab-backend-full-9xsg6dkz\source\scripts\backend_test_runner.py --execute C:\Users\jimli\AppData\Local\Temp\quantlab-backend-full-9xsg6dkz\run-config.json
```

Its snapshot working directory is `...\quantlab-backend-full-9xsg6dkz\source`
(established from the tested runner's `cwd=snapshot`). `run-config.json` records
`backend/tests -q -ra -p no:cacheprovider --durations=0 --durations-min=0`, with
`--basetemp` and `--junitxml` targeting that run's `pytest-tmp` and `junit.xml`.
The configured ini options are `-v --tb=short -q`; AnyIO 4.13.0 is the only
auto-loaded plugin. This metadata describes the run; it is not an instruction
to repeat it during evidence finalization.

Exact skip reasons from the log and JUnit record:

- `test_experiment_audit.py:711`, `test_audit_root_symlink_not_followed`:
  `symlink creation not permitted on this platform`.
- `test_experiment_audit.py:885`, `test_audit_artifact_symlink_not_followed`:
  `symlink creation not permitted on this platform`.
- `test_experiment_review.py:2755`, `test_cli_rejects_symlink_output_into_the_store`:
  `symlink creation is not permitted on this platform`.

Evidence identifiers (SHA-256 of the existing files, not new manifests):

| File | SHA-256 |
| --- | --- |
| `snapshot-manifest.json` | `25d5c07037705cf8984f48cd79dad2e08e28fc24b2411053ca644400855ccdf3` |
| `collection.json` | `16d08f5bdf946fd27c108c3af5914760bc905fa86c33fb3820d7bbc5e77d0b6f` |
| `runner-result.json` | `aad2b91b7b60d5ab407b6f720789154341df8a8cc3fc6fea2a580a9f2863e50d` |
| `pytest.log` | `ff3be8849013ca9e9f7808ce2b5e774f4d032605c9e96539e39a047d6866ddab` |

### Snapshot, Database and Frozen-Evidence Boundaries

Before documentation edits, all 1,053 source files and their copied snapshot
files matched the manifest, and the current tracked/nonignored-untracked path
inventory matched. No product/test/runner/configuration/dependency/version drift
was found. The only later edits are documentation finalization in `README.md`,
`CHANGELOG.md`, `STOP_POINT.md`, `TASKS.md`, `docs/PROJECT_SNAPSHOT.md`,
`docs/FORWARD_ROADMAP_PHASES_63_70.md`, this report, and
`docs/PHASE_64_IMPLEMENTATION.md`. These later documentation bytes were not part
of the passing snapshot. No executable code was changed or test rerun to relabel
that snapshot.

The existing before/after DB records agree on SHA-256
`3b26e4b910194ecf0c01fe42c353f591b26b103e06c3f065ed9c0df8eb76f2f5`,
size 8,015,872 and `mtime_ns: 1785770877973245900`, with no recorded sidecar.
This establishes the active DB protection independently of Git ignoring it.
The review did not open the active database through SQLite.

No dedicated frozen-evidence result field was recorded. Tracked screenshots,
the release checksum manifest, frozen-demo fixture/source and guards are covered
by the 1,053-file source/snapshot checks and match current bytes; screenshot Git
diff is empty. This is preservation evidence, not a new browser or checksum-
validator run. Ignored external artifacts have no complete before/after byte
inventory in this run, so preservation of every ignored artifact is **not
verified** by the source manifest. No broad cleanup was performed.

### Count Reconciliation and Remaining Gates

The superseded run had 4,349 passed + 9 failed + 3 skipped = 4,361 tests. The
passing run has 4,359 passed + 3 skipped = 4,362. Comparing actual collection
records found zero removed IDs and exactly one added ID:
`tests/test_backend_test_maintenance.py::test_runner_keeps_nested_subprocess_text_encoding_consistent`.
The passing ordered collection also exactly matches the final 4,362-ID
collection-only record at `quantlab-backend-full-dqq9ami1`.

The passing `phases.jsonl` confirms all nine former encoding-failure IDs and all
eight absent/present variants of the four database-safety tests passed. They
are not unresolved failures of this run. Historical logs remain intact below.
These results are not proof of complete test coverage. Overall speedup has not
been established; parallel execution remains unverified and disabled.

Still pending: independent Phase 64/maintenance review, actual CI on the final
reviewed commit, user production build, isolated full browser/smoke verification,
and existing dependency-security/release gates. Prior frontend checks are
historical implementation evidence, not checks rerun for this task. No commit,
push, workflow, tag, release, deployment or Phase 65 work was performed.

## Verification Commands

Run from `C:\quantlab` in PowerShell. The existing runner now preserves repository
artifacts instead of deleting them. No command installs dependencies, starts
user services, runs frontend builds, or enables parallel workers. Existing tests
that create and close their own ephemeral loopback HTTP server remain unchanged.

```powershell
# Explicit files or node IDs; repeat entries in the array as needed.
.\scripts\run_backend_tests.ps1 -Scope focused -Tests @('backend/tests/test_strategy_ensemble.py')

# Audited database-free subset only. Not full regression.
.\scripts\run_backend_tests.ps1 -Scope fast

# Selected scope with cProfile and per-phase durations. Profiling adds overhead.
.\scripts\run_backend_tests.ps1 -Scope profile -Tests @('backend/tests/test_factor_diagnostics.py::test_demo_is_idempotent_and_covers_the_documented_states')

# Complete collection without execution, for collection/coverage inspection.
.\scripts\run_backend_tests.ps1 -Scope full -CollectOnly

# Complete backend regression, serial, without any test filter.
.\scripts\run_backend_tests.ps1 -Scope full
```

Use `-Python .\.venv\Scripts\python.exe` to pin the interpreter. Otherwise the
runner prefers `backend\venv`, then `.venv`, then PATH. Clear `PYTEST_ADDOPTS`
before invoking it; inherited hidden filters or worker options are rejected.
Full/fast scopes reject a narrower `-Tests` argument. Failures remain nonzero;
pytest's zero-selected-tests exit code is retained, including all-deselected
runs. Platform-specific skips remain visible in the summary (`-ra`).

## Isolation and Evidence

Each invocation creates a unique `quantlab-backend-<scope>-*` directory under
Windows TEMP, outside the repository. Nothing is automatically removed.

The runner copies current tracked and nonignored untracked working-tree bytes,
including uncommitted Phase 64 source, into a test-owned source snapshot. This is
not `git archive HEAD`. It excludes active databases/sidecars, local artifacts,
secrets, environments, and build caches, and refuses source links outside the
checkout. Tracked test fixtures outside application data directories remain
included. The copy is verified with SHA-256 per file. No `.git` directory is
copied; HEAD, status, diff, and source-byte hashes provide the tested identity.
Code that optionally inspects Git from the snapshot may report no Git metadata.

The child imports the snapshot backend, uses a unique pytest temporary root,
enables consistent UTF-8 mode for subprocess writers and readers, disables
bytecode/cache writes, and rejects SQLite access outside its run directory
(SQLite URI connections are intentionally unsupported by this test runner).
Subprocess CLI tests execute snapshot scripts with their existing explicit
temporary paths. This is isolation for the known suite, not an OS security
sandbox for arbitrary code. The active DB is only read as file bytes for before/
after hashes, size, and modification time; it is never opened with SQLite.

Evidence retained in each run directory:

- `snapshot-manifest.json`, `worktree.diff`: exact source identity and omitted paths.
- `runtime.json`, `pytest-config.json`: interpreter, installed versions, plugins,
  worker/thread environment, pytest options, and pytest import time.
- `collection.json`: ordered collected, selected, and deselected IDs plus startup/
  collection duration. Full mode checks that no collected test was deselected.
- `phases.jsonl`: setup/call/teardown duration and outcome for every test.
- `pytest.log`, `junit.xml`, `pytest-result.json`: complete output and pytest result.
- `runner-result.json`: subprocess exit, process/total/setup wall time, snapshot
  and source consistency, and active DB protection checks.
- `sqlite-violations.json`: forbidden SQLite attempts, even if caught by a test.
- `profile.pstats`: only for executed profile scope; not comparable to plain timing.

An interrupted run with no final result file is incomplete, never green. Retain
its partial logs instead of deleting evidence or repeatedly restarting full runs.

## Fixture Changes

Only Signal Ensemble, Factor Diagnostics, and Strategy Ensemble opt into the new
fixture. The fast lane contains their 76 explicitly audited `db_free` cases;
162 other cases in those files are deselected, not removed. SQLite is forbidden
for these pure tests, including attempts hidden by broad exception assertions.
Application-wide imports are deferred until API tests need them.

Other cases receive an independent writable database copied from one empty
session schema created in temporary storage using real `db.init_db()`. Connections
are closed and WAL checkpointed before copying. No active database, seeded demo,
computed metric, or expected answer is used as a template. `fresh_schema` cases
still run actual initialization/migrations. Other test modules retain their
existing fixtures. No bootstrap sample count or mathematical assertion changed.

The four experiment-review safety tests each run twice: application databases
initially absent and initially present with sentinel contents. Production DB
defaults/override and the working directory point to the controlled workspace;
the collector, renderers, CLI, and real/tampered pipeline use actual source.
Snapshots protect database bytes, sidecars, directory creation, artifacts, and
the existing store-integrity assertions. Negative controls demonstrate detection
of DB creation, DB modification, a sidecar, and an unauthorized artifacts directory.

## Measured Results Before Full Regression

Evidence from the initial timing pair is retained at:
`C:\Users\jimli\AppData\Local\Temp\quantlab-test-maintenance-d383fc6af68e4947b9d403e1f81817fb`.
The 15 explicit node selections expand to the same 18 cases in both runs.
Python 3.13.5 (Anaconda), pytest 9.0.3, NumPy 2.4.6, SciPy 1.17.1, pandas 3.0.3,
FastAPI 0.136.3, Pydantic 2.13.4, and httpx 0.28.1 were used. AnyIO was the only
auto-loaded pytest plugin. Execution was serial with unchanged, unset BLAS/OpenMP
thread overrides. NumPy reported OpenBLAS 0.3.31.188.0, MAX_THREADS=24.

| Same 18 cases | Before | After |
| --- | ---: | ---: |
| Passed | 18 | 18 |
| Exit code | 0 | 0 |
| Pytest elapsed seconds | 82.02 | 121.37 |
| Process wall seconds | 84.03 | 123.26 |
| Sum setup seconds (rounded duration output) | 24.51 | 7.56 |
| Sum call seconds | 52.65 | 111.17 |
| Sum teardown seconds (rounded) | 0.00 | 0.00 |

Separate pre-change collection took 4.60 seconds. Residual time outside the
reported phases includes imports, collection, and reporting; it is not test-body
execution. Setup work decreased, but **the comparable selection did not become
faster overall**. Demo body times increased from 31.92/19.17 to 59.32/44.47 seconds.
Deferring the application import also moves that one-time cost into the first
API test's setup/call rather than collection; per-test body totals include it.
No whole-suite speedup is inferred from this pair or from the smaller fast lane.

Targeted pre-change cProfile (two cases; profiling overhead included) measured
32.18 seconds in SQLite execute calls, 3.20 in commit, and 4.65 cumulative in two
schema initializations. Repeated schema setup and write-heavy demo integration
are measured costs. Antivirus, filesystem variability, broader numerical work,
network waits, and whole-suite bottlenecks were not established by that profile.

The four corrected safety tests plus negative controls passed 12 cases in 26.36s.
The initial corrected direct fast subset passed 76 cases in 3.30s; running via the
snapshot runner passed the same subset in 10.38s pytest time. These different
scopes/startup conditions are not an overall performance comparison.

The complete affected-file run (the three lab files, experiment review, and
maintenance infrastructure tests) passed 543 tests with one existing Windows
symlink-permission skip in 625.82s, without deselections. Its evidence is retained
at `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-41f2ctyh`.
This includes all 18 maintenance cases and both states of all four safety tests.
The final complete backend run is a separate gate, recorded by its own runner
result, not implied by these focused results.

## Superseded Historical Full Run and Focused Repair

The original maintenance task's single complete execution collected the same ordered 4,361 IDs as its
preflight, with zero deselections: **4,349 passed, 9 failed, 3 skipped**, exit 1,
in **3,001.18 seconds**. Process wall time was 3,005.59s; total runner wall time
including snapshot setup/checks was 3,009.20s. Setup accounted for 1,430.71s,
test calls for 1,532.10s, and teardown for 1.83s. This is not a green result or a
controlled whole-suite speedup comparison with the user's earlier run.
The largest remaining module was Signal Decay at 604.87s (174.85s setup,
429.98s calls). Portfolio Attribution used 216.92s and Factor Diagnostics 211.79s.
These are measured module totals, not a reason to skip their integration cases.

Evidence: `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-full-vnc52uuo`.
All eight absent/present database-safety cases passed. All three skips were
existing Windows symlink-permission cases. The active database, original source,
and copied source all passed their unchanged checks.

Nine subprocess-output tests failed because the initial runner set
`PYTHONIOENCODING=utf-8` while nested subprocess text readers still used Windows
CP950. Their reader threads raised `UnicodeDecodeError`, leaving captured output
unavailable. The runner now also sets `PYTHONUTF8=1`, records both settings, and
has a nested-Unicode-subprocess regression test. Production CLI code and its
assertions were not weakened. That task ran only focused follow-up checks after
the repair, respecting its one-full-run stopping rule. A repaired complete run
was unverified at that handoff. The user's later passing full run above now
supersedes this result; the failed full-run evidence is retained as history.

The focused UTF-8 follow-up passed **136 tests in 114.43s**, exit 0, without
warnings, across all eight subprocess-oriented/maintenance test modules,
including every previously failing test and the new encoding regression.
Evidence: `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-f1bor1t5`.
The encoding regression adds one case to the current collection. The active DB
and source protection checks also passed in this follow-up; none of these
focused results substituted for a full run. The later user-completed full run
is independently identified above and was not rerun during this review.

## Parallelism and Workflow

Keep serial execution. pytest-xdist is neither declared nor locally installed;
no dependency or global `-n auto` was added. Isolation was narrowed to three lab
modules, not audited across every module, CLI subprocess, shared default output,
and environment mutation in the entire suite. Two/four-worker safety and speed
were not measured, so there is no parallel speedup claim or scheduler choice.
CI remains its existing serial Python 3.11 full collection; it was not triggered.

During development, use focused tests first and the fast subset as a cheap extra
check. Before review, run all affected persistence/API/migration cases, inspect
collection IDs, then run the complete suite once on stable source. Preserve any
failure evidence and diagnose it; do not erase user data or weaken tests to make
the result green. Frontend checks remain scoped to frontend changes. Release
decisions still require their separate existing gates; a green backend run alone
does not authorize release, commit, tag, deployment, or Phase 65.
