import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithUser } from "@/test/testUtils";
import { monitorCatalog, monitorSnapshot } from "@/test/fixtures/marketMonitor";
import { MONITOR_WATCHLIST_KEY } from "@/lib/marketMonitorWatchlist";
import MarketMonitorPanel from "./MarketMonitorPanel";

function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
const json = (value: unknown) => new Response(JSON.stringify(value));
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  localStorage.clear();
  fetchMock = vi.fn(async (url: string) => json(url.endsWith("/catalog") ? monitorCatalog : monitorSnapshot(new URL(url, "http://localhost").searchParams.get("company") ?? "nvda")));
  vi.stubGlobal("fetch", fetchMock);
});

it("hydrates preferences before snapshots and preserves intentional empty preferences without writing defaults", async () => {
  localStorage.setItem(MONITOR_WATCHLIST_KEY, '{"version":1,"ids":[]}');
  const write = vi.spyOn(Storage.prototype, "setItem");
  render(<MarketMonitorPanel />);
  expect(await screen.findByText("Your watchlist is empty.")).toBeVisible();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock.mock.calls[1][0]).toBe("/api/market-monitor/snapshot?ids=");
  expect(write).not.toHaveBeenCalled();
});

it("adds, reorders and removes supported instruments while preserving unrelated storage", async () => {
  localStorage.setItem("quantlab.settings.v1", "keep");
  const { user } = renderWithUser(<MarketMonitorPanel />);
  await screen.findByRole("button", { name: "Move up NVIDIA" });
  await user.click(screen.getByRole("button", { name: "Move up NVIDIA" }));
  expect(JSON.parse(localStorage.getItem(MONITOR_WATCHLIST_KEY)!).ids).toEqual(["nvda", "sp500"]);
  await user.selectOptions(screen.getByLabelText("Add instrument"), "aapl");
  await user.click(screen.getByRole("button", { name: "Add" }));
  expect(JSON.parse(localStorage.getItem(MONITOR_WATCHLIST_KEY)!).ids).toEqual(["nvda", "sp500", "aapl"]);
  await user.click(screen.getByRole("button", { name: "Remove S&P 500" }));
  expect(JSON.parse(localStorage.getItem(MONITOR_WATCHLIST_KEY)!).ids).toEqual(["nvda", "aapl"]);
  expect(localStorage.getItem("quantlab.settings.v1")).toBe("keep");
});

it("retains usable in-memory watchlist updates when storage is denied", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("full"); });
  const { user } = renderWithUser(<MarketMonitorPanel />);
  await user.click(await screen.findByRole("button", { name: "Remove NVIDIA" }));
  expect(screen.queryByRole("button", { name: "Remove NVIDIA" })).not.toBeInTheDocument();
  expect(screen.getByText(/updated for this visit/)).toBeVisible();
});

it("renders real response values, negative basis points, original links and setup state", async () => {
  render(<MarketMonitorPanel />);
  expect(await screen.findByRole("link", { name: /Fed statement/ })).toHaveAttribute("href", "https://www.federalreserve.gov/new.htm");
  expect(within(screen.getByRole("region", { name: "Treasury rates" })).getByText(/-50.00/)).toHaveTextContent("bps");
  expect(screen.getByText(/-10.00 bps/)).toBeVisible();
  expect(screen.getByText("Change unavailable")).toBeVisible();
  expect(within(screen.getByRole("region", { name: "Selected company" })).getByText("Setup required")).toBeVisible();
  expect(screen.getByText("2026-12-08 to 2026-12-09")).toBeVisible();
});

it("filters sources/categories and selects company detail through the serialized request", async () => {
  const { user } = renderWithUser(<MarketMonitorPanel />);
  await screen.findByRole("link", { name: /Fed statement/ });
  await user.selectOptions(screen.getByLabelText("News category"), "news");
  expect(screen.queryByRole("link", { name: /Fed statement/ })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Apple company headline/ })).toBeVisible();
  await user.selectOptions(screen.getByRole("combobox", { name: "Selected company" }), "aapl");
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes("company=aapl"))).toBe(true));
  await user.click(screen.getByLabelText("Company name/ticker text match"));
  expect(screen.getByRole("link", { name: /Apple company headline/ })).toBeVisible();
});

