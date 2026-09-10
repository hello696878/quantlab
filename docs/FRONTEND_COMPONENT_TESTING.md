# Frontend Component Testing (Phase 63.0, v1)

Phase 64 extends this foundation with `StrategyEnsemblePanel.test.tsx` and
`strategyEnsembleLink.test.ts`. They cover local API loading/empty/offline/retry,
demo/detail rendering, duplicate-action prevention, editable JSON, unmount
safety and permalink lifecycle. Production data is never replaced by these
test fixtures. Chart geometry remains browser-only, not certified by jsdom.
Current checks and unresolved gates: [PHASE_64_IMPLEMENTATION.md](PHASE_64_IMPLEMENTATION.md).

QuantLab's first frontend unit/component test layer. Companion document:
[`FRONTEND_REGISTRY_DRIFT_GUARDS.md`](FRONTEND_REGISTRY_DRIFT_GUARDS.md).

> These tests are a regression signal for shared components and navigation
> identity. They are **not** proof that the frontend is correct, not an
> accessibility certification, and not a replacement for the Playwright suite
> or the user-run production smoke pass.

## 1. The three testing layers

| Layer | Runner | Environment | Backend | What it protects |
|---|---|---|---|---|
| **Component / unit** (this document) | Vitest | jsdom, offline | none — network is blocked | shared components, navigation registries, pure utilities |
| **Browser E2E** (`frontend/e2e/`) | Playwright | real Chromium | backend + frontend running against isolated data | full workflows, responsive geometry, frozen demo path |
| **Manual production smoke** | human | production build | local services | the built app, real navigation, release evidence |

Component tests never replace the other two. A green unit run says the shared
pieces still behave; it says nothing about a workflow end to end.

## 2. Stack and why

