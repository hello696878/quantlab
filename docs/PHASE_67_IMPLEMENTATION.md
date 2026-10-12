# Phase 67 Implementation Handoff

Date: 2026-10-07. Implementation task, not the separate independent review.

## Frozen Baseline and Authority

Started clean on `main` at `008760c46564839500e6108db84d8ffebab3f875`, with empty
index, no tracked diff and no nonignored untracked files. Verified annotated
`v4.84.0-reproducible-run-replay-environment-manifest-v1` resolves to that commit.
Its tag annotation and the user task report exact-doc CI **37482126828** passed
both jobs; CI was not retrieved or rerun in this task. Prior Phase 66 user build
and single Edge evidence remain inherited historical evidence, not Phase 67 tests.

Created authorized branch `phase67-futures-point-in-time-calendar-foundation`
from that exact baseline. HEAD is unchanged. VERSION becomes `4.85.0-dev`.
No staging, commit, push, tag, workflow, PR, service or Phase 68 operation.
Existing frozen Phase 65/66 evidence remains unchanged.

## As Built

Source audit and precise model/identity semantics are in
[FUTURES_POINT_IN_TIME_CONTRACT.md](FUTURES_POINT_IN_TIME_CONTRACT.md).
Calendar/roll/diagnostics/CLI assumptions are in
[FUTURES_DECLARED_CALENDAR_AND_VALIDATION.md](FUTURES_DECLARED_CALENDAR_AND_VALIDATION.md).

- Frozen Pydantic snapshot/bar/availability/license models; separate immutable
  revisions and inclusive explicit as-of policies, unknown knowledge retained.
- Finite complete declared calendar, real DST gap/fold checks, intervals/breaks,
  early close and overnight label semantics, material identity/provenance.
- Explicit keyword calendar scheduling in the existing roll/stitch engine;
  legacy paths and hashes unchanged, no second price engine.
- Retrospective classification plus separate decision-input availability audit;
  no causal/PIT-certification claim and no future daily-volume/OI execution fiction.
- Ingestion-seam typed local preview/disabled external selection. The source
  audit found no existing futures provider flag to reuse, so no second flag or
  unrelated Globe/yfinance integration was invented.
- Tiny invented ES M/U 2025 corpus, deliberate missing expected front quote,
  synthetic closure, early close/break/overnight intervals and retained correction.
- Read-only CLI, structured/human summaries, bounded parser/path refusals,
  separate physical/table/calendar/spec/envelope/derived identities.

No frontend, API contract, dependencies, workflows, Dockerfiles, backtest math,
models, registry schema, downloads or active datastore changes. Narrow shared
interfaces are only additive datastore functions/keywords; lower-level existing
safe local reads and bounded JSON identity are reused unchanged.

## Verification Ledger

Local runtime inspected: existing `C:\quantlab\.venv\Scripts\python.exe`,
Python **3.13.5**, Pydantic **2.13.4**; real Chicago timezone source is installed
`tzdata` **2026.2**. It is not pinned and this is not Python 3.11 evidence.
No packages were installed or upgraded. CI remains the separate 3.11 gate.

Preserved setup attempts:

1. Focused runner invoked with `tests/...` instead of required repository-relative
   `backend/tests/...` targets: exit 1 before any snapshot/test, explicit target
   validation error. Corrected only invocation.
2. Correct target invocation under default sandbox: exit 1 before tests; external
   temp evidence write denied. Directory
   `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-b65hpswg`
   was retained, not deleted. Normal approval was then used; no runner edits.
3. First executed focused snapshot at
   `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-rqsuj0ni`:
   **79 passed, 1 skipped, 2 setup/teardown errors**, pytest 28.15s,
   runner total 59.165s, pytest/process/outer exit 1. One oversized CSV parameter's
   automatic node ID exceeded Windows' 32767-character environment-variable bound.
   Added short parameter IDs, without changing data/assertions or adding skips.
   Skip: `physical symlink unavailable in this local context: 1314`.
   Runner source/snapshot/active-DB protection checks were all true.

