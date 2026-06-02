/**
 * Markdown research-report generation (client-side, v1).
 *
 * All reports are built in the browser from existing result state and
 * downloaded as a `.md` file — no backend, no stored files, no PDF rendering.
 * Each builder returns `{ filename, content }`; PDF export is future work.
 */

import type {
  BacktestResponse,
  EquityPoint,
  FactorAnalysisResponse,
  PerformanceMetrics,
  PortfolioBacktestResponse,
  PortfolioOptimizeResponse,
  RiskDashboardResponse,
  SavedBacktestFull,
  StressTestResponse,
  TradeRecord,
} from "./types";

export interface Report {
  filename: string;
  content: string;
}

// ---------------------------------------------------------------------------
// Download helper
// ---------------------------------------------------------------------------

/** Trigger a browser download of a text file. */
export function downloadTextFile(
  filename: string,
  content: string,
  mime = "text/markdown;charset=utf-8",
): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

export function formatPercent(value: number | null | undefined, decimals = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(decimals)}%`;
}

export function formatCurrency(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatRatio(value: number | null | undefined, decimals = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(decimals);
}

function slug(s: string): string {
  return (
    s
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "report"
  );
}

/** "20260602-1530" — local timestamp for filenames. */
function timestamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}` +
    `-${p(d.getHours())}${p(d.getMinutes())}`
  );
}

function generatedAt(): string {
  return new Date().toISOString();
}

// ---------------------------------------------------------------------------
// Markdown helpers
// ---------------------------------------------------------------------------

function mdTable(headers: string[], rows: (string | number)[][]): string {
  const head = `| ${headers.join(" | ")} |`;
  const sep = `| ${headers.map(() => "---").join(" | ")} |`;
  const body = rows.map((r) => `| ${r.map((c) => String(c)).join(" | ")} |`).join("\n");
  return `${head}\n${sep}\n${body}`;
}

/** Performance-metrics table from a PerformanceMetrics-like object. */
function metricsTable(
  metrics: PerformanceMetrics | Record<string, unknown>,
  includeBenchmark?: Partial<PerformanceMetrics>,
): string {
  const m = metrics as Record<string, unknown>;
  const num = (v: unknown) => (typeof v === "number" ? v : undefined);
  const rows: (string | number)[][] = [
    ["Total Return", formatPercent(num(m.total_return))],
    ["CAGR", formatPercent(num(m.cagr))],
    ["Sharpe Ratio", formatRatio(num(m.sharpe_ratio))],
    ["Sortino Ratio", formatRatio(num(m.sortino_ratio))],
    ["Calmar Ratio", formatRatio(num(m.calmar_ratio))],
    ["Max Drawdown", formatPercent(num(m.max_drawdown))],
    ["Volatility", formatPercent(num(m.volatility))],
    ["Win Rate", formatPercent(num(m.win_rate))],
    ["Trading Days", num(m.num_days) ?? "—"],
  ];
  if (includeBenchmark) {
    const b = includeBenchmark;
    return mdTable(
      ["Metric", "Strategy", "Benchmark"],
      [
        ["Total Return", formatPercent(num(m.total_return)), formatPercent(b.total_return)],
        ["CAGR", formatPercent(num(m.cagr)), formatPercent(b.cagr)],
        ["Sharpe Ratio", formatRatio(num(m.sharpe_ratio)), formatRatio(b.sharpe_ratio)],
        ["Sortino Ratio", formatRatio(num(m.sortino_ratio)), formatRatio(b.sortino_ratio)],
        ["Calmar Ratio", formatRatio(num(m.calmar_ratio)), formatRatio(b.calmar_ratio)],
        ["Max Drawdown", formatPercent(num(m.max_drawdown)), formatPercent(b.max_drawdown)],
        ["Volatility", formatPercent(num(m.volatility)), formatPercent(b.volatility)],
        ["Win Rate", formatPercent(num(m.win_rate)), formatPercent(b.win_rate)],
      ],
    );
  }
  return mdTable(["Metric", "Value"], rows);
}

