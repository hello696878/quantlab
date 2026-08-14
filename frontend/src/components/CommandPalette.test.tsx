/**
 * Command palette component tests (Phase 63.0).
 *
 * The palette is the keyboard route into every workspace, so these tests cover
 * the flows a broken search would silently take away: finding a workspace by
 * its canonical label, finding it by a keyword alias that is never displayed,
 * running it with the keyboard, and telling the user honestly when nothing
 * matched.
 *
 * The palette fetches saved backtests/reports/templates when it opens. That
 * local API client is mocked here — the global network guard in
 * `src/test/setup.ts` fails any unmocked request, so a missing mock can never
 * pass silently.
 */

import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CommandPalette, {
  openCommandPalette,
  type Command,
} from "@/components/CommandPalette";
import { WORKSPACE_COMMANDS } from "@/lib/workspaceRegistry";
import { renderWithUser } from "@/test/testUtils";

vi.mock("@/lib/api", () => ({
  // Deterministic empty resource lists: the palette's saved-resource section is
  // not what these tests are about, and empty keeps the result list to commands.
  listSavedBacktests: vi.fn(async () => []),
  listSavedReports: vi.fn(async () => []),
  listCustomStrategyTemplates: vi.fn(async () => []),
  listStrategyGallery: vi.fn(async () => []),
  classifyApiError: (error: unknown) => ({
    backendUnavailable: false,
    message: String(error),
  }),
}));

/** Commands built exactly the way the page builds them, minus the closures. */
function navCommands(onRun: (view: string) => void): Command[] {
  return WORKSPACE_COMMANDS.map((c) => ({
    id: `nav-${c.title}`,
    group: "Navigation",
    title: c.title,
    keywords: c.keywords,
    run: () => onRun(String(c.view)),
  }));
}

function renderPalette(onRun = vi.fn()) {
  const result = renderWithUser(
    <CommandPalette
      commands={navCommands(onRun)}
      onOpenBacktest={vi.fn()}
      onOpenReport={vi.fn()}
      onOpenSavedTemplate={vi.fn()}
      onOpenGalleryTemplate={vi.fn()}
    />,
  );
  return { ...result, onRun };
}

/**
 * Open the palette and wait for its saved-resource fetch to settle.
 *
 * The palette fetches saved backtests/reports/templates whenever it opens.
 * Settling that promise here keeps every assertion deterministic and means the
 * suite never has to suppress React's `act(...)` warning — an unsettled state
 * update stays a real, visible signal.
 */
async function open(): Promise<HTMLElement> {
  // `openCommandPalette()` dispatches a window event that synchronously sets
  // state, so it has to run inside `act`.
  await act(async () => {
    openCommandPalette();
  });
  const dialog = await screen.findByRole("dialog", { name: "Command palette" });
  // Flush the `Promise.allSettled` resource fetch inside `act` so its state
  // update is accounted for. Without this the suite would either be racy or
  // have to silence React's act(...) warning — and silencing it would hide
  // genuine unhandled updates in future tests.
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
  await waitFor(() =>
    expect(screen.queryByText(/Loading saved resources/)).toBeNull(),
  );
  return dialog;
}

describe("CommandPalette", () => {
  beforeEach(() => {
    // The palette only renders after mount + an explicit open event.
    vi.clearAllMocks();
  });

  it("stays closed until it is opened", () => {
    renderPalette();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens as a labelled modal dialog with a focused search box", async () => {
    renderPalette();
    const dialog = await open();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const input = screen.getByPlaceholderText(/Search commands/);
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("finds a workspace by its canonical command title", async () => {
    const { user } = renderPalette();
    await open();
    await user.type(screen.getByPlaceholderText(/Search commands/), "Signal Ensemble");
    expect(
      screen.getByRole("button", { name: /Open Signal Ensemble Lab/ }),
    ).toBeInTheDocument();
  });

  it("finds a workspace by a keyword alias that is never displayed", async () => {
    const { user } = renderPalette();
    await open();
    // "dendrogram" appears only in the Signal Ensemble command's keywords.
    await user.type(screen.getByPlaceholderText(/Search commands/), "dendrogram");
    const match = screen.getByRole("button", { name: /Open Signal Ensemble Lab/ });
    expect(match).toBeInTheDocument();
    expect(match).not.toHaveTextContent("dendrogram");
  });

  it("navigates to the exact view when a workspace command is chosen", async () => {
    const { user, onRun } = renderPalette();
    await open();
    await user.type(screen.getByPlaceholderText(/Search commands/), "Factor Diagnostics");
    await user.click(screen.getByRole("button", { name: /Open Factor Diagnostics/ }));
    expect(onRun).toHaveBeenCalledWith("factordiagnostics");
    // Running a command closes the palette so the workspace is visible.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("supports the arrow-key + Enter keyboard flow", async () => {
    const { user, onRun } = renderPalette();
    await open();
    const input = screen.getByPlaceholderText(/Search commands/);
    await user.type(input, "Open Signal");
    const before = screen.getAllByRole("button").map((b) => b.textContent);
    expect(before.length).toBeGreaterThan(1);
    await user.keyboard("{ArrowDown}{Enter}");
    expect(onRun).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape without running anything", async () => {
    const { user, onRun } = renderPalette();
    await open();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(onRun).not.toHaveBeenCalled();
  });

  it("shows an honest empty state for an unknown search", async () => {
    const { user } = renderPalette();
    await open();
    await user.type(
      screen.getByPlaceholderText(/Search commands/),
      "zzzz-not-a-workspace",
    );
    expect(screen.getByText(/No results found/)).toBeInTheDocument();
    expect(screen.getByText(/zzzz-not-a-workspace/)).toBeInTheDocument();
  });

  it("gives every rendered result an accessible name", async () => {
    const { user } = renderPalette();
    await open();
    await user.type(screen.getByPlaceholderText(/Search commands/), "Open");
    for (const button of screen.getAllByRole("button")) {
      expect(button.textContent?.trim()).not.toBe("");
    }
  });
});
