export interface ServingCapabilities {
  schema: "serving_capabilities_v1";
  mode: "local" | "read_only_demo";
  policy: "local_v1" | "read_only_demo_v1";
  corpus_id: string | null;
  synthetic: boolean;
  capabilities: string[];
}

export function corpusPrecondition(corpusId?: string): RequestInit {
  if (corpusId === undefined) return {};
  if (!/^[0-9a-f]{64}$/.test(corpusId)) throw new Error("Demo corpus identity unavailable");
  return { cache: "no-store", headers: { "X-QuantLab-Expected-Corpus": corpusId } };
}

export function checkCapabilities(value: unknown): ServingCapabilities {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Capabilities unavailable");
  const v = value as Record<string, unknown>;
  const keys = ["schema", "mode", "policy", "corpus_id", "synthetic", "capabilities"];
  if (Object.keys(v).length !== keys.length || keys.some((key) => !(key in v)) || v.schema !== "serving_capabilities_v1") {
    throw new Error("Unsupported capability contract");
  }
  const demo = v.mode === "read_only_demo";
  if ((!demo && v.mode !== "local") || v.policy !== (demo ? "read_only_demo_v1" : "local_v1") ||
      v.synthetic !== demo || (demo ? typeof v.corpus_id !== "string" || !/^[0-9a-f]{64}$/.test(v.corpus_id) : v.corpus_id !== null) ||
      JSON.stringify(v.capabilities) !== JSON.stringify(demo ? ["browse_saved_sma", "explain_saved_sma"] : ["local_research"])) {
    throw new Error("Capabilities could not be verified");
  }
  return value as ServingCapabilities;
}

export async function loadCapabilities(signal: AbortSignal): Promise<ServingCapabilities> {
  const response = await fetch("/api/capabilities", { cache: "no-store", signal });
  if (!response.ok) throw new Error("Backend capabilities unavailable");
  const text = await response.text();
  if (text.length > 2048) throw new Error("Capabilities exceed supported bounds");
  const value = checkCapabilities(JSON.parse(text));
  const expected = process.env.NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE;
  if (expected !== undefined && expected !== "local" && expected !== "read_only_demo") throw new Error("Invalid frontend mode configuration");
  if (expected !== undefined && expected !== value.mode) throw new Error("Frontend/backend serving mode mismatch");
  return value;
}
