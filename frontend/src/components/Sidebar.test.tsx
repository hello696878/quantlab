/**
 * Sidebar component tests (Phase 63.0).
 *
 * Behaviour, not markup: the groups and entries the registry declares are the
 * ones the user can see and activate, the active workspace exposes an
 * accessible state, and navigation reports the exact view id.
 */

import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Sidebar, { NAV, NAV_GROUPS } from "@/components/Sidebar";
import { WORKSPACES, WORKSPACE_VISIBILITY } from "@/lib/workspaceRegistry";
import { renderWithUser } from "@/test/testUtils";

describe("Sidebar", () => {
  it("renders one accessible navigation landmark", () => {
    renderWithUser(<Sidebar active="home" onNav={vi.fn()} />);
    expect(screen.getByRole("navigation", { name: "Workspaces" })).toBeInTheDocument();
  });

  it("renders every registered group heading", () => {
    renderWithUser(<Sidebar active="home" onNav={vi.fn()} />);
    for (const group of NAV_GROUPS) {
      expect(
        screen.getByText(group.label),
        `missing sidebar group heading "${group.label}"`,
      ).toBeInTheDocument();
    }
  });

  it("renders every public workspace entry as a button with its label", () => {
    renderWithUser(<Sidebar active="home" onNav={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: "Workspaces" });
    for (const workspace of WORKSPACES.filter((w) => w.publicWorkspace)) {
      // Exact accessible-name match: several labels are substrings of others
      // ("Backtest" vs "CSV Backtest"), and a substring match would hide a
      // genuinely missing entry.
      expect(
        within(nav).getByRole("button", { name: workspace.label }),
        `missing sidebar button for "${workspace.label}"`,
      ).toBeInTheDocument();
    }
  });

  it("does not render an entry for an internal view", () => {
    renderWithUser(<Sidebar active="home" onNav={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: "Workspaces" });
    const internal = Object.entries(WORKSPACE_VISIBILITY)
      .filter(([, visibility]) => visibility === "internal")
      .map(([id]) => id);
    // Empty today; the assertion keeps the guarantee once a hidden view exists.
    for (const id of internal) {
      const entry = NAV.find((n) => n.id === id);
      if (!entry) continue;
      expect(within(nav).queryByRole("button", { name: entry.label })).toBeNull();
    }
    expect(within(nav).getAllByRole("button")).toHaveLength(
      WORKSPACES.filter((w) => w.publicWorkspace).length,
    );
  });

  it("marks the active workspace with aria-current and no other entry", () => {
    renderWithUser(<Sidebar active="signalensemble" onNav={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: "Workspaces" });
    const current = within(nav)
      .getAllByRole("button")
      .filter((button) => button.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent("Signal Ensemble Lab");
  });

  it("reports the exact view id when an entry is activated", async () => {
    const onNav = vi.fn();
    const { user } = renderWithUser(<Sidebar active="home" onNav={onNav} />);
    await user.click(screen.getByRole("button", { name: "Signal Decay Lab" }));
    expect(onNav).toHaveBeenCalledTimes(1);
    expect(onNav).toHaveBeenCalledWith("signaldecay");
  });

  it("keeps every entry keyboard reachable", async () => {
    const onNav = vi.fn();
    const { user } = renderWithUser(<Sidebar active="home" onNav={onNav} />);
    const target = screen.getByRole("button", { name: "Factor Diagnostics" });
    target.focus();
    expect(target).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onNav).toHaveBeenCalledWith("factordiagnostics");
  });

  it("renders group headings as decoration, not as focusable controls", () => {
    renderWithUser(<Sidebar active="home" onNav={vi.fn()} />);
    for (const group of NAV_GROUPS) {
      const heading = screen.getByText(group.label);
      expect(heading.getAttribute("aria-hidden")).toBe("true");
      expect(heading.tagName).not.toBe("BUTTON");
    }
  });
});
