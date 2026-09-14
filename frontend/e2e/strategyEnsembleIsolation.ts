/** Test-only handshake with the actual backend reached through the UI proxy. */
export const isolationHeader = "x-quantlab-e2e-token";
export async function verifyStrategyEnsembleIsolation(
  baseURL: string | undefined,
  token: string | undefined,
  get: (url: string, options: { headers: Record<string, string>; maxRedirects: number }) => Promise<{
    ok(): boolean; json(): Promise<unknown>;
  }>,
): Promise<void> {
  if (!baseURL || !["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL).hostname)) {
    throw new Error("Strategy ensemble E2E requires a loopback frontend");
  }
  if (!token || !/^[a-f0-9]{64}$/.test(token)) {
    throw new Error("Start the disposable E2E harness and set its E2E_STRATEGY_ENSEMBLE_TOKEN");
  }
  const response = await get(new URL("/api/strategy-ensembles/e2e-isolation", baseURL).href,
    { headers: { [isolationHeader]: token }, maxRedirects: 0 });
  if (!response.ok()) throw new Error("Backend did not verify a disposable E2E database; no seeding permitted");
  const value = await response.json();
  if (!value || typeof value !== "object") throw new Error("Invalid E2E database identity proof");
  const proof = value as Record<string, unknown>;
  if (proof.kind !== "quantlab_strategy_ensemble_disposable_v1" || proof.token !== token
      || proof.database_verified !== true || typeof proof.database_identity !== "string"
      || !/^quantlab-strategy-ensemble-e2e-[a-zA-Z0-9_-]+$/.test(proof.database_identity)) {
    throw new Error("Backend database identity does not match this disposable E2E session");
  }
}