/** Equity-curve summary stats from a numeric value series. */
function equitySummary(values: number[]): string {
  if (!values.length) return "_No equity data._";
  const start = values[0];
  const end = values[values.length - 1];
  let peak = values[0];
  let worstDd = 0;
  for (const v of values) {
    if (v > peak) peak = v;
    const dd = peak > 0 ? (v - peak) / peak : 0;
    if (dd < worstDd) worstDd = dd;
  }
  const finalDd = peak > 0 ? (end - peak) / peak : 0;
  return mdTable(
    ["Measure", "Value"],
    [
      ["Start Equity", formatCurrency(start)],
      ["End Equity", formatCurrency(end)],
      ["Peak Equity", formatCurrency(peak)],
      ["Final Drawdown", formatPercent(finalDd)],
      ["Worst Drawdown", formatPercent(worstDd)],
    ],
  );
}

function tradesSummary(trades: TradeRecord[]): string {
  if (!trades.length) return "_No trades._";
  const fmt = (t: TradeRecord) =>
    [t.date, t.action, `$${t.price.toFixed(2)}`, t.shares, `$${t.cost.toFixed(2)}`];
  const head = trades.slice(0, 5);
  const tail = trades.length > 10 ? trades.slice(-5) : [];
  const rows = head.map(fmt);
  if (tail.length) {
    rows.push(["…", "…", "…", "…", "…"]);
    rows.push(...tail.map(fmt));
  } else {
    rows.push(...trades.slice(5).map(fmt));
  }
  return (
    `Total trade events: **${trades.length}**\n\n` +
    mdTable(["Date", "Action", "Price", "Shares", "Cost"], rows)
  );
}

const DISCLAIMER = `## Risk / Caveats

- **Historical backtest only.** Results reflect simulated performance on past data.
- **No guarantee of future performance.** Past results do not predict future returns.
- **Data source limitations.** Prices come from Yahoo Finance (yfinance) and may contain gaps or errors.
- **Transaction cost & slippage.** Costs use a simple basis-point assumption; real fills, slippage, and market impact are not modelled.
- **Possible overfitting.** Parameters or weights chosen on historical data may not generalise out-of-sample.
- This report is for research and educational purposes only and is **not investment advice**.
`;

function header(analysisType: string): string {
  return `# QuantLab Research Report\n\n_Generated at ${generatedAt()}_\n\n**Analysis type:** ${analysisType}\n`;
}

function weightsTable(weights: Record<string, number>): string {
  return mdTable(
    ["Asset", "Weight"],
    Object.entries(weights)
      .sort((a, b) => b[1] - a[1])
      .map(([t, w]) => [t, formatPercent(w, 1)]),
  );
}

// ---------------------------------------------------------------------------
// Builders
// ---------------------------------------------------------------------------

const STRATEGY_LABELS: Record<string, string> = {
  sma_crossover: "SMA Crossover",
  rsi_mean_reversion: "RSI Mean Reversion",
  bollinger_band: "Bollinger Band",
  momentum: "Time-Series Momentum",
  volatility_breakout: "Volatility Breakout",
  pairs: "Pairs Trading",
  custom: "Custom Strategy",
};

function backtestParams(r: BacktestResponse): [string, string][] {
  switch (r.strategy) {
    case "sma_crossover":
      return [["Fast window", String(r.fast_window)], ["Slow window", String(r.slow_window)]];
    case "rsi_mean_reversion":
      return [
        ["RSI window", String(r.rsi_window)],
        ["Oversold threshold", String(r.oversold_threshold)],
        ["Exit threshold", String(r.exit_threshold)],
      ];
    case "bollinger_band":
      return [
        ["Window", String(r.bb_window)],
        ["Std devs", String(r.bb_num_std)],
        ["Exit band", String(r.bb_exit_band)],
      ];
    case "momentum":
      return [
        ["Momentum window", String(r.momentum_window)],
        ["Entry threshold", String(r.momentum_entry_threshold)],
        ["Exit threshold", String(r.momentum_exit_threshold)],
      ];
    case "volatility_breakout":
      return [
        ["Lookback window", String(r.vb_lookback_window)],
        ["Breakout multiplier", String(r.vb_breakout_multiplier)],
        ["Exit window", String(r.vb_exit_window)],
      ];
    case "pairs":
      return [
        ["Asset Y", String(r.pairs_asset_y)],
        ["Asset X", String(r.pairs_asset_x)],
        ["Lookback window", String(r.pairs_lookback_window)],
        ["Entry z-score", String(r.pairs_entry_z_score)],
        ["Exit z-score", String(r.pairs_exit_z_score)],
      ];
    default:
      return [];
  }
}

