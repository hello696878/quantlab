import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import PortfolioDiagnosticsPanel from "./PortfolioDiagnosticsPanel";
import ServingGate from "./ServingGate";
import * as api from "@/lib/portfolioDiagnostics";
import * as draftHelpers from "@/lib/portfolioDiagnosticsComposer";

vi.mock("@/lib/portfolioDiagnostics", async (original) => ({ ...await original<typeof api>(),
  listRuns: vi.fn(), getRun: vi.fn(), getLabSummary: vi.fn(), getRebalances: vi.fn(), createRun: vi.fn(), executeRun: vi.fn() }));
vi.mock("./ReadOnlyDemo", () => ({ default: () => <p>Approved demo browsing</p> }));

it.each(["pending", "failed", "unknown", "read_only_demo"])("never mounts Diagnostics or Composer in %s capability state", async (mode) => {
  const projection = vi.spyOn(draftHelpers, "preparePortfolioReuse");
  const value = mode === "read_only_demo"
    ? { schema: "serving_capabilities_v1", mode, policy: "read_only_demo_v1", corpus_id: "a".repeat(64), synthetic: true, capabilities: ["browse_saved_sma", "explain_saved_sma"] }
    : { mode };
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => mode === "pending" ? new Promise(() => {})
    : mode === "failed" ? Promise.reject(new Error("offline")) : Promise.resolve(new Response(JSON.stringify(value)))));
  render(<ServingGate><PortfolioDiagnosticsPanel /></ServingGate>); await act(async () => {});
  if (mode === "read_only_demo") expect(await screen.findByText("Approved demo browsing")).toBeVisible();
  if (mode === "failed" || mode === "unknown") expect(await screen.findByRole("alert")).toBeVisible();
  expect(screen.queryByRole("button", { name: "New portfolio run" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Use return data in a new portfolio" })).not.toBeInTheDocument();
  expect(projection).not.toHaveBeenCalled();
  for (const method of [api.listRuns, api.getRun, api.getLabSummary, api.getRebalances, api.createRun, api.executeRun]) expect(method).not.toHaveBeenCalled();
});
