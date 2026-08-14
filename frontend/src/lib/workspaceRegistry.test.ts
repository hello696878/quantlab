/**
 * Registry drift guards (Phase 63.0).
 *
 * These tests fail when the navigation surfaces stop agreeing with each other:
 * the `View` union, the sidebar, the workspace registry, the command palette
 * data, the root switcher, the header metadata and the dashboard's navigation
 * targets. They assert against imported runtime values wherever possible and
 * fall back to the narrow, documented source scans in `src/test/sourceScan.ts`
 * only for the two pieces that are not runtime values.
 *
 * They are contracts about identity, not about product design: adding a
 * workspace is expected to touch several of them at once, and the failure
 * messages name the file to update.
 */

import { describe, expect, it } from "vitest";
import { NAV, NAV_GROUPS } from "@/components/Sidebar";
import {
  ALL_VIEW_IDS,
  INTERNAL_VIEW_REASONS,
  WORKSPACES,
  WORKSPACE_BY_ID,
  WORKSPACE_COMMANDS,
  WORKSPACE_GROUPS,
  WORKSPACE_VISIBILITY,
} from "@/lib/workspaceRegistry";
import {
  readComponentNavTargets,
  readHandleNavLiterals,
  readSwitcherViewIds,
  readViewMetaKeys,
  readViewUnionIds,
} from "@/test/sourceScan";

const VIEW_ID_PATTERN = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;

const viewUnionIds = readViewUnionIds();
const switcherIds = readSwitcherViewIds();
const registryIds = ALL_VIEW_IDS.map(String);

function sorted(values: readonly string[]): string[] {
  return values.slice().sort();
}

// ---------------------------------------------------------------------------
// View identities
// ---------------------------------------------------------------------------