export function buildBacktestReport(r: BacktestResponse): Report {
  const label = STRATEGY_LABELS[r.strategy] ?? r.strategy;
  const m = r.strategy_metrics;
  const params = backtestParams(r);
  const content = [
    header("Single-Strategy Backtest"),
    `## Metadata\n`,
    mdTable(
      ["Field", "Value"],
      [
        ["Ticker", r.ticker],
        ["Strategy", label],
        ["Date range", `${r.start_date} → ${r.end_date}`],
        ["Initial capital", formatCurrency(r.initial_capital)],
        ["Transaction cost", `${r.transaction_cost_bps} bps`],
      ],
    ),
    `\n## Executive Summary\n`,
    `- **Total Return:** ${formatPercent(m.total_return)}`,
    `- **CAGR:** ${formatPercent(m.cagr)}`,
    `- **Sharpe:** ${formatRatio(m.sharpe_ratio)}`,
    `- **Sortino:** ${formatRatio(m.sortino_ratio)}`,
    `- **Max Drawdown:** ${formatPercent(m.max_drawdown)}`,
    `- **Volatility:** ${formatPercent(m.volatility)}`,
    `- **Trades:** ${r.num_trades}`,
    `\n## Parameters\n`,
    params.length ? mdTable(["Parameter", "Value"], params) : "_No parameters._",
    `\n## Performance Metrics\n`,
    metricsTable(m, r.benchmark_metrics),
    `\n## Equity Curve Summary\n`,
    equitySummary((r.equity_curve as EquityPoint[]).map((p) => p.strategy)),
    `\n## Trades Summary\n`,
    tradesSummary(r.trades),
    `\n${DISCLAIMER}`,
  ].join("\n");

  return {
    filename: `quantlab-report-${slug(r.ticker)}-${slug(r.strategy)}-${r.start_date}-${r.end_date}.md`,
    content,
  };
}

export function buildSavedBacktestReport(rec: SavedBacktestFull): Report {
  const m = (rec.metrics ?? {}) as Partial<PerformanceMetrics> & Record<string, unknown>;
  const num = (v: unknown) => (typeof v === "number" ? v : undefined);
  const params = Object.entries(rec.params ?? {}).map(
    ([k, v]) => [k, String(v)] as [string, string],
  );
  const equity = (rec.equity_curve ?? []).map((p) => p.strategy);
  const content = [
    header("Saved Backtest"),
    `## Metadata\n`,
    mdTable(
      ["Field", "Value"],
      [
        ["Name", rec.name],
        ["Ticker", rec.ticker],
        ["Strategy", STRATEGY_LABELS[rec.strategy] ?? rec.strategy],
        ["Date range", `${rec.start_date} → ${rec.end_date}`],
        ["Initial capital", formatCurrency(rec.initial_capital)],
        ["Transaction cost", `${rec.transaction_cost_bps} bps`],
        ["Saved at", rec.created_at],
      ],
    ),
    `\n## Executive Summary\n`,
    `- **Total Return:** ${formatPercent(num(m.total_return))}`,
    `- **CAGR:** ${formatPercent(num(m.cagr))}`,
    `- **Sharpe:** ${formatRatio(num(m.sharpe_ratio))}`,
    `- **Sortino:** ${formatRatio(num(m.sortino_ratio))}`,
    `- **Max Drawdown:** ${formatPercent(num(m.max_drawdown))}`,
    `- **Volatility:** ${formatPercent(num(m.volatility))}`,
    `- **Trades:** ${rec.trades?.length ?? 0}`,
    rec.notes ? `\n## Notes\n\n${rec.notes}` : "",
    `\n## Parameters\n`,
    params.length ? mdTable(["Parameter", "Value"], params) : "_No parameters._",
    `\n## Performance Metrics\n`,
    metricsTable(m),
    `\n## Equity Curve Summary\n`,
    equitySummary(equity),
    `\n## Trades Summary\n`,
    tradesSummary((rec.trades ?? []) as TradeRecord[]),
    `\n${DISCLAIMER}`,
  ].join("\n");

  return { filename: `quantlab-report-saved-${slug(rec.name)}.md`, content };
}

