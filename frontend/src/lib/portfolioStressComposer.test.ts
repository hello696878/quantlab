import { describe, expect, it } from "vitest";
import { BacktestApiError } from "./api";
import { buildAssetShockRun, creationOutcomeUnknown, shockText, type ComposerDraft } from "./portfolioStressComposer";
import { portfolio, rebalances } from "@/test/fixtures/portfolioStressComposer";

const source = { portfolio, rebalance: rebalances[0] };
const draft: ComposerDraft = { name: " My assumptions ", shocks: { a: "-10", b: " " }, missingPolicy: "unavailable", notional: "" };

describe("asset shock Composer payload", () => {
  it("pins explicit non-final IDs and percent units without response-only fields", () => {
    expect(buildAssetShockRun(source, draft)).toEqual({ name: "My assumptions", portfolio_run_id: 11, portfolio_rebalance_id: 2,
      scenario: { scenario_definition_id: "ui_asset_shock_v1", name: "My assumptions", scenario_type: "hypothetical_asset_shock",
        source: "user", missing_shock_policy: "unavailable", asset_shocks: { a: { value: -10, unit: "percent" } } } });
  });
  it("distinguishes blank, explicit zero, and both missing policies", () => {
    const payload = buildAssetShockRun(source, { ...draft, shocks: { a: "0.", b: "0" }, missingPolicy: "zero", notional: "1000" });
    expect(payload.scenario.asset_shocks).toEqual({ a: { value: 0, unit: "percent" }, b: { value: 0, unit: "percent" } });
    expect(payload.scenario.missing_shock_policy).toBe("zero");
    expect(payload.notional).toBe(1000);
  });
  it.each(["constructor", "toString", "__proto__"])("treats an omitted %s shock as blank and retains its explicit zero", (assetId) => {
    const specialSource = {
      portfolio: { ...portfolio, universe: { ...portfolio.universe,
        assets: [...portfolio.universe.assets, { ...portfolio.universe.assets[0], asset_id: assetId, name: assetId, group: null }] } },
      rebalance: { ...source.rebalance, weights: { a: 0.5, b: 0.4, [assetId]: 0.1 } },
    };
    expect(shockText(draft.shocks, assetId)).toBe("");
    const omitted = buildAssetShockRun(specialSource, draft);
    expect(Object.hasOwn(omitted.scenario.asset_shocks, assetId)).toBe(false);
    expect(omitted.scenario.missing_shock_policy).toBe("unavailable");
    expect(Object.hasOwn(buildAssetShockRun(specialSource, { ...draft, missingPolicy: "zero" })
      .scenario.asset_shocks, assetId)).toBe(false);
    const supplied = { ...draft.shocks, [assetId]: "0" };
    expect(shockText(supplied, assetId)).toBe("0");
    expect(buildAssetShockRun(specialSource, { ...draft, shocks: supplied }).scenario.asset_shocks[assetId])
      .toEqual({ value: 0, unit: "percent" });
  });
  it("accepts the stored zero-based rebalance ID without substituting final weights", () => {
    expect(buildAssetShockRun({ ...source, rebalance: { ...source.rebalance, rebalance_id: 0 } }, draft)
      .portfolio_rebalance_id).toBe(0);
    expect(() => buildAssetShockRun({ ...source, rebalance: { ...source.rebalance, rebalance_id: -1 } }, draft)).toThrow(/Select/);
  });
  it.each(["-100", "+100", "-.5", "1e1"])("accepts valid percent token %s", (a) => {
    expect(buildAssetShockRun(source, { ...draft, shocks: { a } }).scenario.asset_shocks.a.value).toBe(Number(a));
  });
  it.each(["-100.01", "100.01", "NaN", "Infinity", "1e999", "10abc", "0x10", "-", "."])("rejects invalid percent token %s", (a) => {
    expect(() => buildAssetShockRun(source, { ...draft, shocks: { a } })).toThrow();
  });
  it.each(["0", "-1", "Infinity", "not a number"])("rejects notional %s", (notional) => {
    expect(() => buildAssetShockRun(source, { ...draft, notional })).toThrow(/Notional/);
  });
  it("requires a current completed source, explicit shock and bounded trimmed name", () => {
    expect(() => buildAssetShockRun(null, draft)).toThrow(/Select/);
    expect(() => buildAssetShockRun({ ...source, portfolio: { ...portfolio, status: "failed" } }, draft)).toThrow(/Select/);
    expect(() => buildAssetShockRun({ ...source, rebalance: { ...source.rebalance, weights: {} } }, draft)).toThrow(/Select/);
    expect(() => buildAssetShockRun(source, { ...draft, shocks: { a: "", b: " " } })).toThrow(/at least one/);
    expect(() => buildAssetShockRun(source, { ...draft, shocks: { outsider: "0" } })).toThrow(/outside/);
    expect(() => buildAssetShockRun(source, { ...draft, name: " " })).toThrow(/Name/);
    expect(() => buildAssetShockRun(source, { ...draft, name: "x".repeat(201) })).toThrow(/Name/);
  });
  it("treats lost/5xx creation responses as ambiguous, not as proven rollbacks", () => {
    expect(creationOutcomeUnknown(new BacktestApiError(0, "offline"))).toBe(true);
    expect(creationOutcomeUnknown(new BacktestApiError(500, "error"))).toBe(true);
    expect(creationOutcomeUnknown(new SyntaxError("bad response"))).toBe(true);
    expect(creationOutcomeUnknown(new BacktestApiError(422, "invalid"))).toBe(false);
  });
});
