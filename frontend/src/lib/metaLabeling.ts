/**
 * API client + types for the Meta-Labeling / Calibration / Threshold Lab
 * (Phase 51.0).  Requests go to /api/meta-labeling/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/meta-labeling";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  status: "pending" | "completed" | "failed" | "invalidated";
  calibration_method: "none" | "sigmoid" | "isotonic";
  oof_status: string;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  observation_count: number;
  labeled_count: number;
  positive_count: number;
  abstained_count: number;
  validation_run_id: number | null;
  validation_method: string | null;
  dataset_version_id: number | null;
  dataset_name: string | null;
  dataset_version_label: string | null;
  dataset_invalidated: boolean | null;
  experiment_id: number | null;
  positive_prevalence: number | null;
  brier_preview: number | null;
  ece_preview: number | null;
  error_message: string | null;
}

export interface MetricsBlock {
  metrics: Record<string, number | null>;
  reasons: Record<string, string>;
  positive_prevalence: number | null;
  valid_count: number;
  ece?: number | null;
  mce?: number | null;
}

export interface ThresholdRow {
  threshold: number;
  accepted: number;
  rejected: number;
  band_abstained: number;
  coverage: number | null;
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
  precision: number | null;
  recall: number | null;
  specificity: number | null;
  f1: number | null;
  balanced_accuracy: number | null;
  accepted_positive_rate: number | null;
  accepted_outcome_mean: number | null;
  accepted_outcome_sum: number | null;
}

export interface RunFull extends RunSummary {
  description: string;
  label_policy: Record<string, unknown>;
  configuration: Record<string, unknown>;
  raw_metrics: MetricsBlock;
  calibrated_metrics: MetricsBlock;
  calibration_params: Record<string, unknown>;
  threshold_analysis: { thresholds?: ThresholdRow[]; abstention?: unknown; grid_size?: number };
  completed_at: string | null;
  duration_ms: number | null;
  notes: string;
  experiment_name: string | null;
  dataset_manifest_fingerprint: string | null;
  dataset_provenance_status: string | null;
  dataset_quality_status: string | null;
  validation_leakage_clean: boolean | null;
  validation_config_fp: string | null;
  validation_result_fp: string | null;
}

export interface CalibrationBin {
  bin_index: number;
  lower_bound: number | null;
  upper_bound: number | null;
  sample_count: number;
  mean_probability: number | null;
  observed_frequency: number | null;
  calibration_gap: number | null;
}

export interface ThresholdPolicy {
  id: number;
  run_id: number;
  name: string;
  threshold: number;
  abstention: { lower: number; upper: number } | null;
  configuration_fingerprint: string;
  observed_coverage: number | null;
  observed_precision: number | null;
  observed_recall: number | null;
  observed_f1: number | null;
  is_baseline: boolean;
  notes: string;
  created_at: string;
}

export interface ObservationRow {
  sample_id: string;
  prediction_time: string;
  primary_side: number;
  raw_probability: number | null;
  calibrated_probability: number | null;
  realized_outcome: number | null;
  meta_label: number | null;
  abstained: boolean;
  split_label: string | null;
}

export interface CompareEntry {
  kind: string;
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

export interface LabSummary {
  runs: number;
  completed: number;
  oof_verified: number;
  calibrated: number;
  threshold_policies: number;
  baselines: number;
  methods: Record<string, number>;
}

export interface RunFilters {
  status?: string;
  calibration_method?: string;
  oof_status?: string;
  query?: string;
}

function unavailable(status: number): string {
  return (
    `Backend request failed (HTTP ${status}). ` +
    "Make sure the FastAPI backend is running at BACKEND_URL, " +
    "or http://localhost:8000 by default."
  );
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new BacktestApiError(0, unavailable(0));
  }
  if (!res.ok) {
    let message = res.status >= 500 ? unavailable(res.status) : `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      /* keep */
    }
    throw new BacktestApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

function q(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") search.set(k, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const getLabSummary = () => request<LabSummary>("/summary");
export const listRuns = (params: RunFilters & { page?: number; page_size?: number } = {}) =>
  request<{ items: RunSummary[]; total: number; page: number; total_pages: number }>(
    `/runs${q(params as Record<string, unknown>)}`,
  );
export const getRun = (id: number) => request<RunFull>(`/runs/${id}`);
export const getCalibration = (id: number) =>
  request<{ bins: Record<string, CalibrationBin[]>; raw_metrics: MetricsBlock; calibrated_metrics: MetricsBlock }>(
    `/runs/${id}/calibration`,
  );
export const listPolicies = (id: number) => request<ThresholdPolicy[]>(`/runs/${id}/threshold-policies`);
export const createPolicy = (id: number, body: { name?: string; threshold: number; abstention?: unknown }) =>
  request<ThresholdPolicy>(`/runs/${id}/threshold-policies`, { method: "POST", body: JSON.stringify(body) });
export const markPolicyBaseline = (policyId: number) =>
  request<ThresholdPolicy>(`/threshold-policies/${policyId}/mark-baseline`, { method: "POST" });
export const listObservations = (id: number, page = 1, pageSize = 25) =>
  request<{ items: ObservationRow[]; total: number; page: number; total_pages: number }>(
    `/runs/${id}/observations?page=${page}&page_size=${pageSize}`,
  );
export const compareRuns = (a: number, b: number) => request<RunComparison>(`/compare?a=${a}&b=${b}`);
export const exportRuns = (filters: RunFilters = {}) =>
  request<Record<string, unknown>>(`/export${q(filters as Record<string, unknown>)}`);
export const seedDemo = () =>
  request<{ created_runs: number; created_policies: number; skipped_existing: number }>("/demo-seed", {
    method: "POST",
  });

export const OOF_LABELS: Record<string, string> = {
  verified_from_validation_run: "OOF verified",
  declared_out_of_fold: "OOF declared",
  not_out_of_fold: "Not out-of-fold",
  unknown: "Unknown",
};

export const shortFp = (v: string | null | undefined) => (v ? v.slice(0, 12) : "—");
