# Phase 64 Frontend Dependency Security Remediation

Verification date: 2026-09-15. Scope: frontend security remediation only, not
Phase 65. Application VERSION remains `4.82.0-dev`.

## Boundary

- Initial branch `main`, clean against `origin/main`; no staged, unstaged or
  untracked changes. HEAD `9d169edb4fbb66022d3643b31457fdecee3189e2`
  (`Review strategy return stream similarity portfolio ensemble diagnostics lab v1`).
- Implementation `1284b3115977f057f4690f643601dc329aac7797` is already committed.
- No index changes, commits, pushes, tags, CI triggers, services or deployment
  are authorized. No backend/Python/quant/schema/runner changes.
- Initial local Node `24.15.0`, npm `11.17.0`, lockfile v3. CI and frontend
  Docker select Node 20; the existing Vite 7.3.6 requires Node 20.19+ or 22.12+.
- Read governing instructions, Phase 63/64 reviews, test/registry guides,
  configs, runtime declarations, current handoffs and disposable E2E harness.

## Dependency Decision (Before Installation)

Versions below were checked against public npm metadata, maintainer release
notes and current advisory ranges. Roles describe dependency reachability, not
proof of exploitation. All paths below are relative to `frontend/node_modules`.

| Family and initial copies | Ancestry / role | Findings | Chosen target and mechanism | Compatibility / checks |
|---|---|---|---|---|
| Next 14.2.29 (one) | Direct application dependency; production App Router server and `/api` rewrites | h25 plus newer Next findings, including Windows RCE and rewrite request smuggling | Direct exact 15.5.25 | Smallest supported major; await globe query, React 19, navigation regressions, user build/browser gates |
| React/DOM 18.3.1 (one each) | Next, Recharts 2.15.4, RTL 16.3.2; runtime/test peers | Compatibility prerequisite, not an assertion that React 18 itself has these Next findings | Exact React/DOM 19.2.8; types 19.2.18 / 19.2.7 | Published peers accept this combination; null refs/scoped JSX types; all component tests and typecheck |
| PostCSS 8.5.15 root, 8.4.31 under `next/node_modules/postcss` | Root dev CSS pipeline through Vite/Tailwind/Autoprefixer; Next's production dependency also processes CSS at build time | qx2v, 6g55, r28c, fxqj | Direct exact 8.5.28; override only `next -> postcss` with `$postcss` | Next 15.5.25 still pins vulnerable 8.4.31. Same PostCSS 8 parse/process/plugin API; real in-memory Tailwind/Autoprefixer regression; build remains required |
| Browserslist 4.28.2 (one) | Babel helper-compilation-targets through plugin-react; Autoprefixer; dev/build | 73wf, c83g; also reconcile maintainer complexity fixes | Compatible transitive update to 4.29.0, no override/direct dependency | Existing parent semver ranges allow 4.x; browser target data can change generated CSS; CSS regression and build gate |
| baseline-browser-mapping 2.10.32 (one) | Browserslist transitive build dependency | w5vr (new audit finding) | Parent/transitive update to 2.11.23 | Same major; no direct application use; invalid input now throws instead of terminating process |
| Nanoid 3.3.12 (one) | Both PostCSS copies share it; production-reachable CSS utility | 28wg, 2v37; maintainer 3.3.19 huge-ID fix | Compatible transitive 3.3.19 through patched PostCSS, no override | Retain CommonJS-compatible major 3; verify every copy |
| postcss-selector-parser 6.1.2 (one) | Tailwind 3.4.19 and postcss-nested 6.2.0; build/dev | w9m9 | Compatible transitive 6.1.4, no override | Retain major 6 and Tailwind 3; parser serialization compatibility test through real Tailwind |
| Vitest / mocker / coverage 3.2.6 (one each) | Direct test runner/provider and internal mocker; dev only | 82fw (new audit finding) | Matched exact Vitest/coverage 4.1.11, internal packages via parent | Maintainer will not patch 3.x. Security-driven single-major update, not runner replacement. Retain jsdom/config/network guards; no Vitest 5/Node migration; full unit run once |

### Framework Choice and Applicability

