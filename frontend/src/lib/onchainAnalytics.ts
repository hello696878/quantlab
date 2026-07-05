/**
 * On-Chain Flow, Exchange Reserve & Whale Concentration Lab — types + API client
 * (Phase 29.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/onchain-analytics/sample   → deterministic sample networks/tokens
 *   POST /api/onchain-analytics/analyze  → flow / activity / whale / regime analytics
 *
 * All data is static illustrative sample data — no live on-chain data, no live
 * token prices, no wallets, no blockchain RPC, smart-contract, explorer, or
 * exchange API calls, educational only, and not investment, trading, or token
 * advice.
 */

export interface OnChainNetworkInput {
  symbol: string;
  token_name: string;
  network_name: string;
  token_price: number;
  circulating_supply: number;
  exchange_reserve_tokens: number;
  exchange_inflow_tokens_24h: number;
  exchange_outflow_tokens_24h: number;
  active_addresses_24h: number;
  transfer_volume_tokens_24h: number;
  transaction_count_24h: number;
  average_transaction_value_tokens?: number | null;
}

export interface HolderCohortInput {
  cohort_name: string;
  holder_count: number;
  token_balance: number;
  description?: string | null;
}

export interface WhaleFlowInput {
  whale_inflow_tokens_24h: number;
  whale_outflow_tokens_24h: number;
  top_10_holder_share: number;
  top_50_holder_share: number;
  top_100_holder_share: number;
}

export interface OnChainScenarioInput {
  name: string;
  price_shock: number;
  inflow_multiplier: number;
  outflow_multiplier: number;
  reserve_change_multiplier: number;
  active_address_shock: number;
  transfer_volume_multiplier: number;
  whale_concentration_shock: number;
}

export interface OnChainAnalysisRequest {
  network: OnChainNetworkInput;
  holder_cohorts: HolderCohortInput[];
  whale_flow: WhaleFlowInput;
  custom_scenarios?: OnChainScenarioInput[] | null;
}

export interface OnChainSampleResponse {
  networks: OnChainAnalysisRequest[];
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface NetworkSummary {
  symbol: string;
  token_name: string;
  network_name: string;
  token_price: number;
  circulating_supply: number;
}

export interface ExchangeFlowAnalysis {
  exchange_reserve_tokens: number;
  exchange_reserve_value: number;
  exchange_reserve_ratio: number;
  exchange_inflow_tokens_24h: number;
  exchange_outflow_tokens_24h: number;
  net_exchange_flow_tokens: number;
  net_exchange_flow_value: number;
  net_exchange_flow_pct_circulating: number;
  reserve_change_tokens: number;
}

export interface ActivityMetrics {
  active_addresses_24h: number;
  transfer_volume_tokens_24h: number;
  transfer_volume_value_24h: number;
  transaction_count_24h: number;
  average_transaction_value_tokens: number;
  token_velocity: number;
}

export interface OnChainValuationMetrics {
  token_price: number;
  market_cap: number;
  nvt_ratio: number;
  nvt_status: "low" | "moderate" | "elevated" | "high";
}

export interface HolderDistributionRow {
  cohort_name: string;
  holder_count: number;
  token_balance: number;
  balance_share: number;
  average_balance: number;
  description?: string | null;
}

export interface WhaleAnalysis {
  whale_inflow_tokens_24h: number;
  whale_outflow_tokens_24h: number;
  whale_net_flow_tokens: number;
  whale_net_flow_pct_circulating: number;
  top_10_holder_share: number;
  top_50_holder_share: number;
  top_100_holder_share: number;
}

export interface ConcentrationAnalysis {
  concentration_score: number;
  gini_style_score: number;
  largest_cohort_share: number;
  notes: string[];
}

export interface RiskRegime {
  regime_id: string;
  regime_label: string;
  score: number;
  drivers: string[];
  explanation: string;
}

export interface OnChainScenarioResult {
  id: string;
  name: string;
  description: string;
  token_price: number;
  market_cap: number;
  net_exchange_flow_tokens: number;
  net_exchange_flow_pct_circulating: number;
  exchange_reserve_ratio: number;
  active_addresses_24h: number;
  transfer_volume_tokens_24h: number;
  token_velocity: number;
  nvt_ratio: number;
  whale_net_flow_tokens: number;
  concentration_score: number;
  regime_label: string;
  notes: string[];
}

export interface OnChainAnalysisResponse {
  data_status: "static_sample";
  network_summary: NetworkSummary;
  exchange_flow: ExchangeFlowAnalysis;
  activity_metrics: ActivityMetrics;
  valuation_metrics: OnChainValuationMetrics;
  holder_distribution: HolderDistributionRow[];
  whale_analysis: WhaleAnalysis;
  concentration_analysis: ConcentrationAnalysis;
  risk_regime: RiskRegime;
  scenario_results: OnChainScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the On-Chain Analytics Lab.");
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
  return res.status >= 500 ? "Server error computing on-chain analytics." : `HTTP ${res.status}`;
}

/** GET /api/onchain-analytics/sample */
export async function fetchOnChainSample(signal?: AbortSignal): Promise<OnChainSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/onchain-analytics/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<OnChainSampleResponse>;
}

/** POST /api/onchain-analytics/analyze */
export async function analyzeOnChain(
  request: OnChainAnalysisRequest,
  signal?: AbortSignal,
): Promise<OnChainAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/onchain-analytics/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<OnChainAnalysisResponse>;
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
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(2)}K`;
  return `${sign}${abs.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

export function signedTokens(value: number): string {
  return value > 0 ? `+${tokens(value)}` : tokens(value);
}

/** NVT for display — the backend caps the ~zero-transfer case at 99999. */
export function nvt(value: number): string {
  return value >= 99_999 ? "∞" : value.toFixed(1);
}
