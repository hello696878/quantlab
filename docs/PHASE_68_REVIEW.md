# Phase 68 Independent Adversarial Review

Date: 2026-10-13 (Asia/Taipei). Independent source/contract review and narrow
verified-defect fixes. No staging, commit, push, tag, workflow trigger,
application service, production build, actual browser execution or Phase 69.

## Exact Target and Initial State

- Attached **main**, initially clean: empty index, no tracked modifications or
  nonignored untracked files.
- Full implementation **5428eb20ae7c1dc33c2e875a1e33370e2423568b**.
- Subject: **Add advanced cross sectional neutralisation scanner validation v1**.
- Exactly one parent: **e23e828952c1dd1dcc320a225e75a0337aa1fd80**.
- Annotated frozen tag
  **v4.85.0-futures-point-in-time-contract-calendar-foundation-adapter-spec-v1**
  resolves to that parent. No branch/tag/history operation was performed.
- VERSION **4.86.0-dev**, unchanged by review.
- Reviewed the complete implementation inventory, new modules and relevant
  surrounding contracts/tests: **27 paths = 13 modified / 14 added**.
  This committed IMPLEMENTATION inventory is separate from the REVIEW inventory below.

~~~text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M VERSION
M backend/app/main.py
A backend/app/scanner/advanced.py
M backend/app/scanner/cross_sectional.py
A backend/app/scanner/pnl.py
A backend/app/scanner/policies.py
A backend/app/scanner/validation.py
A backend/app/scanner_validation_routes.py
M backend/app/schemas.py
A backend/tests/test_scanner_advanced.py
A backend/tests/test_scanner_validation.py
A docs/CROSS_SECTIONAL_NEUTRALISATION_AND_SCANNER_VALIDATION.md
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/PHASE_68_IMPLEMENTATION.md
M docs/VERSION_MANIFEST.md
A frontend/e2e/scanner-neutralisation.spec.ts
A frontend/src/components/ScannerLabPanel.test.tsx
M frontend/src/components/ScannerLabPanel.tsx
A frontend/src/components/ScannerResearchResults.tsx
M frontend/src/lib/api.ts
A frontend/src/lib/scannerAdvanced.test.ts
A frontend/src/lib/scannerAdvanced.ts
M frontend/src/lib/types.ts
~~~

Historical [implementation handoff](PHASE_68_IMPLEMENTATION.md) is preserved.
Current status documents now name the actual main/implementation SHA and the
review result; historical Phase 67 sections and prior reports remain historical.

## Severity-Ranked CONFIRMED Findings and Fixes

References identify the final fixed source; findings concern the implementation
bytes inspected before these fixes. No P0/P1 defect was confirmed.

