/**
 * API client + types for the Feature Importance / Stability / Drift
 * Diagnostics Lab (Phase 52.0).  Requests go to /api/feature-diagnostics/*
 * via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/feature-diagnostics";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  status: "pending" | "completed" | "failed" | "invalidated";
  method: "permutation" | "native_impurity" | "coefficient";
  model_type: string;
  target_type: string;
  metric: string;
  metric_direction: string;
  split_source: string;
  integrity_status: string;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  sample_count: number;
  feature_count: number;
  split_count: number;
  valid_split_count: number;
  invalid_split_count: number;
  is_baseline: boolean;
  validation_run_id: number | null;
  validation_method: string | null;
  dataset_version_id: number | null;
  dataset_name: string | null;
  dataset_version_label: string | null;
  dataset_invalidated: boolean | null;
  experiment_id: number | null;
  meta_label_run_id: number | null;
  top_feature: string | null;
  top_feature_importance: number | null;
  stable_feature_count: number;
  unstable_feature_count: number;
  drift_flag_count: number;
  error_message: string | null;
}

export interface StabilityPair {
  split_a: string;
  split_b: string;
  spearman: number | null;
  kendall: number | null;
  top_k_overlap: number | null;
  note: string | null;
}

export interface StabilitySummary {
  valid_split_count?: number;
  pairwise_split_count?: number;
  truncated?: boolean;
  truncation_note?: string | null;
  top_k?: number;
  pairs?: StabilityPair[];
  mean_spearman?: number | null;
  min_spearman?: number | null;
  mean_kendall?: number | null;
  mean_top_k_overlap?: number | null;
  score_formula?: string;
  thresholds?: Record<string, number>;
}

export interface SplitMeta {
  split_id: string;
  split_index: number;
  split_fingerprint: string | null;
  status: string;
  baseline_score: number | null;
  train_count: number | null;
  evaluated_count: number | null;
  warning: string | null;
}

export interface RunFull extends RunSummary {
  description: string;
  configuration: Record<string, unknown>;
  baseline_fingerprint: string | null;
  baseline_scope: string | null;
  splits: SplitMeta[];
  stability_summary: StabilitySummary;
  importance_drift: Record<string, unknown>;
  references: {
    coefficients?: {
      rows: { feature_name: string; mean_coefficient: number; mean_abs_coefficient: number; sign: number; sign_consistent: boolean; standardized: boolean }[];
      fitted_splits: number;
      caveats: string[];
    };
    native_impurity?: {
      rows: { feature_name: string; mean_native_importance: number }[];
      fitted_splits: number;
      caveats: string[];
    };
  };
  drift_context: { mode?: string; reference_label?: string; comparison_label?: string; reference_count?: number; comparison_count?: number };
  warnings: string[];
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
  meta_label_run_name: string | null;
  meta_label_oof_status: string | null;
  meta_label_calibration_method: string | null;
  meta_label_result_fp: string | null;
}

export interface FeatureResult {
  feature_name: string;
  definition: { display_name?: string | null; feature_group?: string | null; source_column?: string | null; description?: string | null };
  rank: number | null;
  mean_importance: number | null;
  median_importance: number | null;
  std_importance: number | null;
  min_importance: number | null;
  max_importance: number | null;
  quantile_interval: { q25: number; q75: number } | null;
  mean_rank: number | null;
  median_rank: number | null;
  rank_std: number | null;
  rank_range: number | null;
  positive_split_fraction: number | null;
  negative_split_fraction: number | null;
  valid_split_count: number;
  stability_score: number | null;
  stability_classification: string;
  sign_consistency: number | null;
  sign_changed_across_splits: boolean;
  warning: string | null;
}

export interface SplitResultRow {
  split_id: string;
  split_index: number;
  feature_name: string;
  baseline_score: number | null;
  mean_importance: number | null;
  std_importance: number | null;
  min_importance: number | null;
  max_importance: number | null;
  positive_repeats: number;
  negative_repeats: number;
  valid_repeats: number;
  permutation_repeats: number;
  rank: number | null;
  status: string;
  warning: string | null;
}

export interface CorrelationGroup {
  group_id: string;
  size: number;
  max_abs_correlation: number | null;
  features: string[];
  pairs: { feature_a: string; feature_b: string; correlation: number; abs_correlation: number; sign: number }[];
  combined_mean_importance: number | null;
}

export interface DriftRow {
  feature_name: string;
  kind: "distribution" | "importance";
  classification: string;
  psi: number | null;
  ks_statistic: number | null;
  /** Set when either side of the comparison is below the small-sample floor. */
  small_sample_warning?: string | null;
  detail: Record<string, unknown>;
}

export interface CompareEntry {
  kind: string;
  field: string;
  a: unknown;
  b: unknown;
  note: string;
}

export interface CompareFeatureRow {
  feature_name: string;
  availability: string;
  a_importance: number | null;
  b_importance: number | null;
  a_rank: number | null;
  b_rank: number | null;
  a_stability: string | null;
  b_stability: string | null;
  abs_difference: number | null;
  pct_difference: number | null;
  rank_change: number | null;
  sign_changed: boolean | null;
  kind: string;
}

export interface RunComparison {
  a_id: number;
  b_id: number;
  groups: Record<string, CompareEntry[]>;
  features: CompareFeatureRow[];
  fingerprint_match: Record<string, boolean>;
  baseline: Record<string, boolean>;
}

export interface LabSummary {
  runs: number;
  completed: number;
  held_out_verified: number;
  stable_features: number;
  drift_flags: number;
  baselines: number;
  methods: Record<string, number>;
}

export interface RunFilters {
  status?: string;
  method?: string;
  metric?: string;
  integrity_status?: string;
  query?: string;
}

export const INTEGRITY_LABELS: Record<string, string> = {
  verified_held_out: "Verified held-out",
  declared_held_out: "Declared held-out",
  not_held_out: "Not held-out",
  unknown: "Unknown",
};

export const shortFp = (fp: string | null | undefined) => (fp ? fp.slice(0, 12) : "—");

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
export const getFeatures = (id: number) =>
  request<{ items: FeatureResult[] }>(`/runs/${id}/features`);
export const getSplits = (id: number) =>
  request<{ splits: SplitMeta[]; items: SplitResultRow[] }>(`/runs/${id}/splits`);
export const getCorrelations = (id: number) =>
  request<{ configuration: Record<string, unknown> | null; groups: CorrelationGroup[] }>(
    `/runs/${id}/correlations`,
  );
export const getDrift = (id: number) =>
  request<{ context: RunFull["drift_context"]; importance_drift: Record<string, unknown>; items: DriftRow[] }>(
    `/runs/${id}/drift`,
  );
export const markBaseline = (id: number) =>
  request<RunFull>(`/runs/${id}/mark-baseline`, { method: "POST", body: "{}" });
export const compareRuns = (a: number, b: number) =>
  request<RunComparison>(`/compare${q({ a, b })}`);
export const exportRuns = (filters: RunFilters = {}) =>
  request<Record<string, unknown>>(`/export${q(filters as Record<string, unknown>)}`);
export const seedDemo = () =>
  request<{ created_runs: number; skipped_existing: number }>("/demo-seed", {
    method: "POST",
    body: "{}",
  });
