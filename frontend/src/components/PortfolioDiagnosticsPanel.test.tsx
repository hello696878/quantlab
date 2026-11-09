import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithUser } from "@/test/testUtils";
import { diagnosticRun, returnInput, storedUniverse } from "@/test/fixtures/portfolioDiagnosticsComposer";
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
  for (const fn of [api.listRuns, api.getLabSummary, api.getRun, api.createRun, api.executeRun, api.seedDemo, api.exportRuns, api.compareRuns, api.getWeights, api.getRiskContributions, api.getRebalances, api.getSensitivity, api.markBaseline]) vi.mocked(fn).mockReset();
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

const reuseAction = "Use return data in a new portfolio";
it("opens a data-only snapshot from the already-viewed detail and cancels without any source write or redundant GET", async () => {
  const source = diagnosticRun({ method: "erc", is_baseline: true, configuration: { estimation: { lookback: 5 } } });
  const before = structuredClone(source); vi.mocked(api.getRun).mockResolvedValue(source);
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: source.name }));
  await user.click(await screen.findByRole("button", { name: reuseAction }));
  expect(screen.getByRole("heading", { name: "New portfolio run" })).toBeVisible();
  const input = JSON.parse((screen.getByLabelText("Return JSON") as HTMLTextAreaElement).value);
  expect(input.timestamps).toEqual(source.universe.timestamps);
  expect(input.assets.map((a: { asset_id: string }) => a.asset_id)).toEqual(["a", "b"]);
  expect(input.assets.map((a: { returns: number[] }) => a.returns)).toEqual(source.universe.assets.map((a) => a.returns));
  expect(screen.getByText(/Return data copied from run #51/)).toBeVisible();
  expect(screen.getByLabelText("Run name")).toHaveValue(""); expect(screen.getByLabelText("Rolling lookback")).toHaveValue("20");
  expect(screen.getByLabelText("Construction method")).toHaveValue("user_supplied");
  expect(screen.getByLabelText("Weight for a (%)")).toHaveValue("");
  await user.click(screen.getByRole("button", { name: "Back to runs" }));
  expect(api.getRun).toHaveBeenCalledExactlyOnceWith(51);
  for (const fn of [api.createRun, api.executeRun, api.seedDemo, api.markBaseline]) expect(fn).not.toHaveBeenCalled();
  expect(source).toEqual(before);
});

it("starts a fresh draft for repeated source A, source B, and blank creation", async () => {
  const a = diagnosticRun();
  const b = diagnosticRun({ id: 52, name: "Second source", universe: storedUniverse(returnInput(25, ["z", "x"])) });
  vi.mocked(api.getRun).mockImplementation(async (id) => id === 52 ? b : a);
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  const openReuse = async (name: string) => {
    await user.click(await screen.findByRole("button", { name }));
    await user.click(await screen.findByRole("button", { name: reuseAction }));
  };
  await openReuse(a.name);
  await user.type(screen.getByLabelText("Run name"), "Old draft");
  await user.type(screen.getByLabelText("Weight for a (%)"), "70");
  await user.selectOptions(screen.getByLabelText("Construction method"), "inverse_volatility");
  await user.clear(screen.getByLabelText("Rolling lookback")); await user.type(screen.getByLabelText("Rolling lookback"), "3");
  await user.click(screen.getByRole("button", { name: "Back to runs" }));
  await openReuse(a.name);
  expect(screen.getByLabelText("Run name")).toHaveValue(""); expect(screen.getByLabelText("Weight for a (%)")).toHaveValue("");
  expect(screen.getByLabelText("Construction method")).toHaveValue("user_supplied"); expect(screen.getByLabelText("Rolling lookback")).toHaveValue("20");
  await user.click(screen.getByRole("button", { name: "Back to runs" }));
  await openReuse(b.name);
  expect(screen.getByText(/Return data copied from run #52, "Second source"/)).toBeVisible();
  const input = JSON.parse((screen.getByLabelText("Return JSON") as HTMLTextAreaElement).value);
  expect(input.assets.map((asset: { asset_id: string }) => asset.asset_id)).toEqual(["z", "x"]);
  expect(input.assets.map((asset: { returns: number[] }) => asset.returns)).toEqual(b.universe.assets.map((asset) => asset.returns));
  expect(input.timestamps).toEqual(b.universe.timestamps);
  expect(screen.getByLabelText("Weight for z (%)")).toHaveValue("");
  await user.click(screen.getByRole("button", { name: "Back to runs" }));
  await user.click(await screen.findByRole("button", { name: "New portfolio run" }));
  expect(screen.getByLabelText("Return JSON")).toHaveValue("");
  expect(screen.queryByLabelText("Validated return preview")).not.toBeInTheDocument();
  expect(screen.queryByText(/Return data copied from run/)).not.toBeInTheDocument();
  expect(api.createRun).not.toHaveBeenCalled(); expect(api.executeRun).not.toHaveBeenCalled();
});

it("permits data reuse even when completed parent construction failed", async () => {
  vi.mocked(api.getRun).mockResolvedValue(diagnosticRun({ solver_status: "failed", risk: null, result_fingerprint: null }));
  vi.mocked(api.getRebalances).mockResolvedValue({ items: [{ ...rebalances[0], weights: null, status: "failed", solver_status: "failed" }] });
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  expect(await screen.findByText(/No usable stored rebalance weights/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: reuseAction }));
  expect(screen.getByLabelText("Validated return preview")).toHaveTextContent("24 observations");
  expect(api.createRun).not.toHaveBeenCalled(); expect(api.executeRun).not.toHaveBeenCalled();
});

it.each(["pending", "running", "failed", "invalidated"] as const)("does not offer writable reuse for parent %s and preserves recovery", async (status) => {
  vi.mocked(api.getRun).mockResolvedValue(diagnosticRun({ status }));
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  expect(await screen.findByRole("button", { name: reuseAction })).toBeDisabled();
  expect(screen.getByText(/reuse is available only for completed/)).toBeVisible();
  if (status === "pending" || status === "failed") expect(screen.getByRole("button", { name: "Recover execution of run #51" })).toBeEnabled();
});

it.each(["missing_returns", "datetime", "metadata", "link_zero"])("shows a useful unsupported-source reason for %s", async (kind) => {
  const source = diagnosticRun();
  if (kind === "missing_returns") Reflect.deleteProperty(source.universe.assets[0], "returns");
  if (kind === "datetime") source.universe.timestamps[0] += "T00:00:00";
  if (kind === "metadata") source.universe.assets[0].metadata = { meaningful: true };
  if (kind === "link_zero") source.dataset_version_id = 0;
  vi.mocked(api.getRun).mockResolvedValue(source);
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: source.name }));
  expect(await screen.findByRole("button", { name: reuseAction })).toBeDisabled();
  expect(screen.getByText(/Return data unavailable for reuse:/)).toHaveTextContent(kind === "missing_returns" ? "returns must be an array" : kind === "datetime" ? "YYYY-MM-DD" : kind === "metadata" ? "metadata" : "dataset_version_id");
  expect(api.createRun).not.toHaveBeenCalled();
});

