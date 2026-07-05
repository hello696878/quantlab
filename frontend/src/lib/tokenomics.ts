/**
 * Tokenomics, Unlock Schedule & Treasury Risk Lab — types + API client (Phase 28.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/tokenomics/sample   → deterministic sample tokens
 *   POST /api/tokenomics/analyze  → valuation / unlock / treasury / regime analytics
 *
 * All data is static illustrative sample data — no live token prices, no live
 * on-chain data, no wallets, no blockchain RPC or smart-contract calls,
 * educational only, and not investment, trading, token, or venture advice.
 */

export interface TokenMarketInput {
  symbol: string;
  token_name: string;
  price: number;
  circulating_supply: number;
  total_supply: number;
  max_supply?: number | null;
  treasury_tokens?: number | null;
  treasury_stables?: number | null;
  monthly_burn_usd: number;
  staking_yield: number;
  emission_rate_annual: number;
  protocol_revenue_annual?: number | null;
}

export interface UnlockEventInput {
  date: string;
  days_until: number;
  category: string;
  tokens: number;
  description?: string | null;
}

export interface HolderConcentrationInput {
  top_1_holder_share: number;
  top_5_holder_share: number;
  top_10_holder_share: number;
  insider_share?: number | null;
  foundation_share?: number | null;
  community_share?: number | null;
}

export interface TokenomicsScenarioInput {
  name: string;
  price_shock: number;
  unlock_multiplier: number;
  emission_multiplier: number;
  burn_multiplier: number;
  treasury_asset_shock: number;
  holder_concentration_shock: number;
}

export interface TokenomicsAnalysisRequest {
  market: TokenMarketInput;
  unlock_events: UnlockEventInput[];
  holder_concentration: HolderConcentrationInput;
  custom_scenarios?: TokenomicsScenarioInput[] | null;
}

export interface TokenomicsSampleResponse {
  tokens: TokenomicsAnalysisRequest[];
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface TokenSummary {
  symbol: string;
  token_name: string;
  price: number;
}

export interface ValuationMetrics {
  market_cap: number;
  fully_diluted_valuation: number;
  fdv_to_market_cap: number;
  float_ratio: number;
  circulating_supply: number;
  total_supply: number;
  max_supply?: number | null;
}

export interface UnlockScheduleRow {
  date: string;
  days_until: number;
  category: string;
  tokens: number;
  unlock_value: number;
  unlock_pct_circulating: number;
  cumulative_unlock_tokens: number;
  cumulative_unlock_pct_circulating: number;
  description?: string | null;
}

export interface UnlockPressure {
  next_30d_tokens: number;
  next_90d_tokens: number;
  next_180d_tokens: number;
  next_365d_tokens: number;
  next_180d_pct_circulating: number;
  pressure_score: number;
  notes: string[];
}

export interface EmissionAnalysis {
  emission_rate_annual: number;
  annual_emission_tokens: number;
  annual_emission_value: number;
  emission_inflation: number;
  notes: string[];
}

export interface StakingAnalysis {
  staking_yield: number;
  real_yield_approx: number;
  protocol_revenue_yield?: number | null;
  notes: string[];
}

export interface TreasuryAnalysis {
  treasury_token_value: number;
  treasury_stables: number;
  treasury_total_value: number;
  monthly_burn_usd: number;
  monthly_revenue_usd: number;
  runway_months: number;
  revenue_adjusted_runway_months: number;
  notes: string[];
}

export interface HolderConcentration {
  top_1_holder_share: number;
  top_5_holder_share: number;
  top_10_holder_share: number;
  insider_share?: number | null;
  foundation_share?: number | null;
  community_share?: number | null;
  concentration_score: number;
  notes: string[];
}

export interface RiskRegime {
  regime_id: string;
  regime_label: string;
  score: number;
  drivers: string[];
  explanation: string;
}

export interface TokenomicsScenarioResult {
  id: string;
  name: string;
  description: string;
  price: number;
  market_cap: number;
  fully_diluted_valuation: number;
  fdv_to_market_cap: number;
  next_180d_unlock_pressure: number;
  emission_inflation: number;
  real_yield_approx: number;
  treasury_value: number;
  runway_months: number;
  concentration_score: number;
  regime_label: string;
  notes: string[];
}

export interface TokenomicsAnalysisResponse {
  data_status: "static_sample";
  token_summary: TokenSummary;
  valuation_metrics: ValuationMetrics;
  unlock_schedule: UnlockScheduleRow[];
  unlock_pressure: UnlockPressure;
  emission_analysis: EmissionAnalysis;
  staking_analysis: StakingAnalysis;
  treasury_analysis: TreasuryAnalysis;
  holder_concentration: HolderConcentration;
  risk_regime: RiskRegime;
  scenario_results: TokenomicsScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Tokenomics Risk Lab.");
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
  return res.status >= 500 ? "Server error computing tokenomics analytics." : `HTTP ${res.status}`;
}

/** GET /api/tokenomics/sample */
export async function fetchTokenomicsSample(signal?: AbortSignal): Promise<TokenomicsSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/tokenomics/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<TokenomicsSampleResponse>;
}

/** POST /api/tokenomics/analyze */
export async function analyzeTokenomics(
  request: TokenomicsAnalysisRequest,
  signal?: AbortSignal,
): Promise<TokenomicsAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/tokenomics/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<TokenomicsAnalysisResponse>;
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

export function num(value: number, digits = 2): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function money(value: number): string {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(2)}K`;
  return `${sign}$${abs.toFixed(2)}`;
}

export function tokens(value: number): string {
  if (Math.abs(value) >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(2)}K`;
  return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

/** Runway months for display — the backend caps the ~zero-burn case at 9999. */
export function runway(value: number): string {
  return value >= 9999 ? "∞" : `${value.toFixed(1)} mo`;
}
