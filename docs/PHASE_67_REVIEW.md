# Phase 67 Independent Adversarial Review

Date: 2026-10-12. One independent review and verified-defect-fix handoff.
No staging, commit, push, tag, workflow trigger, application service or Phase 68.

## Exact target and initial state

- Attached branch: **main**.
- Implementation: **66aa3da7eb79ce6b1f07000e90d1dc930b65df41**.
- Exact subject: **Add futures point in time data contract calendar foundation adapter specification v1**.
- Single parent: **008760c46564839500e6108db84d8ffebab3f875**.
- Frozen annotated tag **v4.84.0-reproducible-run-replay-environment-manifest-v1**
  resolves to that parent.
- VERSION: **4.85.0-dev**, unchanged by this review.
- Initially empty index, no tracked working diff or nonignored untracked files.
- Read root AGENTS.md and CLAUDE.md; no nested instruction files found.
  The explicit current task governs the older Phase 1 scope language.
- Reviewed the complete committed implementation diff collectively, actual
  source/consumers/tests, implementation ledger, both contract/runbook documents
  and the Phase 67 roadmap. Located the inventory by content: **29 exact paths,
  9 modified / 20 added**, equal to the implementation commit's changed set.
  No Markdown staging section was executed.

Exact implementation inventory, relative to its parent:

~~~text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M VERSION
M backend/app/datastore/futures_continuous.py
M backend/app/datastore/ingest.py
A backend/app/futures_pit/__init__.py
A backend/app/futures_pit/adapter.py
A backend/app/futures_pit/calendar.py
A backend/app/futures_pit/diagnostics.py
A backend/app/futures_pit/models.py
A backend/app/futures_pit/revisions.py
A backend/app/futures_pit/roll.py
A backend/tests/fixtures/futures_pit/bars.csv
A backend/tests/fixtures/futures_pit/calendar.json
A backend/tests/fixtures/futures_pit/correction-metadata.json
A backend/tests/fixtures/futures_pit/correction.csv
A backend/tests/fixtures/futures_pit/invalid/boolean-price.csv
A backend/tests/fixtures/futures_pit/metadata.json
A backend/tests/test_futures_pit_contract_calendar.py
A backend/tests/test_futures_pit_revisions.py
A backend/tests/test_futures_pit_roll_adapter.py
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/FUTURES_DECLARED_CALENDAR_AND_VALIDATION.md
A docs/FUTURES_POINT_IN_TIME_CONTRACT.md
A docs/PHASE_67_IMPLEMENTATION.md
M docs/VERSION_MANIFEST.md
A scripts/validate_futures_point_in_time.py
~~~

## Severity-ranked confirmed findings and fixes

References are current reviewed source lines. All listed findings are fixed;
no unresolved confirmed P0/P1/P2 finding remains within the delivered scope.