| Severity | Confirmed trigger and consequence | Narrow fix and independent evidence |
| --- | --- | --- |
| P2 | An availability time just after midnight, e.g. 00:00:00.0000001Z, was silently truncated by datetime.fromisoformat to the decision cutoff. A late declaration could become eligible. | backend/app/scanner/policies.py:59 rejects precision beyond six fractional digits, including comma notation. test_scanner_review_quant.py:105 and :114 cover refusals, offset equivalence, retained microseconds and actual one-microsecond cutoff exclusion. |
| P2 | UTC conversion of year-boundary offset timestamps could raise an uncontrolled OverflowError during Pydantic model validation instead of a bounded refusal. | policies.py:65 converts UTC-range overflow into ValueError. Both exposure/factor cases and both API paths are covered by the new quant and validation regression modules. |
| P2 | After a successful advanced basket, a later failed rebalance correctly liquidated actual holdings but the top-level latest_ranking still displayed the older successful weights and static generated sectors. | backend/app/scanner/cross_sectional.py:279 uses the latest attempted advanced rebalance and current declarations, including cash/null sectors. Legacy latest-successful behavior remains. Nullable schema/type/rendering and real cash-turnover/component cases verify the displayed state. |
| P2 | Finite individual net returns above -1 could compound to floating-point zero. The advanced finite-positive-wealth guard accepted that zero and presentation cleaning could hide undefined drawdown. | cross_sectional.py:222 also refuses equity <= 0 before metrics/presentation. A 600-session fixed alternating-return/high-turnover case independently exercises underflow without any individual loss <= -1. No unrelated legacy economics was changed. |
| P2 | Changing quantiles, gross exposure or liquidity could change holdings/outcomes while leaving the advertised family fingerprint unchanged. | backend/app/scanner/validation.py:79 binds the full normalized scanner configuration; :88 checks retained request/family consistency. Three actual-selection cases and a rehashed inconsistent-request case verify this. The implementation result fingerprint already bound the full request; it was not the missing identity. |
| P2 | The new validation path inherited a permissive ScannerRequest: numeric strings/Booleans and unknown options could be coerced/ignored before computation. Opt-in advanced backtests had the same base-request gap. | validation.py:32 uses a strict validation-only subclass; backend/app/schemas.py:4832 validates raw new advanced options/types. Sixteen two-endpoint cases refuse before generation. An independent legacy model case preserves omitted-option coercion/ignored-option behavior. |
| P2 | New endpoint execution errors were sanitized, but pre-handler model errors still reached the global handler that echoed submitted values. Advanced declaration failures had the same privacy problem. The new validation body also lacked pre-parse byte/duplicate-key enforcement. | backend/app/scanner_validation_routes.py:13 streams at most 4 MiB, applies bounded plain-JSON/duplicate-key checks and sanitizes typed validation errors while retaining typed OpenAPI. main.py:435 and :4650 scope private errors to opt-in advanced requests. Secret-bearing nested errors, malformed/nonfinite/deep/oversize JSON and no-computation spies verify bounded 422s. Legacy error behavior is not globally rewritten. |
| P3 | Scanner education presented top-quantile-long/bottom-short and gross-equals-target as unqualified facts, although advanced projection can change signs and caps/scaling/cash can change gross. Current handoffs also still named the implementation branch/review as pending. | frontend/src/components/ScannerLabPanel.tsx:471 distinguishes legacy construction from actual advanced final weights; related current docs now record the reviewed target and pending publication gates. |

The existing browser scenario also had assurance gaps: an empty fold array could
satisfy every(), and checking only a filename did not verify download contents.
These are confirmed test-coverage gaps, not invented observed browser failures.
The same scenario now requires three nonempty audited folds, displayed raw/
Bonferroni/Holm values, declared provenance, beta/PBO/DSR unavailability, JSON
equal to the actual completed response, edit invalidation, navigation, no extra
research POSTs and the existing 1440/1024/768 layout assertions. No assertions
were weakened; no sleeps, retries or broad first() selector were added.

## Numerical, Timing and Legacy Conclusions

Actual integration: cross_sectional.py -> advanced.keyed_panel/advanced_weights
for opt-in requests; both basic and advanced use pnl.portfolio_pnl. Validation
uses the same generator, scorers, keyed panel, advanced weights and P&L directly,
then actual Phase 52 normalization/splits/audits and Phase 53 corrections.
Validation never reconstructs returns or weights from rounded/downsampled charts.

Phase 59 ols_fit is genuinely called for CURRENT cross-sectional score
residualisation with intercept/rank_policy=fail. Sector encoding is intercept
plus K-1 dummies; beta uses intercept plus one declared/trailing beta. This is
descriptive residualisation, not a new signal or learned return-prediction fit.

Residual orthogonality is not final-weight neutrality. Quantile selection is
followed by a separate selected-support joint least-squares/SVD projection.
Unselected names never enter; signs may change. Full design conditioning,
rank-exhausted support, zero/near-zero residual/direction and final constraints
are checked. Gross normalization, volatility scaling and gross caps are followed
by FINAL net/sector/beta checks with 1e-9 * max(1,gross); beta error additionally
uses the declared maximum-absolute-beta scale. Unsupported sector+beta modes
are refused, not approximated by ridge or populated with a forced portfolio.

Independent fixtures verify sector-explained scores -> cash, feasible sector
weights [0.25,-0.25,0.25,-0.25], and a known beta-neutral book
[0.25,0.25,-0.25,-0.25]. Missing inputs remain exclusions/refusals, not zero
exposures. Advanced failed rebalances actually set zero weights and charge
liquidation turnover; their previews now show that cash. No prior basket is
silently promoted to newly verified neutral holdings.

