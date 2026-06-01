// ---------------------------------------------------------------------------
// Mirrors the Pydantic schemas in backend/app/schemas.py exactly.
// Keep these in sync when the backend changes.
// ---------------------------------------------------------------------------

export type StrategyType =
  | "sma_crossover"
  | "rsi_mean_reversion"
  | "bollinger_band"
  | "momentum"
  | "volatility_breakout"
  | "pairs";

export type BacktestResponseStrategyType = StrategyType | "custom";

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

export interface PairsBacktestRequest {
  asset_y: string;
  asset_x: string;
  start_date: string;
  end_date: string;
  lookback_window: number;
  entry_z_score: number;
  exit_z_score: number;
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
  calmar_ratio: number;
  win_rate: number;
  num_days: number;
}

export interface TradeRecord {
  date: string;
  /** Single-asset: "BUY" | "SELL".  Pairs: "LONG SPREAD" | "SHORT SPREAD" | "EXIT". */
  action: "BUY" | "SELL" | "LONG SPREAD" | "SHORT SPREAD" | "EXIT";
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
// Unified response  (all six strategy endpoints return this shape)
// ---------------------------------------------------------------------------

export interface BacktestResponse {
  ticker: string;
  start_date: string;
  end_date: string;

  /** Which strategy produced this result. */
  strategy: BacktestResponseStrategyType;

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

  /** Pairs Trading params — null when strategy is not pairs. */
  pairs_asset_y: string | null;
  pairs_asset_x: string | null;
  pairs_lookback_window: number | null;
  pairs_entry_z_score: number | null;
  pairs_exit_z_score: number | null;

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

// ---------------------------------------------------------------------------
// Research — SMA Parameter Sweep
// ---------------------------------------------------------------------------

export interface SmaSweepRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  /** 1–10 values, each >= 2. */
  fast_windows: number[];
  /** 1–10 values, each >= 2. */
  slow_windows: number[];
  transaction_cost_bps: number;
  initial_capital: number;
}

export interface SmaSweepRow {
  fast_window: number;
  slow_window: number;
  total_return: number;
  cagr: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  volatility: number;
  num_trades: number;
}

export interface SmaSweepResponse {
  ticker: string;
  start_date: string;
  end_date: string;
  transaction_cost_bps: number;
  initial_capital: number;
  /** Number of valid (fast < slow) combinations that were run. */
  num_combinations: number;
  results: SmaSweepRow[];
}

// ---------------------------------------------------------------------------
// Research — SMA Train/Test Out-of-Sample Validation
// ---------------------------------------------------------------------------

export interface SmaTrainTestRequest {
  ticker: string;
  start_date: string;
  split_date: string;
  end_date: string;
  /** 1–10 values, each >= 2. */
  fast_windows: number[];
  /** 1–10 values, each >= 2. */
  slow_windows: number[];
  transaction_cost_bps: number;
  initial_capital: number;
  selection_metric: "sharpe_ratio" | "cagr" | "calmar_ratio";
}

export interface SmaTrainTestResponse {
  ticker: string;
  start_date: string;
  split_date: string;
  end_date: string;
  transaction_cost_bps: number;
  initial_capital: number;
  selection_metric: string;

  in_sample_days: number;
  out_of_sample_days: number;

  best_fast_window: number;
  best_slow_window: number;

  in_sample_metrics: PerformanceMetrics;
  out_of_sample_metrics: PerformanceMetrics;
  out_of_sample_benchmark_metrics: PerformanceMetrics;

  out_of_sample_equity_curve: EquityPoint[];
  out_of_sample_trades: TradeRecord[];
  out_of_sample_num_trades: number;

  /** OOS Sharpe − IS Sharpe.  Negative = OOS is worse. */
  sharpe_degradation: number;
  /** OOS CAGR − IS CAGR.  Negative = OOS is worse. */
  cagr_degradation: number;
  /** OOS Calmar − IS Calmar.  Negative = OOS is worse. */
  calmar_degradation: number;
  /** abs(OOS max drawdown) − abs(IS max drawdown). Positive = deeper OOS drawdown. */
  max_drawdown_worsening: number;