export function buildPortfolioBacktestReport(r: PortfolioBacktestResponse): Report {
  const m = r.metrics;
  const turnovers = r.rebalance_events.map((e) => e.turnover);
  const avgTurnover = turnovers.length
    ? turnovers.reduce((a, b) => a + b, 0) / turnovers.length
    : 0;
  const finalWeights = r.weights.length ? r.weights[r.weights.length - 1].weights : {};
  const content = [
    header("Equal-Weight Portfolio Backtest"),
    `## Metadata\n`,
    mdTable(
      ["Field", "Value"],
      [
        ["Tickers", r.tickers.join(", ")],
        ["Strategy", "Equal-weight portfolio"],
        ["Rebalance", r.rebalance_frequency],
        ["Benchmark", r.benchmark_ticker],
        ["Date range", `${r.start_date} → ${r.end_date}`],
        ["Initial capital", formatCurrency(r.initial_capital)],
        ["Transaction cost", `${r.transaction_cost_bps} bps`],
      ],
    ),
    `\n## Executive Summary\n`,
    `- **Total Return:** ${formatPercent(m.total_return)}`,
    `- **CAGR:** ${formatPercent(m.cagr)}`,
    `- **Sharpe:** ${formatRatio(m.sharpe_ratio)}`,
    `- **Sortino:** ${formatRatio(m.sortino_ratio)}`,
    `- **Max Drawdown:** ${formatPercent(m.max_drawdown)}`,
    `- **Volatility:** ${formatPercent(m.volatility)}`,
    `\n## Final Weights\n`,
    Object.keys(finalWeights).length ? weightsTable(finalWeights) : "_No weights._",
    `\n## Performance Metrics\n`,
    metricsTable(m, r.benchmark_metrics),
    `\n## Equity Curve Summary\n`,
    equitySummary(r.equity_curve.map((p) => p.portfolio)),
    `\n## Rebalance Events Summary\n`,
    `- **Rebalance events:** ${r.rebalance_events.length}`,
    `- **Average turnover:** ${formatPercent(avgTurnover, 1)}`,
    `\n${DISCLAIMER}`,
  ].join("\n");

  return { filename: `quantlab-report-portfolio-backtest-${timestamp()}.md`, content };
}

export function buildPortfolioOptimizeReport(r: PortfolioOptimizeResponse): Report {
  const m = r.metrics;
  const content = [
    header("Portfolio Optimization (in-sample)"),
    `## Metadata\n`,
    mdTable(
      ["Field", "Value"],
      [
        ["Tickers", r.tickers.join(", ")],
        ["Objective", r.objective],
        ["Date range", `${r.start_date} → ${r.end_date}`],
        ["Initial capital", formatCurrency(r.initial_capital)],
        ["Risk-free rate", formatPercent(r.risk_free_rate)],
      ],
    ),
    `\n## Executive Summary\n`,
    `- **Expected Return (annual):** ${formatPercent(r.portfolio_expected_return)}`,
    `- **Volatility (annual):** ${formatPercent(r.portfolio_volatility)}`,
    `- **Sharpe:** ${formatRatio(r.portfolio_sharpe)}`,
    `- **Backtest Total Return:** ${formatPercent(m.total_return)}`,
    `- **Backtest Max Drawdown:** ${formatPercent(m.max_drawdown)}`,
    `\n## Optimized Weights\n`,
    weightsTable(r.weights),
    `\n## Performance Metrics (optimized vs equal weight)\n`,
    metricsTable(m, r.equal_weight_metrics),
    `\n## Equity Curve Summary\n`,
    equitySummary(r.equity_curve.map((p) => p.value)),
    `\n> ⚠️ In-sample optimization: weights were fit and backtested on the same window and can overfit.`,
    `\n${DISCLAIMER}`,
  ].join("\n");

  return { filename: `quantlab-report-optimization-${slug(r.objective)}-${timestamp()}.md`, content };
}

