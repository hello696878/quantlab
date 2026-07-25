/**
 * API client + types for the Portfolio Stress Testing, Scenario Shock and
 * Drawdown Attribution Lab (Phase 57.0).  Requests go to
 * /api/portfolio-stress/* via the Next proxy.
 */

import { BacktestApiError } from "./api";

const BASE = "/api/portfolio-stress";

export interface RunSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed" | "invalidated";
  scenario_type: string;
  asset_count: number;
  scenario_count: number;
  integrity_status: string;
  completeness_status: string;
  scenario_return: number | null;
  scenario_pnl: number | null;
  stressed_volatility: number | null;
  baseline_volatility: number | null;
  breach_count: number;
  episode_count: number;
  max_drawdown: number | null;
  configuration_fingerprint: string;
  result_fingerprint: string | null;
  scenario_fingerprint: string;
  is_baseline: boolean;
  portfolio_run_id: number;
  portfolio_rebalance_id: number | null;
  portfolio_run_name: string | null;
  portfolio_method: string | null;
  dataset_version_id: number | null;
  dataset_name: string | null;
  dataset_version_label: string | null;
  regime_run_id: number | null;
  regime_run_name: string | null;
  cost_diagnostic_run_id: number | null;
  cost_run_name: string | null;
  cost_model_fingerprint: string | null;
  experiment_id: number | null;
  experiment_name: string | null;
  error_message: string | null;
}

export interface ReconciliationBlock {
  baseline_value: number;
  direct_shock_return: number | null;
  stressed_cost_return: number | null;
  stressed_cost_state?: string;
  stressed_cost_reason?: string | null;
  stressed_cost_completeness?: string | null;
  cost_basis_note?: string | null;
  net_scenario_return: number | null;
  net_basis_note?: string | null;
  scenario_pnl: number | null;
  risk_effect_note: string;
  completeness: string;
}

export interface RiskSummaryBlock {
  available?: boolean;
  reason?: string | null;
  stressed_note?: string | null;
  baseline_volatility: number | null;
  stressed_volatility: number | null;
  volatility_change: number | null;
  baseline_identity_ok: boolean | null;
  stressed_identity_ok: boolean | null;
  largest_pcr_increase: { asset_id: string; pcr_change: number } | null;
  largest_pcr_decrease: { asset_id: string; pcr_change: number } | null;
  note: string;
}

export interface CostEstimate {
  status: string;
  reason: string | null;
  components: Record<string, number | null> | null;
  component_reasons?: Record<string, string>;
  total_cost_return: number | null;
  total_cost_notional: number | null;
  completeness: string | null;
}

export interface CostStressBlock {
  reference_turnover: number;
  reference_note: string;
  base: CostEstimate | null;
  base_model_fingerprint: string | null;
  stressed: CostEstimate | null;
  stressed_model_fingerprint: string | null;
  participation: {
    participation: number | null;
    base_adv_notional?: number;
    adv_multiplier?: number;
    traded_notional?: number;
    threshold?: number;
    above_threshold?: boolean;
    reason?: string;
  } | null;
}

export interface DrawdownBlock {
  available: boolean;
  reason: string | null;
  convention: string | null;
  max_drawdown: number | null;
  episode_count: number;
  episodes_truncated?: boolean;
  series: { timestamps: string[]; wealth: number[]; drawdowns: number[] } | null;
  attribution: {
    episode_id: number;
    group_contributions: Record<string, number>;
    portfolio_contribution_sum: number;
    weight_policy: string;
    reconciliation_note: string;
  } | null;
}

export interface CovarianceStressBlock {
  available: boolean;
  reason: string | null;
  report: Record<string, unknown> | null;
  report_after_repair: Record<string, unknown> | null;
  repair: { repaired: boolean; policy: string; floor: number | null } | null;
  stressed_vols: number[] | null;
  stressed_correlation: number[][] | null;
  requested_vols?: number[] | null;
  requested_correlation?: number[][] | null;
  clamped: boolean | null;
}

export interface DriftedBlock {
  available: boolean;
  reason: string | null;
  cash_weight: number | null;
  note: string | null;
}

export interface RunFull extends RunSummary {
  configuration: Record<string, unknown> & {
    scenario?: Record<string, unknown>;
    notional?: number | null;
    execution_order?: string[];
    sensitivity?: Record<string, number[]>;
  };
  baseline_weight_fingerprint: string | null;
  baseline_covariance_fingerprint: string | null;
  stressed_covariance_fingerprint: string | null;
  reconciliation: ReconciliationBlock | null;
  risk_summary: RiskSummaryBlock | null;
  cost_stress: CostStressBlock | null;
  drawdown: DrawdownBlock | null;
  covariance_stress: CovarianceStressBlock | null;
  drifted: DriftedBlock | null;
  warnings: string[];
  completed_at: string | null;
  duration_ms: number | null;
  notes: string;
}