4. Expanded interim regression at
   `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-yzprc1b6`:
   **373 passed, 1 skipped, 374 selected, 0 deselected**, pytest summary 130.88s
   (machine pytest wall 131.000s), runner 155.577s, all exits 0 and protection
   checks true. This predates final typed-build/Panama edge strengthening.
5. Strengthened-edge run at
   `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-y9c2pf6u`:
   **372 passed, 2 failed, 1 skipped, 375 selected**, pytest 92.49s, runner
   107.522s, exits 1, protection checks true. Boolean/infinite build-input cases
   exposed validation order: legacy normalization preceded strict typed checks.
   Fixed only opt-in declared-mode ordering; assertions were not weakened.
6. **Final stable implementation run** at
   `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-swmqtk6x`:
   **374 passed, 1 skipped, 375 collected/selected, 0 deselected**, no failures
   or setup/teardown errors. 96 new nodes (95 pass, 1 skip), 279 existing nodes
   (all pass). Pytest summary **126.36s**, machine pytest wall **126.575s**;
   snapshot setup **7.884s**, child process **128.390s**, total runner **152.740s**.
   Pytest process, machine pytest and outer runner exits **0**.
   Skip, unchanged across executed runs:
   `physical symlink unavailable in this local context: 1314` (Windows privilege).
   Real hardlink refusal executed; Linux physical-symlink execution remains pending.

Machine artifacts retained per run: collection, per-node/phase outcomes,
verbose durations, skip reasons, pytest logs, JUnit XML, runtime, exact snapshot
manifest/worktree diff, SQLite audit and runner result. No successful run is
fabricated by combining different snapshots. The final run is one serial
protected snapshot; no source edits occurred while any protected run was active.

Final runtime: Windows 11 build 26100, existing repository Python 3.13.5;
fastapi 0.136.3, uvicorn 0.48.0, python-multipart 0.0.29, pandas 3.0.3,
numpy 2.4.6, scipy 1.17.1, yfinance 1.4.0 (metadata only; no fetch),
pydantic 2.13.4, python-dateutil 2.9.0.post0, pytest 9.0.3, httpx 0.28.1,
tzdata 2026.2. Full installed environment is retained in `runtime.json`.

Exact final command (earlier expanded runs used the same 13 targets;
the first executed run used only the first three):

```powershell
& .\scripts\run_backend_tests.ps1 -Scope focused -Python C:\quantlab\.venv\Scripts\python.exe -Tests @(
  'backend/tests/test_futures_pit_contract_calendar.py',
  'backend/tests/test_futures_pit_revisions.py',
  'backend/tests/test_futures_pit_roll_adapter.py',
  'backend/tests/test_futures_daily_bar.py',
  'backend/tests/test_futures_csv_fixtures.py',
  'backend/tests/test_futures_continuous.py',
  'backend/tests/test_store.py',
  'backend/tests/test_instruments_registry.py',
  'backend/tests/test_ingest_local_futures_csv.py',
  'backend/tests/test_build_local_continuous_futures.py',
  'backend/tests/test_build_local_continuous_futures_ym.py',
  'backend/tests/test_local_futures_ml_pipeline.py',
  'backend/tests/test_run_replay_identity_review.py'
)
```

CLI acceptance executed **inside those tests**, not repeated merely for another
summary: demo returns warning/exit 1 with real invented input findings,
17 selected observations, one June 13 roll, earlier close 100 / later 102;
no-arguments/external return invalid/exit 2; explicit valid local selection
returns pass/exit 0; unknown price basis returns incomplete/exit 3.

No whole-tree backend, frontend tests/typecheck/build/discovery/browser,
optional PyArrow/container, audit or application-service check was run.

## Publication Boundary

Next authorized gate is independent review of the resulting exact diff, then
user-created implementation/review commits and exact-commit CI/publication.
The future tag is
`v4.85.0-futures-point-in-time-contract-calendar-foundation-adapter-spec-v1`;
it does not exist from this task. Suggested later subjects:

- `Add futures point in time data contract calendar foundation adapter specification v1`
- `Review futures point in time data contract calendar foundation adapter specification v1`

