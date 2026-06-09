/**
 * Markdown research-report generation (client-side, v1).
 *
 * All reports are built in the browser from existing result state and
 * downloaded as a `.md` file — no backend and no stored files.
 * Each builder assembles a structured `ReportDoc` from the result, then
 * `renderReport(doc, template)` emits the Markdown for the chosen branded
 * template (Standard / Executive Summary / Quant Tear Sheet / Risk Report).
 * The print/PDF preview and Save-to-gallery flow reuse this same Markdown.
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
  SavedReportSourceType,
  StressTestResponse,
  TradeRecord,
} from "./types";

export interface Report {
  filename: string;
  content: string;
  /**
   * Optional structured metadata used when saving the report to the local
   * Report Gallery (Saved Reports).  Markdown download and PDF print ignore
   * these fields; the Save flow maps them onto a `SavedReportCreate` payload.
   */
  title?: string;
  reportType?: string;
  sourceType?: SavedReportSourceType;
  sourceId?: number | null;
  tickers?: string[];
  strategy?: string | null;
  dateRangeStart?: string | null;
  dateRangeEnd?: string | null;
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Branded report templates
// ---------------------------------------------------------------------------

export type ReportTemplate =
  | "standard"
  | "executive_summary"
  | "quant_tear_sheet"
  | "risk_report";

/** Selectable templates, in display order. */
export const REPORT_TEMPLATES: { id: ReportTemplate; label: string }[] = [
  { id: "standard", label: "Standard Research Report" },
  { id: "executive_summary", label: "Executive Summary" },
  { id: "quant_tear_sheet", label: "Quant Tear Sheet" },
  { id: "risk_report", label: "Risk Report" },
];

const TEMPLATE_LABELS: Record<ReportTemplate, string> = {
  standard: "Standard Research Report",
  executive_summary: "Executive Summary",
  quant_tear_sheet: "Quant Tear Sheet",
  risk_report: "Risk Report",
};

const TEMPLATE_FILE_SLUG: Record<ReportTemplate, string> = {
  standard: "",
  executive_summary: "executive-summary",
  quant_tear_sheet: "tear-sheet",
  risk_report: "risk-report",
};

interface BacktestReportOptions {
  analysisType?: string;
  dataSource?: "yfinance" | "csv";
  extraParameters?: [string, string][];
  /** Overrides the saved-report source type (defaults to "backtest"). */
  sourceType?: SavedReportSourceType;
}

