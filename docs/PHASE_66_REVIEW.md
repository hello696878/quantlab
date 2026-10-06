# Phase 66 Independent Adversarial Review

Date: 2026-10-05. Repository: `C:\quantlab`. VERSION: `4.84.0-dev`.
Scope: Reproducible Run Replay by Hash and Environment Manifest v1.

**Decision:** safe to keep the bounded implementation with these review fixes;
ready for the user's review commit. Release verification remains incomplete:
final review-commit Python 3.11 CI, user production build and isolated browser
execution are pending. This review performs no staging or publication action.

## 1. Exact target and initial state

| Item | Verified value at review start |
|---|---|
| Branch | `main`, attached |
| Implementation HEAD | `b7bb025200f1c900847cda8f0651bcc662d0b2aa` |
| Subject | `Add reproducible run replay by hash environment manifest v1` |
| Single parent | `c250d7e7de241e18ee8555af4af4c56cef1b4a73` |
| Frozen tag | `v4.83.0-unified-ml-lifecycle-model-artifact-registry-v1`, peeled to that parent |
| VERSION | `4.84.0-dev` |
| Index / unstaged / nonignored untracked | All empty |
| Implementation inventory | 38 exact paths: 19 modified / 19 added; 2140 insertions / 38 deletions |

The inventory in `PHASE_66_IMPLEMENTATION.md` was located by content and
compared with `git diff HEAD^ HEAD --name-only`: exact membership matched,
not just the count. Its Markdown staging section was not executed.
The implementation-session branch/unchanged-parent statements remain historical
in that report; the current review target is the committed implementation above.

Read `AGENTS.md`, `CLAUDE.md`, the implementation report, Phase 66 runbook and
roadmap, the complete implementation diff and relevant surrounding code/tests,
saved-backtest and legacy reproducibility contracts, dataset/lifecycle public
contracts, protected runner and browser isolation runbooks. No nested repository
instructions were found. The explicit bounded Phase 66 request governs this work.

Expected later user review subject:
`Review reproducible run replay by hash environment manifest v1`.
Future user tag: `v4.84.0-reproducible-run-replay-environment-manifest-v1`.
It is not created by this review; the frozen parent tag is unchanged.

## 2. Confirmed findings and fixes

References marked **original** refer to implementation HEAD above; current
references refer to the uncommitted fixed source. P1 means materially incorrect
restoration/binding; it is not a claim of an authenticated remote exploit.
All confirmed findings below are fixed within the delivered Phase 66 scope.