Synthetic sessions assume UTC-midnight cutoffs, not real exchange closes.
Declared exposures/liquidity must be available by decision t. Trailing beta and
fixed-weight sample volatility read only permitted returns through t, not
future rows. Minimum observations, zero/unknown factor variance, insufficient
volatility history, ddof=1, annualization 252, desired/actual scale, cap binding
and achieved ex-ante volatility remain explicit. The new hand volatility case
uses returns [.02,.04,.06], sample SD .02 and estimate .02*sqrt(252); target and
capped variants preserve final neutrality. The trailing-beta case recovers
known betas at its exact five-observation minimum. Fixed-history future-only
perturbations do not change earlier weights/betas. A different horizon's
synthetic generation is not used as a leakage test.

The synthetic generator, signals, bucket selector and metrics source blobs
match the pre-Phase-68 parent exactly. Generator blob:
e4a06a4a43710f9bd2f475b556715a7f2c5f0d35. The extracted shared P&L has the
same pre-68 equations:
gross[k] = weights[k-1] dot returns[k];
turnover[t] = sum(abs(weights[t]-weights[t-1]));
net[t+1] = gross[t+1] - turnover[t]*cost_bps/10000.
There is exactly one execution lag and one cost deduction, including
neutralisation/scaling/cash transitions. No borrow, real fills, impact model
or terminal liquidation is added.

Twelve independent fixed-panel legacy cases cover both strategy IDs, all three
frequencies, zero/positive costs, exact successful decisions and failed-basket
carry, gross/net returns, turnover, compounded equity, drawdown, latest basket
and skipped counts. Seven invalid-input cases preserve pre-generation refusal.
The direct legacy metrics helper's first-equity peak convention is a
pre-existing limitation, documented by a regression rather than rewritten;
normal scanner warmup includes a zero-return observation anchoring capital 1.
Legacy defaults/numerical behavior remain compatible; additive advanced fields
and nullable advanced sectors are not claimed to be identical API keys.

## Actual Fixed-Selection Validation and Declared Statistics

POST /scanner/validate evaluates actual predeclared DAILY dollar/sector
selections. No supervised parameters are fitted: trained_parameters=[] and
training_used_for_fit=false. Current test-date features/declarations may
transform current scores; held-out outcome labels fit nothing. Learned beta/
volatility and weekly/monthly carried-holding validation remain explicitly
unavailable with specific reasons, without execution through a basic path.

One sample represents a whole decision-date cross-section with exact asset/
session identity, feature-window metadata and a closed decision-to-next-session
outcome interval. Contemporaneous assets are never split across folds. Actual
normalize_samples, purged_kfold, audit_split and configuration/split fingerprints
are called. The independent seven-sample January 2023 case specifies:
test days [03,04,05]/[06,09]/[10,11], purged [06]/[05,10]/[09], and a two-calendar-
day embargo [none]/[11]/[none]. Exact train membership, weekend boundaries,
audits and actual API outcomes/costs are reconciled independently.

Each contiguous held-out block starts from cash and charges entry once.
No forced terminal liquidation is added; nonadjacent blocks are not stitched
into a fictional wealth curve. Retrospective purged CV is not chronological
deployable walk-forward or proof of learned-policy OOS performance.
All fixed candidates remain visible; there is no automatic winner.

The complete DECLARED family is retained in candidate order. Only valid supplied
p-values enter m; missing/null differs from zero. Invalid/nonfinite/Boolean
values and duplicate candidate IDs are rejected before calculation. Actual
Phase 53 adjust_p_values remains unchanged:
raw [.01,.04,.20], Bonferroni [.03,.12,.60], Holm [.03,.08,.20].
Values remain declared even when bound to input/family/result hashes; no
Sharpe/rank/return-derived p-value, supported inferential test or statistical
certification is invented. Partial-family counts/missing IDs and neutral
threshold states remain explicit. BH requires its stated independence/PRDS
assumptions. PBO/DSR remain unavailable.

## API, Export, UI and Browser Isolation

No new database, persistence/registry, provider, real universe or strategy was
added. POST Run/Validate are explicit. GET/navigation/input edits do not run
research; form/policy edits detach results and stale/unmounted responses are
ignored. Four new rendered component cases cover batched duplicate Validate,
edited/unmounted results, exact completed-result download and cash/null-sector
presentation. The existing duplicate Run case now dispatches two clicks within
one React batch while the button is still enabled, exercising the actual guard.

The download serializes the pinned completed response, including the retained
normalized request, seed/universe panel, candidates, split settings, costs,
outcomes and diagnostics. It does not mix later form edits. Family/result
consistency is checked without rerunning research. SHA-256 remains an integrity
identifier, not trusted provenance, independent execution or financial truth.
Bounded JSON refuses nonfinite material; unavailable values retain null/reasons.

