import type { RebalanceRow, RunFull as PortfolioRun } from "@/lib/portfolioDiagnostics";
import type { RunFull } from "@/lib/portfolioStress";

// Deliberately small API doubles: only fields consumed by these UI workflows.
export const portfolio = {
  id: 11, name: "Stored research portfolio", status: "completed", integrity_status: "full_sample_descriptive",
  universe: { timestamps: ["2024-01-01", "2024-02-01"], frequency: "daily",
    assets: [{ asset_id: "a", name: "Asset A", group: null, returns: [0.01, -0.005] },
      { asset_id: "b", name: "Asset B", group: null, returns: [0.002, 0.004] }] },
  warnings: ["Supplied observations; not a market-data certification."],
} as PortfolioRun;

const rebalanceDefaults = {
  window_start: 0, window_end: 20, turnover: null, gross_change: null, solver_status: "solved",
  constraint_violation_count: 0, weight_fingerprint: null, prior_weights: null,
  solver: {}, constraint_violations: [], cost: null, status: "solved", reason: null,
};

export const rebalances: RebalanceRow[] = [
  { ...rebalanceDefaults, rebalance_id: 2, decision_timestamp: "2024-01-01T00:00:00", effective_timestamp: "2024-01-02T00:00:00",
    weights: { a: 1.2, b: -0.2 }, covariance_fingerprint: null },
  { ...rebalanceDefaults, rebalance_id: 9, decision_timestamp: "2024-02-01T00:00:00", effective_timestamp: null,
    weights: { a: 0.4, b: 0.6 }, covariance_fingerprint: "last-covariance" },
];

export function stressRun(overrides: Partial<RunFull> = {}): RunFull {
  return {
    id: 42, name: "User shock result", description: "", status: "completed", created_at: "2024-02-02", updated_at: "2024-02-02",
    scenario_type: "hypothetical_asset_shock", asset_count: 2, scenario_count: 1, integrity_status: "verified_deterministic_rule",
    completeness_status: "partial", scenario_return: null, scenario_pnl: null, stressed_volatility: null,
    baseline_volatility: null, breach_count: 0, episode_count: 0, max_drawdown: null,
    configuration_fingerprint: "c".repeat(64), result_fingerprint: "r".repeat(64), scenario_fingerprint: "s".repeat(64), is_baseline: false,
    portfolio_run_id: 11, portfolio_rebalance_id: 2, portfolio_run_name: portfolio.name, portfolio_method: "supplied_weights",
    dataset_version_id: null, dataset_name: null, dataset_version_label: null, regime_run_id: null, regime_run_name: null,
    cost_diagnostic_run_id: null, cost_run_name: null, cost_model_fingerprint: null, experiment_id: null, experiment_name: null,
    error_message: null, configuration: { scenario: { scenario_type: "hypothetical_asset_shock", missing_shock_policy: "unavailable" } },
    baseline_weight_fingerprint: "w".repeat(64), baseline_covariance_fingerprint: null, stressed_covariance_fingerprint: null,
    reconciliation: { baseline_value: 1, direct_shock_return: null, stressed_cost_return: null, net_scenario_return: null,
      scenario_pnl: null, risk_effect_note: "Risk diagnostics unavailable for this earlier rebalance.", completeness: "partial" },
    risk_summary: null, cost_stress: null, drawdown: null, covariance_stress: null, drifted: null,
    warnings: ["Unspecified shock; partial coverage."], completed_at: "2024-02-02", duration_ms: 1, notes: "",
    ...overrides,
  };
}
