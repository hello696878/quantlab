/**
 * Market Microstructure & Execution Lab — types + API client (Phase 25.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/microstructure/sample   → deterministic sample instruments
 *   POST /api/microstructure/analyze  → order book / tape / execution analytics
 *
 * All data is static illustrative sample data — no live order books or trades,
 * no broker / exchange integration, educational only, and not investment,
 * trading, or order-routing advice.
 */

export type Side = "buy" | "sell";
export type LiquidityFlag = "maker" | "taker";

export interface OrderBookLevelInput {
  price: number;
  size: number;
}

export interface OrderBookSnapshotInput {
  symbol: string;
  timestamp: string;
  bids: OrderBookLevelInput[];
  asks: OrderBookLevelInput[];
}

export interface TradePrintInput {
  timestamp: string;
  price: number;
  size: number;
  side: Side;
}

export interface ExecutionOrderInput {
  symbol: string;
  side: Side;
  quantity: number;
  arrival_price: number;
  decision_price?: number | null;
  benchmark_price?: number | null;
  risk_aversion?: number | null;
  participation_limit?: number | null;
}

export interface ExecutionFillInput {
  timestamp: string;
  price: number;
  quantity: number;
  venue?: string | null;
  liquidity_flag?: LiquidityFlag | null;
}

export interface MarketMicrostructureAnalysisRequest {
  order_book: OrderBookSnapshotInput;
  trades: TradePrintInput[];
  execution_order: ExecutionOrderInput;
  fills: ExecutionFillInput[];
  volume_curve: number[];
  average_daily_volume: number;
  volatility_bps: number;
  impact_coefficient: number;
}

export interface MicrostructureSampleResponse {
  instruments: MarketMicrostructureAnalysisRequest[];
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface InstrumentSummary {
  symbol: string;
  timestamp: string;
  best_bid: number;
  best_ask: number;
  mid_price: number;
}

export interface OrderBookSummary {
  best_bid: number;
  best_ask: number;
  mid_price: number;
  spread: number;
  spread_bps: number;
  top_of_book_imbalance: number;
  depth_imbalance_5: number;
  microprice: number;
  microprice_vs_mid_bps: number;
}

export interface DepthLevel {
  level: number;
  bid_price: number;
  bid_size: number;
  cumulative_bid_size: number;
  ask_price: number;
  ask_size: number;
  cumulative_ask_size: number;
}

export interface TradeTapeSummary {
  trade_count: number;
  total_volume: number;
  vwap: number;
  twap: number;
  trade_imbalance: number;
  buy_volume: number;
  sell_volume: number;
}

export interface ExecutionSummary {
  side: Side;
  parent_quantity: number;
  arrival_price: number;
  average_execution_price: number;
  filled_quantity: number;
  fill_ratio: number;
  implementation_shortfall: number;
  shortfall_bps: number;
  slippage_bps: number;
  participation_rate: number;
  market_impact_bps: number;
}

export interface ScheduleComparisonResult {
  schedule_name: string;
  child_orders: number;
  expected_avg_price: number;
  expected_shortfall_bps: number;
  expected_spread_cost_bps: number;
  expected_impact_bps: number;
  participation_rate: number;
  completion_rate: number;
  notes: string[];
}

export interface LiquidityScenarioResult {
  id: string;
  name: string;
  description: string;
  spread_bps: number;
  total_depth: number;
  depth_imbalance: number;
  microprice: number;
  immediate_shortfall_bps: number;
  twap_shortfall_bps: number;
  vwap_shortfall_bps: number;
  pov_shortfall_bps: number;
  notes: string[];
}

export interface MarketMicrostructureAnalysisResponse {
  data_status: "static_sample";
  instrument_summary: InstrumentSummary;
  order_book_summary: OrderBookSummary;
  depth_table: DepthLevel[];
  trade_tape_summary: TradeTapeSummary;
  execution_summary: ExecutionSummary;
  schedule_comparison: ScheduleComparisonResult[];
  liquidity_scenarios: LiquidityScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Microstructure Lab.");
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
  return res.status >= 500 ? "Server error computing microstructure analytics." : `HTTP ${res.status}`;
}

/** GET /api/microstructure/sample */
export async function fetchMicrostructureSample(
  signal?: AbortSignal,
): Promise<MicrostructureSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/microstructure/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<MicrostructureSampleResponse>;
}

/** POST /api/microstructure/analyze */
export async function analyzeMicrostructure(
  request: MarketMicrostructureAnalysisRequest,
  signal?: AbortSignal,
): Promise<MarketMicrostructureAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/microstructure/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<MarketMicrostructureAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function bps(value: number, digits = 1): string {
  return `${value.toFixed(digits)} bps`;
}

export function num(value: number, digits = 2): string {
  return value.toFixed(digits);
}

export function signedBps(value: number, digits = 1): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)} bps`;
}

export function compact(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(2)}K`;
  return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
