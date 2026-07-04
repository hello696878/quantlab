/**
 * DeFi Yield, Stablecoin Peg & Lending Risk Lab — types + API client (Phase 27.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/defi-risk/sample   → deterministic sample DeFi markets
 *   POST /api/defi-risk/analyze  → peg / utilization / collateral / net-APY analytics
 *
 * All data is static illustrative sample data — no live protocol data, no live
 * crypto prices, no wallets, no blockchain RPC or smart-contract calls,
 * educational only, and not investment, trading, lending, borrowing, or
 * liquidation advice.
 */

export type PegStatus = "on_peg" | "minor_deviation" | "depegged";
export type UtilizationRegime = "low" | "moderate" | "high" | "extreme";

export interface StablecoinInput {
  symbol: string;
  target_peg: number;
  market_price: number;
  supply_weight?: number | null;
  reserve_quality_score?: number | null;
}

export interface DeFiMarketInput {
  protocol_name: string;
  chain: string;
  asset_symbol: string;
  total_supplied: number;
  total_borrowed: number;
  liquidity: number;
  base_rate: number;
  slope_1: number;
  slope_2: number;
  kink_utilization: number;
  reserve_factor: number;
  lending_apy: number;
  borrow_apy: number;
}

export interface CollateralPositionInput {
  collateral_asset: string;
  collateral_amount: number;
  collateral_price: number;
  debt_asset: string;
  debt_amount: number;
  debt_price: number;
  liquidation_threshold: number;
  collateral_factor: number;
  liquidation_penalty: number;
  borrow_apy: number;
  supply_apy: number;
}

export interface DeFiScenarioInput {
  name: string;
  collateral_price_shock: number;
  debt_price_shock: number;
  stablecoin_depeg_shock: number;
  utilization_shock: number;
  liquidity_shock: number;
  borrow_rate_shock: number;
  liquidation_threshold_shock: number;
}

export interface DeFiRiskAnalysisRequest {
  sample_id: string;
  stablecoin: StablecoinInput;
  market: DeFiMarketInput;
  position: CollateralPositionInput;
  fees_apy: number;
  custom_scenarios?: DeFiScenarioInput[] | null;
}

export interface DeFiRiskSampleResponse {
  samples: DeFiRiskAnalysisRequest[];
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface ProtocolSummary {
  sample_id: string;
  protocol_name: string;
  chain: string;
  asset_symbol: string;
  collateral_asset: string;
  debt_asset: string;
}

export interface StablecoinPegAnalysis {
  symbol: string;
  target_peg: number;
  market_price: number;
  peg_deviation: number;
  peg_deviation_bps: number;
  reserve_quality_score?: number | null;
  status: PegStatus;
}

export interface UtilizationAnalysis {
  total_supplied: number;
  total_borrowed: number;
  liquidity: number;
  utilization: number;
  kink_utilization: number;
  utilization_regime: UtilizationRegime;
}

export interface InterestRateModelResult {
  borrow_apy_model: number;
  supply_apy_model: number;
  reserve_factor: number;
  base_rate: number;
  slope_1: number;
  slope_2: number;
  kink_utilization: number;
}

export interface CollateralRisk {
  collateral_value: number;
  debt_value: number;
  loan_to_value: number;
  collateral_factor: number;
  liquidation_threshold: number;
  health_factor: number;
  liquidation_price_approx: number;
  liquidation_distance_bps: number;
  liquidation_penalty: number;
}

export interface NetAPYAnalysis {
  supply_apy: number;
  borrow_apy: number;
  fees_apy: number;
  net_apy: number;
  notes: string[];
}

export interface RiskRegime {
  regime_id: string;
  regime_label: string;
  score: number;
  drivers: string[];
  explanation: string;
}

export interface DeFiScenarioResult {
  id: string;
  name: string;
  description: string;
  peg_deviation_bps: number;
  utilization: number;
  borrow_apy: number;
  supply_apy: number;
  collateral_value: number;
  debt_value: number;
  loan_to_value: number;
  health_factor: number;
  liquidation_price: number;
  liquidation_distance_bps: number;
  net_apy: number;
  regime_label: string;
  notes: string[];
}

export interface DeFiRiskAnalysisResponse {
  data_status: "static_sample";
  protocol_summary: ProtocolSummary;
  stablecoin_peg: StablecoinPegAnalysis;
  utilization_analysis: UtilizationAnalysis;
  interest_rate_model: InterestRateModelResult;
  collateral_risk: CollateralRisk;
  net_apy_analysis: NetAPYAnalysis;
  risk_regime: RiskRegime;
  scenario_results: DeFiScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the DeFi Risk Lab.");
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
  return res.status >= 500 ? "Server error computing DeFi risk analytics." : `HTTP ${res.status}`;
}

/** GET /api/defi-risk/sample */
export async function fetchDefiRiskSample(signal?: AbortSignal): Promise<DeFiRiskSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/defi-risk/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<DeFiRiskSampleResponse>;
}

/** POST /api/defi-risk/analyze */
export async function analyzeDefiRisk(
  request: DeFiRiskAnalysisRequest,
  signal?: AbortSignal,
): Promise<DeFiRiskAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/defi-risk/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<DeFiRiskAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function pct(value: number, digits = 2): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number, digits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

export function bps(value: number, digits = 0): string {
  return `${value.toFixed(digits)} bps`;
}

export function signedBps(value: number, digits = 0): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)} bps`;
}

export function num(value: number, digits = 2): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function money(value: number): string {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(2)}K`;
  return `${sign}$${abs.toFixed(2)}`;
}

/** Health factor for display — the backend caps the no-debt case at 999. */
export function hf(value: number): string {
  return value >= 999 ? "∞ (no debt)" : value.toFixed(2);
}
