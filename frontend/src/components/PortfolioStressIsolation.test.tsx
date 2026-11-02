import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import PortfolioStressComposer from "./PortfolioStressComposer";
import ServingGate from "./ServingGate";
import * as portfolios from "@/lib/portfolioDiagnostics";
import * as stress from "@/lib/portfolioStress";

vi.mock("@/lib/portfolioDiagnostics", async (original) => ({ ...await original<typeof portfolios>(),
  listRuns: vi.fn(), getRun: vi.fn(), getRebalances: vi.fn() }));
vi.mock("@/lib/portfolioStress", async (original) => ({ ...await original<typeof stress>(), createRun: vi.fn(), executeRun: vi.fn() }));
vi.mock("./ReadOnlyDemo", () => ({ default: () => <p>Approved demo browsing</p> }));

it.each(["pending", "failed", "unknown", "read_only_demo"])("never mounts Composer helpers in %s capability state", async (mode) => {
  const value = mode === "read_only_demo"
    ? { schema: "serving_capabilities_v1", mode, policy: "read_only_demo_v1", corpus_id: "a".repeat(64), synthetic: true, capabilities: ["browse_saved_sma", "explain_saved_sma"] }
    : { mode };
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => mode === "pending" ? new Promise(() => {})
    : mode === "failed" ? Promise.reject(new Error("offline")) : Promise.resolve(new Response(JSON.stringify(value)))));
  render(<ServingGate><PortfolioStressComposer onBack={vi.fn()} onOpen={vi.fn()} /></ServingGate>);
  await act(async () => {});
  if (mode === "read_only_demo") expect(await screen.findByText("Approved demo browsing")).toBeVisible();
  if (mode === "failed" || mode === "unknown") expect(await screen.findByRole("alert")).toBeVisible();
  expect(screen.queryByRole("heading", { name: "New stress run" })).not.toBeInTheDocument();
  for (const method of [portfolios.listRuns, portfolios.getRun, portfolios.getRebalances, stress.createRun, stress.executeRun]) expect(method).not.toHaveBeenCalled();
});