it("ignores obsolete detail and child responses after the newest source enters a reuse draft", async () => {
  const old = deferred<api.RunFull>(); const children = deferred<Awaited<ReturnType<typeof api.getRebalances>>>();
  const b = diagnosticRun({ id: 52, name: "Second source", universe: storedUniverse(returnInput(25)) });
  vi.mocked(api.getRun).mockReturnValueOnce(old.promise).mockResolvedValueOnce(b);
  vi.mocked(api.getRebalances).mockReturnValueOnce(children.promise);
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  await user.click(screen.getByRole("button", { name: "Second source" }));
  await user.click(await screen.findByRole("button", { name: reuseAction }));
  await act(async () => { old.resolve(diagnosticRun()); children.resolve({ items: rebalances }); });
  expect(screen.getByRole("heading", { name: "New portfolio run" })).toBeVisible();
  expect(screen.getByText(/Return data copied from run #52/)).toBeVisible();
  expect(screen.getByLabelText("Validated return preview")).toHaveTextContent("25 observations");
  expect(api.getRun).toHaveBeenCalledTimes(2); expect(api.createRun).not.toHaveBeenCalled();
});

it("separates recovery of the newly created ID from reuse and clears that recovery on the next reuse", async () => {
  vi.mocked(api.getRun).mockResolvedValueOnce(diagnosticRun())
    .mockResolvedValueOnce(diagnosticRun({ id: 61, status: "pending" })).mockResolvedValueOnce(diagnosticRun());
  vi.mocked(api.createRun).mockResolvedValue(diagnosticRun({ id: 61, status: "pending" }));
  vi.mocked(api.executeRun).mockRejectedValueOnce(new Error("Lost new execution response"));
  const { user } = renderWithUser(<PortfolioDiagnosticsPanel />);
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  await user.click(await screen.findByRole("button", { name: reuseAction }));
  await user.type(screen.getByLabelText("Run name"), "New run"); await user.selectOptions(screen.getByLabelText("Construction method"), "equal_weight");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  await user.click(await screen.findByRole("button", { name: "Open stored run" }));
  await user.click(await screen.findByRole("button", { name: "Recover execution of run #61" }));
  expect(screen.getByRole("heading", { name: "Recover portfolio run" })).toBeVisible();
  expect(screen.queryByText(/Return data copied from run/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Return JSON")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Back to runs" }));
  await user.click(await screen.findByRole("button", { name: "My supplied portfolio" }));
  await user.click(await screen.findByRole("button", { name: reuseAction }));
  expect(screen.getByLabelText("Run name")).toHaveValue(""); expect(screen.getByLabelText("Construction method")).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Refresh stored run" })).not.toBeInTheDocument();
  expect(api.createRun).toHaveBeenCalledOnce(); expect(api.executeRun).toHaveBeenCalledExactlyOnceWith(61);
});