export interface AssetResultRow {
  asset_id: string;
  group: string | null;
  weight: number | null;
  shock: number | null;
  shock_source: string | null;
  contribution: number | null;
  abs_share: number | null;
  drifted_weight: number | null;
  status: string;
}

export interface RiskResultRow {
  asset_id: string;
  baseline_mcr: number | null;
  baseline_ccr: number | null;
  baseline_pcr: number | null;
  stressed_mcr: number | null;
  stressed_ccr: number | null;
  stressed_pcr: number | null;
  pcr_change: number | null;
  rank_change: number | null;
  state: string;
}

export interface ConstraintResultRow {
  book: string;
  constraint: string;
  detail: string;
  amount: number | null;
  asset_id: string | null;
}

export interface EpisodeRow {
  episode_id: number;
  peak_timestamp: string;
  peak_is_initial_capital: boolean;
  trough_timestamp: string;
  recovery_timestamp: string | null;
  depth: number;
  duration: number;
  recovery_duration: number | null;
  status: string;
}

export interface AttributionRow {
  asset_id: string;
  group: string | null;
  episode_id: number | null;
  contribution: number | null;
  average_weight: number | null;
  abs_share: number | null;
}

export interface SensitivityRow {
  scenario_index: number;
  dimension: string;
  value: number | null;
  is_base: boolean;
  scenario_return: number | null;
  stressed_volatility: number | null;
  contribution_hhi: number | null;
  breach_count: number;
  cost_return: number | null;
  completeness: string | null;
  status: string;
  reason: string | null;
  fingerprint: string;
}

export interface ScenarioBlock {
  scenario_definition_id: string;
  name: string;
  description: string;
  scenario_type: string;
  source: string;
  integrity_status: string;
  fingerprint: string;
  definition: Record<string, unknown>;
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
  contributions: { asset_id: string; availability: string;
                   a_contribution: number | null;
                   b_contribution: number | null }[];
  fingerprint_match: Record<string, boolean>;
  baseline: Record<string, boolean>;
}

export interface LabSummary {
  runs: number;
  completed: number;
  scenarios: number;
  constraint_breaches: number;
  drawdown_episodes: number;
  baselines: number;
}

export interface RunFilters {
  status?: string;
  integrity_status?: string;
  completeness_status?: string;
  scenario_type?: string;
  query?: string;
}

export const SCENARIO_TYPE_LABELS: Record<string, string> = {
  historical_window: "Historical window",
  historical_single_period: "Historical single period",
  hypothetical_asset_shock: "Asset shock",
  hypothetical_group_shock: "Group shock",
  volatility_stress: "Volatility stress",
  correlation_stress: "Correlation stress",
  liquidity_and_cost_stress: "Liquidity / cost stress",
  combined_scenario: "Combined scenario",
  user_supplied_descriptive: "User-supplied (descriptive)",
};

export const INTEGRITY_LABELS: Record<string, string> = {
  verified_historical_window: "Verified historical window",
  verified_deterministic_rule: "Verified deterministic rule",
  supplied_descriptive: "Supplied (descriptive)",
  full_sample_descriptive: "Full-sample descriptive",
  unknown: "Unknown",
  invalid: "Invalid",
};

export const shortFp = (fp: string | null | undefined) => (fp ? fp.slice(0, 12) : "—");

export const fmtPct = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;

export const fmtNum = (v: number | null | undefined, digits = 4) =>
  v === null || v === undefined ? "—" : v.toFixed(digits);

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
export const getScenario = (id: number) =>
  request<{ scenario: ScenarioBlock | null }>(`/runs/${id}/scenario`);
export const getAssetResults = (id: number) =>
  request<{ items: AssetResultRow[] }>(`/runs/${id}/asset-results`);
export const getRiskResults = (id: number) =>
  request<{ items: RiskResultRow[] }>(`/runs/${id}/risk-results`);
export const getConstraintResults = (id: number) =>
  request<{ items: ConstraintResultRow[] }>(`/runs/${id}/constraint-results`);
export const getEpisodes = (id: number) =>
  request<{ items: EpisodeRow[] }>(`/runs/${id}/episodes`);
export const getAttribution = (id: number) =>
  request<{ items: AttributionRow[] }>(`/runs/${id}/attribution`);
export const getSensitivity = (id: number) =>
  request<{ items: SensitivityRow[] }>(`/runs/${id}/sensitivity`);
export const markBaseline = (id: number) =>
  request<RunFull>(`/runs/${id}/mark-baseline`, { method: "POST", body: "{}" });
export const compareRuns = (a: number, b: number) =>
  request<RunComparison>(`/compare${q({ a, b })}`);
export const exportRuns = (filters: RunFilters = {}) =>
  request<Record<string, unknown>>(`/export${q(filters as Record<string, unknown>)}`);
export const seedDemo = () =>
  request<{ created: boolean; created_count: number; skipped_count: number; run_ids: number[] }>(
    "/demo-seed", { method: "POST", body: "{}" });
