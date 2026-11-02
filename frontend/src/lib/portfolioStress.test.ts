import { expect, it, vi } from "vitest";
import { createRun, executeRun, type AssetShockRunCreate } from "./portfolioStress";
import { BacktestApiError } from "./api";
import { stressRun } from "@/test/fixtures/portfolioStressComposer";

const payload: AssetShockRunCreate = { name: "Explicit shock", portfolio_run_id: 11, portfolio_rebalance_id: 2,
  scenario: { scenario_definition_id: "ui_asset_shock_v1", name: "Explicit shock", scenario_type: "hypothetical_asset_shock",
    source: "user", missing_shock_policy: "unavailable", asset_shocks: { a: { value: -10, unit: "percent" } } } };

it.each([0, 2])("creates rebalance %s through the real proxy path with raw percent entries", async (rebalanceId) => {
  const result = stressRun({ status: "pending", portfolio_rebalance_id: rebalanceId });
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(result), { status: 201 }));
  vi.stubGlobal("fetch", fetch);
  const selectedPayload = { ...payload, portfolio_rebalance_id: rebalanceId };
  expect(await createRun(selectedPayload)).toEqual(result);
  expect(fetch).toHaveBeenCalledWith("/api/portfolio-stress/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(selectedPayload) });
});
it("executes the returned ID without creating an experiment", async () => {
  const result = stressRun();
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)));
  vi.stubGlobal("fetch", fetch);
  expect(await executeRun(42)).toEqual(result);
  expect(fetch).toHaveBeenCalledWith("/api/portfolio-stress/runs/42/execute", { method: "POST", headers: { "Content-Type": "application/json" }, body: '{"create_experiment":false}' });
});
it.each(["Unrecognized asset", [{ loc: ["body", "scenario", "asset_shocks"], msg: "Invalid shock" }]])("retains backend validation details", async (detail) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status: 422 })));
  await expect(createRun(payload)).rejects.toThrow(typeof detail === "string" ? detail : "scenario.asset_shocks: Invalid shock");
});
it("retains transport failure identity for ambiguous writes", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  await expect(executeRun(42)).rejects.toMatchObject({ status: 0 });
});
it("does not turn HTTP-successful failed status into a transport success claim", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(stressRun({ status: "failed" })))));
  expect((await executeRun(42)).status).toBe("failed");
});
it("keeps 409 conflicts typed", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "run invalidated" }), { status: 409 })));
  await expect(executeRun(42)).rejects.toBeInstanceOf(BacktestApiError);
});
