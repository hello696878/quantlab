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
