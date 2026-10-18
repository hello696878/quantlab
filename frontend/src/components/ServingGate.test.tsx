import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import ServingGate from "./ServingGate";

const local = { schema: "serving_capabilities_v1", mode: "local", policy: "local_v1", corpus_id: null, synthetic: false, capabilities: ["local_research"] };
const demo = { schema: "serving_capabilities_v1", mode: "read_only_demo", policy: "read_only_demo_v1", corpus_id: "a".repeat(64), synthetic: true, capabilities: ["browse_saved_sma", "explain_saved_sma"] };
const record = { id: 1, created_at: "2026-10-18T00:00:00Z", name: "Synthetic SMA showcase", ticker: "SYNTHETIC", strategy: "sma_crossover",
  start_date: "2000-01-03", end_date: "2000-09-08", total_return: .02, cagr: .03, sharpe_ratio: .5, max_drawdown: -.1,
  notes: "Synthetic fixture", config_hash_full: null, config_schema: null, initial_capital: 100000, transaction_cost_bps: 10,
  params: { fast_window: 5, slow_window: 20 }, metrics: {}, equity_curve: [], trades: [] };

it("does not mount normal workflows while capabilities are pending", async () => {
  let finish!: (r: Response) => void;
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>((resolve) => { finish = resolve; })));
  const mounted = vi.fn();
  function Ordinary() { mounted(); return <input aria-label="Existing research form" defaultValue="unsaved" />; }
  render(<ServingGate><Ordinary /></ServingGate>);
  expect(screen.getByRole("status")).toHaveTextContent("Checking");
  expect(mounted).not.toHaveBeenCalled();
  finish(new Response(JSON.stringify(local)));
  const field = await screen.findByRole("textbox", { name: "Existing research form" });
  expect(field).toHaveValue("unsaved");
});

it.each([new Response("{}"), new Response("internal private path", { status: 503 }), new Response("not JSON")])(
  "fails conservatively and retains a retry action", async (response) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    render(<ServingGate><p>Writable research</p></ServingGate>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Workspaces remain locked");
    expect(screen.queryByText("Writable research")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry connection" })).toBeEnabled();
    expect(screen.queryByText("internal private path")).not.toBeInTheDocument();
  });

it("retry can verify normal mode without changing existing settings", async () => {
  localStorage.setItem("quantlab.settings.v1", JSON.stringify({ accent_color: "emerald" }));
  const before = localStorage.getItem("quantlab.settings.v1");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new TypeError("network failure")).mockResolvedValueOnce(new Response(JSON.stringify(local))));
  render(<ServingGate><p>Local workspaces</p></ServingGate>);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry connection" }));
  expect(await screen.findByText("Local workspaces")).toBeVisible();
  expect(localStorage.getItem("quantlab.settings.v1")).toBe(before);
});

it("demo direct navigation only mounts approved browsing; deletes, saves and runs stay unavailable", async () => {
  history.replaceState(null, "", "/?view=backtest#run-replay=not-approved");
  const fetch = vi.fn().mockImplementation(async (url: string) => {
    if (url === "/api/capabilities") return new Response(JSON.stringify(demo));
    if (url === "/api/health") return new Response(JSON.stringify({ status: "ok" }));
    if (url === "/api/saved-backtests") return new Response(JSON.stringify([record]));
    if (url === "/api/saved-backtests/1") return new Response(JSON.stringify(record));
    throw new Error("Unexpected demo request");
  });
  vi.stubGlobal("fetch", fetch);
  render(<ServingGate><p>Ordinary research must not mount</p></ServingGate>);
  expect(await screen.findByRole("region", { name: "Read-only synthetic demo" })).toHaveAttribute("data-corpus-id", demo.corpus_id);
  expect(screen.queryByText("Ordinary research must not mount")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Backtest" })).toBeDisabled();
  const remove = await screen.findByRole("button", { name: "Delete" });
  expect(remove).toBeDisabled(); fireEvent.click(remove);
  fireEvent.click(screen.getByRole("button", { name: "View" }));
  await screen.findByRole("heading", { name: "Synthetic SMA showcase" });
  expect(screen.queryByRole("button", { name: "Save Report" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Register known configuration" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Explain stored result" })).toBeEnabled();
  for (const path of ["/api/saved-backtests", "/api/saved-backtests/1"]) {
    expect(fetch).toHaveBeenCalledWith(path, expect.objectContaining({ cache: "no-store", headers: { "X-QuantLab-Expected-Corpus": demo.corpus_id } }));
  }
  await waitFor(() => expect(fetch.mock.calls.every(([, options]) => !options?.method || options.method === "GET")).toBe(true));
});

it("does not replace a pinned demo with data from a restarted backend", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => {
    if (url === "/api/capabilities") return new Response(JSON.stringify(demo));
    if (url === "/api/health") return new Response(JSON.stringify({ status: "ok" }));
    return new Response(JSON.stringify({ detail: "Prepared corpus changed; reload before browsing" }), { status: 409 });
  }));
  render(<ServingGate><p>Writable research</p></ServingGate>);
  expect(await screen.findByText(/Prepared corpus changed; reload before browsing/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "View" })).not.toBeInTheDocument();
  expect(screen.queryByText("Writable research")).not.toBeInTheDocument();
});

it("makes a confirmed frontend/backend mode mismatch explicit", async () => {
  vi.stubEnv("NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE", "local");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(demo))));
  render(<ServingGate><p>Writable research</p></ServingGate>);
  expect(await screen.findByRole("alert")).toHaveTextContent("Frontend/backend serving mode mismatch");
  expect(screen.queryByText("Writable research")).not.toBeInTheDocument();
});
