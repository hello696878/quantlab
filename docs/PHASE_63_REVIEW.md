# Phase 63 Review: Frontend Component Tests and Registry Drift Guards

Review performed September 6-7, 2026 (Asia/Taipei), against implementation
`0d1c9030fcc5e8b80e0f37b8e9b110d73cd5a4fb`. Changes remain uncommitted.
No production build, frontend/backend service, browser session, CI workflow, publication or
Phase 64 implementation was started during this review.

## Findings First

| Severity | Finding | Resolution / reason it matters |
|---|---|---|
| P1 | The added Vitest 2.1.9/Vite 5.4.21 chain had critical/high npm advisories, including Vitest's exposed UI-server advisory GHSA-5xrq-8626-4rwp. | Patched Vitest and coverage to 3.2.6 and the resolved Vite to 7.3.6. The reviewed tools install and run. No server was exposed during review. |
| P1, pre-existing | npm audit still reports four high-severity package findings: browserslist, nanoid, Next.js and PostCSS; one low finding remains in postcss-selector-parser. | Not concealed or mass-upgraded. A production Next.js migration is outside this test-foundation pass; npm proposes a major upgrade for Next/PostCSS. These remain blockers under the request's no-unresolved-high readiness rule. |
| P2 | Sidebar completeness was checked against WORKSPACES, itself derived from Sidebar, so deleting a public Sidebar entry could satisfy both sides of the assertion. | Expected public IDs now come independently from exhaustive visibility metadata, with negative fixtures for missing/stale/internal targets. |
| P2 | Regex scanning accepted non-rendering view comparisons as component mappings and could miss alternate quotes, optional calls and data-table targets. | Replaced with test-only TypeScript AST checks and adversarial fixtures. A surviving Globe side effect cannot mask a removed Globe rendering branch. |
| P2 | A throwing fetch double could be caught by application error handling, allowing a missing mock to pass; other common HTTP paths were unguarded. | Record attempted fetch/XHR/socket-style browser/Node HTTP calls and assert the record is empty after each test, even if the application catches the thrown error. This is a guard, not an OS network sandbox. |
| P2 | Direct clipboard/storage/scroll property replacements and fake timers were not reliably restored by restoreMocks alone. | Explicit descriptor/global/timer/DOM/storage/URL cleanup plus shuffled, state-contamination regression cases. |
| P2 | The documented watch command inherited watch:false, so it was not a reliable watch workflow. | Removed the override and made test:unit:watch explicitly use --watch; CI still uses vitest run. |
| P2 | A conditional Dashboard assertion silently passed when a required button disappeared; keyboard checks did not prove exact destinations. | Required all nine primary quick actions and strengthened case-insensitive search, ArrowUp/Down, Enter, shortcut toggling and query-reset assertions. |
| P3 | The malformed KaTeX fixture contained an unintended doubled backslash; documentation overstated scanner coverage, had stale navigation locations and an invalid Windows path. | Use real malformed LaTeX with observable fallback assertions; corrected scope, paths, versions, pending gates, build/CI distinctions and historical counts. |

## Required Review Record

1. **Initial branch and worktree.** `main...origin/main`, clean tracked/untracked
   worktree at entry. Ignored active database, environment/build directories
   and existing browser evidence were already present. No stash/reset/clean.
2. **Implementation verification.** HEAD is the requested `0d1c903` commit,
   message `Add frontend component test foundation registry drift guards v1`.
   Parent is the confirmed Phase 62 review `ceb5c41792ec1148232e8a1a3d613c72ecb7e155`.
3. **Exact changed-file review.** All 32 implementation files were inspected;
   the inventory below separates runtime, test/config and documentation files.
   No backend file occurs in that implementation diff.
4. **Large diff.** Verified 6,688 insertions / 771 deletions. Lockfile accounts
   for 4,217 insertions / 676 deletions; page.tsx for 4 / 60. The remaining
   35 deleted lines are package/config/docs edits. The removed page array was
   relocated, not lost. JSON diff alignment around the large added package
   blocks explains apparent deleted/reinserted old lockfile entries.