| Rank | Confirmed behavior and consequence | Correction and regression |
| --- | --- | --- |
| P2 | Pydantic/OS exception strings exposed submitted values/paths and could make large responses. Default argparse failures echoed arbitrary argv outside the JSON boundary. | backend/app/futures_pit/adapter.py:98 bounds/sanitizes failures; scripts/validate_futures_point_in_time.py:24 and :111 return invalid JSON/exit 2. Exact safe refusal messages remain useful. Real subprocess cases cover a synthetic secret, 200 extra fields and a 16K argument; help still exits 0. |
| P2 | Extreme offset instants overflowed UTC conversion; unknown roots raised InstrumentError outside normal validation, producing CLI tracebacks. | backend/app/futures_pit/models.py:40 and :103 convert these to validation errors. Public boundaries handle them defensively. Both offset extremes, unknown root and malformed contract are tested through real model/CLI paths. |
| P2 | Generic root IDs permitted colon/drive/stream syntax before registry lookup. Windows joining could interpret a different-drive ID as a drive-relative spec path before later root rejection. | backend/app/futures_pit/models.py:103 requires 1..10 canonical uppercase letters/digits before lookup. Four spy regressions prove these inputs never reach the registry. The legacy registry/economics are unchanged. |
| P2 | Declared-mode uint64 volume at 2**63 passed dtype checks before legacy int64 casting could wrap it; unsafe numeric magnitudes were not bounded consistently. Huge diagnostic integers could escape as OverflowError. | backend/app/futures_pit/roll.py:17 bounds opt-in prices/volume/OI before normalization. Diagnostics convert overflow to a finding. Tests cover both roll/build paths, unsafe uint64/huge values and the exact safe boundary. No legacy tightening. |
| P2 | decision_eligibility accepted a different material calendar with the same ID/version. Moving its effective start past known receipts could qualify an event after its original start. | backend/app/futures_pit/roll.py:105 checks the event calendar fingerprint. Regression retains original June 12 22:00Z start and refuses a substituted June 13 03:30Z start at a 03:15Z cutoff. The audit remains retrospective. |
| P2 | A valid incoming v2->v3 batch called v3 ambiguous when its explicit parent was in the same incoming snapshot, although selection accepted that chain. | backend/app/futures_pit/revisions.py:61 recognizes parents in both snapshots, preserving contradiction precedence. Four existing/new-key and forward/reversed cases require intended statuses and final close 103. as_of still validates the complete graph. |
| P2 | Continuous validation compared only supplied rows. Dropped leading/trailing sessions could evade errors because gap checks used the shortened range. A genuine one-row series could have no findings. | backend/app/futures_pit/diagnostics.py:23 warns on insufficient history; :74 checks all expected built timestamps. Independent June 9/20 truncation assertions require errors, preserve inputs and keep a one-quote series insufficient. |
| P2 | Timezone provenance could borrow a version from a different TZPATH root than the requested zone, and used a stale imported TZPATH tuple. | backend/app/futures_pit/calendar.py:25 reads the live path and only the supplying root's version. Real copied Chicago TZif fixtures verify correct attribution, unknown version without borrowing and both UTC folds. Cached origin remains disclosed as unknown. |
| P3 | Current handoffs named the old implementation branch/base as current HEAD and review pending. Contract wording incorrectly promised invariance for newly appended already-eligible corrections. | Current docs now identify main/implementation SHA, separate review evidence and pending commit/CI. Invariance is restricted to compatible valid after-cutoff revisions. Historical implementation/Phase 66 reports are preserved. |

Five new review test files provide **51 executed passing nodes**:
calendar 2, CLI 18, diagnostics 4, revisions 18, roll 9.
A second static review found no additional confirmed defect.
No pre-fix execution was performed: old failure mechanisms were established
from the actual source and independently specified regression inputs.

## Snapshot, identity, availability and revisions

Public path: explicit CSV/JSON -> guarded bounded buffers -> strict declarations
-> immutable Snapshot/DeclaredCalendar -> validate_binding -> revision/as-of
-> market-only legacy frame -> existing roll/stitch engine -> diagnostics/CLI.
Metadata is validated/retained separately before the legacy twelve-column bridge,
not silently discarded by normalization.

Snapshot, bars, availability, license and calendar children are frozen models;
collections are tuples, not stored mutable DataFrames/dicts. New tests mutate
caller nested dictionaries/lists, exported model_dump and returned legacy frames.
Stored values and recomputed table/envelope/legacy hashes remain unchanged.
No mutable cached scientific hash payload was found. This covers validated public
use, not deliberate Python bypasses such as model_construct,
model_copy(update=...) or object.__setattr__.

Physical SHA-256 binds the bytes actually parsed. Market, calendar, envelope and
derived identities have separate namespaces/material. Legacy raw hashing keeps
its existing twelve-significant-digit CSV normalization; it is not the new
provenance identity. Envelope binds actual spec/calendar/knowledge/license
material; CLI derived identity binds retained envelopes, selected revisions,
mode/cutoff and roll/adjustment policy. Display IDs, whitespace-independent
identity and self-consistent checksums do not attest truthful claims.

Trading labels, source field availability and local receipt remain separate.
Inspection time never fills historical receipt. Null OI is not zero; the default
source boundary requires all three field availability times. Declared-source
and local-observed selection differ, are inclusive and UTC-normalized.
Independent one-microsecond-before/exact/offset-equivalent assertions passed.

Selection deduplicates identical revisions and refuses contradictory versions,
missing parents, roots/branches, ties/non-increasing known times and disconnected
cycles. No lexical-ID/input-order winner. A valid compatible revision after the
chosen cutoff preserves earlier selection; newly supplied already-eligible
evidence may change it. Row-level compare is not graph certification.
Lower-level as_of callers must first bind snapshots to their material
calendar/spec; public preview/CLI do. No authentic publication, complete dataset
or independently reconstructed historical receipt is established.

## Calendar and retrospective roll conclusions

