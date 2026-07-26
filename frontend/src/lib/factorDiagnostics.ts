/**
 * API client + types for the Factor Exposure, Return Decomposition and Macro
 * Sensitivity Diagnostics Lab (Phase 59.0).  Requests go to
 * /api/factor-diagnostics/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/factor-diagnostics";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed" | "invalidated";
  analysis_mode: string;
  regression_method: string;
  intercept_policy: string;
  rank_policy: string;
  timing_policy: string;
  vintage_policy: string;
  target_id: string;
  target_type: string;
  target_source: string;
  return_convention: string;
  return_frequency: string;
  currency: string;
  observation_start: string | null;
  observation_end: string | null;
  factor_count: number;
  observation_count: number;
  excluded_period_count: number;
  integrity_status: string;
  completeness_status: string;
  rank_status: string | null;
  reconciliation_status: string | null;
  r_squared: number | null;
  adjusted_r_squared: number | null;
  root_mean_squared_error: number | null;
  residual_std: number | null;
  intercept: number | null;
  condition_number: number | null;
  degrees_of_freedom: number | null;
  held_out_r_squared: number | null;
  target_fingerprint: string;
  observation_fingerprint: string;
  model_policy_fingerprint: string;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  is_baseline: boolean;
  error_message: string | null;
}

export interface FactorDefinition {
  factor_id: string;
  name: string;
  description: string;
  category: string;
  source: string;
  unit: string;
  transformed_unit: string;
  frequency: string;
  transformation: string;
  lag: number;
  availability_policy: string;
  missing_policy: string;
  standardisation_policy: string;
  standardisation_window: number | null;
  winsorisation_policy: string;
  definition_fingerprint: string;
}

export interface FitBlock {
  method: string;
  intercept_policy: string;
  observations: number;
  factors: number;
  parameters: number;
  degrees_of_freedom: number | null;
  residual_sum_of_squares: number;
  total_sum_of_squares: number;
  r_squared: number | null;
  adjusted_r_squared: number | null;
  r_squared_note: string | null;
  root_mean_squared_error: number | null;
  residual_mean: number | null;
  residual_std: number | null;
  rank: number | null;
  expected_rank: number;
  rank_status: string;
  rank_policy: string;
  standard_error_method: string | null;
  standard_error_assumptions: string | null;
  standard_error_state: string;
  standard_error_note: string | null;
  confidence_level: number | null;
  condition_number: number | null;
  condition_state: string;
  condition_note: string;
  singular_values: number[];
  constant_columns: string[];
  duplicate_columns: { factor_a: string; factor_b: string }[];
  ridge_lambda?: number | null;
  ridge_scaling?: string | null;
}

export interface SummaryBlock {
  periods_decomposed: number;
  periods_unavailable: number;
  measured_return_sum: number | null;
  intercept_contribution_sum: number | null;
  factor_contribution_sums: Record<string, number | null>;
  modelled_return_sum: number | null;
  residual_sum: number | null;
  reconciliation_difference: number | null;
  reconciliation_state: string;
  convention: string;
}

export interface VifRow {
  factor_id: string;
  vif: number | null;
  r_squared: number | null;
  state: string;
  reason: string | null;
  warning: boolean;
}

export interface MulticollinearityBlock {
  correlation: {
    factor_ids: string[];
    rows: { factor_id: string; values: (number | null)[] }[];
    constant_factors: string[];
    note: string;
  };
  vif: VifRow[];
  rank: number | null;
  expected_rank: number;
  rank_status: string;
  singular_values: number[];
  condition_number: number | null;
  condition_state: string;
  condition_note: string;
  constant_columns: string[];
  duplicate_columns: { factor_a: string; factor_b: string }[];
  note: string;
}

export interface ResidualBlock {
  observations: number;
  mean: number | null;
  std: number | null;
  skewness: number | null;
  excess_kurtosis: number | null;
  lag1_autocorrelation: number | null;
  largest_absolute: {
    period_start: string | null;
    residual: number;
    absolute_residual: number;
  }[];
  concentration: number | null;
  effective_periods: number | null;
  cumulative_drawdown: number | null;
  skewness_convention: string;
  kurtosis_convention: string;
  drawdown_convention: string;
  small_sample_note: string | null;
  note: string;
}

export interface StabilityRow {
  factor_id: string;
  windows_available: number;
  windows_total: number;
  availability_rate: number | null;
  mean: number | null;
  median: number | null;
  std: number | null;
  minimum: number | null;
  maximum: number | null;
  sign_changes: number | null;
  max_absolute_change: number | null;
  mean_absolute_change: number | null;
  note: string;
}

export interface ExposureComparisonRow {
  factor_id: string;
  portfolio_exposure: number | null;
  benchmark_exposure: number | null;
  active_exposure: number | null;
  portfolio_contribution: number | null;
  benchmark_contribution: number | null;
  active_contribution: number | null;
  note: string;
  benchmark_identity?: { benchmark_id: string; kind: string; source: string };
}

export interface HeldOutBlock {
  split_label: string | null;
  leakage_clean: boolean | null;
  training_observations: number;
  held_out_observations: number;
  purged_observations: number;
  embargoed_observations: number;
  training_r_squared: number | null;
  training_rmse: number | null;
  r_squared: number | null;
  rmse: number | null;
  correlation: number | null;
  residual_mean: number | null;
  residual_std: number | null;
  r_squared_formula: string;
  note: string;
  reason?: string;
}

export interface StressLinkageBlock {
  rows: {
    factor_id: string;
    shock: number | null;
    exposure: number | null;
    contribution: number | null;
    state: string;
  }[];
  total_contribution: number;
  residual_component: number | null;
  residual_note: string;
  formula: string;
  comparability_warning: string;
  stress_identity: Record<string, unknown>;
}

export interface AttributionLinkageBlock {
  attribution_run_id: number;
  attribution_run_name: string | null;
  column: string;
  measured_return_sum: number | null;
  modelled_return_sum: number | null;
  residual_sum: number | null;
  reconciliation_difference: number | null;
  note: string;
  cost_note: string;
}

export interface MultipleTestingBlock {
  methods: string[];
  alpha: number | null;
  family: string | null;
  hypotheses: number;
  rows: {
    factor_id: string;
    raw_p_value: number | null;
    bonferroni: number | null;
    holm: number | null;
    bh: number | null;
    state_raw: string;
    state_bonferroni: string;
    state_holm: string;
    state_bh: string;
    provenance_status: string;
  }[];
  note?: string;
  skipped?: string;
}

export interface RunFull extends RunSummary {
  configuration: Record<string, unknown>;
  factors: FactorDefinition[];
  target: Record<string, unknown> | null;
  policy: Record<string, unknown> | null;
  deferred: Record<string, unknown> | null;
  fit: FitBlock | null;
  summary: SummaryBlock | null;
  multicollinearity: MulticollinearityBlock | null;
  residual_diagnostics: ResidualBlock | null;
  stability: StabilityRow[];
  rolling_summary: {
    windows: number;
    estimated: number;
    rank_deficient: number;
    failed: number;
    condition_warnings: number;
    convention: string;
  } | null;
  exposure_comparison: ExposureComparisonRow[];
  held_out: HeldOutBlock | null;
  stress_linkage: StressLinkageBlock | null;
  attribution_linkage: AttributionLinkageBlock | null;
  multiple_testing: MultipleTestingBlock | null;
  warnings: string[];
  dataset_identity: Record<string, unknown>;
  portfolio_run_name: string | null;
  validation_run_name: string | null;
  validation_split_label: string | null;
  validation_leakage_clean: boolean | null;
  regime_run_name: string | null;
  stress_run_name: string | null;
}

export interface CoefficientRow {
  factor_id: string;
  coefficient: number | null;
  coefficient_unit: string | null;
  exposure_state: string;
  standard_error: number | null;
  t_statistic: number | null;
  p_value: number | null;
  p_bonferroni: number | null;
  p_holm: number | null;
  p_bh: number | null;
  confidence_lower: number | null;
  confidence_upper: number | null;
  contribution_sum: number | null;
  vif: number | null;
  vif_state: string | null;
  warning: string | null;
  unavailable_reason: string | null;
}

export interface PeriodRow {
  period_index: number;
  period_start: string;
  period_end: string | null;
  information_available_at: string | null;
  measured_return: number | null;
  intercept_contribution: number | null;
  modelled_return: number | null;
  residual: number | null;
  reconciliation_difference: number | null;
  reconciliation_state: string;
  exposure_state: string;
  regime_label: string | null;
  membership: string | null;
  factor_contributions: Record<string, number | null>;
  exposures: Record<string, number | null>;
  factor_values: Record<string, number | null>;
}

export interface ObservationRow {
  factor_id: string;
  period_index: number;
  observation_id: string;
  source_timestamp: string;
  available_at: string | null;
  effective_timestamp: string;
  knowable_at: string | null;
  release_timestamp: string | null;
  transformed_value: number | null;
  unit: string;
  quality_state: string;
  vintage_state: string;
}

export interface RollingRow {
  window_id: number;
  window_start: string;
  window_end: string;
  decision_timestamp: string | null;
  effective_timestamp: string | null;
  observations: number;
  intercept: number | null;
  r_squared: number | null;
  condition_number: number | null;
  rank: number | null;
  rank_status: string | null;
  status: string;
  reason: string | null;
  fingerprint: string | null;
  coefficients: Record<string, number>;
}

export interface RegimeRow {
  regime_label: string;
  definition_id: string | null;
  observations: number;
  rare: boolean;
  r_squared: number | null;
  condition_number: number | null;
  rank_status: string | null;
  intercept: number | null;
  residual_mean: number | null;
  residual_std: number | null;
  measured_return_sum: number | null;
  modelled_return_sum: number | null;
  residual_sum: number | null;
  completeness: string;
  status: string;
  reason: string | null;
  coefficients: Record<string, number>;
  contributions: Record<string, number | null>;
}

export interface SensitivityRow {
  scenario_index: number;
  label: string;
  is_base: boolean;
  description: string;
  observations: number | null;
  regression_method: string | null;
  intercept: number | null;
  r_squared: number | null;
  adjusted_r_squared: number | null;
  root_mean_squared_error: number | null;
  residual_std: number | null;
  condition_number: number | null;
  rank: number | null;
  rank_status: string | null;
  reconciliation_state: string | null;
  held_out_r_squared: number | null;
  status: string;
  reason: string | null;
  fingerprint: string | null;
  coefficients: Record<string, number>;
}

export interface RunComparison {
  a_id: number;
  b_id: number;
  comparability_warnings: string[];
  coefficients: {
    factor_id: string;
    a_coefficient: number | null;
    b_coefficient: number | null;
    difference: number | null;
    a_present: boolean;
    b_present: boolean;
  }[];
  metrics: Record<string, { a: number | null; b: number | null }>;
  fingerprint_match: Record<string, boolean>;
  baseline: { a: boolean; b: boolean };
  note: string;
}

export interface LabSummary {
  runs: number;
  completed: number;
  factors: number;
  observations: number;
  verified_runs: number;
  rank_deficient_runs: number;
  baselines: number;
}

export interface RunFilters {
  status?: string;
  analysis_mode?: string;
  regression_method?: string;
  integrity_status?: string;
  completeness_status?: string;
  rank_status?: string;
  timing_policy?: string;
  target_type?: string;
  is_baseline?: boolean;
  query?: string;
  sort_by?: string;
  sort_dir?: string;
}

export const INTEGRITY_LABELS: Record<string, string> = {
  verified_from_validation_split: "Verified — validation split",
  verified_causal_lag: "Verified — causal lag",
  verified_trailing_estimation: "Verified — trailing estimation",
  supplied_descriptive: "Supplied (descriptive)",
  contemporaneous_descriptive: "Contemporaneous (descriptive)",
  full_sample_descriptive: "Full sample (descriptive)",
  unknown: "Unknown",
  invalid: "Invalid",
};

export const MODE_LABELS: Record<string, string> = {
  time_series_regression: "Time-series regression",
  supplied_exposure_aggregation: "Supplied exposure aggregation",
};

export const TIMING_LABELS: Record<string, string> = {
  lagged_causal: "Lagged causal",
  contemporaneous: "Contemporaneous",
  full_sample_descriptive: "Full-sample descriptive",
  future_looking_invalid: "Future-looking (INVALID)",
};

export const RANK_LABELS: Record<string, string> = {
  full_rank: "Full rank",
  rank_deficient_descriptive: "Rank deficient (descriptive)",
};

export const shortFp = (fp: string | null | undefined) => (fp ? fp.slice(0, 12) : "—");

export const fmtNum = (v: number | null | undefined, digits = 6) =>
  v === null || v === undefined || !Number.isFinite(v)
    ? "—"
    : v.toFixed(digits);

export const fmtPct = (v: number | null | undefined, digits = 3) =>
  v === null || v === undefined || !Number.isFinite(v)
    ? "—"
    : `${(v * 100).toFixed(digits)}%`;

export const fmtSci = (v: number | null | undefined, digits = 3) => {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  if (v === 0) return "0";
  return Math.abs(v) < 1e-4 || Math.abs(v) >= 1e6
    ? v.toExponential(digits)
    : v.toFixed(digits + 2);
};

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
export const getCoefficients = (id: number) =>
  request<{ items: CoefficientRow[] }>(`/runs/${id}/coefficients`);
export const getPeriods = (id: number) =>
  request<{ items: PeriodRow[] }>(`/runs/${id}/periods`);
export const getObservations = (id: number, factorId?: string) =>
  request<{ items: ObservationRow[] }>(
    `/runs/${id}/observations${q({ factor_id: factorId })}`,
  );
export const getRolling = (id: number) =>
  request<{ items: RollingRow[]; summary: Record<string, unknown> | null }>(
    `/runs/${id}/rolling`,
  );
export const getStability = (id: number) =>
  request<{ items: StabilityRow[]; summary: Record<string, unknown> | null }>(
    `/runs/${id}/stability`,
  );
export const getRegimes = (id: number) =>
  request<{ items: RegimeRow[]; rare_threshold: number }>(`/runs/${id}/regimes`);
export const getSensitivity = (id: number) =>
  request<{ items: SensitivityRow[]; note: string }>(`/runs/${id}/sensitivity`);
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