| Severity | Confirmed defect in original implementation | Fix and regression evidence |
|---|---|---|
| P1 | `backend/app/run_replay/service.py:138-160`: hashing stored inputs against their own hashes allowed well-formed, rehashed contradictions with the original request, canonical config, saved run, schema or environment roles. | Independent reconstruction and record/envelope checks in current `service.py:71`, `:80`, `:178`. Persistence review tests `:46`, `:53`, `:60`, `:83`, `:267`, `:281` reject rehashed contradictions and swapped saved IDs. |
| P1 | Original `service.py:96-108`: a dataset pin was checked against the configured fingerprint only when retained CSV text existed. A context with absent bytes could claim an unrelated dataset. | Every dataset pin must match CSV configuration/content; retained or reselected bytes also require independent Registry schema/count/size checks (`service.py:89`, `:102`). Tests `:114`, `:126`, `:192`, `:208` cover rollback, substitutions and payload tampering. |
| P1 | Original `frontend/src/components/BacktestForm.tsx:276`, `:459-473`: the real form mounted with explicit simple cost 37 bps but an inactive top-level 10 bps value; its effect replaced 37 with 10. | Form state seeds effective model cost. Stateful actual-form/HTTP tests preserve the nondefault request and model semantics (`ReplayBacktestForm.test.tsx`). Separate P2 case: absent commission/slippage/spread components now remain zero, including after editing one component, rather than acquiring UI defaults 5/5/2. |
| P1 | Original `BacktestForm.tsx:981` and `frontend/src/app/page.tsx:1972`: clicking the already active SMA strategy detached local replay data; the next Run could take the provider path. | Active strategy selection is inert; other strategies and fixed local ticker/dates cannot silently replace the attached local input. Actual form edit/click/Run regression asserts `/contexts/19/execute-local` with the CSV and edited window, with no earlier request. Explicit detach/preset remains available. |
| P2 | Original `service.py:110-114`: parent context validation required existence but did not bind the parent to the saved input. | Current `service.py:112` requires an earlier saved record and equal fixed ticker/date/provider/fingerprint/dataset pin; parameter edits remain valid. Tests `:137`, `:151`, `:177` cover swapped parents, valid provider reruns, distinct saves and historical preservation. |
| P2 | Original `RunReplayPanel.tsx:121-123`: confirmation applied previously inspected preflight without a fresh material check. | Current `RunReplayPanel.tsx:123` fetches fresh preflight and verifies context/hash/input/integrity/availability; sequence guards reject stale confirmation and context-switch responses. Component regressions cover cancellation, changed input, late replies and refusal without Run. |
| P2 | Original `page.tsx:929`: an earlier Run response could replace newer presets, restored context or edited form state. | Synchronous pending and sequence guards (`page.tsx:821`, `:916`, `:936`) discard old success/error/finally responses. Actual request boundary is shared with stateful form tests in `runReplay.ts:108`. Full-page asynchronous DOM behavior remains a browser gate, not a claimed unit acceptance result. |
| P2 | Original `BacktestForm.tsx:654-658`: changing sensitivity metric discarded recorded custom grids and run cap. | Retain fast/slow grids and `max_runs` when changing only the metric; actual form request regression checks the edited metric and unchanged grid/cap. |
| P2 | Original `page.tsx:943`: Saved Backtests navigation inserted an intermediate Home history entry before the replay permalink. | Single destination push plus replace-only cleanup; URL/history helper regressions and strengthened browser back/reload assertions. Real browser execution remains pending. |
| P2 | Original `service.py:314-315`: demo found its newly saved context by searching the first 50 contexts. The 51st same-config save could commit successfully then fail to return its context. Partial demo failures also lacked a useful account of already committed owned records. | Lookup by saved ID (`store.py:28`, `service.py:405`). Partial failure returns 409 with confirmed dataset/version/saved IDs (`service.py:407`), preserving records. Tests `:240`, `:361` exercise both boundaries. |
| P2 | Original `identity.py:24`, `:78-84`: huge integers such as `10**400` reached float conversion and raised `OverflowError`; canonical non-object JSON raised `AttributeError`. | Bound integer magnitude before conversion and validate JSON text/object shape. Pure identity tests `:22-43` require controlled `ValueError`; API wrappers retain controlled refusal. |
| P2 | Original `adapter.py:51`: Python accepted compact/week ISO dates that HTML date inputs cannot represent exactly. | Exact restoration requires `YYYY-MM-DD` (`adapter.py:49-53`); pure tests `:148-161` refuse unsupported representations. Historical date strings/hashes and ordinary legacy endpoints are not rewritten. |
| P2 | Original `environment.py:57-61`: equal Git commits could appear matched despite dirty or unknown working trees. | Source fields remain unknown unless both checkouts are explicitly clean (`environment.py:64-77`); pure tests `:179-200` cover clean, dirty, missing and changed fields. |
| P3 | Original `environment.py:22-32`: a missing VERSION file prevented independent Git metadata collection. | VERSION and Git collection fail independently (`environment.py:24-37`); pure tests `:203-251` cover missing sources. Execution/save/inspection roles and allowlisted envelope validation are covered at `:164-176`. |

Saved-backtest database handles now close explicitly after reads/writes
(`backend/app/saved_backtests.py:86`, `:128`, `:139`, `:152`), preserving existing
transaction/rollback behavior. No quant signals, PnL, metrics, annualization
algorithm, legacy serializer, dependencies or workflows were changed.

One review-development correction followed the first green backend snapshot:
the newly tightened parent rule was initially CSV-only, while provider restored
Run could also submit a parent. Source tracing identified the inconsistency.
The final rule supports matching provider declarations, and the frontend attaches
a provider parent only when the **actual returned canonical identity** and pin
match. Changed ticker/date/fingerprint removes the parent; missing execution
capture is not fabricated. Two API tests and eight frontend cases cover this
correction. The first 203-pass snapshot is not presented as validating it.

## 3. Save, resolve, restore and trust conclusions

Actual path:

`execution request -> existing effective normalization -> result metadata -> explicit save -> stored context -> full-hash resolution -> selected preflight -> fresh confirmed form restoration -> separate user Run`.

| Boundary | Actual source and origin |
|---|---|
| Execution | Existing SMA endpoint / CSV single-asset helper in `backend/app/main.py`; result construction and request normalization precede capture. Provider prices originate from the normal execution path; no resolver fetch. |
| Capture | `run_replay/routes.py:18` records strict wire JSON if representable; otherwise execution records a labelled validated model/defaults. `execution_context` is optional response metadata. CSV identity uses actual parsed input and raw-byte fingerprint. |
| Save | `SaveBacktestModal.tsx` submits the displayed actual result fields plus optional capture. The local HTTP caller can also submit declarations; the API does not attest that this response was produced by the engine. |
| Registration | `saved_backtests.py:74` and `service.py:128` insert saved result and context in one SQLite transaction, independently validate config/scalars/request/pins/environment, and roll back both on error. |
| Resolution | `service.py:231` requires full lowercase 64-character hashes, returns bounded contexts ordered by ID, and never chooses latest. Context selection is explicit even when only one is displayed. |
| Inspection/export | `service.py:267`, `:313` verify stored material and classify present/missing/unavailable input. Export excludes CSV bytes and Registry locators. |
| Restoration | `adapter.restore`, fresh `RunReplayPanel` confirmation and `page.applyReplay` prefill the SMA form. They do not call an engine/provider or save a result. |
| Deliberate Run | `runReplay.ts:108` uses normal provider execution only for provider contexts, or `service.py:343` for local input; the latter rechecks material immediately before the existing CSV engine. A later explicit save creates a new record. |