Every covered date is classified once. Expected opens, declared closures,
missing expected bars and outside coverage remain distinct. Invented June 11
closure is not missing data; June 10 missing front data is. Inclusive
count/between/on_or_before and strict previous/next conventions passed.
Midnight-UTC legacy trading labels are not reinterpreted as real Chicago closes.

UTC-normalized intervals/breaks reject overlap/contradictions. Overnight labels,
early closes, 23/25-hour UTC durations and unchanged session counts are tested.
Real DST gap refusal and fold 0/1 independently yield 2025-11-02 06:30Z / 07:30Z.
No missing-zone fallback to UTC/fixed offsets. Calendar hashes bind material and
declarations; later calendar declarations are not automatically historical knowledge.

Declared confirmation uses expected sessions: missing observations break a
streak; closures do not. Prior/effective sessions come from the calendar; both
contracts' seam/effective quotes are required, otherwise refusal rather than
sliding. Fallback retains calendar-day units. Expiry is existing spec-derived
third-Friday, not authoritative holiday-adjusted exchange expiry.
No-calendar/default source paths and legacy hash algorithms remain unchanged;
relevant existing regressions passed.

All schedules and back-adjustment remain **RETROSPECTIVE**. Corpus June 12 OI
arrives June 13 02:00Z, after the June 12 22:00Z effective start, and fails
decision eligibility. Earlier synthetic declarations and receipt differences
are separately tested. Decision/effective session instants are exposed, but no
causal execution engine or closing-quote availability at session opening is
claimed. Future back-adjustment can alter earlier levels; no invalid full
adjusted-history prefix invariant is imposed.

## Continuous diagnostics and real public local acceptance

The existing builder is the only stitching/adjustment engine. Independent seam
assertions use old close 100, new prior 110, new roll close 111: ratio 1.1,
Panama gap 10. Raw 100->111 contains a spread, not a tradable 11% return.
The separate retained correction changes old close 100->102.

Diagnostics rebuild/compare actual selected material, including all built rows,
order/duplicates, gaps/closures, transitions/flags, raw/adjusted fields, finite
factors, same-contract spikes and seams. Valid nonpositive Panama levels warn.
Thresholds flag only: no clipping, interpolation, filling or price rewrite.
A single quote cannot receive an empty clean result.

The actual ingestion seam reuses local_path/pinned_directory/_read: explicit
local regular files, link/reparse/hardlink refusal, bounded reads and retained
parent identities. JSON rejects duplicate keys/depth/nonfinite/oversized values;
CSV has exact unique columns, cell/row bounds and strict numeric syntax.
Physical hashes use parsed buffers; all three buffers are reread for mutation.
This is not an atomic multi-file/adversarial-filesystem snapshot guarantee.

No provider fallback/enable flag/network client, arbitrary locator dereference,
archive extraction, executable serialization, recursive scan, export/default
output or database initialization exists in this path. External requests fail
before reads/network regardless of environment flags. Provider-looking metadata
does not activate acquisition. License/provenance remain unverified declarations;
no approved vendor, legal certification or official calendar claim.

Actual CLI/library acceptance ran within the protected suite, including **17 new
real subprocess invocations from an external temporary cwd**, preserving source
bytes/mtime and directory inventories. Valid supplied input exits 0; demo exits 1
with 17 observations, June 13 roll and 100/102 restatement; invalid/no-input/
disabled exit 2; unknown basis exits 3. Help exits 0. No redundant standalone CLI
run or mocked whole-path acceptance. No export exists to have output collisions;
unsupported output arguments are refusals.

## Inherited implementation evidence, not new review runs

PHASE_67_IMPLEMENTATION.md and its machine artifacts remain unchanged:

| Attempt/snapshot suffix | Reported result |
| --- | --- |
| Wrong tests/... target form | Exit 1 before snapshot/tests; invocation corrected. |
| Correct targets/default sandbox | Exit 1 before tests; temp write denied; b65hpswg retained. |
| rqsuj0ni | 79 passed / 1 skipped / 2 setup-teardown errors; pytest 28.15s; runner 59.165s; reported exits 1. Automatic node ID exceeded Windows environment bound; only short IDs corrected. |
| yzprc1b6 | 373 passed / 1 skipped / 374 selected / 0 deselected; pytest 130.88s, machine 131.000s; runner 155.577s; exits 0. Predates final typed/Panama strengthening. |
| y9c2pf6u | 372 passed / 2 failed / 1 skipped / 375 selected; pytest 92.49s; runner 107.522s; exits 1. Strict opt-in validation order fixed afterward. |
| swmqtk6x final implementation | 374 passed / 1 skipped / 375 selected / 0 deselected; pytest 126.36s; machine 126.575s; setup 7.884s; child 128.390s; runner 152.740s; pytest/machine/outer exits 0. 95 new passes + 279 existing passes; symlink skip 1314. |

