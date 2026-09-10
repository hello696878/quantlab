# Frontend Registry Drift Guards (Phase 63.0, v1)

Phase 64 adds `strategyensemble` through the existing View/visibility/sidebar/
command/header/component mapping contract. No parallel router or registry.
Focused link tests cover initial deep links, browser-history destinations and
leaving via direct demo navigation; panel tests mock only the local API client.
See [implementation evidence](PHASE_64_IMPLEMENTATION.md).

Deterministic tests that fail when QuantLab's navigation surfaces stop
agreeing with each other. Companion document:
[`FRONTEND_COMPONENT_TESTING.md`](FRONTEND_COMPONENT_TESTING.md).

> These guards protect **identity**, not design: they check that every routed
> workspace exists everywhere it should and nowhere it should not. They make
> no claim that any workspace behaves correctly.

## 1. The problem they solve

A workspace's identity is spread across five hand-maintained places:

| # | Surface | File |
|---|---|---|
| 1 | the `View` union (the type of a route) | `frontend/src/components/AppShell.tsx` |
| 2 | sidebar entries (label, group, order, icon) | `frontend/src/components/Sidebar.tsx` |
| 3 | header metadata (`VIEW_META`) | `frontend/src/app/page.tsx` |
| 4 | the workspace switcher (`{view === "x" && <Panel/>}`) | `frontend/src/app/page.tsx` |
| 5 | command-palette navigation commands | `frontend/src/lib/workspaceRegistry.ts` |

TypeScript checks typed navigation targets, and `VIEW_META: Record<View, …>`
is exhaustive. It does not require exhaustive sidebar, JSX-switcher or palette
coverage: a new view can have a header but no page or navigation entry. Some
panels also cast strings (`handleNav(route as View)`), bypassing target checking.
The guards add completeness and cross-surface checks, not a new router.

## 2. The canonical registry

`frontend/src/lib/workspaceRegistry.ts` holds the minimum metadata needed to
verify the five surfaces — and no more:

| Export | What it is |
|---|---|
| `WORKSPACE_VISIBILITY` | `Record<View, "sidebar" \| "internal">` — an exhaustive classification. Adding a `View` member without classifying it is a **compile error**. |
| `INTERNAL_VIEW_REASONS` | `Partial<Record<View, string>>` — every `internal` view must state why it is hidden. Empty today. |
| `WORKSPACES` | one entry per sidebar item (`id`, `label`, `group`, `visibility`, `publicWorkspace`), **derived from `NAV_GROUPS`**, not an independent list of expected public IDs. |
| `WORKSPACE_BY_ID`, `WORKSPACE_GROUPS`, `ALL_VIEW_IDS` | lookups used by the guards and tests. |
| `WORKSPACE_COMMANDS` | the palette's navigation command data (`view`, `title`, `keywords`), moved verbatim out of the page component. |

**Deliberately not in the registry**: transient sub-views — portfolio tabs,
library/paper/disaster slugs, options tabs. They are state inside a workspace,
not routes, and including them would make the registry describe something the
router does not own.

`View` in AppShell remains the canonical identity type. The registry joins
metadata for verification; it does not implement routing or access control.
The public-ID expectation comes independently from `WORKSPACE_VISIBILITY`,
so deleting a sidebar item cannot also delete the test's expected value.
There are currently 58 identities, all public, and 59 navigation commands.
Counts are observations, not frozen assertions. Search keywords may overlap:
they are not URL aliases. Unique command titles protect the `nav-title` keys.

### What the Phase 63 refactor changed

Exactly two behaviour-preserving moves:

1. `NAV_COMMANDS` (58 entries) moved verbatim from inside `HomePage` to
   `WORKSPACE_COMMANDS` in the registry; `page.tsx` now aliases it. Same
   titles, same keywords, same order, same `run` closures.
2. `page.tsx` imports the registry.

No label, ordering, grouping, visibility or behaviour changed, and
`npx tsc --noEmit` stayed clean across the move.

## 3. What the guards check

`frontend/src/lib/workspaceRegistry.test.ts` checks the real source and
mutation fixtures for missing, stale, duplicated and internal targets:

**View identities** — no duplicate ids · no empty ids · ids match
`^[a-z][a-z0-9]*(-[a-z0-9]+)*$` · every union member classified in the
registry · only valid visibility values · every `internal` view has a stated
reason · no stale reason for a non-internal view.

**Component mapping** — every registered workspace has a `view === "…"` branch
in the switcher (otherwise it renders a header over an empty page) · no
switcher branch for an unregistered view · every workspace has header
metadata.

**Sidebar** — targets only registered views · lists every public workspace
exactly once · lists no internal view · order matches the registry
deterministically · non-empty labels and known group headings · no duplicate
group heading · no empty group · every entry resolves in `WORKSPACE_BY_ID`.

**Command palette** — commands target only registered views · every public
workspace is reachable from the palette · command titles are unique (they
become React keys) · keywords are non-empty and lowercase · a view may carry
more than one command (`sweep` does) but never a repeated title.

