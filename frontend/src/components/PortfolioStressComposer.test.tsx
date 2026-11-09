import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithUser } from "@/test/testUtils";
import * as portfolios from "@/lib/portfolioDiagnostics";
import * as stress from "@/lib/portfolioStress";
import { BacktestApiError } from "@/lib/api";
import { portfolio, rebalances, stressRun } from "@/test/fixtures/portfolioStressComposer";
import PortfolioStressComposer from "./PortfolioStressComposer";

vi.mock("@/lib/portfolioDiagnostics", async (original) => ({ ...await original<typeof portfolios>(),
  listRuns: vi.fn(), getRun: vi.fn(), getRebalances: vi.fn(), getWeights: vi.fn() }));
vi.mock("@/lib/portfolioStress", async (original) => ({ ...await original<typeof stress>(),
  createRun: vi.fn(), executeRun: vi.fn(), getRun: vi.fn() }));

const onOpen = vi.fn();
const onBack = vi.fn();
const second = { ...portfolio, id: 22, name: "Second portfolio", universe: { ...portfolio.universe,
  assets: [{ ...portfolio.universe.assets[0], asset_id: "c", name: "Asset C", group: null }] } };
const listing = { items: [portfolio, second], total: 2, page: 1, total_pages: 1 };

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => {
  for (const fn of [portfolios.listRuns, portfolios.getRun, portfolios.getRebalances, portfolios.getWeights,
    stress.createRun, stress.executeRun, stress.getRun]) vi.mocked(fn).mockReset();
  onOpen.mockReset(); onBack.mockReset();
  vi.mocked(portfolios.listRuns).mockResolvedValue(listing);
  vi.mocked(portfolios.getRun).mockResolvedValue(portfolio);
  vi.mocked(portfolios.getRebalances).mockResolvedValue({ items: rebalances });
  vi.mocked(stress.createRun).mockResolvedValue(stressRun({ status: "pending" }));
  vi.mocked(stress.executeRun).mockResolvedValue(stressRun());
  vi.mocked(stress.getRun).mockResolvedValue(stressRun({ status: "failed", error_message: "Review failed execution" }));
});

function setup() { return renderWithUser(<PortfolioStressComposer onBack={onBack} onOpen={onOpen} />); }

async function prepare(user: ReturnType<typeof setup>["user"]) {
  await user.selectOptions(await screen.findByLabelText("Completed portfolio"), "11");
  await user.selectOptions(await screen.findByLabelText("Stored rebalance"), "2");
  await user.type(screen.getByLabelText("Run name"), "My assumptions");
  await user.type(screen.getByLabelText("Shock for a (%)"), "-10");
}

it("uses the selected earlier signed stored weights and explicit ID, never final weights", async () => {
  const { user } = setup();
  await prepare(user);
  expect(screen.getByText("120.00%")).toBeVisible();
  expect(screen.getByText("-20.00%")).toBeVisible();
  expect(screen.getByText(rebalances[0].effective_timestamp!)).toBeVisible();
  expect(screen.getByText(portfolio.warnings[0])).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(stress.createRun).toHaveBeenCalledWith(expect.objectContaining({ portfolio_run_id: 11, portfolio_rebalance_id: 2,
    scenario: expect.objectContaining({ asset_shocks: { a: { value: -10, unit: "percent" } }, missing_shock_policy: "unavailable" }) }));
  expect(portfolios.getWeights).not.toHaveBeenCalled();
  expect(stress.executeRun).toHaveBeenCalledExactlyOnceWith(42);
  expect(onOpen).toHaveBeenCalledExactlyOnceWith(stressRun());
});

it("allows selecting another rebalance without fabricating or normalizing its weights", async () => {
  const { user } = setup(); await prepare(user);
  await user.selectOptions(screen.getByLabelText("Stored rebalance"), "9");
  expect(screen.getByText("40.00%")).toBeVisible();
  expect(screen.getByText("60.00%")).toBeVisible();
  expect(screen.getByLabelText("Shock for a (%)")).toHaveValue("");
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
});