Implementation evidence reports source/snapshot/DB protections true and a bounded
43-path data/screenshot protection inventory. These are distinct snapshots,
not a combined full-suite pass or execution of the physical skip.
They do not verify reviewer fixes. Phase 66 CI/build/Edge statements remain
historical; not retrieved, triggered or rerun by this review.

## Newly executed final focused review

One serial protected execution, with no source/docs edits during the run.
Snapshot includes the uncommitted fixes and all five new test files, not a
HEAD-only archive.

Evidence root:
**C:/Users/jimli/AppData/Local/Temp/quantlab-backend-focused-qau0ckrg**

Snapshot manifest SHA-256:
**5d79912ca0dfe58717ca4840a26a732c1a52915cebbff4dce8868ac48db9acb1**

Exact inspected-runner command:

~~~powershell
& .\scripts\run_backend_tests.ps1 -Scope focused -Python C:\quantlab\.venv\Scripts\python.exe -Tests @(
 'backend/tests/test_futures_pit_contract_calendar.py',
 'backend/tests/test_futures_pit_revisions.py',
 'backend/tests/test_futures_pit_roll_adapter.py',
 'backend/tests/test_futures_pit_review_calendar.py',
 'backend/tests/test_futures_pit_review_cli.py',
 'backend/tests/test_futures_pit_review_diagnostics.py',
 'backend/tests/test_futures_pit_review_revisions.py',
 'backend/tests/test_futures_pit_review_roll.py',
 'backend/tests/test_futures_daily_bar.py',
 'backend/tests/test_futures_csv_fixtures.py',
 'backend/tests/test_futures_continuous.py',
 'backend/tests/test_store.py',
 'backend/tests/test_instruments_registry.py',
 'backend/tests/test_ingest_local_futures_csv.py',
 'backend/tests/test_build_local_continuous_futures.py',
 'backend/tests/test_build_local_continuous_futures_ym.py',
 'backend/tests/test_local_futures_ml_pipeline.py'
)
~~~

No Phase 66 replay target was rerun. The implementation's 50-node
run_replay_identity_review target is omitted, and 51 new review nodes added.
This explains 376 rather than 375 selected nodes.

- **376 collected/selected, 0 deselected; 375 passed, 1 skipped**.
  All 376 setup/teardown phases passed; no failures/errors.
- New review files: 51 passes. Original Phase 67 files: 95 passes / 1 skip.
  Existing futures/store/ingest/instrument/local-pipeline files: 229 passes.
- Pytest printed summary: **133.26s (0:02:13)**.
- Machine pytest wall **134.4721591998823s**; startup/collection
  **18.671881299931556s**.
- Snapshot setup **18.902384100016207s**; child wall **136.5995176997967s**;
  total runner **159.70819709985517s**.
- Machine pytest exit **0**, pytest process exit **0**, outer runner/tool
  process exit **0**, recorded separately.
- worktree_bytes_unchanged, snapshot_bytes_unchanged, active_db_unchanged,
  child_evidence_complete: **true**. sqlite-violations.json is **[]**.
- Collection, per-phase/node results, durations, skips, JUnit, logs, exact source
  manifest/diff, runtime/protection artifacts retained. No cleanup.

Existing runtime: **C:/quantlab/.venv/Scripts/python.exe**, Python **3.13.5**
Anaconda-packaged, MSC v.1929 64-bit AMD64; Windows-11-10.0.26100-SP0, one worker.
Pydantic 2.13.4, pandas 3.0.3, numpy 2.4.6, scipy 1.17.1, pytest 9.0.3,
PyYAML 6.0.3, fastapi 0.136.3, uvicorn 0.48.0, httpx 0.28.1,
python-multipart 0.0.29, python-dateutil 2.9.0.post0; yfinance 1.4.0 metadata
only, no fetch. Full package/environment metadata retained in runtime.json.

Actual timezone source inspected: TZPATH is C:/quantlab/.venv/share/zoneinfo,
with no Chicago file. Fallback **tzdata 2026.2**, IANA **2026b**, supplies real
Chicago TZif bytes, SHA-256
**c27b739ff46a7df0594e120d725b439217e11e44ea9a50cdc49130383b5482e7**.
No pin/installation implied. Split-root tests use owned copies, restore the
path/clear their test cache. Previously cached object origin is not tracked.