**Cross-module links** — every literal `handleNav("x")` in `page.tsx` targets
a registered view (these are the string casts the compiler cannot check) ·
every literal `onNav("x")` across all component files targets a registered view
· no cross-link exposes an `internal` view.

Demo Center module ids and Scenario Studio `ScenarioModuleId`s are **not**
scanned: they are backend-owned identity, not workspace routes, and parsing
them would be the brittle prose-matching this phase avoided.

## 4. Adding things safely

**A new workspace** — add the id to the `View` union; add
`WORKSPACE_VISIBILITY` (compile error until you do); add the sidebar entry
(`NAV_GROUPS`) with a label, icon and group; add the `VIEW_META` title and
subtitle; add the `{view === "id" && <Panel/>}` branch; add at least one
`WORKSPACE_COMMANDS` entry with a unique title and lowercase keywords. Run
`npm run test:unit` — the guards name whichever step is missing.

**A hidden/internal workspace** — set `WORKSPACE_VISIBILITY` to `"internal"`,
add a nonblank `INTERNAL_VIEW_REASONS` entry, and keep it out of the sidebar,
palette navigation commands and every public cross-link. This is a test
policy, not a runtime security boundary; no internal view exists today.

**A sidebar entry** — it must point at a registered, public view; the registry
derives from the sidebar, so re-ordering or relabelling is safe and the guards
follow.

**A dashboard card or panel cross-link** — use a literal
`onNav("registered-id")`. The cross-link guard scans those literals.

**A command-palette command** — add it to `WORKSPACE_COMMANDS` with a unique
title; the palette id is derived from the title, so duplicates would collide as
React keys.

**Deep links** — the app keeps view state in React (`useState<View>`), and the
only URL-parameter surface is the Globe permalink helper
(`frontend/src/lib/globe/permalink.ts`). It recognizes exactly `view=globe`
plus market/tour/presentation fields. Other values, including other valid
workspace IDs, do not select a workspace: initial load remains Home, and
the existing popstate handler returns Home for non-Globe URLs. The `/globe`
route redirects to the canonical query form. Helper tests cover this narrow
contract; browser back/forward and full page hydration still need browser
verification. No general or hidden-view URL resolver was introduced.

## 5. The source-scan limitation (read this before changing page.tsx)

Two of the five surfaces are not runtime values:

* the `View` union is a **type**, erased before any test can import it;
* the switcher is 58 `{view === "x" && …}` JSX expressions inside one
  2.5k-line client component — importing it into jsdom would pull in every
  analytics panel, and converting it to a component map would be the broad
  navigation rewrite this phase was not allowed to do.

The test-only scanner uses the existing TypeScript compiler API for the View
type, JSX switcher branches, VIEW_META keys, literal handleNav/onNav calls
(including optional calls), and reviewed frontend-owned route/view tables in
HomeDashboard, PortfolioShowcase, DeveloperOnboarding, ReleaseNotesCenter and
PublicReleaseCandidate. It never evaluates source. Comments and prose are AST
nodes, not matches; LF/CRLF, single/double quotes and indentation are covered.
Only comparisons that conditionally render JSX count as switcher branches,
so the Globe navigation side effect cannot hide a missing Globe panel.

Reads are anchored to frontend/src, realpaths must remain beneath that root,
symlink entries are not traversed, and test/spec/fixture/generated/hidden
directories are excluded. Missing reviewed files, malformed source and
unsupported required declaration shapes fail with actionable errors.

Limits: this is not data-flow analysis. Arbitrary runtime callbacks, renamed
navigation APIs, new data-table conventions, computed routes, backend-supplied
Demo Center links and transient Scenario/Research module IDs are not inferred.
Review new dynamic navigation explicitly and extend the narrow scanner/tests
when appropriate. Imported Sidebar/registry values remain the source of
labels/order, not a duplicate frozen list. Typecheck and browser checks still
matter; a JSX branch's presence does not prove its component renders correctly.

## 6. Common failure messages

| Message | Meaning | Fix |
|---|---|---|
| `WORKSPACE_VISIBILITY … must classify every member of the View union` | a view was added to the union only | classify it in the registry |
| `these views are registered but have no \`view === "…"\` branch` | header exists, page does not | add the switcher branch |
| `src/app/page.tsx renders these ids but they are not in the View union` | stale branch after a rename | delete or rename the branch |
| `these components navigate to view ids that no longer exist` | a stale `onNav("…")` cross-link | update the target |
| `public workspaces unreachable from the command palette` | missing palette command | add a `WORKSPACE_COMMANDS` entry |
| `command titles become palette ids … duplicates would collide` | two commands share a title | make the title unique |
| `Expected exactly one exported View type` | the union moved or changed shape | update `sourceScan.ts` **and** this document together |

## 7. What these guards do not do

They do not verify that a workspace renders correctly, that its analytics are
right, that navigation works in a real browser (Playwright's job), or that the
production build serves the route. They are an identity contract only.