it("clears the company-only filter when company selection is cleared", async () => {
  const { user } = renderWithUser(<MarketMonitorPanel />);
  const company = await screen.findByRole("combobox", { name: "Selected company" });
  await user.selectOptions(company, "aapl");
  await screen.findByRole("link", { name: /Apple company headline/ });
  const companyFilter = screen.getByLabelText("Company name/ticker text match");
  await user.click(companyFilter);
  expect(companyFilter).toBeChecked();
  expect(screen.queryByRole("link", { name: /Fed statement/ })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Apple company headline/ })).toBeVisible();

  await user.selectOptions(company, "nvda");
  expect(companyFilter).toBeChecked();
  expect(screen.queryByRole("link", { name: /Apple company headline/ })).not.toBeInTheDocument();
  await user.selectOptions(company, "aapl");
  expect(await screen.findByRole("link", { name: /Apple company headline/ })).toBeVisible();

  await user.selectOptions(company, "");
  expect(companyFilter).toBeDisabled();
  expect(companyFilter).not.toBeChecked();
  expect(await screen.findByRole("link", { name: /Fed statement/ })).toBeVisible();
  expect(screen.getByRole("link", { name: /Apple company headline/ })).toBeVisible();
});

it("ignores obsolete selections and aborts their requests even if the old response resolves late", async () => {
  const old = deferred<Response>();
  fetchMock.mockImplementation((url: string) => url.endsWith("/catalog") ? Promise.resolve(json(monitorCatalog)) : url.includes("company=nvda") ? old.promise : Promise.resolve(json(monitorSnapshot("aapl"))));
  const { user } = renderWithUser(<MarketMonitorPanel />);
  await user.selectOptions(await screen.findByRole("combobox", { name: "Selected company" }), "aapl");
  const stale = monitorSnapshot(); stale.sources[3].items[0].title = "OBSOLETE RESULT";
  await act(async () => old.resolve(json(stale)));
  expect(screen.queryByText("OBSOLETE RESULT")).not.toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Selected company" })).getByText(/222.00/)).toBeVisible();
});

it("prevents duplicate refreshes, retains the prior snapshot on failure, and cleans up pending work", async () => {
  const pending = deferred<Response>();
  render(<MarketMonitorPanel />);
  await screen.findByRole("link", { name: /Fed statement/ });
  fetchMock.mockImplementation(() => pending.promise);
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  fireEvent.click(screen.getByRole("button", { name: "Refreshing..." }));
  expect(fetchMock).toHaveBeenCalledTimes(3);
  await act(async () => pending.resolve(new Response("offline", { status: 503 })));
  expect(await screen.findByRole("alert")).toHaveTextContent("previous successful snapshot");
  expect(screen.getByRole("link", { name: /Fed statement/ })).toBeVisible();
});

it("cleans up interval/abort work and does not refresh while hidden", async () => {
  vi.useFakeTimers();
  let result: ReturnType<typeof render>;
  await act(async () => { result = render(<MarketMonitorPanel />); });
  expect(fetchMock).toHaveBeenCalledTimes(2);
  const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
  await act(async () => { await vi.advanceTimersByTimeAsync(300_000); });
  expect(fetchMock).toHaveBeenCalledTimes(2);
  visibility.mockReturnValue("visible");
  await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
  expect(fetchMock).toHaveBeenCalledTimes(3);
  result!.unmount();
  await act(async () => { await vi.advanceTimersByTimeAsync(600_000); });
  expect(fetchMock).toHaveBeenCalledTimes(3);
  vi.useRealTimers();
});

it("shows a useful catalog failure and retry instead of fake data", async () => {
  fetchMock.mockRejectedValueOnce(new Error("offline"));
  const { user } = renderWithUser(<MarketMonitorPanel />);
  expect(await screen.findByRole("alert")).toHaveTextContent("could not reach the backend");
  await user.click(screen.getByRole("button", { name: "Retry catalog" }));
  expect(await screen.findByRole("region", { name: "Personal watchlist" })).toBeVisible();
});

it("keeps source failures, stale data and safe text visible alongside successful sources", async () => {
  const snapshot = monitorSnapshot();
  snapshot.sources[0].status = "stale"; snapshot.sources[0].message = "Last successful observation retained";
  snapshot.sources[4].status = "unavailable"; snapshot.sources[4].items = [];
  snapshot.sources[3].items[0].title = "<script>alert('fixture')</script>";
  fetchMock.mockImplementation(async (url: string) => json(url.endsWith("/catalog") ? monitorCatalog : snapshot));
  render(<MarketMonitorPanel />);
  expect(await screen.findByText("<script>alert('fixture')</script>")).toBeVisible();
  expect(document.querySelector("script")).toBeNull();
  expect(within(screen.getByRole("region", { name: "Personal watchlist" })).getByText("Stale")).toBeVisible();
  expect(screen.getByText(/1 unavailable/)).toBeVisible();
  expect(within(screen.getByRole("region", { name: "Treasury rates" })).getByText(/-50.00/)).toBeVisible();
});