## Platform gap and operational attempts

Capabilities inspected before final verification, without installation:

- Existing Windows Python **3.11.9**, but **pytest absent**; no 3.11 tests
  executed or borrowed runtime packages substituted.
- Initial sandbox WSL enumeration: E_ACCESSDENIED. Permitted read enumeration
  then exited 0: Ubuntu and docker-desktop were stopped.
- Existing Ubuntu probe: /usr/bin/python3 **3.12.3**, GCC 13.3.0.
  No python3.11 found at the inspected command path or /usr/bin/python3.11.
  Dependency probe exit 0: pytest/pydantic/pandas/numpy/fastapi/yfinance absent.
  It cannot execute this scope as installed; it is not relabeled Python 3.11.
- Docker client **29.5.2**, desktop-linux; engine pipe unavailable.
  Version/image-list probes failed to connect. No engine/application service
  started, image pulled/built, package installed, privilege/Developer Mode changed
  or Docker reset.
- A sandbox read of the elevated run's new evidence was denied; permitted read
  succeeded. This was evidence access, not another test execution.
- One report-authoring tool call failed before writing (JavaScript ReferenceError);
  corrected without file loss, source changes or any test rerun.
- Exactly one review test execution occurred, passed with the retained skip.
  No failed review test run was discarded or combined with another result.

Pending physical operation:
**backend/tests/test_futures_pit_roll_adapter.py::test_physical_symlink_refused**
(source line 221, skip at 226):
**physical symlink unavailable in this local context: 1314**.
Real hardlink refusal/mutation checks executed; no mocked physical link.
Linux physical-symlink execution and final Python 3.11 coverage remain pending
in an appropriately provisioned isolated environment/exact-commit CI.

Retain real timezone IDs at that gate:
**test_futures_pit_contract_calendar.py::test_real_chicago_dst_gap_fold_and_offset**,
**test_futures_pit_contract_calendar.py::test_dst_duration_does_not_change_session_count**,
and both **test_futures_pit_review_calendar.py** cases.
Their Windows 3.13 checks passed; Linux 3.11 execution is not established.

## Final protection and REVIEW inventory

The existing 43-path protection inventory was refreshed at review start and
compared after work: exact SHA-256, size and mtime retained. Index bytes unchanged,
staged set empty. VERSION, frozen screenshots, historical implementation/Phase 66
reports and scientific fixtures unchanged. Tests did not open the active database;
SQLite audit violations empty. No generated/runtime/user-data/credential files
are in the pending set.

Scientific source/tests match the completed protected snapshot. Only six current
status documents and this report were written after backend verification; both
semantic contract/runbook corrections were already in the tested snapshot.
**This review report was edited after backend verification.**
No later code/test changes invalidate that focused result. Final documentation
bytes still await exact-review-commit CI; this is not a whole-tree pass.

Exact REVIEW pending set: **21 paths = 15 modified / 6 new**, all unstaged.
Separate from the 29 already-committed implementation paths:

~~~text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M backend/app/futures_pit/adapter.py
M backend/app/futures_pit/calendar.py
M backend/app/futures_pit/diagnostics.py
M backend/app/futures_pit/models.py
M backend/app/futures_pit/revisions.py
M backend/app/futures_pit/roll.py
M docs/FORWARD_ROADMAP_PHASES_63_70.md
M docs/FUTURES_DECLARED_CALENDAR_AND_VALIDATION.md
M docs/FUTURES_POINT_IN_TIME_CONTRACT.md
M docs/VERSION_MANIFEST.md
M scripts/validate_futures_point_in_time.py
A backend/tests/test_futures_pit_review_calendar.py
A backend/tests/test_futures_pit_review_cli.py
A backend/tests/test_futures_pit_review_diagnostics.py
A backend/tests/test_futures_pit_review_revisions.py
A backend/tests/test_futures_pit_review_roll.py
A docs/PHASE_67_REVIEW.md
~~~

Tracked diff/new-file whitespace checks passed. No staging command executed;
the inventory supports a later separately authorized Git action.

## Decision, limitations and remaining gates

**Safe to keep: yes**, as a bounded local declared-data foundation.
**Ready for the user's review commit: yes**, with the disclosed platform skip
and exact-commit CI gate. No release/provider/official-calendar/PIT certification.

