import { isolationHeader, verifyStrategyEnsembleIsolation } from "./strategyEnsembleIsolation";

export async function verifyMLLifecycleIsolation(
  baseURL: string | undefined, token: string | undefined,
  get: Parameters<typeof verifyStrategyEnsembleIsolation>[2],
): Promise<void> {
  const strategyProof = await verifyStrategyEnsembleIsolation(baseURL, token, get);
  const response = await get(new URL("/api/ml-lifecycles/e2e/isolation", baseURL).href,
    { headers: { [isolationHeader]: token! }, maxRedirects: 0 });
  if (!response.ok()) throw new Error("Phase 65 disposable database guard is unavailable; no mutation permitted");
  const value: unknown = await response.json();
  if (!value || typeof value !== "object") throw new Error("Phase 65 serving database identity was not verified");
  const proof = value as Record<string, unknown>;
  if (proof.kind !== "quantlab_ml_lifecycle_disposable_v1" || proof.token !== token || proof.database_verified !== true
      || proof.database_identity !== strategyProof.database_identity) {
    throw new Error("Phase 65 serving database identity was not verified");
  }
}
