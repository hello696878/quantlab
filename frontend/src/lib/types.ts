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
// Portfolio Optimization (in-sample, long-only)
// ---------------------------------------------------------------------------

export type PortfolioObjective =
  | "equal_weight"
  | "min_volatility"
  | "max_sharpe";

export interface PortfolioOptimizeRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  risk_free_rate: number;
  transaction_cost_bps: number;
  objective: PortfolioObjective;
}

export interface PortfolioOptEquityPoint {
  date: string;
  value: number;
}

export interface PortfolioOptDrawdownPoint {
  date: string;
  portfolio: number;
  equal_weight: number;
}

export interface PortfolioOptimizeResponse {
  tickers: string[];
  objective: PortfolioObjective;
  start_date: string;
  end_date: string;
  initial_capital: number;
  risk_free_rate: number;
  transaction_cost_bps: number;
  weights: Record<string, number>;
  expected_returns: Record<string, number>;
  covariance_matrix: Record<string, Record<string, number>>;
  portfolio_expected_return: number;
  portfolio_volatility: number;
  portfolio_sharpe: number;
  metrics: PerformanceMetrics;
  equal_weight_metrics: PerformanceMetrics;
  equity_curve: PortfolioOptEquityPoint[];
  equal_weight_equity_curve: PortfolioOptEquityPoint[];
  drawdown: PortfolioOptDrawdownPoint[];
  in_sample_warning: string;
}

// ---------------------------------------------------------------------------
// Efficient Frontier
// ---------------------------------------------------------------------------

export interface EfficientFrontierRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  risk_free_rate: number;
  num_portfolios: number;
}

export interface FrontierPortfolioPoint {
  expected_return: number;
  volatility: number;
  sharpe: number;
  weights: Record<string, number>;
}

export interface FrontierCurvePoint {
  expected_return: number;
  volatility: number;
}

export interface EfficientFrontierResponse {
  tickers: string[];
  start_date: string;
  end_date: string;
  risk_free_rate: number;
  num_portfolios: number;
  expected_returns: Record<string, number>;
  covariance_matrix: Record<string, Record<string, number>>;
  random_portfolios: FrontierPortfolioPoint[];
  equal_weight: FrontierPortfolioPoint;
  min_volatility: FrontierPortfolioPoint;
  max_sharpe: FrontierPortfolioPoint;
  frontier_points: FrontierCurvePoint[];
  in_sample_note: string;
}

// ---------------------------------------------------------------------------
// Portfolio Stress Testing / Scenario Analysis
// ---------------------------------------------------------------------------

export interface StressScenarioInput {
  name: string;
  start_date: string;
  end_date: string;
}

export interface StressTestRequest {
  tickers: string[];
  weights?: Record<string, number> | null;
  start_date: string;
  end_date: string;
  initial_capital: number;
  transaction_cost_bps: number;
  scenarios: StressScenarioInput[];
  benchmark_ticker: string;
}

export interface StressScenarioResult {
  name: string;
  start_date: string;
  end_date: string;
  total_return: number;
  max_drawdown: number;
  annualized_volatility: number;
  worst_day_return: number;
  best_day_return: number;
  benchmark_total_return: number;
  benchmark_max_drawdown: number;
  benchmark_worst_day_return: number;
  benchmark_best_day_return: number;
  excess_return: number;
  correlation_matrix: Record<string, Record<string, number>>;
  portfolio_equity_curve: PortfolioOptEquityPoint[];
  benchmark_equity_curve: PortfolioOptEquityPoint[];
}

export interface StressTestResponse {
  tickers: string[];
  weights: Record<string, number>;
  start_date: string;
  end_date: string;
  benchmark_ticker: string;
  full_period_metrics: PerformanceMetrics;
  benchmark_full_period_metrics: PerformanceMetrics;
  full_equity_curve: PortfolioOptEquityPoint[];
  benchmark_equity_curve: PortfolioOptEquityPoint[];
  scenarios: StressScenarioResult[];
  historical_note: string;
}