No additional confirmed defect or unconfirmed hypothesis is promoted to a finding.
Known limits: unverified availability/rights/provenance, finite synthetic coverage,
spec-derived expiry, retrospective decisions/history, non-atomic reads and
ZoneInfo cache-origin uncertainty. Missing broader provider/causal capabilities
are explicitly deferred, not review failures.

Next: user-created review commit, expected subject
**Review futures point in time data contract calendar foundation adapter specification v1**,
then **final exact-review-commit Python 3.11/Linux whole-tree CI**, including
physical symlink and real DST cases. Existing CI is unchanged; its configured
normal jobs may run when the user publishes. No new local frontend/typecheck/
discovery/browser/production-build gate is justified because frontend/build
inputs are unchanged; none was executed. Local public CLI acceptance is covered
above; future platform claims must name their actual source/runtime.

Future user tag:
**v4.85.0-futures-point-in-time-contract-calendar-foundation-adapter-spec-v1**.
Not created here. No second report/finalization task, staging, commit, push, tag,
deployment or Phase 68 was performed.

## Post-review five-case platform verification (2026-10-12)

This dated section supersedes only the earlier pending review-commit/CI/platform
status. All original review findings, failures, historical counts, runtime and
protection evidence above are retained. No implementation or independent-review
cycle was repeated. The new verification passed; only the seven authorized
current-status/handoff documents are changed for documentation staging.

### Existing CI and historical Windows evidence remain separate

The task supplied completed exact-review-commit CI evidence, not newly retrieved
or rerun in this verification: run **38208475431**, attempt **1**, SHA
**92498c531e2a2864b40eb6a0c669b39a4760311a**. Backend job **114677128831** and
frontend job **114677128539** are completed/success. The supplied retrieved
backend log records Ubuntu **24.04.5**, CPython **3.11.17**,
`python -m pytest -q`, **4849 passed / 18 skipped in 561.39s**. Its quiet summary
does not identify skipped nodes/reasons; the supplied artifact listing is empty.
No assertion is made that these skips are optional dependencies or that the
physical-symlink case passed in CI. No CI process exit code is inferred.

The historical Windows/Python 3.13.5 protected review remains **375 passed /
1 physical-symlink capability skip / 376 selected**, with its exact durations,
recorded exits, real timezone provenance and protection evidence above unchanged.
The new five passes below are not added to 4849 or 375 to invent a suite result.

### Source, archive and disposable environment identity

Before work and after tests, `main` was clean, the index empty and HEAD exactly
**92498c531e2a2864b40eb6a0c669b39a4760311a** (the committed review).
VERSION stays **4.85.0-dev**. The previous attempt stopped before archives,
installation, containers, tests, edits or staging: both sandbox and approved
Docker probes exited **1**, with missing `dockerDesktopLinuxEngine` pipe, not
an established permission denial. The user then started Docker Desktop.
One approved connectivity recheck on resume exited **0**: Docker Desktop
**4.75.0 (227598)**, Engine/client **29.5.2**, `desktop-linux`, Linux/amd64.

External task root, retained without deleting prior evidence:

**C:/Users/jimli/AppData/Local/Temp/quantlab-phase67-fivecase-3c60e0898c634d8da249a799182df5c5**

`input/source.tar` was produced with Git's binary output option, not PowerShell
text redirection:

~~~powershell
git -c core.autocrlf=false archive --format=tar --output=<task-root>/input/source.tar 92498c531e2a2864b40eb6a0c669b39a4760311a
~~~

- Committed tree: **54abcd04163fb4d0835d0ba3c4ca3cde98b15876**.
- Archive SHA-256: **b3949de85f3db0dd991b44f9834cef8e6be04a7319f262b19f5c1c7df753f39a**;
  **23,080,960 bytes**, archive command exit **0**, **2.3729104s**.
- Archive global commit comment matches HEAD. All **1,143** committed blob
  paths, Git blob identities and executable-mode classifications match the
  recorded Git tree, with no extra/missing members. Extracted file SHA-256/size
  identities match those verified archive bytes. No live working-directory copy.
- Official **python:3.11-slim-bookworm**, image ID and repo digest
  **sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89**;
  Linux/amd64, image created **2026-10-06T02:04:13.792985192Z**.
  Pull exit **0**, **46.9827016s**; image inspect exit **0**.
