import { expect, it, vi } from "vitest";
import { verifyMLLifecycleIsolation } from "../../e2e/mlLifecycleIsolation";

const token = "c".repeat(64);
const baseProof = { kind: "quantlab_strategy_ensemble_disposable_v1", token,
  database_identity: "quantlab-strategy-ensemble-e2e-owned", database_verified: true };

it("requires both the physical DB proof and Phase 65 request guard", async () => {
  const get = vi.fn().mockResolvedValueOnce({ ok: () => true, json: async () => baseProof })
    .mockResolvedValueOnce({ ok: () => true, json: async () => ({ ...baseProof, kind: "quantlab_ml_lifecycle_disposable_v1" }) });
  await verifyMLLifecycleIsolation("http://localhost:3100", token, get);
  expect(get).toHaveBeenLastCalledWith("http://localhost:3100/api/ml-lifecycles/e2e/isolation", { headers: { "x-quantlab-e2e-token": token }, maxRedirects: 0 });
});

it("refuses an older harness that does not guard lifecycle mutations", async () => {
  const get = vi.fn().mockResolvedValue({ ok: () => true, json: async () => baseProof });
  await expect(verifyMLLifecycleIsolation("http://localhost:3100", token, get)).rejects.toThrow("not verified");
});

it("refuses a missing token before network access", async () => {
  const get = vi.fn();
  await expect(verifyMLLifecycleIsolation("http://localhost:3100", undefined, get)).rejects.toThrow();
  expect(get).not.toHaveBeenCalled();
});

it.each([null, {}, { ...baseProof, kind: "quantlab_ml_lifecycle_disposable_v1", database_identity: undefined },
  { ...baseProof, kind: "quantlab_ml_lifecycle_disposable_v1", database_identity: "quantlab-strategy-ensemble-e2e-other" },
  { ...baseProof, kind: "quantlab_ml_lifecycle_disposable_v1", database_verified: false },
  { ...baseProof, kind: "quantlab_ml_lifecycle_disposable_v1", token: "d".repeat(64) }])(
  "refuses malformed or different lifecycle database proof before permitting mutation", async (proof) => {
    const get = vi.fn().mockResolvedValueOnce({ ok: () => true, json: async () => baseProof })
      .mockResolvedValueOnce({ ok: () => true, json: async () => proof });
    await expect(verifyMLLifecycleIsolation("http://localhost:3100", token, get)).rejects.toThrow("not verified");
  });

it("does not request lifecycle proof if the strategy database handshake fails", async () => {
  const get = vi.fn().mockResolvedValue({ ok: () => false });
  await expect(verifyMLLifecycleIsolation("http://localhost:3100", token, get)).rejects.toThrow();
  expect(get).toHaveBeenCalledTimes(1);
});
