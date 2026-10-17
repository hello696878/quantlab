# Phase 69 Independent Adversarial Review — Deterministic Evidence-Grounded Research Explainer v1

Date: 2026-10-16. This is the independent source review and verified-defect-fix handoff, not an implementation rerun or release acceptance.

## Target and initial state

- Attached branch: `main`; implementation HEAD: `ff7a288baa56ba61cb58d0de3aba524ec7a441cf`.
- Exact subject: `Add deterministic evidence grounded research explainer v1`.
- Exactly one parent: `2cd8f2585816fda0dc389f5a721ab02b0a3d71d8`.
- Existing annotated tag `v4.86.0-cross-sectional-neutralisation-scanner-validation-v1` resolves to that parent; VERSION was and remains `4.87.0-dev`.
- Initial index, unstaged tracked changes and nonignored untracked inventory were empty. No branch switch, history rewrite or overwrite occurred.
- Read root `AGENTS.md`, `CLAUDE.md`, the implementation report, support/runbook, complete 24-path implementation diff, and relevant saved/replay/metrics/fixture/runner/frontend/isolation contracts.

The committed implementation inventory is **24 paths: 12 modified /12 added**. It is distinct from the REVIEW pending inventory and later staging plan below:

```text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M VERSION
M backend/app/main.py
A backend/app/research_explainer/__init__.py
A backend/app/research_explainer/contract.py
A backend/app/research_explainer/routes.py
A backend/app/research_explainer/service.py
M backend/app/run_replay/service.py
M backend/tests/conftest.py
A backend/tests/test_research_explainer.py
A backend/tests/test_research_explainer_storage.py
A docs/EVIDENCE_GROUNDED_RESEARCH_EXPLAINER.md
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/PHASE_69_IMPLEMENTATION.md
M docs/VERSION_MANIFEST.md
A frontend/e2e/research-explainer.spec.ts
A frontend/src/components/ResearchExplanationPanel.test.tsx
A frontend/src/components/ResearchExplanationPanel.tsx
M frontend/src/components/SavedBacktestDetail.tsx
A frontend/src/lib/researchExplainer.ts
M scripts/backend_test_runner.py
```

## Confirmed findings and fixes

These are confirmed source/behavior defects, severity-ranked by their impact. Original references describe the implementation HEAD; linked references describe the repaired working source. No observed main-database corruption or production exploitation is claimed.