Hashes detect inconsistent material, not authenticity. A writer able to forge
all saved data and hashes can fabricate a coherent history. Submitted metrics,
execution environment and runtime/source declarations remain
`declared_execution_metadata_not_attestation`. Save/inspection collection is
never backdated. A self-consistent checksum is not proof an execution occurred.

Identity conclusions:

- Existing `backtest_config_v1` / `comparison_config_v1` canonical algorithms
  and display prefixes remain unchanged; existing reproducibility tests pass.
  Full hash lookup refuses prefixes/malformed values with 422 and unknown hashes
  with 404. Page size is <=50 and page <=1000; deterministic ordering, deleted
  contexts, repeated same-config saves and ambiguous selection are tested.
- `replay_input_v1` separately includes canonical settings, supported original
  effective cost precision/diagnostics, actual dataset material/content/manifest
  pins and optional lifecycle provenance. Environment/result changes do not
  become configuration or input changes merely because they differ.
- `environment_manifest_v1`, result identity and `saved_execution_v1` are
  separate. The saved-execution hash includes database-local saved ID/time;
  repeated saves have distinct saved-context identities, without proving that
  the engine ran twice. Config equality alone cannot promise identical results.
- New strict JSON preserves list order and timestamp strings, distinguishes
  JSON numeric/Boolean forms, rejects duplicate keys/nonfinite/unsafe values,
  and bounds depth 20, nodes 300000 and bytes. The request mapper separately
  enforces executable numeric/Boolean types and known fields. It does not
  replace the legacy serializer or rewrite old hashes.

## 4. Dataset, artifact and environment boundaries

Retained input requires actual bounded UTF-8 bytes, not an ID or locator.
The raw UTF-8 SHA-256 must match canonical `dataset_fingerprint`; dates, <=128 KiB,
<=2000 cleaned rows, Registry schema/count/size and material pins are checked.
Invalidated/inactive/deleted/mutated Registry versions and changed bytes refuse
readiness/execution. Missing bytes require deliberate verified reselection.
No arbitrary server path/URL dereference and no local-to-provider fallback.

The existing CSV parser is a **daily-close contract**: timezone-aware inputs
convert to UTC calendar dates; naive inputs retain their calendar dates.
It removes invalid rows, keeps the last uploaded row for a duplicate date,
and sorts. A literal close column takes precedence over adjusted close; optional
OHLCV columns are ignored. Ticker is a declared request/Registry label, not an
independently verified entity in the two-column price series. This is not an
executable intraday table contract. Different raw bytes can express the same cleaned daily closes
but still have different raw-byte identities. Exact timestamp strings in JSON
are distinct from parser-normalized calendar dates; no intraday replay claim.
Ticker/date identity remains fixed for attached local input; changing that input
requires deliberate detach/CSV Upload rather than silent filtering.

Optional Phase 65 links are `provenance_only`, checked through public read-only
`dataset_binding` / `get_run` contracts; no model-to-strategy-return adapter was
invented. Owned incomplete/corrupted lifecycle material is tested through the
real public API without fitting or diagnostic execution. Positive complete-link
coverage uses the existing mocked public contract; full positive lifecycle
integration is not newly certified by this review.

Python/backend distribution versions come from the relevant runtime; VERSION
and Git identity come from that checkout. Only allowlisted fields are captured;
no username/home path, unrestricted system/environment inventory, credentials,
installation or runtime switching. Frontend Node/build metadata stay unknown
unless actually recorded. Tests cover same/different/unknown comparisons and
role validation. `not_applicable` is reserved in the response type; v1 has no
producer of that state, so no live not-applicable field pass is claimed.
Dirty/unknown source cleanliness yields unknown source comparisons, while
package fields compare independently. Different SHA/version values alone do
not establish changed numerical behavior; matching fields are not bit-identical
reproducibility certification.