interface PositionSizingMeta {
  type?: string;
  label?: string;
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
  a.download = ensureMarkdownFilename(filename);
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

function ensureMarkdownFilename(filename: string): string {
  const cleaned = filename.trim().replace(/[\\/:*?"<>|]+/g, "-") || "quantlab-report.md";
  return cleaned.toLowerCase().endsWith(".md") ? cleaned : `${cleaned}.md`;
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
  const head = `| ${headers.map(mdCell).join(" | ")} |`;
  const sep = `| ${headers.map(() => "---").join(" | ")} |`;
  const body = rows.map((r) => `| ${r.map(mdCell).join(" | ")} |`).join("\n");
  return body ? `${head}\n${sep}\n${body}` : `${head}\n${sep}`;
}

function mdCell(value: string | number): string {
  return String(value)
    .replace(/\r?\n/g, " ")
    .replace(/\|/g, "\\|")
    .trim();
}

function mdText(value: string): string {
  return value.replace(/\r\n/g, "\n").trim();
}

function formatParamValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "object") {
    const record = value as { label?: unknown };
    if (typeof record.label === "string") return record.label;
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function positionSizingMeta(value: unknown): PositionSizingMeta | undefined {
  if (!value || typeof value !== "object") return undefined;
  const record = value as { type?: unknown; label?: unknown };
  return {
    type: typeof record.type === "string" ? record.type : undefined,
    label: typeof record.label === "string" ? record.label : undefined,
  };
}

function positionSizingCaveat(positionSizing?: PositionSizingMeta): string {
  if (!positionSizing) return "";
  if (
    positionSizing.type === "full_allocation" ||
    positionSizing.type === "full"
  ) {
    return "";
  }
  const label = positionSizing.label ?? positionSizing.type ?? "custom sizing";
  return (
    `\n- **Position sizing.** Results reflect effective scaled exposure (${label}); ` +
    `returns, drawdowns, transaction costs, and trade events are based on ` +
    `exposure changes after sizing.`
  );
}

/** Wrap a body in a level-2 section heading. */
function section(heading: string, body: string): string {
  return `## ${heading}\n\n${body}`;
}

/** Join section blocks, dropping empty ones, with a trailing newline. */
function joinBlocks(blocks: (string | undefined | null)[]): string {
  return (
    blocks.filter((b): b is string => Boolean(b && b.trim())).join("\n\n") + "\n"
  );
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

/** Worst (deepest) peak-to-trough drawdown of an equity series, or undefined. */
function worstDrawdownValue(values: number[]): number | undefined {
  if (!values.length) return undefined;
  let peak = values[0];
  let worst = 0;
  for (const v of values) {
    if (v > peak) peak = v;
    const dd = peak > 0 ? (v - peak) / peak : 0;
    if (dd < worst) worst = dd;
  }
  return worst;
}

/** Drawdown-focused summary table (tear sheet). */
function drawdownSummary(values: number[]): string {
  if (!values.length) return "_No equity data._";
  let peak = values[0];
  let worst = 0;
  for (const v of values) {
    if (v > peak) peak = v;
    const dd = peak > 0 ? (v - peak) / peak : 0;
    if (dd < worst) worst = dd;
  }
  const end = values[values.length - 1];
  const finalDd = peak > 0 ? (end - peak) / peak : 0;
  return mdTable(
    ["Measure", "Value"],
    [
      ["Peak Equity", formatCurrency(peak)],
      ["Worst Drawdown", formatPercent(worst)],
      ["Final Drawdown", formatPercent(finalDd)],
    ],
  );
}

function tradesSummary(trades: TradeRecord[]): string {
  if (!trades.length) return "_No trades._";
  const fmt = (t: TradeRecord) =>
    [
      t.date,
      t.action,
      formatCurrency(t.price),
      t.shares.toLocaleString("en-US", { maximumFractionDigits: 4 }),
      formatCurrency(t.cost),
    ];
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
    mdTable(["Date", "Action", "Price", "Shares", "Transaction Cost"], rows)
  );
}

/** Square correlation/exposure matrix table. */
function corrMatrixTable(
  labels: string[],
  matrix: Record<string, Record<string, number>>,
): string {
  return mdTable(
    ["", ...labels],
    labels.map((row) => [row, ...labels.map((col) => formatRatio(matrix[row]?.[col]))]),
  );
}

const CRYPTO_BASE_TICKERS = new Set([
  "BTC",
  "ETH",
  "SOL",
  "BNB",
  "XRP",
  "ADA",
  "DOGE",
  "AVAX",
  "DOT",
  "LINK",
  "LTC",
  "BCH",
  "MATIC",
  "SHIB",
  "TRX",
  "UNI",
  "XLM",
  "ATOM",
  "ETC",
]);

function splitTickerLabel(label: string): string[] {
  return label
    .split(/[,\s/]+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

function isCryptoTicker(ticker: string): boolean {
  const t = ticker.trim().toUpperCase();
  const base = t.split("-")[0];
  return CRYPTO_BASE_TICKERS.has(base) || t.includes("CRYPTO");
}

/** Short-selling caveat bullets, included when a short-enabled mode was used. */
function shortSellingCaveat(positionMode?: string): string {
  if (positionMode !== "short_only" && positionMode !== "long_short") return "";
  const label = positionMode === "short_only" ? "short-only" : "long/short";
  return (
    `\n- **Short selling — risks not modelled.** This backtest ran in ${label} mode.  ` +
    `Borrow costs, margin, liquidation, and funding are **excluded**, and short ` +
    `exposure carries risks not represented here.\n- **Sensitivity.** Long/short ` +
    `results may be highly sensitive to signal timing and transaction costs.`
  );
}

function riskCaveats(
  tickers: string[],
  dataSource: BacktestReportOptions["dataSource"] = "yfinance",
  positionMode?: string,
  positionSizing?: PositionSizingMeta,
): string {
  const dataLine =
    dataSource === "csv"
      ? "- **Data source limitations.** Prices come from the uploaded CSV file; column choices, missing rows, date cleaning, and stale or erroneous prices affect results."
      : "- **Data source limitations.** Prices come from Yahoo Finance (yfinance) and may contain gaps or errors.";
  const cryptoTickers = Array.from(new Set(tickers.filter(isCryptoTicker)));
  const cryptoLine = cryptoTickers.length
    ? `\n- **Crypto / 24/7 markets.** ${cryptoTickers.join(", ")} trades outside equity market hours; annualized return, volatility, Sharpe, Sortino, and CAGR use QuantLab's standard daily-return convention and should be compared with care.`
    : "";

  return `## Risk / Caveats

- **Historical backtest only.** Results reflect simulated performance on past data.
- **No guarantee of future performance.** Past results do not predict future returns.
${dataLine}
- **Transaction cost & slippage.** Costs use a simple basis-point assumption; real fills, slippage, and market impact are not modelled.${positionSizingCaveat(positionSizing)}
- **Possible overfitting.** Parameters or weights chosen on historical data may not generalise out-of-sample.
- This report is for research and educational purposes only and is **not investment advice**.${shortSellingCaveat(positionMode)}
${cryptoLine}
`;
}

/** Shorter caveat block for the Executive Summary template. */
function keyCaveats(
  tickers: string[],
  dataSource: BacktestReportOptions["dataSource"] = "yfinance",
  positionMode?: string,
  positionSizing?: PositionSizingMeta,
): string {
  const cryptoTickers = Array.from(new Set(tickers.filter(isCryptoTicker)));
  const cryptoLine = cryptoTickers.length
    ? `\n- **Crypto / 24-7 markets.** ${cryptoTickers.join(", ")} use the standard daily-return convention; compare with care.`
    : "";
  const dataWord = dataSource === "csv" ? "Uploaded-CSV prices" : "Yahoo Finance prices";
  return `## Key Caveats

- **Historical only — no guarantee.** Simulated past performance does not predict future returns.
- **Simplified costs & data.** ${dataWord} with basis-point cost assumptions; slippage and market impact are not modelled.${positionSizingCaveat(positionSizing)}
- Research and educational purposes only — **not investment advice**.${shortSellingCaveat(positionMode)}${cryptoLine}
`;
}

/** Annualization note appended to the Quant Tear Sheet. */
function annualizationNote(): string {
  return "> **Annualization note.** CAGR, volatility, Sharpe, and Sortino assume ~252 trading days per year and are extrapolated from the sampled window; short periods can distort them.";
}

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
// Structured report model + template renderer
// ---------------------------------------------------------------------------

interface ReportSaveMeta {
  title: string;
  reportType: string;
  sourceType: SavedReportSourceType;
  sourceId?: number | null;
  tickers: string[];
  strategy?: string | null;
  dateRangeStart?: string | null;
  dateRangeEnd?: string | null;
  metadata: Record<string, unknown>;
}

interface ReportDoc {
  analysisType: string;
  caveatTickers: string[];
  dataSource?: "yfinance" | "csv";
  /** Direction mode, when applicable — drives the short-selling caveat. */
  positionMode?: string;
  /** Position sizing, when applicable — drives the sizing caveat. */
  positionSizing?: PositionSizingMeta;
  fileSlug: string;
  save: ReportSaveMeta;

  /** Metadata table body, reused across templates. */
  metadataBody: string;

  /** Standard template: ordered, fully-formed blocks (header + caveats added by renderer). */
  standardBlocks: string[];

  /** Executive summary. */
  topMetrics: [string, string][];
  interpretation?: string;
  execContext: [string, string][];

  /** Quant tear sheet (sections omitted when not applicable). */
  tear?: {
    metricTable?: string;
    strategyVsBenchmark?: string;
    equitySummary?: string;
    drawdownSummary?: string;
    tradesOrEvents?: string;
  };

  /** Risk report (sections omitted when not applicable — never fabricated). */
  risk?: {
    metrics?: [string, string][];
    stress?: string;
    factorExposures?: string;
    correlation?: string;
    riskContribution?: string;
    diagnostics?: string;
  };
}

function renderStandard(doc: ReportDoc): string {
  return joinBlocks([
    header(doc.analysisType),
    ...doc.standardBlocks,
    riskCaveats(
      doc.caveatTickers,
      doc.dataSource,
      doc.positionMode,
      doc.positionSizing,
    ),
  ]);
}

function renderExecutive(doc: ReportDoc): string {
  const ctx = doc.execContext.map(([k, v]) => `- **${k}:** ${v}`).join("\n");
  const head =
    `# QuantLab Research Report — Executive Summary\n\n` +
    `_Generated at ${generatedAt()}_\n\n` +
    `**Analysis type:** ${doc.analysisType}\n\n` +
    ctx;
  const top = doc.topMetrics.slice(0, 5);
  return joinBlocks([
    head,
    top.length ? section("Key Metrics", mdTable(["Metric", "Value"], top)) : "",
    doc.interpretation ? section("Interpretation", doc.interpretation) : "",
    keyCaveats(
      doc.caveatTickers,
      doc.dataSource,
      doc.positionMode,
      doc.positionSizing,
    ),
  ]);
}

function renderTearSheet(doc: ReportDoc): string {
  const t = doc.tear ?? {};
  return joinBlocks([
    header(`${doc.analysisType} — Tear Sheet`),
    section("Metadata", doc.metadataBody),
    t.metricTable ? section("Performance Metrics", t.metricTable) : "",
    t.strategyVsBenchmark ? section("Strategy vs Benchmark", t.strategyVsBenchmark) : "",
    t.equitySummary ? section("Equity Curve Summary", t.equitySummary) : "",
    t.drawdownSummary ? section("Drawdown Summary", t.drawdownSummary) : "",
    t.tradesOrEvents ? section("Trades / Events Summary", t.tradesOrEvents) : "",
    annualizationNote(),
    riskCaveats(
      doc.caveatTickers,
      doc.dataSource,
      doc.positionMode,
      doc.positionSizing,
    ),
  ]);
}

function renderRiskReport(doc: ReportDoc): string {
  const r = doc.risk ?? {};
  return joinBlocks([
    header(`${doc.analysisType} — Risk Report`),
    section("Metadata", doc.metadataBody),
    r.metrics && r.metrics.length
      ? section("Risk Metrics", mdTable(["Measure", "Value"], r.metrics))
      : "",
    r.stress ? section("Stress Test Metrics", r.stress) : "",
    r.factorExposures ? section("Factor Exposures", r.factorExposures) : "",
    r.correlation ? section("Correlation Diagnostics", r.correlation) : "",
    r.riskContribution ? section("Risk Contribution", r.riskContribution) : "",
    r.diagnostics ? section("Diagnostics", r.diagnostics) : "",
    riskCaveats(
      doc.caveatTickers,
      doc.dataSource,
      doc.positionMode,
      doc.positionSizing,
    ),
  ]);
}

/** Assemble the final Markdown report for the selected template. */
function renderReport(doc: ReportDoc, template: ReportTemplate): Report {
  let content: string;
  if (template === "executive_summary") content = renderExecutive(doc);
  else if (template === "quant_tear_sheet") content = renderTearSheet(doc);
  else if (template === "risk_report") content = renderRiskReport(doc);
  else content = renderStandard(doc);

  const fileTail = TEMPLATE_FILE_SLUG[template] ? `-${TEMPLATE_FILE_SLUG[template]}` : "";
  const title =
    template === "standard"
      ? doc.save.title
      : `${doc.save.title} — ${TEMPLATE_LABELS[template]}`;

  return {
    filename: `quantlab-report-${doc.fileSlug}${fileTail}.md`,
    content,
    title,
    reportType: doc.save.reportType,
    sourceType: doc.save.sourceType,
    sourceId: doc.save.sourceId ?? null,
    tickers: doc.save.tickers,
    strategy: doc.save.strategy ?? null,
    dateRangeStart: doc.save.dateRangeStart ?? null,
    dateRangeEnd: doc.save.dateRangeEnd ?? null,
    metadata: { ...doc.save.metadata, report_template: template },
  };
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

export function buildBacktestReport(
  r: BacktestResponse,
  options: BacktestReportOptions = {},
  template: ReportTemplate = "standard",
): Report {
  const label = STRATEGY_LABELS[r.strategy] ?? r.strategy;
  const m = r.strategy_metrics;
  const params = [...backtestParams(r), ...(options.extraParameters ?? [])];
  const analysisType = options.analysisType ?? "Single-Strategy Backtest";
  const sizingMeta = positionSizingMeta(r.position_sizing);
  const caveatTickers =
    r.strategy === "pairs"
      ? [r.pairs_asset_y, r.pairs_asset_x].filter((t): t is string => Boolean(t))
      : splitTickerLabel(r.ticker);
  const equity = (r.equity_curve as EquityPoint[]).map((p) => p.strategy);

  const modeLabels: Record<string, string> = {
    long_only: "Long only",
    short_only: "Short only",
    long_short: "Long / Short",
  };
  const metaRows: [string, string][] = [
    ["Ticker", r.ticker],
    ["Strategy", label],
    ["Date range", `${r.start_date} → ${r.end_date}`],
    ["Initial capital", formatCurrency(r.initial_capital)],
    [
      "Transaction cost",
      `${r.transaction_cost_bps} bps${r.cost_model ? " per side (effective)" : ""}`,
    ],
  ];
  if (r.cost_model) {
    metaRows.push(["Cost model", r.cost_model.label]);
  }
  if (typeof r.total_transaction_cost === "number") {
    metaRows.push(["Total transaction cost", formatCurrency(r.total_transaction_cost)]);
  }
  if (typeof r.cost_drag_return === "number") {
    metaRows.push(["Cost drag (return)", formatPercent(r.cost_drag_return)]);
  }
  if (r.position_sizing) {
    metaRows.push(["Position sizing", r.position_sizing.label]);
  }
  if (typeof r.average_exposure === "number") {
    metaRows.push(["Average exposure", formatPercent(r.average_exposure)]);
  }
  if (r.position_mode) {
    metaRows.push(["Direction", modeLabels[r.position_mode] ?? r.position_mode]);
  }
  const metadataBody = mdTable(["Field", "Value"], metaRows);

  const execBullets = [
    `- **Total Return:** ${formatPercent(m.total_return)}`,
    `- **CAGR:** ${formatPercent(m.cagr)}`,
    `- **Sharpe:** ${formatRatio(m.sharpe_ratio)}`,
    `- **Sortino:** ${formatRatio(m.sortino_ratio)}`,
    `- **Max Drawdown:** ${formatPercent(m.max_drawdown)}`,
    `- **Volatility:** ${formatPercent(m.volatility)}`,
    `- **Trades:** ${r.num_trades}`,
  ].join("\n");

  const doc: ReportDoc = {
    analysisType,
    caveatTickers,
    dataSource: options.dataSource,
    positionMode: r.position_mode,
    positionSizing: sizingMeta,
    fileSlug: `${slug(r.ticker)}-${slug(r.strategy)}-${r.start_date}-${r.end_date}`,
    metadataBody,
    standardBlocks: [
      section("Metadata", metadataBody),
      section("Executive Summary", execBullets),
      section("Parameters", params.length ? mdTable(["Parameter", "Value"], params) : "_No parameters._"),
      section("Performance Metrics", metricsTable(m, r.benchmark_metrics)),
      section("Equity Curve Summary", equitySummary(equity)),
      section("Trades Summary", tradesSummary(r.trades)),
    ],
    topMetrics: [
      ["Total Return", formatPercent(m.total_return)],
      ["CAGR", formatPercent(m.cagr)],
      ["Sharpe Ratio", formatRatio(m.sharpe_ratio)],
      ["Max Drawdown", formatPercent(m.max_drawdown)],
      ["Volatility", formatPercent(m.volatility)],
    ],
    interpretation:
      `Over ${r.start_date} to ${r.end_date}, the ${label} strategy on ${r.ticker} produced a total return of ` +
      `${formatPercent(m.total_return)} (CAGR ${formatPercent(m.cagr)}) with a Sharpe ratio of ` +
      `${formatRatio(m.sharpe_ratio)} and a maximum drawdown of ${formatPercent(m.max_drawdown)}. ` +
      `Annualized volatility was ${formatPercent(m.volatility)} across ${r.num_trades} trade events.`,
    execContext: [
      ["Ticker", r.ticker],
      ["Date range", `${r.start_date} → ${r.end_date}`],
      ["Trades", String(r.num_trades)],
    ],
    tear: {
      metricTable: metricsTable(m),
      strategyVsBenchmark: metricsTable(m, r.benchmark_metrics),
      equitySummary: equitySummary(equity),
      drawdownSummary: drawdownSummary(equity),
      tradesOrEvents: tradesSummary(r.trades),
    },
    risk: {
      metrics: [
        ["Volatility (annualized)", formatPercent(m.volatility)],
        ["Max Drawdown", formatPercent(m.max_drawdown)],
        ["Worst Drawdown", formatPercent(worstDrawdownValue(equity))],
        ["Sharpe Ratio", formatRatio(m.sharpe_ratio)],
        ["Sortino Ratio", formatRatio(m.sortino_ratio)],
      ],
    },
    save: {
      title: `${r.ticker.toUpperCase()} — ${label}`,
      reportType: "markdown",
      sourceType: options.sourceType ?? "backtest",
      tickers: caveatTickers,
      strategy: r.strategy,
      dateRangeStart: r.start_date,
      dateRangeEnd: r.end_date,
      metadata: {
        analysis_type: analysisType,
        position_mode: r.position_mode ?? "long_only",
        total_return: m.total_return,
        cagr: m.cagr,
        sharpe_ratio: m.sharpe_ratio,
        sortino_ratio: m.sortino_ratio,
        max_drawdown: m.max_drawdown,
        volatility: m.volatility,
        num_trades: r.num_trades,
        position_sizing: r.position_sizing ?? null,
        average_exposure: r.average_exposure ?? null,
      },
    },
  };

  return renderReport(doc, template);
}

export function buildSavedBacktestReport(
  rec: SavedBacktestFull,
  template: ReportTemplate = "standard",
): Report {
  const m = (rec.metrics ?? {}) as Partial<PerformanceMetrics> & Record<string, unknown>;
  const num = (v: unknown) => (typeof v === "number" ? v : undefined);
  const params = Object.entries(rec.params ?? {}).map(
    ([k, v]) => [k, formatParamValue(v)] as [string, string],
  );
  const equity = (rec.equity_curve ?? []).map((p) => p.strategy);
  const trades = (rec.trades ?? []) as TradeRecord[];
  const caveatTickers = splitTickerLabel(rec.ticker);
  const label = STRATEGY_LABELS[rec.strategy] ?? rec.strategy;
  const savedPositionMode =
    typeof rec.params?.position_mode === "string"
      ? rec.params.position_mode
      : undefined;
  const savedPositionSizing = positionSizingMeta(rec.params?.position_sizing);

  const savedMetaRows: [string, string][] = [
      ["Name", rec.name],
      ["Ticker", rec.ticker],
      ["Strategy", label],
      ["Date range", `${rec.start_date} → ${rec.end_date}`],
      ["Initial capital", formatCurrency(rec.initial_capital)],
      ["Transaction cost", `${rec.transaction_cost_bps} bps`],
      ["Saved at", rec.created_at],
    ];
  const costModel = rec.params?.cost_model;
  if (costModel && typeof costModel === "object") {
    savedMetaRows.push(["Cost model", formatParamValue(costModel)]);
  }
  if (typeof rec.params?.total_transaction_cost === "number") {
    savedMetaRows.push([
      "Total transaction cost",
      formatCurrency(rec.params.total_transaction_cost),
    ]);
  }
  if (typeof rec.params?.cost_drag_return === "number") {
    savedMetaRows.push([
      "Cost drag (return)",
      formatPercent(rec.params.cost_drag_return),
    ]);
  }
  if (savedPositionSizing) {
    savedMetaRows.push([
      "Position sizing",
      savedPositionSizing.label ?? formatParamValue(rec.params.position_sizing),
    ]);
  }
  if (typeof rec.params?.average_exposure === "number") {
    savedMetaRows.push([
      "Average exposure",
      formatPercent(rec.params.average_exposure),
    ]);
  }

  const metadataBody = mdTable(["Field", "Value"], savedMetaRows);

  const execBullets = [
    `- **Total Return:** ${formatPercent(num(m.total_return))}`,
    `- **CAGR:** ${formatPercent(num(m.cagr))}`,
    `- **Sharpe:** ${formatRatio(num(m.sharpe_ratio))}`,
    `- **Sortino:** ${formatRatio(num(m.sortino_ratio))}`,
    `- **Max Drawdown:** ${formatPercent(num(m.max_drawdown))}`,
    `- **Volatility:** ${formatPercent(num(m.volatility))}`,
    `- **Trades:** ${trades.length}`,
  ].join("\n");

  const doc: ReportDoc = {
    analysisType: "Saved Backtest",
    caveatTickers,
    positionMode: savedPositionMode,
    positionSizing: savedPositionSizing,
    fileSlug: `saved-${slug(rec.name)}`,
    metadataBody,
    standardBlocks: [
      section("Metadata", metadataBody),
      section("Executive Summary", execBullets),
      ...(rec.notes ? [section("Notes", mdText(rec.notes))] : []),
      section("Parameters", params.length ? mdTable(["Parameter", "Value"], params) : "_No parameters._"),
      section("Performance Metrics", metricsTable(m)),
      section("Equity Curve Summary", equitySummary(equity)),
      section("Trades Summary", tradesSummary(trades)),
    ],
    topMetrics: [
      ["Total Return", formatPercent(num(m.total_return))],
      ["CAGR", formatPercent(num(m.cagr))],
      ["Sharpe Ratio", formatRatio(num(m.sharpe_ratio))],
      ["Max Drawdown", formatPercent(num(m.max_drawdown))],
      ["Volatility", formatPercent(num(m.volatility))],
    ],
    interpretation:
      `Saved backtest "${rec.name}" (${label} on ${rec.ticker}, ${rec.start_date} to ${rec.end_date}) ` +
      `had a total return of ${formatPercent(num(m.total_return))}, a Sharpe ratio of ` +
      `${formatRatio(num(m.sharpe_ratio))}, and a maximum drawdown of ${formatPercent(num(m.max_drawdown))}.`,
    execContext: [
      ["Ticker", rec.ticker],
      ["Date range", `${rec.start_date} → ${rec.end_date}`],
      ["Trades", String(trades.length)],
    ],
    tear: {
      metricTable: metricsTable(m),
      equitySummary: equitySummary(equity),
      drawdownSummary: drawdownSummary(equity),
      tradesOrEvents: tradesSummary(trades),
    },
    risk: {
      metrics: [
        ["Volatility (annualized)", formatPercent(num(m.volatility))],
        ["Max Drawdown", formatPercent(num(m.max_drawdown))],
        ["Worst Drawdown", formatPercent(worstDrawdownValue(equity))],
        ["Sharpe Ratio", formatRatio(num(m.sharpe_ratio))],
        ["Sortino Ratio", formatRatio(num(m.sortino_ratio))],
      ],
    },
    save: {
      title: rec.name,
      reportType: "markdown",
      sourceType: "backtest",
      sourceId: rec.id,
      tickers: caveatTickers,
      strategy: rec.strategy,
      dateRangeStart: rec.start_date,
      dateRangeEnd: rec.end_date,
      metadata: {
        total_return: num(m.total_return),
        cagr: num(m.cagr),
        sharpe_ratio: num(m.sharpe_ratio),
        max_drawdown: num(m.max_drawdown),
        position_mode: savedPositionMode ?? "long_only",
        position_sizing: rec.params?.position_sizing ?? null,
        average_exposure:
          typeof rec.params?.average_exposure === "number"
            ? rec.params.average_exposure
            : null,
        saved_backtest_id: rec.id,
      },
    },
  };

  return renderReport(doc, template);
}

export function buildPortfolioBacktestReport(
  r: PortfolioBacktestResponse,
  template: ReportTemplate = "standard",
): Report {
  const m = r.metrics;
  const turnovers = r.rebalance_events.map((e) => e.turnover);
  const avgTurnover = turnovers.length
    ? turnovers.reduce((a, b) => a + b, 0) / turnovers.length
    : 0;
  const finalWeights = r.weights.length ? r.weights[r.weights.length - 1].weights : {};
  const equity = r.equity_curve.map((p) => p.portfolio);

  const metadataBody = mdTable(
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
  );

  const execBullets = [
    `- **Total Return:** ${formatPercent(m.total_return)}`,
    `- **CAGR:** ${formatPercent(m.cagr)}`,
    `- **Sharpe:** ${formatRatio(m.sharpe_ratio)}`,
    `- **Sortino:** ${formatRatio(m.sortino_ratio)}`,
    `- **Max Drawdown:** ${formatPercent(m.max_drawdown)}`,
    `- **Volatility:** ${formatPercent(m.volatility)}`,
  ].join("\n");

  const eventsBody = [
    `- **Rebalance events:** ${r.rebalance_events.length}`,
    `- **Average turnover:** ${formatPercent(avgTurnover, 1)}`,
  ].join("\n");

  const doc: ReportDoc = {
    analysisType: "Equal-Weight Portfolio Backtest",
    caveatTickers: [...r.tickers, r.benchmark_ticker],
    fileSlug: `portfolio-backtest-${timestamp()}`,
    metadataBody,
    standardBlocks: [
      section("Metadata", metadataBody),
      section("Executive Summary", execBullets),
      section(
        "Final Weights",
        Object.keys(finalWeights).length ? weightsTable(finalWeights) : "_No weights._",
      ),
      section("Performance Metrics", metricsTable(m, r.benchmark_metrics)),
      section("Equity Curve Summary", equitySummary(equity)),
      section("Rebalance Events Summary", eventsBody),
    ],
    topMetrics: [
      ["Total Return", formatPercent(m.total_return)],
      ["CAGR", formatPercent(m.cagr)],
      ["Sharpe Ratio", formatRatio(m.sharpe_ratio)],
      ["Max Drawdown", formatPercent(m.max_drawdown)],
      ["Volatility", formatPercent(m.volatility)],
    ],
    interpretation:
      `The equal-weight portfolio of ${r.tickers.join(", ")} (${r.rebalance_frequency} rebalancing, ${r.start_date} to ${r.end_date}) ` +
      `returned ${formatPercent(m.total_return)} (CAGR ${formatPercent(m.cagr)}) with a Sharpe of ${formatRatio(m.sharpe_ratio)} ` +
      `and a maximum drawdown of ${formatPercent(m.max_drawdown)} versus the ${r.benchmark_ticker} benchmark.`,
    execContext: [
      ["Tickers", r.tickers.join(", ")],
      ["Benchmark", r.benchmark_ticker],
      ["Date range", `${r.start_date} → ${r.end_date}`],
    ],
    tear: {
      metricTable: metricsTable(m),
      strategyVsBenchmark: metricsTable(m, r.benchmark_metrics),
      equitySummary: equitySummary(equity),
      drawdownSummary: drawdownSummary(equity),
      tradesOrEvents: eventsBody,
    },
    risk: {
      metrics: [
        ["Volatility (annualized)", formatPercent(m.volatility)],
        ["Max Drawdown", formatPercent(m.max_drawdown)],
        ["Worst Drawdown", formatPercent(worstDrawdownValue(equity))],
        ["Sharpe Ratio", formatRatio(m.sharpe_ratio)],
        ["Sortino Ratio", formatRatio(m.sortino_ratio)],
      ],
    },
    save: {
      title: `Equal-Weight Portfolio — ${r.tickers.join(", ")}`,
      reportType: "markdown",
      sourceType: "portfolio_backtest",
      tickers: r.tickers,
      strategy: "equal_weight",
      dateRangeStart: r.start_date,
      dateRangeEnd: r.end_date,
      metadata: {
        rebalance_frequency: r.rebalance_frequency,
        total_return: m.total_return,
        cagr: m.cagr,
        sharpe_ratio: m.sharpe_ratio,
        max_drawdown: m.max_drawdown,
        volatility: m.volatility,
        rebalance_events: r.rebalance_events.length,
        average_turnover: avgTurnover,
      },
    },
  };

  return renderReport(doc, template);
}

export function buildPortfolioOptimizeReport(
  r: PortfolioOptimizeResponse,
  template: ReportTemplate = "standard",
): Report {
  const m = r.metrics;
  const equity = r.equity_curve.map((p) => p.value);
  const inSample =
    r.in_sample_warning ||
    "In-sample optimization: weights were fit and backtested on the same window and can overfit.";

  const metadataBody = mdTable(
    ["Field", "Value"],
    [
      ["Tickers", r.tickers.join(", ")],
      ["Objective", r.objective],
      ["Date range", `${r.start_date} → ${r.end_date}`],
      ["Initial capital", formatCurrency(r.initial_capital)],
      ["Risk-free rate", formatPercent(r.risk_free_rate)],
      ["Transaction cost", `${r.transaction_cost_bps} bps`],
    ],
  );

  const execBullets = [
    `- **Expected Return (annual):** ${formatPercent(r.portfolio_expected_return)}`,
    `- **Volatility (annual):** ${formatPercent(r.portfolio_volatility)}`,
    `- **Sharpe:** ${formatRatio(r.portfolio_sharpe)}`,
    `- **Backtest Total Return:** ${formatPercent(m.total_return)}`,
    `- **Backtest Max Drawdown:** ${formatPercent(m.max_drawdown)}`,
  ].join("\n");

  const doc: ReportDoc = {
    analysisType: "Portfolio Optimization (in-sample)",
    caveatTickers: r.tickers,
    fileSlug: `optimization-${slug(r.objective)}-${timestamp()}`,
    metadataBody,
    standardBlocks: [
      section("Metadata", metadataBody),
      section("Executive Summary", execBullets),
      section("Optimized Weights", weightsTable(r.weights)),
      section("Performance Metrics (optimized vs equal weight)", metricsTable(m, r.equal_weight_metrics)),
      section("Equity Curve Summary", equitySummary(equity)),
      `> ${mdText(inSample)}`,
    ],
    topMetrics: [
      ["Expected Return (annual)", formatPercent(r.portfolio_expected_return)],
      ["Volatility (annual)", formatPercent(r.portfolio_volatility)],
      ["Sharpe Ratio", formatRatio(r.portfolio_sharpe)],
      ["Backtest Total Return", formatPercent(m.total_return)],
      ["Backtest Max Drawdown", formatPercent(m.max_drawdown)],
    ],
    interpretation:
      `Optimizing ${r.tickers.join(", ")} for "${r.objective}" over ${r.start_date} to ${r.end_date} yielded an expected annual ` +
      `return of ${formatPercent(r.portfolio_expected_return)} at ${formatPercent(r.portfolio_volatility)} volatility ` +
      `(Sharpe ${formatRatio(r.portfolio_sharpe)}). These weights are fit and backtested in-sample and can overfit.`,
    execContext: [
      ["Tickers", r.tickers.join(", ")],
      ["Objective", r.objective],
      ["Date range", `${r.start_date} → ${r.end_date}`],
    ],
    tear: {
      metricTable: metricsTable(m),
      strategyVsBenchmark: metricsTable(m, r.equal_weight_metrics),
      equitySummary: equitySummary(equity),
      drawdownSummary: drawdownSummary(equity),
    },
    risk: {
      metrics: [
        ["Volatility (annual)", formatPercent(r.portfolio_volatility)],
        ["Max Drawdown", formatPercent(m.max_drawdown)],
        ["Worst Drawdown", formatPercent(worstDrawdownValue(equity))],
        ["Sharpe Ratio", formatRatio(r.portfolio_sharpe)],
      ],
      diagnostics: `- ${mdText(inSample)}`,
    },
    save: {
      title: `Portfolio Optimization — ${r.objective}`,
      reportType: "markdown",
      sourceType: "portfolio_optimization",
      tickers: r.tickers,
      strategy: r.objective,
      dateRangeStart: r.start_date,
      dateRangeEnd: r.end_date,
      metadata: {
        objective: r.objective,
        expected_return: r.portfolio_expected_return,
        volatility: r.portfolio_volatility,
        sharpe: r.portfolio_sharpe,
        total_return: m.total_return,
        max_drawdown: m.max_drawdown,
      },
    },
  };

  return renderReport(doc, template);
}

export function buildRiskDashboardReport(
  r: RiskDashboardResponse,
  template: ReportTemplate = "standard",
): Report {
  const ew = r.equal_weight_portfolio;
  const diag = r.correlation_diagnostics;
  const assetRows = r.tickers.map((t) => [
    t,
    formatPercent(r.asset_annual_returns[t], 1),
    formatPercent(r.asset_annual_volatilities[t], 1),
    formatPercent(r.risk_contribution[t], 1),
  ]);
  const assetRiskTable = mdTable(
    ["Ticker", "Annual Return", "Annual Volatility", "Risk Contribution"],
    assetRows,
  );
  const corr = corrMatrixTable(r.tickers, r.correlation_matrix);

  const metadataBody = mdTable(
    ["Field", "Value"],
    [
      ["Tickers", r.tickers.join(", ")],
      ["Date range", `${r.start_date} → ${r.end_date}`],
    ],
  );

  const execBullets = [
    `- **Equal-Weight Return (annual):** ${formatPercent(ew.expected_return)}`,
    `- **Equal-Weight Volatility (annual):** ${formatPercent(ew.volatility)}`,
    `- **Diversification Ratio:** ${formatRatio(ew.diversification_ratio)}`,
    `- **Average Pairwise Correlation:** ${formatRatio(diag.average_pairwise_correlation)}`,
    `- **Most Correlated:** ${diag.most_correlated_pair?.join(" / ") ?? "—"} (${formatRatio(diag.max_pairwise_correlation)})`,
    `- **Least Correlated:** ${diag.least_correlated_pair?.join(" / ") ?? "—"} (${formatRatio(diag.min_pairwise_correlation)})`,
  ].join("\n");

  const diagnosticsBody = [
    `- **Average pairwise correlation:** ${formatRatio(diag.average_pairwise_correlation)}`,
    `- **Most correlated:** ${diag.most_correlated_pair?.join(" / ") ?? "—"} (${formatRatio(diag.max_pairwise_correlation)})`,
    `- **Least correlated:** ${diag.least_correlated_pair?.join(" / ") ?? "—"} (${formatRatio(diag.min_pairwise_correlation)})`,
  ].join("\n");

  const doc: ReportDoc = {
    analysisType: "Portfolio Risk Dashboard",
    caveatTickers: r.tickers,
    fileSlug: `risk-dashboard-${timestamp()}`,
    metadataBody,
    standardBlocks: [
      section("Metadata", metadataBody),
      section("Executive Summary", execBullets),
      section("Equal-Weight Portfolio", weightsTable(ew.weights)),
      section("Asset Risk Summary", assetRiskTable),
      section("Correlation Matrix", corr),
      ...(r.historical_note ? [section("Method Note", mdText(r.historical_note))] : []),
    ],
    topMetrics: [
      ["Equal-Weight Return (annual)", formatPercent(ew.expected_return)],
      ["Equal-Weight Volatility (annual)", formatPercent(ew.volatility)],
      ["Diversification Ratio", formatRatio(ew.diversification_ratio)],
      ["Avg Pairwise Correlation", formatRatio(diag.average_pairwise_correlation)],
      ["Assets", String(r.tickers.length)],
    ],
    interpretation:
      `The equal-weight portfolio of ${r.tickers.join(", ")} has an annual volatility of ${formatPercent(ew.volatility)} ` +
      `and a diversification ratio of ${formatRatio(ew.diversification_ratio)}; the average pairwise correlation is ` +
      `${formatRatio(diag.average_pairwise_correlation)} (most correlated: ${diag.most_correlated_pair?.join(" / ") ?? "—"}).`,
    execContext: [
      ["Tickers", r.tickers.join(", ")],
      ["Date range", `${r.start_date} → ${r.end_date}`],
    ],
    risk: {
      metrics: [
        ["Equal-Weight Volatility (annual)", formatPercent(ew.volatility)],
        ["Equal-Weight Return (annual)", formatPercent(ew.expected_return)],
        ["Diversification Ratio", formatRatio(ew.diversification_ratio)],
        ["Average Pairwise Correlation", formatRatio(diag.average_pairwise_correlation)],
      ],
      correlation: corr,
      riskContribution: assetRiskTable,
      diagnostics: diagnosticsBody,
    },
    save: {
      title: `Risk Dashboard — ${r.tickers.join(", ")}`,
      reportType: "markdown",
      sourceType: "risk_dashboard",
      tickers: r.tickers,
      strategy: null,
      dateRangeStart: r.start_date,
      dateRangeEnd: r.end_date,
      metadata: {
        expected_return: ew.expected_return,
        volatility: ew.volatility,
        diversification_ratio: ew.diversification_ratio,
        average_pairwise_correlation: diag.average_pairwise_correlation,
      },
    },
  };

  return renderReport(doc, template);
}

export function buildStressTestReport(
  r: StressTestResponse,
  template: ReportTemplate = "standard",
): Report {
  const m = r.full_period_metrics;
  const equity = r.full_equity_curve.map((p) => p.value);
  const scnRows = r.scenarios.map((s) => [
    s.name,
    formatPercent(s.total_return, 1),
    formatPercent(s.benchmark_total_return, 1),
    formatPercent(s.excess_return, 1),
    formatPercent(s.max_drawdown, 1),
    formatPercent(s.worst_day_return, 1),
    formatPercent(s.annualized_volatility, 0),
  ]);
  const scenarioTable = mdTable(
    ["Scenario", "Portfolio", "Benchmark", "Excess", "Max DD", "Worst Day", "Volatility"],
    scnRows,
  );

  const metadataBody = mdTable(
    ["Field", "Value"],
    [
      ["Tickers", r.tickers.join(", ")],
      ["Benchmark", r.benchmark_ticker],
      ["Date range", `${r.start_date} → ${r.end_date}`],
    ],
  );

  const doc: ReportDoc = {
    analysisType: "Portfolio Stress Test",
    caveatTickers: [...r.tickers, r.benchmark_ticker],
    fileSlug: `stress-test-${timestamp()}`,
    metadataBody,
    standardBlocks: [
      section("Metadata", metadataBody),
      section("Weights", weightsTable(r.weights)),
      section("Full-Period Performance (portfolio vs benchmark)", metricsTable(m, r.benchmark_full_period_metrics)),
      section("Scenario Comparison", scenarioTable),
      ...(r.historical_note ? [section("Method Note", mdText(r.historical_note))] : []),
    ],
    topMetrics: [
      ["Full-Period Total Return", formatPercent(m.total_return)],
      ["Max Drawdown", formatPercent(m.max_drawdown)],
      ["Volatility", formatPercent(m.volatility)],
      ["Sharpe Ratio", formatRatio(m.sharpe_ratio)],
      ["Scenarios", String(r.scenarios.length)],
    ],
    interpretation:
      `Across the full period (${r.start_date} to ${r.end_date}), the portfolio of ${r.tickers.join(", ")} returned ` +
      `${formatPercent(m.total_return)} with a maximum drawdown of ${formatPercent(m.max_drawdown)}; ` +
      `${r.scenarios.length} stress scenario(s) were evaluated against the ${r.benchmark_ticker} benchmark.`,
    execContext: [
      ["Tickers", r.tickers.join(", ")],
      ["Benchmark", r.benchmark_ticker],
      ["Date range", `${r.start_date} → ${r.end_date}`],
    ],
    tear: {
      metricTable: metricsTable(m),
      strategyVsBenchmark: metricsTable(m, r.benchmark_full_period_metrics),
      equitySummary: equitySummary(equity),
      drawdownSummary: drawdownSummary(equity),
      tradesOrEvents: scenarioTable,
    },
    risk: {
      metrics: [
        ["Volatility (annualized)", formatPercent(m.volatility)],
        ["Max Drawdown", formatPercent(m.max_drawdown)],
        ["Worst Drawdown", formatPercent(worstDrawdownValue(equity))],
        ["Sharpe Ratio", formatRatio(m.sharpe_ratio)],
      ],
      stress: scenarioTable,
    },
    save: {
      title: `Stress Test — ${r.tickers.join(", ")}`,
      reportType: "markdown",
      sourceType: "stress_test",
      tickers: r.tickers,
      strategy: null,
      dateRangeStart: r.start_date,
      dateRangeEnd: r.end_date,
      metadata: {
        benchmark_ticker: r.benchmark_ticker,
        scenarios: r.scenarios.length,
        full_period_total_return: m.total_return,
        full_period_max_drawdown: m.max_drawdown,
      },
    },
  };

  return renderReport(doc, template);
}

export function buildFactorAnalysisReport(
  r: FactorAnalysisResponse,
  template: ReportTemplate = "standard",
): Report {
  const factorNames = Object.keys(r.factor_tickers);
  const betaRows = factorNames.map((name) => [
    name,
    r.factor_tickers[name],
    formatRatio(r.betas[name]),
  ]);
  const betaTable = mdTable(["Factor", "ETF", "Beta"], betaRows);
  const factorCorr = corrMatrixTable(factorNames, r.factor_correlation_matrix);

  const diagnosticsBody = [
    `- **Largest Exposure:** ${r.diagnostics.absolute_largest_exposure ?? "—"}`,
    `- **Strongest +:** ${r.diagnostics.strongest_positive_factor ?? "—"}`,
    `- **Strongest −:** ${r.diagnostics.strongest_negative_factor ?? "—"}`,
    `- **Multicollinearity warning:** ${r.diagnostics.multicollinearity_warning ? "yes" : "no"}`,
  ].join("\n");

  const metadataBody = mdTable(
    ["Field", "Value"],
    [
      ["Tickers", r.tickers.join(", ")],
      ["Date range", `${r.start_date} → ${r.end_date}`],
      ["Factors", factorNames.map((n) => `${n} (${r.factor_tickers[n]})`).join(", ")],
    ],
  );

  const execBullets = [
    `- **R²:** ${formatRatio(r.r_squared, 3)}`,
    `- **Annualized Alpha:** ${formatPercent(r.alpha_annualized)}`,
    `- **Residual Volatility:** ${formatPercent(r.residual_volatility)}`,
    `- **Largest Exposure:** ${r.diagnostics.absolute_largest_exposure ?? "—"}`,
    `- **Strongest +:** ${r.diagnostics.strongest_positive_factor ?? "—"} · **Strongest −:** ${r.diagnostics.strongest_negative_factor ?? "—"}`,
    ...(r.diagnostics.multicollinearity_warning
      ? ["\n> ⚠️ Multicollinearity detected — individual betas may be unstable."]
      : []),
  ].join("\n");

  const doc: ReportDoc = {
    analysisType: "Factor Exposure / Regression Analysis",
    caveatTickers: [...r.tickers, ...Object.values(r.factor_tickers)],
    fileSlug: `factor-analysis-${timestamp()}`,
    metadataBody,
    standardBlocks: [
      section("Metadata", metadataBody),
      section("Executive Summary", execBullets),
      section("Portfolio Weights", weightsTable(r.weights)),
      section("Factor Betas", betaTable),
      ...(r.historical_note ? [section("Method Note", mdText(r.historical_note))] : []),
    ],
    topMetrics: [
      ["R²", formatRatio(r.r_squared, 3)],
      ["Annualized Alpha", formatPercent(r.alpha_annualized)],
      ["Residual Volatility", formatPercent(r.residual_volatility)],
      ["Largest Exposure", r.diagnostics.absolute_largest_exposure ?? "—"],
      ["Strongest +", r.diagnostics.strongest_positive_factor ?? "—"],
    ],
    interpretation:
      `The portfolio of ${r.tickers.join(", ")} regressed on ${factorNames.length} factor(s) has an R² of ` +
      `${formatRatio(r.r_squared, 3)} and annualized alpha of ${formatPercent(r.alpha_annualized)}. ` +
      `Its largest exposure is ${r.diagnostics.absolute_largest_exposure ?? "—"}` +
      `${r.diagnostics.multicollinearity_warning ? "; multicollinearity was detected, so individual betas may be unstable." : "."}`,
    execContext: [
      ["Tickers", r.tickers.join(", ")],
      ["Date range", `${r.start_date} → ${r.end_date}`],
      ["Factors", factorNames.join(", ")],
    ],
    risk: {
      metrics: [
        ["R²", formatRatio(r.r_squared, 3)],
        ["Annualized Alpha", formatPercent(r.alpha_annualized)],
        ["Residual Volatility", formatPercent(r.residual_volatility)],
      ],
      factorExposures: betaTable,
      correlation: factorCorr,
      diagnostics: diagnosticsBody,
    },
    save: {
      title: `Factor Analysis — ${r.tickers.join(", ")}`,
      reportType: "markdown",
      sourceType: "factor_analysis",
      tickers: r.tickers,
      strategy: null,
      dateRangeStart: r.start_date,
      dateRangeEnd: r.end_date,
      metadata: {
        r_squared: r.r_squared,
        alpha_annualized: r.alpha_annualized,
        residual_volatility: r.residual_volatility,
        multicollinearity_warning: r.diagnostics.multicollinearity_warning,
      },
    },
  };

  return renderReport(doc, template);
}
