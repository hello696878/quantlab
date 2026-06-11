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

/** Strategy direction mode (SMA Crossover, Momentum, Volatility Breakout). */
export type PositionMode = "long_only" | "short_only" | "long_short";

/** Transaction-cost / slippage model (research v1). All bps charged on turnover. */
export type CostModelType = "simple_bps" | "commission_slippage" | "conservative";

export interface CostModel {
  type: CostModelType;
  /** simple_bps: one-way cost (falls back to request.transaction_cost_bps when omitted). */
  transaction_cost_bps?: number;
  /** commission_slippage components. */
  commission_bps?: number;
  slippage_bps?: number;
  spread_bps?: number;
}

/** Resolved cost model echoed on the response (present only when one was supplied). */
export interface CostModelResolved {
  type: CostModelType;
  label: string;
  commission_bps: number;
  slippage_bps: number;
  spread_bps: number;
  effective_bps_per_side: number;
}

/** Position-sizing model (research v1). Scales exposure magnitude only; |exposure| ≤ 1. */
export type PositionSizingType =
  | "full_allocation"
  | "fixed_fraction"
  | "volatility_target"
  | "max_exposure";

export interface PositionSizing {
  type: PositionSizingType;
  /** fixed_fraction: capital fraction (0–1]. */
  fraction?: number;
  /** volatility_target: annualized target volatility (e.g. 0.15). */
  target_volatility?: number;
  /** volatility_target: realized-vol lookback in trading days (default 20). */
  lookback_days?: number;
  /** max_exposure / volatility_target: cap on |exposure| (0–1]; remainder stays in cash. */
  max_exposure?: number;
}

/** Resolved position sizing echoed on the response (full_allocation when omitted). */
export interface PositionSizingResolved {
  type: PositionSizingType;
  label: string;
  fraction?: number | null;
  target_volatility?: number | null;
  lookback_days?: number | null;
  max_exposure?: number | null;
}

/** Risk-management exits (research v1). Rules close to cash only; never reverse. */
export type RiskManagementType =
  | "none"
  | "fixed_stop_take_profit"
  | "trailing_stop"
  | "max_holding_days"
  | "combined";

export interface RiskManagement {
  type: RiskManagementType;
  /** Decimals (0.10 = 10%). */
  stop_loss_pct?: number;
  take_profit_pct?: number;
  trailing_stop_pct?: number;
  max_holding_days?: number;
}

export interface RiskManagementResolved {
  type: RiskManagementType;
  label: string;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  trailing_stop_pct?: number | null;
  max_holding_days?: number | null;
}

export interface RiskDiagnostics {
  risk_exit_count: number;
  stop_loss_count: number;
  take_profit_count: number;
  trailing_stop_count: number;
  max_holding_exit_count: number;
  risk_exit_rate: number;
}

/** Annualization convention for risk metrics (research v1). */
export type AnnualizationMode = "trading_days_252" | "crypto_365" | "auto";

/** Robustness Lab v1 — opt-in bootstrap on daily strategy returns. */
export interface RobustnessConfig {
  enabled: boolean;
  method?: "block_bootstrap_returns";
  n_simulations?: number;
  block_size?: number;
  seed?: number;
}

export interface RobustnessSummary {
  median_final_return: number;
  p05_final_return: number;
  p95_final_return: number;
  probability_of_loss: number;
  probability_of_outperforming_benchmark?: number | null;
  median_max_drawdown: number;
  /** The bad tail: 95th-percentile drawdown severity (more negative than median). */
  p95_max_drawdown: number;
  median_sharpe: number;
  p05_sharpe: number;
  p95_sharpe: number;
}

export interface RobustnessHistogramBin {
  lower: number;
  upper: number;
  count: number;
}

export interface RobustnessResult {
  enabled: boolean;
  method: string;
  n_simulations: number;
  block_size: number;
  seed: number;
  summary?: RobustnessSummary | null;
  final_return_histogram: RobustnessHistogramBin[];
  /** Heuristic A–F grade (null when not computable) — not a recommendation. */
  grade?: "A" | "B" | "C" | "D" | "F" | null;
  deflated_sharpe?: number | null;
  warnings: string[];
}

