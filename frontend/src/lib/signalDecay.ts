/**
 * API client + types for the Signal Decay, Forecast Horizon, Turnover and
 * Implementation Lag Diagnostics Lab (Phase 60.0).  Requests go to
 * /api/signal-decay/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/signal-decay";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed" | "invalidated";
  signal_id: string;
  signal_type: string;
  outcome_id: string;
  outcome_target_type: string;
  frequency: string;
  entity_count: number;
  observation_count: number;
  horizon_count: number;
  lag_count: number;
  observation_start: string | null;
  observation_end: string | null;
  integrity_status: string;
  completeness_status: string;
  overlap_status: string | null;
  first_horizon_rank_ic: number | null;
  mean_one_way_turnover: number | null;
  signal_fingerprint: string;
  outcome_fingerprint: string;
  universe_fingerprint: string;
  horizon_fingerprint: string;
  analysis_fingerprint: string;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  is_baseline: boolean;
  error_message: string | null;
}

export interface DecayBlock {
  statistic: string;
  horizons_available: number;
  first_sign_change_horizon: number | null;
  first_below_threshold_horizon: number | null;
  absolute_threshold: number | null;
  max_absolute_statistic: number | null;
  max_absolute_horizon: number | null;
  ratio_to_first_horizon: Record<string, number>;
  note: string;
  exponential_fit?: {
    state: string;
    reason: string | null;
    log_slope: number | null;
    log_intercept: number | null;
    half_life: number | null;
    r_squared: number | null;
    fitted: { horizon: number; fitted_absolute_statistic: number }[];
    residuals: { horizon: number; log_residual: number }[];
    half_life_unit: string;
    convention: string;
  };
}

export interface OverlapBlock {
  horizon: number | string;
  entry_lag: number;
  interval_count: number;
  overlapping_interval_count: number;
  overlap_ratio: number | null;
  max_simultaneous_overlap: number;
  state: string;
}

export interface TurnoverSummary {
  rebalance_count: number;
  mean_one_way_turnover: number | null;
  max_one_way_turnover: number | null;
  mean_jaccard_top: number | null;
  average_holding_duration: number | null;
  holding_duration_unit: string;
  initial_policy: string;
  turnover_convention: string;
  initial_policy_note: string;
}

export interface HoldingOverlapBlock {
  open_cohort_model: string;
  cohort_normalisation: string;
  max_concurrent_cohorts: number | null;
  average_concurrent_cohorts: number | null;
  gross_exposure_overlapping: number | null;
  gross_exposure_note: string | null;
  warning: string | null;
  state: string;
}

export interface CostBlock {
  reference_notional: number;
  model_fingerprint: string | null;
  per_side_bps_computable: number;
  components: {
    component: string;
    model: string | null;
    per_side_bps: number | null;
    scalable: boolean;
    state: string;
    reason: string | null;
    note?: string;
  }[];
  unavailable_components: string[];
  total_cost: number | null;
  total_cost_return: number | null;
  costed_rebalances: number;
  skipped_rebalances: number;
  completeness: string;
  convention: string;
  spread_adjustment_convention?: string;
}

export interface HeldOutBlock {
  split_label: string;
  leakage_clean: boolean | null;
  training_observations: number;
  held_out_observations: number;
  purged_observations: number;
  embargoed_observations: number;
  training: Record<string, unknown>;
  held_out: Record<string, unknown>;
  full_sample: Record<string, unknown>;
  frozen_bucket_thresholds: number[] | null;
  held_out_buckets_available: boolean;
  note: string;
}

export interface FactorResidualBlock {
  factor_run_id: number;
  factor_run_name: string | null;
  result_fingerprint: string | null;
  model_policy_fingerprint: string | null;
  state: string;
  reason: string | null;
  unmatched_pairs: number;
  convention: string;
}

export interface MultipleTestingBlock {
  methods: string[];
  alpha: number;
  family: string;
  hypotheses: number;
  rows: Record<string, unknown>[];
  note: string;
}

export interface RunFull extends RunSummary {
  configuration: Record<string, unknown>;
  signal: Record<string, unknown> | null;
  outcome: Record<string, unknown> | null;
  horizon_policy: Record<string, unknown> | null;
  bucket_policy: Record<string, unknown> | null;
  turnover_policy: Record<string, unknown> | null;
  policy: Record<string, unknown> | null;
  decay: DecayBlock[];
  overlap: OverlapBlock[];
  turnover_summary: TurnoverSummary | null;
  holding_overlap: HoldingOverlapBlock | null;
  cost: CostBlock | null;
  held_out: HeldOutBlock | null;
  factor_residual: FactorResidualBlock | null;
  multiple_testing: MultipleTestingBlock | null;
  signal_diagnostics: {
    autocorrelation: {
      lag: number;
      autocorrelation: number | null;
      observations: number;
      reason: string | null;
    }[];
    note: string;
  } | null;
  warnings: string[];
  dataset_identity: Record<string, unknown>;
  feature_identity: Record<string, unknown> | null;
  meta_label_identity: Record<string, unknown> | null;
  validation_identity: Record<string, unknown> | null;
  regime_identity: Record<string, unknown> | null;
  cost_identity: Record<string, unknown> | null;
  factor_identity: Record<string, unknown> | null;
}

export interface HorizonRow {
  horizon: number | string;
  entry_lag: number;
  selection: string;
  outcome_scope: string;
  observations: number;
  unavailable_count: number;
  pearson: number | null;
  pearson_p_value: number | null;
  spearman: number | null;
  spearman_p_value: number | null;
  spearman_p_adjusted: number | null;
  kendall: number | null;
  kendall_p_value: number | null;
  mean_cross_sectional_ic: number | null;
  ic_ratio: number | null;
  top_minus_bottom: number | null;
  cost_adjusted_spread: number | null;
  monotonicity_spearman: number | null;
  overlap_ratio: number | null;
  max_simultaneous_overlap: number | null;
  effective_non_overlapping: number | null;
  overlap_state: string | null;
  p_value_note: string | null;
  state: string;
  reason: string | null;
  detail: Record<string, unknown>;
}

export interface BucketRow {
  horizon: number | string;
  entry_lag: number;
  outcome_scope: string;
  bucket: number;
  observations: number;
  score_minimum: number | null;
  score_maximum: number | null;
  mean_outcome: number | null;
  median_outcome: number | null;
  std_outcome: number | null;
  positive_rate: number | null;
  state: string;
  reason: string | null;
}

export interface TurnoverRow {
  horizon: number | string;
  entry_lag: number;
  timestamp: string;
  universe_size: number;
  top_size: number;
  bottom_size: number;
  top_entries: number;
  top_exits: number;
  bottom_entries: number;
  bottom_exits: number;
  jaccard_top: number | null;
  one_way_turnover: number | null;
  cost: number | null;
  cost_return: number | null;
  cost_state: string | null;
}

export interface RegimeRow {
  regime_label: string;
  horizon: number | string;
  entry_lag: number;
  observations: number;
  rare: boolean;
  pearson: number | null;
  spearman: number | null;
  top_minus_bottom: number | null;
  overlap_ratio: number | null;
  state: string;
  reason: string | null;
}

export interface BootstrapRow {
  horizon: number | string;
  entry_lag: number;
  statistic: string;
  method: string;
  seed: number;
  resamples: number;
  valid_resamples: number;
  observed: number | null;
  quantiles: Record<string, number>;
  state: string;
  reason: string | null;
}

export interface ObservationRow {
  observation_id: string;
  entity_id: string;
  source_timestamp: string;
  generated_at: string | null;
  available_at: string;
  availability_assumed: boolean;
  raw_value: number | null;
  rank_value: number | null;
}

export interface RunComparison {
  a_id: number;
  b_id: number;
  comparability_warnings: string[];
  fields: Record<string, string>;
  horizon_rows: {
    horizon: string;
    entry_lag: number;
    a_spearman: number | null;
    b_spearman: number | null;
    a_spread: number | null;
    b_spread: number | null;
    presence: string;
  }[];
  metrics: Record<string, { a: number | null; b: number | null }>;
  baseline: { a: boolean; b: boolean };
  note: string;
}

export interface LabSummary {
  runs: number;
  completed: number;
  signals: number;
  observations: number;
  horizon_rows: number;
  overlapping_runs: number;
  baselines: number;
}

export interface RunFilters {
  status?: string;
  signal_type?: string;
  outcome_target_type?: string;
  integrity_status?: string;
  completeness_status?: string;
  overlap_status?: string;
  is_baseline?: boolean;
  query?: string;
  sort_by?: string;
  sort_dir?: string;
}

export const INTEGRITY_LABELS: Record<string, string> = {
  verified_from_validation_split: "Verified — validation split",
  verified_point_in_time: "Verified — point in time",
  verified_trailing_signal: "Verified — trailing signal",
  supplied_descriptive: "Supplied (descriptive)",
  full_sample_descriptive: "Full sample (descriptive)",
  unknown: "Unknown",
  invalid: "Invalid",
};

export const OVERLAP_LABELS: Record<string, string> = {
  non_overlapping: "Non-overlapping",
  partially_overlapping: "Partially overlapping",
  overlapping: "Overlapping",
  not_applicable: "n/a",
};

export const SIGNAL_TYPE_LABELS: Record<string, string> = {
  continuous_score: "Continuous score",
  probability: "Probability",
  rank: "Rank",
  ordinal_category: "Ordinal category",
  binary_indicator: "Binary indicator",
  user_supplied_descriptive: "User-supplied (descriptive)",
};

export const shortFp = (fp: string | null | undefined) => (fp ? fp.slice(0, 12) : "—");

export const fmtNum = (v: number | null | undefined, digits = 4) =>
  v === null || v === undefined || !Number.isFinite(v) ? "—" : v.toFixed(digits);

export const fmtPct = (v: number | null | undefined, digits = 3) =>
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
  request<{ items: RunSummary[]; total: number; page: number; total_pages: number }>(
    `/runs${q(params as Record<string, unknown>)}`,
  );
export const getRun = (id: number) => request<RunFull>(`/runs/${id}`);
export const getHorizons = (id: number) =>
  request<{ items: HorizonRow[] }>(`/runs/${id}/horizons`);
export const getBuckets = (id: number) =>
  request<{ items: BucketRow[] }>(`/runs/${id}/buckets`);
export const getTurnover = (id: number) =>
  request<{
    items: TurnoverRow[];
    summary: TurnoverSummary | null;
    holding_overlap: HoldingOverlapBlock | null;
  }>(`/runs/${id}/turnover`);
export const getObservations = (id: number) =>
  request<{ items: ObservationRow[] }>(`/runs/${id}/observations`);
export const getRegimes = (id: number) =>
  request<{ items: RegimeRow[]; rare_threshold: number }>(`/runs/${id}/regimes`);
export const getBootstrap = (id: number) =>
  request<{ items: BootstrapRow[] }>(`/runs/${id}/bootstrap`);
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