// ---------------------------------------------------------------------------
// Factor Exposure / Regression Analysis
// ---------------------------------------------------------------------------

export interface FactorAnalysisRequest {
  tickers: string[];
  weights?: Record<string, number> | null;
  start_date: string;
  end_date: string;
  initial_capital: number;
  factor_tickers: Record<string, string>;
}

export interface FactorDiagnostics {
  strongest_positive_factor: string | null;
  strongest_negative_factor: string | null;
  absolute_largest_exposure: string | null;
  multicollinearity_warning: boolean;
}

export interface FactorRegressionPoint {
  date: string;
  actual_return: number;
  fitted_return: number;
  residual: number;
}

export interface FactorAnalysisResponse {
  tickers: string[];
  weights: Record<string, number>;
  start_date: string;
  end_date: string;
  factor_tickers: Record<string, string>;
  alpha_daily: number;
  alpha_annualized: number;
  betas: Record<string, number>;
  r_squared: number;
  residual_volatility: number;
  factor_correlation_matrix: Record<string, Record<string, number>>;
  diagnostics: FactorDiagnostics;
  regression_points: FactorRegressionPoint[];
  actual_equity_curve: PortfolioOptEquityPoint[];
  fitted_equity_curve: PortfolioOptEquityPoint[];
  historical_note: string;
}

// ---------------------------------------------------------------------------
// Portfolio Risk Dashboard
// ---------------------------------------------------------------------------

export interface RiskDashboardRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
}

export interface EqualWeightRiskSummary {
  expected_return: number;
  volatility: number;
  diversification_ratio: number;
  weights: Record<string, number>;
}

export interface CorrelationDiagnostics {
  average_pairwise_correlation: number;
  max_pairwise_correlation: number;
  min_pairwise_correlation: number;
  most_correlated_pair: string[] | null;
  least_correlated_pair: string[] | null;
}

export interface RiskDashboardResponse {
  tickers: string[];
  start_date: string;
  end_date: string;
  asset_annual_returns: Record<string, number>;
  asset_annual_volatilities: Record<string, number>;
  correlation_matrix: Record<string, Record<string, number>>;
  covariance_matrix: Record<string, Record<string, number>>;
  equal_weight_portfolio: EqualWeightRiskSummary;
  correlation_diagnostics: CorrelationDiagnostics;
  risk_contribution: Record<string, number>;
  historical_note: string;
}

// ---------------------------------------------------------------------------
// Walk-Forward Portfolio Optimization
// ---------------------------------------------------------------------------

export interface PortfolioWalkForwardRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  train_window_days: number;
  test_window_days: number;
  step_days: number;
  objective: PortfolioObjective;
  risk_free_rate: number;
  initial_capital: number;
  transaction_cost_bps: number;
}

export interface PortfolioWalkForwardWindow {
  train_start_date: string;
  train_end_date: string;
  test_start_date: string;
  test_end_date: string;
  weights: Record<string, number>;
  train_expected_return: number;
  train_volatility: number;
  train_sharpe: number;
  test_metrics: PerformanceMetrics;
  turnover: number;
  transaction_cost: number;
}

export interface PortfolioWeightStability {
  average_turnover: number;
  max_turnover: number;
  average_weight_by_asset: Record<string, number>;
  min_weight_by_asset: Record<string, number>;
  max_weight_by_asset: Record<string, number>;
}

export interface PortfolioWalkForwardResponse {
  tickers: string[];
  objective: PortfolioObjective;
  start_date: string;
  end_date: string;
  train_window_days: number;
  test_window_days: number;
  step_days: number;
  risk_free_rate: number;
  initial_capital: number;
  transaction_cost_bps: number;
  num_windows: number;
  windows: PortfolioWalkForwardWindow[];
  stitched_equity_curve: PortfolioOptEquityPoint[];
  benchmark_equity_curve: PortfolioOptEquityPoint[];
  drawdown: PortfolioDrawdownPoint[];
  metrics: PerformanceMetrics;
  benchmark_metrics: PerformanceMetrics;
  weight_stability: PortfolioWeightStability;
  oos_note: string;
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