5. **Dependencies.** Eight added devDependencies have specific uses: vitest
   (runner), jsdom (DOM), @testing-library/react (rendering), /dom (its peer),
   /jest-dom (matchers), /user-event (interaction), @vitejs/plugin-react (JSX),
   @vitest/coverage-v8 (the coverage script). No second runner, DOM environment
   or browser framework. Jest-named matcher/transitive utilities are not a
   second Jest runner. React 18/Next 14 application dependencies stay unchanged.
6. **Lockfile.** lockfileVersion remains 3. Package entries, including root:
   160 before, 410 in implementation, 424 after the security fix. All 160 old
   keys remain in implementation; 250 are added. Among common entries, only
   hasown changed version/resolved/integrity (2.0.3 to 2.0.4); root dev metadata
   is the only other changed entry. Thus no general old-package or integrity
   rewrite was found. The hasown bump is required by the added jsdom/form-data
   chain: form-data 4.0.6 requires ^2.0.4. Attempting to retain 2.0.3 fails npm ci,
   so that required bump was retained. Review changes stay within the test chain.
7. **npm ci.** Final clean installation passed: 364 packages installed, 365
   audited. Local Node 24.15.0/npm 11.17.0; the reviewed Vite requires
   `^20.19.0 || >=22.12.0`, compatible with latest Node 20 selected by CI.
   The initial sandbox EPERM required a permitted rerun with process access.
   Deprecated-package and npm install-script-policy notices were not suppressed;
   installation and subsequent workers succeeded. Audit findings are not green.
8. **Vitest config.** One setup module per test file/environment, jsdom,
   @ alias resolves frontend/src, explicit globals configuration, only
   src/**/*.{test,spec}.{ts,tsx}; e2e, node_modules and .next excluded.
   Coverage uses the installed V8 provider and ignored artifact directory,
   console summary only, no claimed threshold. Coverage itself was not run.
9. **Setup/global mocks.** Narrow missing-layout shims only. No global Next
   navigation/application-module success mocks and no console suppression.
   Browser descriptors, spies, stubbed globals, timers, storage, DOM and URL
   state are restored. Native jsdom RAF remains intact; no IntersectionObserver
   or layout-fidelity claim. Component-specific API doubles remain local.
10. **Source scan.** Uses the existing TypeScript compiler API, not evaluation.
    Parses the View union, explicit VIEW_META keys, JSX rendering branches,
    literal onNav/handleNav calls (including optional-call syntax) and five
    listed frontend navigation-data tables. Tests cover LF/CRLF, comments,
    prose, quotes, malformed source, duplicate/invalid literals and exclusions.
    Paths are deterministic, realpath-contained under frontend/src; symlink
    entries, test/fixture/generated/hidden directories are excluded. It is
    syntax checking, not complete route/dataflow verification.
11. **Registry architecture.** AppShell's View union remains the canonical
    identity type. WORKSPACE_VISIBILITY classifies it exhaustively; Sidebar
    still owns labels/order/groups; the registry joins these for verification.
    No runtime router or permission system was introduced. Keywords are search
    words, not aliases; shared keywords are legitimate and route-alias collision
    tests would invent a contract that does not exist.
12. **Completeness.** Independently enumerated 57 View IDs, 57 JSX mappings,
    57 header entries/public Sidebar entries, 11 groups and 58 navigation
    commands. Research Tools and Parameter Sweep intentionally share a target.
    Tests compare identities and policy, not a frozen count. No internal IDs
    currently exist; future internal entries require nonblank reasons.
13. **page.tsx preservation.** Compared pre/post command data structurally:
    all 58 ordered view/title/keyword tuples identical. Compared the page's AST
    after removing only the relocated declaration/import and normalizing line
    endings: identical. Default Home, Globe query effect/popstate behavior,
    lazy imports, render conditions, API payloads and side effects are preserved.
