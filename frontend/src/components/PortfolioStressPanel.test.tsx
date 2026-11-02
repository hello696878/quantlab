import { act, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithUser } from "@/test/testUtils";
import { portfolio, rebalances, stressRun } from "@/test/fixtures/portfolioStressComposer";
import * as api from "@/lib/portfolioStress";
import * as portfolios from "@/lib/portfolioDiagnostics";
import { BacktestApiError } from "@/lib/api";
import * as notices from "@/lib/toast";
import PortfolioStressPanel from "./PortfolioStressPanel";

vi.mock("@/lib/portfolioStress", async (original) => ({ ...await original<typeof api>(),
  listRuns: vi.fn(), getLabSummary: vi.fn(), getRun: vi.fn(), createRun: vi.fn(), executeRun: vi.fn(), seedDemo: vi.fn(),
  compareRuns: vi.fn(), exportRuns: vi.fn(), markBaseline: vi.fn(), getAssetResults: vi.fn(), getRiskResults: vi.fn(),
  getConstraintResults: vi.fn(), getEpisodes: vi.fn(), getAttribution: vi.fn(), getSensitivity: vi.fn() }));
vi.mock("@/lib/portfolioDiagnostics", async (original) => ({ ...await original<typeof portfolios>(),
  listRuns: vi.fn(), getRun: vi.fn(), getRebalances: vi.fn() }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

async function prepareComposer(user: ReturnType<typeof renderWithUser>["user"]) {
  await user.click(screen.getByRole("button", { name: "New stress run" }));
  await user.selectOptions(await screen.findByLabelText("Completed portfolio"), "11");
  await user.selectOptions(await screen.findByLabelText("Stored rebalance"), "2");
  await user.type(screen.getByLabelText("Run name"), "Retained assumptions");
  await user.type(screen.getByLabelText("Shock for a (%)"), "-10");
}

beforeEach(() => {
  vi.mocked(api.listRuns).mockResolvedValue({ items: [stressRun(), stressRun({ id: 43, name: "Second result" })], total: 2, page: 1, total_pages: 1 });
  vi.mocked(api.getLabSummary).mockResolvedValue({ runs: 2, completed: 2, scenarios: 2, constraint_breaches: 0, drawdown_episodes: 0, baselines: 0 });
  vi.mocked(api.getRun).mockResolvedValue(stressRun());
  vi.mocked(api.createRun).mockResolvedValue(stressRun({ status: "pending" }));
  vi.mocked(api.executeRun).mockResolvedValue(stressRun());
  for (const fn of [api.getAssetResults, api.getRiskResults, api.getConstraintResults, api.getEpisodes, api.getAttribution, api.getSensitivity]) {
    vi.mocked(fn).mockResolvedValue({ items: [] });
  }
  vi.mocked(portfolios.listRuns).mockResolvedValue({ items: [portfolio], total: 1, page: 1, total_pages: 1 });
  vi.mocked(portfolios.getRun).mockResolvedValue(portfolio);
  vi.mocked(portfolios.getRebalances).mockResolvedValue({ items: rebalances });
  vi.mocked(api.compareRuns).mockResolvedValue({ a_id: 42, b_id: 43, comparability_warnings: ["different assumptions"], groups: {}, contributions: [], fingerprint_match: {}, baseline: {} });
});

it("offers Composer from the empty state and returns to the real list", async () => {
  vi.mocked(api.listRuns).mockResolvedValue({ items: [], total: 0, page: 1, total_pages: 0 });
  const { user } = renderWithUser(<PortfolioStressPanel />);
  await user.click(await screen.findByRole("button", { name: "Create a stress run" }));
  expect(await screen.findByLabelText("Completed portfolio")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Back to runs" }));
  expect(await screen.findByText("No portfolio-stress runs yet")).toBeVisible();
  expect(api.seedDemo).not.toHaveBeenCalled();
});

it("opens the returned stored result in the existing real detail with partial/unavailable values", async () => {
  const { user } = renderWithUser(<PortfolioStressPanel />);
  await user.click(screen.getByRole("button", { name: "New stress run" }));
  await user.selectOptions(await screen.findByLabelText("Completed portfolio"), "11");
  await user.selectOptions(await screen.findByLabelText("Stored rebalance"), "2");
  await user.type(screen.getByLabelText("Run name"), "My shock");
  await user.type(screen.getByLabelText("Shock for a (%)"), "-10");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  const detail = await screen.findByTestId("portfolio-stress-detail");
  expect(within(detail).getByRole("heading", { name: "User shock result" })).toBeVisible();
  expect(within(detail).getByText("partial")).toBeVisible();
  expect(within(detail).getByText(/Unspecified shock; partial coverage\./)).toBeVisible();
  expect(within(detail).getByText(/withheld/)).toBeVisible();
  expect(within(detail).getByText(/no notional configured/)).toBeVisible();
  expect(api.createRun).toHaveBeenCalledTimes(1);
  expect(api.executeRun).toHaveBeenCalledExactlyOnceWith(42);
  expect(api.markBaseline).not.toHaveBeenCalled();
  expect(detail.textContent).toBeFiniteNumericText();
});

it("preserves existing list detail and comparison actions without creating a run", async () => {
  const { user } = renderWithUser(<PortfolioStressPanel />);
  await user.click(await screen.findByRole("button", { name: "User shock result" }));
  await screen.findByTestId("portfolio-stress-detail");
  await user.click(screen.getByRole("button", { name: /Back to runs/ }));
  await user.click(await screen.findByLabelText("Select User shock result for comparison"));
  await user.click(screen.getByLabelText("Select Second result for comparison"));
  await user.click(screen.getByRole("button", { name: "Compare selected" }));
  expect(await screen.findByText(/different assumptions/)).toBeVisible();
  expect(api.compareRuns).toHaveBeenCalledWith(42, 43);
  expect(api.createRun).not.toHaveBeenCalled();
});

it("preserves export through the existing API and real payload", async () => {
  vi.mocked(api.exportRuns).mockResolvedValue({ runs: [{ id: 42 }] });
  const create = vi.fn(() => "blob:test"), revoke = vi.fn();
  vi.stubGlobal("URL", class extends URL { static createObjectURL = create; static revokeObjectURL = revoke; });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const { user } = renderWithUser(<PortfolioStressPanel />);
  await screen.findByRole("button", { name: "User shock result" });
  await user.click(screen.getByRole("button", { name: "Export JSON" }));
  await waitFor(() => expect(api.exportRuns).toHaveBeenCalledWith({}));
  expect(create).toHaveBeenCalledOnce();
  expect(click).toHaveBeenCalledOnce();
  expect(revoke).toHaveBeenCalledWith("blob:test");
});

it("list responses while Composer is open cannot replace its form", async () => {
  let finish!: (value: Awaited<ReturnType<typeof api.listRuns>>) => void;
  vi.mocked(api.listRuns).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const { user } = renderWithUser(<PortfolioStressPanel />);
  await user.click(screen.getByRole("button", { name: "New stress run" }));
  await act(async () => finish({ items: [stressRun()], total: 1, page: 1, total_pages: 1 }));
  expect(screen.getByRole("heading", { name: "New stress run" })).toBeVisible();
});

it.each(["success", "failure"])("ignores obsolete detail %s during Composer creation and retains its recovery ID", async (outcome) => {
  const oldDetail = deferred<api.RunFull>();
  const creation = deferred<api.RunFull>();
  vi.mocked(api.getRun).mockReturnValueOnce(oldDetail.promise);
  vi.mocked(api.createRun).mockReturnValueOnce(creation.promise);
  vi.mocked(api.executeRun).mockRejectedValueOnce(new BacktestApiError(0, "lost execution response"));
  const notify = vi.spyOn(notices, "notifyBackendOffline").mockImplementation(() => {});
  const { user } = renderWithUser(<PortfolioStressPanel />);
  await user.click(await screen.findByRole("button", { name: "User shock result" }));
  await prepareComposer(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  await act(async () => {
    if (outcome === "success") oldDetail.resolve(stressRun({ name: "Obsolete detail" }));
    else oldDetail.reject(new BacktestApiError(0, "obsolete offline response"));
  });
  expect(screen.getByRole("heading", { name: "New stress run" })).toBeVisible();
  expect(screen.getByLabelText("Run name")).toHaveValue("Retained assumptions");
  expect(screen.getByLabelText("Shock for a (%)")).toHaveValue("-10");
  expect(notify).not.toHaveBeenCalled();
  await act(async () => creation.resolve(stressRun({ status: "pending" })));
  expect(await screen.findByRole("alert")).toHaveTextContent("Run #42 was created");
  expect(screen.getByRole("button", { name: "Refresh stored run" })).toBeVisible();
  expect(api.createRun).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ portfolio_run_id: 11,
    portfolio_rebalance_id: 2, scenario: expect.objectContaining({ asset_shocks: { a: { value: -10, unit: "percent" } } }) }));
  expect(api.executeRun).toHaveBeenCalledExactlyOnceWith(42);
});

it("can inspect a failed execution and resume the same stored ID without another creation", async () => {
  vi.mocked(api.executeRun).mockRejectedValueOnce(new BacktestApiError(0, "lost execution response"));
  vi.mocked(api.getRun).mockResolvedValue(stressRun({ status: "failed", error_message: "Stored failure" }));
  const { user } = renderWithUser(<PortfolioStressPanel />);
  await prepareComposer(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  await user.click(await screen.findByRole("button", { name: "Open stored run" }));
  expect(await screen.findByTestId("portfolio-stress-detail")).toHaveTextContent("Stored failure");
  for (const fn of [portfolios.listRuns, portfolios.getRun, portfolios.getRebalances]) vi.mocked(fn).mockClear();
  await user.click(screen.getByRole("button", { name: "Recover execution of run #42" }));
  expect(screen.getByRole("heading", { name: "Recover stress run" })).toBeVisible();
  expect(screen.queryByLabelText("Completed portfolio")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Retry execution of this run" })).toBeDisabled();
  expect(api.createRun).toHaveBeenCalledTimes(1);
  expect(api.executeRun).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", { name: "Refresh stored run" }));
  await user.click(screen.getByRole("button", { name: "Retry execution of this run" }));
  await screen.findByTestId("portfolio-stress-detail");
  expect(api.createRun).toHaveBeenCalledTimes(1);
  expect(vi.mocked(api.executeRun).mock.calls).toEqual([[42], [42]]);
  expect(vi.mocked(api.getRun).mock.calls).toEqual([[42], [42], [42]]);
  for (const fn of [portfolios.listRuns, portfolios.getRun, portfolios.getRebalances]) expect(fn).not.toHaveBeenCalled();
});

it("recovers a pending record found after an unknown creation response without recreating it", async () => {
  vi.mocked(api.listRuns).mockResolvedValueOnce({ items: [], total: 0, page: 1, total_pages: 0 })
    .mockResolvedValue({ items: [stressRun({ status: "pending", result_fingerprint: null })], total: 1, page: 1, total_pages: 1 });
  vi.mocked(api.createRun).mockRejectedValueOnce(new BacktestApiError(0, "lost creation response"));
  vi.mocked(api.getRun).mockResolvedValue(stressRun({ status: "pending", result_fingerprint: null }));
  const { user } = renderWithUser(<PortfolioStressPanel />);
  await prepareComposer(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Creation outcome is unknown");
  await user.click(screen.getByRole("button", { name: "Inspect run list" }));
  await user.click(await screen.findByRole("button", { name: "User shock result" }));
  await screen.findByTestId("portfolio-stress-detail");
  await user.click(screen.getByRole("button", { name: "Recover execution of run #42" }));
  expect(api.createRun).toHaveBeenCalledTimes(1);
  expect(api.executeRun).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Refresh stored run" }));
  await user.click(screen.getByRole("button", { name: "Retry execution of this run" }));
  await screen.findByTestId("portfolio-stress-detail");
  expect(api.createRun).toHaveBeenCalledTimes(1);
  expect(api.executeRun).toHaveBeenCalledExactlyOnceWith(42);
  expect(vi.mocked(api.getRun).mock.calls).toEqual([[42], [42], [42]]);
});