Material revalidation occurs at preflight and immediately before explicit local
engine entry. Those reads, registry connections and execution do **not** form an
atomic cross-registry snapshot. Concurrent writers can also shift offset pages
and counts. These are disclosed concurrency limitations, not claimed resolved
by checksum validation. Provider prices are not frozen by matching settings or
parent linkage. Export references database-local IDs and excludes data bytes;
it is not a portable self-contained replay bundle.

## 5. Real SMA round-trip and side-effect conclusions

The frontend regression renders the real controlled `BacktestForm`, changes
state and clicks the ordinary Run button through the same `executeSmaRequest`
boundary used by Page. It asserts the actual HTTP endpoint/body, not just two
helpers calling the same normalizer. The Python pure test independently
specifies the expected canonical configuration for that same nondefault wire
fixture (`test_run_replay_identity_review.py:80-145`). Existing API tests provide
real save/resolve/preflight/local engine coverage, with destination component
tests covering confirmation and displayed fields. These compose the bounded
round-trip evidence; they are not a newly executed browser end-to-end test.

| Supported setting group | Exercised nondefault fixture |
|---|---|
| Asset/date/windows/capital | BTC-USD, 2020-02-03..2021-04-05, fast 7 / slow 31, capital 234567 |
| Costs | Inactive top-level 10 with explicit simple model 37; missing commission components remain zero, including one-field edits |
| Position/sizing | Long-short; volatility target .23, lookback 17, exposure cap .73 |
| Risk | Combined stop .07, take .19, trail .04, maximum holding 13; separate partial-rule case remains blank rather than defaulted |
| Benchmark/annualization | Custom QQQ and recorded auto annualization resolving to 365; local-input fixture uses no remote custom benchmark |
| Diagnostics | Robustness 213 iterations / block 7 / seed 19; sensitivity CAGR, fast [3,7], slow [21,31], max runs 4; metric-only edit preserves grids/cap |
| Data binding | Attached local input remains local through window edits and active-SMA clicks; ticker/date controls fixed; unsupported provider fails closed |

Recorded requests preserve effective cost precision and diagnostics. Legacy
config-only restoration has only canonical values, including six-decimal cost
precision; unknown original representations/diagnostics remain unknown.
The `vol_lookback` alias can require the labelled validated/defaulted capture
instead of exact raw wire capture. Unsupported form representations, including
compact/week dates, are refused rather than silently converted and labelled
exact. Canonical semantic restoration is not recovery of discarded UI state.

Actual provider/engine/write boundaries are spied in owned API regressions:
hash lookup, preflight, export and check-input preserve physical owned database
bytes and call no provider/engine/registration/demo writes. Legacy rows are not
backfilled on GET/startup. Explicit registration/demo/Run/save are the distinct
mutation boundaries. The demo creates 180 deterministic daily prices, uses
existing SMA 5/20 engine logic and saves the actual result with retained data;
it is not a disconnected fixture or a profit claim. Dataset/version/result
stages commit separately; failures preserve records and disclose confirmed IDs.

Component tests cover no automatic Run on mounting/restoring/editing, cancel,
stale confirmation/context replies, missing/changed data and reselection.
One rapid duplicate-Apply regression uses the actual HTTP preflight helper with
a deferred response and two clicks in one React batch while the button is still
enabled. It proves one fresh GET, one eventual restoration and an exact read-only
network inventory, with no execution/provider/save request.
Source inspection supports preservation of unsaved edits when merely reopening
the same context and duplicate Run protection. Source guards invalidate pending
Runs on newer actual form edits, context/preset/strategy changes and unmount.
Full Page race DOM behavior, real refresh/back/forward and geometry remain
pending browser acceptance; mocks are not counted as those gates.

## 6. Persistence, API, frontend and browser isolation

Fresh schema and real migration of an owned complete pre-Phase-66 saved schema
preserve every saved scalar/notes/JSON/result field (`persistence_review.py:317`,
full filename in inventory). Additive nullable indexed hash/schema columns and
one context per saved row do not force one execution per config hash. Explicit
legacy registration is idempotent. Parameterized SQL, bounded pages/IDs/JSON and
existing save behavior remain; no startup provenance invention or old result
overwrite. Invalid new captures return 422 and roll back save/context together;
unknown IDs/hashes return 404. Corrupt stored replay content returns 409;
missing/changed dataset or artifact material is reported by preflight with
HTTP 200 and `integrity="changed"`, and blocks explicit local execution with 409.

Replay body limit is 256 KiB, save body 4 MiB before parsing, stored context
512 KiB, original request 32 KiB and environment 8 KiB; positive IDs <=2^31-1.
Strict duplicates/schema/module/identifier conflicts and resource limits are
covered by existing and new regressions. Deleted contexts no longer resolve;
intentional parameter-edited reruns can save distinctly without replacing history.