/** Stability Lab v1 — opt-in parameter-sensitivity sweep (SMA Crossover). */
export type SensitivityMetric =
  | "sharpe"
  | "total_return"
  | "cagr"
  | "max_drawdown"
  | "calmar";

export interface SensitivityConfig {
  enabled: boolean;
  metric?: SensitivityMetric;
  x_param?: "fast_window";
  y_param?: "slow_window";
  x_values?: number[];
  y_values?: number[];
  max_runs?: number;
}

export interface SensitivityRunMetrics {
  sharpe: number;
  total_return: number;
  cagr: number;
  max_drawdown: number;
  calmar: number;
}

export interface SensitivityRun {
  fast_window: number;
  slow_window: number;
  valid: boolean;
  metrics?: SensitivityRunMetrics | null;
  num_trades?: number | null;
  warning?: string | null;
}

export interface SensitivityPoint {
  fast_window: number;
  slow_window: number;
  value?: number | null;
}

export interface SensitivitySummary {
  best_value?: number | null;
  best_params?: SensitivityPoint | null;
  selected_value?: number | null;
  neighbor_median?: number | null;
  neighbor_min?: number | null;
  /** Heuristic 0–1 (null when too few valid neighbors). */
  stability_score?: number | null;
  fragility_flag: boolean;
  explanation: string;
}

export interface SensitivityResult {
  enabled: boolean;
  supported: boolean;
  strategy: string;
  metric: SensitivityMetric;
  x_param: string;
  y_param: string;
  x_values: number[];
  y_values: number[];
  selected_point?: SensitivityPoint | null;
  /** Rows = y_values, columns = x_values; null = invalid cell. */
  matrix: (number | null)[][];
  runs: SensitivityRun[];
  summary?: SensitivitySummary | null;
  warnings: string[];
}

/** Deterministic fingerprint of the normalized result-changing inputs. */
export interface Reproducibility {
  schema_version: string;
  /** Short display hash (first 12 hex chars of the SHA-256). */
  config_hash: string;
  /** Full SHA-256 hex of the canonical config JSON. */
  config_hash_full: string;
  /** Compact canonical JSON the hash was computed over (for audit). */
  canonical_config_json: string;
}

/** Benchmark comparison (research v1). Never changes strategy trades/results. */
export type BenchmarkMode = "none" | "buy_and_hold_same_asset" | "custom_ticker";

export interface BenchmarkConfig {
  mode: BenchmarkMode;
  /** Required for custom_ticker; ignored otherwise. */
  ticker?: string;
}

export interface BenchmarkMetricsBlock {
  total_return: number;
  cagr: number;
  volatility: number;
  sharpe: number;
  max_drawdown: number;
}

/** Strategy-vs-benchmark metrics on aligned returns (null = not computable). */
export interface ActiveMetrics {
  excess_total_return?: number | null;
  excess_cagr?: number | null;
  alpha?: number | null;
  beta?: number | null;
  correlation?: number | null;
  tracking_error?: number | null;
  information_ratio?: number | null;
  aligned_points?: number | null;
}

export interface BenchmarkEquityPoint {
  date: string;
  equity: number;
}

export interface BenchmarkAnalytics {
  mode: BenchmarkMode;
  ticker?: string | null;
  display_name: string;
  metrics?: BenchmarkMetricsBlock | null;
  active_metrics?: ActiveMetrics | null;
  equity_curve?: BenchmarkEquityPoint[] | null;
  data_provider?: string | null;
  data_quality?: DataQuality | null;
  warnings: string[];
}

/** Diagnostics for the price series fed to the engine (informational only). */
export interface DataQuality {
  provider: string;
  ticker: string;
  requested_start_date: string;
  requested_end_date: string;
  actual_start_date?: string | null;
  actual_end_date?: string | null;
  row_count: number;
  missing_value_count: number;
  duplicate_date_count: number;
  inferred_frequency: string;
  calendar_gap_count: number;
  first_price?: number | null;
  last_price?: number | null;
  price_column_used: string;
  adjusted: boolean;
  warnings: string[];
}