## Protection and Gate Decisions

- Final runner: `worktree_bytes_unchanged`, `snapshot_bytes_unchanged`,
  `active_db_unchanged`, `child_evidence_complete` all **true**;
  `sqlite-violations.json` is `[]`. Tests use snapshot/test-owned storage.
- Initial independent protection manifest:
  `C:\Users\jimli\AppData\Local\Temp\quantlab-phase67-088e07c0c27d4b96be4d4d0839280fc9\baseline.json`.
  All 43 recorded active-data/frozen screenshot files retain exact hash, size
  and modification time; index bytes identical. No intended source data is
  written or cleaned. This is a bounded recorded inventory, not a claim about
  every unrelated file on the user's computer.
- Scientific/runtime source, tests, fixtures, VERSION and shared inputs match
  the final protected snapshot; only handoff/current-status documentation is
  updated after testing to record evidence. Earlier results are explicitly separate.
- Tracked diff check and new-file trailing-whitespace checks pass. Pending set
  is exactly 29 paths below, no staged paths; no runtime binaries, user data,
  credentials, caches, logs, build/browser output or screenshots in that set.
  Existing LF/CRLF warnings were observed, without Git configuration changes,
  blanket normalization or staging. Frozen Phase 65/66 reports are unchanged.
- Local strict/calendar/revision/roll/CLI regression gate: **passed with one
  honestly retained platform skip**. Independent review: **pending**. Exact
  committed Python 3.11 CI, including physical Linux symlink: **pending**.
  Provider/official-calendar/PIT-certification capabilities: **not implemented**,
  not failed gates disguised as green. No frontend change means no new local
  frontend/browser gate was requested or executed.

**Safe to keep as a bounded local foundation and ready for independent review.**
Not a release/publication or real-provider/official-calendar/PIT certification.

## Exact Pending Inventory and User-Only Staging Plan

**29 paths: 9 modified, 20 new.** This implementation handoff is included.
The index remains empty; these paths were not staged. Before later user staging,
recheck branch/base, exact pending membership, independent-review amendments and
byte evidence; do not substitute a historical inventory or stage extra artifacts.
Only the following explicit command block is a later user plan, **not executed**:

```powershell
$phase67Paths = @(
  # Modified (9)
  'CHANGELOG.md',
  'README.md',
  'STOP_POINT.md',
  'TASKS.md',
  'VERSION',
  'backend/app/datastore/futures_continuous.py',
  'backend/app/datastore/ingest.py',
  'docs/FORWARD_ROADMAP_PHASES_63_70.md',
  'docs/VERSION_MANIFEST.md',
  # New (20)
  'backend/app/futures_pit/__init__.py',
  'backend/app/futures_pit/adapter.py',
  'backend/app/futures_pit/calendar.py',
  'backend/app/futures_pit/diagnostics.py',
  'backend/app/futures_pit/models.py',
  'backend/app/futures_pit/revisions.py',
  'backend/app/futures_pit/roll.py',
  'backend/tests/fixtures/futures_pit/bars.csv',
  'backend/tests/fixtures/futures_pit/calendar.json',
  'backend/tests/fixtures/futures_pit/correction-metadata.json',
  'backend/tests/fixtures/futures_pit/correction.csv',
  'backend/tests/fixtures/futures_pit/invalid/boolean-price.csv',
  'backend/tests/fixtures/futures_pit/metadata.json',
  'backend/tests/test_futures_pit_contract_calendar.py',
  'backend/tests/test_futures_pit_revisions.py',
  'backend/tests/test_futures_pit_roll_adapter.py',
  'docs/FUTURES_DECLARED_CALENDAR_AND_VALIDATION.md',
  'docs/FUTURES_POINT_IN_TIME_CONTRACT.md',
  'docs/PHASE_67_IMPLEMENTATION.md',
  'scripts/validate_futures_point_in_time.py'
)
git --literal-pathspecs add -- @phase67Paths
```

Do not execute the whole Markdown document as a script. This plan does not
authorize Codex to stage, commit, push, tag or implement Phase 68.
