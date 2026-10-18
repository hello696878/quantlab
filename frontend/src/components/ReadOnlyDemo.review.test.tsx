import { act, fireEvent, render, screen } from "@testing-library/react";
import { Blob as NodeBlob } from "node:buffer";
import { expect, it, vi } from "vitest";
import ReadOnlyDemo from "./ReadOnlyDemo";
import ServingGate from "./ServingGate";
import ResearchExplanationPanel from "./ResearchExplanationPanel";
import type { ServingCapabilities } from "@/lib/servingCapabilities";
import type { ResearchExplanation } from "@/lib/researchExplainer";

const local = { schema: "serving_capabilities_v1", mode: "local", policy: "local_v1", corpus_id: null, synthetic: false, capabilities: ["local_research"] };
const corpusA = "a".repeat(64), corpusB = "b".repeat(64);
function capabilities(corpus = corpusA): ServingCapabilities {
  return { schema: "serving_capabilities_v1", mode: "read_only_demo", policy: "read_only_demo_v1", corpus_id: corpus,
    synthetic: true, capabilities: ["browse_saved_sma", "explain_saved_sma"] };
}
function record(name: string) {
  return { id: 1, created_at: "2026-10-18T00:00:00Z", name, ticker: "SYNTHETIC", strategy: "sma_crossover",
    start_date: "2000-01-03", end_date: "2000-09-08", total_return: .02, cagr: .03, sharpe_ratio: .5, max_drawdown: -.1,
    notes: "Synthetic fixture", config_hash_full: null, config_schema: null, initial_capital: 100000, transaction_cost_bps: 10,
    params: { fast_window: 5, slow_window: 20 }, metrics: {}, equity_curve: [], trades: [] };
}
function explanation(value: number, display: string): ResearchExplanation {
  return { schema_version: "research_explanation_v1", adapter_version: "saved_sma_v1", template_version: "saved_sma_en_v1",
    policy_version: "stored_facts_policy_v1", locale: "en-US", identity: { source_kind: "saved_backtest", source_schema: "saved_backtests_row_v1",
      saved_backtest_id: 1, created_at: "2020-01-01T00:00:00Z", material_hash: "c".repeat(64), trust: "legacy_unverified", context: null },
    evidence: { saved: { metrics: { total_return: value } } }, facts: [{ id: "total_return", source: "saved", path: "/metrics/total_return",
      state: "available", value, unit: "decimal_return", rule: "percent_2", display }],
    statements: [{ template_id: "total_return", text: `The stored total return is ${display}.`, facts: ["total_return"], policy_id: null }],
    fingerprint: "d".repeat(64) };
}

it("does not use cached local permissions when the fresh capability contract is unavailable", async () => {
  localStorage.setItem("quantlab.serving_capabilities", JSON.stringify(local));
  localStorage.setItem("quantlab.settings.v1", JSON.stringify({ accent_color: "emerald" }));
  const before = localStorage.getItem("quantlab.settings.v1");
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...local, unexpected: true })));
  vi.stubGlobal("fetch", fetch);
  const mounted = vi.fn();
  function Ordinary() { mounted(); return <p>Writable ordinary workflow</p>; }
  render(<ServingGate><Ordinary /></ServingGate>);
  await screen.findByRole("alert");
  expect(mounted).not.toHaveBeenCalled();
  expect(fetch.mock.calls.map(([path]) => path)).toEqual(["/api/capabilities"]);
  expect(localStorage.getItem("quantlab.settings.v1")).toBe(before);
});

it("ignores a prior normal handshake that finishes after the current demo gate mounts", async () => {
  let finishOld!: (value: Response) => void;
  let handshakeCount = 0;
  const fetch = vi.fn().mockImplementation((url: string) => {
    if (url === "/api/capabilities") {
      if (++handshakeCount === 1) return new Promise<Response>((resolve) => { finishOld = resolve; });
      return Promise.resolve(new Response(JSON.stringify(capabilities())));
    }
    if (url === "/api/health") return Promise.resolve(new Response(JSON.stringify({ status: "ok" })));
    if (url === "/api/saved-backtests") return Promise.resolve(new Response(JSON.stringify([record("Current demo")])));
    throw new Error("Unexpected request");
  });
  vi.stubGlobal("fetch", fetch);
  const mounted = vi.fn();
  function Ordinary() { mounted(); return <p>Writable ordinary workflow</p>; }
  const old = render(<ServingGate><Ordinary /></ServingGate>);
  old.unmount();
  render(<ServingGate><Ordinary /></ServingGate>);
  await screen.findByRole("region", { name: "Read-only synthetic demo" });
  await act(async () => finishOld(new Response(JSON.stringify(local))));
  expect(mounted).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Backtest" })).toBeDisabled();
  expect(screen.queryByText("Writable ordinary workflow")).not.toBeInTheDocument();
});

