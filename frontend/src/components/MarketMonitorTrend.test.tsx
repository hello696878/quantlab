import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { monitorCatalog, monitorHistory, monitorSnapshot } from "@/test/fixtures/marketMonitor";
import { MONITOR_WATCHLIST_KEY } from "@/lib/marketMonitorWatchlist";
import MarketMonitorPanel from "./MarketMonitorPanel";

// SVG layout is covered in Edge, not jsdom.
vi.mock("recharts", async (importOriginal) => ({
  ...await importOriginal<typeof import("recharts")>(),
  ResponsiveContainer: () => <span>Chart container</span>,
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const view = (name: string) => screen.getByRole("button", { name: `View trend for ${name}` });
const trend = (name: string) => screen.getByRole("region", { name: `Trend for ${name}` });
let fetchMock: ReturnType<typeof vi.fn>;
let history: (id: string, signal: AbortSignal) => Promise<Response>;
let snapshot: () => Promise<Response>;

beforeEach(() => {
  history = async (id) => json(monitorHistory(id));
  snapshot = async () => json(monitorSnapshot());
  fetchMock = vi.fn(async (input: string, init: RequestInit) => {
    const url = new URL(input, "http://localhost");
    if (url.pathname.endsWith("/catalog")) return json(monitorCatalog);
    if (url.pathname.endsWith("/snapshot")) return snapshot();
    if (url.pathname.endsWith("/history")) return history(url.searchParams.get("instrument_id")!, init.signal!);
    throw new Error("Unhandled test request");
  });
  vi.stubGlobal("fetch", fetchMock);
});

const historyCalls = () => fetchMock.mock.calls.filter(([url]) => url.includes("/history?"));

it("loads only the selected history before the pending snapshot and keeps company action separate", async () => {
  snapshot = () => new Promise<Response>(() => {});
  localStorage.setItem(MONITOR_WATCHLIST_KEY, JSON.stringify({ version: 1, ids: ["sp500", "nvda", "treasury2y"] }));
  render(<MarketMonitorPanel />);
  await screen.findByRole("button", { name: "View trend for S&P 500" });
  expect(historyCalls()).toHaveLength(0);
  expect(screen.queryByRole("button", { name: "View trend for treasury2y" })).not.toBeInTheDocument();
  fireEvent.click(view("S&P 500"));
  const panel = within(trend("S&P 500"));
  expect(await panel.findByText("Observed dates: 2026-11-05 to 2026-11-09")).toBeVisible();
  expect(screen.getByText("Loading observations...")).toBeVisible();
  fireEvent.click(panel.getByText("Daily values (3)"));
  const table = panel.getByRole("table", { name: "Daily values for S&P 500" });
  expect(within(table).getByRole("rowheader", { name: "2026-11-05" })).toBeVisible();
  expect(within(table).getByRole("cell", { name: "100.125" })).toBeVisible();
  expect(historyCalls().map(([url]) => url)).toEqual(["/api/market-monitor/history?instrument_id=sp500"]);
  fireEvent.click(within(screen.getByRole("region", { name: "Personal watchlist" })).getByRole("button", { name: "NVIDIA" }));
  expect(screen.getByRole("combobox", { name: "Selected company" })).toHaveValue("nvda");
  expect(trend("S&P 500")).toBeVisible();
  expect(historyCalls()).toHaveLength(1);
});

it("aborts a superseded selection and ignores its late response", async () => {
  const old = deferred<Response>();
  history = async (id) => id === "sp500" ? old.promise : json(monitorHistory(id));
  render(<MarketMonitorPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "View trend for S&P 500" }));
  await waitFor(() => expect(historyCalls()).toHaveLength(1));
  fireEvent.click(view("NVIDIA"));
  const panel = within(trend("NVIDIA"));
  await panel.findByText("Daily values (3)");
  expect(historyCalls()[0][1].signal.aborted).toBe(true);
  await act(async () => old.resolve(json(monitorHistory("sp500"))));
  expect(screen.queryByRole("region", { name: "Trend for S&P 500" })).not.toBeInTheDocument();
  fireEvent.click(panel.getByText("Daily values (3)"));
  expect(panel.getByRole("cell", { name: "123.5" })).toBeVisible();
  expect(panel.queryByRole("cell", { name: "100.125" })).not.toBeInTheDocument();
});

it("keeps only same-instrument history after failed refresh and leaves snapshot content alone", async () => {
  render(<MarketMonitorPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "View trend for S&P 500" }));
  const first = within(trend("S&P 500"));
  await first.findByText("Daily values (3)");
  history = async () => json({ detail: "History request failed" }, 503);
  fireEvent.click(first.getByRole("button", { name: "Refresh trend" }));
  expect(await first.findByRole("alert")).toHaveTextContent("Showing the last successful trend");
  expect(first.getByText("Stale")).toBeVisible();
  expect(first.getByText("Daily values (3)")).toBeVisible();
  expect(screen.getByRole("link", { name: /Fed statement/ })).toBeVisible();
  fireEvent.click(view("NVIDIA"));
  const second = within(trend("NVIDIA"));
  expect(await second.findByRole("alert")).toHaveTextContent("History request failed");
  expect(second.getByText("Unavailable")).toBeVisible();
  expect(second.queryByText("Daily values (3)")).not.toBeInTheDocument();
});

