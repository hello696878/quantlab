/**
 * Portfolio Risk Lab — types + API client (Phase 21.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/portfolio-risk/sample   → deterministic 8-asset sample portfolio
 *   POST /api/portfolio-risk/analyze  → full risk analytics
 *
 * All data is static illustrative sample data — no live data, not advice.
 */

export interface PortfolioAsset {
  id: string;
  name: string;
  ticker: string;
  asset_class: string;
  region: string;
  weight: number;
  expected_return: number;
  volatility: number;
  sample_return_series: number[];
}

export interface StressScenario {
  name: string;
  description?: string | null;
  shocks: Record<string, number>;
}

export interface SamplePortfolioResponse {
  assets: PortfolioAsset[];
  risk_free_rate: number;
  confidence_level: number;
  stress_scenario: StressScenario | null;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface OptimizationConstraintsInput {
  min_weight?: number;
  max_weight?: number;
  target_return?: number | null;
  target_volatility?: number | null;
  previous_weights?: Record<string, number> | null;
}

export interface PortfolioAnalysisRequest {
  assets: PortfolioAsset[];
  risk_free_rate: number;
  confidence_level: number;
  stress_scenario?: StressScenario | null;
  allow_short?: boolean;
  optimization_constraints?: OptimizationConstraintsInput | null;
  risk_aversion?: number;
  tau?: number;
  simulation_config?: PortfolioSimulationConfig | null;
}

export interface FrontierPoint {
  expected_return: number;
  volatility: number;
  sharpe: number;
  weights: Record<string, number>;
}

export interface NamedPortfolio {
  label: string;
  weights: Record<string, number>;
  expected_return: number;
  volatility: number;
  sharpe: number;
}

export interface AssetRiskContribution {
  id: string;
  name: string;
  weight: number;
  marginal_contribution: number;
  component_contribution: number;
  percent_contribution: number;
}

export interface StressResult {
  name: string;
  asset_pnl: Record<string, number>;
  portfolio_pnl: number;
}

export interface FactorDefinition {
  id: string;
  name: string;
  category: string;
  description: string;
  volatility: number;
  is_sample: boolean;
}

export interface PortfolioFactorExposure {
  factor_id: string;
  name: string;
  exposure: number;
  contribution_to_variance: number;
  contribution_to_volatility: number;
  percent_risk_contribution: number;
}

export interface SpecificRiskContribution {
  variance: number;
  contribution_to_volatility: number;
  percent_risk_contribution: number;
}

export interface FactorModelSummary {
  factor_variance: number;
  specific_variance: number;
  model_variance: number;
  model_volatility: number;
}

export interface ScenarioDefinition {
  id: string;
  name: string;
  description: string;
  factor_shocks: Record<string, number>;
  asset_shocks?: Record<string, number> | null;
  is_sample: boolean;
}

export interface ScenarioFactorImpact {
  factor_id: string;
  name: string;
  shock: number;
  impact: number;
}

export interface ScenarioAssetImpact {
  asset_id: string;
  name: string;
  weight: number;
  impact: number;
  contribution: number;
}

export interface ScenarioResult {
  scenario_id: string;
  name: string;
  portfolio_return_impact: number;
  factor_impact: ScenarioFactorImpact[];
  asset_impact: ScenarioAssetImpact[];
  worst_asset: string;
  best_asset: string;
  notes: string[];
}

export interface OptimizedPortfolio {
  id: string;
  name: string;
  objective: string;
  weights: Record<string, number>;
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
  turnover: number;
  notes: string[];
  feasible: boolean;
}

export interface EffectiveConstraints {
  min_weight: number;
  max_weight: number;
  target_return?: number | null;
  target_volatility?: number | null;
  turnover_penalty?: number | null;
}

export interface OptimizationResults {
  current_portfolio: OptimizedPortfolio;
  equal_weight_portfolio: OptimizedPortfolio;
  max_sharpe_portfolio: OptimizedPortfolio;
  min_variance_portfolio: OptimizedPortfolio;
  risk_parity_portfolio: OptimizedPortfolio;
  target_return_portfolio?: OptimizedPortfolio | null;
  target_volatility_portfolio?: OptimizedPortfolio | null;
  candidate_count: number;
  constraints: EffectiveConstraints;
  notes: string[];
}

export interface BlackLittermanView {
  id: string;
  description: string;
  asset_weights: Record<string, number>;
  view_return: number;
  confidence: number;
  is_sample: boolean;
}

export interface AssetReturnView {
  asset_id: string;
  name: string;
  implied_return: number;
  posterior_return: number;
  prior_return: number;
}

export interface BlackLittermanResult {
  risk_aversion: number;
  tau: number;
  returns: AssetReturnView[];
  views: BlackLittermanView[];
  bl_optimized_portfolio: OptimizedPortfolio;
  notes: string[];
}

export interface RebalanceAssetDelta {
  asset_id: string;
  name: string;
  current_weight: number;
  target_weight: number;
  delta: number;
}

export interface RebalanceAnalysis {
  target_portfolio_id: string;
  asset_deltas: RebalanceAssetDelta[];
  absolute_turnover: number;
  largest_increase: string;
  largest_decrease: string;
  note: string;
}

export type SimulationMethod = "parametric_gaussian" | "historical_bootstrap";

export interface PortfolioSimulationConfig {
  horizon_days?: number;
  num_paths?: number;
  initial_value?: number;
  seed?: number;
  drawdown_threshold?: number;
  method?: SimulationMethod;
}

export interface MonteCarloFanPoint {
  day: number;
  p05: number;
  p25: number;
  median: number;
  p75: number;
  p95: number;
}

export interface MonteCarloPathPoint {
  day: number;
  value: number;
}

export interface MonteCarloSamplePath {
  path_id: number;
  points: MonteCarloPathPoint[];
}

export interface MonteCarloSummary {
  method: SimulationMethod;
  seed: number;
  horizon_days: number;
  num_paths: number;
  initial_value: number;
  terminal_wealth_mean: number;
  terminal_wealth_median: number;
  terminal_wealth_p05: number;
  terminal_wealth_p95: number;
  probability_of_loss: number;
  probability_drawdown_breach: number;
  drawdown_threshold: number;
  max_drawdown_mean: number;
  max_drawdown_p05: number;
  max_drawdown_p95: number;
  simulated_var_95: number;
  simulated_cvar_95: number;
  fan_chart_points: MonteCarloFanPoint[];
  sample_paths: MonteCarloSamplePath[];
  notes: string[];
}

export interface SensitivityResult {
  id: string;
  name: string;
  description: string;
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
  historical_var: number;
  historical_cvar: number;
  notes: string[];
}

export interface OptimizationRobustnessResult {
  portfolio_id: string;
  name: string;
  base_sharpe: number;
  worst_case_sharpe: number;
  sharpe_range: number;
  rank_stability: number;
  notes: string[];
}

export interface PortfolioAnalysisResponse {
  asset_order: string[];
  asset_names: Record<string, string>;
  normalized_weights: Record<string, number>;
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
  covariance_matrix: number[][];
  correlation_matrix: number[][];
  asset_risk_contributions: AssetRiskContribution[];
  historical_var: number;
  historical_cvar: number;
  var_horizon: string;
  confidence_level: number;
  risk_free_rate: number;
  stress_result: StressResult | null;
  efficient_frontier: FrontierPoint[];
  min_variance_portfolio: NamedPortfolio;
  risk_parity_portfolio: NamedPortfolio;
  factors: FactorDefinition[];
  factor_order: string[];
  factor_exposures: number[][];
  factor_covariance_matrix: number[][];
  factor_correlation_matrix: number[][];
  portfolio_factor_exposure: PortfolioFactorExposure[];
  specific_risk_contribution: SpecificRiskContribution;
  factor_model: FactorModelSummary;
  scenario_library: ScenarioDefinition[];
  scenario_results: ScenarioResult[];
  optimization_results: OptimizationResults;
  black_litterman: BlackLittermanResult;
  rebalance_analysis: RebalanceAnalysis;
  monte_carlo: MonteCarloSummary;
  bootstrap_robustness: MonteCarloSummary;
  assumption_sensitivity: SensitivityResult[];
  optimization_robustness: OptimizationRobustnessResult[];
  notes: string[];
  data_status: "static_sample";
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error(
    "Backend unavailable — start the QuantLab API to use the Portfolio Risk Lab.",
  );
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  } catch {
    // ignore — fall through to status text
  }
  return res.status >= 500 ? "Server error computing portfolio analytics." : `HTTP ${res.status}`;
}