Canonical workspace registry, Sidebar, Command Palette, Saved Backtests actions,
bounded validated hash/context URL, history and cleanup are connected to the
actual workspace. Loading/error/empty/ambiguous/config-only/incomplete/changed
states and accessible confirmation controls have source/component coverage.
Dark styles and layout constraints were inspected; actual browser geometry is
not certified by unit tests.

The strengthened `frontend/e2e/run-replay.spec.ts` asserts actual Saved
Backtests selection/preflight, JSON export without CSV, cancel and confirmed
restore, populated destination form and no implicit execution. It separately
clicks local Run, checks the intended mutation/request boundary, exercises
history/reload/refusal and overflow at 1440/1024/768. This specification was
discovered, **not executed**.

Mutating browser fixtures require equal verified disposable database identities
through the frontend proxy for strategy-ensemble and replay ownership proof.
The harness rechecks identity for replay/save requests. Eight new owned
in-process cases (`test_run_replay_harness_review.py`) mutate token/marker/override
or actual connection identity after proof, and assert refusal before either
`/run-replay/demo` or `/saved-backtests` mutation. This is stronger than a flag,
but is not real proxy/browser acceptance. No services or browsers started.

## 7. Inherited and read-only CI evidence

The unchanged `PHASE_66_IMPLEMENTATION.md` preserves its own failed attempts,
snapshots and later corrections. These are inherited, not review executions:

| Implementation record | Outcome / meaning |
|---|---|
| `quantlab-backend-focused-g39gci0h` | External evidence write denied; outer 1 before tests, no pass claim |
| `...-a54uks55` | 79 passed / 4 failed, pytest 149.00s; child 154.23s, total 166.14s; reported exits 1. CSV argument order/SQLite REAL identity corrected |
| `...-h75mk40h` | 39 passed / 2 failed, pytest 11.15s; child 13.5282s, total 27.0835s; reported exits 1. Fixture identity/harness lookup corrected |
| `...-aheav_f0` | 58 passed, pytest 12.77s; child 15.2039s, total 25.4730s; reported exits 0; superseded by later bounded fixes/tests |
| Final `...-plvoqbj1` | 91 selected/passed, zero skips; pytest summary 117.62s / instrumentation 117.8281s; child 120.4390s, total 144.4977s, setup 5.6781s. Pytest internal, child and outer exits 0; four protection/completeness flags true |
| Final frontend | 208 tests / 22 files, Vitest 6.06s, process 6.7437s, exit 0; TypeScript 16.0576s, exit 0; discovery 277/21, 2.3538s, exit 0 |

The final inherited backend snapshot SHA-256 is
`f7b185c42345c3ca3d9da5b5e40a88222128d049cd61d5f3197116aed3e918a2`.
It identifies parent HEAD `c250d7e7...` plus uncommitted implementation, not
an exact b7 commit verification. Earlier 207-test frontend/focused checks and
initial TypeScript exit 2 remain separate in the implementation report; none
are relabelled as a final combined whole-suite result.

