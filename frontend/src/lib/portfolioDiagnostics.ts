/**
 * API client + types for the Portfolio Construction, Risk Budgeting,
 * Diversification and Constraint Diagnostics Lab (Phase 56.0).  Requests go
 * to /api/portfolio-diagnostics/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/portfolio-diagnostics";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "invalidated";
  method: string;
  covariance_method: string;
  asset_count: number;
  observation_count: number;
  rebalance_count: number;
  integrity_status: string;
  solver_status: string | null;
  portfolio_volatility: number | null;
  effective_positions: number | null;
  max_budget_deviation: number | null;
  mean_turnover: number | null;
  constraint_violation_count: number;
  universe_fingerprint: string;
  constraint_fingerprint: string;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  is_baseline: boolean;
  dataset_version_id: number | null;
  dataset_name: string | null;
  dataset_version_label: string | null;
  dataset_invalidated: boolean | null;
  validation_run_id: number | null;
  validation_method: string | null;
  regime_run_id: number | null;
  regime_definition_id: string | null;
  cost_diagnostic_run_id: number | null;
  overfitting_run_id: number | null;
  experiment_id: number | null;
  error_message: string | null;
}

export interface RiskBlock {
  variance: number;
  volatility: number;
  mcr: number[] | null;
  ccr: number[] | null;
  pcr: number[] | null;
  identity_ok: boolean | null;
  note: string | null;
}

export interface BudgetRow {
  asset_id: string;
  target_budget: number | null;
  measured_pcr: number | null;
  abs_difference: number | null;
  signed_difference: number | null;
  relative_difference: number | null;
  state: string;
}

export interface BudgetBlock {
  rows: BudgetRow[];
  max_abs_deviation: number | null;
  mean_abs_deviation: number | null;
  rms_deviation: number | null;
  within_tolerance_count: number | null;
  tolerance: number;
  target_sum: number | null;
  measured_sum: number | null;
}

export interface ConcentrationBlock {
  weight_hhi: number | null;
  effective_positions: number | null;
  max_abs_weight: number | null;
  top3_abs_weight_share: number | null;
  risk_contribution_hhi: number | null;
  effective_risk_contributors: number | null;
  avg_pairwise_correlation: number | null;
  median_pairwise_correlation: number | null;
  max_pairwise_correlation: number | null;
  diversification_ratio: number | null;
}

export interface CovarianceBlock {
  matrix: number[][];
  correlation: number[][] | null;
  report: Record<string, unknown> & { warnings?: string[]; psd?: boolean; condition_number?: number | null; min_eigenvalue?: number | null };
  report_after_repair: Record<string, unknown>;
  repair: { repaired: boolean; policy: string; floor: number | null;
            original_eigenvalues: number[] | null;
            repaired_eigenvalues: number[] | null };
  window: [number, number];
}

export interface RegimeRow {
  regime_label: string;
  observation_count: number;
  mean_return: number;
  return_std: number | null;
  cumulative_return: number;
  rebalance_count: number;
  mean_turnover: number | null;
  cost_completeness: string[] | null;
  rare_regime_warning: boolean;
}

export interface RegimeBlock {
  regime_run_id: number;
  regime_run_name: string;
  definition_id: string;
  definition_integrity: string;
  run_max_budget_deviation: number | null;
  note: string;
  rows: RegimeRow[];
}

export interface RunFull extends RunSummary {
  description: string;
  configuration: Record<string, unknown>;
  universe: { timestamps: string[]; frequency: string;
              assets: { asset_id: string; name: string; group: string | null }[] };
  risk: RiskBlock | null;
  budget: BudgetBlock | null;
  concentration: ConcentrationBlock | null;
  covariance: CovarianceBlock | null;
  regimes: RegimeBlock | null;
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
  regime_run_name: string | null;
  regime_run_integrity: string | null;
  cost_run_name: string | null;
  cost_model_fingerprint: string | null;
  overfitting_name: string | null;
  overfitting_pbo: number | null;
  overfitting_universe_fp: string | null;
}

export interface WeightRow {
  asset_id: string;
  raw_weight: number | null;
  weight: number | null;
  lower_bound: number | null;
  upper_bound: number | null;
  group: string | null;
  constraint_status: string;
}

export interface ContributionRow {
  asset_id: string;
  weight: number | null;
  mcr: number | null;
  ccr: number | null;
  pcr: number | null;
  target_budget: number | null;
  abs_difference: number | null;
  signed_difference: number | null;
  state: string;
}

export interface RebalanceRow {
  rebalance_id: number;
  decision_timestamp: string;
  effective_timestamp: string | null;
  window_start: number | null;
  window_end: number | null;
  turnover: number | null;
  gross_change: number | null;
  solver_status: string | null;
  constraint_violation_count: number;
  covariance_fingerprint: string | null;
  weight_fingerprint: string | null;
  weights: Record<string, number> | null;
  prior_weights: Record<string, number> | null;
  solver: Record<string, unknown>;
  constraint_violations: { constraint: string; detail: string; amount: number; asset_id: string | null }[];
  cost: { status: string; total_cost_return: number | null; total_cost_notional: number | null; completeness: string | null; components: Record<string, number | null> | null; component_reasons?: Record<string, string> } | null;
  status: string;
  reason: string | null;
}

export interface SensitivityRow {
  scenario_index: number;
  dimension: string;
  value: number | null;
  is_base: boolean;
  portfolio_volatility: number | null;
  effective_positions: number | null;
  max_budget_deviation: number | null;
  turnover: number | null;
  solver_status: string | null;
  constraint_violation_count: number;
  cost_return: number | null;
  status: string;
  reason: string | null;
  fingerprint: string;
}

export interface AssetRow {
  asset_index: number;
  asset_id: string;
  name: string;
  asset_type: string;
  group: string | null;
  currency: string | null;
  volatility: number | null;
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
  weights: { asset_id: string; availability: string; a_weight: number | null;
             b_weight: number | null; difference: number | null }[];
  fingerprint_match: Record<string, boolean>;
  baseline: Record<string, boolean>;
}

export interface LabSummary {
  runs: number;
  completed: number;
  assets: number;
  constraint_violations: number;
  solver_failures: number;
  baselines: number;
}

export interface RunFilters {
  status?: string;
  integrity_status?: string;
  solver_status?: string;
  method?: string;
  query?: string;
}

export const INTEGRITY_LABELS: Record<string, string> = {
  verified_from_validation_split: "Verified (training split)",
  verified_causal_rolling: "Verified causal window",
  declared: "Declared",
  full_sample_descriptive: "Full-sample descriptive",
  unknown: "Unknown",
  invalid: "Invalid",
};

export const METHOD_LABELS: Record<string, string> = {
  user_supplied: "User-supplied",
  equal_weight: "Equal weight",
  inverse_volatility: "Inverse volatility",
  erc: "Equal risk contribution",
  min_variance: "Minimum variance",
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
export const getAssets = (id: number) =>
  request<{ items: AssetRow[] }>(`/runs/${id}/assets`);
export const getWeights = (id: number) =>
  request<{ items: WeightRow[] }>(`/runs/${id}/weights`);
export const getRiskContributions = (id: number) =>
  request<{ items: ContributionRow[] }>(`/runs/${id}/risk-contributions`);
export const getRebalances = (id: number) =>
  request<{ items: RebalanceRow[] }>(`/runs/${id}/rebalances`);
export const getSensitivity = (id: number) =>
  request<{ items: SensitivityRow[] }>(`/runs/${id}/sensitivity`);
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