  /** True when OOS Sharpe < 0 or OOS Sharpe < 50 % of IS Sharpe. */
  oos_collapsed: boolean;

  /** All IS sweep rows for reference display. */
  all_in_sample_results: SmaSweepRow[];
}

// ---------------------------------------------------------------------------
// Research — SMA Walk-Forward Optimization
// ---------------------------------------------------------------------------

export interface SmaWalkForwardRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  train_window_days: number;
  test_window_days: number;
  step_days: number;
  fast_windows: number[];
  slow_windows: number[];
  selection_metric: "sharpe_ratio" | "cagr" | "calmar_ratio";
  initial_capital: number;
  transaction_cost_bps: number;
}

export interface SmaWalkForwardBestParams {
  fast_window: number;
  slow_window: number;
}

export interface SmaWalkForwardWindow {
  window_index: number;
  train_start_date: string;
  train_end_date: string;
  test_start_date: string;
  test_end_date: string;
  train_days: number;
  test_days: number;
  best_fast_window: number;
  best_slow_window: number;
  train_metrics: PerformanceMetrics;
  test_metrics: PerformanceMetrics;
  test_benchmark_metrics: PerformanceMetrics;
  num_trades: number;
}

export interface SmaWalkForwardParamStability {
  num_windows: number;
  unique_parameter_sets: number;
  most_common_fast_window: number;
  most_common_slow_window: number;
  most_common_count: number;
  all_selected_params: SmaWalkForwardBestParams[];
  parameters_unstable: boolean;
}

export interface SmaWalkForwardResponse {
  ticker: string;
  start_date: string;
  end_date: string;
  train_window_days: number;
  test_window_days: number;
  step_days: number;
  selection_metric: string;
  initial_capital: number;
  transaction_cost_bps: number;

  num_windows: number;
  windows: SmaWalkForwardWindow[];

  stitched_equity_curve: EquityPoint[];

  aggregate_metrics: PerformanceMetrics;
  aggregate_benchmark_metrics: PerformanceMetrics;

  parameter_stability: SmaWalkForwardParamStability;
}

// ---------------------------------------------------------------------------
// Research — Strategy Comparison
// ---------------------------------------------------------------------------

export interface StrategyComparisonRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  transaction_cost_bps: number;
}

export interface StrategyResultItem {
  strategy: string;
  display_name: string;
  params: Record<string, number | string>;
  metrics: PerformanceMetrics;
  equity_curve: EquityPoint[];
  num_trades: number;
}

export interface StrategyComparisonRanking {
  best_by_sharpe: string;
  best_by_cagr: string;
  best_by_calmar: string;
  lowest_drawdown: string;
}

export interface StrategyComparisonResponse {
  ticker: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  transaction_cost_bps: number;
  strategies: StrategyResultItem[];
  /** Buy-and-hold equity curve — strategy and benchmark fields both carry the benchmark value. */
  benchmark: EquityPoint[];
  benchmark_metrics: PerformanceMetrics;
  ranking: StrategyComparisonRanking;
}

// ---------------------------------------------------------------------------
// Saved Backtests
// ---------------------------------------------------------------------------

export interface SavedBacktestCreate {
  name: string;
  ticker: string;
  strategy: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  transaction_cost_bps: number;
  params: Record<string, unknown>;
  metrics: Record<string, unknown>;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
  notes: string;
}

/** Lightweight list-view row — no large JSON blobs. */
export interface SavedBacktestSummary {
  id: number;
  created_at: string;
  name: string;
  ticker: string;
  strategy: string;
  start_date: string;
  end_date: string;
  total_return: number | null;
  cagr: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  notes: string;
}

/** Full record including equity curve and trades. */
export interface SavedBacktestFull extends SavedBacktestSummary {
  initial_capital: number;
  transaction_cost_bps: number;
  params: Record<string, unknown>;
  metrics: Record<string, unknown>;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
}

export interface DeleteResponse {
  deleted: boolean;
  id: number;
}

// ---------------------------------------------------------------------------
// Custom Strategy Builder (v1)
// ---------------------------------------------------------------------------