14. **Identity guards.** Duplicate, empty, malformed and mixed-case IDs fail;
    visibility is exhaustive and values validated. Label uniqueness and group
    validity are checked. Mutation fixtures show failures without editing live
    production files. No alias domain was added.
15. **Mapping guards.** Expected-vs-actual checks reject missing, duplicate and
    stale JSX/header IDs. Only actual JSX render conditions count; unrelated
    comparisons do not. A branch's presence still does not prove panel behavior
    or that its child is the intended component; browser/manual checks remain.
16. **Sidebar.** Real component tests check group/entry order, names, active
    aria-current, clicks and keyboard activation. Independent visibility checks
    now catch deleted entries and internal exposure. No hidden route exists in
    the real data; that policy is exercised with mutation fixtures.
17. **Dashboard.** Real component tests require all nine primary quick actions
    and exact callbacks. AST coverage includes card view fields, not merely
    direct calls. Repeated destinations across starting paths/cards are allowed;
    non-workspace demo/preset actions are not forced into the View domain.
18. **Command Palette.** Uses the actual WORKSPACE_COMMANDS construction,
    with API resource fetches mocked locally. Tests cover canonical labels,
    uppercase keyword search, focused/labelled dialog, ArrowDown/ArrowUp
    (existing clamp behavior), exact Enter target, query reset, Escape,
    Ctrl/Meta+K toggling and empty results. Navigation titles generate unique
    command IDs. Non-navigation actions and every saved-resource path are not
    comprehensively component-tested; their production code was unchanged.
19. **Deep links.** New tests exercise the real Globe permalink helpers:
    exact view=globe acceptance, other/unknown/case-mismatched/internal-fixture
    IDs rejected, market fallback, push/replace/clear and SSR guards. There is
    no generic workspace query router. Page inspection confirms non-Globe URLs
    start/fall back to Home; browser back/forward was not executed in this pass.
20. **Cross-module links.** Checks literal page handleNav and production
    component onNav calls plus HomeDashboard, PortfolioShowcase,
    DeveloperOnboarding, ReleaseNotesCenter and PublicReleaseCandidate data.
    DemoCenter's backend-provided route fields remain a declared gap. Scenario
    and Research Workspace module IDs and portfolio/model/paper subpanel states
    are not top-level View IDs. New naming/data conventions need explicit tests.
21. **FormulaReference/SafeMath.** Real KaTeX normal/malformed rendering,
    grouped formulas, explanation/collapse, source-copy, rejected/absent
    clipboard paths and a narrowly mocked throwing-renderer fallback covered.
    The throwing spy is restored even on assertion failure; no global KaTeX mock.
22. **Shared states.** Loading semantics, skeleton structure, empty/action
    states, error alert/detail and offline/retry behavior covered by ten tests.
    Placeholders contain no invented records or performance results.
23. **Settings.** Defaults, malformed/wrong-shape storage, unsupported values,
    non-finite sanitization, unavailable storage access and valid nondefault
    roundtrip covered. Zero transaction cost survives. SSR import without window
    is tested, with targeted module reset. Settings production logic unchanged.
24. **Browser API isolation.** Three shuffle-safe contamination cases verify
    clean storage/DOM/clipboard/scroll/timer state, then deliberately dirty it
    for cleanup. URL restoration is exercised by permalink tests. Unused
    redundant restoration/numeric helper functions were removed.
25. **Accessibility assertions.** Role/name queries, focus, keyboard actions,
    aria-current and status/alert semantics are meaningful component assertions.
    No automated accessibility certification, contrast or layout proof claimed.
26. **Type safety.** Tests are included in the existing `**/*.ts` / `**/*.tsx` typecheck.
    View callbacks remain typed; no production any escape was introduced.
    Removed unsafe clipboard/storage casts. Record<string,...> in test helpers
    intentionally accepts invalid mutation fixtures. The Vitest Assertion<T=any>
    declaration merge mirrors Vitest's generic signature, not a runtime escape.