/** Why a trade happened (only present when risk management is active). */
export type TradeReason =
  | "signal_entry"
  | "signal_exit"
  | "signal_flip"
  | "stop_loss"
  | "take_profit"
  | "trailing_stop"
  | "max_holding_days";

export interface BacktestRequest {
  ticker: string;
  start_date: string;
  end_date: string;
  fast_window: number;
  slow_window: number;
  transaction_cost_bps: number;
  initial_capital: number;
  position_mode?: PositionMode;
  cost_model?: CostModel;
  position_sizing?: PositionSizing;
  risk_management?: RiskManagement;
  annualization_mode?: AnnualizationMode;
  benchmark?: BenchmarkConfig;
  robustness?: RobustnessConfig;
  sensitivity?: SensitivityConfig;
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
  cost_model?: CostModel;
  position_sizing?: PositionSizing;
  risk_management?: RiskManagement;
  annualization_mode?: AnnualizationMode;
  benchmark?: BenchmarkConfig;
  robustness?: RobustnessConfig;
  sensitivity?: SensitivityConfig;
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
  cost_model?: CostModel;
  position_sizing?: PositionSizing;
  risk_management?: RiskManagement;
  annualization_mode?: AnnualizationMode;
  benchmark?: BenchmarkConfig;
  robustness?: RobustnessConfig;
  sensitivity?: SensitivityConfig;
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
  position_mode?: PositionMode;
  cost_model?: CostModel;
  position_sizing?: PositionSizing;
  risk_management?: RiskManagement;
  annualization_mode?: AnnualizationMode;
  benchmark?: BenchmarkConfig;
  robustness?: RobustnessConfig;
  sensitivity?: SensitivityConfig;
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
  position_mode?: PositionMode;
  cost_model?: CostModel;
  position_sizing?: PositionSizing;
  risk_management?: RiskManagement;
  annualization_mode?: AnnualizationMode;
  benchmark?: BenchmarkConfig;
  robustness?: RobustnessConfig;
  sensitivity?: SensitivityConfig;
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
  cost_model?: CostModel;
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
  /**
   * Single-asset long/short: "BUY" | "SELL" | "SHORT" | "COVER" |
   * "FLIP_TO_LONG" | "FLIP_TO_SHORT".  Pairs: "LONG SPREAD" | "SHORT SPREAD" |
   * "EXIT".
   */
  action:
    | "BUY"
    | "SELL"
    | "SHORT"
    | "COVER"
    | "FLIP_TO_LONG"
    | "FLIP_TO_SHORT"
    | "LONG SPREAD"
    | "SHORT SPREAD"
    | "EXIT";
  price: number;
  shares: number;
  cost: number;
  /** Present only when risk management is active (null otherwise). */
  reason?: TradeReason | null;
}

export interface EquityPoint {
  date: string;
  strategy: number;
  benchmark: number;
}

/** Direction / exposure diagnostics (present for single-asset backtests). */
export interface BacktestDiagnostics {
  long_trade_count: number;
  short_trade_count: number;
  percent_time_long: number;
  percent_time_short: number;
  percent_time_cash: number;
  gross_long_return: number;
  gross_short_return: number;
  short_return_contribution: number;
  turnover_estimate: number;
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