export type CustomIndicatorName =
  | "sma"
  | "rsi"
  | "bb_upper"
  | "bb_middle"
  | "bb_lower"
  | "momentum";

export type CustomOperator = ">" | ">=" | "<" | "<=";

export type CustomOperand =
  | { type: "close" }
  | { type: "constant"; value: number }
  | {
      type: "indicator";
      name: CustomIndicatorName;
      params: { window: number; num_std?: number };
    };

export interface CustomRule {
  left: CustomOperand;
  operator: CustomOperator;
  right: CustomOperand;
}

export interface CustomStrategyRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  transaction_cost_bps: number;
  initial_capital: number;
  entry_rules: CustomRule[];
  entry_logic: "all" | "any";
  exit_rules: CustomRule[];
  exit_logic: "all" | "any";
}

// ---------------------------------------------------------------------------
// Multi-Asset Portfolio Backtesting
// ---------------------------------------------------------------------------

export type PortfolioRebalanceFrequency =
  | "none"
  | "monthly"
  | "quarterly"
  | "yearly";

export interface PortfolioBacktestRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  rebalance_frequency: PortfolioRebalanceFrequency;
  transaction_cost_bps: number;
}

export interface PortfolioEquityPoint {
  date: string;
  portfolio: number;
  benchmark: number;
}

export interface PortfolioDrawdownPoint {
  date: string;
  portfolio: number;
  benchmark: number;
}

export interface PortfolioWeightPoint {
  date: string;
  weights: Record<string, number>;
}

export interface PortfolioRebalanceEvent {
  date: string;
  turnover: number;
  cost: number;
}

export interface PortfolioBacktestResponse {
  tickers: string[];
  start_date: string;
  end_date: string;
  strategy: string;
  rebalance_frequency: PortfolioRebalanceFrequency;
  initial_capital: number;
  transaction_cost_bps: number;
  benchmark_ticker: string;
  metrics: PerformanceMetrics;
  benchmark_metrics: PerformanceMetrics;
  equity_curve: PortfolioEquityPoint[];
  drawdown: PortfolioDrawdownPoint[];
  weights: PortfolioWeightPoint[];
  rebalance_events: PortfolioRebalanceEvent[];
}

// ---------------------------------------------------------------------------
// Saved Custom Strategy Templates (reusable rule definitions, not results)
// ---------------------------------------------------------------------------

/** Template logic uses AND/OR (the builder uses all/any — map at the seam). */
export type CustomTemplateLogic = "AND" | "OR";

export interface CustomStrategyTemplateCreate {
  name: string;
  description: string;
  entry_logic: CustomTemplateLogic;
  exit_logic: CustomTemplateLogic;
  entry_rules: CustomRule[];
  exit_rules: CustomRule[];
  tags: string[];
}

export interface CustomStrategyTemplateSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  description: string;
  entry_logic: CustomTemplateLogic;
  exit_logic: CustomTemplateLogic;
  num_entry_rules: number;
  num_exit_rules: number;
  tags: string[];
}

export interface CustomStrategyTemplateFull {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  description: string;
  entry_logic: CustomTemplateLogic;
  exit_logic: CustomTemplateLogic;
  entry_rules: CustomRule[];
  exit_rules: CustomRule[];
  tags: string[];
}

/** A built-in, read-only gallery template (same rule shape + presentation meta). */
export interface GalleryTemplate {
  id: string;
  name: string;
  description: string;
  entry_logic: CustomTemplateLogic;
  exit_logic: CustomTemplateLogic;
  entry_rules: CustomRule[];
  exit_rules: CustomRule[];
  tags: string[];
  difficulty: "beginner" | "intermediate" | "advanced";
  category: "trend" | "mean_reversion" | "momentum";
}

/** Portable export/import envelope — no id / timestamps / local detail. */
export interface CustomStrategyTemplateExport {
  schema_version: "1.0";
  type: "quantlab_custom_strategy_template";
  name: string;
  description: string;
  entry_logic: CustomTemplateLogic;
  exit_logic: CustomTemplateLogic;
  entry_rules: CustomRule[];
  exit_rules: CustomRule[];
  tags: string[];
}
