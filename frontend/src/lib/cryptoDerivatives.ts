/**
 * Crypto Perpetual Futures Funding & Basis Lab — types + API client (Phase 26.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/crypto-derivatives/sample   → deterministic sample crypto markets
 *   POST /api/crypto-derivatives/analyze  → basis / funding / position / carry analytics
 *
 * All data is static illustrative sample data — no live exchange data, no live
 * crypto prices, no broker / exchange integration, educational only, and not
 * investment, trading, or liquidation advice.
 */

export type Side = "long" | "short";
export type CurveShape = "contango" | "backwardation" | "mixed" | "flat";

export interface CryptoMarketInput {
  symbol: string;
  spot_price: number;
  perp_mark_price: number;
  index_price: number;
  funding_rate_8h: number;
  next_funding_hours: number;
  risk_free_rate?: number | null;
}

export interface DatedFutureInput {
  contract: string;
  maturity_days: number;
  futures_price: number;
}

export interface PositionInput {
  side: Side;
  notional: number;
  entry_price: number;
  mark_price: number;
  leverage: number;
  initial_margin_rate: number;
  maintenance_margin_rate: number;
  taker_fee_rate?: number | null;
  maker_fee_rate?: number | null;
}

export interface FundingScenarioInput {
  name: string;
  spot_shock: number;
  perp_basis_shock_bps: number;
  futures_premium_mult: number;
  funding_rate_shock: number;
  volatility_multiplier: number;
  margin_multiplier: number;
}

export interface CryptoDerivativesAnalysisRequest {
  market: CryptoMarketInput;
  dated_futures: DatedFutureInput[];
  position: PositionInput;
  funding_intervals_per_day: number;
  custom_scenarios?: FundingScenarioInput[] | null;
}

export interface CryptoDerivativesSampleResponse {
  markets: CryptoDerivativesAnalysisRequest[];
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface MarketSummary {
  symbol: string;
  spot_price: number;
  index_price: number;
  perp_mark_price: number;
  funding_rate_8h: number;
  next_funding_hours: number;
}

export interface FuturesCurvePoint {
  contract: string;
  maturity_days: number;
  futures_price: number;
  basis: number;
  basis_bps: number;
  annualized_basis: number;
}

export interface BasisAnalysis {
  perp_basis: number;
  perp_basis_bps: number;
  average_futures_basis_bps: number;
  max_annualized_basis: number;
  curve_shape: CurveShape;
}

export interface FundingAnalysis {
  funding_rate_8h: number;
  funding_annualized_compound: number;
  funding_annualized_simple: number;
  long_funding_pnl_daily: number;
  short_funding_pnl_daily: number;
  next_funding_hours: number;
}

export interface PositionRisk {
  side: Side;
  notional: number;
  leverage: number;
  initial_margin: number;
  maintenance_margin: number;
  unrealized_pnl: number;
  margin_ratio: number;
  liquidation_price_approx: number;
  liquidation_distance_bps: number;
}

export interface CarryAnalysis {
  best_carry_contract: string;
  annualized_basis: number;
  estimated_costs: number;
  expected_gross_carry: number;
  notes: string[];
}

export interface FundingRegime {
  regime_id: string;
  regime_label: string;
  score: number;
  drivers: string[];
  explanation: string;
  notes: string[];
}

export interface CryptoScenarioResult {
  id: string;
  name: string;
  description: string;
  shocked_spot: number;
  shocked_perp_mark: number;
  perp_basis_bps: number;
  annualized_basis: number;
  funding_annualized: number;
  long_funding_pnl: number;
  short_funding_pnl: number;
  position_pnl: number;
  margin_ratio: number;
  liquidation_distance_bps: number;
  regime_label: string;
  notes: string[];
}

export interface CryptoDerivativesAnalysisResponse {
  data_status: "static_sample";
  market_summary: MarketSummary;
  basis_analysis: BasisAnalysis;
  funding_analysis: FundingAnalysis;
  futures_curve: FuturesCurvePoint[];
  position_risk: PositionRisk;
  carry_analysis: CarryAnalysis;
  funding_regime: FundingRegime;
  scenario_results: CryptoScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Crypto Derivatives Lab.");
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
  return res.status >= 500 ? "Server error computing crypto-derivatives analytics." : `HTTP ${res.status}`;
}

/** GET /api/crypto-derivatives/sample */
export async function fetchCryptoDerivativesSample(
  signal?: AbortSignal,
): Promise<CryptoDerivativesSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/crypto-derivatives/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<CryptoDerivativesSampleResponse>;
}

/** POST /api/crypto-derivatives/analyze */
export async function analyzeCryptoDerivatives(
  request: CryptoDerivativesAnalysisRequest,
  signal?: AbortSignal,
): Promise<CryptoDerivativesAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/crypto-derivatives/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<CryptoDerivativesAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function bps(value: number, digits = 1): string {
  return `${value.toFixed(digits)} bps`;
}

export function signedBps(value: number, digits = 1): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)} bps`;
}

export function pct(value: number, digits = 2): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number, digits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
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

export function signedMoney(value: number): string {
  return value > 0 ? `+${money(value)}` : money(value);
}