Before generation, assets/calendar span, candidate/fold count and numeric
request options are bounded. Generated session/work dimensions are checked
before projection; date*asset^2 and the fixed candidate/fold caps prevent an
unbounded dimension product. Advanced caps: 50 assets, 1400 calendar days,
1000 sessions, 2,500,000 date*asset^2 units; declarations 10000 exposure/1000
factor rows. Validation: 30 assets, 420 calendar days, 300 sessions, 1-4
candidates, 2-5 folds and 0-30 embargo days. Canonical JSON bounds bytes,
depth and nodes; the new route also limits streamed request bytes before
typed parsing. No broad filesystem access/provider fallback is introduced.

Actual browser contract was READ, not executed:
scripts/strategy_ensemble_e2e.py is a fresh-process, single-worker/no-reload
factory; its documented backend port is 8766. It exclusively creates an
external quantlab-strategy-ensemble-e2e-* root, browser.sqlite3 and
isolation-token.txt, installing the DB override BEFORE importing app.main.
It verifies marker, file/link/device identity, actual get_db_path and serving
PRAGMA main location. The scanner spec requires a loopback frontend and
64-lowercase-hex E2E_STRATEGY_ENSEMBLE_TOKEN, then requests
/api/strategy-ensembles/e2e-isolation through that actual frontend proxy with
x-quantlab-e2e-token and no redirects before navigation. Kind/token/verified
flag/prefixed database identity must match; an opt-in flag alone is insufficient.

BACKEND_URL must point the user-owned frontend to that disposable backend.
E2E_BASE_URL selects the already-running loopback frontend; default localhost:3000.
The Chromium project defaults to the installed msedge channel. Playwright has
no webServer and starts no service. Per-request harness middleware covers
strategy-ensemble routes, not scanner routes: this scanner scenario is stateless
and performs no seeding. No broader per-scanner-request DB-gating claim is made.
Responsive/visual/download/navigation acceptance remains unexecuted.

## Inherited Verification: Separate Snapshots, Not New Review Passes

Read the preserved implementation report and retained machine records.
No workflow was fetched/triggered; implementation or Phase 67 CI would not
verify subsequent reviewer fixes.

| Historical run | Precise scope/result | Printed pytest / exits |
| --- | --- | --- |
| Broad 85bis2c9 | 250 passed, zero skips: policy21 + validation12 + scanner40 + factor98 + split engine35 + model API15 + overfitting29 | 387.93s; machine pytest/test process/outer 0 |
| Final scanner 6cjf48oi | 74 passed, zero skips: policy22 + validation12 + existing scanner40 | 14.43s; machine pytest/test process/outer 0 |
| Frontend implementation | 241 passed / 24 files; TypeScript passed | 6.73s Vitest; unit host7.4317306s, TypeScript16.2509173s; exits0 |
| Browser implementation discovery | 1 focused / 278 overall, zero executed | host2.2633041s /1.6326054s; exits0 |

Broad root C:/Users/jimli/AppData/Local/Temp/quantlab-backend-focused-85bis2c9;
manifest c5de9feed386651ff084f0b1ff661524691aeff205c19dcc9b21ae4c4ee7c373.
Final root C:/Users/jimli/AppData/Local/Temp/quantlab-backend-focused-6cjf48oi;
manifest d1eea1b44acf2414a16ca205d2f43b777d5a0efbdffc0286bea676c411535c5c.
Both snapshot identities are the pre-implementation parent plus dirty
implementation material, not clean implementation/review commit tests.

The ONLY executable change between those snapshots was advanced.py's explicit
selected-support rank exhaustion refusal, with its additional policy test.
The semantic runbook also changed. Direct manifest comparison additionally
finds README, STOP_POINT, TASKS, roadmap and the implementation ledger changed;
these documentation differences are not hidden by saying only three total
paths changed. The final 74 rechecked scanner integration/legacy, policy and
validation tests, not the existing factor/split/API/overfitting modules.
250+74 is not a final 324-case whole-suite pass.

Inherited machine pytest walls: 388.11108119995333s /14.928109099855646s;
snapshot setup6.804111399920657s /10.542118599871174s;
process390.90749899996445s /18.280113600194454s;
runner409.6810737999622s /36.8400268999394s.
Both retained source/snapshot/active-DB protections and child evidence passed;
SQLite violations were empty.