- Actual runtime: Debian GNU/Linux **12 (bookworm)**, CPython **3.11.17**
  (GCC **12.2.0**), `/usr/local/bin/python`, kernel
  **6.6.87.2-microsoft-standard-WSL2**, glibc **2.36**, one serial worker.
  This is not a reconstruction of the Ubuntu GitHub runner.
- Declared backend requirements installed only inside this disposable container:
  fastapi **0.143.0**, uvicorn **0.54.0**, python-multipart **0.0.32**,
  pandas **3.0.6**, numpy **2.4.6**, scipy **1.17.1**, yfinance **1.7.0**,
  pydantic **2.14.1** / pydantic_core **2.50.1**, python-dateutil **2.9.0.post0**,
  pytest **9.1.1**, httpx **0.28.1**, PyYAML **6.0.3**, pluggy **1.6.0**,
  pip **24.0**. Full installed metadata is retained in `evidence/environment.json`
  and the existing runner's `runtime.json`. No PyArrow installation was requested.
  pip's container-root warning is retained; no host/user Python was installed into.

The uniquely named container was
`quantlab-phase67-fivecase-3c60e0898c634d8da249a799182df5c5`, full ID
**5b2594dc3d570b05781657cb2fa662c02f61425c74e17c5e1794f52ea1b7f8ca**.
Its recorded invocation uses the exact image ID and only two bind mounts:
task-owned `input` to `/input` read-only and task-owned `evidence` to `/evidence`
writable. No live checkout, active database, home, credentials, socket, extra
volume, privileged mode or exposed port. Source extraction is
`/work/run/source`; basetemp is `/work/run/pytest-tmp`. Both are **overlayfs**,
not Windows bind mounts. No application service was started.

### Actual timezone material before execution

Real **America/Chicago** came from the image's system TZPATH root
**/usr/share/zoneinfo**, file **/usr/share/zoneinfo/America/Chicago**.
Supplying `tzdata.zi` reports IANA **2026c**; system package version is
**2026c-0+deb12u1** (`dpkg-query` exit **0**). TZif material is **3,592 bytes**,
SHA-256 **feba326ebe88eac20017a718748c46c68469a1e7f5e7716dcb8f1d43a6e6f686**.
The original bytes are retained as `evidence/America-Chicago.TZif`.
TZPATH, package/source details and the hash are in `timezone-provenance.json`.
Real timezone material was present; no test-only tzdata package was installed.

The two review fixtures copy those real TZif bytes into owned Linux temporary
roots and deliberately label them `synthetic-unrelated` / `synthetic-supplying`.
These are fixture labels, not installed IANA releases. The second case removes
the supplying label and requires an unknown version without borrowing another
root's version. Cache-origin uncertainty and unpinned provenance remain disclosed.

### Exactly five existing calls, executed once

Committed definitions and pytest/runner configuration were inspected before
execution. All five are unparameterized. The existing protected runner's
`--execute` mode was used directly with an external task-owned run config,
not the Windows wrapper. Its source-root checks, serial enforcement, SQLite
audit guard and db-free fixtures stayed enabled. Source is inside the private
Linux run directory; bytecode is disabled and pytest's cache provider disabled.

Declared-requirements setup command:

~~~text
/usr/local/bin/python -m pip install --disable-pip-version-check --no-cache-dir -r /work/run/source/backend/requirements.txt
~~~

Actual test process, cwd `/work/run/source`:

~~~text
/usr/local/bin/python -u /work/run/source/scripts/backend_test_runner.py --execute /work/run/run-config.json
~~~

`run-config.json` supplies only the following five full repository-relative
node IDs, followed by these pytest arguments (rootdir is `source/backend`):

~~~text
backend/tests/test_futures_pit_roll_adapter.py::test_physical_symlink_refused
backend/tests/test_futures_pit_contract_calendar.py::test_real_chicago_dst_gap_fold_and_offset
backend/tests/test_futures_pit_contract_calendar.py::test_dst_duration_does_not_change_session_count
backend/tests/test_futures_pit_review_calendar.py::test_timezone_provenance_uses_current_path_and_the_zone_supplying_root
backend/tests/test_futures_pit_review_calendar.py::test_missing_supplying_version_does_not_borrow_another_roots_label
-o addopts= -vv -ra --tb=short -p no:cacheprovider --durations=0 --durations-min=0 --basetemp /work/run/pytest-tmp --junitxml /work/run/junit.xml
~~~

