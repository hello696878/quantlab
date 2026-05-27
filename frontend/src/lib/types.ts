// ---------------------------------------------------------------------------
// Mirrors the Pydantic schemas in backend/app/schemas.py exactly.
// Keep these in sync when the backend changes.
// ---------------------------------------------------------------------------

export type StrategyType =
  | "sma_crossover"
  | "rsi_mean_reversion"
  | "bollinger_band"
  | "momentum"
  | "volatility_breakout";

// ---------------------------------------------------------------------------
// Requests
// ---------------------------------------------------------------------------

export interface BacktestRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  fast_window: number;
  slow_window: number;
  transaction_cost_bps: number;
  initial_capital: number;
}

export interface RsiBacktestRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  rsi_window: number;
  oversold_threshold: number;
  exit_threshold: number;
  transaction_cost_bps: number;
  initial_capital: number;
}

export interface BbBacktestRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  bb_window: number;
  num_std: number;
  exit_band: "middle" | "upper";
  transaction_cost_bps: number;
  initial_capital: number;
}

export interface MomentumBacktestRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  momentum_window: number;
  entry_threshold: number;
  exit_threshold: number;
  transaction_cost_bps: number;
  initial_capital: number;
}

export interface VbBacktestRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  lookback_window: number;
  breakout_multiplier: number;
  exit_window: number;
  transaction_cost_bps: number;
  initial_capital: number;
}

/** Fields shared by every backtest request type. */
export interface CommonParams {
  ticker: string;
  start_date: string;
  end_date: string;
  transaction_cost_bps: number;
  initial_capital: number;
}

// ---------------------------------------------------------------------------
// Response building blocks
// ---------------------------------------------------------------------------

export interface PerformanceMetrics {
  total_return: number;
  cagr: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  volatility: number;
  win_rate: number;
  num_days: number;
}

export interface TradeRecord {
  date: string;
  action: "BUY" | "SELL";
  price: number;
  shares: number;
  cost: number;
}

export interface EquityPoint {
  date: string;
  strategy: number;
  benchmark: number;
}

// ---------------------------------------------------------------------------
// Unified response  (all five strategy endpoints return this shape)
// ---------------------------------------------------------------------------

export interface BacktestResponse {
  ticker: string;
  start_date: string;
  end_date: string;

  /** Which strategy produced this result. */
  strategy: StrategyType;

  /** SMA params — 0 when strategy is not sma_crossover. */
  fast_window: number;
  slow_window: number;

  /** RSI params — null when strategy is not rsi_mean_reversion. */
  rsi_window: number | null;
  oversold_threshold: number | null;
  exit_threshold: number | null;

  /** Bollinger Band params — null when strategy is not bollinger_band. */
  bb_window: number | null;
  bb_num_std: number | null;
  bb_exit_band: "middle" | "upper" | null;

  /** Momentum params — null when strategy is not momentum. */
  momentum_window: number | null;
  momentum_entry_threshold: number | null;
  momentum_exit_threshold: number | null;

  /** Volatility Breakout params — null when strategy is not volatility_breakout. */
  vb_lookback_window: number | null;
  vb_breakout_multiplier: number | null;
  vb_exit_window: number | null;

  transaction_cost_bps: number;
  initial_capital: number;
  strategy_metrics: PerformanceMetrics;
  benchmark_metrics: PerformanceMetrics;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
  num_trades: number;
}

// A backend 422 / 404 error detail string.
export interface ApiError {
  detail: string;
}