it("explicitly selects rebalance zero instead of the different latest stored book", async () => {
  vi.mocked(portfolios.getRebalances).mockResolvedValue({ items: [{ ...rebalances[0], rebalance_id: 0 }, rebalances[1]] });
  vi.mocked(stress.createRun).mockResolvedValue(stressRun({ status: "pending", portfolio_rebalance_id: 0 }));
  vi.mocked(stress.executeRun).mockResolvedValue(stressRun({ portfolio_rebalance_id: 0 }));
  const { user } = setup();
  await user.selectOptions(await screen.findByLabelText("Completed portfolio"), "11");
  await user.selectOptions(await screen.findByLabelText("Stored rebalance"), "0");
  expect(screen.getByText("120.00%")).toBeVisible();
  expect(screen.getByText("-20.00%")).toBeVisible();
  expect(screen.queryByText("40.00%")).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Run name"), "First book");
  await user.type(screen.getByLabelText("Shock for a (%)"), "-10");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(stress.createRun).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ portfolio_rebalance_id: 0 }));
  expect(onOpen).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ portfolio_rebalance_id: 0 }));
  expect(portfolios.getWeights).not.toHaveBeenCalled();
});

it("keeps prototype-named asset shocks blank until explicitly supplied", async () => {
  const prototypePortfolio = { ...portfolio, universe: { ...portfolio.universe,
    assets: [{ ...portfolio.universe.assets[0], asset_id: "constructor", name: "Constructor asset", group: null },
      { ...portfolio.universe.assets[1], asset_id: "__proto__", name: "Prototype asset", group: null }] } };
  vi.mocked(portfolios.getRun).mockResolvedValue(prototypePortfolio);
  vi.mocked(portfolios.getRebalances).mockResolvedValue({ items: [{ ...rebalances[0],
    weights: Object.fromEntries([["constructor", 0.6], ["__proto__", 0.4]]) }] });
  const { user } = setup();
  await user.selectOptions(await screen.findByLabelText("Completed portfolio"), "11");
  await user.selectOptions(await screen.findByLabelText("Stored rebalance"), "2");
  await user.type(screen.getByLabelText("Run name"), "Prototype-named source");
  expect(screen.getByLabelText("Shock for constructor (%)")).toHaveValue("");
  expect(screen.getByLabelText("Shock for __proto__ (%)")).toHaveValue("");
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
  await user.type(screen.getByLabelText("Shock for __proto__ (%)"), "0");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  const body = vi.mocked(stress.createRun).mock.calls[0][0];
  expect(body.scenario.asset_shocks).toEqual(Object.fromEntries([["__proto__", { value: 0, unit: "percent" }]]));
  expect(Object.hasOwn(body.scenario.asset_shocks, "constructor")).toBe(false);
});