[Next's support policy](https://nextjs.org/support-policy) lists 14 as unsupported
and 15 as Maintenance LTS (two years from 2024-10-21, so re-evaluate its support
window before a later release). 15.5.25 is the current 15.x backport, not the old
minimum patch from h25. [Its release](https://github.com/vercel/next.js/releases/tag/v15.5.25)
follows 15.5.24's security fixes and conditionally restores AVIF only with newer
Sharp. [App Router migration guidance](https://nextjs.org/docs/app/guides/upgrading/version-15)
requires React 19 and async request APIs. React/DOM 19.2.8 and matching 19.2 types
meet Next, existing Recharts and Testing Library peer ranges without force flags.

The application has a client workspace page, a server layout and `/globe`
redirect. There are no API route handlers: `next.config.js` rewrites `/api/:path*`
to `BACKEND_URL`. No Server Actions, middleware, `next/headers` or server fetch
cache configuration was found. Browser clients remain client-side fetches; no
new research-record caching or routing system is introduced. The globe query
is the only async request API migration. Next 15 retains the existing webpack
build default and deprecated `next lint` command; no bundler/lint migration.

Windows-hosted Next is within the RCE advisory's prerequisites; no exploit was
attempted. Rewrites are used here. AVIF optimization, CSP, custom servers,
WebSocket upgrades and attacker-controlled CSS inputs were not demonstrated
as reachable application exploit paths. This is not a waiver: affected packages
are updated regardless. PostCSS is a build dependency with filesystem access;
its nested copy must not be hidden by a root-only or production-only audit.
Nanoid's reported loops require attacker-controlled sizes. Vitest's new issue
requires a reachable mocker dev-server registration path; this repo's offline
jsdom unit run does not expose that server. Its affected dependency is still
replaced by the maintained security release.

### Sources and Ranges

All short advisory identifiers above mean the complete `GHSA-...` identifiers
in these links. Historical findings are not assumed current without checking.

- [Next h25m-26qc-wcjf](https://github.com/vercel/next.js/security/advisories/GHSA-h25m-26qc-wcjf): 14.x remains affected; the 15.5 branch minimum for this finding is 15.5.10.
- [Next Windows RCE p293-qw3h-jr36](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36) and [AVIF 2xp9-vwfh-vxw4](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4): 15.5 branch patched at 15.5.24.
- [Browserslist 73wf-gq98-2v4g](https://github.com/browserslist/browserslist/security/advisories/GHSA-73wf-gq98-2v4g) and [4.28.7 release](https://github.com/browserslist/browserslist/releases/tag/4.28.7): patched above 4.28.6. [4.29.0 release](https://github.com/browserslist/browserslist/releases/tag/4.29.0) is compatible with existing parents.
- [PostCSS r28c-9q8g-f849](https://github.com/postcss/postcss/security/advisories/GHSA-r28c-9q8g-f849): <=8.5.17, patched 8.5.18. [fxqj-rqcc-2cmp](https://github.com/postcss/postcss/security/advisories/GHSA-fxqj-rqcc-2cmp): <=8.5.22, patched 8.5.23. Older [6g55-p6wh-862q](https://github.com/postcss/postcss/security/advisories/GHSA-6g55-p6wh-862q) affects <=8.5.11; [qx2v-qp2m-jg93](https://github.com/postcss/postcss/security/advisories/GHSA-qx2v-qp2m-jg93) affects <8.5.10. [8.5.28](https://github.com/postcss/postcss/releases/tag/8.5.28) includes a type regression fix.
- [Nanoid 28wg-ghj8-5hjv](https://github.com/advisories/GHSA-28wg-ghj8-5hjv): 3.x patch 3.3.16. [2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8): 3.x patch 3.3.18. [3.3.19](https://github.com/ai/nanoid/releases/tag/3.3.19) adds a huge-ID safeguard.
- [Selector parser w9m9-85wc-3x92](https://github.com/advisories/GHSA-w9m9-85wc-3x92): >=6.1.0 <6.1.3 or >=7.1.0 <7.1.3. [6.1.4](https://github.com/postcss/postcss-selector-parser/releases/tag/6.1.4) adds a serialization follow-up.
- [Baseline mapping w5vr-8v7q-w6rv](https://github.com/advisories/GHSA-w5vr-8v7q-w6rv) and [maintainer change](https://github.com/web-platform-dx/baseline-browser-mapping/pull/137): >=2.0.0 <2.11.0.
- [Vitest 82fw-gwwq-j7x9](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9): >=2.1.0 <4.1.11; no 3.x backport planned. [4.1.11 release](https://github.com/vitest-dev/vitest/releases/tag/v4.1.11) restricts redirect mocks to the file-serving allowlist. Existing Vite 7.3.6, Node and jsdom are compatible; 5.x would require an unnecessary runtime migration.
- Package metadata was read from `https://registry.npmjs.org/<package>/<version>`, including engines, dependencies and peer dependencies. GitHub's public version-filtered advisory API returned empty arrays for each proposed target; this is supplementary evidence, not a security certification.

The API filter was independently checked with `next@14.2.29`: 29 findings,
versus none for `next@15.5.25`. The original full audit retains every advisory
and affected range. Next's complete matching baseline set (all `GHSA-`):

```text
3h52-269p-cp9r g5qg-72qw-gw5v 4342-x723-ch2f xv57-4mr9-wg8v
mwv6-3258-q52c 5j59-xgg2-r9c4 9g9p-9gw9-jx7f h25m-26qc-wcjf
ggv3-7p47-pfv8 3x4c-7xq6-9pq8 q4gf-8mx6-v5v3 8h8q-6873-q5fj
3g8h-86w9-wvmq ffhc-5mcf-pf4q vfv6-92ff-j949 gx5p-jg67-6x7h
h64f-5h5j-jqjh c4j6-fc7j-m34r wfc6-r584-vfw7 36qx-fr4f-26g5
m99w-x7hq-7vfj 89xv-2m56-2m9x 68g3-v927-f742 4633-3j49-mh5q
4c39-4ccg-62r3 p9j2-gv94-2wf4 955p-x3mx-jcvp p293-qw3h-jr36
2xp9-vwfh-vxw4
```

Browserslist's other matching baseline finding is
[GHSA-c83g-rgw3-j3cx](https://github.com/advisories/GHSA-c83g-rgw3-j3cx)
(unbounded query-result caching, <=4.28.6). Current target checks also cover
newer published ranges, not just the named baseline findings. For Nanoid,
the already-fixed integer-overflow advisory in 3.3.12 was not confused with
the two still-affected generator-size advisories.

## Resulting Tree and Compatibility

Every relevant installed package matches its lockfile version. Exactly one
resolved instance remains for each family in the decision table. The nested
Next PostCSS 8.4.31 is gone: Next resolves the root 8.5.28 through the scoped
override. PostCSS remains production-reachable in the lockfile despite also
being a direct dev declaration; it was not moved to hide an audit finding.

Lockfile dependency entries changed from 423 to 392 (excluding root). Next's
env/SWC/styled-jsx/helpers follow its parent release, including optional Sharp
0.35.4 and platform binaries. React brings scheduler 0.27.0 and matching types.
Vitest's internal packages follow 4.1.11; its obsolete vite-node/tinypool and
coverage dependencies disappear, and the parent requires newer Chai/AST
coverage utilities. Browserslist brings updated browser datasets and mapping.
The npm peer-tree resolution also advanced Recharts' compatible `fast-equals`
patch 5.4.0 to 5.4.2; Recharts itself stays 2.15.4. Vite stays 7.3.6,
plugin-react 4.7.0, Tailwind 3.4.19, jsdom 25.0.1 and Playwright 1.61.1.
No blanket update, lockfile deletion, manual integrity edit or peer-bypass flag.

Application changes are deliberately small:

- `/globe` awaits the query promise before redirecting. Five tests cover
  pending resolution, first repeated values, trimming/encoding, empty input
  and unchanged canonical destination/dynamic behavior. Only Next's redirect
  function is mocked; this is not a server/browser integration test.
- `GlobeLabPanel` declares the nullability its DOM ref already has.
  `PortfolioStressDetail` imports React's element type instead of using the
  removed global JSX namespace. Neither change alters rendered content or math.
- Three tests read the actual unchanged Next rewrite configuration with the
  default URL and both spellings of the disposable harness URL. They protect
  configuration, not actual proxy forwarding, which remains a browser gate.
- One test resolves PostCSS from Next's package location and processes real
  Tailwind responsive/color utilities plus Autoprefixer CSS in memory. No
  build output or user file is written. It does not replace the production build.

The [version-pinned Vitest 4 migration guide](https://github.com/vitest-dev/vitest/blob/v4.1.11/docs/guide/migration.md)
was checked after the hosted v4 guide could not be opened by the browser tool.
Existing explicit includes/excludes, mock clearing/restoration and network
guards remain unchanged and pass. No removed advanced runner API is used.
V8 coverage remapping changes in v4; coverage percentages were not rerun or
compared and old coverage numbers are not asserted equivalent.

## Verification Evidence

External evidence directory (not a tracked report/artifact):
`C:\Users\jimli\AppData\Local\Temp\quantlab-phase64-security-4fb42e2912c74bef84d4b41de355408e`.

Before changes: full `npm audit --json` exit 1, 9 affected package nodes
(1 critical, 3 high, 4 moderate, 1 low). Production `npm audit --json --omit=dev`
exit 1, 3 affected nodes (1 critical, 2 high). The full-audit wrapper initially
failed to parse trailing npm update notices; the complete JSON was recovered
from the preserved raw output without another audit. An advisory-query wrapper
also initially counted an empty array as one object; a corrected query preserved
raw `[]` responses separately. Neither wrapper error was a vulnerability result.
An unprivileged process inventory was denied; read-only elevated inventory
succeeded and showed no QuantLab Next/Vite process. No process was stopped.

| Command (working directory `C:\quantlab\frontend`) | Result |
|---|---|
| `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` | Exit 0; updated only declarations' resolution, not installed tree. Transitional warnings referenced old React 18 peer nodes being replaced. |
| `npm update browserslist baseline-browser-mapping postcss-selector-parser --package-lock-only --ignore-scripts --no-audit --no-fund` | Exit 0; targeted remaining compatible transitives. |
| `npm ci --strict-peer-deps --no-audit --no-fund` | One install, exit 0, 308 platform-selected packages; no peer override/force flags or final peer errors. |
| `npm ls --all --json` | Exit 0, no dependency problems. All affected lockfile/installed copies additionally compared. |
| `npm run test:unit` | One full run: 166 tests, 15 files passed; exit 0; Vitest duration 12.28s. Original 157 retained, nine new tests in two files. |
| `npx tsc --noEmit` | Exit 0. No compatibility failures or repeat run needed. |
| `npx playwright test --list --project=chromium --reporter=list` | Exit 0; 275 tests in 19 files, unchanged discovery. No execution or browser/report overwrite. |
| `npm audit --json` | After: exit 0, no known findings reported in full tree. |
| `npm audit --json --omit=dev` | After: exit 0, no known findings reported in production tree. |
| `git diff --check` | Passed; only Git's LF/CRLF conversion notices, no whitespace errors or configuration change. |

Raw results are `npm-ci.log`, `unit-tests.log`, `typescript.log`,
`chromium-discovery.log`, `dependency-tree.json`, and both `audit-after-*.json`
with separate stderr files in the external evidence directory. No frontend
test was removed, skipped to pass, globally muted or replaced by a successful
HTTP mock. The nine new tests are all deterministic/offline.

Install warnings: existing Recharts 2 and `whatwg-encoding` deprecations;
npm's allow-scripts warning listed esbuild 0.28.2's uncovered postinstall.
No blanket script approval was added. The installed esbuild-backed unit
transform ran successfully. These warnings are distinct from advisory findings.
No after-audit tool failure occurred. Counts alone are not proof of complete
security: the named ranges, all resolved copies and maintainer patches were
also reconciled. No dependency finding remains identified by this bounded
check; unknown/unpublished issues and deployment exploitability remain unverified.

Frontend build was not run in Codex by instruction. Please run it locally.
No dev server, production server, actual browser E2E or backend suite ran here.

## Existing Backend Evidence

Read-only [CI run 34814054179](https://github.com/hello696878/quantlab/actions/runs/34814054179)
is completed/success for exact SHA `9d169edb4fbb66022d3643b31457fdecee3189e2`.
Both Backend Tests and Frontend Tests & Build jobs and their test/build steps
are successful. This covers the base review commit, NOT this dependency patch.
The review's 198 focused Windows backend tests and four exit statuses of zero
remain separate evidence. The earlier 4,359-pass full run is historical only.
No backend suite is rerun for this frontend-only patch.

## Preservation and Handoff

Initial hashes captured for all 1,061 tracked files and 24 protected data,
artifact and screenshot files; Git index hash captured separately. Comparisons
found only the intended source/docs changes, no backend changes, no protected
size/hash/mtime changes and no index change. No DB connection was opened;
protection checks read file bytes only. Existing frozen fixtures/screenshots,
artifacts, user configuration and `.next` output were not edited or deleted.
TypeScript's normal ignored incremental cache and installed node_modules are
verification/install outputs, not staged source.

Exact changed-path list for a later explicitly authorized staging step
(10 paths; none staged by this task):

```text
TASKS.md
STOP_POINT.md
docs/PHASE_64_SECURITY_REMEDIATION.md
frontend/package.json
frontend/package-lock.json
frontend/src/app/globe/page.tsx
frontend/src/app/globe/page.test.ts
frontend/src/components/GlobeLabPanel.tsx
frontend/src/components/PortfolioStressDetail.tsx
frontend/src/test/frameworkCompatibility.test.ts
```

User-owned production build, isolated real-browser verification, final-commit
CI and a targeted independent dependency/override check remain required. Do not
call the application release-ready based on unit tests or an audit count.

### Remaining Release Gates

- Production build and token-verified browser execution through the real
  frontend proxy, including 1024/768 layouts, charts, navigation/back/forward,
  saved mutable records and retry/error behavior. Unit tests do not certify
  React 19 chart geometry, hydration or compiled Next behavior.
- A targeted independent check of the dependency/override decision and final
  lockfile, not another broad Phase 64 backend review.
- Exact-SHA CI for the eventual user-created patch commit. The base commit's
  successful build does not cover these dependencies; no workflow was triggered.
- CI and Docker still select Node 20. Although its >=20.19 releases satisfy
  package engines, [Node's current support table](https://nodejs.org/en/about/previous-releases)
  lists 20 as EOL. A supported Node 24 LTS runtime/CI update needs a separate
  bounded decision before release. It is not silently included here because
  the selected dependency compatibility does not require changing those files.
  Local checks used Node 24.15.0; this is not a Node/OS security certification.
- Recheck Next 15's Maintenance LTS window before release (two years from
  2024-10-21). Recharts 2's deprecation remains a maintenance/browser-risk note,
  not a newly established vulnerability or authorization for a chart rewrite.

**Safe to keep:** yes, as a bounded uncommitted security patch with successful
local checks. **Ready for targeted patch review and a later user-created
commit:** yes, with these pending gates visible. **Ready to release:** no.
No complete-security, production-build or real-browser success claim is made.
Suggested later user-created subject:
`Fix frontend dependency security blockers for phase64 release`.
No staging, commit, push, tag, deployment or Phase 65 action occurred.

## Exact User-Only Build and Browser Commands

These are a handoff, not commands executed by Codex. Use three fresh PowerShell
windows. Confirm ports 8766 and 3100 are free; do not stop another user's service
or redirect this test to the ordinary backend. Use the existing repo venv and
the installed frontend dependencies. No backend full rerun is needed here.

Shell 1, disposable backend (one worker, no reload):

```powershell
Set-Location C:\quantlab
$env:E2E_STRATEGY_ENSEMBLE_TOKEN = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))")
if ($LASTEXITCODE -ne 0) { throw 'Token generation failed' }
Write-Output $env:E2E_STRATEGY_ENSEMBLE_TOKEN
.\.venv\Scripts\python.exe -m uvicorn scripts.strategy_ensemble_e2e:create_app --factory --host 127.0.0.1 --port 8766
```

The factory creates an exclusive external test DB before importing the app;
keep the displayed token for shell 3. It never points at the active local DB.

Shell 2, final production build and server against that harness:

```powershell
Set-Location C:\quantlab\frontend
$env:BACKEND_URL = 'http://127.0.0.1:8766'
$env:NEXT_TELEMETRY_DISABLED = '1'
npm run build
if ($LASTEXITCODE -ne 0) { throw 'Production build failed; do not start or test a stale build' }
.\node_modules\.bin\next.cmd start --hostname 127.0.0.1 --port 3100
```

The direct local Next binary avoids `npm start`'s hardcoded `--port 3000`;
there is exactly one port argument. Set `BACKEND_URL` before BOTH build and
start because rewrites from an older build can point to another backend.

Shell 3, same token, loopback frontend and a NEW external output directory:

```powershell
Set-Location C:\quantlab\frontend
$env:E2E_STRATEGY_ENSEMBLE_TOKEN = Read-Host 'Paste the exact token from shell 1'
if ($env:E2E_STRATEGY_ENSEMBLE_TOKEN -cnotmatch '^[0-9a-f]{64}$') { throw 'Invalid token' }
$env:E2E_STRATEGY_ENSEMBLE_ISOLATED = '1'
$env:E2E_BASE_URL = 'http://127.0.0.1:3100'
$env:E2E_BROWSER_CHANNEL = 'msedge'
$browserEvidence = Join-Path $env:TEMP ('quantlab-phase64-security-browser-' + [guid]::NewGuid().ToString('N'))
npx playwright test e2e/strategy-ensemble.spec.ts --project=chromium --reporter=list --output $browserEvidence
if ($LASTEXITCODE -ne 0) { throw 'Browser verification failed; retain the evidence' }
```

This selects the existing 21-test Strategy Ensemble workflow, including its
layout checks. Before any navigation/seed, it requires the token-bound identity
proof via `/api/strategy-ensembles/e2e-isolation` from the actual frontend proxy.
The opt-in flag alone is not proof. A proof failure must be investigated, never
bypassed by seeding an ordinary backend. The list reporter and unique output
preserve previous browser reports and frozen screenshots. Inspect the built
app's other existing navigation, formulas/charts and `/globe?market=tw` manually
as additional framework smoke checks; do not run unrelated mutating specs
against this harness without their own verified isolation.

## Independent Review and Runtime Alignment: 2026-09-16

This section supersedes the earlier runtime gate, ten-path handoff and
three-shell commands, not the dated implementation evidence above. No backend
suite, build, service, browser, Docker build or CI workflow was run in this review.

### Identity and Evidence Reconciliation

- Branch `main`, HEAD `9d169edb4fbb66022d3643b31457fdecee3189e2`, VERSION
  `4.82.0-dev`; index empty. The exact original ten paths matched the list above.
- Starting file copies and ordered SHA-256 manifest were captured before edits.
  Manifest SHA-256:
  `6448A1017C31F304CD3703AFE4195CE411703532C6C93507E881492EA856FFEF`.
  Index SHA-256:
  `F00FF3DA7B6CBA538F203F539C6DB549B4B9386D009EFB837E729DCBEEF36076`.
- New external evidence:
  `C:\Users\jimli\AppData\Local\Temp\quantlab-phase64-security-review-c144b6a55821408eaf1c889e52f4d2ea`.
  `identity.json`, `starting-patch.json`, `starting-patch/`, `source-before.json`
  (1,061 tracked files) and `protected-before.json` (27 files including env files)
  identify the actual working-tree bytes, without a preliminary commit.
- The earlier install/unit/discovery logs support 308 installed packages,
  166 tests/15 files and 275 discovered tests/19 files. Earlier audit JSON
  supports full-tree 9 to 0 and production 3 to 0, not nine distinct CVEs.
  Its full-before output has a trailing npm notice. The named old TypeScript
  log is **absent**, not independently recoverable as a successful empty log.
  Old command exit codes are author-reported, not embedded in those raw logs.
  Today's structured result files record each new exit code explicitly.
- Public CI job metadata independently confirms both jobs succeeded on the
  exact base review SHA. The supplied backend summary, **4,459 passed in
  704.74s**, is user-provided evidence; job metadata does not contain that count.
  Neither that run nor the historical 198 focused / 4,359 full results executes
  the uncommitted security patch. No backend test was repeated.

### Findings and Reviewer Changes

| Severity | Confirmed finding | Resolution / why it matters |
|---|---|---|
| P1, release blocker | Both CI application runtimes and Docker still selected EOL Node 20. | CI now resolves latest Node 24; Docker retains Alpine/single-stage architecture with `node:24-alpine`. Engine floor and current instructions agree. This removes an unsupported declared runtime, not every possible runtime vulnerability. |
| P2 | Base CI annotations explicitly warn that checkout v4, setup-node v4 and setup-python v5 declare Node 20 and are forced onto Node 24. Browser artifact upload v4 also declares Node 20. | Use checkout v5, setup-node/setup-python v6 and upload-artifact v6, verified from official action manifests/releases. No insecure opt-out. |
| P2, handoff | Original build and start commands were separate top-level statements: pasted execution could continue to stale build startup after an error. Runtime and Python identity checks were also absent. | Replacement commands below enclose build/start in one guarded block and select explicit executables, loopback ports and the token-bound disposable factory. |
| P3 | Current onboarding/docs still recommended Node 18/20 and described old framework/test packages. | Update relevant install/CI/onboarding guidance, plus environment/CI-summary display text, without changing test runners. |
| P3 | PostCSS regression duplicated a literal version; the old report names a missing TypeScript log. | Read the version and override relationship from the real manifest while retaining real CSS processing. Record the evidence gap above and fresh TypeScript exit below. |

No verified defect required changing the original three application compatibility
edits, package versions, financial calculations, API schemas or routing. All nine
new regressions remain. Runtime differences between Windows and Alpine, compiled
proxy behavior, React 19 chart geometry and hydration remain **unverified risks**,
not asserted defects or successful browser coverage.

### Independent Dependency Review

All matching nested lockfile entries and installed manifests were compared, not
just root dependencies. One instance remains per named family. Registry metadata
confirms Next 15.5.25 still requires PostCSS 8.4.31; the narrow
`next -> postcss: "$postcss"` override is therefore necessary. Next resolves the
same PostCSS 8.5.28 instance as the tested Tailwind/Autoprefixer pipeline. PostCSS
and Nanoid remain production-reachable; no package was moved to hide findings.

Exact versions retained: Next **15.5.25**; React/React DOM **19.2.8**;
React types **19.2.18**, DOM types **19.2.7**; PostCSS **8.5.28**;
Browserslist **4.29.0**; baseline-browser-mapping **2.11.23**;
Nanoid **3.3.19**; postcss-selector-parser **6.1.4**;
Vitest/mocker/coverage **4.1.11**. Vite **7.3.6**, Recharts **2.15.4**,
Playwright **1.61.1** and Sharp **0.35.4** are unchanged by this review.

The installed peer graph agrees with published React/DOM, Next, Recharts and
Testing Library ranges. App Router uses React 19, not the Pages Router's older
React allowance. Current version-filtered GitHub advisory responses were empty
for all 15 inspected package/version targets (including the five requested
families, framework peers and test tooling). Positive control Next 14.2.29
returned 29 findings. `current-advisories.json` retains the real arrays and full
positive-control records, avoiding the old empty-array counting mistake.
The ranges and maintainer sources cited in the implementation section were
reconciled with this check, including newer PostCSS/Nanoid/Next findings, not
treated as a permanently complete list. These queries and audits do not cover
unpublished vulnerabilities or prove an application exploit path.

`registry-metadata.json`, `starting-dependency-copies.json`, final
`dependency-tree.json` and `final-dependency-copies.json` retain the ancestry,
engines/peers and all-copy checks. Lockfile refresh changed **only root engines**;
all 392 dependency entries and integrity values are preserved from the starting
patch. No `--force`, `--legacy-peer-deps`, audit ignore, severity threshold,
registry switch or manual node_modules repair. Registry is npmjs.org; configured
omit is empty, audit enabled, legacy peers/force disabled. The CI/install command
explicitly enables strict peers regardless of npm's default setting.

### Runtime Policy and Exceptions

- Node **24 LTS**, project floor `>=24.20.0 <25`, npm `>=11 <12`.
  `packageManager: npm@11.17.0` records the verified npm tool; it is not an
  automatic installer or enforcement mechanism. CI/Docker may use the npm 11
  bundled with their chosen Node image; record its actual version in release
  evidence and retain strict-peer install/tests. No global npm/Node update.
- Main CI and browser CI: `node-version: "24"`, `check-latest: true`.
  Docker: `node:24-alpine`, unchanged OS family and build architecture.
  Release builders must pull the moving tag and record the resolved image;
  no image digest is invented. Compose has no Node override and its
  `BACKEND_URL` build argument/runtime value remain unchanged.
- Official [Node schedule](https://github.com/nodejs/Release/blob/main/schedule.json)
  ends Node 20 support on 2026-04-30; Node 24 is supported through 2028-04-30.
  [24.21.0](https://nodejs.org/en/blog/release/v24.21.0) is the current LTS release
  on this review date, but is **not installed locally**. The already-available
  [24.20.0](https://nodejs.org/en/blog/release/v24.20.0) is used for bounded
  compatibility checks, not represented as the newest runtime or an OS/TLS
  security certification. Its embedded Undici 7.29.0 advisory query returned no
  matches. The engine floor is a tested minimum, not a permanent security floor:
  use the latest patched 24.x before release and recheck advisories then.
- Actual selected executable:
  `C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\6f12e0ef1c6e5061\bin\node.exe`
  (**24.20.0**, Windows x64). npm CLI:
  `C:\Users\jimli\AppData\Roaming\npm\node_modules\npm\bin\npm-cli.js`
  (**11.17.0**). Child PATH was changed only inside verification processes.
  Global Node remains **24.15.0**; bundled primary Node is **24.19.0**. The
  Program Files npm CLI itself is 11.12.1, while its wrapper redirects to the
  roaming 11.17.0 CLI; explicit invocation avoids ambiguity. No downloads or
  global/PATH/system settings changes were made to obtain a Node runtime.
- All applicable dependency engines accept this runtime. An initial read-only
  preflight incorrectly included Sharp's optional Windows **ia32** binary,
  whose engine is Node 20 only. Correct platform filtering excludes it on x64;
  the install had not started. Windows 32-bit is not verified/supported by this
  handoff. Docker image metadata confirms the official 24 Alpine tag exists;
  static inspection is **not** a Docker build/runtime check.
- No existing `.nvmrc`/`.node-version` was found; none was invented.
  `@types/node ^20` is a compatible compile-time API baseline (accepted by
  Vite/Vitest peers), not a Node runtime selection. It remains unchanged.
  Historical release/showcase copy is not rewritten. The old missing-npx hint
  in `scripts/run_frontend_typecheck.ps1` still says Node 18; it does not select
  a runtime and was left outside the prohibited test-runner-code scope. Use
  the current frontend README/engine requirement, not that legacy hint.

### Actions Runtime, Separate From Application Node

Official sources: [checkout v5](https://github.com/actions/checkout/releases/tag/v5.0.0),
[setup-node v6](https://github.com/actions/setup-node/tree/v6),
[setup-python v6](https://github.com/actions/setup-python/releases/tag/v6.0.0),
[upload-artifact v6](https://github.com/actions/upload-artifact/releases/tag/v6.0.0).
Their manifests use Node 24 and require runner **2.327.1+**. Upload-artifact v5
was inspected and still defaults to Node 20; v6 is the necessary runtime move,
not a blanket upgrade to every latest major. Setup-node v6's automatic caching
change is compatible with the already-explicit npm cache and lockfile path.
Existing moving major action tags are retained as a policy, not described as
immutable SHA pins. Ubuntu hosted runners, workflow triggers/permissions,
Python 3.11, `python -m pytest -q`, test/build gates and browser isolation opt-in
are preserved. Changing Actions' runtime does not install application Node;
both were aligned separately. Base CI annotations and official releases are
retained in `base-frontend-ci-annotations.json` / `action-runtime-sources.json`.

### Framework Contract Review

- Five globe tests exercise awaiting an unresolved query, repeated parameters,
  trimming/encoding and missing/empty inputs. Only the final redirect primitive
  is mocked; they do not claim a compiled Next request was exercised.
- Three proxy-configuration tests inspect the real `next.config.js`, including
  both disposable BACKEND_URL spellings. The CSS test checks the declared scoped
  override and processes actual responsive/color utilities and vendor prefixes;
  it is not solely a version assertion. Unit network guards remain intact.
- No API Route Handler, Server Action, middleware, `next/headers` request API
  or server fetch-cache layer was found. The only asynchronous request API edit
  is the globe query. Existing client/server boundaries and mounted/effect
  cleanup remain; Strategy Ensemble list effects reject stale responses and
  actions use a lock plus unmount guard. Browser APIs stay guarded/client-side.
- The installed Next proxy implementation retains query-string reconstruction,
  request/body streaming and HTTP proxy behavior; offline proxy failures can
  return non-JSON 500s. The Strategy Ensemble client uses `cache: "no-store"`,
  GET/POST and JSON bodies, preserves meaningful 4xx/422 errors, catches network
  failures and provides a friendly non-JSON/5xx fallback. The identity proof uses
  Playwright's direct API request through the **frontend** rewrite, with token
  matching and redirects disabled, not a cacheable Server Component fetch or
  an environment-only attestation. No proof/baseline safety check was weakened.
- Canonical registry, Sidebar, Dashboard/palette commands, Strategy Ensemble
  permalink and Globe/back/forward paths remain wired to existing state.
  Formula components render local KaTeX; chart wrappers remain unchanged.
  Unit/type checks cannot certify production hydration, geometry, request
  forwarding, all HTTP verbs or browser history; the bounded real smoke below
  is still required. No API contract, financial logic or chart data changed.

### New Verification Results

Every command uses the explicit runtime above. No successful full check was
repeated. A sandbox `EPERM spawn` stopped the first unit command **before test
collection**; its log/result were kept and the permitted retry executed the suite.

| Command / check | New result |
|---|---|
| Lockfile-only strict refresh, scripts/audit/fund disabled | Exit 0; root engines only, no package resolution changes |
| `npm ci --strict-peer-deps --no-audit --no-fund` | One clean install, exit 0; 308 packages in 44s |
| `npm run test:unit` | 166 passed, 15 files, exit 0; 5.36s reported duration; first sandbox launch failed before collection |
| `npx tsc --noEmit` (local npm exec equivalent) | Exit 0, no diagnostics |
| `npx playwright test --list --project=chromium --reporter=list` | Exit 0; 275 tests, 19 files; discovery only |
| `npm ls --all --json` | Exit 0, no dependency problems |
| `npm audit --json` | Exit 0; 0 findings; valid JSON, no registry error |
| `npm audit --json --omit=dev` | Exit 0; 0 findings; valid JSON, no registry error |

`npm-ci-result.json`, `runtime-identity.json`, `frontend-check-results*.json`
and `tree-audit-results.json` record actual process exits. Separate logs preserve
stderr and the failed sandbox attempt. `--no-audit` was used only to separate
installation from the two full-scope final audits, not omit evidence. Existing
Recharts/whatwg-encoding deprecations and npm's uncovered esbuild postinstall
warning remain disclosed; no blanket script approval was added. The actual
esbuild-backed unit transforms succeeded. V8 coverage was not rerun.

Frontend build was not run in Codex by instruction. Please run it locally.
No actual browser execution or Docker build/runtime result exists for this patch.

### Protection and Exact Future Staging Inventory

Starting tracked bytes, all 27 protected data/sidecar/artifact/screenshot/env
files and index identity were checked again at handoff: no unexpected tracked
changes, protected size/hash/mtime changes, backend/screenshot diff or index
change; nothing staged. See `final-hygiene.json`. `git diff --check` passed
(only existing LF/CRLF conversion notices; no Git configuration change).
All five replacement PowerShell blocks parsed without syntax errors; they were
not executed. The original application compatibility fixes and five globe
regressions are byte-identical to the captured starting patch.
The intended set is **23 paths** (20 tracked modifications, three new files),
not an artificial preservation of the original count of ten. The original
application fixes and tests remain; only the test's duplicate version literal
was made manifest-driven. No backend source/dependency/schema/test-runner file,
fixture, active database, screenshot or prior evidence is part of this set.

Future user-owned staging commands **only**, not executed by this review:

```powershell
Set-Location C:\quantlab
$paths = @(
  '.github/workflows/browser-e2e.yml'
  '.github/workflows/ci.yml'
  'README.md'
  'STOP_POINT.md'
  'TASKS.md'
  'docs/CI.md'
  'docs/CI_BROWSER_E2E.md'
  'docs/DEVELOPER_ONBOARDING.md'
  'docs/FRONTEND_COMPONENT_TESTING.md'
  'docs/LOCAL_DEMO_GUIDE.md'
  'docs/PHASE_64_SECURITY_REMEDIATION.md'
  'frontend/Dockerfile'
  'frontend/README.md'
  'frontend/package-lock.json'
  'frontend/package.json'
  'frontend/src/app/globe/page.test.ts'
  'frontend/src/app/globe/page.tsx'
  'frontend/src/components/DeveloperOnboardingPanel.tsx'
  'frontend/src/components/GlobeLabPanel.tsx'
  'frontend/src/components/PortfolioStressDetail.tsx'
  'frontend/src/test/frameworkCompatibility.test.ts'
  'scripts/check_environment.ps1'
  'scripts/print_browser_e2e_ci_summary.ps1'
)
# Re-review status/diff and this exact set immediately before staging.
git --literal-pathspecs add -- $paths
if ($LASTEXITCODE -ne 0) { throw 'Staging failed; do not reset or discard' }
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'Staged hygiene failed' }
git diff --cached --name-status
git status -sb
```

No staging/commit/push/tag/CI trigger/deployment/Phase 65 action is authorized
or performed here. Suggested later **user-created** subject remains
`Fix frontend dependency security blockers for phase64 release`.

### Replacement Three-Shell Handoff

These exact PowerShell blocks are for **later user execution**, not executed
by Codex. They use the verified available Node 24.20.0 path; for release prefer
the latest patched 24.x (currently 24.21.0), installed separately by the user,
then substitute its verified executable and repeat the relevant runtime checks.
Do not silently fall back to global 24.15.0 if the selected path is gone.
Keep all tokens/evidence private; failure traces may include the temporary
token in headers. Never paste that token into chat or commit it.

**Shell 1: verified Python, external disposable database, one worker.** The
actual repo venv resolves to the path below and Python 3.13.5; this does not
change CI's Python 3.11. Clipboard transfer avoids printing the token.

```powershell
& {
  $ErrorActionPreference = 'Stop'
  Set-Location C:\quantlab
  $python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
  $actual = & $python -c 'import sys; print(sys.executable)'
  if ($LASTEXITCODE -ne 0 -or $actual -ine $python) { throw 'Unexpected Python executable' }
  Write-Output $actual
  & $python --version
  if ($LASTEXITCODE -ne 0) { throw 'Python check failed' }
  if (Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq 8766) {
    throw 'Port 8766 is occupied; do not reuse or stop another service'
  }
  $env:E2E_STRATEGY_ENSEMBLE_TOKEN = & $python -c 'import secrets; print(secrets.token_hex(32))'
  if ($LASTEXITCODE -ne 0 -or $env:E2E_STRATEGY_ENSEMBLE_TOKEN -cnotmatch '^[0-9a-f]{64}$') {
    throw 'Token generation failed'
  }
  Set-Clipboard -Value $env:E2E_STRATEGY_ENSEMBLE_TOKEN
  Write-Output 'Temporary token is on the clipboard for shell 3; do not paste it into chat.'
  & $python -m uvicorn scripts.strategy_ensemble_e2e:create_app --factory --host 127.0.0.1 --port 8766 --workers 1
  if ($LASTEXITCODE -ne 0) { throw 'Disposable backend exited with an error' }
}
```

The factory installs its external DB override **before** importing `app.main`,
retains an ownership marker and revalidates storage on each lab request. No
`--reload`, normal backend, active DB or invented DB environment variable.

**Shell 2: inspect running processes, then build and start in one block.** Stop
here if any existing Next process might use this checkout's `.next` output;
inspect ambiguous processes manually, never kill or delete output to proceed.

```powershell
& {
  $ErrorActionPreference = 'Stop'
  Set-Location C:\quantlab\frontend
  $node = 'C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\6f12e0ef1c6e5061\bin\node.exe'
  $npm = 'C:\Users\jimli\AppData\Roaming\npm\node_modules\npm\bin\npm-cli.js'
  if (-not (Test-Path $node) -or -not (Test-Path $npm)) { throw 'Verified runtime is unavailable' }
  & $node -e 'const [major,minor]=process.versions.node.split(".").map(Number); console.log(process.execPath,process.version); if(major!==24||minor<20)process.exit(1)'
  if ($LASTEXITCODE -ne 0) { throw 'Use patched Node 24 LTS, minimum 24.20.0' }
  $npmVersion = & $node $npm --version
  if ($LASTEXITCODE -ne 0 -or $npmVersion -ne '11.17.0') { throw 'Review the changed npm version first' }
  Write-Output "npm $npmVersion"
  $servers = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction Stop | Where-Object {
    $_.CommandLine -match '(?i)([\\/]next[\\/]|next-server|\bnext(?:\.cmd)?\s+(dev|start)\b)'
  })
  if ($servers.Count) {
    $servers | Select-Object ProcessId, CommandLine
    throw 'Existing Next process: confirm no shared build output before proceeding'
  }
  if (Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq 3100) {
    throw 'Port 3100 is occupied; do not reuse or stop another service'
  }
  $env:BACKEND_URL = 'http://127.0.0.1:8766'
  $env:NEXT_TELEMETRY_DISABLED = '1'
  $oldPath = $env:PATH
  try {
    $env:PATH = "$(Split-Path $node);$oldPath"
    & $node $npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Build failed; never start a stale build' }
    & $node .\node_modules\next\dist\bin\next start --hostname 127.0.0.1 --port 3100
    if ($LASTEXITCODE -ne 0) { throw 'Production server exited with an error' }
  } finally { $env:PATH = $oldPath }
}
```

This runs the real `build` script, then the installed Next CLI without
`npm start`'s conflicting port 3000. BACKEND_URL is set before **both** operations.

**Shell 3: same token and actual frontend proxy; new external evidence.** Run
after both services are ready, keeping shell 1's token on the clipboard until
this shell imports it. A changed token/backend/proxy fails the built-in proof.

```powershell
& {
  $ErrorActionPreference = 'Stop'
  Set-Location C:\quantlab\frontend
  $node = 'C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\6f12e0ef1c6e5061\bin\node.exe'
  & $node -e 'const [major,minor]=process.versions.node.split(".").map(Number); console.log(process.execPath,process.version); if(major!==24||minor<20)process.exit(1)'
  if ($LASTEXITCODE -ne 0) { throw 'Unsupported or unavailable Node runtime' }
  $env:E2E_STRATEGY_ENSEMBLE_TOKEN = (Get-Clipboard -Raw).Trim()
  if ($env:E2E_STRATEGY_ENSEMBLE_TOKEN -cnotmatch '^[0-9a-f]{64}$') { throw 'Use shell 1 token, not a new token' }
  Set-Clipboard -Value ''
  $env:E2E_STRATEGY_ENSEMBLE_ISOLATED = '1'
  $env:E2E_BASE_URL = 'http://127.0.0.1:3100'
  $env:E2E_BROWSER_CHANNEL = 'msedge'
  $env:NEXT_TELEMETRY_DISABLED = '1'
  $evidence = Join-Path $env:TEMP ('quantlab-phase64-security-browser-' + [guid]::NewGuid().ToString('N'))
  & $node .\node_modules\@playwright\test\cli.js test e2e/strategy-ensemble.spec.ts --project=chromium --reporter=list --output $evidence
  if ($LASTEXITCODE -ne 0) { throw 'Targeted browser check failed; retain evidence and do not bypass isolation' }
  Write-Output "Targeted browser evidence: $evidence"
}
```

The `chromium` **project** plus `msedge` **channel** means installed Microsoft
Edge (Chromium engine), **not bundled Chromium**. The spec verifies
`/api/strategy-ensembles/e2e-isolation` through port 3100 before each test, with
the same token, redirect rejection and database identity validation. It executes
**21 targeted tests**, not all 275 discovered tests. List-only reporter plus a
unique OS-temp output keeps prior reports/frozen screenshots untouched.

### Bounded Broader Smoke, User Only

Inspected `frozen-demo.spec.ts`, `scenario-studio.spec.ts`, `pairs-ko-pep.spec.ts`
and their shared helpers before recommending them: four Home/sidebar/palette/
read-only Saved Reports tests, one deterministic Scenario Studio analysis and
one KO/PEP fixture backtest (six tests total). No saved-data mutation action or
other lab's isolation prerequisites are silently enabled by this subset.
The harness overrides the shared SQLite layer; these specs do **not** have their
own token preflight, so run the existing proof immediately before this subset:

```powershell
& {
  $ErrorActionPreference = 'Stop'
  Set-Location C:\quantlab\frontend
  $node = 'C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\6f12e0ef1c6e5061\bin\node.exe'
  # Keep shell 3's exact BASE_URL, channel and token; never target the ordinary backend.
  & $node --input-type=module -e @'
import { request } from '@playwright/test';
import { verifyStrategyEnsembleIsolation } from './e2e/strategyEnsembleIsolation.ts';
const api = await request.newContext();
try {
  await verifyStrategyEnsembleIsolation(process.env.E2E_BASE_URL,
    process.env.E2E_STRATEGY_ENSEMBLE_TOKEN, (url, options) => api.get(url, options));
} finally { await api.dispose(); }
'@
  if ($LASTEXITCODE -ne 0) { throw 'Actual frontend proxy did not prove isolation; stop' }
  $evidence = Join-Path $env:TEMP ('quantlab-phase64-framework-smoke-' + [guid]::NewGuid().ToString('N'))
  & $node .\node_modules\@playwright\test\cli.js test e2e/frozen-demo.spec.ts e2e/scenario-studio.spec.ts e2e/pairs-ko-pep.spec.ts --project=chromium --reporter=list --output $evidence
  if ($LASTEXITCODE -ne 0) { throw 'Broader smoke failed; retain evidence' }
  Write-Output "Broader smoke evidence: $evidence"
}
```

Additionally inspect the built app manually: local KaTeX formulas in Options
or another sample-only lab, readable charts/tooltips and no hydration errors,
1024/768 widths, `/globe?market=tw` redirect/selection and back/forward, and
Strategy Ensemble retry/error states. Avoid external provider actions. Frozen
checks retain Scenario severity 100.0 (8/8), KO/PEP dates 2016-07-11 to 2026-07-11,
119 trades, -23.0%/+112.7% and visible charts. Do not update frozen assertions to
make a failure pass. The existing helpers do not prove zero outbound network
traffic or detect every console/hydration issue; manually inspect those too.
No recommendation to blindly run all mutation-heavy specs.

### Decision and Remaining Gates

**Safe to keep:** yes, as the bounded uncommitted patch. **Ready for user-owned
build/browser verification:** yes, with the guarded runtime/isolation commands.
**Ready for a later user-created commit:** yes as a reviewed patch with the
remaining gates disclosed, not permission to commit here. **Release ready: no.**

Remaining gates: successful final production build, actual token-verified Edge
targeted plus bounded framework smoke (including manual formula/chart/hydration
checks), Docker pull/build/runtime verification, latest patched Node 24 runtime
confirmation and exact final-commit CI. CI's Node 24 application runtime and
Alpine image have not been executed by this review. Recheck Next 15's Maintenance
LTS window (two years from 2024-10-21) and current advisories before release.
Recharts 2 deprecation remains a maintenance risk, not authorization for a chart
rewrite. No complete security certification, deployment or Phase 65 claim.
