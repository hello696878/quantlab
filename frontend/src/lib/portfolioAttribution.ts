/**
 * API client + types for the Portfolio Performance Attribution, Benchmark
 * and Active Risk Lab (Phase 58.0).  Requests go to
 * /api/portfolio-attribution/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/portfolio-attribution";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed" | "invalidated";
  attribution_method: string;
  brinson_variant: string | null;
  linking_method: string;
  return_convention: string;
  return_frequency: string;
  weight_timing_policy: string;
  benchmark_timing_policy: string;
  observation_start: string | null;
  observation_end: string | null;
  asset_count: number;
  group_count: number;
  period_count: number;
  integrity_status: string;
  completeness_status: string;
  reconciliation_status: string;
  portfolio_market_return: number | null;
  portfolio_net_return: number | null;
  benchmark_return: number | null;
  active_return: number | null;
  total_cost_return: number | null;
  tracking_error: number | null;
  information_ratio: number | null;
  observation_fingerprint: string;
  policy_fingerprint: string;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  is_baseline: boolean;
  portfolio_run_id: number;
  portfolio_run_name: string | null;
  portfolio_method: string | null;
  benchmark_name: string | null;
  dataset_name: string | null;
  dataset_version_label: string | null;
  dataset_invalidated: boolean | null;
  cost_run_name: string | null;
  cost_model_fingerprint: string | null;
  regime_run_name: string | null;
  stress_run_name: string | null;
  validation_run_name: string | null;
  validation_leakage_clean: boolean | null;
  experiment_id: number | null;
  experiment_name: string | null;
  error_message: string | null;
}

export interface LinkingBlock {
  method: string;
  period_count: number;
  arithmetic_active_return: number | null;
  compounded_portfolio_return: number | null;
  compounded_benchmark_return: number | null;
  geometric_active_return: number | null;
  arithmetic_effects: Record<string, number>;
  arithmetic_explained: number;
  arithmetic_vs_geometric_gap: number | null;
  arithmetic_caveat: string;
  linked_effects: Record<string, number> | null;
  linked_explained: number | null;
  linked_target: number | null;
  linking_residual: number | null;
  linked_residual_term?: number | null;
  linked_total_including_residual?: number | null;
  closure_residual?: number | null;
  closure_note?: string;
  within_tolerance: boolean | null;
  smoothing_factors: number[] | null;
  total_scaling_factor?: number;
  available: boolean;
  reason: string | null;
  carino_note?: string;
}

export interface CostBlock {
  total_cost_return: number | null;
  component_totals: Record<string, number | null>;
  component_states: Record<string, "complete" | "partial" | "unavailable">;
  gross_market_return_all_periods: number;
  gross_market_return_costed_periods: number;
  net_return_costed_periods: number | null;
  costed_period_count: number;
  traded_period_count: number;
  unavailable_period_count: number;
  completeness: string;
  basis_note: string;
  source_note: string;
  stress_note: string;
}

export interface ActiveRiskBlock {
  observation_count: number;
  mean_active_return: number | null;
  arithmetic_active_return: number | null;
  frequency: string;
  periods_per_year: number | null;
  std_convention: string;
  active_return_std: number | null;
  tracking_error: number | null;
  annualized_tracking_error: number | null;
  annualization_note?: string;
  downside_active_deviation: number | null;
  positive_active_rate: number | null;
  negative_active_rate: number | null;
  hit_rate: number | null;
  hit_rate_definition?: string;
  information_ratio: number | null;
  information_ratio_state: string;
  information_ratio_reason: string | null;
  information_ratio_definition?: string;
  note: string;
}

export interface ConcentrationBlock {
  label: string;
  count: number;
  herfindahl: number | null;
  effective_contributors: number | null;
  largest_absolute_share: number | null;
  top3_absolute_share: number | null;
  positive_total: number;
  negative_total: number;
  positive_concentration?: number | null;
  negative_concentration?: number | null;
  state: string;
  reason: string | null;
  note: string;
}

export interface ActiveDrawdownBlock {
  available: boolean;
  reason: string | null;
  max_active_drawdown: number | null;
  series: { wealth: number[]; drawdowns: number[] } | null;
  convention?: string;
}

export interface SummaryBlock {
  portfolio_market_return_arithmetic: number;
  benchmark_return_arithmetic: number | null;
  active_return_arithmetic: number | null;
  asset_contribution_sum: number;
  group_contribution_sum: number;
  contribution_reconciled: boolean;
  group_reconciled: boolean;
  brinson_reconciled: boolean | null;
  tolerance: number;
  time_weighted_return: { available: boolean; value: number | null;
                          reason: string | null; convention: string | null };
  benchmark_time_weighted_return: { available: boolean; value: number | null;
                                    reason: string | null;
                                    convention: string | null } | null;
  active_drawdown: ActiveDrawdownBlock | null;
  group_concentration: ConcentrationBlock | null;
  period_concentration: ConcentrationBlock | null;
  regime_note: string | null;
  execution_order: string[];
}

export interface RunFull extends RunSummary {
  configuration: Record<string, unknown> & {
    execution_order?: string[];
    benchmark?: Record<string, unknown>;
    policy?: Record<string, unknown>;
    factor_attribution?: string;
    scope_note?: string;
  };
  summary: SummaryBlock | null;
  linking: LinkingBlock | null;
  cost: CostBlock | null;
  active_risk: ActiveRiskBlock | null;
  concentration: ConcentrationBlock | null;
  warnings: string[];
}

export interface PeriodRow {
  period_id: number;
  period_start: string;
  period_end: string;
  information_available_at: string;
  portfolio_market_return: number | null;
  transaction_cost_return: number | null;
  cost_state: string | null;
  portfolio_net_return: number | null;
  benchmark_return: number | null;
  active_return: number | null;
  allocation_effect: number | null;
  selection_effect: number | null;
  interaction_effect: number | null;
  residual: number | null;
  reconciliation_state: string | null;
  cash_weight: number | null;
  regime_label: string | null;
}

export interface AssetRow {
  asset_id: string;
  group_id: string | null;
  average_weight: number | null;
  arithmetic_contribution: number | null;
  linked_contribution: number | null;
  positive_contribution: number | null;
  negative_contribution: number | null;
  absolute_contribution: number | null;
  absolute_share: number | null;
  signed_share: number | null;
  observation_count: number;
}

export interface GroupRow {
  group_id: string;
  asset_count: number;
  average_weight: number | null;
  arithmetic_contribution: number | null;
  linked_contribution: number | null;
  positive_contribution: number | null;
  negative_contribution: number | null;
  absolute_contribution: number | null;
  absolute_share: number | null;
  signed_share: number | null;
}

export interface BrinsonRow {
  group_id: string;
  presence: string | null;
  average_portfolio_weight: number | null;
  average_benchmark_weight: number | null;
  allocation_effect: number | null;
  selection_effect: number | null;
  interaction_effect: number | null;
  total_effect: number | null;
  linked_allocation_effect: number | null;
  linked_selection_effect: number | null;
  linked_interaction_effect: number | null;
  unavailable_periods: number;
}

export interface RegimeRow {
  regime_label: string;
  observation_count: number;
  portfolio_market_return: number | null;
  benchmark_return: number | null;
  active_return: number | null;
  cost_return: number | null;
  net_return: number | null;
  allocation_effect: number | null;
  selection_effect: number | null;
  interaction_effect: number | null;
  tracking_error: number | null;
  contribution_herfindahl: number | null;
  completeness: string | null;
  rare_regime_warning: boolean;
}

export interface DrawdownRow {
  episode_id: number;
  peak_timestamp: string | null;
  trough_timestamp: string | null;
  recovery_timestamp: string | null;
  period_count: number;
  portfolio_market_return: number | null;
  benchmark_return: number | null;
  active_return: number | null;
  cost_return: number | null;
  allocation_effect: number | null;
  selection_effect: number | null;
  interaction_effect: number | null;
  residual: number | null;
  reconciliation_state: string | null;
  contributions: { asset_id: string; contribution: number }[];
}

export interface BenchmarkBlock {
  benchmark_id: string;
  name: string;
  description: string;
  source: string;
  kind: string;
  return_convention: string;
  timing_policy: string;
  asset_count: number;
  weight_sum: number | null;
  definition: Record<string, unknown>;
  fingerprint: string;
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
  brinson: { group_id: string; availability: string;
             a_allocation: number | null; b_allocation: number | null;
             a_selection: number | null; b_selection: number | null;
             a_interaction: number | null; b_interaction: number | null }[];
  contributions: { asset_id: string; availability: string;
                   a_contribution: number | null;
                   b_contribution: number | null }[];
  fingerprint_match: Record<string, boolean>;
  baseline: Record<string, boolean>;
  note?: string;
}

export interface LabSummary {
  runs: number;
  completed: number;
  periods: number;
  benchmarked_runs: number;
  reconciled_runs: number;
  baselines: number;
}

export interface RunFilters {
  status?: string;
  integrity_status?: string;
  completeness_status?: string;
  reconciliation_status?: string;
  attribution_method?: string;
  linking_method?: string;
  query?: string;
}

export const INTEGRITY_LABELS: Record<string, string> = {
  verified_from_stored_rebalance: "Verified (stored rebalance)",
  verified_causal_weights: "Verified causal weights",
  supplied_descriptive: "Supplied (descriptive)",
  full_sample_descriptive: "Full-sample descriptive",
  unknown: "Unknown",
  invalid: "Invalid",
};

export const METHOD_LABELS: Record<string, string> = {
  brinson: "Brinson",
  contribution_only: "Contribution only",
};

export const VARIANT_LABELS: Record<string, string> = {
  brinson_fachler: "Brinson-Fachler",
  brinson_hood_beebower: "Brinson-Hood-Beebower",
};

export const LINKING_LABELS: Record<string, string> = {
  arithmetic: "Arithmetic (reference)",
  carino: "Carino (geometric)",
};

export const shortFp = (fp: string | null | undefined) => (fp ? fp.slice(0, 12) : "—");

export const fmtPct = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined || !Number.isFinite(v)
    ? "—"
    : `${(v * 100).toFixed(digits)}%`;

export const fmtBps = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined || !Number.isFinite(v)
    ? "—"
    : `${(v * 10000).toFixed(digits)} bps`;

export const fmtNum = (v: number | null | undefined, digits = 4) =>
  v === null || v === undefined || !Number.isFinite(v) ? "—" : v.toFixed(digits);

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
export const getBenchmark = (id: number) =>
  request<{ benchmark: BenchmarkBlock | null }>(`/runs/${id}/benchmark`);
export const getPeriods = (id: number) =>
  request<{ items: PeriodRow[] }>(`/runs/${id}/periods`);
export const getAssets = (id: number) =>
  request<{ items: AssetRow[] }>(`/runs/${id}/assets`);
export const getGroups = (id: number) =>
  request<{ items: GroupRow[] }>(`/runs/${id}/groups`);
export const getBrinson = (id: number) =>
  request<{ items: BrinsonRow[] }>(`/runs/${id}/brinson`);
export const getRegimes = (id: number) =>
  request<{ items: RegimeRow[]; note: string | null }>(`/runs/${id}/regimes`);
export const getDrawdowns = (id: number) =>
  request<{ items: DrawdownRow[] }>(`/runs/${id}/drawdowns`);
export const markBaseline = (id: number) =>
  request<RunFull>(`/runs/${id}/mark-baseline`, { method: "POST", body: "{}" });
export const compareRuns = (a: number, b: number) =>
  request<RunComparison>(`/compare${q({ a, b })}`);
export const exportRuns = (filters: RunFilters = {}) =>
  request<Record<string, unknown>>(`/export${q(filters as Record<string, unknown>)}`);
export const seedDemo = () =>
  request<{ created: boolean; created_count: number; skipped_count: number;
            run_ids: number[] }>("/demo-seed", { method: "POST", body: "{}" });
