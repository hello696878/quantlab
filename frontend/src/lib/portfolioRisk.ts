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

export interface PortfolioAnalysisRequest {
  assets: PortfolioAsset[];
  risk_free_rate: number;
  confidence_level: number;
  stress_scenario?: StressScenario | null;
  allow_short?: boolean;
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
Stress P&L             Σ w_i · stress_return_i`;