export function buildRiskDashboardReport(r: RiskDashboardResponse): Report {
  const ew = r.equal_weight_portfolio;
  const diag = r.correlation_diagnostics;
  const assetRows = r.tickers.map((t) => [
    t,
    formatPercent(r.asset_annual_returns[t], 1),
    formatPercent(r.asset_annual_volatilities[t], 1),
    formatPercent(r.risk_contribution[t], 1),
  ]);
  const corrRows = r.tickers.map((row) => [
    row,
    ...r.tickers.map((col) => formatRatio(r.correlation_matrix[row][col])),
  ]);
  const content = [
    header("Portfolio Risk Dashboard"),
    `## Metadata\n`,
    mdTable(
      ["Field", "Value"],
      [
        ["Tickers", r.tickers.join(", ")],
        ["Date range", `${r.start_date} → ${r.end_date}`],
      ],
    ),
    `\n## Executive Summary\n`,
    `- **Equal-Weight Return (annual):** ${formatPercent(ew.expected_return)}`,
    `- **Equal-Weight Volatility (annual):** ${formatPercent(ew.volatility)}`,
    `- **Diversification Ratio:** ${formatRatio(ew.diversification_ratio)}`,
    `- **Average Pairwise Correlation:** ${formatRatio(diag.average_pairwise_correlation)}`,
    `- **Most Correlated:** ${diag.most_correlated_pair?.join(" / ") ?? "—"} (${formatRatio(diag.max_pairwise_correlation)})`,
    `- **Least Correlated:** ${diag.least_correlated_pair?.join(" / ") ?? "—"} (${formatRatio(diag.min_pairwise_correlation)})`,
    `\n## Asset Risk Summary\n`,
    mdTable(["Ticker", "Annual Return", "Annual Volatility", "Risk Contribution"], assetRows),
    `\n## Correlation Matrix\n`,
    mdTable(["", ...r.tickers], corrRows),
    `\n${DISCLAIMER}`,
  ].join("\n");

  return { filename: `quantlab-report-risk-dashboard-${timestamp()}.md`, content };
}

export function buildStressTestReport(r: StressTestResponse): Report {
  const scnRows = r.scenarios.map((s) => [
    s.name,
    formatPercent(s.total_return, 1),
    formatPercent(s.benchmark_total_return, 1),
    formatPercent(s.excess_return, 1),
    formatPercent(s.max_drawdown, 1),
    formatPercent(s.worst_day_return, 1),
    formatPercent(s.annualized_volatility, 0),
  ]);
  const content = [
    header("Portfolio Stress Test"),
    `## Metadata\n`,
    mdTable(
      ["Field", "Value"],
      [
        ["Tickers", r.tickers.join(", ")],
        ["Benchmark", r.benchmark_ticker],
        ["Date range", `${r.start_date} → ${r.end_date}`],
      ],
    ),
    `\n## Weights\n`,
    weightsTable(r.weights),
    `\n## Full-Period Performance (portfolio vs benchmark)\n`,
    metricsTable(r.full_period_metrics, r.benchmark_full_period_metrics),
    `\n## Scenario Comparison\n`,
    mdTable(
      ["Scenario", "Portfolio", "Benchmark", "Excess", "Max DD", "Worst Day", "Volatility"],
      scnRows,
    ),
    `\n${DISCLAIMER}`,
  ].join("\n");

  return { filename: `quantlab-report-stress-test-${timestamp()}.md`, content };
}

export function buildFactorAnalysisReport(r: FactorAnalysisResponse): Report {
  const factorNames = Object.keys(r.factor_tickers);
  const betaRows = factorNames.map((name) => [
    name,
    r.factor_tickers[name],
    formatRatio(r.betas[name]),
  ]);
  const content = [
    header("Factor Exposure / Regression Analysis"),
    `## Metadata\n`,
    mdTable(
      ["Field", "Value"],
      [
        ["Tickers", r.tickers.join(", ")],
        ["Date range", `${r.start_date} → ${r.end_date}`],
        ["Factors", factorNames.map((n) => `${n} (${r.factor_tickers[n]})`).join(", ")],
      ],
    ),
    `\n## Executive Summary\n`,
    `- **R²:** ${formatRatio(r.r_squared, 3)}`,
    `- **Annualized Alpha:** ${formatPercent(r.alpha_annualized)}`,
    `- **Residual Volatility:** ${formatPercent(r.residual_volatility)}`,
    `- **Largest Exposure:** ${r.diagnostics.absolute_largest_exposure ?? "—"}`,
    `- **Strongest +:** ${r.diagnostics.strongest_positive_factor ?? "—"} · **Strongest −:** ${r.diagnostics.strongest_negative_factor ?? "—"}`,
    r.diagnostics.multicollinearity_warning
      ? `\n> ⚠️ Multicollinearity detected — individual betas may be unstable.`
      : "",
    `\n## Portfolio Weights\n`,
    weightsTable(r.weights),
    `\n## Factor Betas\n`,
    mdTable(["Factor", "ETF", "Beta"], betaRows),
    `\n${DISCLAIMER}`,
  ].join("\n");

  return { filename: `quantlab-report-factor-analysis-${timestamp()}.md`, content };
}
