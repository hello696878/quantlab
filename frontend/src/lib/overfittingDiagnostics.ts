/**
 * API client + types for the Backtest Overfitting / PBO / Deflated Sharpe /
 * Multiple Testing Diagnostics Lab (Phase 53.0).  Requests go to
 * /api/overfitting-diagnostics/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/overfitting-diagnostics";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  status: "pending" | "completed" | "failed" | "invalidated";
  metric: string;
  block_count: number;
  candidate_count: number;
  observation_count: number;
  combination_count: number;
  valid_split_count: number;
  invalid_split_count: number;
  pbo_estimate: number | null;
  psr: number | null;
  dsr: number | null;
  benchmark_sharpe: number | null;
  effective_trial_count: number | null;
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
  experiment_id: number | null;
  feature_diagnostics_run_id: number | null;
  error_message: string | null;
}

export interface LambdaStats {
  mean: number | null;
  median: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
  q05: number | null;
  q25: number | null;
  q75: number | null;
  q95: number | null;
  fraction_below_zero: number | null;
  fraction_at_zero: number | null;
}

export interface SelectionEntry {
  candidate_id: string;
  selected_count: number;
  selection_frequency: number;
  mean_oos_rank_when_selected: number | null;
  median_oos_rank_when_selected: number | null;
  mean_lambda_when_selected: number | null;
  median_lambda_when_selected: number | null;
  mean_degradation_when_selected: number | null;
  below_median_oos_fraction: number | null;
  negative_oos_fraction: number | null;
  mean_is_rank: number | null;
  mean_oos_rank: number | null;
}

export interface PboAggregate {
  combination_count?: number;
  valid_split_count?: number;
  invalid_split_count?: number;
  tie_in_sample_count?: number;
  tie_out_of_sample_count?: number;
  pbo_estimate?: number | null;
  pbo_note?: string;
  rank_convention?: string;
  lambda_zero_policy?: string;
  lambda_stats?: LambdaStats | null;
  is_oos_correlation?: { pearson: number | null; spearman: number | null; note: string } | null;
  oos_loss_fraction?: number | null;
  oos_loss_note?: string;
  mean_degradation?: number | null;
  median_degradation?: number | null;
  mean_rank_degradation?: number | null;
  median_rank_degradation?: number | null;
  selection?: SelectionEntry[];
}

export interface SharpeBlockPart {
  psr?: number | null;
  dsr?: number | null;
  status: string;
  note: string | null;
  benchmark_sharpe?: number | null;
  expected_max_sharpe?: number | null;
  min_track_record?: number | null;
  approx_years?: number | null;
  unit?: string;
  confidence?: number;
}

export interface SharpeDiagnostics {
  sharpe_convention?: string;
  skew_convention?: string;
  kurtosis_convention?: string;
  benchmark_sharpe?: number;
  confidence?: number;
  trials_raw?: number;
  trials_effective?: number | null;
  trial_policy?: { mode: string; manual_value: number | null };
  periods_per_year?: number | null;
  focus_note?: string;
  focus_candidate_id?: string | null;
  observed_sharpe?: number | null;
  observations?: number | null;
  skewness?: number | null;
  kurtosis?: number | null;
  small_sample_warning?: string | null;
  sharpe_variance?: number | null;
  psr?: SharpeBlockPart;
  dsr?: SharpeBlockPart;
  min_track_record?: SharpeBlockPart;
}

export interface Dependence {
  threshold?: number;
  candidate_count?: number;
  defined_candidate_count?: number;
  constant_candidates?: string[];
  constant_note?: string | null;
  mean_abs_correlation?: number | null;
  median_abs_correlation?: number | null;
  high_correlation_pairs?: { candidate_a: string; candidate_b: string; correlation: number; abs_correlation: number }[];
  clusters?: { cluster_id: string; candidates: string[]; size: number }[];
  effective_trials_estimate?: number | null;
  effective_trials_note?: string;
}

export interface RunFull extends RunSummary {
  description: string;
  configuration: Record<string, unknown>;
  timestamps: string[];
  blocks: { block_id: number; start: number; end: number; size: number }[];
  pbo_aggregate: PboAggregate;
  sharpe_diagnostics: SharpeDiagnostics;
  dependence: Dependence;
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
  validation_result_fp: string | null;
  validation_valid_splits: number | null;
  validation_invalid_splits: number | null;
  feature_run_name: string | null;
  feature_run_integrity: string | null;
}

export interface CandidateRow {
  candidate_id: string;
  name: string;
  description: string;
  candidate_group: string | null;
  nominal_p_value: number | null;
  raw_sharpe: number | null;
  skewness: number | null;
  kurtosis: number | null;
  psr: number | null;
  sharpe_status: string | null;
  sharpe_note: string | null;
  mean_return: number | null;
  cumulative_return: number | null;
  selection_frequency: number | null;
  mean_oos_rank: number | null;
  status: string;
}

export interface SplitRow {
  split_id: string;
  split_index: number;
  is_block_ids: number[];
  oos_block_ids: number[];
  selected_candidate_id: string | null;
  is_metric: number | null;
  oos_metric: number | null;
  oos_rank: number | null;
  oos_defined_count: number | null;
  relative_rank: number | null;
  lambda: number | null;
  degradation: number | null;
  rank_degradation: number | null;
  tie_in_sample: boolean;
  tie_out_of_sample: boolean;
  status: string;
  warning: string | null;
}

export interface MultipleTestingRow {
  candidate_id: string;
  raw_p_value: number | null;
  bonferroni: number | null;
  holm: number | null;
  bh: number | null;
  provenance_status: string;
  provenance: Record<string, unknown> | null;
  state_raw: string;
  state_bonferroni: string;
  state_holm: string;
  state_bh: string;
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
  selection: {
    candidate_id: string; availability: string;
    a_selection_frequency: number | null; b_selection_frequency: number | null;
    a_mean_oos_rank: number | null; b_mean_oos_rank: number | null;
  }[];
  fingerprint_match: Record<string, boolean>;
  baseline: Record<string, boolean>;
}

export interface LabSummary {
  runs: number;
  completed: number;
  candidates: number;
  valid_splits: number;
  baselines: number;
  adjusted_below_threshold: number;
  metrics: Record<string, number>;
}

export interface RunFilters {
  status?: string;
  metric?: string;
  query?: string;
}

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
export const getCandidates = (id: number) =>
  request<{ items: CandidateRow[] }>(`/runs/${id}/candidates`);
export const getSplits = (id: number, page = 1, page_size = 100) =>
  request<{ items: SplitRow[]; total: number; page: number; total_pages: number }>(
    `/runs/${id}/pbo-splits${q({ page, page_size })}`,
  );
export const getMultipleTesting = (id: number) =>
  request<{ alpha: number | null; items: MultipleTestingRow[] }>(
    `/runs/${id}/multiple-testing`,
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