27. **CI.** One npm ci, then one-shot unit tests, tsc and the existing build;
    failures propagate normally. Node 20, npm lockfile cache, read-only
    permissions unchanged. No new secrets, env expansion, services or browser
    download. Main-targeted push/PR workflow only; E2E remains manual. No run
    was triggered and no current-commit green CI claim is made.
28. **Scripts.** test:unit=vitest run; test:unit:watch=vitest --watch;
    test:unit:coverage=vitest run --coverage; test:frontend=vitest run &&
    tsc --noEmit. No passWithNoTests, hidden build, backend dependency or cycle.
    The interactive watch session was not left running.
29. **Network isolation.** Unexpected guarded calls throw and remain recorded
    after application catches; local API mocks do not globally return HTTP 200.
    No unit request reached a provider, backend or active database. Direct raw
    sockets or a new networking library are not sandboxed; future tests must
    extend the guard or use an OS network policy rather than claim impossibility.
30. **React warnings/errors.** No act, hydration, duplicate-key, unsupported-API
    or unhandled-rejection warning in final runs. Exactly one intentional,
    forwarded console.error sentinel proves stderr was not muted. Logging alone
    is visible, not automatically fatal; thrown/unhandled errors fail tests.
31. **Determinism.** Two final normal runs and seeded shuffle all have identical
    10-file/128-test passing results. No skipped or weakened tests. Runtime varies
    with the concurrent backend load and is not treated as an invariant.
32. **Unit run #1.** PASS, 128 tests / 10 files, exit 0; September 7 00:03:43
    local, Vitest duration 14.23s (under backend load).
33. **Unit run #2.** PASS, 128 tests / 10 files, exit 0; September 7 00:04:34,
    5.18s. Shuffle seed 6301 at 00:06:24 also PASS, same counts, 5.14s.
34. **Typecheck.** `npx tsc --noEmit` PASS, exit 0, rerun after final code edits.
35. **Playwright discovery.** PASS: 18 spec files, 254 Chromium tests, unchanged
    from Phase 62. Used --reporter=list in addition to the requested --list
    --project=chromium so discovery did not overwrite existing HTML evidence.
36. **Full Playwright.** Not run: no verified isolated services/test database
    were available and starting services was forbidden. Existing user data
    is not a valid target for seeding E2E. No browser installed/launched.
37. **Backend suite.** Full requested command with the root .venv Python:
    **4,268 passed, 3 skipped, 4 failed**, exit 1, 2352.72s (39m12s).
    PYTHONIOENCODING was unset. The initial sandbox attempt was interrupted
    after Windows temporary-directory permission errors; the authorized rerun
    completed with only the four known failures below. The full suite is NOT
    green. No backend tests or production code were changed or weakened.
    The three existing skips concern unavailable Windows symlink permissions;
    no skip or xfail was added by this review.
38. **Known environment failures.** The four named experiment_review tests
    pass unchanged in a clean temporary git export of the same HEAD:
    4 passed / 276 deselected, exit 0, 3.97s. Active database/evidence were not
    copied, moved or deleted. Temporary export/archive were removed afterward.
    In the full active-workspace run, test_collect_creates_no_repo_artifacts_or_db
    (line 1458), test_all_renderers_return_str_and_touch_no_repo_artifacts
    (2068), and test_cli_creates_no_database_or_repo_artifacts (2810) fail on
    the pre-existing backend/data/quantlab.db. The fourth,
    test_e2e_experiment_evidence_pack_over_real_and_tampered_runs (3117), fails
    on the pre-existing artifacts directory. Existing August 14 Playwright
    evidence was deliberately preserved instead of broadly deleted; that is a
    documented deviation from the supplied pre-clean command. No other full-run
    failures occurred. The clean-export result classifies these as environment
    preconditions without weakening assertions or touching user records.
39. **Product preservation.** No backend, finance engine, provider, API/schema,
    request payload, result, label, order, visibility, default view or runtime
    navigation changes. Review's only production-source edit is a registry
    comment clarifying Sidebar-derived metadata and search keywords.
