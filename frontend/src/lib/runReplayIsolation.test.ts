import { expect, it, vi } from "vitest";
import { verifyRunReplayIsolation } from "../../e2e/runReplayIsolation";

it("refuses unequal database identities even with valid tokens", async () => {
  const token = "a".repeat(64);
  const get = vi.fn().mockResolvedValueOnce({ ok: () => true, json: async () => ({
    kind: "quantlab_strategy_ensemble_disposable_v1", token, database_verified: true,
    database_identity: "quantlab-strategy-ensemble-e2e-one" }) }).mockResolvedValueOnce({ ok: () => true, json: async () => ({
      kind: "quantlab_run_replay_disposable_v1", token, database_verified: true,
      database_identity: "quantlab-strategy-ensemble-e2e-other" }) });
  await expect(verifyRunReplayIsolation("http://localhost:3000", token, get)).rejects.toThrow("positively verified");
});
it("requires equal real-route ownership proof", async () => {
  const token = "b".repeat(64), database_identity = "quantlab-strategy-ensemble-e2e-same";
  const get = vi.fn().mockResolvedValueOnce({ ok: () => true, json: async () => ({
    kind: "quantlab_strategy_ensemble_disposable_v1", token, database_verified: true, database_identity }) })
    .mockResolvedValueOnce({ ok: () => true, json: async () => ({ kind: "quantlab_run_replay_disposable_v1", token, database_verified: true, database_identity }) });
  await expect(verifyRunReplayIsolation("http://localhost:3000", token, get)).resolves.toEqual({ database_identity });
  expect(get.mock.calls[1][0]).toBe("http://localhost:3000/api/run-replay/e2e/isolation");
});