| Priority | Confirmed defect and consequence | Narrow fix / independent regression |
| --- | --- | --- |
| P1 | Original explainer `acquire()` opened a closed WAL-header database with `mode=ro`; actual SQLite created persistent empty WAL and 32 KiB SHM files. Read-only SQL did not meet the no-sidecar-create boundary. | [Storage preflight](../backend/app/research_explainer/service.py#L34) refuses observed WAL headers and journal/WAL/SHM sidecars before connecting, checks again after BEGIN. Owned closed-WAL, committed-WAL and rollback-journal cases assert refusal before connection and exact file inventory/bytes. |
| P2 | Original URI guard used generic URL parsing that normalized spelling/query/control forms differently from SQLite; the audit event also omits `uri=True/False`. The fixture's replaceable connection wrapper could leak across monkeypatch teardown. | [Permanent explicit-URI wrapper](../scripts/backend_test_runner.py#L24), canonical URI parsing and [current-scope preflight](../backend/tests/conftest.py#L39). Cached/dbapi2, lookalike roots, db_free, uri=False, unwrapped calls and exact teardown-order controls retain denial and evidence. The first full focused run exposed the real teardown leak; its failure is retained below. |
| P2 | Original aggregate lengths omitted date/config fields; context used SELECT *, allowing unrelated extension columns to be materialized. Structural limits were applied after JSON decoding. | [Bounded acquisition](../backend/app/research_explainer/service.py#L47) checks every selected field, selects six code-owned context columns, refuses duplicate context rows and lexically caps bytes/depth/tokens/container entries/string/scalar work before any full decoder. Decoder spies prove oversized/deep/wide material is refused first; oversized unselected private context columns are never loaded. Shared legacy JSON behavior is unchanged. |
| P2 | Unknown metric units/status spellings such as `units`, `total_return_available=false` or per-metric params flags were discarded, leaving confident scalar wording. | [Closed metric and saved-SMA parameter keys](../backend/app/research_explainer/service.py#L13), based on actual save/replay producers. Unsupported declarations refuse; existing cost, annualization, provider and data-quality metadata remains supported without interpretation. |
| P2 | `verified(saved_snapshot=...)` did not explicitly bind the supplied saved ID to the context row. A different supplied ID with coherently rehashed execution material could pass this missing local cross-check. | [Positive ID/equality check](../backend/app/run_replay/service.py#L190); regression keeps context/snapshot saved ID unchanged but supplies another ID and rehashes execution. This is consistency checking, not malicious-writer authentication. |
| P2 | Ambient Decimal precision/rounding/traps could change displayed text and fingerprints for identical pinned material. | [Fixed local half-even Decimal context](../backend/app/research_explainer/contract.py#L109); hostile contexts preserve exact text/hash and leave the caller's Decimal settings unchanged, including subnormal/tiny and large values. |
| P2 | Set-only projection checks accepted empty arrays as params/metrics; unused context leaves could contain invalid types or contradict saved SMA params while the bundle still claimed recorded hashes match. | [Strict nested object and context validation](../backend/app/research_explainer/contract.py#L173); all context windows must be positive strict integers, and overlapping saved/context values must match in type and value. Coherent outer rehashes cannot legalize these contradictions. |
| P2 | Negative stored volatility produced an annualized volatility sentence despite the nonnegative sample-standard-deviation definition. | [Volatility refusal](../backend/app/research_explainer/contract.py#L155), preserving negative returns/ratios and available zero. Independent literal arithmetic/wording test uses actual metric definitions. |
| P2 | Frontend JSON reserialization changed Python float tokens (`100.0`/`-0.0` to `100`/`0`), so a semantically equal download could invalidate backend raw-type/hash verification. Parsed-object export equality missed this. | [Retained validated wire document](../frontend/src/lib/researchExplainer.ts#L24) is bound to the displayed object; exact text is exported without refetch. Copied/mutated bundles refuse, including signed-zero/coherent edits. Backend and frontend regressions demonstrate the original identity loss; browser spec now compares exact response/download text. |
| P3 | Frontend pointer lookup accepted array properties such as length; backend/frontend could return missing before noticing malformed later escapes. No current v1 fact uses array pointers, so this is a latent helper boundary. | Both parsers validate every token first and distinguish canonical bounded array indices from arbitrary object keys; hand-specified slash/tilde/object/array/missing cases. |
| P3 | HTTPException refusal responses lacked the promised no-store header although success responses set it. | [Bounded 404/409/422 errors](../backend/app/research_explainer/routes.py#L7) now include Cache-Control: no-store; seven API cases assert headers, secret-free bounded errors and no acquisition for malformed requests. |

## Source, facts and trust conclusions

The explicit detail button calls the fixed GET endpoint, acquires selected saved/context material in one SQLite read transaction, closes the connection, verifies existing replay bindings against that same saved row, projects the allowlist, renders fixed templates and validates the final bundle. No get_connection/init_db/backfill/migration/registry-write fallback is used. No current environment capture is backdated into execution.

Actual save/read fixtures exercise legacy and replay-backed sources. The root demo legitimately executes the existing engine and saves data **before** forbidden-work spies. During explanation, spies on engine/provider, initialization/writable helpers, save/register/demo/replay execution, dataset/artifact pins and lifecycle entry points fail if called. The entire setup is not described as read-only.

Normal rollback storage and missing-file behavior are covered. WAL/journal states now refuse, including a nonempty committed WAL; no immutable live reader or main-file-only copy is used. The transaction test proves a competing owned writer cannot commit between source reads, then can commit after the reader closes. The competing test writer is deliberate setup/control work, not an explanation write. Header/sidecar preflight is an observed-state check, **not** atomic filesystem protection against a process racing a path replacement or journal-mode change. No universal concurrent-filesystem/VFS sandbox is claimed.

Saved ID/creation time/material hash and context ID/schema/result/input/execution/config/snapshot bindings distinguish same-config different records/results. Optional provenance absence remains distinct from malformed/changed/incomplete advertised context; corruption never silently downgrades to legacy. Parent contexts and other strategies are refused. Optional lifecycle/dataset links are not followed, authenticated, or promoted to model-origin evidence. A root demo requiring an unsupported parent was considered and disproved by the actual fixture; support was not expanded.

Legacy facts are explicitly unverified. Material identity covers the existing selected saved result, including decoded params/metrics/equity/trades, while the exported evidence is only a small projection. The final validator cannot recompute the entire original historical source or context digest from that projection. Consistency hashes are not signatures, authenticity, historical execution attestation, statistical validity or protection from a coherent malicious rewrite of all unattested identities/content.

Every fact binds source/path, raw type/value, state, unit, formatting rule and exact template wording; policy-only statements identify the policy/template instead of fabricated fields. Reader verification rejects inconsistent supplied saved/context IDs. The closed bundle validator rejects wrong fact IDs, same-valued wrong paths, units/displays/rules, raw types, template/fact bindings, policies and prose after a valid outer rehash. It cannot authenticate a coherently replaced valid source ID from the projection alone. Fixed dictionaries produce 15 facts and 23 statements, capped at 20/40 and 64 KiB. No metric, trade count, sample size or causal conclusion is calculated by the explainer.

Independent hand oracle: equities 100→110→99 have returns +0.10/−0.10, total return −0.01, peak drawdown −0.10, positive-return fraction 1/2, and three equity observations. With explicit **test-only** periods_per_year=2, sample return SD ×sqrt(2)=0.20 volatility. The test asserts these raw values and literal sentences before comparison with rendering. It crosses the actual JSON persistence boundary; the initial NumPy-valued fixture failure is retained below.

USD follows the existing SavedBacktestCreate contract, not the ticker. Volatility is recorded annualized decimal return, but this adapter does not establish the annualization convention or crypto suitability. Win rate means positive-return days, not profitable trades; num_days means equity observations including the initial point, not trading days or return periods. Missing/null/available zero remain distinct. Boolean/nonfinite/unsafe numeric values, invalid fractions/drawdown signs/counts, negative volatility and unsupported units/status metadata refuse. Tiny nonzero displays use scientific notation rather than false zero; fixed half-even formatting changes presentation only.

Code-owned templates and exact negative disclaimers are allowlisted; a disclaimer cannot license advice. Stored names, notes, hostile markup/multiline text/Unicode/URLs/synthetic secrets never become narrative or trusted HTML/Markdown/source labels. No LLM/provider client, dynamic evaluation, free-form template selection or new analytics was added.

## API, UI, export and browser isolation

Only GET /research-explainer/saved-backtests/{id} and the optional expected full fingerprint are accepted. IDs, duplicate/unknown/oversized queries, schema/material failures and errors are bounded. 404 denotes missing source, 409 relevant change/integrity failure, and 422 unsupported/invalid material/request. Expected checks consider actual result/context material; unsupported metadata changes become refusals rather than fresh confident wording. Name/note-only changes do not alter scientific material identity.

No production stale-response defect was confirmed. Existing ticket/identity/busy guards survive A-after-B, duplicate clicks, late successful/failed checks after a newer source, pending unmount/remount, evidence drawers and export ownership tests. Opening details does not automatically explain. A retained result is visibly a pinned snapshot; it does not imply current availability after an earlier successful check. Failed current-source checks detach it. Source expansion uses text rendering, correct raw/display/unit/path/identity and no external navigation.

The browser scenario is audited against the actual unique Saved Backtests row and View button, explicit Explain, keyboard Source access, raw source binding, 1440/1024/768 layout checks, exact download bytes, expected-fingerprint recheck, deliberate fixture-owned deletion, 404 detachment and navigation. No sleeps, force clicks, first() broadening, hidden retries or timeout relaxation were added. It remains **discovered, not executed**.

The existing run_replay_e2e harness requires a fresh user-selected loopback frontend/proxy, 64-lowercase-hex token and x-quantlab-e2e-token header. Both /api/strategy-ensembles/e2e-isolation and /api/run-replay/e2e/isolation must positively prove the same owned database through the actual frontend proxy before demo writes. The harness checks canonical exclusive external-temp ownership, marker/device/inode, actual get_db_path and PRAGMA main identity, no symlink/hardlink substitution, single fresh worker/no reload, and rechecks guarded saved/replay requests. The explainer GET itself is not a harness middleware write gate. No old token, port, server or runtime path was reused, and no harness/services/browser was started here.

## Shared replay and verification infrastructure

The saved_snapshot argument avoids a later writable saved-record read while preserving legacy/config/result/input/environment/execution/CSV bindings. Public callers still use the default saved lookup and parent checks; the explainer passes its transaction-pinned saved row, checks explicit ID equality and refuses unsupported parent contexts. No replay registration or historical environment recapture occurs on explanation.

Exact file URI syntax plus explicit uri=True intent is required through the stable wrapper. Plain paths retain owned-root checks; writable/shared/duplicate/normalized URI forms refuse. Audit hooks cover dbapi2 and cached calls; pre-install unwrapped URI calls fail closed. db_free denies even memory connections. Stable current-scope preflights fix monkeypatch teardown leakage without weakening the original idempotence assertion. These are Python test guardrails, not a hostile-Python/native/subprocess filesystem sandbox.

The tiny owned negative child has pytest exit 0/one passed test but records four unauthorized URI attempts and returns process exit 1, as asserted by the parent test. Its retained violation list and absence of database files were inspected independently; no separate child process-result file is invented. No failing control targeted the active database. Existing small runner controls cover normal pass/fail/import/no-tests exits, incomplete evidence, setup/teardown errors, configuration deselection, source additions/links, cached SQLite aliases, interruption and PowerShell exit propagation.

Snapshots use actual tracked and nonignored untracked working bytes, including all new review tests and edited shared files; no git-archive-HEAD substitution. Original collection node IDs remain intact. The Windows oversized implementation parameter case retains its explicit short test ID and full payload/assertions; runner IDs were not shortened or collided. Source inventories, node counts and phase records were checked independently, not accepted only from runner success flags.

## Verification evidence — separate runs, not summed

External review evidence root:
`C:\Users\jimli\AppData\Local\Temp\quantlab-phase69-review-a71585eb4fe5492c9531b1c6c44b2d6a`.
Backend run roots below are under `C:\Users\jimli\AppData\Local\Temp\`.

### Independent SQLite behavior

Actual command:

```powershell
& C:\quantlab\.venv\Scripts\python.exe -B 'C:\Users\jimli\AppData\Local\Temp\quantlab-phase69-review-a71585eb4fe5492c9531b1c6c44b2d6a\sqlite-probe.py' 'C:\Users\jimli\AppData\Local\Temp\quantlab-phase69-review-a71585eb4fe5492c9531b1c6c44b2d6a'
```

Exit 0; tool wall 3.846 seconds. Python 3.13.5 / SQLite 3.50.2, fresh owned temporary storage only, no application import. Retained `independent-sqlite/probe-results.json` and script show main file SHA/size unchanged, but a closed WAL-header read created persistent `owned.db-wal` (0 bytes) and `owned.db-shm` (32768 bytes). Eight URI interpretation cases retain actual reads/errors/write denial/file inventories. Windows uri=False/uppercase/blank-extra forms failed to open; encoded key and NUL-suffix forms were accepted by SQLite but are now rejected by the guard's canonical grammar. No Linux outcome is inferred.

### New backend commands and outcomes

Initial small command, then identical corrected rerun:

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused `
  --test backend/tests/test_backend_sqlite_boundary_review.py `
  --test backend/tests/test_research_explainer_storage_review.py `
  --test backend/tests/test_research_explainer_api_review.py `
  --test backend/tests/test_research_explainer_review_contract.py::test_decimal_context_cannot_change_pinned_text_or_fingerprint `
  --test backend/tests/test_research_explainer_review_contract.py::test_stored_metric_words_match_hand_computable_equity_not_trade_counts `
  --test backend/tests/test_research_explainer_review_contract.py::test_number_reserialization_can_break_pinned_hash_despite_equal_parsed_values
```

The initial run's hand-oracle metric outputs included NumPy scalars. Its five raw arithmetic assertions passed, but bypassing save/JSON decode caused the strict native-JSON display validator to refuse. Only that review fixture was corrected to `json.loads(json.dumps(metrics))`, matching saved_backtests persistence; no product numeric coercion was added.

Final focused command, used for both the first attempt and final retry:

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused `
  --test backend/tests/test_research_explainer.py `
  --test backend/tests/test_research_explainer_storage.py `
  --test backend/tests/test_research_explainer_review_contract.py `
  --test backend/tests/test_research_explainer_api_review.py `
  --test backend/tests/test_research_explainer_storage_review.py `
  --test backend/tests/test_backend_sqlite_boundary_review.py `
  --test backend/tests/test_saved_backtests.py `
  --test backend/tests/test_run_replay.py `
  --test backend/tests/test_run_replay_persistence_review.py `
  --test backend/tests/test_run_replay_identity_review.py `
  --test backend/tests/test_backend_test_maintenance.py `
  --test backend/tests/test_backend_runner_review.py
```

This scope covers explainer contract/storage/API, real saved consumers, replay public/default/pinned consumers, identity/persistence and modified fixture/runner safeguards. It excludes unchanged lifecycle modules and unrelated futures/whole-tree modules; optional lifecycle execution is already forbidden by explainer spies. It was not an automatic rerun of every inherited target.

The first final-scope failure confirmed a real fixture wrapper lifetime leak after test monkeypatch teardown, not source drift: corrected-small and first-final attempts shared the same source-manifest hash. Permanent current-scope preflights replaced per-fixture connect replacement. The original installation identity assertion remains; a new teardown-order case proves restoration, subsequent db_free denial and post-boundary normal memory access.

Corrected affected command before the final retry, deliberately preserving the failing storage-before-guard order:

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused `
  --test backend/tests/test_research_explainer_storage_review.py `
  --test backend/tests/test_backend_sqlite_boundary_review.py `
  --test backend/tests/test_backend_test_maintenance.py
```

| New run root | Selected / outcome | Printed pytest seconds | Machine pytest / collection / snapshot setup / test-process / outer-runner seconds | pytest / child / outer / tool exits | Source manifest SHA-256 |
| --- | --- | --- | --- | --- | --- |
| quantlab-backend-focused-vnx5ybq5 | 64 selected: 63 passed, 1 failed; 0 skips/errors | 31.44 | 32.238809399990714 /27.527887699994608 /11.258097300000372 /35.41545079999196 /52.5106276999868 | 1 /1 /1 /1 | 7b169004364dd556cbd2253586b24d3c33e6c64140023692c6810fc4f9270499 |
| quantlab-backend-focused-1md276o9 | 64 passed; 0 skips/failures/errors | 7.92 | 8.022271499998169 /4.073808299988741 /4.328498300004867 /9.802902999988873 /17.74084359999688 | 0 /0 /0 /0 | badf713e491818b2f24a86f30347328e92474fc5e9f9f11cb46910a1525328f9 |
| quantlab-backend-focused-osx53qt_ | 409 selected: 408 passed, 1 failed; 0 skips/errors | 139.63 | 139.655159499991 /3.9646731999964686 /4.371532299992396 /142.0047601999977 /158.95335219999833 | 1 /1 /1 /1 | badf713e491818b2f24a86f30347328e92474fc5e9f9f11cb46910a1525328f9 |
| quantlab-backend-focused-fwz57hdd | 72 passed; 0 skips/failures/errors | 21.39 | 21.589288199989824 /7.0791288999898825 /4.956160599991563 /24.234298000010313 /45.81431109999539 | 0 /0 /0 /0 | f402e6ff4d86c3913ca41cc74b40c223110dd33bee715f947d8a2e7d835ac0b0 |
| quantlab-backend-focused-se8fsnqt | 410 passed; 0 skips/deselection/failures/errors | 188.28 | 188.40510790000553 /10.36945790000027 /4.580417999997735 /191.14683740001055 /214.53430159999698 | 0 /0 /0 /0 | f402e6ff4d86c3913ca41cc74b40c223110dd33bee715f947d8a2e7d835ac0b0 |

No run is added to another as a final whole-suite total. Every run has retained runtime/config, collection, per-node phases, pytest result/log, JUnit, manifest, worktree diff, runner result and protection evidence. All reported setup/teardown phases passed, including the two failed-call runs; no skipped node or skip reason exists in these new scopes. Passing runs independently have complete child evidence. Failed runs retain their actual nonzero codes and are not described as passing.

All new runs recorded snapshot/worktree/active-file protection equality and outer SQLite violations `[]`. Negative-control violation lists are separate intentional owned-child evidence. The active-file comparison is the existing runner's before/after byte-hash check, not an active DB connection, a new application-data audit or a global filesystem guarantee.

Current backend runtime actually recorded: C:\quantlab\.venv\Scripts\python.exe, Anaconda Python 3.13.5 MSC v.1929 AMD64, SQLite 3.50.2; Windows-11-10.0.26100-SP0; one worker; pytest 9.0.3, NumPy 2.4.6, pandas 3.0.3, SciPy 1.17.1, Pydantic 2.13.4, FastAPI 0.136.3, httpx 0.28.1, Starlette 1.1.0. Runtime manifests retain the complete installed-package/plugin/environment metadata. UTF-8/bytecode suppression is explicit; no thread-count environment values or Linux/Python 3.11 execution are inferred.

### New frontend checks

Freshly discovered executable: `C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\a5a02988362ca169\bin\node.exe`, Node 24.21.0. Existing npm CLI: `C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js`, actual npm 11.12.1. No runtime/package installation or upgrade. Actual tool versions: Vitest 4.1.11, TypeScript 5.9.3, Playwright 1.61.1.

From C:\quantlab\frontend, with that exact Node executable and the external evidence root:

```powershell
$node = 'C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\a5a02988362ca169\bin\node.exe'
$reviewEvidence = 'C:\Users\jimli\AppData\Local\Temp\quantlab-phase69-review-a71585eb4fe5492c9531b1c6c44b2d6a'
& $node node_modules/vitest/vitest.mjs run --reporter=default --reporter=json --outputFile.json=$reviewEvidence/frontend-unit-export-final.json
& $node node_modules/typescript/bin/tsc --noEmit --incremental false
& $node node_modules/@playwright/test/cli.js test e2e/research-explainer.spec.ts --project=chromium --list --reporter=list
& $node node_modules/@playwright/test/cli.js test --project=chromium --list --reporter=list
```

| Final frontend check | Actual outcome | Duration | Process/tool exit |
| --- | --- | --- | --- |
| Unit suite after export fix | 258 passed /25 files, zero failed/pending/todo/skips; 13 explanation/helper cases included | Vitest 6.05s; process 6.8115009s | 0 |
| TypeScript | Passed, no diagnostics | process 20.1932351s | 0 |
| Focused Chromium discovery | 1 test /1 file, not executed | process 1.4158955s | 0 |
| Overall Chromium discovery | 279 tests /23 files, not executed | process 1.2754846s | 0 |

Retained frontend-export-final-source-before/after manifests independently match all 11 source/config/harness SHA-256 and size entries. Timestamps naturally differ. JSON test results independently contain 25 passed files/258 passed cases. Intentional setupIsolation error-sentinel console text remains part of its passing test, not a hidden suite failure.

New frontend startup failure is preserved: first unit attempt esbuild spawn EPERM before collection, process/tool exit 1 after 2.1647169s, frontend-unit.log/process metadata; no test counts inferred. Same approved suite retried with process permission: 255/25 passed, Vitest 22.90s/process 30.5125191s, exit 0. After whole-pointer validation, a separate pre-export snapshot again passed 255/25, Vitest 5.95s/process 7.0477746s, exit 0. Both precede the export fix and are not the final 258 result. All logs/JSON/process records remain; the final new seven frontend cases are included in 258, not additional passes.

### Inherited implementation evidence

Unmodified [PHASE_69_IMPLEMENTATION.md](PHASE_69_IMPLEMENTATION.md) remains the historical source of setup/collection failures and implementation claims. Existing manifests/selected node records were reread, not rerun or silently upgraded.

| Inherited backend root | Actual recorded result | Printed seconds | Machine pytest / collection / snapshot setup / test-process / outer-runner seconds | pytest / child / outer exits | Manifest SHA-256 |
| --- | --- | --- | --- | --- | --- |
| quantlab-backend-focused-7y_s7ms9 | 330 selected/passed, 0 skips/deselection/failures/errors; 990 phase records | 193.84 | 194.0306305999984 /7.440573200001381 /5.268675599996641 /196.63243640000292 /207.33735100000195 | 0 /0 /0 | 40027a7515a3107d6809b82b54c7e20d269aa4bdc2423d47bcfd57a0697fce26 |
| quantlab-backend-focused-ppdqqsra | 73 selected/passed, 0 skips/deselection/failures/errors; 219 phase records | 10.18 | 10.43128369999613 /6.36727499999688 /4.10013899999467 /12.882168500000262 /22.418103099997097 | 0 /0 /0 | 7841d9bcfe952a30458af86e4763c6f89683c1d51c2854feecafc535082704d6 |

The inherited broad command used the protected runner with these exact --test targets: test_research_explainer.py, test_research_explainer_storage.py, test_saved_backtests.py, test_run_replay.py, test_run_replay_persistence_review.py, test_run_replay_identity_review.py, test_ml_lifecycle.py, test_ml_lifecycle_review.py, test_backend_test_maintenance.py, test_backend_runner_review.py, each under backend/tests. The final affected command used only the first two. Both used `& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused` and explicit --test arguments; exact expanded pytest argv remains in each run-config.json.

Independent manifest comparison confirms the broad→final-affected executable differences are exactly explainer contract.py, explainer service.py and test_research_explainer_storage.py; missing/omitted inventories empty. The 330 comprised 45 pure/26 storage/259 older cases; the 73 comprised 45 pure/28 storage. Final affected fixes included fixed table discovery, partial replay-index refusal, legacy canonical/saved-row disagreement and annualization limitation wording. Nine metadata/docs/VERSION paths were finalized afterward. These are separate historical snapshots, not 403 final passes, and do not establish current-review-tree readiness.

Inherited failed attempts retained exactly:

- `quantlab-backend-focused-twg7movv`: evidence-directory PermissionError, process/tool 1; no usable runner/test result, selected count or protection result inferred.
- `quantlab-backend-focused-gq5ftpz0`: conftest collection import shadowed local scripts with an installed scripts package. Child/outer exit 4; no pytest result/selected count; phase file empty. Outer 22.4497560000018s, process 3.1138554999997723s, snapshot setup 13.753380800000741s; recorded protections true. Exact-file import repaired it.
- `quantlab-backend-focused-ubtcw8oc`: 65 selected, 64 call passes, one setup error and one teardown error from the 600 KB automatic parameter ID exceeding Windows PYTEST_CURRENT_TEST environment length. Printed 24.97s; machine 25.1044069999989s, process 27.267725300000166s, outer 36.35074049999821s, setup 4.470778800001426s; pytest/child/outer/tool 1, protections true and outer violations []. Explicit short case ID retained full payload/assertions.

Inherited frontend was 251 passed/25 files, Vitest 23.87s/process 33.861988s; final TypeScript 16.3412102s, all exit 0. Separate development TypeScript was 19.6797326s/exit 0. Discovery was 1 focused/279 overall, process 1.3268342s/1.2335539s, exits 0, none executed. Inherited Node 24.21.0 used the former cfb32733c877621e runtime directory; actual npm was 11.12.1 despite the packageManager label. These results and the inherited Python 3.13.5 environment are preserved, not reused as fresh final-review acceptance.

Final current-source focused result is **410 passed, zero skips/failures/errors**, not a whole-tree pass. Independent collection/phase/JUnit reconciliation gives 410 unique selected nodes, 1230 passed setup/call/teardown records, no malformed node groups, and zero missing/omitted snapshot paths. New review modules contribute 118 included cases: contract58, API7, storage26, guards27. Existing modules contribute explainer45/storage28/saved31/replay43/persistence33/identity50/maintenance19/runner43. All are included in 410, not additional passes.

The corrected-affected and final-retry source manifests are identical. Comparing the preceding BADF snapshot with the final F402 snapshot changes exactly conftest.py, backend_test_runner.py and test_backend_sqlite_boundary_review.py. Actual edited/new executable bytes match the final snapshot; the implementation's 330/73 and earlier review 64/409 evidence are not silently upgraded to this final source.

**This report and the seven current-document corrections were written/edited after backend verification.** They were not present in the tested source snapshot and do not represent newly tested executable bytes. No executable source/test/browser spec changed after final backend/frontend verification. Final pending-file hashes/sizes are recorded externally in `final-hygiene.json`, including the finalized report, for later staging revalidation.

## Final REVIEW inventory and later user-only staging plan

**21 intended pending paths: 16 modified /5 new, all unstaged.** This is the complete REVIEW inventory relative to implementation HEAD, not the implementation's 24 paths. No code or document outside this list was intentionally changed:

| Change | Repository-relative path |
| --- | --- |
| M | CHANGELOG.md |
| M | README.md |
| M | STOP_POINT.md |
| M | TASKS.md |
| M | backend/app/research_explainer/contract.py |
| M | backend/app/research_explainer/routes.py |
| M | backend/app/research_explainer/service.py |
| M | backend/app/run_replay/service.py |
| M | backend/tests/conftest.py |
| A | backend/tests/test_backend_sqlite_boundary_review.py |
| A | backend/tests/test_research_explainer_api_review.py |
| A | backend/tests/test_research_explainer_review_contract.py |
| A | backend/tests/test_research_explainer_storage_review.py |
| M | docs/EVIDENCE_GROUNDED_RESEARCH_EXPLAINER.md |
| M | docs/FORWARD_ROADMAP_PHASES_63_70.md |
| A | docs/PHASE_69_REVIEW.md |
| M | docs/VERSION_MANIFEST.md |
| M | frontend/e2e/research-explainer.spec.ts |
| M | frontend/src/components/ResearchExplanationPanel.test.tsx |
| M | frontend/src/lib/researchExplainer.ts |
| M | scripts/backend_test_runner.py |

New files are source regressions and this review report, not runtime/generated output. No intended JSON/CSV fixture was rejected solely for its format; this review adds no fixture data files.

**Do not run this section as a Markdown script. No staging is performed by this review.** A later user-authorized staging task must reread this exact inventory and finalized file hashes, verify main/HEAD/VERSION, inspect complete index/unstaged/nonignored-untracked membership and content, preserve unrelated staging, then use only these explicit literal paths:

```powershell
git --literal-pathspecs add -- `
  'CHANGELOG.md' `
  'README.md' `
  'STOP_POINT.md' `
  'TASKS.md' `
  'backend/app/research_explainer/contract.py' `
  'backend/app/research_explainer/routes.py' `
  'backend/app/research_explainer/service.py' `
  'backend/app/run_replay/service.py' `
  'backend/tests/conftest.py' `
  'backend/tests/test_backend_sqlite_boundary_review.py' `
  'backend/tests/test_research_explainer_api_review.py' `
  'backend/tests/test_research_explainer_review_contract.py' `
  'backend/tests/test_research_explainer_storage_review.py' `
  'docs/EVIDENCE_GROUNDED_RESEARCH_EXPLAINER.md' `
  'docs/FORWARD_ROADMAP_PHASES_63_70.md' `
  'docs/PHASE_69_REVIEW.md' `
  'docs/VERSION_MANIFEST.md' `
  'frontend/e2e/research-explainer.spec.ts' `
  'frontend/src/components/ResearchExplanationPanel.test.tsx' `
  'frontend/src/lib/researchExplainer.ts' `
  'scripts/backend_test_runner.py'
```

After later staging, require exact approved/staged membership, 21 paths with 16 modified/5 added classifications, this finalized report included, cached whitespace/EOF checks, no remaining intended unstaged/untracked content, protected files unchanged and no unintended database/sidecar/credential/log/cache/dependency/build/browser files. Stage no extra path to reach a count. No force/renormalize/config changes or blanket/directory staging. A future staged-tree identity may only be generated by the later authorized staging task; none is claimed here.

## Preservation, decision and remaining gates

The final index is empty; its raw SHA-256/size matches the initial baseline (`09732d8e73e8c7daeb8aba3e1d241ffb567f8314189bac0cf1a2de86f3e20482`, 125106 bytes). VERSION and all 50 separately captured non-database protected files match initial SHA-256/size: frozen screenshots, Phase66–68 implementation/review reports, Phase69 implementation evidence and backend/data/.gitkeep. Active-file protection is only the recorded runner byte-hash comparison described above; no active SQLite connection or new protection audit was made. Frozen Phase68 tag resolution is unchanged.

Final Git/whitespace/EOF checks cover tracked differences and all five new files. No staged changes or unintended nonignored untracked artifacts remain; the four new regression modules and this report are intentionally untracked until later staging. Authorized source/test fixes and current docs are the only working changes. Evidence artifacts stay in owned external temporary directories; no existing evidence/artifact was deleted.

Tracked `git diff --check` exited 0. New-file `git diff --no-index --check -- NUL <explicit file>` checks each exited 1 for the expected added-file difference; their only diagnostics were ordinary LF-to-CRLF future-checkout warnings, with no whitespace diagnostics. All five new files have one final line terminator and no excess EOF blank line. No line-ending normalization was performed and the index was not populated to run a cached check.

**Safe to keep: yes**, for the documented bounded stored-SMA adapter and observed supported storage. **Ready for user review-commit decision: yes**, after inspection of this unstaged inventory; this is local focused correctness evidence and not release acceptance. No unresolved confirmed local defect is concealed by a skip or weakened check. Cross-platform filesystem behavior and unsupported adapters remain explicit limitations.

Still pending: exact-review-commit **Python 3.11/Linux whole-tree CI**, user production build, isolated real browser acceptance through the owned disposable harness, and remaining platform coverage. Existing runner cases exercised owned Windows junction rejection; Linux/physical-symlink execution and inherited security resolution remain pending. Retrospective/PIT conclusions from older phases were not upgraded or rerun.

Later user-controlled review subject: `Review deterministic evidence grounded research explainer v1`; future tag: `v4.87.0-deterministic-evidence-grounded-research-explainer-v1`, not created. No staging, commit, push, tag, PR, deployment, workflow trigger, service, actual browser run, production/Docker build, package installation, active-database connection or Phase70 work occurred. Stop at this single handoff.