40. **Documentation.** Audited governing instructions, README/changelog,
    blueprint/status/reconciliation, roadmap, handoff, version, CI/runbooks and
    frontend testing docs. Corrected stale source-scan/coverage claims, paths,
    Node requirements, watch usage, navigation locations, pending review status
    and distinction between runner builds and user smoke. Historical evidence
    remains historical, not evidence for this commit.
41. **VERSION/roadmap.** VERSION remains 4.81.0-dev. Exact future tag is
    v4.81.0-frontend-component-test-foundation-registry-drift-guards-v1; it does
    not exist. Corrected the forward roadmap's alternate spelling. Phase 64
    remains Strategy Return Stream, Strategy Similarity and Portfolio Ensemble
    Diagnostics Lab v1; nothing from that phase implemented.
42. **Security scan.** Repository-standard secret-pattern scan plus scoped
    test/config execution/path scan performed. Matches were documented names,
    domain words (tokenomics) or syntax tokens, not credentials. No new secret,
    absolute user path or shell/eval/dynamic-execution path in test helpers.
    Compiler parsing never executes scanned source. This is not a security audit
    certification; npm's remaining package advisories are explicit blockers.
43. **Overclaim scan.** Removed claims that source checks cover only two files,
    all API clients live in api.ts, all workspace rendering is proven, E2E
    writes nothing persistent, and no tooling builds. No claim that tests,
    accessibility, full browser coverage or future release approval are complete.
44. **Hygiene.** git diff --check passed after removing a new EOF blank line.
    Nothing staged. Changed-path artifact scan found no DB/env/log/cache/report
    output. Ignored node_modules/.next/tsbuildinfo/venvs/cache and prior evidence
    remain local. No broad cleanup of unrelated ignored files.
45. **Frozen evidence.** No diff under docs/screenshots or frozen Scenario
    Studio/KO-PEP fixtures/specs; no evidence recapture or baseline update.
46. **Active database.** No action targeted the active DB. Its size and UTC
    modification time remained 8,015,872 bytes / 2026-08-03T15:27:57.9732459Z
    through the observed run. No pre-review hash was captured, so this is
    metadata verification plus action/test isolation, not a claimed hash proof.
47. **Defects/severity.** See the findings table: added critical/high toolchain
    advisories, six P2 test/config weaknesses, and P3 fixture/documentation
    issues. Pre-existing high application/build advisories remain unresolved.
48. **Fixes.** Patched only test-tool dependencies; independent identity oracles;
    AST and mutation guards; browser/network isolation; real interaction and
    permalink/storage tests; watch fix; honest documentation. No new features.
49. **Files changed during review.** Exact inventory below. Backend, E2E specs,
    application panels, page.tsx, VERSION and workflow behavior unchanged.
50. **Limitations.** No production build, coverage run, full browser suite,
    actual Node 20 execution or new-commit CI evidence. No complete dynamic
    cross-link/dataflow, page mounting/history, analytics-panel, responsive,
    visual or accessibility coverage. Model/paper catalog references and
    standalone formatters from the earlier outline remain explicitly deferred.
51. **Safe to keep.** The scoped testing fixes are useful and suitable to retain
    for local development. The strict all-gates/no-security-issue decision is
    NOT an unconditional pass while the four pre-existing high findings remain.
52. **Ready for manual verification.** YES for trusted local verification with
    isolated services/data and a user-run production build/smoke. Not approval
    to expose this dependency stack publicly.
53. **Ready for review commit.** FALSE under the requested no-unresolved-high
    rule until the remaining dependency issues are resolved/reviewed and the
    required checks rerun. Do not interpret passing component tests as approval.
54. **Ready for v4.81 tag.** FALSE. Requires the review commit, relevant green CI,
    user production build, production browser smoke and final hygiene checks.
    No commit/push/tag/release/deployment was executed here.
55. **Exact user commit/push commands.** Provided at the end for AFTER blockers
    and final verification are resolved. They stage explicit review paths only;
    inspect any additional security-fix paths separately before committing.

