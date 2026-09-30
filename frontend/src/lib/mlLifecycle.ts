import { BacktestApiError } from "@/lib/api";

export type Adapter = "validation" | "calibration" | "features" | "costs" | "decay";
export interface Summary {
  id: number; name: string; created_at: string; lifecycle_hash: string; dataset_version_id: number;
  stored_status: "stored"; processing_status: "idle" | "running" | "failed";
  completeness: "complete" | "incomplete"; integrity: "intact" | "changed"; validation_state: string;
}
export interface Listing { items: Summary[]; total: number; page: number; page_size: number }
export interface Run extends Summary {
  dataset_content_hash: string; dataset_manifest_hash: string;
  integrity_messages: string[]; identities: Record<string, string | null>;
  links: { adapter: Adapter; destination_id: number | null; status: string; content_hash: string | null;
    error: string | null; integrity: string; workspace: string }[];
  snapshot: {
    schema_version: 1; origin: string; source_environment: unknown; inspection_environment?: unknown;
    unavailable: string[]; source: unknown; feature_order?: string[]; specs?: unknown;
    models?: { hash: string; role: string; train_run_hash: string; train_ids: string[];
      training_cutoff: string; feature_order: string[]; parameters: unknown; spec: unknown }[];
    splits?: { hash: string; role: string; membership: Record<"train" | "test" | "purged" | "embargoed", string[]>; audit: unknown }[];
    calibration?: { hash: string; method: string; fit_ids: string[]; threshold: number; score_role: string; meaning: string };
    predictions?: { sample_id: string; model_hash: string; role: string; raw_probability: number; calibrated_probability?: number }[];
    evaluation?: { role: string; metrics: Record<string, number | null>; policy: unknown; periods: unknown; signals: unknown };
    samples?: unknown[];
  };
}
export interface Comparison { schema_version: number; note: string; rows: { field: string; a: unknown; b: unknown }[]; metrics: unknown[] }

async function request<T>(path: string, post = false): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);
  try {
    let response: Response;
    try {
      response = await fetch(`/api/ml-lifecycles${path}`, { method: post ? "POST" : "GET", cache: "no-store", signal: controller.signal });
    } catch {
      throw new BacktestApiError(0, "Local backend unavailable or request timed out. Stored research remains in SQLite.");
    }
    if (!response.ok) {
      let message = response.status >= 500 ? "Local backend unavailable. Please retry." : `Request refused (HTTP ${response.status}).`;
      try {
        const body = await response.json();
        if (response.status < 500 && typeof body.detail === "string") message = body.detail;
      } catch { /* Keep the safe proxy fallback. */ }
      throw new BacktestApiError(response.status, message);
    }
    return await response.json() as T;
  } finally { clearTimeout(timeout); }
}

export const listRuns = (page: number, completeness: string, integrity: string) => {
  const query = new URLSearchParams({ page: String(page), page_size: "20" });
  if (completeness) query.set("completeness", completeness);
  if (integrity) query.set("integrity", integrity);
  return request<Listing>(`?${query}`);
};
export const getRun = (id: number) => request<Run>(`/${id}`);
export const loadDemo = () => request<Run>("/demo", true);
export const compareRuns = (a: number, b: number) => request<Comparison>(`/compare?a=${a}&b=${b}`);
export const exportRun = (id: number) => request<unknown>(`/${id}/export`);
export const linkedRecord = (id: number, adapter: Adapter) => request<unknown>(`/${id}/links/${adapter}`);
