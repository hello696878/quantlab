import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StrategyEnsemblePanel from "./StrategyEnsemblePanel";
import { renderWithUser } from "@/test/testUtils";
import * as api from "@/lib/strategyEnsemble";
import { BacktestApiError } from "@/lib/api";
import fixture from "@/test/fixtures/strategyEnsemble.json";

vi.mock("@/lib/strategyEnsemble", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/strategyEnsemble")>(),
  listRuns: vi.fn(), getRun: vi.fn(), seedDemo: vi.fn(), createRun: vi.fn(),
  executeRun: vi.fn(), markBaseline: vi.fn(), invalidateRun: vi.fn(), compareRuns: vi.fn(), exportRun: vi.fn(),
}));
// Layout is browser-tested. Keep actual detail tables; omit only the chart container in jsdom.
vi.mock("recharts", async (importOriginal) => ({
  ...await importOriginal<typeof import("recharts")>(), ResponsiveContainer: () => null,
}));
const run = fixture as api.Run;
const listing = { items: [run], total: 1, page: 1, page_size: 25 };

beforeEach(() => {
  vi.mocked(api.listRuns).mockResolvedValue(listing);
  vi.mocked(api.getRun).mockResolvedValue(run);
  vi.mocked(api.seedDemo).mockResolvedValue({ created_count: 0, skipped_count: 10, run_ids: [1] });
});

describe("StrategyEnsemblePanel", () => {
  it("renders loading without invented records", () => {
    vi.mocked(api.listRuns).mockReturnValue(new Promise(() => {}));
    renderWithUser(<StrategyEnsemblePanel />);
    expect(screen.getByRole("status", { name: /Loading/ })).toBeInTheDocument();
    expect(screen.queryByText(run.name)).not.toBeInTheDocument();
  });
  it("shows an empty state", async () => {
    vi.mocked(api.listRuns).mockResolvedValue({ ...listing, items: [], total: 0 });
    renderWithUser(<StrategyEnsemblePanel />);
    expect(await screen.findByText("No strategy ensemble runs")).toBeInTheDocument();
  });
  it("loads demo once and opens actual fixture detail without running a backtest", async () => {
    const { user } = renderWithUser(<StrategyEnsemblePanel />);
    await screen.findByRole("button", { name: run.name });
    await user.click(screen.getByRole("button", { name: "Load demo runs" }));
    expect(await screen.findByText("0 demo runs created; 10 already present.")).toBeInTheDocument();
    expect(api.seedDemo).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: run.name }));
    expect(await screen.findByRole("table", { name: "Static strategy-return weights" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Cost basis and turnover" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Ensemble period reconciliation and drawdown" })).toBeInTheDocument();
    const firstStart = run.results!.ensemble.drawdown.periods[0].period_start.replace("T", " ").replace(/\.0+Z$/, " UTC");
    expect(screen.getAllByText(firstStart).length).toBeGreaterThan(0);
    expect(api.executeRun).not.toHaveBeenCalled();
    expect(screen.getByTestId("strategy-ensemble-detail").textContent).not.toMatch(/NaN|Infinity/);
  });
  it("prevents duplicate requests while loading a demo", async () => {
    let resolve!: (value: Awaited<ReturnType<typeof api.seedDemo>>) => void;
    vi.mocked(api.seedDemo).mockReturnValue(new Promise((done) => { resolve = done; }));
    const { user } = renderWithUser(<StrategyEnsemblePanel />);
    await screen.findByRole("button", { name: run.name });
    await user.dblClick(screen.getByRole("button", { name: "Load demo runs" }));
    expect(api.seedDemo).toHaveBeenCalledTimes(1);
    await act(async () => resolve({ created_count: 0, skipped_count: 10, run_ids: [1] }));
  });
  it("keeps offline context and retries the list", async () => {
    vi.mocked(api.listRuns).mockRejectedValueOnce(new BacktestApiError(0, "Backend unavailable"));
    const { user } = renderWithUser(<StrategyEnsemblePanel />);
    expect(await screen.findByText("Backend offline")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Retry/ }));
    expect(await screen.findByRole("button", { name: run.name })).toBeInTheDocument();
  });
  it("keeps form editing intact and rejects malformed JSON locally", async () => {
    const { user } = renderWithUser(<StrategyEnsemblePanel />);
    await screen.findByRole("button", { name: run.name });
    await user.click(screen.getByText("Create supplied return-stream run"));
    const input = screen.getByLabelText("Run definition (JSON)");
    await user.type(input, "not json");
    await user.click(screen.getByRole("button", { name: "Create run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("valid JSON");
    expect(api.createRun).not.toHaveBeenCalled();
    await user.clear(input);
    expect(input).toHaveValue("");
  });
  it("ignores a list result arriving after unmount", async () => {
    let resolve!: (value: api.Listing) => void;
    vi.mocked(api.listRuns).mockReturnValue(new Promise((done) => { resolve = done; }));
    const { unmount } = renderWithUser(<StrategyEnsemblePanel />);
    unmount();
    await act(async () => resolve(listing));
    await waitFor(() => expect(screen.queryByText(run.name)).not.toBeInTheDocument());
  });
});