## Implementation File Inventory (32)

| Area | Files inspected |
|---|---|
| Runtime | frontend/src/app/page.tsx; frontend/src/lib/workspaceRegistry.ts |
| Runner/CI/dependencies | .github/workflows/ci.yml; frontend/package.json; frontend/package-lock.json; frontend/vitest.config.ts |
| Test helpers | frontend/src/test/setup.ts; frontend/src/test/sourceScan.ts; frontend/src/test/testUtils.tsx |
| Tests | frontend/src/components/Sidebar.test.tsx; CommandPalette.test.tsx; HomeDashboard.test.tsx; math/FormulaReference.test.tsx; ui/states.test.tsx; frontend/src/lib/settings.test.ts; workspaceRegistry.test.ts |
| Root documentation/version | README.md; CHANGELOG.md; VERSION |
| Frontend documentation | frontend/README.md |
| docs/ | BROWSER_E2E_RUNBOOK.md; CI.md; CI_BROWSER_E2E.md; COMMAND_REFERENCE.md; DEVELOPER_ONBOARDING.md; FORWARD_ROADMAP_PHASES_63_70.md; FRONTEND_COMPONENT_TESTING.md; FRONTEND_REGISTRY_DRIFT_GUARDS.md; PROJECT_SNAPSHOT.md; ROADMAP.md; TROUBLESHOOTING.md; VERSION_MANIFEST.md |

## Review File Inventory and Gated User Commands

The array is also the complete inventory of this review's edits (34 files).
The sole application-source change is the comment in workspaceRegistry.ts.
Everything else is tests, their dependencies/config or documentation.

**Do not run the commit/push portion until item 53's blockers are resolved.**
These are instructions for the user, not commands executed by this review.
An eventual user push will trigger the existing main CI workflow.

```powershell
cd C:\quantlab
$reviewFiles = @(
  'CHANGELOG.md'
  'README.md'
  'STOP_POINT.md'
  'TASKS.md'
  'docs/BROWSER_E2E_RUNBOOK.md'
  'docs/CI.md'
  'docs/CI_BROWSER_E2E.md'
  'docs/DEVELOPER_ONBOARDING.md'
  'docs/FORWARD_ROADMAP_PHASES_63_70.md'
  'docs/FRONTEND_COMPONENT_TESTING.md'
  'docs/FRONTEND_REGISTRY_DRIFT_GUARDS.md'
  'docs/PHASE_63_REVIEW.md'
  'docs/PROJECT_SNAPSHOT.md'
  'docs/ROADMAP.md'
  'docs/TROUBLESHOOTING.md'
  'docs/VERSION_MANIFEST.md'
  'frontend/README.md'
  'frontend/package-lock.json'
  'frontend/package.json'
  'frontend/vitest.config.ts'
  'frontend/src/components/CommandPalette.test.tsx'
  'frontend/src/components/HomeDashboard.test.tsx'
  'frontend/src/components/math/FormulaReference.test.tsx'
  'frontend/src/lib/settings.test.ts'
  'frontend/src/lib/workspaceRegistry.test.ts'
  'frontend/src/lib/workspaceRegistry.ts'
  'frontend/src/lib/globe/permalink.test.ts'
  'frontend/src/test/setup.ts'
  'frontend/src/test/sourceScan.ts'
  'frontend/src/test/testUtils.tsx'
  'frontend/src/test/networkGuard.ts'
  'frontend/src/test/registryAssertions.ts'
  'frontend/src/test/setupIsolation.test.tsx'
  'frontend/src/test/sourceScan.test.ts'
)
git status -sb
git diff --check
git add -- $reviewFiles
git diff --cached --check
git diff --cached --stat
git diff --cached
# Stop and inspect the staged changes and required verification evidence.
git commit -m 'Review frontend component test foundation registry drift guards v1'
git push origin main
```

Frontend build was not run in Codex by instruction. Please run it locally.