Preserved DEVELOPMENT failures, never relabelled:
- lbptw9h_: 57 passed/1 failed, 39.30s, pytest-process/outer1,
  runner86.368003100s; future-only fixture incorrectly changed historical bits.
- jr9ebnj_: 24 passed/8 failed/8 teardown errors,18.57s,
  pytest-process/outer1,runner32.517098100s; TestClient lifespan attempted a
  guarded TEST-OWNED DB initialization in db_free tests, not the active DB.
- Initial TypeScript exit2 concerned unsupported exact locator options in
  Testing Library. Historical focused frontend13 passed/2files,32.12s,exit0,
  preceded final test strengthening.

Inherited runtime: Windows Python3.13.5; Node24.21.0/npm11.17.0.
Implementation Python3.11.9 ast.parse of15 files was SYNTAX ONLY, not runtime
coverage and not verification of these later review fixes. No old Phase 67
symlink/DST/container task or implementation CI was rerun.

## New Review Verification

Source stable throughout the protected execution. One justified focused scope
covers new Phase 68 defects, the shared scanner kernel and the actual reused
factor/split/API/overfitting contracts; no complete local backend suite.

Exact invocation from C:/quantlab:

~~~powershell
& C:\quantlab\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused --test backend/tests/test_scanner_advanced.py --test backend/tests/test_scanner_validation.py --test backend/tests/test_scanner_review_quant.py --test backend/tests/test_scanner_validation_review.py --test backend/tests/test_scanner.py --test backend/tests/test_factor_diagnostics.py --test backend/tests/test_model_validation_engine.py --test backend/tests/test_model_validation_api.py --test backend/tests/test_overfitting_diagnostics.py
~~~

Snapshot/evidence **C:/Users/jimli/AppData/Local/Temp/quantlab-backend-focused-ntlrru_7**.
Manifest SHA-256 **99811c870fe425c393ae8ed1fa2b1b2f20a2094363e1bf1dbe3745fbecc5c25d**.
Identity HEAD is the implementation5428eb20... with the actual uncommitted
review source/tests and semantic runbook corrections captured in the manifest/diff.

**321 collected/selected; 321 passed / 0 skipped / 0 failed / 0 errors.**
All321 setup and teardown phases passed; no skip reason applies.
New review cases: quant35 + validation/API35 = **70, included in321**, not
additional passes. Existing delivered Phase68 cases22+12 and relevant older
scanner40/factor98/split35/model API15/overfitting29 account for the remainder.

- Printed summary **321 passed in623.54s (0:10:23)**.
- Machine pytest wall **623.7141177000012s**;
  startup/collection **7.217306799953803s**.
- Snapshot setup **5.885772499954328s**;
  child/test-process wall **626.8105032001622s**;
  total outer runner **649.6862733999733s**.
- Machine pytest exit **0**, pytest-process exit **0**, outer runner/tool exit **0**.
- worktree_bytes_unchanged, snapshot_bytes_unchanged, active_db_unchanged and
  child_evidence_complete all **true**; sqlite-violations.json is **[]**.
- Per-node/phase outcomes/durations, collection, JUnit, runtime/environment,
  source/diff and protection records are retained without cleanup.

Actual runtime: existing C:/quantlab/.venv/Scripts/python.exe, Anaconda
**Python3.13.5**, Windows11 build26100/AMD64, one worker; numpy2.4.6,
pandas3.0.3, scipy1.17.1, pydantic2.13.4, pytest9.0.3, fastapi0.136.3,
httpx0.28.1, starlette1.1.0, PyYAML6.0.3. No package/environment upgrade.

Frontend evidence root:
**C:/Users/jimli/AppData/Local/Temp/quantlab-phase68-review-21f06c29cb534fcd90c972d8a500013a**.
Fresh existence/version discovery verified Node **24.21.0** at
C:/Users/jimli/AppData/Local/OpenAI/Codex/runtimes/cua_node/cfb32733c877621e/bin/node.exe.
Existing CLI C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js reports
**npm11.12.1**, supported by engines; historical11.17.0 is not relabelled current.
Checks use Node directly, not an installation or borrowed package environment.

Exact frontend commands, cwd C:/quantlab/frontend; node is the verified full
executable above and externalEvidence is the external review directory:

