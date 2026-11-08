import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithUser } from "@/test/testUtils";
import { diagnosticRun, returnInput } from "@/test/fixtures/portfolioDiagnosticsComposer";
import { rebalances } from "@/test/fixtures/portfolioStressComposer";
import * as api from "@/lib/portfolioDiagnostics";
import * as notices from "@/lib/toast";
import PortfolioDiagnosticsPanel from "./PortfolioDiagnosticsPanel";

vi.mock("@/lib/portfolioDiagnostics", async (original) => ({ ...await original<typeof api>(),
  listRuns: vi.fn(), getLabSummary: vi.fn(), getRun: vi.fn(), createRun: vi.fn(), executeRun: vi.fn(), seedDemo: vi.fn(), exportRuns: vi.fn(), compareRuns: vi.fn(),
  getWeights: vi.fn(), getRiskContributions: vi.fn(), getRebalances: vi.fn(), getSensitivity: vi.fn(), markBaseline: vi.fn() }));
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (err: unknown) => void;
  const promise = new Promise<T>((ok, fail) => { resolve = ok; reject = fail; }); return { promise, resolve, reject };
}
beforeEach(() => {
  for (const fn of [api.listRuns, api.getLabSummary, api.getRun, api.createRun, api.executeRun, api.seedDemo, api.exportRuns, api.compareRuns, api.getWeights, api.getRiskContributions, api.getRebalances, api.getSensitivity]) vi.mocked(fn).mockReset();
  vi.mocked(api.listRuns).mockResolvedValue({ items: [diagnosticRun(), diagnosticRun({ id: 52, name: "Second source" })], total: 2, page: 1, total_pages: 1 });
  vi.mocked(api.getLabSummary).mockResolvedValue({ runs: 2, completed: 2, assets: 4, constraint_violations: 0, solver_failures: 0, baselines: 0 });
  vi.mocked(api.getRun).mockResolvedValue(diagnosticRun());
  vi.mocked(api.createRun).mockResolvedValue(diagnosticRun({ status: "pending" }));
  vi.mocked(api.executeRun).mockResolvedValue(diagnosticRun());
  [api.getWeights, api.getRiskContributions, api.getSensitivity].forEach((fn) => vi.mocked(fn).mockResolvedValue({ items: [] }));
  vi.mocked(api.getRebalances).mockResolvedValue({ items: [{ ...rebalances[0], rebalance_id: 0, status: "completed", solver_status: "closed_form", weights: { a: 0.7, b: 0.3 } }] });
});

