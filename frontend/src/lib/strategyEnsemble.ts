import { BacktestApiError } from "./api";

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export interface RunSummary {
  id: number; name: string; status: "created" | "completed" | "failed" | "invalidated";
  is_baseline: boolean; error_message: string | null; created_at: string;
}
export interface Definition {
  strategy_id: string; strategy_name: string; source_type: "supplied";
  source_run_id: string | null; source_fingerprint: string; configuration_fingerprint: string;
  dataset_identity: string; dataset_version_id: number | null; return_convention: "simple_arithmetic";
  gross_or_net: "gross" | "net_of_strategy_costs" | "partially_costed" | "unknown";
  frequency: "daily" | "weekly" | "monthly" | "hourly" | "irregular"; currency: string;
  leverage_convention: "already_in_returns" | "unlevered" | "unknown";
  exposure_convention: "strategy_return_weight"; availability_policy: "outcome_at_or_after_period_end";
  configuration_available_at: string; observation_start: string; observation_end: string;
  metadata: Record<string, string>;
}
export interface WealthPeriod {
  period_start: string; period_end: string; return_value: number; wealth: number;
  running_peak: number; drawdown: number;
}
export interface Drawdowns {
  periods: WealthPeriod[]; episodes: Json[]; max_drawdown: number | null; compounded_return: number | null;
}
export interface Weights {
  original: Record<string, number>; effective: Record<string, number>;
  sum: number; gross: number; net: number; max_absolute_weight: number;
  zero_weight_strategies: string[]; normalization_residual: number | null;
}
export interface Ensemble {
  weights: Weights; n: number;
  periods: { period_start: string; period_end: string; contributions: Record<string, number>; ensemble_return: number; residual: number }[];
  contribution_summary: { strategy_id: string; arithmetic_contribution: number; share: number | null; positive_periods: number; negative_periods: number; absolute_share: number | null }[];
  absolute_contribution_concentration: number | null; reconciliation_max_residual: number;
  arithmetic_sum: number; arithmetic_geometric_gap: number | null;
  mean_return: number | null; volatility_per_period: number | null; drawdown: Drawdowns;
  turnover: { initial_allocation: number | null; subsequent_target_weight_change: number; executed_rebalance_turnover: number | null; underlying: Json[] };
  costs: { basis: string; completeness: string; allocation_cost: number | null; underlying_cost_deducted_again: boolean;
    gross_ensemble_reference: number | null; net_of_strategy_costs_reference: number | null; fully_net_ensemble: number | null; reason: string };
}
export interface Correlation { value: number | null; p_value: number | null; reason: string | null }
export interface Pair {
  strategy_a: string; strategy_b: string; n: number; alignment: string;
  correlations: { pearson: Correlation; spearman: Correlation };
  covariance: number | null; covariance_units: string; sign_agreement: number | null;
  simultaneous_loss_count: number; simultaneous_gain_count: number; positive_agreement: number | null;
  negative_agreement: number | null; opposite_sign_count: number; joint_loss_rate: number | null;
  mean_absolute_difference: number | null;
  empirical_lower_tail_overlap: { state: string; reason: string | null; jaccard?: number | null; joint_count?: number; quantile?: number; ties?: string; threshold_a?: number; threshold_b?: number; b_given_a?: number | null; a_given_b?: number | null; opposite_tail_rate?: number };
  drawdown_overlap: { simultaneous_periods: number; state_agreement: number | null; severe_periods: number; deepest_episode_overlap: number; loss_period_overlap: number };
}
export interface Matrix {
  strategy_ids: string[]; n: number; method: string; sample: string;
  values: number[][] | null; eigenvalues: number[] | null; rank: number | null; condition: number | null;
  effective_strategy_count: number | null; mean_absolute_correlation: number | null;
  maximum_absolute_correlation: number | null; psd_tolerance: number; state: string; reason: string | null;
}
export interface Results {
  definition_fingerprints: Record<string, string>;
  coverage: { strict_intersection_periods: number; union_periods: number; gaps: number; exclusion_reason: string;
    strategies: { strategy_id: string; stored_periods: number; missing_periods: number; excluded_periods: number; coverage_ratio: number }[] };
  pairwise: Pair[]; matrix: Matrix; strategy_drawdowns: Record<string, Drawdowns>;
  ensemble: Ensemble; baseline_eligible: boolean; integrity: string; warnings: string[];
  regimes: { label: string; n: number; rare: boolean; minimum: number; integrity: string;
    statistics: { mean_return: number | null; volatility_per_period: number | null; contributions: Ensemble["contribution_summary"];
      minimum_observed_full_path_drawdown: number; drawdown_periods: number; pairwise: Pair[]; matrix: Matrix } | null }[];
  validation: { state: "unavailable"; reason: string } | { state: "available"; split_label: string; reason: string;
    training: ValidationBlock; held_out: ValidationBlock; memberships: Record<string, string[]>; weights_frozen: boolean; full_sample_descriptive: number | null };
  multiple_testing: Json; deferred: Record<string, string>;
  sensitivity: { label: string; is_base: boolean; fingerprint: string; policy: Json; weights: Weights; n: number;
    mean_return: number | null; volatility_per_period: number | null; compounded_return: number | null;
    max_drawdown: number | null; concentration: number | null; mean_absolute_correlation: number | null;
    turnover: Ensemble["turnover"]; costs: Ensemble["costs"] }[];
}
export interface ValidationBlock {
  sample_ids: string[]; n: number; mean_return: number | null; volatility_per_period: number | null;
  drawdown: Drawdowns; weights: Record<string, number>;
}
export interface Run extends RunSummary {
  updated_at: string; request: { name: string; definitions: Definition[]; observations: Json[]; policy: Json; analysis: Json; weights_available_at: string; [key: string]: unknown };
  links: Json; results: Results | null; fingerprints: Record<string, string>;
  experiment_id: number | null; experiment_requested: number;
}
export interface Listing { items: RunSummary[]; total: number; page: number; page_size: number }
export interface Comparison {
  comparable_inputs: boolean; reason: string;
  runs: { id: number; name: string; fingerprints: Record<string, string>; ensemble: Pick<Ensemble, "n" | "weights" | "mean_return" | "volatility_per_period" | "costs"> }[];
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  try {
    let res: Response;
    try {
      res = await fetch(`/api/strategy-ensembles${path}`, {
        method: body === undefined ? "GET" : "POST", cache: "no-store", signal: controller.signal,
        headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new BacktestApiError(0, "Local backend unavailable or request timed out. Saved runs remain in SQLite.");
    }
    if (!res.ok) {
      let message = res.status >= 500 ? "Local backend unavailable. Please retry." : `Request failed (HTTP ${res.status}).`;
      try {
        const data = await res.json();
        if (res.status < 500 && typeof data.detail === "string") message = data.detail;
        else if (res.status === 422 && Array.isArray(data.detail)) {
          message = data.detail.map((e: { loc?: unknown[]; msg?: string }) => `${e.loc?.join(".") ?? "Input"}: ${e.msg ?? "Invalid value"}`).join("; ");
        }
      } catch { /* Preserve the friendly fallback for non-JSON proxy errors. */ }
      throw new BacktestApiError(res.status, message);
    }
    return await res.json() as T;
  } finally { clearTimeout(timer); }
}

export const listRuns = (page = 1) => request<Listing>(`/runs?page=${page}&page_size=25`);
export const getRun = (id: number) => request<Run>(`/runs/${id}`);
export const createRun = (body: unknown) => request<Run>("/runs", body);
export const executeRun = (id: number, createExperiment = false) => request<Run>(`/runs/${id}/execute`, { create_experiment: createExperiment });
export const markBaseline = (id: number) => request<Run>(`/runs/${id}/mark-baseline`, {});
export const invalidateRun = (id: number, reason: string) => request<Run>(`/runs/${id}/invalidate`, { reason });
export const seedDemo = () => request<{ created_count: number; skipped_count: number; run_ids: number[] }>("/demo-seed", {});
export const compareRuns = (a: number, b: number) => request<Comparison>(`/compare?a=${a}&b=${b}`);
export const exportRun = (id: number) => request<Json>(`/export?run_id=${id}`);
export const number = (v: number | null | undefined, digits = 4) => v == null || !Number.isFinite(v) ? "Unavailable" : v.toLocaleString("en-US", { maximumFractionDigits: digits });
export const percent = (v: number | null | undefined) => v == null || !Number.isFinite(v) ? "Unavailable" : `${number(v * 100, 2)}%`;
