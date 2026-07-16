/**
 * API client + types for the Research Experiment Registry (Phase 48.0).
 *
 * All requests go to /api/experiment-registry/* which Next.js rewrites to the
 * FastAPI backend.  Errors reuse the shared BacktestApiError / classifyApiError
 * machinery so the panel can branch on offline / validation / not-found the same
 * way every other view does.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/experiment-registry";

// ---------------------------------------------------------------------------
// Types (mirror the backend Pydantic response models)
// ---------------------------------------------------------------------------

export type ExperimentStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "invalidated";

export type ReproducibilityStatus =
  | "unknown"
  | "reproducible"
  | "partially_reproducible"
  | "not_reproducible";

export interface ExperimentSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  module: string;
  experiment_type: string;
  status: ExperimentStatus;
  reproducibility_status: ReproducibilityStatus;
  duration_ms: number | null;
  dataset_name: string | null;
  dataset_version: string | null;
  dataset_fingerprint: string | null;
  random_seed: number | null;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  is_baseline: boolean;
  git_commit: string | null;
  app_version: string | null;
  tags: string[];
  metrics: Record<string, unknown>;
  parent_experiment_id: number | null;
}

export interface ExperimentFull extends ExperimentSummary {
  description: string;
  started_at: string | null;
  completed_at: string | null;
  parameters: Record<string, unknown>;
  provenance: Record<string, unknown>;
  notes: string;
  error_message: string | null;
}

export interface ExperimentListResponse {
  items: ExperimentSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface RegistrySummary {
  total: number;
  by_status: Record<string, number>;
  by_reproducibility: Record<string, number>;
  baselines: number;
  modules_represented: number;
  modules: string[];
  experiment_types: string[];
  tags: string[];
}

export interface ReproducibilityCheck {
  name: string;
  state: string;
}

export interface ReproducibilityAssessment {
  status: ReproducibilityStatus;
  reference_id: number | null;
  summary: string;
  checks: ReproducibilityCheck[];
}

export interface ComparisonEntry {
  key: string;
  state: "same" | "changed" | "only_in_a" | "only_in_b";
  a: unknown;
  b: unknown;
  abs_diff: number | null;
  pct_diff: number | null;
}

export interface ComparisonResponse {
  a_id: number;
  b_id: number;
  groups: Record<string, ComparisonEntry[]>;
  summary: Record<string, Record<string, number>>;
  fingerprint_match: Record<string, boolean>;
}

export interface ExportResponse {
  schema_version: string;
  exported_at: string;
  filters: Record<string, unknown>;
  count: number;
  experiments: ExperimentFull[];
}

export interface DemoSeedResponse {
  created: number;
  skipped: number;
  total: number;
  experiment_ids: number[];
}

export interface ExperimentFilters {
  module?: string;
  experiment_type?: string;
  status?: string;
  reproducibility_status?: string;
  baseline?: boolean;
  tag?: string;
  query?: string;
  created_from?: string;
  created_to?: string;
  configuration_fingerprint?: string;
  dataset_fingerprint?: string;
}

export interface ListParams extends ExperimentFilters {
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

// ---------------------------------------------------------------------------
// Fetch helper (shared error semantics)
// ---------------------------------------------------------------------------

function backendUnavailableMessage(status: number): string {
  return (
    `Backend request failed (HTTP ${status}). ` +
    "Make sure the FastAPI backend is running at BACKEND_URL, " +
    "or http://localhost:8000 by default."
  );
}

function formatDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => {
        if (!d || typeof d !== "object") return null;
        const item = d as { loc?: unknown[]; msg?: unknown };
        if (typeof item.msg !== "string") return null;
        const field =
          Array.isArray(item.loc) && item.loc.length > 0
            ? String(item.loc[item.loc.length - 1])
            : null;
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .filter((m): m is string => Boolean(m));
    if (msgs.length > 0) return msgs.join("; ");
  }
  return fallback;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new BacktestApiError(0, backendUnavailableMessage(0));
  }
  if (!res.ok) {
    let message =
      res.status >= 500 ? backendUnavailableMessage(res.status) : `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = formatDetail(body?.detail, message);
    } catch {
      // keep the HTTP status message
    }
    throw new BacktestApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function toQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export function getRegistrySummary(): Promise<RegistrySummary> {
  return request<RegistrySummary>("/summary");
}

export function listExperiments(params: ListParams = {}): Promise<ExperimentListResponse> {
  return request<ExperimentListResponse>(`/experiments${toQuery(params as Record<string, unknown>)}`);
}

export function getExperiment(id: number): Promise<ExperimentFull> {
  return request<ExperimentFull>(`/experiments/${id}`);
}

export function updateExperiment(
  id: number,
  body: { name?: string; description?: string; notes?: string; tags?: string[] },
): Promise<ExperimentFull> {
  return request<ExperimentFull>(`/experiments/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function markBaseline(id: number): Promise<ExperimentFull> {
  return request<ExperimentFull>(`/experiments/${id}/mark-baseline`, { method: "POST" });
}

export function invalidateExperiment(id: number): Promise<ExperimentFull> {
  return request<ExperimentFull>(`/experiments/${id}/invalidate`, { method: "POST" });
}

export function deleteExperiment(id: number): Promise<{ deleted: boolean; id: number }> {
  return request<{ deleted: boolean; id: number }>(`/experiments/${id}`, { method: "DELETE" });
}

export function getReproducibility(id: number): Promise<ReproducibilityAssessment> {
  return request<ReproducibilityAssessment>(`/experiments/${id}/reproducibility`);
}

export function compareExperiments(a: number, b: number): Promise<ComparisonResponse> {
  return request<ComparisonResponse>(`/compare?a=${a}&b=${b}`);
}

export function exportExperiments(filters: ExperimentFilters = {}): Promise<ExportResponse> {
  return request<ExportResponse>(`/export${toQuery(filters as Record<string, unknown>)}`);
}

export function seedDemoRegistry(): Promise<DemoSeedResponse> {
  return request<DemoSeedResponse>("/demo-seed", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

export const STATUS_LABELS: Record<ExperimentStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  invalidated: "Invalidated",
};

export const REPRO_LABELS: Record<ReproducibilityStatus, string> = {
  unknown: "Unknown",
  reproducible: "Reproducible",
  partially_reproducible: "Partial",
  not_reproducible: "Not reproducible",
};

export function shortFingerprint(value: string | null | undefined): string {
  if (!value) return "—";
  return value.slice(0, 12);
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 19);
}

/** A single readable metric preview ("sharpe 1.50"), deterministic by key. */
export function metricPreview(metrics: Record<string, unknown>): string {
  const keys = Object.keys(metrics).sort();
  if (keys.length === 0) return "—";
  const key = keys[0];
  const value = metrics[key];
  const shown = typeof value === "number" ? formatNumber(value) : String(value);
  const suffix = keys.length > 1 ? ` +${keys.length - 1}` : "";
  return `${key} ${shown}${suffix}`;
}

export function formatNumber(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return String(value);
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(4).replace(/\.?0+$/, "");
}