  /** Effective per-side cost in bps applied (resolved from cost_model when supplied). */
  transaction_cost_bps: number;
  initial_capital: number;
  /** Resolved cost model echo — present only when a cost_model was supplied. */
  cost_model?: CostModelResolved | null;
  /** Effective per-side cost in bps applied on turnover. */
  effective_cost_bps?: number | null;
  /** Sum of all per-trade dollar transaction costs over the backtest. */
  total_transaction_cost?: number | null;
  /** Total return given up to transaction costs (gross-of-cost minus net). */
  cost_drag_return?: number | null;
  /** Resolved position-sizing echo — full_allocation when omitted by older callers. */
  position_sizing?: PositionSizingResolved | null;
  /** Mean absolute exposure (|position|) over the backtest period. */
  average_exposure?: number | null;
  /** Resolved risk-management echo — present only when risk rules are active. */
  risk_management?: RiskManagementResolved | null;
  /** Risk-exit counts — present only when risk rules are active. */
  risk_diagnostics?: RiskDiagnostics | null;
  /** Annualization convention (research v1) — present on new responses. */
  annualization_mode?: AnnualizationMode | null;
  annualization_mode_used?: string | null;
  periods_per_year?: number | null;
  annualization_warning?: string | null;
  /** Market-data provider + diagnostics (research v1) — present on new responses. */
  data_provider?: string | null;
  data_quality?: DataQuality | null;
  /** Benchmark + active analytics (absent when benchmark mode is "none"). */
  benchmark_analytics?: BenchmarkAnalytics | null;
  /** Reproducible config hash of the normalized inputs. */
  reproducibility?: Reproducibility | null;
  /** Robustness Lab block (present only when requested). */
  robustness?: RobustnessResult | null;
  /** Stability Lab parameter-sensitivity block (present only when requested). */
  sensitivity?: SensitivityResult | null;
  /** Direction mode used (defaults to "long_only" for strategies without it). */
  position_mode?: PositionMode;
  strategy_metrics: PerformanceMetrics;
  benchmark_metrics: PerformanceMetrics;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
  num_trades: number;
  /** Direction / exposure diagnostics (absent on older saved results). */
  diagnostics?: BacktestDiagnostics | null;
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
  position_mode?: PositionMode;
  cost_model?: CostModel;
  position_sizing?: PositionSizing;
  risk_management?: RiskManagement;
  annualization_mode?: AnnualizationMode;
  benchmark?: BenchmarkConfig;
}

export interface StrategyResultItem {
  strategy: string;
  display_name: string;
  params: Record<string, number | string>;
  /** Direction mode actually applied (long_only for RSI/Bollinger). */
  position_mode?: PositionMode;
  metrics: PerformanceMetrics;
  equity_curve: EquityPoint[];
  num_trades: number;
  average_exposure?: number | null;
  risk_exit_count?: number | null;
  effective_cost_bps?: number | null;
  unsupported_features?: string[];
  warnings?: string[];
  /** Strategy-vs-benchmark metrics (absent when benchmark mode is "none"). */
  active_metrics?: ActiveMetrics | null;
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
  /** Direction mode requested for the comparison (defaults to long_only). */
  position_mode?: PositionMode;
  cost_model?: CostModelResolved | null;
  effective_cost_bps?: number | null;
  position_sizing?: PositionSizingResolved | null;
  risk_management?: RiskManagementResolved | null;
  warnings?: string[];
  annualization_mode?: AnnualizationMode | null;
  annualization_mode_used?: string | null;
  periods_per_year?: number | null;
  annualization_warning?: string | null;
  data_provider?: string | null;
  data_quality?: DataQuality | null;
  /** Shared benchmark block (absent when benchmark mode is "none"). */
  benchmark_analytics?: BenchmarkAnalytics | null;
  /** Reproducible config hash of the normalized comparison inputs. */
  reproducibility?: Reproducibility | null;
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
// Saved Reports (Report Gallery)
// ---------------------------------------------------------------------------

export type SavedReportSourceType =
  | "backtest"
  | "csv_backtest"
  | "custom_strategy"
  | "portfolio_backtest"
  | "portfolio_optimization"
  | "risk_dashboard"
  | "stress_test"
  | "factor_analysis"
  | "manual";

export interface SavedReportCreate {
  title: string;
  report_type: string;
  source_type: SavedReportSourceType;
  source_id?: number | null;
  tickers: string[];
  strategy?: string | null;
  date_range_start?: string | null;
  date_range_end?: string | null;
  markdown_content: string;
  metadata: Record<string, unknown>;
  notes: string;
}

/** Mutable-metadata payload for PUT /saved-reports/{id}. */
export interface SavedReportUpdate {
  title: string;
  notes: string;
  metadata: Record<string, unknown>;
}

/** Lightweight list-view row — no Markdown content blob. */
export interface SavedReportSummary {
  id: number;
  created_at: string;
  updated_at: string;
  title: string;
  report_type: string;
  source_type: SavedReportSourceType;
  source_id: number | null;
  tickers: string[];
  strategy: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  notes: string;
}

/** Full record including the Markdown content and structured metadata. */
export interface SavedReportFull extends SavedReportSummary {
  markdown_content: string;
  metadata: Record<string, unknown>;
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
