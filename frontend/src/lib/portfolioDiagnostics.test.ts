import { expect, it, vi } from "vitest";
import { createRun, executeRun } from "./portfolioDiagnostics";
import { buildPortfolioRun, parsePortfolioReturns } from "./portfolioDiagnosticsComposer";
import { constructionInput, returnInput } from "@/test/fixtures/portfolioDiagnosticsComposer";

it("posts validated source data and explicitly disables experiment creation on execute", async () => {
  const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ id: 51 })));
  vi.stubGlobal("fetch", fetch);
  const payload = buildPortfolioRun(parsePortfolioReturns(JSON.stringify(returnInput())), "Source", { a: "70", b: "30" }, "20");
  await createRun(payload);
  await executeRun(51);
  expect(fetch.mock.calls[0]).toEqual(["/api/portfolio-diagnostics/runs", { headers: { "Content-Type": "application/json" }, method: "POST", body: JSON.stringify(payload) }]);
  expect(fetch.mock.calls[1]).toEqual(["/api/portfolio-diagnostics/runs/51/execute", { headers: { "Content-Type": "application/json" }, method: "POST", body: '{"create_experiment":false}' }]);
});

it("preserves useful public-schema validation errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ["body", "name"], msg: "Too long" }] }), { status: 422 })));
  await expect(executeRun(51)).rejects.toThrow("body.name: Too long");
});

it.each(["equal_weight", "inverse_volatility"] as const)("serializes the real %s request without stale manual fields", async (method) => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 51 })));
  vi.stubGlobal("fetch", fetch);
  const data = parsePortfolioReturns(JSON.stringify(constructionInput()));
  await createRun(buildPortfolioRun(data, "Derived", { a: "70", b: "30" }, "20", method));
  const [url, options] = fetch.mock.calls[0];
  expect(url).toBe("/api/portfolio-diagnostics/runs");
  const body = JSON.parse(options.body);
  expect(body).toMatchObject({ ...data, method, normalization: "sum_to_one", estimation: { mode: "rolling", lookback: 20, lag: 1 } });
  for (const key of ["weights", "weight_provenance", "volatility_floor"]) expect(Object.hasOwn(body, key)).toBe(false);
});
