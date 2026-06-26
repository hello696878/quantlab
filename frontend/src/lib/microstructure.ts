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

export interface QuoteUpdateInput {
  timestamp: string;
  bid: number;
  ask: number;
  bid_size: number;
  ask_size: number;
  mid_price?: number | null;
}

export interface SignedTradeInput {
  timestamp: string;
  price: number;
  size: number;
  side: Side;
  mid_before: number;
  mid_after_5s?: number | null;
  mid_after_30s?: number | null;
  volume_bucket?: number | null;
}

export interface ToxicityConfig {
  bucket_volume: number;
  realized_spread_horizon_seconds: number;
  vpin_window_buckets: number;
  lambda_window_trades: number;
  regime_threshold_low: number;
  regime_threshold_high: number;
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
  commission_per_unit: number;
  quotes?: QuoteUpdateInput[] | null;
  signed_trades?: SignedTradeInput[] | null;
  toxicity_config?: ToxicityConfig | null;
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

export interface TCAAttributionRow {
  component: string;
  cost_bps: number;
  share: number;
}

export interface TCAResult {
  benchmark_arrival_bps: number;
  benchmark_vwap_bps: number;
  benchmark_twap_bps: number;
  spread_cost_bps: number;
  impact_cost_bps: number;
  timing_cost_bps: number;
  fees_bps: number;
  total_cost_bps: number;
  attribution_rows: TCAAttributionRow[];
  notes: string[];
}

export interface OrderFlowSummary {
  trade_count: number;
  buy_volume: number;
  sell_volume: number;
  total_volume: number;
  signed_volume: number;
  order_flow_imbalance: number;
  average_queue_imbalance: number;
}

export interface SpreadQuality {
  average_effective_spread_bps: number;
  average_realized_spread_bps: number;
  average_adverse_selection_bps: number;
  effective_spread_p95_bps: number;
  adverse_selection_p95_bps: number;
}

export interface ToxicityMetrics {
  vpin: number;
  vpin_bucket_count: number;
  kyle_lambda?: number | null;
  amihud_illiquidity: number;
  toxicity_score: number;
  notes: string[];
}

export interface LiquidityRegime {
  regime_id: string;
  regime_label: string;
  score: number;
  drivers: string[];
  explanation: string;
}

export interface ToxicityScenarioResult {
  id: string;
  name: string;
  description: string;
  order_flow_imbalance: number;
  queue_imbalance: number;
  vpin: number;
  effective_spread_bps: number;
  realized_spread_bps: number;
  adverse_selection_bps: number;
  kyle_lambda?: number | null;
  amihud_illiquidity: number;
  regime_label: string;
  notes: string[];
}

export interface OrderFlowToxicityResult {
  data_status: "static_sample";
  order_flow_summary: OrderFlowSummary;
  spread_quality: SpreadQuality;
  toxicity_metrics: ToxicityMetrics;
  liquidity_regime: LiquidityRegime;
  toxicity_scenarios: ToxicityScenarioResult[];
  formula_notes: string[];
  disclaimer: string;
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
  tca: TCAResult;
  order_flow_toxicity: OrderFlowToxicityResult;
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

/** Compact scientific notation for very small/large magnitudes (e.g. Amihud). */
export function sci(value: number, digits = 2): string {
  if (value === 0) return "0";
  if (Math.abs(value) < 1e-3 || Math.abs(value) >= 1e6) return value.toExponential(digits);
  return value.toFixed(Math.max(digits, 4));
}

/** Kyle lambda or "—" when undefined (null on zero signed-volume variance). */
export function lambdaFmt(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value === 0) return "0";
  return Math.abs(value) >= 0.001 ? value.toFixed(4) : value.toExponential(2);
}
