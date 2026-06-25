/**
 * Volatility Surface & Variance Swap Lab — types + API client (Phase 24.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/volatility/sample   → deterministic sample option chain
 *   POST /api/volatility/analyze  → IV surface / skew / variance swap / vega
 *
 * All data is static illustrative sample data — no live option chains or market
 * data, educational only, not investment / trading advice, and not official VIX /
 * exchange methodology.
 */

export type OptionType = "call" | "put";

export interface UnderlyingInput {
  symbol: string;
  spot_price: number;
  risk_free_rate: number;
  dividend_yield: number;
  realized_returns?: number[] | null;
}

export interface OptionQuoteInput {
  option_id: string;
  option_type: OptionType;
  strike: number;
  maturity_days: number;
  mid_price: number;
  bid?: number | null;
  ask?: number | null;
  open_interest?: number | null;
  volume?: number | null;
}

export interface OptionPositionInput {
  option_id: string;
  quantity: number;
  contract_multiplier: number;
}

export interface VolatilityAnalysisRequest {
  underlying: UnderlyingInput;
  option_quotes: OptionQuoteInput[];
  positions?: OptionPositionInput[] | null;
  variance_swap_maturity_days?: number | null;
}

export interface VolatilitySampleResponse {
  request: VolatilityAnalysisRequest;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface UnderlyingSummary {
  symbol: string;
  spot_price: number;
  risk_free_rate: number;
  dividend_yield: number;
}

export interface OptionAnalysis {
  option_id: string;
  option_type: OptionType;
  strike: number;
  maturity_days: number;
  maturity_years: number;
  moneyness: number;
  log_moneyness: number;
  mid_price: number;
  implied_volatility?: number | null;
  iv_note?: string | null;
  vega: number;
  delta: number;
  intrinsic_value: number;
  time_value: number;
}

export interface SmilePoint {
  maturity_days: number;
  strike: number;
  moneyness: number;
  implied_volatility: number;
  option_type: OptionType;
  vega: number;
}

export interface TermStructurePoint {
  maturity_days: number;
  atm_implied_volatility: number;
}

export interface SkewMetric {
  maturity_days: number;
  put_90_iv: number;
  atm_iv: number;
  call_110_iv: number;
  put_spread: number;
  call_spread: number;
  skew_slope: number;
  risk_reversal_25d?: number | null;
}

export interface SurfaceSummary {
  atm_iv_30d: number;
  atm_iv_90d: number;
  atm_iv_1y: number;
  min_iv: number;
  max_iv: number;
  average_iv: number;
  steepest_skew_maturity: number;
  term_structure_slope: number;
}

export interface RealizedVolatility {
  num_returns: number;
  realized_vol_annual: number;
  realized_vol_20d?: number | null;
  realized_vol_60d?: number | null;
  realized_vol_120d?: number | null;
}

export interface ImpliedRealizedSpread {
  implied_atm_30d: number;
  realized_vol: number;
  spread: number;
}

export interface VarianceStripPoint {
  strike: number;
  otm_type: OptionType;
  otm_price: number;
  delta_k: number;
  weight: number;
  contribution: number;
}

export interface VarianceSwap {
  maturity_days: number;
  maturity_years: number;
  forward: number;
  variance_strike: number;
  volatility_strike: number;
  strip_points: VarianceStripPoint[];
  notes: string[];
}

export interface VegaGroup {
  key: string;
  vega: number;
}

export interface VegaExposure {
  total_vega: number;
  positions_used: number;
  vega_by_maturity: VegaGroup[];
  vega_by_moneyness: VegaGroup[];
}

export interface VolatilityScenarioResult {
  id: string;
  name: string;
  description: string;
  parallel_iv_shift: number;
  skew_shift: number;
  term_structure_shift: number;
  spot_shock: number;
  shifted_atm_iv_30d: number;
  shifted_atm_iv_1y: number;
  term_structure_slope: number;
  atm_iv_change: number;
  skew_change: number;
  portfolio_value_change: number;
  total_vega: number;
  notes: string[];
}

export interface VolatilityAnalysisResponse {
  data_status: "static_sample";
  underlying: UnderlyingSummary;
  option_quotes: OptionAnalysis[];
  smile_points: SmilePoint[];
  term_structure: TermStructurePoint[];
  skew_metrics: SkewMetric[];
  surface_summary: SurfaceSummary;
  realized_volatility: RealizedVolatility;
  implied_realized_spread: ImpliedRealizedSpread;
  variance_swap: VarianceSwap;
  vega_exposure: VegaExposure;
  scenario_results: VolatilityScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Volatility Lab.");
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
  return res.status >= 500 ? "Server error computing volatility analytics." : `HTTP ${res.status}`;
}

/** GET /api/volatility/sample */
export async function fetchVolatilitySample(signal?: AbortSignal): Promise<VolatilitySampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/volatility/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<VolatilitySampleResponse>;
}

/** POST /api/volatility/analyze */
export async function analyzeVolatility(
  request: VolatilityAnalysisRequest,
  signal?: AbortSignal,
): Promise<VolatilityAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/volatility/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<VolatilityAnalysisResponse>;
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

export function compact(value: number): string {
  return Math.round(value).toLocaleString("en-US");
}
