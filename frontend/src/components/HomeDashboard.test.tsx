/**
 * Dashboard navigation tests (Phase 63.0).
 *
 * The dashboard is the first screen and the widest set of cross-workspace
 * links in the product, so these tests assert that its cards actually open the
 * workspace they name. Stale targets are caught structurally by the registry
 * drift guards (`src/lib/workspaceRegistry.test.ts`); these tests cover the
 * click path itself.
 *
 * The dashboard loads saved backtests and reports on mount. That local API
 * client is mocked — the network guard in `src/test/setup.ts` fails any
 * unmocked request, so a missing mock cannot pass silently.
 */

import { act, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import HomeDashboard from "@/components/HomeDashboard";
import { ALL_VIEW_IDS } from "@/lib/workspaceRegistry";
import { renderWithUser } from "@/test/testUtils";

vi.mock("@/lib/api", () => ({
  listSavedBacktests: vi.fn(async () => []),
  listSavedReports: vi.fn(async () => []),
  checkHealth: vi.fn(async () => ({ status: "ok" })),
  classifyApiError: (error: unknown) => ({
    backendUnavailable: false,
    message: String(error),
  }),
}));

function renderDashboard() {
  const onNav = vi.fn();
  const result = renderWithUser(
    <HomeDashboard
      onNav={onNav}
      onOpenBacktest={vi.fn()}
      onOpenReport={vi.fn()}
      onDemo={vi.fn()}
    />,
  );
  return { ...result, onNav };
}

async function settle(): Promise<void> {
  // Flush the saved-work fetches so their state updates happen inside `act`.
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("HomeDashboard", () => {
  it("renders without reaching the network", async () => {
    renderDashboard();
    await settle();
    expect(screen.getByText(/Welcome to QuantLab/i)).toBeInTheDocument();
  });

  it("opens the Backtest workspace from the primary quick action", async () => {
    const { user, onNav } = renderDashboard();
    await settle();
    await user.click(screen.getByRole("button", { name: /Run Single-Asset Backtest/i }));
    await waitFor(() => expect(onNav).toHaveBeenCalled());
    expect(onNav.mock.calls.flat()).toContain("backtest");
  });

  it("opens Saved Reports from its quick action", async () => {
    const { user, onNav } = renderDashboard();
    await settle();
    await user.click(screen.getByRole("button", { name: /View Saved Reports/i }));
    expect(onNav).toHaveBeenCalledWith("reports");
  });

  it("only ever navigates to registered view ids", async () => {
    const { user, onNav } = renderDashboard();
    await settle();
    // Exercise a representative set of dashboard controls and assert that no
    // click produces a view id the router does not know.
    for (const name of [/Open Portfolio Lab/i, /Build Custom Strategy/i, /Open Settings/i]) {
      const button = screen.queryByRole("button", { name });
      if (button) await user.click(button);
    }
    const targets = onNav.mock.calls.map((call) => String(call[0]));
    expect(targets.length).toBeGreaterThan(0);
    const unknown = targets.filter((t) => !ALL_VIEW_IDS.map(String).includes(t));
    expect(unknown, `dashboard navigated to unknown views: ${unknown.join(", ")}`).toEqual(
      [],
    );
  });

  it("gives every rendered control an accessible name", async () => {
    renderDashboard();
    await settle();
    const unnamed = screen
      .getAllByRole("button")
      .filter((button) => (button.textContent ?? "").trim() === "" &&
        !button.getAttribute("aria-label"));
    expect(unnamed, "buttons without an accessible name").toHaveLength(0);
  });

  it("renders no NaN or Infinity in its summary tiles", async () => {
    const { container } = renderDashboard();
    await settle();
    expect(container.textContent ?? "").toBeFiniteNumericText();
  });
});
