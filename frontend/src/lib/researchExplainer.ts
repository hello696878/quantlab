import { BacktestApiError } from "./api";
import { corpusPrecondition } from "./servingCapabilities";

export interface ExplanationFact {
  id: string; source: "saved" | "context"; path: string;
  state: "available" | "missing" | "null";
  value: string | number | null; unit: string; rule: string; display: string | null;
}
export interface ResearchExplanation {
  schema_version: "research_explanation_v1";
  adapter_version: "saved_sma_v1"; template_version: "saved_sma_en_v1";
  policy_version: "stored_facts_policy_v1"; locale: "en-US";
  identity: {
    source_kind: "saved_backtest"; source_schema: string; saved_backtest_id: number;
    created_at: string; material_hash: string; trust: "legacy_unverified" | "recorded_hashes_match";
    context: { id: number; schema: string; snapshot_hash: string; result_hash: string;
      input_hash: string; execution_hash: string; config_hash_full: string } | null;
  };
  evidence: Record<string, unknown>;
  facts: ExplanationFact[];
  statements: { template_id: string; text: string; facts: string[]; policy_id: string | null }[];
  fingerprint: string;
}

// Preserve the validated wire document: reserializing JavaScript numbers loses
// JSON distinctions such as Python 0.0 versus 0 and negative zero.
const retainedDocuments = new WeakMap<ResearchExplanation, { text: string; snapshot: ResearchExplanation }>();

function sameJsonValue(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (!left || !right || typeof left !== "object" || typeof right !== "object" || Array.isArray(left) !== Array.isArray(right)) return false;
  if (Array.isArray(left) && Array.isArray(right) && left.length !== right.length) return false;
  const keys = Object.keys(left);
  if (keys.length !== Object.keys(right).length) return false;
  return keys.every((key) => Object.prototype.hasOwnProperty.call(right, key) &&
    sameJsonValue((left as Record<string, unknown>)[key], (right as Record<string, unknown>)[key]));
}

export function resolveFact(bundle: ResearchExplanation, fact: ExplanationFact): { present: boolean; value: unknown } {
  if (typeof fact.path !== "string" || !fact.path.startsWith("/")) throw new Error("Invalid evidence reference");
  const parts = fact.path.slice(1).split("/");
  if (parts.some((part) => /~(?![01])/.test(part))) throw new Error("Invalid evidence reference");
  let value: unknown = bundle.evidence[fact.source];
  for (const part of parts) {
    const key = part.replace(/~1/g, "/").replace(/~0/g, "~");
    if (Array.isArray(value) && (!/^(0|[1-9][0-9]*)$/.test(key) || key.length > 8 || Number(key) >= value.length)) {
      return { present: false, value: null };
    }
    if (!value || typeof value !== "object" || !Object.prototype.hasOwnProperty.call(value, key)) return { present: false, value: null };
    value = (value as Record<string, unknown>)[key];
  }
  return { present: true, value };
}

export function checkExplanation(bundle: ResearchExplanation, id: number): ResearchExplanation {
  if (bundle.schema_version !== "research_explanation_v1" || bundle.adapter_version !== "saved_sma_v1" ||
      bundle.template_version !== "saved_sma_en_v1" || bundle.policy_version !== "stored_facts_policy_v1" ||
      bundle.locale !== "en-US" || bundle.identity.source_kind !== "saved_backtest" || bundle.identity.saved_backtest_id !== id ||
      !/^[0-9a-f]{64}$/.test(bundle.fingerprint) || bundle.facts.length > 20 || bundle.statements.length > 40) throw new Error("Unsupported explanation response");
  const ids = new Set<string>();
  for (const fact of bundle.facts) {
    const bound = resolveFact(bundle, fact);
    if (ids.has(fact.id) || bound.present !== (fact.state !== "missing") || bound.value !== fact.value ||
        fact.state === "available" && (fact.display === null || typeof fact.value === "boolean" || typeof fact.value === "number" && !Number.isFinite(fact.value))) throw new Error("Invalid explanation binding");
    ids.add(fact.id);
  }
  for (const statement of bundle.statements) {
    if (statement.text.length > 500 || !statement.facts.length && statement.policy_id !== bundle.policy_version || statement.facts.some((key) => !ids.has(key))) throw new Error("Unresolved explanation statement");
  }
  return bundle;
}

export async function explainSavedBacktest(id: number, expected?: string, corpusId?: string): Promise<ResearchExplanation> {
  const response = await fetch(`/api/research-explainer/saved-backtests/${id}${expected ? `?expected=${encodeURIComponent(expected)}` : ""}`, { cache: "no-store", ...corpusPrecondition(corpusId) });
  const text = await response.text();
  if (text.length > 64 * 1024) throw new Error("Explanation exceeds supported size");
  let result;
  try { result = JSON.parse(text); } catch { throw new Error("Stored explanation service is unavailable"); }
  if (!response.ok) throw new BacktestApiError(response.status, typeof result?.detail === "string" ? result.detail : "Stored explanation is unavailable");
  const bundle = checkExplanation(result, id);
  retainedDocuments.set(bundle, { text, snapshot: structuredClone(bundle) });
  return bundle;
}

export function downloadExplanation(bundle: ResearchExplanation): void {
  checkExplanation(bundle, bundle.identity.saved_backtest_id);
  const retained = retainedDocuments.get(bundle);
  if (!retained || !sameJsonValue(bundle, retained.snapshot)) throw new Error("Pinned explanation changed or has no retained response");
  const url = URL.createObjectURL(new Blob([retained.text], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = `quantlab-explanation-${bundle.identity.saved_backtest_id}.json`;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