| Existing test (backend/tests/) | Call outcome | Call duration (s) |
| --- | --- | --- |
| test_futures_pit_roll_adapter.py::test_physical_symlink_refused | passed | 0.001034695 |
| test_futures_pit_contract_calendar.py::test_real_chicago_dst_gap_fold_and_offset | passed | 0.000766419 |
| test_futures_pit_contract_calendar.py::test_dst_duration_does_not_change_session_count | passed | 0.000581572 |
| test_futures_pit_review_calendar.py::test_timezone_provenance_uses_current_path_and_the_zone_supplying_root | passed | 0.000440320 |
| test_futures_pit_review_calendar.py::test_missing_supplying_version_does_not_borrow_another_roots_label | passed | 0.000449813 |

**5 collected/selected, 0 deselected; 5 passed, 0 skipped, 0 failed, 0 errors.**
All five setup/teardown phases passed. There are no new skip reasons.
The real symlink remains visible to post-run `lstat` (mode **41471**), targeting
the committed corpus `bars.csv`; its importer-refusal assertion passed.
`physical-symlink-evidence.json` records the link/target, overlayfs and target hash.
No mocked link or weakened assertion was used.

| Measurement/status | Recorded value |
| --- | --- |
| Printed pytest summary | 5 passed in 1.02s |
| Machine pytest wall | 1.391872671s |
| Startup/collection | 1.371876173s |
| Protected runner test-process wall / exit | 2.128663350s / 0 |
| Machine pytest exit | 0 |
| Requirements installation wall / process exit | 242.199344331s / 0 |
| Container bootstrap wall / exit | 247.625301401s / 0 |
| Host docker-run wall / CLI exit | 249.2520757s / 0 |
| Docker-recorded container exit / inspect exit | 0 / 0 |
| Bootstrap start/end UTC | 2026-10-12T06:56:12.676622Z / 2026-10-12T07:00:20.286048Z |

Per-phase outcomes/durations, selection, JUnit XML, verbose log and skip-summary
output, package metadata, install/pull logs, host invocation, image/container
inspection, exact snapshot manifest and process statuses are retained under
`evidence/`. The task-owned orchestration helper and its recorded SHA-256 remain
under `input/` / `evidence/host-invocation.json`; no repository runner was edited.
The successful tests were not repeated. No new setup/test failure occurred on
resume; the earlier unavailable-engine attempt remains recorded separately.

### Protection, cleanup and remaining publication boundary

- Private extracted source bytes/sizes remain identical across setup and tests.
  All **1,143** tracked working files matched the preflight SHA-256/size inventory
  after tests, before documentation edits. The index bytes also matched.
- Both recorded active-data files (`backend/data/.gitkeep` and `quantlab.db`)
  retained exact hashes/sizes/mtime. The active DB was never opened or mounted;
  SQLite audit violations are **[]**. Frozen screenshots and historical reports
  are covered by the unchanged tracked-file inventory and remain outside the diff.
- Only the recorded stopped task-owned container was removed, after evidence
  export/inspection: cleanup CLI exit **0**. No image, volume, prior evidence,
  active data or external task evidence was removed. Archive and logs remain.
- The physical Linux symlink and real Linux/Python 3.11 DST/provenance gate is
  now **closed by this five-node execution**. Supplied exact-review CI is already
  successful; its **18 unidentified skips remain unidentified**, not reconstructed.
- No full suite, complete modules, public CLI subprocess acceptance, frontend
  checks/builds, browser tests, audit, Docker application build or Phase 65/66
  platform check was rerun. No source/test/fixture/dependency/workflow/configuration
  or VERSION edit; no new standalone finalization report.
- Documentation-only handoff/staging is authorized for README.md, STOP_POINT.md,
  TASKS.md, CHANGELOG.md, this report, VERSION_MANIFEST.md and
  FORWARD_ROADMAP_PHASES_63_70.md. Exact membership, relative links, whitespace,
  final-newline hygiene and staging byte preservation are checked before handoff;
  the staged tree identity is returned separately, not embedded self-referentially.

**Ready for user documentation commit/publication: yes**, subject to the final
documentation/index hygiene check. Publication/verification of that documentation
revision and user creation of
**v4.85.0-futures-point-in-time-contract-calendar-foundation-adapter-spec-v1**
remain pending. The tag was checked absent, not created. This source CI does not
cover a future documentation commit. Declared local data/calendars and
**retrospective** rolls remain the boundary: no external provider, official
calendar or full PIT certification. No commit, push, tag, workflow trigger,
deployment or Phase 68 is performed by this task.