| Choice | Version | Why |
|---|---|---|
| **Vitest** | `3.2.6` | TypeScript/JSX test transforms via Vite (separate from Next's build pipeline); patched test server dependencies. |
| **@vitest/coverage-v8** | `3.2.6` | Coverage provider, pinned to exactly the runner version. |
| **@vitejs/plugin-react** | `^4.7.0` | JSX/Fast-Refresh transform for the test build only. |
| **@testing-library/react** | `^16.3.2` | Behaviour-first queries; discourages implementation-detail assertions. |
| **@testing-library/dom** | `^10.4.1` | Explicit peer of RTL 16. |
| **@testing-library/jest-dom** | `^6.9.1` | Semantic matchers (`toBeVisible`, `toHaveFocus`, `toHaveAttribute`). |
| **@testing-library/user-event** | `^14.6.4` | Real event sequences (focus, typing, keyboard) rather than synthetic clicks. |
| **jsdom** | `^25.0.1` | DOM without a browser download. |

Version ranges are the ones recorded in `frontend/package.json`; the exact
resolved versions are in `frontend/package-lock.json`.

The reviewed lockfile uses Vite 7.3.6 and requires Node `^20.19.0 || >=22.12.0`
(local verification: Node 24.15.0; CI selects the latest Node 20).
The Phase 63-added Vitest/Vite advisories were patched. `npm audit` still
reports pre-existing application/build dependencies; see the Phase 63 review
report before making any security or release-readiness claim.

All eight are **devDependencies**. There is exactly one runner and one DOM
environment — no Jest, no happy-dom, no second browser automation framework
(Playwright remains the only one). Nothing is fetched from a CDN and no test
needs a running service.

Rejected on purpose: Jest (would need a Babel/SWC transform layer beside the
existing toolchain), snapshot-first testing (large snapshots assert nothing a
reader can check), and any automated accessibility scanner (a new dependency
this phase did not need in order to add the accessibility-oriented assertions
it does make).

## 3. Commands

```bash
cd C:\quantlab\frontend && npm run test:unit
```

```bash
cd C:\quantlab\frontend && npm run test:unit:watch
```

```bash
cd C:\quantlab\frontend && npm run test:unit:coverage
```

```bash
cd C:\quantlab\frontend && npm run test:frontend
```

* `test:unit` — one-shot; the CI-safe form. Exit code 0 means green.
* `test:unit:watch` — local interactive only; never used in CI.
* `test:unit:coverage` — v8 coverage (`@vitest/coverage-v8`). The configured
  reporter is `text-summary`, so the numbers are printed to the console and
  nothing is written to disk. If an on-disk reporter (`html`, `lcov`) is ever
  added it lands in `artifacts/frontend-coverage/`, which is gitignored.
  Coverage output is never committed.

  The measured figure today is low by construction — the include globs cover
  all of `src/lib/**` and `src/components/**` while only a small subset has
  tests, so most of the denominator is untested analytics panels. Treat it as
  a baseline to move, not a quality score.
* `test:frontend` — `test:unit` followed by `tsc --noEmit`.

None of these start a server, and none of them require the backend.

## 4. Layout and conventions

```
frontend/
  vitest.config.ts              runner config (jsdom, alias, includes)
  src/test/setup.ts             global setup: shims, network guard, matcher
  src/test/testUtils.tsx        render + user-event, clipboard/storage stubs
  src/test/sourceScan.ts        narrow, documented source scanners
  src/**/<Name>.test.tsx        component tests beside the component
  src/lib/<name>.test.ts        utility and registry tests beside the module
```

Tests live next to what they test. `vitest.config.ts` includes
`src/**/*.{test,spec}.{ts,tsx}` and explicitly excludes `e2e/**` so Playwright
specs are never executed by the wrong runner.

## 5. Setup and mocks

`src/test/setup.ts` installs, per test:

* **network guards** for fetch, XHR send, WebSocket, EventSource, sendBeacon
  when present, and Node HTTP/HTTPS request/get. Attempts throw and are
  recorded; teardown fails even if application code caught the first error.
  Guards are installed before test modules load and reinstalled per test.
  These prevent accidental standard HTTP calls, not hostile code executing
  arbitrary raw sockets or child processes; this is not a security sandbox;
* missing `matchMedia`, `ResizeObserver` and `scrollIntoView` shims;
  jsdom's actual requestAnimationFrame is retained;
* cleared storage, restored clipboard/storage/prototype descriptors, real
  timers, restored globals/spies, DOM cleanup and reset URL per test;
* `toBeFiniteNumericText()` — the repository's NaN/Infinity honesty rule as a
  matcher.

It deliberately does **not** silence React warnings or errors. A test-owned
console.error sentinel is intentionally printed by the isolation regression;
other stderr must be investigated. Logging alone is not automatically a test
failure, whereas thrown errors, unhandled rejections and blocked network
attempts fail. Async assertions use Testing Library/act without global muting.

`src/test/testUtils.tsx` provides `renderWithUser`, `stubClipboard`
(`ok` / `reject` / `absent`) and `stubUnavailableLocalStorage`.
Storage restoration is automatic in setup; numeric checks use the shared matcher.

**Clipboard ordering matters**: call `stubClipboard(...)` *after*
`renderWithUser(...)`, because `userEvent.setup()` installs its own clipboard
stub and would otherwise overwrite yours.

## 6. API mocking policy

* Component tests never call the live backend.
* Mock the **specific local client module** (`vi.mock("@/lib/api", …)`) and
  return deterministic, repository-owned data.
* Never mock HTTP globally as successful — the network guard exists precisely
  so a forgotten mock fails.
* Assert loading, success and error paths where the component has them.
* Do not copy large demo payloads into tests; the smallest deterministic
  fixture that exercises the branch is the right one.

## 7. Browser-API policy

Shims cover what jsdom lacks, nothing more. Tests that care about a failure
mode simulate it explicitly:

* `localStorage` unavailable (throwing accessor) and malformed stored values —
  `src/lib/settings.test.ts`;
* clipboard rejected and clipboard absent — `FormulaReference.test.tsx`;
* KaTeX renderer throwing — `SafeMath` falls back to raw LaTeX.

A shim must never hide a real error. If a component would crash in a browser
without an API, the test should show that, not paper over it.

## 8. What is covered today

| Area | File | Focus |
|---|---|---|
| Registry drift guards | `src/lib/workspaceRegistry.test.ts` | identity/mapping/sidebar/palette/cross-link contracts and adversarial mutation fixtures |
| Sidebar | `src/components/Sidebar.test.tsx` | groups, entries, `aria-current`, navigation ids, keyboard |
| Command palette | `src/components/CommandPalette.test.tsx` | label + alias search, keyboard flow, empty state, Escape |
| Dashboard | `src/components/HomeDashboard.test.tsx` | quick-action navigation targets, accessible names, no NaN |
| Formula reference / SafeMath | `src/components/math/FormulaReference.test.tsx` | rendering, invalid math, LaTeX copy + failure states, collapse |
| Shared state primitives | `src/components/ui/states.test.tsx` | empty/error/offline/loading roles and retry callbacks |
| Settings + storage safety | `src/lib/settings.test.ts` | defaults, malformed JSON, unavailable storage, sanitisation |
| Source scanner | `src/test/sourceScan.test.ts` | syntax, comments/prose, quotes, CRLF, invalid IDs, non-production paths |
| Setup isolation | `src/test/setupIsolation.test.tsx` | DOM, storage, clipboard, timers, console visibility and caught network attempts |
| Globe permalinks | `src/lib/globe/permalink.test.ts` | existing query/fallback/history helpers and SSR safety, not a general router |

Deliberately **not** covered in v1: the large analytics panels (their maths is
tested on the backend and their workflows in Playwright), chart rendering
internals, and anything requiring a real layout engine.

## 9. Test-quality rules

Tests must be deterministic and offline: no real network, no active database,
no wall-clock or random values unless frozen/seeded, no sleeps, no
test-order dependence. Mocks are restored automatically (`restoreMocks`,
`clearMocks`, `unstubGlobals` in `vitest.config.ts`) and `localStorage` is
cleared around every test.

Prefer semantic queries (`getByRole` with an accessible name, `getByLabelText`)
over class names or test ids. Use exact accessible-name matching where labels
share substrings ("Backtest" vs "CSV Backtest"). Avoid large snapshots. Reject
NaN/Infinity in numeric output.

## 10. Accessibility-oriented assertions

The suite asserts that the navigation landmark has an accessible name, that the
active workspace exposes `aria-current="page"`, that group headings are
decorative (`aria-hidden`) rather than focusable, that every rendered control
has an accessible name, that the palette is a labelled modal dialog with a
focused input, and that the keyboard flow (focus → Enter, ArrowDown → Enter,
Escape) works.

That is a floor, not a certification: **no WCAG conformance is claimed** and no
automated accessibility scanner runs.

## 11. CI behaviour

`.github/workflows/ci.yml`, job **Frontend Tests & Build**:

1. `npm ci` (lockfile install)
2. `npm run test:unit` ← added in Phase 63.0
3. `npx tsc --noEmit`
4. `npm run build`

One-shot, no watch mode, no browser download, no backend, no secrets, no new
permissions. Playwright continues to run only in the manually triggered
`browser-e2e.yml` workflow.

## 12. Known omissions

* No frontend visual-regression system (deliberate — pixel tests are excluded
  by repository policy; the five frozen screenshots remain release evidence,
  not assertions).
* No accessibility scanner, no performance/bundle budget.
* No component tests for the analytics panels or chart internals.
* The source scans use the TypeScript syntax tree, not runtime data-flow analysis — see
  [`FRONTEND_REGISTRY_DRIFT_GUARDS.md`](FRONTEND_REGISTRY_DRIFT_GUARDS.md) §5.
* Coverage is available but not enforced; no threshold is claimed.
* **No frontend/backend route-manifest guard (deliberately deferred).** A guard
  that compares the paths in `frontend/src/lib/api.ts` against a manifest of
  FastAPI routes was considered and not built. Clients also live in per-lab
  files, not only `api.ts`; TypeScript does not verify server path existence,
  and the browser suite does not exercise every route. This remains a real
  coverage gap, not evidence of complete API compatibility.

## 13. How Phase 64 should use this foundation

Phase 64 (strategy return-stream work) inherits three things:

1. **Add the workspace to the registry first.** A new `View` member fails
   `WORKSPACE_VISIBILITY` at compile time and the drift guards at run time
   until the sidebar entry, switcher branch, header metadata and palette
   command all exist.
2. **Write the lab's shared pieces test-first where they are reusable.** New
   shared primitives belong beside their component with a `.test.tsx`.
3. **Keep the layer boundary.** Component tests for shared behaviour;
   Playwright for the workflow; backend tests for the maths. Do not push
   numeric verification into jsdom.
