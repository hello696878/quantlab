/**
 * API client + types for the Purged CV / Embargo / CPCV Model Validation Lab
 * (Phase 50.0).  Requests go to /api/model-validation/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/model-validation";

export type Method = "standard_kfold" | "walk_forward" | "purged_kfold" | "cpcv";
export type RunStatus = "pending" | "completed" | "failed" | "invalidated";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  method: Method;
  status: RunStatus;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  sample_count: number;
  split_count: number;
  valid_split_count: number;
  invalid_split_count: number;
  leakage_clean: boolean | null;
  duration_ms: number | null;
  experiment_id: number | null;
  dataset_version_id: number | null;
  dataset_name: string | null;
  dataset_version_label: string | null;
  dataset_invalidated: boolean | null;
  random_seed: number | null;
  is_baseline: boolean;
  key_metric_preview: string | null;
  error_message: string | null;
}

export interface RunFull extends RunSummary {
  description: string;
  configuration: Record<string, unknown>;
  aggregate_metrics: Record<string, { mean?: number; median?: number; std?: number; min?: number; max?: number; valid_folds: number }>;
  leakage_summary: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  app_version: string | null;
  git_commit: string | null;
  notes: string;
  experiment_name: string | null;
  dataset_manifest_fingerprint: string | null;
  dataset_provenance_status: string | null;
  dataset_quality_status: string | null;
}

export interface SplitRecord {
  id: number;
  validation_run_id: number;
  split_index: number;
  split_label: string;
  split_fingerprint: string;
  status: "valid" | "invalid";
  train_ids: string[];
  test_ids: string[];
  purged_ids: string[];
  embargoed_ids: string[];
  diagnostics: Record<string, unknown> & {
    remaining_overlap_count?: number;
    train_count?: number;
    test_count?: number;
    purged_count?: number;
    embargoed_count?: number;
    test_prediction_range?: { min: string; max: string } | null;
    train_prediction_range?: { min: string; max: string } | null;
  };
  metrics: { metrics: Record<string, number | null>; reasons: Record<string, string> };
}

export interface RunSample {
  sample_id: string;
  prediction_time: string;
  evaluation_time: string;
  label: number | null;
  prediction: number | null;
  score: number | null;
  ret: number | null;
}

export interface RunListResponse {
  items: RunSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LabSummary {
  runs: number;
  completed: number;
  leakage_clean: number;
  invalid_splits: number;
  baselines: number;
  linked_datasets: number;
  methods: Record<string, number>;
}

export interface CompareEntry {
  kind: "same" | "changed" | "only_in_a" | "only_in_b" | "unavailable";
  field: string;
  a: unknown;
  b: unknown;
  note: string;
}

export interface RunComparison {
  a_id: number;
  b_id: number;
  groups: Record<string, CompareEntry[]>;
  fingerprint_match: Record<string, boolean>;
}

export interface RunFilters {
  method?: string;
  status?: string;
  baseline?: boolean;
  leakage_clean?: boolean;
  query?: string;
}

export interface ListParams extends RunFilters {
  page?: number;
  page_size?: number;
}

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
      // keep status message
    }
    throw new BacktestApiError(res.status, message);
  }
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

export function getLabSummary(): Promise<LabSummary> {
  return request<LabSummary>("/summary");
}

export function listRuns(params: ListParams = {}): Promise<RunListResponse> {
  return request<RunListResponse>(`/runs${toQuery(params as Record<string, unknown>)}`);
}

export function getRun(id: number): Promise<RunFull> {
  return request<RunFull>(`/runs/${id}`);
}

export function listRunSplits(id: number): Promise<SplitRecord[]> {
  return request<SplitRecord[]>(`/runs/${id}/splits`);
}

export function listRunSamples(id: number): Promise<RunSample[]> {
  return request<RunSample[]>(`/runs/${id}/samples`);
}

export function markRunBaseline(id: number): Promise<RunFull> {
  return request<RunFull>(`/runs/${id}/mark-baseline`, { method: "POST" });
}

export function compareRuns(a: number, b: number): Promise<RunComparison> {
  return request<RunComparison>(`/compare?a=${a}&b=${b}`);
}

export function exportRuns(filters: RunFilters = {}): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/export${toQuery(filters as Record<string, unknown>)}`);
}

export function seedDemoValidation(): Promise<{ created_runs: number; skipped_existing: number }> {
  return request<{ created_runs: number; skipped_existing: number }>("/demo-seed", {
    method: "POST",
  });
}

export const METHOD_LABELS: Record<string, string> = {
  standard_kfold: "Standard K-fold (reference)",
  walk_forward: "Walk-forward",
  purged_kfold: "Purged K-fold",
  cpcv: "CPCV",
};

export function shortFp(value: string | null | undefined): string {
  return value ? value.slice(0, 12) : "—";
}

export function fmtTs(iso: string | null | undefined): string {
  return iso ? iso.replace("T", " ").slice(0, 19) : "—";
}
