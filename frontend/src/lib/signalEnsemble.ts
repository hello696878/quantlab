/**
 * API client + types for the Signal Ensemble, Redundancy and Combination
 * Diagnostics Lab (Phase 61.0).  Requests go to /api/signal-ensembles/*
 * via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/signal-ensembles";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed" | "invalidated";
  combination_mode: string;
  alignment_policy: string;
  frequency: string;
  signal_count: number;
  entity_count: number;
  observation_count: number;
  strict_intersection_count: number;
  combined_available_count: number | null;
  observation_start: string | null;
  observation_end: string | null;
  integrity_status: string;
  completeness_status: string;
  mean_absolute_correlation: number | null;
  effective_signal_count: number | null;
  universe_fingerprint: string | null;
  combination_fingerprint: string | null;
  similarity_fingerprint: string | null;
  analysis_fingerprint: string | null;
  configuration_fingerprint: string | null;
  result_fingerprint: string | null;
  is_baseline: boolean;
  error_message: string | null;
}

export interface CorrelationCell {
  method: string;
  observations: number;
  statistic: number | null;
  p_value: number | null;
  p_value_note: string | null;
  signal_tie_count: number | null;
  state: string;
  reason: string | null;
}

export interface PairwiseRow {
  signal_a: string;
  signal_b: string;
  alignment_mode: string;
  overlap_count: number;
  coverage_a: number | null;
  coverage_b: number | null;
  pearson: number | null;
  pearson_p: number | null;
  spearman: number | null;
  spearman_p: number | null;
  spearman_p_adjusted: number | null;
  kendall: number | null;
  kendall_p: number | null;
  mean_absolute_difference: number | null;
  sign_agreement_rate: number | null;
  zero_sign_count: number | null;
  agreement: {
    bucket_count: number;
    observations: number;
    exact_agreement_rate: number | null;
    adjacent_agreement_rate: number | null;
    top_bucket_jaccard: number | null;
    bottom_bucket_jaccard: number | null;
    directional_disagreement_count: number | null;
    state: string;
    reason: string | null;
  } | null;
  tails: {
    quantile: number;
    observations: number;
    tail_size: number | null;
    both_lower_count: number | null;
    both_upper_count: number | null;
    opposite_tail_count: number | null;
    lower_conditional_overlap: number | null;
    upper_conditional_overlap: number | null;
    state: string;
    reason: string | null;
  } | null;
  correlations: Record<string, CorrelationCell> | null;
  state: string;
  reason: string | null;
}

export interface MatrixBlock {
  signal_ids: string[];
  method: string;
  cells: (number | null)[][];
  unavailable_cells: { signal_a: string; signal_b: string; reason: string | null }[];
  complete: boolean;
}

export interface DistanceBlock {
  signal_ids: string[];
  formula: string;
  correlation_method: string;
  cells: (number | null)[][];
  complete: boolean;
  note: string;
}

export interface MatrixDiagnostics {
  method: string;
  signal_count: number;
  eigenvalues: number[] | null;
  negative_eigenvalue_count: number | null;
  matrix_rank: number | null;
  condition_number: number | null;
  condition_number_note: string | null;
  eigenvalue_concentration_top: number | null;
  effective_signal_count: number | null;
  effective_signal_count_note: string;
  psd_within_tolerance: boolean | null;
  state: string;
  reason: string | null;
  warnings: string[];
}

export interface ClusteringBlock {
  linkage: string;
  threshold: number;
  criterion: string;
  merges: { left: number; right: number; distance: number; size: number }[] | null;
  clusters: { signal_id: string; cluster: number }[] | null;
  leaf_order: string[] | null;
  cluster_count: number | null;
  state: string;
  reason: string | null;
  note: string;
}

export interface RedundancyBlock {
  method: string;
  pair_count: number;
  available_pair_count: number;
  mean_absolute_correlation: number | null;
  median_absolute_correlation: number | null;
  max_absolute_correlation: number | null;
  nearest_neighbour_similarity: { signal_id: string; max_absolute_correlation: number | null }[];
  average_exact_bucket_agreement: number | null;
  average_sign_agreement: number | null;
  note: string;
}

export interface DefinitionRow {
  signal_id: string;
  name: string;
  definition: Record<string, unknown>;
  definition_fingerprint: string;
  orientation: string;
  normalisation: Record<string, unknown>;
  stored_observations: number;
  coverage: number | null;
}

export interface CombinedObservation {
  entity_id: string;
  timestamp: string;
  available_at: string | null;
  combined_score: number | null;
  component_count: number;
  missing_signal_ids: string[];
  state: string;
  reason: string | null;
}

export interface ComponentRow {
  entity_id: string;
  timestamp: string;
  signal_id: string;
  raw_value: number | null;
  oriented_value: number | null;
  normalised_value: number | null;
  configured_weight: number | null;
  effective_weight: number | null;
  contribution: number | null;
  sign_vote: number | null;
  missing: boolean;
}

export interface HorizonRow {
  scope: string;
  subject_id: string | null;
  horizon: string;
  entry_lag: number;
  outcome_scope: string;
  observations: number;
  pearson: number | null;
  spearman: number | null;
  spearman_p: number | null;
  spearman_p_adjusted: number | null;
  mean_cross_sectional_ic: number | null;
  top_minus_bottom: number | null;
  cost_adjusted_spread: number | null;
  overlap_ratio: number | null;
  mean_one_way_turnover: number | null;
  state: string;
  reason: string | null;
  detail: Record<string, unknown> | null;
}

export interface LeaveOneOutRow {
  omitted_signal_id: string;
  metrics: {
    coverage: number | null;
    coverage_delta: number | null;
    mean_absolute_correlation: number | null;
    mean_absolute_correlation_delta: number | null;
    effective_signal_count: number | null;
    effective_signal_count_delta: number | null;
    first_horizon_spearman: number | null;
    first_horizon_spearman_delta: number | null;
    first_horizon_spread: number | null;
    first_horizon_spread_delta: number | null;
    mean_one_way_turnover: number | null;
    mean_one_way_turnover_delta: number | null;
    note: string;
  };
  state: string;
  reason: string | null;
}

export interface RegimeRow {
  regime_label: string;
  observations: number;
  rare: boolean;
  mean_absolute_correlation: number | null;
  effective_signal_count: number | null;
  combined_spearman: number | null;
  top_minus_bottom: number | null;
  coverage: number | null;
  state: string;
  reason: string | null;
  detail: Record<string, unknown> | null;
}

export interface BootstrapRow {
  statistic: string;
  method: string;
  seed: number;
  resamples: number;
  block_length: number | null;
  quantiles: { q025: number; q500: number; q975: number; note: string } | null;
  unavailable_resamples: number | null;
  state: string;
  reason: string | null;
}

export interface SensitivityRow {
  scenario_index: number;
  is_base: boolean;
  label: string;
  scenario: Record<string, unknown>;
  scenario_fingerprint: string;
  metrics: Record<string, number | string | null>;
  warnings: string[];
  state: string;
  reason: string | null;
}

export interface RunFull extends RunSummary {
  definitions: DefinitionRow[];
  missingness: {
    union_keys: number;
    strict_intersection_keys: number;
    strict_intersection_coverage: number | null;
    post_normalisation_intersection_keys?: number;
    per_signal: {
      signal_id: string;
      union_keys: number;
      present: number;
      stored_null: number;
      absent: number;
      coverage: number | null;
    }[];
    note: string;
  } | null;
  matrix: MatrixBlock | null;
  distance: DistanceBlock | null;
  matrix_diagnostics: MatrixDiagnostics | null;
  clustering: ClusteringBlock | null;
  redundancy: RedundancyBlock | null;
  reconciliation: {
    tolerance: number;
    checked: number;
    failures: number;
    state: string;
    note: string;
  } | null;
  combination_coverage: number | null;
  turnover_summary: Record<string, number | string | null> | null;
  holding_overlap: Record<string, unknown> | null;
  cost: Record<string, unknown> | null;
  component_turnover: Record<string, number | null> | null;
  multiple_testing: Record<string, unknown> | null;
  held_out: {
    split_label: string;
    leakage_clean: boolean | null;
    training_observations: number;
    held_out_observations: number;
    purged_observations: number;
    embargoed_observations: number;
    training: { observations: number; spearman: number | null; reason: string | null };
    held_out: { observations: number; spearman: number | null; reason: string | null };
    full_sample: { observations: number; spearman: number | null; reason: string | null };
    training_mean_absolute_correlation: number | null;
    note: string;
  } | null;
  factor_residual: {
    factor_run_name: string | null;
    result_fingerprint: string | null;
    matched_pairs: number;
    unmatched_pairs: number;
    signal_value_residualisation: { state: string; reason: string };
    convention: string;
  } | null;
  leave_one_out: LeaveOneOutRow[];
  contribution_rows_total: number | null;
  contribution_rows_stored: number | null;
  warnings: string[];
  normalisation_reasons: Record<string, Record<string, number>> | null;
}

export interface RunComparison {
  run_a: { id: number; name: string; status: string };
  run_b: { id: number; name: string; status: string };
  fields: { field: string; a: unknown; b: unknown; state: string }[];
  metrics: Record<string, { a: number | null; b: number | null }>;
  directly_comparable: boolean;
  warnings: string[];
  note: string;
}

export interface LabSummary {
  runs: number;
  completed: number;
  signals: number;
  observations: number;
  pairwise_rows: number;
  baselines: number;
}

export interface RunFilters {
  status?: string;
  combination_mode?: string;
  alignment_policy?: string;
  integrity_status?: string;
  completeness_status?: string;
  is_baseline?: boolean;
  query?: string;
}

export const INTEGRITY_LABELS: Record<string, string> = {
  verified_from_validation_split: "Verified — validation split",
  verified_point_in_time: "Verified — point in time",
  verified_trailing_transformation: "Verified — trailing transformation",
  supplied_descriptive: "Supplied (descriptive)",
  contemporaneous_descriptive: "Contemporaneous (descriptive)",
  full_sample_descriptive: "Full sample (descriptive)",
  unknown: "Unknown",
  invalid: "Invalid",
};

export const MODE_LABELS: Record<string, string> = {
  equal_weight: "Equal weight",
  user_weights: "User weights",
  rank_average: "Rank average",
  majority_sign: "Majority sign",
};

export const ALIGNMENT_LABELS: Record<string, string> = {
  strict_intersection: "Strict intersection",
  pairwise_complete: "Pairwise complete",
};

export const shortFp = (fp: string | null | undefined) =>
  fp ? `${fp.slice(0, 10)}…` : "—";

export const fmtNum = (v: number | null | undefined, digits = 4) =>
  v === null || v === undefined || !Number.isFinite(v) ? "—" : v.toFixed(digits);

export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined || !Number.isFinite(v)
    ? "—"
    : `${(v * 100).toFixed(digits)}%`;

export const fmtP = (v: number | null | undefined) => {
  if (v === null || v === undefined || !Number.isFinite(v)) return "unavailable";
  if (v < 1e-4) return v.toExponential(2);
  return v.toFixed(4);
};

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
  request<{ items: RunSummary[]; total: number; page: number; page_size: number }>(
    `/runs${q(params as Record<string, unknown>)}`,
  );
export const getRun = (id: number) => request<RunFull>(`/runs/${id}`);
export const getPairwise = (id: number) =>
  request<{ items: PairwiseRow[] }>(`/runs/${id}/pairwise`);
export const getMatrix = (id: number) =>
  request<{
    matrix: MatrixBlock | null;
    distance: DistanceBlock | null;
    diagnostics: MatrixDiagnostics | null;
    clustering: ClusteringBlock | null;
    redundancy: RedundancyBlock | null;
  }>(`/runs/${id}/matrix`);
export const getComponents = (id: number, limit = 500) =>
  request<{
    observations: CombinedObservation[];
    components: ComponentRow[];
    reconciliation: RunFull["reconciliation"];
    contribution_rows_total: number | null;
    contribution_rows_stored: number | null;
  }>(`/runs/${id}/components${q({ limit })}`);
export const getHorizons = (id: number) =>
  request<{ items: HorizonRow[] }>(`/runs/${id}/horizons`);
export const getLeaveOneOut = (id: number) =>
  request<{ items: LeaveOneOutRow[] }>(`/runs/${id}/leave-one-out`);
export const getRegimes = (id: number) =>
  request<{ items: RegimeRow[] }>(`/runs/${id}/regimes`);
export const getBootstrap = (id: number) =>
  request<{ items: BootstrapRow[] }>(`/runs/${id}/bootstrap`);
export const getSensitivity = (id: number) =>
  request<{ items: SensitivityRow[] }>(`/runs/${id}/sensitivity`);
export const markBaseline = (id: number) =>
  request<RunFull>(`/runs/${id}/mark-baseline`, { method: "POST", body: "{}" });
export const compareRuns = (a: number, b: number) =>
  request<RunComparison>(`/compare${q({ a, b })}`);
export const exportRuns = (filters: RunFilters = {}) =>
  request<Record<string, unknown>>(`/export${q(filters as Record<string, unknown>)}`);
export const seedDemo = () =>
  request<{
    created: boolean;
    created_count: number;
    skipped_count: number;
    run_ids: number[];
  }>("/demo-seed", { method: "POST", body: "{}" });
