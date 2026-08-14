# Frontend Registry Drift Guards (Phase 63.0, v1)

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

TypeScript only links two of them: `VIEW_META` is `Record<View, …>`, so it is
exhaustive by construction. **Nothing** made the sidebar, the switcher or the
palette agree — a new view could ship with a header and no page, or a renamed
view could leave a dead palette command, and both compiled cleanly. Panels also
call `onNav` through string casts (`handleNav(route as View)`), which bypasses
the compiler entirely.

## 2. The canonical registry

`frontend/src/lib/workspaceRegistry.ts` holds the minimum metadata needed to
verify the five surfaces — and no more:

| Export | What it is |
|---|---|
| `WORKSPACE_VISIBILITY` | `Record<View, "sidebar" \| "internal">` — an exhaustive classification. Adding a `View` member without classifying it is a **compile error**. |
| `INTERNAL_VIEW_REASONS` | `Partial<Record<View, string>>` — every `internal` view must state why it is hidden. Empty today. |
| `WORKSPACES` | one entry per routed view (`id`, `label`, `group`, `visibility`, `publicWorkspace`), **derived from `NAV_GROUPS`** so labels/order/grouping stay owned by the sidebar. |
| `WORKSPACE_BY_ID`, `WORKSPACE_GROUPS`, `ALL_VIEW_IDS` | lookups used by the guards and tests. |
| `WORKSPACE_COMMANDS` | the palette's navigation command data (`view`, `title`, `keywords`), moved verbatim out of the page component. |

**Deliberately not in the registry**: transient sub-views — portfolio tabs,
library/paper/disaster slugs, options tabs. They are state inside a workspace,
not routes, and including them would make the registry describe something the
router does not own.

### What the Phase 63 refactor changed

Exactly two behaviour-preserving moves:

1. `NAV_COMMANDS` (58 entries) moved verbatim from inside `HomePage` to
   `WORKSPACE_COMMANDS` in the registry; `page.tsx` now aliases it. Same
   titles, same keywords, same order, same `run` closures.
2. `page.tsx` imports the registry.

No label, ordering, grouping, visibility or behaviour changed, and
`npx tsc --noEmit` stayed clean across the move.

## 3. What the guards check

`frontend/src/lib/workspaceRegistry.test.ts` — 26 assertions:

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
add an `INTERNAL_VIEW_REASONS` entry, and keep it out of the sidebar and out of
every `onNav(...)` cross-link.

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
(`frontend/src/lib/globe/permalink.ts`), which resolves market ids rather than
view ids. There is no view-level deep-link parser to guard today; if one is
added it must accept only registered ids and fall back to `home`, and this
document and the guards must be updated together.

## 5. The source-scan limitation (read this before changing page.tsx)

Two of the five surfaces are not runtime values:

* the `View` union is a **type**, erased before any test can import it;
* the switcher is 57 `{view === "x" && …}` JSX expressions inside one
  2.5k-line client component — importing it into jsdom would pull in every
  analytics panel, and converting it to a component map would be the broad
  navigation rewrite this phase was not allowed to do.

For those two only, `frontend/src/test/sourceScan.ts` reads the source text.
Its documented limits:

* it matches literal patterns only — an id built at runtime is invisible to it;
* comments and block comments are stripped first, so prose is never treated as
  a route;
* it is a tripwire, not a parser: if these files are restructured so the
  patterns disappear, the scanners **throw with a message naming the file to
  fix** rather than silently passing.

Everything else — sidebar, palette, registry, cross-links — is asserted against
real imported values.

## 6. Common failure messages

| Message | Meaning | Fix |
|---|---|---|
| `WORKSPACE_VISIBILITY … must classify every member of the View union` | a view was added to the union only | classify it in the registry |
| `these views are registered but have no \`view === "…"\` branch` | header exists, page does not | add the switcher branch |
| `src/app/page.tsx renders these ids but they are not in the View union` | stale branch after a rename | delete or rename the branch |
| `these components navigate to view ids that no longer exist` | a stale `onNav("…")` cross-link | update the target |
| `public workspaces unreachable from the command palette` | missing palette command | add a `WORKSPACE_COMMANDS` entry |
| `command titles become palette ids … duplicates would collide` | two commands share a title | make the title unique |
| `Could not find "export type View =" …` | the union moved or changed shape | update `sourceScan.ts` **and** this document together |

## 7. What these guards do not do

They do not verify that a workspace renders correctly, that its analytics are
right, that navigation works in a real browser (Playwright's job), or that the
production build serves the route. They are an identity contract only.