it.each([
  monitorHistory("nvda"),
  monitorHistory("sp500", { instrument: { ...monitorHistory("sp500").instrument, symbol: "ES=F", kind: "futures_reference" } }),
])("rejects an API response with incompatible instrument identity", async (response) => {
  history = async () => json(response);
  render(<MarketMonitorPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "View trend for S&P 500" }));
  const panel = within(trend("S&P 500"));
  expect(await panel.findByRole("alert")).toHaveTextContent("did not match the selected instrument");
  expect(panel.queryByText("Daily values (3)")).not.toBeInTheDocument();
});

it.each([
  { points: [null] },
  { points: [{ date: "2026-11-05", value: null }] },
  { points: [{ date: "2026-11-31", value: 10 }] },
  { points: [{ date: "2026-11-06", value: 10 }, { date: "2026-11-05", value: 20 }] },
  { status: "unavailable" },
])("rejects malformed HTTP 200 history (%j)", async (overrides) => {
  history = async (id) => json({ ...monitorHistory(id), ...overrides });
  render(<MarketMonitorPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "View trend for S&P 500" }));
  const panel = within(trend("S&P 500"));
  expect(await panel.findByRole("alert")).toHaveTextContent("invalid daily history");
  expect(panel.queryByRole("img")).not.toBeInTheDocument();
  expect(panel.getByText("No daily closes available.")).toBeVisible();
});

it("keeps the last good series and retrieval time when the backend has no cached history", async () => {
  render(<MarketMonitorPanel />);
  const opener = await screen.findByRole("button", { name: "View trend for S&P 500" });
  fireEvent.click(opener);
  const section = trend("S&P 500");
  const panel = within(section);
  expect(section).toHaveFocus();
  await panel.findByText("Daily values (3)");
  const previous = monitorHistory("sp500");
  const checkedAt = "2026-11-10T10:16:00Z";
  history = async (id) => json(monitorHistory(id, {
    status: "unavailable", points: [], timezone: null, retrieved_at: null, checked_at: checkedAt, message: "Source unavailable.",
  }));
  fireEvent.click(panel.getByRole("button", { name: "Refresh trend" }));
  expect(await panel.findByText(/Showing the last successful trend for this instrument/)).toBeVisible();
  expect(panel.getByText("Stale")).toBeVisible();
  expect(panel.getByText("Daily values (3)")).toBeVisible();
  expect(panel.getByText(/Retrieved:.*Checked:/).textContent).toBe(
    "Retrieved: " + new Date(previous.retrieved_at!).toLocaleString() + " / Checked: " + new Date(checkedAt).toLocaleString());
  const close = panel.getByRole("button", { name: "Close trend" });
  close.focus();
  fireEvent.click(close);
  expect(opener).toHaveFocus();
  expect(screen.queryByRole("region", { name: "Trend for S&P 500" })).not.toBeInTheDocument();
});

it("does not refetch on reorder or unrelated edits, and aborts on removal and unmount", async () => {
  history = () => new Promise<Response>(() => {});
  const app = render(<MarketMonitorPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "View trend for S&P 500" }));
  await waitFor(() => expect(historyCalls()).toHaveLength(1));
  fireEvent.click(screen.getByRole("button", { name: "Move up NVIDIA" }));
  fireEvent.change(screen.getByRole("combobox", { name: "Add instrument" }), { target: { value: "aapl" } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(trend("S&P 500")).toBeVisible();
  expect(historyCalls()).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Remove S&P 500" }));
  expect(screen.queryByRole("region", { name: "Trend for S&P 500" })).not.toBeInTheDocument();
  expect(historyCalls()[0][1].signal.aborted).toBe(true);
  fireEvent.click(view("NVIDIA"));
  await waitFor(() => expect(historyCalls()).toHaveLength(2));
  app.unmount();
  expect(historyCalls()[1][1].signal.aborted).toBe(true);
});

it("shows unavailable, single-point and stale responses with source context", async () => {
  history = async (id) => json(monitorHistory(id, { status: "unavailable", points: [], retrieved_at: null, message: "No daily closes were returned." }));
  render(<MarketMonitorPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "View trend for S&P 500" }));
  const panel = within(trend("S&P 500"));
  expect(await panel.findByText("No daily closes available.")).toBeVisible();
  expect(panel.getByText("No daily closes were returned.")).toBeVisible();
  history = async (id) => json(monitorHistory(id, { points: [{ date: "2026-11-05", value: 98.5 }], status: "stale", message: "Previous history retained." }));
  fireEvent.click(panel.getByRole("button", { name: "Refresh trend" }));
  expect(await panel.findByText(/insufficient history/)).toBeVisible();
  expect(panel.getByText("Stale")).toBeVisible();
  expect(panel.getByText("Previous history retained.")).toBeVisible();
  expect(panel.getByText(/Retrieved:.*Checked:/)).toBeVisible();
  expect(panel.getByRole("link", { name: "Yahoo Finance" })).toHaveAttribute("href", "https://finance.yahoo.com/");
});
