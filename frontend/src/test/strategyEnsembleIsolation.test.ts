import { describe, expect, it, vi } from "vitest";
import { verifyStrategyEnsembleIsolation } from "../../e2e/strategyEnsembleIsolation";

const token = "a".repeat(64);
const proof = { kind: "quantlab_strategy_ensemble_disposable_v1", token,
  database_identity: "quantlab-strategy-ensemble-e2e-test123", database_verified: true };
const response = (value: unknown, ok = true) => ({ ok: () => ok, json: async () => value });

describe("Strategy ensemble E2E database isolation", () => {
  it.each([undefined, "1", "b".repeat(63)])("does not contact a service without a session token (%s)", async (value) => {
    const get = vi.fn();
    await expect(verifyStrategyEnsembleIsolation("http://localhost:3100", value, get)).rejects.toThrow(/disposable E2E harness/);
    expect(get).not.toHaveBeenCalled();
  });
  it("rejects a non-loopback destination before any request", async () => {
    const get = vi.fn();
    await expect(verifyStrategyEnsembleIsolation("https://example.com", token, get)).rejects.toThrow(/loopback/);
    expect(get).not.toHaveBeenCalled();
  });
  it.each([response({}, false), response({}), response({ ...proof, token: "b".repeat(64) }),
    response({ ...proof, database_verified: false }), response({ ...proof, database_identity: "quantlab.db" })])(
    "fails closed on an absent, mismatched or unverified service identity", async (reply) => {
      await expect(verifyStrategyEnsembleIsolation("http://localhost:3100", token, async () => reply)).rejects.toThrow();
    });
  it("verifies the same frontend proxy with redirects disabled", async () => {
    const get = vi.fn().mockResolvedValue(response(proof));
    await verifyStrategyEnsembleIsolation("http://localhost:3100", token, get);
    expect(get).toHaveBeenCalledWith("http://localhost:3100/api/strategy-ensembles/e2e-isolation", {
      headers: { "x-quantlab-e2e-token": token }, maxRedirects: 0,
    });
  });
});
