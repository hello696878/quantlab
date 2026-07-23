/**
 * API client + types for the Transaction Cost, Slippage, Market Impact and
 * Capacity Diagnostics Lab (Phase 55.0).  Requests go to
 * /api/cost-diagnostics/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/cost-diagnostics";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "invalidated";
  observation_type: "trade" | "period";
  candidate_count: number;
  observation_count: number;
  currency: string | null;
  integrity_status: string;
  completeness_status: string;
  gross_total: number | null;
  net_total: number | null;
  total_cost: number | null;
  participation_warning_count: number;
  unavailable_input_count: number;
  universe_fingerprint: string;
  cost_model_fingerprint: string;
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
  regime_run_id: number | null;
  regime_definition_id: string | null;
  feature_diagnostics_run_id: number | null;
  meta_label_run_id: number | null;
  experiment_id: number | null;
  error_message: string | null;
}

export interface ComponentTotals {
  commission: number | null;
  spread: number | null;
  slippage: number | null;
  impact: number | null;
}

export interface Aggregates {
  observation_count: number;
  gross_total: number;
  net_total: number | null;
  total_cost: number | null;
  component_totals: ComponentTotals;
  component_unavailable_counts: Record<string, number>;
  cost_fraction_of_gross_magnitude: number | null;
  cost_fraction_of_traded_notional: number | null;
  total_traded_notional: number | null;
  notional_observation_count: number;
  total_turnover: number | null;
  turnover_observation_count: number;
  gross_stats: { mean: number | null; median: number | null; std: number | null; sharpe_like: number | null; positive_rate: number | null };
  net_stats: { mean: number | null; median: number | null; std: number | null; sharpe_like: number | null; positive_rate: number | null };
  net_observation_count: number;
  gross_positive_net_nonpositive_count: number;
  unavailable_cost_count: number;
  partial_result_count: number;
  gross_only_count: number;
  gross_candidate_matrix_fingerprint?: string | null;
  net_candidate_matrix_fingerprint?: string | null;
  note?: string;
}

export interface Breakeven {
  status: "available" | "unavailable";
  reason?: string;
  note: string;
  mean_breakeven_cost_per_observation?: number | null;
  aggregate_breakeven_bps_of_notional?: number | null;
  bps_reason?: string;
  max_cost_multiplier?: number | null;
  component_breakeven_multipliers?: Record<string, { multiplier: number | null; reason: string | null } | null>;
  breakeven_impact_coefficient?: number | null;
}

export interface RegimeRow {
  regime_label: string;
  observation_count: number;
  gross_total: number;
  total_cost: number;
  net_total: number | null;
  spread_total: number | null;
  slippage_total: number | null;
  impact_total: number | null;
  mean_participation: number | null;
  incomplete_input_count: number;
  rare_regime_warning: boolean;
}

export interface RegimeBlock {
  regime_run_id: number;
  regime_run_name: string;
  definition_id: string;
  definition_integrity: string;
  note: string;
  rows: RegimeRow[];
}

export interface RunFull extends RunSummary {
  description: string;
  configuration: Record<string, unknown>;
  observations: Record<string, unknown>[];
  aggregates: Aggregates | null;
  breakeven: Breakeven | null;
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
  overfitting_name: string | null;
  overfitting_pbo: number | null;
  overfitting_psr: number | null;
  overfitting_dsr: number | null;
  overfitting_universe_fp: string | null;
  regime_run_name: string | null;
  regime_run_integrity: string | null;
  feature_run_name: string | null;
  feature_run_integrity: string | null;
  meta_label_run_name: string | null;
}

export interface ObservationRow {
  observation_id: string;
  candidate_id: string;
  timestamp: string;
  side: string | null;
  quantity: number | null;
  traded_notional: number | null;
  turnover: number | null;
  gross_value: number;
  gross_return: number | null;
  commission_cost: number | null;
  spread_cost: number | null;
  slippage_cost: number | null;
  impact_cost: number | null;
  total_cost: number | null;
  net_value: number | null;
  net_return: number | null;
  completeness: string;
  participation: number | null;
  participation_status: string | null;
  breakeven_bps: number | null;
  regime_label: string | null;
  unavailable_components: string[];
  warnings: string[];
}

export interface SensitivityRow {
  scenario_index: number;
  is_base: boolean;
  commission_multiplier: number;
  spread_multiplier: number;
  slippage_multiplier: number;
  impact_multiplier: number;
  total_cost: number | null;
  net_total: number | null;
  net_positive_rate: number | null;
  gross_positive_net_nonpositive_count: number;
  unavailable_cost_count: number;
  fingerprint: string;
}

export interface CapacityRow {
  scale: number;
  is_base: boolean;
  traded_notional: number | null;
  mean_participation: number | null;
  max_participation: number | null;
  above_threshold_count: number;
  commission_total: number | null;
  spread_total: number | null;
  slippage_total: number | null;
  impact_total: number | null;
  total_cost: number | null;
  gross_total: number | null;
  net_total: number | null;
  unavailable_liquidity_count: number;
  excluded_count: number;
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
  fingerprint_match: Record<string, boolean>;
  baseline: Record<string, boolean>;
}

export interface LabSummary {
  runs: number;
  completed: number;
  observations: number;
  participation_warnings: number;
  incomplete_input_observations: number;
  baselines: number;
}

export interface RunFilters {
  status?: string;
  integrity_status?: string;
  completeness_status?: string;
  observation_type?: string;
  query?: string;
}

export const INTEGRITY_LABELS: Record<string, string> = {
  supplied_realized: "Supplied realized",
  verified_causal_input: "Verified causal inputs",
  verified_from_dataset_lineage: "Verified (dataset lineage)",
  declared: "Declared assumptions",
  full_sample_descriptive: "Full-sample descriptive",
  unknown: "Unknown",
  invalid: "Invalid",
};

export const COMPLETENESS_LABELS: Record<string, string> = {
  complete: "Complete",
  partial: "Partial",
  gross_only: "Gross only",
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
export const getObservations = (
  id: number,
  params: { candidate_id?: string; completeness?: string; page?: number; page_size?: number } = {},
) =>
  request<{ items: ObservationRow[]; total: number; page: number; total_pages: number }>(
    `/runs/${id}/observations${q(params as Record<string, unknown>)}`,
  );
export const getSensitivity = (id: number) =>
  request<{ items: SensitivityRow[] }>(`/runs/${id}/sensitivity`);
export const getCapacity = (id: number) =>
  request<{ items: CapacityRow[] }>(`/runs/${id}/capacity`);
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