describe("view identities", () => {
  it("declares no duplicate view ids", () => {
    expect(sorted(viewUnionIds)).toEqual(sorted(Array.from(new Set(viewUnionIds))));
  });

  it("uses the documented id format (lowercase, hyphen-separated)", () => {
    const bad = viewUnionIds.filter((id) => !VIEW_ID_PATTERN.test(id));
    expect(
      bad,
      `view ids must be lowercase alphanumeric with single hyphens: ${bad.join(", ")}`,
    ).toEqual([]);
  });

  it("declares no empty ids", () => {
    expect(viewUnionIds.filter((id) => id.trim() === "")).toEqual([]);
  });

  it("classifies every view in the workspace registry", () => {
    expect(
      sorted(registryIds),
      "WORKSPACE_VISIBILITY in src/lib/workspaceRegistry.ts must classify every " +
        "member of the View union in src/components/AppShell.tsx",
    ).toEqual(sorted(viewUnionIds));
  });

  it("uses only valid visibility values", () => {
    const invalid = Object.entries(WORKSPACE_VISIBILITY).filter(
      ([, visibility]) => visibility !== "sidebar" && visibility !== "internal",
    );
    expect(invalid).toEqual([]);
  });

  it("requires a stated reason for every internal (non-sidebar) view", () => {
    const internal = Object.entries(WORKSPACE_VISIBILITY)
      .filter(([, visibility]) => visibility === "internal")
      .map(([id]) => id);
    const undocumented = internal.filter(
      (id) => !(INTERNAL_VIEW_REASONS as Record<string, string | undefined>)[id],
    );
    expect(
      undocumented,
      "every internal view needs an explicit reason in INTERNAL_VIEW_REASONS",
    ).toEqual([]);
  });

  it("does not document a reason for a view that is not internal", () => {
    const stale = Object.keys(INTERNAL_VIEW_REASONS).filter(
      (id) => WORKSPACE_VISIBILITY[id as keyof typeof WORKSPACE_VISIBILITY] !== "internal",
    );
    expect(stale, "stale INTERNAL_VIEW_REASONS entries").toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Component mapping (root workspace switcher)
// ---------------------------------------------------------------------------

describe("component mapping", () => {
  it("renders a branch for every routed workspace", () => {
    const missing = registryIds.filter((id) => !switcherIds.includes(id));
    expect(
      missing,
      "these views are registered but have no `view === \"…\"` branch in " +
        "src/app/page.tsx, so they would render an empty page: " +
        missing.join(", "),
    ).toEqual([]);
  });

  it("has no switcher branch for an unregistered view", () => {
    const stale = switcherIds.filter((id) => !registryIds.includes(id));
    expect(
      stale,
      "src/app/page.tsx renders these ids but they are not in the View union: " +
        stale.join(", "),
    ).toEqual([]);
  });

  it("gives every routed workspace header metadata", () => {
    const metaKeys = readViewMetaKeys();
    expect(sorted(metaKeys)).toEqual(sorted(registryIds));
  });
});

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

describe("sidebar", () => {
  it("targets only registered views", () => {
    const unknown = NAV.map((n) => String(n.id)).filter(
      (id) => !registryIds.includes(id),
    );
    expect(unknown, "sidebar entries pointing at unknown views").toEqual([]);
  });

  it("lists every public workspace exactly once", () => {
    const sidebarIds = NAV.map((n) => String(n.id));
    const publicIds = WORKSPACES.filter((w) => w.publicWorkspace).map((w) =>
      String(w.id),
    );
    expect(sorted(sidebarIds)).toEqual(sorted(publicIds));
    expect(
      sidebarIds.length,
      "a duplicated sidebar entry renders the same workspace twice",
    ).toBe(new Set(sidebarIds).size);
  });

  it("does not list internal views", () => {
    const internal = Object.entries(WORKSPACE_VISIBILITY)
      .filter(([, v]) => v === "internal")
      .map(([id]) => id);
    const leaked = NAV.map((n) => String(n.id)).filter((id) => internal.includes(id));
    expect(leaked, "internal views must not appear in the sidebar").toEqual([]);
  });

  it("keeps a deterministic order that the registry mirrors", () => {
    expect(WORKSPACES.map((w) => String(w.id))).toEqual(NAV.map((n) => String(n.id)));
  });

  it("uses non-empty labels and known group headings", () => {
    for (const entry of WORKSPACES) {
      expect(entry.label.trim(), `empty label for ${entry.id}`).not.toBe("");
      expect(
        WORKSPACE_GROUPS,
        `unknown group "${entry.group}" for ${entry.id}`,
      ).toContain(entry.group);
    }
  });

  it("declares no duplicate group headings", () => {
    expect(sorted(WORKSPACE_GROUPS)).toEqual(sorted(Array.from(new Set(WORKSPACE_GROUPS))));
  });

  it("has no empty sidebar group", () => {
    const empty = NAV_GROUPS.filter((g) => g.items.length === 0).map((g) => g.label);
    expect(empty).toEqual([]);
  });

  it("gives every sidebar entry a lookup in the registry", () => {
    for (const item of NAV) {
      expect(
        WORKSPACE_BY_ID[item.id],
        `WORKSPACE_BY_ID is missing ${String(item.id)}`,
      ).toBeDefined();
    }
  });
});

// ---------------------------------------------------------------------------
// Command palette data
// ---------------------------------------------------------------------------

describe("command palette registry", () => {
  it("targets only registered views", () => {
    const unknown = WORKSPACE_COMMANDS.map((c) => String(c.view)).filter(
      (id) => !registryIds.includes(id),
    );
    expect(
      unknown,
      "palette commands pointing at removed views: " + unknown.join(", "),
    ).toEqual([]);
  });

  it("reaches every public workspace", () => {
    const covered = new Set(WORKSPACE_COMMANDS.map((c) => String(c.view)));
    const missing = WORKSPACES.filter((w) => w.publicWorkspace)
      .map((w) => String(w.id))
      .filter((id) => !covered.has(id));
    expect(
      missing,
      "public workspaces unreachable from the command palette: " + missing.join(", "),
    ).toEqual([]);
  });

  it("declares unique command titles", () => {
    const titles = WORKSPACE_COMMANDS.map((c) => c.title);
    const duplicates = titles.filter((t, i) => titles.indexOf(t) !== i);
    expect(
      duplicates,
      "command titles become palette ids (`nav-${title}`), so duplicates would " +
        "collide as React keys: " + duplicates.join(", "),
    ).toEqual([]);
  });

  it("declares deterministic, non-empty keyword aliases", () => {
    for (const command of WORKSPACE_COMMANDS) {
      expect(command.keywords.trim(), `empty keywords for ${command.title}`).not.toBe(
        "",
      );
      expect(
        command.keywords,
        `keywords for ${command.title} must be lowercase for predictable search`,
      ).toBe(command.keywords.toLowerCase());
    }
  });

  it("only repeats a view when the alternate entry is a distinct command", () => {
    const byView = new Map<string, string[]>();
    for (const command of WORKSPACE_COMMANDS) {
      const key = String(command.view);
      byView.set(key, [...(byView.get(key) ?? []), command.title]);
    }
    for (const [view, titles] of Array.from(byView.entries())) {
      expect(
        new Set(titles).size,
        `view ${view} has repeated command titles`,
      ).toBe(titles.length);
    }
  });
});

// ---------------------------------------------------------------------------
// Cross-module navigation targets
// ---------------------------------------------------------------------------

describe("cross-module navigation targets", () => {
  it("only navigates to registered views from literal handleNav calls", () => {
    const targets = readHandleNavLiterals();
    expect(targets.length, "no literal handleNav targets found to check").toBeGreaterThan(
      0,
    );
    const unknown = targets.filter((id) => !registryIds.includes(id));
    expect(
      unknown,
      "src/app/page.tsx navigates to unknown views (these are string casts the " +
        "compiler cannot check): " + unknown.join(", "),
    ).toEqual([]);
  });

  it("only links to registered views from dashboard and panel cross-links", () => {
    const targets = readComponentNavTargets();
    expect(
      targets.length,
      "no component onNav targets found — the scan pattern may be stale",
    ).toBeGreaterThan(0);
    const stale = targets.filter((t) => !registryIds.includes(t.view));
    expect(
      stale.map((t) => `${t.file} → ${t.view}`),
      "these components navigate to view ids that no longer exist",
    ).toEqual([]);
  });

  it("never exposes an internal view through a cross-link", () => {
    const internal = Object.entries(WORKSPACE_VISIBILITY)
      .filter(([, v]) => v === "internal")
      .map(([id]) => id);
    const leaked = readComponentNavTargets().filter((t) => internal.includes(t.view));
    expect(
      leaked.map((t) => `${t.file} → ${t.view}`),
      "internal views must not be reachable from a public card or button",
    ).toEqual([]);
  });
});
