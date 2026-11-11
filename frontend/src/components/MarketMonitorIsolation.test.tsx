import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import ServingGate from "./ServingGate";
import MarketMonitorPanel from "./MarketMonitorPanel";
vi.mock("./ReadOnlyDemo", () => ({ default: () => <p>Approved demo only</p> }));
it.each(["pending", "error", "unknown", "read_only_demo"])("never mounts Monitor in %s mode", async (mode) => {
  const fetch = vi.fn((_url: string) => mode === "pending" ? new Promise<Response>(() => {}) : mode === "error" ? Promise.reject(new Error("offline")) : Promise.resolve(new Response(JSON.stringify(mode === "read_only_demo"
    ? { schema: "serving_capabilities_v1", mode, policy: "read_only_demo_v1", corpus_id: "a".repeat(64), synthetic: true, capabilities: ["browse_saved_sma", "explain_saved_sma"] }
    : { mode }))));
  vi.stubGlobal("fetch", fetch);
  render(<ServingGate><MarketMonitorPanel /></ServingGate>);
  if (mode === "read_only_demo") await screen.findByText("Approved demo only");
  if (mode === "error" || mode === "unknown") await screen.findByRole("alert");
  expect(screen.queryByRole("region", { name: "Personal watchlist" })).not.toBeInTheDocument();
  expect(fetch.mock.calls.every(([url]) => url === "/api/capabilities")).toBe(true);
});