/** GET /api/portfolio-risk/sample */
export async function fetchSamplePortfolio(
  signal?: AbortSignal,
): Promise<SamplePortfolioResponse> {
  let res: Response;
  try {
    res = await fetch("/api/portfolio-risk/sample", {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<SamplePortfolioResponse>;
}

/** POST /api/portfolio-risk/analyze */
export async function analyzePortfolio(
  request: PortfolioAnalysisRequest,
  signal?: AbortSignal,
): Promise<PortfolioAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/portfolio-risk/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<PortfolioAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function pct(value: number, digits = 2): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number, digits = 2): string {
  return value.toFixed(digits);
}

/** Copyable plain-text formula reference for the explanation panel. */
export const PORTFOLIO_FORMULAS = `Portfolio return       r_p = wᵀμ
Portfolio variance     σ_p² = wᵀΣw
Portfolio volatility   σ_p = sqrt(wᵀΣw)
Sharpe ratio           (r_p − r_f) / σ_p
Correlation            ρ_ij = Σ_ij / (σ_i · σ_j)
Marginal risk (MCR)    MCR = Σw / σ_p
Component risk (CCR)    CCR_i = w_i · MCR_i
Percent risk           CCR_i / σ_p
Historical VaR         VaR_c = −quantile(r_p, 1 − c)
Historical CVaR / ES   CVaR_c = −mean(r_p ≤ quantile(r_p, 1 − c))
Stress P&L             Σ w_i · stress_return_i

Factor exposure        portfolio_beta = Bᵀw
Factor variance        β_pᵀ F β_p
Specific variance      wᵀ D w   (D = diag of residual variances)
Model variance         factor_variance + specific_variance
Factor % risk          (β_p,f · (F β_p)_f) / model_variance
Specific % risk        specific_variance / model_variance
Scenario asset impact  Σ_f beta_i,f · shock_f + asset_specific_shock_i
Scenario portfolio P&L Σ_i w_i · asset_impact_i

Mean-variance opt.     max (wᵀμ − r_f) / sqrt(wᵀΣw),  s.t. long-only box
BL implied returns     π = δ · Σ · w_market
BL posterior returns   μ_bl = [ (τΣ)⁻¹ + Pᵀ Ω⁻¹ P ]⁻¹ · [ (τΣ)⁻¹ π + Pᵀ Ω⁻¹ q ]
Turnover               0.5 · Σ_i |target_w_i − current_w_i|

MC daily return        r_t ~ N(μ_p/252, σ_p/√252)   (parametric Gaussian)
Wealth path            W_t = W_0 · Π_{s≤t} (1 + r_s)
Drawdown               DD_t = W_t / max(W_0..W_t) − 1
Max drawdown           min_t DD_t
Prob of loss           mean( W_T < W_0 )
Prob DD breach         mean( maxDD ≤ threshold )`;
