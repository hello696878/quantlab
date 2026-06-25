/**
 * Futures & Commodities Lab — types + API client (Phase 23.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/futures/sample   → deterministic sample commodities + curves
 *   POST /api/futures/analyze  → cost-of-carry + curve + margin analytics
 *
 * All data is static illustrative sample data — no live futures/commodity data,
 * educational only, not investment / trading / risk-management advice.
 */

export type PositionType = "long" | "short";
export type CurveShape = "contango" | "backwardation" | "mixed";

export interface FuturesContractInput {
  commodity_name: string;
  symbol: string;
  spot_price: number;
  risk_free_rate: number;
  storage_cost_rate: number;
  convenience_yield: number;
  contract_multiplier: number;
  initial_margin_rate: number;
  maintenance_margin_rate: number;
}

export interface FuturesCurvePoint {
  contract: string;
  maturity_months: number;
  futures_price: number;
  volume?: number | null;
  open_interest?: number | null;
}

export interface FuturesPositionInput {
  position_type: PositionType;
  contracts: number;
  entry_price: number;
  exit_price: number;
  contract_multiplier: number;
}

export interface FuturesAnalysisRequest {
  contract: FuturesContractInput;
  curve: FuturesCurvePoint[];
  position: FuturesPositionInput;
}

export interface FuturesSampleResponse {
  commodities: FuturesAnalysisRequest[];
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface CommoditySummary {
  commodity_name: string;
  symbol: string;
  spot_price: number;
  risk_free_rate: number;
  storage_cost_rate: number;
  convenience_yield: number;
  contract_multiplier: number;
  initial_margin_rate: number;
  maintenance_margin_rate: number;
  cost_of_carry_rate: number;
}

export interface TheoreticalPricing {
  spot_price: number;
  cost_of_carry_rate: number;
  model_futures_12m: number;
  model_near: number;
  model_far: number;
}

export interface CurveAnalysisPoint {
  contract: string;
  maturity_months: number;
  maturity_years: number;
  observed_futures: number;
  model_futures: number;
  basis: number;
  annualized_basis: number;
  implied_convenience_yield: number;
  pricing_deviation: number;
  roll_yield?: number | null;
}

export interface CurveAnalysis {
  points: CurveAnalysisPoint[];
  curve_slope: number;
  curve_shape: CurveShape;
  near_contract: string;
  far_contract: string;
  near_basis: number;
}

export interface RollYieldRow {
  from_contract: string;
  to_contract: string;
  near_price: number;
  next_price: number;
  roll_yield: number;
}

export interface CalendarSpreadAnalysis {
  near_contract: string;
  deferred_contract: string;
  near_price: number;
  deferred_price: number;
  spread: number;
  spread_pct: number;
}

export interface PositionPnl {
  position_type: PositionType;
  contracts: number;
  entry_price: number;
  exit_price: number;
  contract_multiplier: number;
  pnl: number;
  notional: number;
  initial_margin: number;
  return_on_margin: number;
}

export interface MarginAnalysis {
  notional: number;
  initial_margin: number;
  maintenance_margin: number;
  leverage: number;
  initial_margin_rate: number;
  maintenance_margin_rate: number;
}

export interface FuturesScenarioResult {
  id: string;
  name: string;
  description: string;
  spot_shock: number;
  curve_parallel_shift: number;
  curve_slope_shock: number;
  convenience_yield_shock: number;
  shocked_spot: number;
  curve_shape: CurveShape;
  near_pnl: number;
  calendar_spread_pnl: number;
  roll_yield: number;
  margin_requirement: number;
  return_on_margin: number;
  notes: string[];
}

export interface FuturesAnalysisResponse {
  data_status: "static_sample";
  commodity_summary: CommoditySummary;
  theoretical_pricing: TheoreticalPricing;
  curve_analysis: CurveAnalysis;
  roll_yield_table: RollYieldRow[];
  calendar_spread_analysis: CalendarSpreadAnalysis;
  position_pnl: PositionPnl;
  margin_analysis: MarginAnalysis;
  scenario_results: FuturesScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Futures & Commodities Lab.");
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
  return res.status >= 500 ? "Server error computing futures analytics." : `HTTP ${res.status}`;
}

/** GET /api/futures/sample */
export async function fetchFuturesSample(signal?: AbortSignal): Promise<FuturesSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/futures/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<FuturesSampleResponse>;
}

/** POST /api/futures/analyze */
export async function analyzeFutures(
  request: FuturesAnalysisRequest,
  signal?: AbortSignal,
): Promise<FuturesAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/futures/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<FuturesAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function money(value: number): string {
  return Math.round(value).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function pct(value: number, digits = 2): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number, digits = 2): string {
  return value.toFixed(digits);
}