~~~powershell
& $node node_modules/vitest/vitest.mjs run --reporter=default --reporter=json --outputFile.json=$externalEvidence/frontend-vitest-retry.json
& $node node_modules/typescript/bin/tsc --noEmit --incremental false
& $node node_modules/@playwright/test/cli.js test e2e/scanner-neutralisation.spec.ts --project=chromium --list --reporter=list
& $node node_modules/@playwright/test/cli.js test --project=chromium --list --reporter=list
~~~

| New check | Actual result | Printed / process duration | Exit |
| --- | --- | --- | --- |
| Initial frontend unit attempt | esbuild spawn EPERM before collection; no unit result | process2.8688814s | 1 |
| Authorized exact unit retry | 245 passed /24 files;0 failed/pending/todo | Vitest23.10s /process33.2382315s | 0 |
| TypeScript | no diagnostics; incremental cache disabled | process31.5938097s | 0 |
| Focused browser discovery | 1 test /1 file; no execution | process1.5891059s | 0 |
| Overall browser discovery | 278 tests /22 files; no execution | process1.9426224s | 0 |

The initial unit command used frontend-vitest.json as its requested JSON path
but failed before collection; its log/process record remains. Retry used process
escalation for the environment startup restriction, no code repair or weakened
test. The existing intentional setupIsolation console-error sentinel is a
passing assertion, not a concealed application failure. Four new component
cases are included in245. Nine frontend source/config files' SHA-256/sizes
match before/after; source remained frozen through all checks.

## Final Hygiene and Exact REVIEW Inventory

No staging occurred. All47 baseline data/frozen screenshot/historical-report
files retain exact SHA-256, sizes and mtime. Index bytes retain initial SHA-256
**8b6ec34d901951d24f5494836c79b4d01c530c4402ee077c98b43e7ce1cf12f7**;
staged set remains empty. VERSION, historical implementation report, Phase67
reports/tag and frozen screenshots remain unchanged. Tests use private
snapshots/test-owned storage; the active DB was not initialized/migrated.