it("preserves edited ordinary form state and settings for the negotiated page lifecycle", async () => {
  localStorage.setItem("quantlab.settings.v1", JSON.stringify({ accent_color: "violet" }));
  const before = localStorage.getItem("quantlab.settings.v1");
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(local)));
  vi.stubGlobal("fetch", fetch);
  function Ordinary() { return <input aria-label="Unsaved ordinary research" defaultValue="original" />; }
  const { rerender } = render(<ServingGate><Ordinary /></ServingGate>);
  fireEvent.change(await screen.findByRole("textbox", { name: "Unsaved ordinary research" }), { target: { value: "edited unsaved work" } });
  rerender(<ServingGate><Ordinary /></ServingGate>);
  expect(screen.getByRole("textbox", { name: "Unsaved ordinary research" })).toHaveValue("edited unsaved work");
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(localStorage.getItem("quantlab.settings.v1")).toBe(before);
});

it("disabled demo navigation and history events never request a hidden writable workflow", async () => {
  const fetch = vi.fn().mockImplementation(async (url: string) => {
    if (url === "/api/health") return new Response(JSON.stringify({ status: "ok" }));
    if (url === "/api/saved-backtests") return new Response(JSON.stringify([record("Synthetic SMA showcase")]));
    throw new Error("Unexpected request");
  });
  vi.stubGlobal("fetch", fetch);
  render(<ReadOnlyDemo capabilities={capabilities()} />);
  await screen.findByRole("button", { name: "View" });
  for (const name of ["Backtest", "CSV Backtest", "Saved Reports", "Settings"]) {
    const control = screen.getByRole("button", { name });
    expect(control).toBeDisabled(); fireEvent.click(control);
  }
  history.pushState(null, "", "/?view=backtest#run-replay=unapproved");
  act(() => window.dispatchEvent(new PopStateEvent("popstate")));
  act(() => window.dispatchEvent(new HashChangeEvent("hashchange")));
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  expect(screen.getByRole("region", { name: "Read-only synthetic demo" })).toBeVisible();
  expect(fetch.mock.calls.map(([path]) => path)).toEqual(["/api/health", "/api/saved-backtests"]);
});

it("keeps a new same-ID corpus detail when an old corpus response arrives late", async () => {
  let finishOld!: (value: Response) => void;
  const fetch = vi.fn().mockImplementation(async (url: string, options?: RequestInit) => {
    if (url === "/api/health") return new Response(JSON.stringify({ status: "ok" }));
    const corpus = (options?.headers as Record<string, string>)["X-QuantLab-Expected-Corpus"];
    if (url === "/api/saved-backtests") return new Response(JSON.stringify([record(corpus === corpusA ? "Old corpus" : "New corpus")]));
    if (url === "/api/saved-backtests/1" && corpus === corpusA) return new Promise<Response>((resolve) => { finishOld = resolve; });
    if (url === "/api/saved-backtests/1" && corpus === corpusB) return new Response(JSON.stringify(record("New corpus")));
    throw new Error("Unexpected request");
  });
  vi.stubGlobal("fetch", fetch);
  const { rerender } = render(<ReadOnlyDemo capabilities={capabilities()} />);
  fireEvent.click(await screen.findByRole("button", { name: "View" }));
  rerender(<ReadOnlyDemo capabilities={capabilities(corpusB)} />);
  await screen.findByRole("heading", { name: "New corpus" });
  await act(async () => finishOld(new Response(JSON.stringify(record("Old corpus")))));
  expect(screen.queryByRole("heading", { name: "Old corpus" })).not.toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Read-only synthetic demo" })).toHaveAttribute("data-corpus-id", corpusB);
  expect(screen.getByRole("button", { name: "Explain stored result" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Save Report" })).not.toBeInTheDocument();
});

it("same-ID corpus changes reject a late explanation and export only the displayed new corpus response", async () => {
  let finishOld!: (value: Response) => void;
  const newText = JSON.stringify(explanation(.25, "25.00%"));
  const fetch = vi.fn().mockReturnValueOnce(new Promise<Response>((resolve) => { finishOld = resolve; }))
    .mockResolvedValueOnce(new Response(newText));
  vi.stubGlobal("fetch", fetch);
  vi.stubGlobal("Blob", NodeBlob);
  const create = vi.fn((_blob: NodeBlob) => "blob:corpus");
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const { rerender } = render(<ResearchExplanationPanel id={1} corpusId={corpusA} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  rerender(<ResearchExplanationPanel id={1} corpusId={corpusB} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  await screen.findByText("The stored total return is 25.00%.");
  await act(async () => finishOld(new Response(JSON.stringify(explanation(-.12, "-12.00%")))));
  expect(screen.queryByText("The stored total return is -12.00%.")).not.toBeInTheDocument();
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Download explanation JSON" }));
  expect(await create.mock.calls[0][0].text()).toBe(newText);
  expect(fetch.mock.calls.map(([, options]) => options.headers["X-QuantLab-Expected-Corpus"])).toEqual([corpusA, corpusB]);
  expect(fetch).toHaveBeenCalledTimes(2);
  vi.runAllTimers(); vi.useRealTimers();
});