async function prepare(user: ReturnType<typeof renderWithUser>["user"]) {
  await user.click(screen.getAllByRole("button", { name: "New portfolio run" })[0]);
  fireEvent.change(screen.getByLabelText("Return JSON"), { target: { value: JSON.stringify(returnInput()) } });
  await user.click(screen.getByRole("button", { name: "Validate return data" }));
  await user.type(screen.getByLabelText("Run name"), "My source");
  await user.type(screen.getByLabelText("Weight for a (%)"), "70"); await user.type(screen.getByLabelText("Weight for b (%)"), "30");
}
it("offers the Composer in the empty state without seeding or fake results", async () => {
  vi.mocked(api.listRuns).mockResolvedValue({ items: [], total: 0, page: 1, total_pages: 0 });
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  const empty = await screen.findByText("No portfolio-diagnostic runs yet");
  const section = empty.parentElement!;
  await user.click(within(section).getByRole("button", { name: "New portfolio run" }));
  expect(screen.getByRole("heading", { name: "New portfolio run" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Back to runs" }));
  expect(await screen.findByText("No portfolio-diagnostic runs yet")).toBeVisible();
  expect(api.seedDemo).not.toHaveBeenCalled(); expect(api.createRun).not.toHaveBeenCalled();
});
it("opens the real stored detail and confirms actual rebalance weights before offering source selection", async () => {
  const pendingRows = deferred<Awaited<ReturnType<typeof api.getRebalances>>>();
  vi.mocked(api.getRebalances).mockReturnValueOnce(pendingRows.promise);
  const onNav = vi.fn(); const { user } = renderWithUser(<PortfolioDiagnosticsPanel onNav={onNav} />);
  await prepare(user); await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("heading", { name: "My supplied portfolio" })).toBeVisible();
  expect(screen.queryByText(/weights are available for selection/)).not.toBeInTheDocument();
  await act(async () => pendingRows.resolve({ items: [{ ...rebalances[0], rebalance_id: 0, weights: { a: 0.7, b: 0.3 } }] }));
  expect(await screen.findByText(/weights are available for selection/)).toBeVisible();
  expect(screen.getByText(/Source #51:/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Open Portfolio Stress" })); expect(onNav).toHaveBeenCalledExactlyOnceWith("portfoliostress");
  expect(api.executeRun).toHaveBeenCalledExactlyOnceWith(51);
});
it("does not equate parent completion with a successful solver or usable book", async () => {
  vi.mocked(api.executeRun).mockResolvedValue(diagnosticRun({ method: "inverse_volatility", solver_status: "failed", warnings: ["no rebalance produced weights; portfolio risk diagnostics are unavailable"] }));
  vi.mocked(api.getRebalances).mockResolvedValue({ items: [{ ...rebalances[0], rebalance_id: 0, weights: null, solver_status: "failed", status: "failed", reason: "no asset has a usable volatility" }] });
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />); await prepare(user);
  await user.selectOptions(screen.getByLabelText("Construction method"), "inverse_volatility");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByText(/No usable stored rebalance weights/)).toBeVisible();
  expect(screen.getByText("no rebalance produced weights; portfolio risk diagnostics are unavailable")).toBeVisible();
  expect(screen.getByText(/Rebalance #0: failed; solver: failed/)).toBeVisible();
  expect(screen.queryByText(/weights are available for selection/)).not.toBeInTheDocument();
  expect(api.createRun).toHaveBeenCalledOnce();
});

it("shows authoritative inverse-volatility weights and per-asset unavailability without claiming provenance certification", async () => {
  const result = diagnosticRun({ method: "inverse_volatility", integrity_status: "verified_causal_rolling", warnings: ["rebalance 0: volatility unavailable for a"] });
  vi.mocked(api.executeRun).mockResolvedValue(result);
  vi.mocked(api.getRebalances).mockResolvedValue({ items: [{ ...rebalances[0], rebalance_id: 0, weights: { a: 0, b: 1 },
    solver: { status: "closed_form", unavailable_assets: [{ asset_id: "a", reason: "zero or negative volatility with no configured floor" }], floored_assets: [] } }] });
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />); await prepare(user);
  await user.selectOptions(screen.getByLabelText("Construction method"), "inverse_volatility");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByText(/weights are available for selection/)).toBeVisible();
  expect(screen.getByText("rebalance 0: volatility unavailable for a")).toBeVisible();
  expect(screen.getByText(/Integrity labels describe the recorded estimation policy/)).toBeVisible();
  expect(screen.getByText(/Inverse volatility.*sample covariance/)).toBeVisible();
  await user.click(screen.getByText("Inspect", { selector: "summary" }));
  expect(screen.getByText(/zero or negative volatility with no configured floor/)).toBeVisible();
  expect(screen.getByText(/Target weights:/).closest("p")).toHaveTextContent('{"a":0,"b":1}');
  expect(screen.queryByText(/Volatility floor applied to:/)).not.toBeInTheDocument();
});
it.each(["pending", "failed"] as const)("can inspect and return to recovery for the same %s ID", async (status) => {
  vi.mocked(api.executeRun).mockRejectedValueOnce(new Error("Lost response"));
  vi.mocked(api.getRun).mockResolvedValue(diagnosticRun({ status }));
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />); await prepare(user); await user.click(screen.getByRole("button", { name: "Create and run" }));
  await user.click(await screen.findByRole("button", { name: "Open stored run" }));
  await user.click(await screen.findByRole("button", { name: "Recover execution of run #51" }));
  expect(screen.getByRole("heading", { name: "Recover portfolio run" })).toBeVisible();
  expect(screen.queryByLabelText("Return JSON")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Refresh stored run" }));
  await user.click(screen.getByRole("button", { name: "Retry execution of this run" }));
  expect(await screen.findByRole("heading", { name: "My supplied portfolio" })).toBeVisible();
  expect(api.createRun).toHaveBeenCalledOnce(); expect(vi.mocked(api.executeRun).mock.calls).toEqual([[51], [51]]);
});
it.each(["resolve", "reject"] as const)("ignores obsolete detail %s after entering Composer", async (outcome) => {
  const pending = deferred<api.RunFull>(); vi.mocked(api.getRun).mockReturnValueOnce(pending.promise);
  const toast = vi.spyOn(notices.toast, "error");
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  await user.click(screen.getByRole("button", { name: "New portfolio run" }));
  await act(async () => { if (outcome === "resolve") pending.resolve(diagnosticRun()); else pending.reject(new Error("obsolete")); });
  expect(screen.getByRole("heading", { name: "New portfolio run" })).toBeVisible(); expect(toast).not.toHaveBeenCalled();
});
it("recovers a pending record found after uncertain creation without creating a replacement", async () => {
  vi.mocked(api.createRun).mockRejectedValueOnce(new Error("Creation response lost"));
  vi.mocked(api.getRun).mockResolvedValue(diagnosticRun({ status: "pending" }));
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Creation outcome is unknown");
  await user.click(screen.getByRole("button", { name: "Inspect run list" }));
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  await user.click(await screen.findByRole("button", { name: "Recover execution of run #51" }));
  await user.click(screen.getByRole("button", { name: "Refresh stored run" }));
  await user.click(screen.getByRole("button", { name: "Retry execution of this run" }));
  expect(await screen.findByRole("heading", { name: "My supplied portfolio" })).toBeVisible();
  expect(api.createRun).toHaveBeenCalledOnce(); expect(api.executeRun).toHaveBeenCalledExactlyOnceWith(51);
});
it("never claims stress availability when stored rebalances fail to load", async () => {
  vi.mocked(api.getRebalances).mockRejectedValue(new Error("Rebalances unavailable"));
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  expect(await screen.findByText("Some portfolio diagnostics could not be loaded")).toBeVisible();
  expect(screen.queryByText(/weights are available for selection/)).not.toBeInTheDocument();
});
it.each(["refresh", "filter", "reset", "page", "unmount"])("invalidates pending detail on %s", async (action) => {
  const pending = deferred<api.RunFull>(); vi.mocked(api.getRun).mockReturnValueOnce(pending.promise);
  vi.mocked(api.listRuns).mockResolvedValue({ items: [diagnosticRun()], total: 30, page: 1, total_pages: 2 });
  const view = renderWithUser(<PortfolioDiagnosticsPanel />);
  await view.user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  if (action === "refresh") await view.user.click(screen.getByRole("button", { name: /Refresh/ }));
  if (action === "filter") await view.user.selectOptions(screen.getByLabelText("Status"), "failed");
  if (action === "reset") await view.user.click(screen.getByRole("button", { name: "Reset filters" }));
  if (action === "page") await view.user.click(screen.getByRole("button", { name: /Next/ }));
  if (action === "unmount") view.unmount();
  await act(async () => pending.resolve(diagnosticRun()));
  expect(screen.queryByRole("heading", { name: "My supplied portfolio" })).not.toBeInTheDocument();
});
it("latest detail selection wins and a wrong response ID is rejected", async () => {
  const old = deferred<api.RunFull>();
  vi.mocked(api.getRun).mockReturnValueOnce(old.promise).mockResolvedValueOnce(diagnosticRun({ id: 52, name: "Second source" }));
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  await user.click(screen.getByRole("button", { name: "Second source" }));
  expect(await screen.findByRole("heading", { name: "Second source" })).toBeVisible();
  await act(async () => old.resolve(diagnosticRun())); expect(screen.getByRole("heading", { name: "Second source" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: /Back to runs/ }));
  vi.mocked(api.getRun).mockResolvedValueOnce(diagnosticRun({ id: 99 })); const toast = vi.spyOn(notices.toast, "error");
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  await waitFor(() => expect(toast).toHaveBeenCalledWith(expect.any(String), "Stored run identity mismatch."));
});
it("preserves comparison, export and explicit demo actions", async () => {
  vi.mocked(api.compareRuns).mockResolvedValue({ a_id: 51, b_id: 52, comparability_warnings: ["different inputs"], groups: {}, weights: [], fingerprint_match: {}, baseline: {} });
  vi.mocked(api.exportRuns).mockResolvedValue({ runs: [{ id: 51 }] });
  vi.mocked(api.seedDemo).mockResolvedValue({ created_runs: 0, skipped_existing: 2 });
  const create = vi.fn(() => "blob:test"), revoke = vi.fn();
  vi.stubGlobal("URL", class extends URL { static createObjectURL = create; static revokeObjectURL = revoke; });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByLabelText("Select My supplied portfolio for comparison"));
  await user.click(screen.getByLabelText("Select Second source for comparison")); await user.click(screen.getByRole("button", { name: "Compare selected" }));
  expect(await screen.findByText(/different inputs/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: /Back to runs/ }));
  await user.click(screen.getByRole("button", { name: "Export JSON" })); await waitFor(() => expect(create).toHaveBeenCalledOnce());
  await user.click(screen.getByRole("button", { name: "Load demo runs" })); expect(api.seedDemo).toHaveBeenCalledOnce();
  expect(api.createRun).not.toHaveBeenCalled();
});