Executable source/tests/frontend changes retain the protected snapshot bytes.
After verification, only seven current documents (CHANGELOG, README, STOP_POINT,
TASKS, roadmap, VERSION_MANIFEST and the runbook's evidence-handoff links) and
this new review report were finalized. The semantic runbook corrections were
already in the tested snapshot; later links/status prose are not claimed tested
executable bytes. This is not a final whole-tree or Python3.11 runtime pass.

Exact REVIEW pending set: **20 paths = 17 modified / 3 added**, all unstaged.

~~~text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M backend/app/main.py
M backend/app/scanner/cross_sectional.py
M backend/app/scanner/policies.py
M backend/app/scanner/validation.py
M backend/app/scanner_validation_routes.py
M backend/app/schemas.py
A backend/tests/test_scanner_review_quant.py
A backend/tests/test_scanner_validation_review.py
M docs/CROSS_SECTIONAL_NEUTRALISATION_AND_SCANNER_VALIDATION.md
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/PHASE_68_REVIEW.md
M docs/VERSION_MANIFEST.md
M frontend/e2e/scanner-neutralisation.spec.ts
M frontend/src/components/ScannerLabPanel.test.tsx
M frontend/src/components/ScannerLabPanel.tsx
M frontend/src/lib/types.ts
~~~

Tracked diff check and new-file trailing-whitespace/EOF checks passed; relative
review links resolve. No database/sidecar, credential, log, runtime binary,
cache/dependency/build/browser output or generated research report belongs to
this pending inventory. Small deterministic fixtures live in intended test
source; no synthetic JSON/CSV fixture is rejected merely for its format.
External evidence is retained, not deleted or staged.

## Later User-Only Staging and Publication Plan

This section is a plan, NOT an executed script. Recheck branch/full HEAD,
VERSION, exact membership/classifications, reviewed source identities and
existing staging before a separately authorized Git action. Preserve unrelated
staging; stop on unexpected changes. Do not use the27-path implementation list.

~~~powershell
$phase68ReviewPaths = @(
  'CHANGELOG.md',
  'README.md',
  'STOP_POINT.md',
  'TASKS.md',
  'backend/app/main.py',
  'backend/app/scanner/cross_sectional.py',
  'backend/app/scanner/policies.py',
  'backend/app/scanner/validation.py',
  'backend/app/scanner_validation_routes.py',
  'backend/app/schemas.py',
  'backend/tests/test_scanner_review_quant.py',
  'backend/tests/test_scanner_validation_review.py',
  'docs/CROSS_SECTIONAL_NEUTRALISATION_AND_SCANNER_VALIDATION.md',
  'docs/FORWARD_ROADMAP_PHASES_63_70.md',
  'docs/PHASE_68_REVIEW.md',
  'docs/VERSION_MANIFEST.md',
  'frontend/e2e/scanner-neutralisation.spec.ts',
  'frontend/src/components/ScannerLabPanel.test.tsx',
  'frontend/src/components/ScannerLabPanel.tsx',
  'frontend/src/lib/types.ts'
)
# Later USER-authorized action only; NOT executed by this review:
git --literal-pathspecs add -- @phase68ReviewPaths
git diff --cached --check
~~~

Do not execute the Markdown document itself. No blanket/directory staging,
force/renormalize, Git configuration change, reset/clean/stash/pull/rebase or
branch switch is part of this review.

**Safe to keep: yes, as bounded synthetic research.**
**Ready for a separately authorized user review commit: yes.**
No unresolved confirmed Phase68 correctness defect remains in the reviewed
scope; this is not a release, market/PIT/statistical certification or a
completed whole-tree/build/browser gate.

Remaining gates: user review commit; final exact-review-commit **Python3.11 CI**;
user production build; actual isolated browser execution/visual/download/
responsive acceptance. Existing legacy helper limitations and unsupported
learned-policy OOS, combined constraints, real data, PBO/DSR stay explicit.
No packages/services/Docker/market requests, Phase67 platform reruns or Phase69.

Expected later user subject:
**Review advanced cross sectional neutralisation scanner validation v1**.
Future user tag, not created:
**v4.86.0-cross-sectional-neutralisation-scanner-validation-v1**.
No staging, commit, push, tag, deployment, workflow trigger, second report or
evidence-finalization task was performed.

## Final Release Verification (2026-10-14)

This section supersedes the historical remaining-gates wording above, without
rewriting that review or its failures. Documentation-only finalization; no
implementation/review/test/build/browser/API computation repeated here.

### Exact Source and Attribution

Read-only Git inspection confirmed clean attached main, empty index and no
nonignored untracked files before edits, at review commit
**094d04263ecd713c3cc2f733b36969a513d21c3d**, committed tree
**5b767c968cc8b95b501f6f8a711a3cf3e4b55b99**. Implementation is
**5428eb20ae7c1dc33c2e875a1e33370e2423568b**. VERSION remains **4.86.0-dev**.
The review commit, not the later documentation commit, supplied the source for
the user-owned build/browser execution and exact-review CI.

Historical results retain their original attribution and scope:
implementation broad **250** and final scanner **74** passes on separate
snapshots, with recorded pytest/process/outer exits zero; review **321 passed,
zero skips, printed 623.54s**, including (not plus) **70** new regressions;
frontend review **245 passed**, TypeScript passed; focused/overall discovery
**1 / 278**, not execution. The initial esbuild spawn EPERM unit startup failure
remains separately recorded above. These are not a new whole-suite total.
Original runtime/protection limitations remain intact; Python 3.11 syntax-only
implementation evidence is not Python 3.11 runtime coverage.

### Exact-Review CI and User Production Build

CI run **38496359420**, attempt **1**, source
**094d04263ecd713c3cc2f733b36969a513d21c3d**:

| Job | Identity | Supplied conclusion |
| --- | --- | --- |
| Backend Tests | 115632903377 | completed / success |
| Frontend Tests & Build | 115632903141 | completed / success |

These results were supplied by the user and retrieved through the GitHub
connector in the coordinating conversation, NOT independently retrieved in this
documentation task. No counts, skip identities or runtime patch versions are
inferred from job success. This closes the exact-review CI gate, not CI for the
future documentation commit. No workflow was triggered or logs mined here.

User-reported production build used the exact review commit/tree above:
Node **24.21.0**, actual npm **11.12.1**, Next.js **15.5.25**. The recorded
packageManager is **npm@11.17.0**, not the actual npm version used.
BACKEND_URL was **http://127.0.0.1:8769**; build exit **0**, built `/api/:path*`
destination `http://127.0.0.1:8769/:path*` verified by the user, post-build
working tree clean. No retained build log was inspected here; these are
user-owned console results, not a new local build or a build of future docs.
Build ID **eWgKc5J8Z4fRTrSZD8GdP** is also confirmed by browser execution.json.

### Artifact-Confirmed Selected Browser Execution

Existing evidence read without execution or copying into Git:
**C:/Users/jimli/AppData/Local/Temp/quantlab-phase68-browser-50fc5c24cb584b3ebc1127568b01c54d**.
Files present: preflight.json, execution.json, junit.xml and test-results/;
test-results contains only .last-run.json, which reports passed/empty failedTests.
No successful screenshot or trace is required or claimed; configured reporters
retain those on failure. No manual visual inspection was performed here.

| Artifact | Confirmed fields |
| --- | --- |
| preflight.json | checked_at 2026-10-14T02:49:33.824Z (10:49:33.824 Asia/Taipei); Playwright 1.61.1; DIRECT and PROXY status 200, same nonempty database identity |
| execution.json | source_commit 094d04263ecd713c3cc2f733b36969a513d21c3d; spec e2e/scanner-neutralisation.spec.ts; Node 24.21.0; browser_channel msedge; build ID above; process_seconds 6.9708954; exit_code 0 |
| junit.xml | project hostname chromium; timestamp 2026-10-14T02:49:35.394Z (10:49:35.394 Asia/Taipei); exactly 1 test case, zero failures/errors/skips; scenario 2.729s; suite total 5.562899000000001s |

User-reported console/harness facts: actual selected browser Microsoft Edge
under project chromium; disposable backend on **8769**, production frontend on
**3100**; matching token/kind/disposable-DB proofs; one worker, retries **0**;
printed scenario **2.7s**, command summary **1 passed in 5.6s**; post-run Git
status clean. Node was selected through existing-runtime discovery. Artifacts
confirm status/identity equality, channel, source, versions, counts and exit;
they do not independently record all token/kind checks or service lifecycle.
No token values, credential contents or request headers are reproduced.
Printed summary, JUnit times and process wall time are distinct measurements.

This one selected committed Scanner scenario covers its asserted explicit
Scanner/validation requests, declared corrections, unavailable beta/PBO/DSR,
downloaded JSON equality, invalidation after edits, navigation and bounded
viewport checks. It is not all 278 E2E tests, full accessibility testing,
manual visual acceptance or independent statistical certification. No fresh
empty-DB assertion is claimed; the phase did not perform one.

### Earlier Failure Retained Separately

User-reported earlier evidence location:
**C:/Users/jimli/AppData/Local/Temp/quantlab-phase68-browser-da8d4aede7954060a9f866d14757638d**.
Read-only inspection found that directory present but empty; no failure log or
diagnostic artifact was available there to independently confirm its contents.
Retain the supplied account: initial DIRECT proof request failed before browser
scenario or Scanner computation; later GET-only diagnostics returned HTTP 200
for direct/proxy with matching token/kind/database identity, diagnostic exit 0.
Original failure root cause remains **unknown**, not a confirmed readiness/race
fault or a passed test. The successful run is a separate execution, not a
relabelling of the failure. No evidence/harness data was deleted in this task.

### Protection, Current Gates and Documentation Publication

Historical 47-file/source/snapshot/active-DB protections above remain evidence
from their original runs. No fresh active-database hashes/audit or DB access is
performed for documentation. The task began with the exact clean review tree;
only the eight existing authorized documents are changed, with source/tests,
fixtures/dependencies/workflows/configuration/VERSION and historical
PHASE_68_IMPLEMENTATION.md excluded. External artifacts stay external.

Implementation/review are committed; exact-review CI, user production build and
one selected isolated browser scenario are complete within the stated evidence
boundaries. Still pending: user documentation commit/publication/verification
and user-created milestone tag. No future documentation SHA, CI or build is
known or implied. Suggested user commit subject:
**Finalize phase68 release evidence and browser acceptance v1**.
Future user tag remains **v4.86.0-cross-sectional-neutralisation-scanner-validation-v1**;
tag creation is not authorized in this task.

Bounded product claims remain: synthetic universe, fixed daily-selection
validation, declared p-values, learned beta/volatility OOS and PBO/DSR
unavailable, no automatic policy selection, provider or new database, and no
alpha/PIT/production certification. Phase 69 is not started. Ready for the
user documentation commit after the authorized exact documentation staging;
no additional identical finalization cycle, tests/builds/browser/API rerun,
services, commit, push, tag, deployment or workflow trigger in this task.