Existing exact-implementation [CI run 37274152339](https://github.com/hello696878/quantlab/actions/runs/37274152339)
was inspected read-only, without dispatch/rerun. Both jobs completed successfully
at HEAD `b7bb025200f1c900847cda8f0651bcc662d0b2aa`:

- Backend job `111647356036`, Ubuntu configured Python 3.11, actual
  `python -m pytest -q`: **4611 passed / 18 skipped in 719.29s**.
  Test step 06:47:15..06:59:16 UTC; job completed 06:59:21 UTC.
  Its quiet summary does not enumerate skip reasons; they remain unspecified.
- Frontend Tests & Build job `111647356372` completed 06:48:23 UTC;
  component/typecheck/build steps succeeded. This existing CI build is not a
  user production build or verification of the later reviewer changes.

The initial sandbox CI read hit an unavailable localhost proxy; the permitted
read-only retry succeeded. No workflow was triggered. User-supplied Phase 65
baseline CI `37208511643` is separate historical evidence. Phase 65 platform,
Parquet/container and skip distinctions were preserved, not rerun or inferred
resolved by unrelated passes. No old full run plus new focused run is spliced
into a new final whole-tree pass.

## 8. Review executions, snapshots and runtimes

All backend executions used the inspected protected runner, frozen source,
one worker, copied source and independently owned SQLite fixtures. Pure identity
tests are `db_free` and do not initialize databases. No local full backend run.

```powershell
# From C:\quantlab; first stable review snapshot
.\scripts\run_backend_tests.ps1 -Scope focused -Python 'C:\quantlab\.venv\Scripts\python.exe' -Tests @(
  'backend/tests/test_run_replay.py',
  'backend/tests/test_run_replay_identity_review.py',
  'backend/tests/test_run_replay_persistence_review.py',
  'backend/tests/test_run_replay_harness_review.py',
  'backend/tests/test_reproducibility.py',
  'backend/tests/test_saved_backtests.py',
  'backend/tests/test_csv_backtest_api.py')

# After the provider-parent correction; only affected backend tests
.\scripts\run_backend_tests.ps1 -Scope focused -Python 'C:\quantlab\.venv\Scripts\python.exe' -Tests @(
  'backend/tests/test_run_replay.py',
  'backend/tests/test_run_replay_persistence_review.py')
```

| Review execution | Counts | Timing (seconds) | Recorded exits |
|---|---|---|---|
| Protected `...-4c03qzlm` | 203 collected / selected / passed; 0 deselected / failed / skipped | Summary 100.27; instrumented pytest 101.7551; child 106.1576; total 128.9449; setup 16.7246 | Pytest internal 0; child process 0; outer runner 0; PowerShell command 0 |
| Final affected `...-ciqqckez` | 76 collected / selected / passed; 0 deselected / failed / skipped | Summary 44.49; instrumented pytest 44.7381; child 47.6167; total 68.7414; setup 4.1046 | Pytest internal 0; child process 0; outer runner 0; PowerShell command 0 |
| First complete review frontend | 226 passed / 22 files | Vitest 25.92; process 39.6597 | 0 |
| Initial review TypeScript | Four errors in new test fixtures, not a pass | Process 43.5320 | 2 |
| Typed-fixture corrected frontend | 226 passed / 22 files | Vitest 6.10; process 7.1338 | 0 |
| Typed-fixture corrected TypeScript | Passed, no emit/incremental output | Process 16.6952 | 0 |
| Final frontend, including duplicate-Apply regression | 227 passed / 22 files | Vitest 6.06; process 6.8305 | 0 |
| Final TypeScript, including duplicate-Apply regression | Passed, no emit/incremental output | Process 12.3475 | 0 |
| Chromium discovery only | 277 tests / 21 files listed; 0 executed | Process 2.8796 | 0 |

Both review backend runs have `status=completed`, `child_evidence_complete`,
`active_db_unchanged`, `worktree_bytes_unchanged` and `snapshot_bytes_unchanged`
true. Evidence directories:
`C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-4c03qzlm` and
`C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-ciqqckez`.

Each snapshot manifest contains 1116 file entries, no missing/omitted source,
HEAD b7 plus its recorded dirty review state. SHA-256 of manifests respectively:
`540ee23b76664d6f53036b91253df87ae3a96d6567989072c6e6fd8bb27e48b4` and
`aaef9992c1856aec191b88a76c0ef79223e084910a91618c9ed7b4eef3edd2d2`.
Logs, JUnit, collection IDs, runtime, phase outcomes, source diff and runner
results remain in those directories. Between these snapshots only five entries
changed: service/persistence test and Page/runReplay helper/helper test. The
first snapshot remains evidence for unchanged identity/harness/shared save,
legacy reproducibility and CSV tests; the 76-pass run covers the final affected
backend. The counts are not added into a final full-suite claim.

Review TypeScript failed on partial typed replay fixtures and an unsupported
`getByRole` option in `ReplayBacktestForm.test.tsx` / `runReplay.test.ts`.
These two test files were corrected with complete typed objects and the proper
query option; no production code, assertion weakening or convenience skips.
The failed log/result is preserved. A final evidence audit identified that rapid
duplicate confirmation had only source coverage; the requested regression was
added to `RunReplayPanel.test.tsx`, followed by the final 227-test suite and
TypeScript check. No production or browser specification changed after discovery;
its 277/21 list remains applicable to the unchanged spec/harness/config bytes.
Final unit/typecheck executions cover all corrected/new test cases. All 612
backend/script entries still match the final protected backend snapshot.
All 273 tracked/nonignored frontend files match
`frontend-confirmation-manifest.json`, captured before the final frontend checks.

Frontend commands, from `C:\quantlab\frontend`, invoked the actually discovered
supported Node executable directly against installed local tools:

```text
node node_modules/vitest/vitest.mjs run
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/@playwright/test/cli.js test --project=chromium --list --reporter=list
```

| Runtime | Actual observed source |
|---|---|
| Python | `C:\quantlab\.venv\Scripts\python.exe`, 3.13.5 (Anaconda), pytest 9.0.3 |
| Backend libraries | FastAPI 0.136.3, numpy 2.4.6, pandas 3.0.3, Pydantic 2.13.4, scipy 1.17.1, Starlette 1.1.0, yfinance 1.4.0; local focused runtime, distinct from CI |
| Node | `C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\45309f9050f7314b\bin\node.exe`, v24.21.0, discovered/revalidated as existing; meets >=24.20.0 <25 |
| npm | Observed 11.12.1 through supported Node and existing `C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js`; packageManager declares 11.17.0. No install performed; npm did not launch these checks |
| Installed frontend metadata | Next 15.5.25, React 19.2.8, Vitest 4.1.11, TypeScript 5.9.3, Playwright 1.61.1 |

External review evidence root:
`C:\Users\jimli\AppData\Local\Temp\quantlab-phase66-review-b0d0af738c234842a5401b73b92f76b4`.
It retains first/final unit, failed/final TypeScript, discovery and protection
metadata/logs, including the final `*-confirmation` records. This directory is
execution evidence, not another handoff report.
No tests/checks were rerun merely to create another summary. Re-execution followed
the actual provider-parent/typed-fixture corrections or the missing requested
duplicate-confirmation regression. No installs, audits,
builds, browser execution, containers, external market data or services here.

**This report was edited after backend verification and finalized after the
final frontend checks.** The seven current-document corrections also followed
backend verification and were finalized with this handoff. They are not present in
the verified backend snapshot. Historical implementation and Phase 65 reports
remain byte-identical. Final review-commit CI must include these documentation
changes and all reviewer fixes.

## 9. Exact inventories and protected final state

### Implementation inventory, relative to its parent (38 paths)

```text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M VERSION
M backend/app/db.py
M backend/app/main.py
A backend/app/run_replay/__init__.py
A backend/app/run_replay/adapter.py
A backend/app/run_replay/environment.py
A backend/app/run_replay/identity.py
A backend/app/run_replay/routes.py
A backend/app/run_replay/service.py
A backend/app/run_replay/store.py
M backend/app/saved_backtests.py
M backend/app/schemas.py
A backend/tests/test_run_replay.py
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/PHASE_66_IMPLEMENTATION.md
A docs/RUN_REPLAY_AND_ENVIRONMENT_MANIFEST.md
M docs/VERSION_MANIFEST.md
A frontend/e2e/run-replay.spec.ts
A frontend/e2e/runReplayIsolation.ts
M frontend/src/app/page.tsx
M frontend/src/components/AppShell.tsx
M frontend/src/components/BacktestForm.tsx
A frontend/src/components/ReplayBacktestForm.test.tsx
A frontend/src/components/RunReplayPanel.test.tsx
A frontend/src/components/RunReplayPanel.tsx
M frontend/src/components/SaveBacktestModal.tsx
M frontend/src/components/SavedBacktestDetail.tsx
M frontend/src/components/Sidebar.tsx
A frontend/src/lib/runReplay.test.ts
A frontend/src/lib/runReplay.ts
A frontend/src/lib/runReplayIsolation.test.ts
M frontend/src/lib/types.ts
M frontend/src/lib/workspaceRegistry.ts
A scripts/run_replay_e2e.py
```

### Pending review inventory, relative to implementation HEAD (25 paths)

21 modified tracked files and four new nonignored files; zero staged paths.
This is the review inventory, not the implementation's 38 paths. `A` below
means a new working file, not an index addition. No staging command was executed.

```text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M backend/app/run_replay/adapter.py
M backend/app/run_replay/environment.py
M backend/app/run_replay/identity.py
M backend/app/run_replay/service.py
M backend/app/run_replay/store.py
M backend/app/saved_backtests.py
A backend/tests/test_run_replay_harness_review.py
A backend/tests/test_run_replay_identity_review.py
A backend/tests/test_run_replay_persistence_review.py
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/PHASE_66_REVIEW.md
M docs/RUN_REPLAY_AND_ENVIRONMENT_MANIFEST.md
M docs/VERSION_MANIFEST.md
M frontend/e2e/run-replay.spec.ts
M frontend/src/app/page.tsx
M frontend/src/components/BacktestForm.tsx
M frontend/src/components/ReplayBacktestForm.test.tsx
M frontend/src/components/RunReplayPanel.test.tsx
M frontend/src/components/RunReplayPanel.tsx
M frontend/src/lib/runReplay.test.ts
M frontend/src/lib/runReplay.ts
```

Minimal current-document changes update Phase 66 status and disclose corrected
semantics/gates; historical blocks/reports remain separate. VERSION, legacy
reproducibility module, dependencies, lockfiles, configurations, workflows and
frozen screenshots are unchanged. No databases, sidecars, credentials, logs,
snapshots, caches, dependency/build/browser outputs appear in the pending set.
Intentional tests contain owned fixture material, not generated outputs.

Protected baseline: 30 files (active data/.gitkeep, 22 screenshot-directory
files, two checksum manifests, two Phase 65 reports, legacy serializer, VERSION).
Bytes, size and modification ticks remain identical; protected path inventory
and active SQLite sidecar absence are preserved. Active DB:
8015872 bytes, SHA-256
`3b26e4b910194ecf0c01fe42c353f591b26b103e06c3f065ed9c0df8eb76f2f5`,
UTC modification ticks `639213676779732459`.
Index entry SHA-256 remains
`70c8d8ba7e3172bf29a343301b80c7566b3f91bc77cb1dc2222894af42eedd7a`;
this is index membership/content evidence, not a promise about Git stat-cache
bytes. Working and cached frozen-screenshot diffs are empty. Working/cached
diff whitespace checks and new-file whitespace checks pass.

Branch/HEAD/parent/frozen tag remain as in section 1. The future v4.84 tag is
absent. No staging, commit, push, tag, reset, clean, stash, branch switch,
pull/rebase, deployment, workflow trigger, active-DB connection/migration,
artifact deletion or Phase 67 occurred. Tests use only owned snapshot databases.

## 10. Decisions and remaining gates

**Safe to keep: YES**, for the explicitly bounded local inspect/prefill/SMA
replay capability with the disclosed trust, provider-history, representability
and concurrency limits. No confirmed blocking finding remains unfixed.

**Ready for user review commit: YES**, after the user reviews this exact 25-path
working set. This decision authorizes no Git mutation by the reviewer. A later
commit must use the intended review subject and preserve evidence distinctions.

**Final release verification: pending.** Required later gates:

- Exact **final review commit** Python 3.11 whole-tree CI; existing b7 CI does
  not validate these fixes. Investigate/report remaining skips/platform checks
  from their actual evidence rather than assuming unrelated passes close them.
- User production build of the final review state; existing implementation CI
  frontend build does not replace this gate.
- Isolated browser execution through verified disposable backend/proxy identity,
  including saved-to-restored form, explicit Run, refusal, history/races and
  intended viewport assertions. Discovery/component mocks do not close it.

No fresh inherited-security resolution or platform certification is claimed.
Other saved strategies remain config-only, other labs deferred, and Phase 67
is not started. Stop after this single review handoff.

## 11. Historical browser attempts and acceptance-spec correction (2026-10-06)

Bounded follow-up on clean `main` at
`9e0a0b5fa1835f090d7a1e4b8b2353c1d872bd46`, VERSION `4.84.0-dev`.
Earlier sections retain their original review snapshots, inventories and gates.
The following browser/build evidence is user-supplied, not rerun by this patch:

- Production build passed on that HEAD.
- First browser attempt failed at disposable-database proof; no demo seed or
  backtest execution occurred.
- Subsequent independent direct/proxy strategy and replay proof checks all
  returned HTTP 200, `database_verified=true` and the same disposable DB identity.
- Second attempt passed immediate isolation proof and seeded `/api/run-replay/demo`
  with HTTP 200, then timed out at the exact-name cell click in the spec.
  Read-only direct/proxy saved-list diagnostics showed the same single demo row,
  saved ID 1; its full hash resolved and one replay context pointed to that row.
  The browser snapshot showed the rendered name cell `Local SMA replay demo✎`.

Source confirms the acceptance-test defect: `SavedBacktestsList.tsx` appends
the notes marker to the name cell; the cell has no open-detail handler. Its
row's exact `View` button calls `onSelect(row.id)`. The spec now selects the row
containing the demo name, asserts visibility and clicks that row's `View` button.
Strict row matching also refuses ambiguity. Isolation proof, timeout, demo name
and all downstream assertions are unchanged; no sleeps, retries or force clicks.
Both failed attempts remain historical failures, without reclassifying either
as a product defect or claiming a final browser pass.

Exact verification command from `C:\quantlab\frontend`, using the newly
discovered supported executable:
`& 'C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\b72f26294f3e61db\bin\node.exe' node_modules/@playwright/test/cli.js test e2e/run-replay.spec.ts --project=chromium --list --reporter=list`.
Node `v24.21.0`; installed Playwright `1.61.1`. Result: **1 test in 1 file
discovered, zero executed**, command exit 0, measured command wall 0.8411576s.
Discovery had no failures. An initial read-only final-inventory command exceeded
Windows' command-length limit (CreateProcessAsUserW error 206) before execution;
no process exit was produced. The shorter verification passed, including
`git diff --check` (exit 0). Unit tests and TypeScript were not rerun for this
locator-only change; no executable product code changed. No services, E2E,
backend/full frontend tests, builds, audits, installs or database cleanup here.

Patch inventory: `frontend/e2e/run-replay.spec.ts` and this historical addendum
only, both unstaged. Safe to keep and ready for user patch commit: **YES**.
Final corrected browser execution on a fresh disposable backend remains pending.
No staging, commit, push, tag, deployment or Phase 67.
