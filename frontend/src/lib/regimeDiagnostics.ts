/**
 * API client + types for the Market Regime Robustness / Conditional
 * Performance Diagnostics Lab (Phase 54.0).  Requests go to
 * /api/regime-diagnostics/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/regime-diagnostics";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  status: "pending" | "completed" | "failed" | "invalidated";
  candidate_count: number;
  observation_count: number;
  period_count: number;
  frequency: string;
  regime_definition_count: number;
  observed_regime_count: number;
  invalid_definition_count: number;
  low_coverage_warning_count: number;
  integrity_status: string;
  universe_fingerprint: string;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  is_baseline: boolean;
  dataset_version_id: number | null;
  dataset_name: string | null;
  dataset_version_label: string | null;
  dataset_invalidated: boolean | null;
  validation_run_id: number | null;
  validation_method: string | null;
  overfitting_run_id: number | null;
  feature_diagnostics_run_id: number | null;
  meta_label_run_id: number | null;
  experiment_id: number | null;
  error_message: string | null;
}

export interface CoverageBlock {
  labeled_periods: number;
  unassigned_periods: number;
  per_label: Record<string, { observations: number; share: number | null }>;
}

export interface RobustnessRow {
  candidate_id: string;
  definition_id: string;
  observed_regimes: number;
  defined_regimes: number;
  unavailable_regimes: number;
  total_observations: number;
  dispersion: number | null;
  sign_consistency: number | null;
  positive_regime_fraction: number | null;
  negative_regime_fraction: number | null;
  lowest_regime_mean: number | null;
  highest_regime_mean: number | null;
  largest_regime_share: number | null;
  classification: string;
  classification_note: string;
}

export interface RankBlock {
  status: string;
  reason?: string;
  labels?: string[];
  truncated?: boolean;
  truncation_note?: string | null;
  rank_convention?: string;
  top_k?: number;
  ranks?: Record<string, Record<string, number | null>>;
  pairs?: { regime_a: string; regime_b: string; spearman: number | null; top_k_overlap: number | null; note: string | null }[];
  mean_spearman?: number | null;
  mean_top_k_overlap?: number | null;
  per_candidate?: { candidate_id: string; rank_std: number | null; rank_range: number | null; defined_regimes: number }[];
}

export interface ConcentrationRow {
  candidate_id: string;
  definition_id: string;
  observation_hhi: number | null;
  positive_outcome_hhi: number | null;
  largest_abs_share: number | null;
  top2_abs_share: number | null;
  largest_signed_share: number | null;
  top2_signed_share: number | null;
  signed_share_note: string | null;
  effective_regime_count: number | null;
  entropy: number | null;
  status: string;
  note: string | null;
}

export interface RunFull extends RunSummary {
  description: string;
  configuration: Record<string, unknown>;
  timestamps: string[];
  candidates: { candidate_id: string; name: string; outcome_kind: string }[];
  coverage: Record<string, CoverageBlock>;
  robustness: RobustnessRow[];
  rank_stability: Record<string, RankBlock>;
  concentration: ConcentrationRow[];
  warnings: string[];
  baseline_scope: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  notes: string;
  experiment_name: string | null;
  dataset_manifest_fingerprint: string | null;
  dataset_provenance_status: string | null;
  dataset_quality_status: string | null;
  validation_leakage_clean: boolean | null;
  validation_config_fp: string | null;
  overfitting_name: string | null;
  overfitting_pbo: number | null;
  overfitting_psr: number | null;
  overfitting_dsr: number | null;
  overfitting_universe_fp: string | null;
  feature_run_name: string | null;
  feature_run_integrity: string | null;
  meta_label_run_name: string | null;
  meta_label_oof_status: string | null;
}

export interface TransitionCandidate {
  candidate_id: string;
  pre_count: number;
  post_count: number;
  pre_mean: number | null;
  post_mean: number | null;
  difference: number | null;
  status: string;
}

export interface TransitionBlock {
  transition_count?: number;
  recorded_count?: number;
  truncated?: boolean;
  truncation_note?: string | null;
  window?: number;
  wording_note?: string;
  transitions?: {
    transition_index: number; timestamp: string; previous_regime: string;
    next_regime: string; window: number; overlapping_window: boolean;
    candidates: TransitionCandidate[];
  }[];
}

export interface DefinitionRow {
  definition_id: string;
  name: string;
  description: string;
  dimension: string;
  source_feature: string | null;
  lookback: number | null;
  lag: number | null;
  threshold_mode: string | null;
  min_observations: number;
  integrity_status: string;
  status: string;
  definition: Record<string, unknown>;
  definition_fingerprint: string;
  thresholds_used: Record<string, unknown> | null;
  threshold_fingerprint: string | null;
  assignments: (string | null)[];
  unavailable_count: number;
  distinct_label_count: number;
  interval_summary: { interval_count?: number; per_label?: Record<string, { intervals: number; mean_duration: number; max_duration: number }> };
  transitions: TransitionBlock;
  warnings: string[];
}

export interface ConditionalRow {
  candidate_id: string;
  definition_id: string;
  regime_label: string;
  observation_count: number;
  coverage: number | null;
  mean: number | null;
  median: number | null;
  std: number | null;
  minimum: number | null;
  maximum: number | null;
  positive_rate: number | null;
  negative_rate: number | null;
  cumulative: number | null;
  sharpe_like: number | null;
  downside_deviation: number | null;
  status: string;
  note: string | null;
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
  comparability_warnings: string[];
  groups: Record<string, CompareEntry[]>;
  robustness: {
    candidate_id: string; definition_id: string; availability: string;
    a_classification: string | null; b_classification: string | null;
    a_sign_consistency: number | null; b_sign_consistency: number | null;
  }[];
  fingerprint_match: Record<string, boolean>;
  baseline: Record<string, boolean>;
}

export interface LabSummary {
  runs: number;
  completed: number;
  candidates: number;
  observed_regimes: number;
  verified_definitions: number;
  low_coverage_warnings: number;
  baselines: number;
}

export interface RunFilters {
  status?: string;
  integrity_status?: string;
  query?: string;
}

export const INTEGRITY_LABELS: Record<string, string> = {
  verified_from_validation_split: "Verified (training split)",
  verified_causal_rule: "Verified causal rule",
  declared: "Declared",
  full_sample_descriptive: "Full-sample descriptive",
  unknown: "Unknown",
  invalid: "Invalid",
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
export const getDefinitions = (id: number) =>
  request<{ items: DefinitionRow[] }>(`/runs/${id}/definitions`);
export const getConditionalResults = (id: number, definition_id?: string) =>
  request<{ items: ConditionalRow[] }>(
    `/runs/${id}/conditional-results${q({ definition_id })}`,
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
