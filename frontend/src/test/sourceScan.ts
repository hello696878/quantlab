/**
 * Narrow source scanners for the registry drift guards (Phase 63.0).
 *
 * Two pieces of navigation identity are NOT reachable as runtime values:
 *
 * 1. the `View` union in `src/components/AppShell.tsx` is a TypeScript type,
 *    so it is erased before any test can import it;
 * 2. the root workspace switcher in `src/app/page.tsx` is a flat chain of
 *    `{view === "x" && <Panel/>}` JSX expressions inside one 2.5k-line client
 *    component — importing it into jsdom would pull in every analytics panel,
 *    and converting all 57 branches into a component map would be exactly the
 *    broad navigation rewrite this phase is not allowed to do.
 *
 * For those two, and only those two, the guards read the source text.
 *
 * DOCUMENTED LIMITATIONS of this approach:
 *
 * * it matches literal patterns only — a view id built at runtime (template
 *   string, variable) is invisible to it;
 * * comments and prose are stripped before matching, so a mention of a view
 *   id in a sentence is never treated as a route;
 * * it is a drift tripwire, not a parser: if these files are ever restructured
 *   so the patterns no longer appear, the guards fail loudly (empty match set)
 *   rather than passing silently.
 *
 * Everything else (sidebar entries, palette commands, dashboard targets,
 * workspace registry) is asserted against real imported values, never text.
 */

import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
/** `frontend/src` — this file lives in `frontend/src/test`. */
const SRC_ROOT = resolve(HERE, "..");

export const APP_SHELL_PATH = resolve(SRC_ROOT, "components/AppShell.tsx");
export const PAGE_PATH = resolve(SRC_ROOT, "app/page.tsx");

function readSource(path: string): string {
  return readFileSync(path, "utf8");
}

/**
 * Remove `//` and block comments so prose can never be mistaken for a route.
 * Deliberately simple: it is applied to first-party source we control, and an
 * over-eager strip can only cause a guard to fail loudly, never to pass.
 */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
}

/**
 * The `View` union members, read from the type declaration in AppShell.
 *
 * Fails loudly (throws) when the declaration cannot be located, so a
 * restructure surfaces as a red test rather than an empty comparison.
 */
export function readViewUnionIds(): string[] {
  const source = readSource(APP_SHELL_PATH);
  const marker = "export type View =";
  const start = source.indexOf(marker);
  if (start < 0) {
    throw new Error(
      `Could not find "${marker}" in src/components/AppShell.tsx. The View ` +
        "union moved or changed shape — update src/test/sourceScan.ts and " +
        "docs/FRONTEND_REGISTRY_DRIFT_GUARDS.md together.",
    );
  }
  const end = source.indexOf(";", start);
  const body = stripComments(source.slice(start + marker.length, end));
  const ids = Array.from(body.matchAll(/"([a-z0-9-]+)"/g)).map((m) => m[1]);
  if (ids.length === 0) {
    throw new Error(
      "The View union declaration produced no members — the drift guard can " +
        "no longer read it. See src/test/sourceScan.ts.",
    );
  }
  return ids;
}

/**
 * The view ids the root switcher actually renders a branch for, read from the
 * `view === "x"` comparisons in `src/app/page.tsx`.
 */
export function readSwitcherViewIds(): string[] {
  const source = stripComments(readSource(PAGE_PATH));
  const ids = Array.from(source.matchAll(/view === "([a-z0-9-]+)"/g)).map((m) => m[1]);
  if (ids.length === 0) {
    throw new Error(
      'No `view === "…"` branches found in src/app/page.tsx. The workspace ' +
        "switcher was restructured — update src/test/sourceScan.ts and " +
        "docs/FRONTEND_REGISTRY_DRIFT_GUARDS.md together.",
    );
  }
  return Array.from(new Set(ids));
}

/**
 * The keys of the header `VIEW_META` map in `src/app/page.tsx`.
 *
 * `VIEW_META` is typed `Record<View, …>`, so TypeScript already guarantees
 * exhaustiveness; this scan is a belt-and-braces check that the runtime object
 * matches the union the guards compare everything else against.
 */
export function readViewMetaKeys(): string[] {
  const source = readSource(PAGE_PATH);
  const marker = "const VIEW_META";
  const start = source.indexOf(marker);
  if (start < 0) {
    throw new Error(
      "Could not find `const VIEW_META` in src/app/page.tsx — update " +
        "src/test/sourceScan.ts and the drift-guard documentation together.",
    );
  }
  const open = source.indexOf("{", start);
  const end = source.indexOf("\n};", open);
  const body = stripComments(source.slice(open, end));
  // Top-level keys are indented exactly two spaces inside the object literal.
  const keys = Array.from(body.matchAll(/^ {2}"?([a-z0-9-]+)"?:\s*\{/gm)).map((m) => m[1]);
  if (keys.length === 0) {
    throw new Error(
      "VIEW_META produced no keys — the header metadata map changed shape. " +
        "See src/test/sourceScan.ts.",
    );
  }
  return keys;
}

/**
 * Literal `handleNav("x")` targets in `src/app/page.tsx`.
 *
 * Panels receive `onNav` callbacks that cast plain strings to `View`
 * (`handleNav(route as View)`), so those cross-panel navigation targets are
 * not type-checked at the call site. Scanning the literals catches a stale id
 * that the compiler cannot.
 */
export function readHandleNavLiterals(): string[] {
  const source = stripComments(readSource(PAGE_PATH));
  const ids = Array.from(source.matchAll(/handleNav\("([a-z0-9-]+)"\)/g)).map((m) => m[1]);
  return Array.from(new Set(ids));
}

/**
 * Every literal `onNav("x")` navigation target across the component tree,
 * with the file that declares it.
 *
 * These are the cross-module links the dashboard and the diagnostics panels
 * use to send the user to another workspace. They are structured calls (never
 * prose), but the `onNav` prop is typed `(view: string) => void` in several
 * panels, so a stale id survives compilation — which is exactly what this
 * guard catches.
 *
 * Module identifiers that belong to other domains (Demo Center module ids,
 * Scenario Studio `ScenarioModuleId`s) are deliberately NOT scanned: they are
 * backend-owned identity, not workspace routes.
 */
export function readComponentNavTargets(): { file: string; view: string }[] {
  const dir = resolve(SRC_ROOT, "components");
  const found: { file: string; view: string }[] = [];
  const walk = (path: string): void => {
    for (const entry of readdirSync(path, { withFileTypes: true })) {
      const child = join(path, entry.name);
      if (entry.isDirectory()) {
        walk(child);
      } else if (entry.name.endsWith(".tsx") && !entry.name.includes(".test.")) {
        const source = stripComments(readFileSync(child, "utf8"));
        for (const match of Array.from(
          source.matchAll(/onNav\("([a-z0-9-]+)"\)/g),
        )) {
          found.push({ file: entry.name, view: match[1] });
        }
      }
    }
  };
  walk(dir);
  return found;
}
