/**
 * Macro Regime & Cross-Asset Allocation Lab — types + API client (Phase 31.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/macro-regime/sample   → deterministic sample macro states
 *   POST /api/macro-regime/analyze  → scoring / regime / allocation analytics
 *
 * All data is static illustrative sample data — no live macro or market data
 * (no FRED, no yfinance in this lab), educational only, and not investment,
 * trading, or asset-allocation advice.
 */

export type IndicatorCategory = "growth" | "inflation" | "policy" | "liquidity" | "credit" | "fx";
export type AssetCategory = "equity" | "duration" | "credit" | "commodity" | "fx" | "real_asset" | "crypto" | "cash";
export type Direction = "higher_is_expansionary" | "higher_is_contractionary";

export interface MacroIndicatorInput {
  name: string;
  category: IndicatorCategory;
  value: number;
  long_run_mean: number;
  long_run_std: number;
  direction: Direction;
  weight: number;
}

export interface AssetClassInput {
  asset_id: string;
  asset_name: string;
  category: AssetCategory;
  expected_return: number;
  volatility: number;
  liquidity_score: number;
  inflation_beta: number;
  growth_beta: number;
  rate_beta: number;
  usd_beta: number;
  credit_beta: number;
}

export interface MacroScenarioInput {
  name: string;
  growth_shock: number;
  inflation_shock: number;
  policy_shock: number;
  liquidity_shock: number;
  credit_shock: number;
  usd_shock: number;
  volatility_multiplier: number;
  correlation_stress: number;
}

export interface MacroRegimeAnalysisRequest {
  sample_id: string;
  sample_name: string;
  indicators: MacroIndicatorInput[];
  assets: AssetClassInput[];
  risk_aversion_lambda: number;
  liquidity_preference_eta: number;
  custom_scenarios?: MacroScenarioInput[] | null;
}

export interface MacroRegimeSampleResponse {
  samples: MacroRegimeAnalysisRequest[];
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface SampleSummary {
  sample_id: string;
  sample_name: string;
  indicator_count: number;
  asset_count: number;
}

export interface IndicatorRow {
  name: string;
  category: IndicatorCategory;
  value: number;
  long_run_mean: number;
  long_run_std: number;
  z_score: number;
  direction_adjusted_score: number;
  weight: number;
}

export interface CategoryScores {
  growth_score: number;
  inflation_score: number;
  policy_score: number;
  liquidity_score: number;
  credit_stress_score: number;
  usd_pressure_score: number;
  composite_macro_score: number;
}

export interface MacroRegime {
  regime_id: string;
  regime_label: string;
  score: number;
  drivers: string[];
  explanation: string;
}

export interface AssetAssumptionRow {
  asset_id: string;
  asset_name: string;
  category: AssetCategory;
  expected_return: number;
  regime_adjusted_expected_return: number;
  volatility: number;
  liquidity_score: number;
  growth_beta: number;
  inflation_beta: number;
  rate_beta: number;
  usd_beta: number;
  credit_beta: number;
}

export interface AllocationResult {
  method: string;
  weights: Record<string, number>;
  portfolio_expected_return: number;
  portfolio_volatility_approx: number;
  risk_contributions: Record<string, number>;
  notes: string[];
}

export interface MacroScenarioResult {
  id: string;
  name: string;
  description: string;
  growth_score: number;
  inflation_score: number;
  policy_score: number;
  liquidity_score: number;
  credit_stress_score: number;
  usd_pressure_score: number;
  regime_label: string;
  portfolio_expected_return: number;
  portfolio_volatility_approx: number;
  largest_weight_asset: string;
  notes: string[];
}

export interface MacroRegimeAnalysisResponse {
  data_status: "static_sample";
  sample_summary: SampleSummary;
  indicator_table: IndicatorRow[];
  category_scores: CategoryScores;
  macro_regime: MacroRegime;
  asset_assumptions: AssetAssumptionRow[];
  allocation_results: AllocationResult[];
  scenario_results: MacroScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Macro Regime Lab.");
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
  return res.status >= 500 ? "Server error computing macro-regime analytics." : `HTTP ${res.status}`;
}

/** GET /api/macro-regime/sample */
export async function fetchMacroRegimeSample(signal?: AbortSignal): Promise<MacroRegimeSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/macro-regime/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<MacroRegimeSampleResponse>;
}

/** POST /api/macro-regime/analyze */
export async function analyzeMacroRegime(
  request: MacroRegimeAnalysisRequest,
  signal?: AbortSignal,
): Promise<MacroRegimeAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/macro-regime/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<MacroRegimeAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function num(value: number, digits = 2): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signedNum(value: number, digits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number, digits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
}