it("paginates actual completed portfolios and clears the dependent selection", async () => {
  vi.mocked(portfolios.listRuns).mockResolvedValueOnce({ ...listing, items: [portfolio], total: 21, total_pages: 2 })
    .mockResolvedValueOnce({ ...listing, items: [second], total: 21, page: 2, total_pages: 2 });
  const { user } = setup(); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Next portfolios" }));
  expect(await screen.findByRole("option", { name: /Second portfolio/ })).toBeVisible();
  expect(portfolios.listRuns).toHaveBeenLastCalledWith({ status: "completed", page: 2, page_size: 20 });
  expect(screen.queryByLabelText("Shock for a (%)")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
});

it("shows honest empty/no-solved-weight states without seeding a portfolio", async () => {
  vi.mocked(portfolios.listRuns).mockResolvedValueOnce({ ...listing, items: [], total: 0, total_pages: 0 });
  const view = setup();
  expect(await screen.findByText("No completed portfolios on this page")).toBeVisible();
  expect(stress.createRun).not.toHaveBeenCalled();
  view.unmount();
  vi.mocked(portfolios.getRebalances).mockResolvedValue({ items: [{ ...rebalances[0], weights: null }] });
  const next = setup();
  await next.user.selectOptions(await screen.findByLabelText("Completed portfolio"), "11");
  expect(await screen.findByText("No stored solved weights")).toBeVisible();
});

it("supports blank, zero, trailing decimals, missing policy and optional notional", async () => {
  const { user } = setup(); await prepare(user);
  const a = screen.getByLabelText("Shock for a (%)");
  await user.clear(a); await user.type(a, "0.");
  expect(a).toHaveValue("0.");
  await user.type(screen.getByLabelText("Shock for b (%)"), "-0.5");
  await user.selectOptions(screen.getByLabelText("Omitted asset shocks"), "zero");
  await user.type(screen.getByLabelText("Notional (optional)"), "1000");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  const body = vi.mocked(stress.createRun).mock.calls[0][0];
  expect(body.scenario.asset_shocks).toEqual({ a: { value: 0, unit: "percent" }, b: { value: -0.5, unit: "percent" } });
  expect(body.scenario.missing_shock_policy).toBe("zero");
  expect(body.notional).toBe(1000);
});

it.each(["100.01", "NaN", "Infinity", "10abc"])("cannot submit invalid shock %s", async (text) => {
  const { user } = setup(); await prepare(user);
  fireEvent.change(screen.getByLabelText("Shock for a (%)"), { target: { value: text } });
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
  expect(stress.createRun).not.toHaveBeenCalled();
});

it("cannot submit invalid notional or blank name; blank notional is omitted", async () => {
  const { user } = setup(); await prepare(user);
  await user.type(screen.getByLabelText("Notional (optional)"), "0");
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
  await user.clear(screen.getByLabelText("Notional (optional)"));
  await user.clear(screen.getByLabelText("Run name"));
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
  await user.type(screen.getByLabelText("Run name"), "New");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(vi.mocked(stress.createRun).mock.calls[0][0]).not.toHaveProperty("notional");
});

it("locks the full source/form while creating and executing and prevents duplicate writes", async () => {
  const creation = deferred<stress.RunFull>(), execution = deferred<stress.RunFull>();
  vi.mocked(stress.createRun).mockReturnValue(creation.promise);
  vi.mocked(stress.executeRun).mockReturnValue(execution.promise);
  const { user } = setup(); await prepare(user);
  await user.dblClick(screen.getByRole("button", { name: "Create and run" }));
  expect(stress.createRun).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("Completed portfolio")).toBeDisabled();
  expect(screen.getByLabelText("Shock for a (%)")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Back to runs" })).toBeDisabled();
  await act(async () => creation.resolve(stressRun({ status: "pending" })));
  expect(stress.executeRun).toHaveBeenCalledExactlyOnceWith(42);
  expect(screen.getByLabelText("Run name")).toBeDisabled();
  await act(async () => execution.resolve(stressRun()));
  expect(onOpen).toHaveBeenCalledTimes(1);
});

it("retains ID after execution failure, refreshes before retry, and never creates again", async () => {
  vi.mocked(stress.executeRun).mockRejectedValueOnce(new BacktestApiError(0, "lost execution response"));
  const { user } = setup(); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Run #42 was created");
  expect(screen.getByRole("button", { name: "Retry execution of this run" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Refresh stored run" }));
  await user.click(screen.getByRole("button", { name: "Retry execution of this run" }));
  await waitFor(() => expect(onOpen).toHaveBeenCalledWith(stressRun()));
  expect(stress.getRun).toHaveBeenCalledTimes(2);
  expect(stress.createRun).toHaveBeenCalledTimes(1);
  expect(stress.executeRun).toHaveBeenCalledTimes(2);
  expect(vi.mocked(stress.executeRun).mock.calls).toEqual([[42], [42]]);
});

it("resolves a lost execution response from storage without repeating completed execution", async () => {
  vi.mocked(stress.executeRun).mockRejectedValue(new BacktestApiError(0, "lost response"));
  vi.mocked(stress.getRun).mockResolvedValue(stressRun());
  const { user } = setup(); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  await user.click(await screen.findByRole("button", { name: "Refresh stored run" }));
  expect(onOpen).toHaveBeenCalledWith(stressRun());
  expect(stress.executeRun).toHaveBeenCalledTimes(1);
});

it.each(["running", "invalidated"] as const)("does not recover execution of a %s run", async (status) => {
  vi.mocked(stress.executeRun).mockRejectedValueOnce(new BacktestApiError(409, "conflict"));
  vi.mocked(stress.getRun).mockResolvedValue(stressRun({ status }));
  const { user } = setup(); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  await user.click(await screen.findByRole("button", { name: "Refresh stored run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(`${status}; execution recovery is unavailable`);
  expect(screen.getByRole("button", { name: "Retry execution of this run" })).toBeDisabled();
});

it("HTTP-successful failed execution is not opened as successful analysis", async () => {
  vi.mocked(stress.executeRun).mockResolvedValue(stressRun({ status: "failed", error_message: "Calculation failed" }));
  const { user } = setup(); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Calculation failed");
  expect(onOpen).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Open stored run" }));
  expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: 42, status: "failed" }));
});

it("lost creation response locks automatic resubmission and offers list inspection", async () => {
  vi.mocked(stress.createRun).mockRejectedValue(new BacktestApiError(0, "lost creation response"));
  const { user } = setup(); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Creation outcome is unknown");
  expect(screen.queryByRole("button", { name: "Create and run" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Inspect run list" }));
  expect(onBack).toHaveBeenCalledOnce();
  expect(stress.createRun).toHaveBeenCalledOnce();
  expect(stress.executeRun).not.toHaveBeenCalled();
});

it("retains validation errors inline and permits correction without claiming an unknown creation", async () => {
  vi.mocked(stress.createRun).mockRejectedValue(new BacktestApiError(422, "Asset became unavailable"));
  const { user } = setup(); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Asset became unavailable");
  expect(screen.getByLabelText("Run name")).toBeEnabled();
  expect(screen.getByRole("button", { name: "Create and run" })).toBeEnabled();
});

it("late source A cannot overwrite B or reuse its shocks", async () => {
  const first = deferred<portfolios.RunFull>();
  vi.mocked(portfolios.getRun).mockReturnValueOnce(first.promise).mockResolvedValueOnce(second);
  vi.mocked(portfolios.getRebalances).mockResolvedValueOnce({ items: rebalances })
    .mockResolvedValueOnce({ items: [{ ...rebalances[0], weights: { c: 1 } }] });
  const { user } = setup();
  await user.selectOptions(await screen.findByLabelText("Completed portfolio"), "11");
  await user.selectOptions(screen.getByLabelText("Completed portfolio"), "22");
  await user.selectOptions(await screen.findByLabelText("Stored rebalance"), "2");
  await act(async () => first.resolve(portfolio));
  expect(screen.getByLabelText("Shock for c (%)")).toHaveValue("");
  expect(screen.queryByLabelText("Shock for a (%)")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
});

it("a new source clears previously edited shocks and disables submit until it loads", async () => {
  const next = deferred<portfolios.RunFull>();
  const { user } = setup(); await prepare(user);
  vi.mocked(portfolios.getRun).mockReturnValue(next.promise);
  await user.selectOptions(screen.getByLabelText("Completed portfolio"), "22");
  expect(screen.queryByLabelText("Shock for a (%)")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
});

it("does not execute a created run after the Composer unmounts", async () => {
  const creation = deferred<stress.RunFull>();
  vi.mocked(stress.createRun).mockReturnValue(creation.promise);
  const { user, unmount } = setup(); await prepare(user);
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  unmount();
  await act(async () => creation.resolve(stressRun({ status: "pending" })));
  expect(stress.executeRun).not.toHaveBeenCalled();
  expect(onOpen).not.toHaveBeenCalled();
});

it("shows offline source errors with a retry instead of fabricated records", async () => {
  vi.mocked(portfolios.listRuns).mockRejectedValueOnce(new BacktestApiError(0, "offline"));
  const { user } = setup();
  expect(await screen.findByText("Backend offline")).toBeVisible();
  await user.click(screen.getByRole("button", { name: /Retry/ }));
  expect(await screen.findByLabelText("Completed portfolio")).toBeEnabled();
});
