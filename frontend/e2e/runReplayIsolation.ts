import { isolationHeader, verifyStrategyEnsembleIsolation } from "./strategyEnsembleIsolation";

export async function verifyRunReplayIsolation(baseURL: string | undefined, token: string | undefined,
  get: Parameters<typeof verifyStrategyEnsembleIsolation>[2]) {
  const original = await verifyStrategyEnsembleIsolation(baseURL, token, get);
  const response = await get(new URL("/api/run-replay/e2e/isolation", baseURL).href,
    { headers: { [isolationHeader]: token! }, maxRedirects: 0 });
  const proof = response.ok() ? await response.json() as Record<string, unknown> : null;
  if (!proof || proof.kind !== "quantlab_run_replay_disposable_v1" || proof.token !== token ||
      proof.database_verified !== true || proof.database_identity !== original.database_identity)
    throw new Error("Replay backend does not use the positively verified disposable database; no mutations permitted");
  return original;
}
