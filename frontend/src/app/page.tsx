"use client";

import { useEffect, useState } from "react";
import AppShell, { type View } from "@/components/AppShell";
import BacktestForm from "@/components/BacktestForm";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";
import SmaSweepPanel from "@/components/SmaSweepPanel";
import SmaTrainTestPanel from "@/components/SmaTrainTestPanel";
import SmaWalkForwardPanel from "@/components/SmaWalkForwardPanel";
import StrategyComparisonPanel from "@/components/StrategyComparisonPanel";
import CsvBacktestPanel from "@/components/CsvBacktestPanel";
import StrategyBuilderPanel from "@/components/StrategyBuilderPanel";
import PortfolioWorkspace, {
  type PortfolioTab,
} from "@/components/PortfolioWorkspace";
import SaveBacktestModal from "@/components/SaveBacktestModal";
import SignalDiagnostics from "@/components/SignalDiagnostics";
import ShortModeDiagnostics from "@/components/ShortModeDiagnostics";
import ShortSellingWarning from "@/components/ShortSellingWarning";
import ExportReportButton from "@/components/ExportReportButton";
import { buildBacktestReport, downloadTextFile } from "@/lib/reportExport";
import SavedBacktestsList from "@/components/SavedBacktestsList";
import SavedBacktestDetail from "@/components/SavedBacktestDetail";
import SavedReportsList from "@/components/SavedReportsList";
import SavedReportDetail from "@/components/SavedReportDetail";
import HomeDashboard from "@/components/HomeDashboard";
import SettingsPanel from "@/components/SettingsPanel";
import CommandPalette, { type Command } from "@/components/CommandPalette";
import { DEMO_PRESETS, type DemoPresetId } from "@/lib/demoPresets";
import { markChecklistStep } from "@/lib/onboarding";
import { applyAccent, loadSettings, resolveDateRange } from "@/lib/settings";
import {
  runBacktest,
  runBbBacktest,
  runMomentumBacktest,
  runPairsBacktest,
  runRsiBacktest,
  runVbBacktest,
} from "@/lib/api";
import type {
  BacktestRequest,
  BacktestResponse,
  BbBacktestRequest,
  MomentumBacktestRequest,
  PairsBacktestRequest,
  RsiBacktestRequest,
  StrategyType,
  VbBacktestRequest,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Default parameters
// ---------------------------------------------------------------------------

// Defaults are demo-friendly starting points, not performance-optimized.
// Classic/long-term variants are available as one-click presets in the form.

const DEFAULT_SMA_PARAMS: BacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  fast_window: 20,
  slow_window: 100,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  position_mode: "long_only",
};

const DEFAULT_RSI_PARAMS: RsiBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  rsi_window: 14,
  oversold_threshold: 35,
  exit_threshold: 55,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

const DEFAULT_BB_PARAMS: BbBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  bb_window: 20,
  num_std: 1.8,
  exit_band: "middle",
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

const DEFAULT_MOMENTUM_PARAMS: MomentumBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  momentum_window: 63,
  entry_threshold: 0.0,
  exit_threshold: 0.0,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  position_mode: "long_only",
};

const DEFAULT_VB_PARAMS: VbBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  lookback_window: 20,
  breakout_multiplier: 0.3,
  exit_window: 10,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  position_mode: "long_only",
};

const DEFAULT_PAIRS_PARAMS: PairsBacktestRequest = {
  asset_y: "KO",
  asset_x: "PEP",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  lookback_window: 60,
  entry_z_score: 1.5,
  exit_z_score: 0.5,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

// Guided "Demo Crypto Momentum" preset — the long-only momentum defaults on a
// crypto ticker. Real backend run; only the inputs are prefilled.
const DEMO_CRYPTO_MOMENTUM_PARAMS: MomentumBacktestRequest = {
  ...DEFAULT_MOMENTUM_PARAMS,
  ticker: "BTC-USD",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a human-readable strategy label from the backtest response. */
function strategyLabel(r: BacktestResponse): string {
  if (r.strategy === "sma_crossover") {
    return `SMA ${r.fast_window}/${r.slow_window}`;
  }
  if (r.strategy === "rsi_mean_reversion") {
    return `RSI(${r.rsi_window ?? 14}) ${r.oversold_threshold}→${r.exit_threshold}`;
  }
  if (r.strategy === "bollinger_band") {
    const exit = r.bb_exit_band === "upper" ? "Upper" : "Mid";
    return `BB(${r.bb_window ?? 20}, ${r.bb_num_std ?? 1.8}σ) exit:${exit}`;
  }
  if (r.strategy === "momentum") {
    const entry = r.momentum_entry_threshold ?? 0;
    const exit = r.momentum_exit_threshold ?? 0;
    return `Momentum(${r.momentum_window ?? 63}) entry:${entry} exit:${exit}`;
  }
  if (r.strategy === "volatility_breakout") {
    return (
      `VolBreakout(${r.vb_lookback_window ?? 20}, ` +
      `${r.vb_breakout_multiplier ?? 0.3}x range, exit:${r.vb_exit_window ?? 10})`
    );
  }
  if (r.strategy === "pairs") {
    return (
      `Pairs ${r.pairs_asset_y ?? ""}/${r.pairs_asset_x ?? ""} ` +
      `Z(${r.pairs_lookback_window ?? 60}) ` +
      `entry:${r.pairs_entry_z_score ?? 1.5} exit:${r.pairs_exit_z_score ?? 0.5}`
    );
  }
  return r.strategy;
}

/** Build a compact param summary shown beside the ticker in the results header. */
function paramSummary(r: BacktestResponse): string {
  const cost = `${r.transaction_cost_bps} bps`;
  const trades = `${r.num_trades} trade events`;
  const modeLabel =
    r.position_mode === "short_only"
      ? "Short-only · "
      : r.position_mode === "long_short"
        ? "Long/Short · "
        : "";
  if (r.strategy === "sma_crossover") {
    return `${modeLabel}SMA ${r.fast_window}/${r.slow_window} · ${cost} · ${trades}`;
  }
  if (r.strategy === "rsi_mean_reversion") {
    return (
      `RSI(${r.rsi_window ?? 14}) OB=${r.oversold_threshold} ` +
      `Exit=${r.exit_threshold} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "bollinger_band") {
    return (
      `BB(${r.bb_window ?? 20}, ${r.bb_num_std ?? 1.8}σ) ` +
      `exit:${r.bb_exit_band ?? "middle"} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "momentum") {
    return (
      `${modeLabel}Momentum(${r.momentum_window ?? 63}) ` +
      `entry:${r.momentum_entry_threshold ?? 0} ` +
      `exit:${r.momentum_exit_threshold ?? 0} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "volatility_breakout") {
    return (
      `${modeLabel}VolBreakout lookback:${r.vb_lookback_window ?? 20} ` +
      `mult:${r.vb_breakout_multiplier ?? 0.3}x range ` +
      `exit mean:${r.vb_exit_window ?? 10} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "pairs") {
    return (
      `Spread ${r.pairs_asset_y ?? ""}/${r.pairs_asset_x ?? ""} ` +
      `lookback:${r.pairs_lookback_window ?? 60} ` +
      `entry:|z|>${r.pairs_entry_z_score ?? 1.5} ` +
      `exit z→±${r.pairs_exit_z_score ?? 0.5} · ${cost} · ${trades}`
    );
  }
  return `${cost} · ${trades}`;
}

const STRATEGY_HEADINGS: Record<
  StrategyType,
  { title: string; description: string }
> = {
  sma_crossover: {
    title: "SMA Crossover Backtest",
    description:
      "Long-only strategy that buys when the fast SMA crosses above the slow " +
      "SMA and exits when it crosses below. Signal is shifted one day forward " +
      "to prevent lookahead bias.",
  },
  rsi_mean_reversion: {
    title: "RSI Mean Reversion Backtest",
    description:
      "Long-only mean-reversion strategy that enters when RSI dips below the " +
      "oversold threshold and exits when RSI recovers above the exit threshold. " +
      "Signal is shifted one day forward to prevent lookahead bias.",
  },
  bollinger_band: {
    title: "Bollinger Band Mean Reversion Backtest",
    description:
      "Long-only mean-reversion strategy that enters when price falls below the " +
      "lower Bollinger Band and exits when price " +
      "recovers to the selected exit band. Signal is shifted one day forward to " +
      "prevent lookahead bias.",
  },
  momentum: {
    title: "Time-Series Momentum Backtest",
    description:
      "Long-only trend-following strategy. Enters when the trailing N-day return " +
      "exceeds the entry threshold and exits when it falls to or below the exit " +
      "threshold. An entry > exit gap creates a hysteresis band that reduces " +
      "turnover in choppy markets. Signal is shifted one day forward to prevent " +
      "lookahead bias.",
  },
  volatility_breakout: {
    title: "Volatility Breakout Backtest",
    description:
      "Long-only trend-following strategy. Enters when price breaks above the " +
      "prior rolling high plus a multiple of the prior high-low range. Exits " +
      "when price falls below the rolling mean exit level. Signal is shifted " +
      "one day forward to prevent lookahead bias.",
  },
  pairs: {
    title: "Pairs Trading Backtest",
    description:
      "Dollar-neutral statistical arbitrage on two correlated assets. Spread = " +
      "log(Y) − log(X). Enters long-spread (long Y / short X) when z-score " +
      "falls below −entry_z, short-spread (short Y / long X) when it rises " +
      "above +entry_z. Long-spread exits when z-score crosses above −exit_z; " +
      "short-spread exits when it crosses below +exit_z. Each leg gets 50 % of " +
      "capital. Benchmark is an equal-weight pair benchmark. Signal shifted one day " +
      "forward to prevent lookahead bias.",
  },
};

/** TopBar title + subtitle per workspace. */
const VIEW_META: Record<View, { title: string; subtitle: string }> = {
  home: {
    title: "Home",
    subtitle:
      "Research, backtest, optimize, and report trading strategies from one local dashboard.",
  },
  backtest: {
    title: "Backtest",
    subtitle: "Run a single strategy on real historical market data.",
  },
  csv: {
    title: "CSV Backtest",
    subtitle: "Upload your own price history and run a single-asset strategy.",
  },
  builder: {
    title: "Strategy Builder",
    subtitle: "Compose a long-only strategy from indicator rules — no code.",
  },
  portfolio: {
    title: "Portfolio Backtest",
    subtitle: "Equal-weight multi-asset portfolio with optional rebalancing.",
  },
  sweep: {
    title: "Parameter Sweep",
    subtitle: "Grid-search SMA fast/slow window combinations.",
  },
  "train-test": {
    title: "Train/Test Validation",
    subtitle: "In-sample parameter selection, out-of-sample evaluation.",
  },
  "walk-forward": {
    title: "Walk-Forward Optimization",
    subtitle: "Rolling re-optimisation with stitched out-of-sample equity.",
  },
  comparison: {
    title: "Strategy Comparison",
    subtitle: "Five single-asset strategies, one ticker, side by side.",
  },
  saved: {
    title: "Saved Backtests",
    subtitle: "Locally persisted results, stored in SQLite.",
  },
  reports: {
    title: "Saved Reports",
    subtitle: "Research reports saved locally in SQLite — view, download, print.",
  },
  settings: {
    title: "Settings",
    subtitle: "Local preferences for defaults, conventions, theme, and reports.",
  },
};

// ---------------------------------------------------------------------------
// Section heading inside content
// ---------------------------------------------------------------------------

function SectionIntro({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h2 className="text-xl font-semibold text-slate-800">{title}</h2>
      <p className="mt-1 text-sm text-slate-500 max-w-2xl">{children}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const [view, setView] = useState<View>("home");

  // Guided-demo banner ("Demo parameters loaded. Click Run to execute.") and
  // the portfolio sub-tab a demo should open on.  `portfolioKey` is bumped to
  // remount PortfolioWorkspace so a demo lands on the right tab even if the
  // user is already in the Portfolio Lab.
  const [demoNotice, setDemoNotice] = useState<string | null>(null);
  const [portfolioTab, setPortfolioTab] = useState<PortfolioTab>("backtest");
  const [portfolioKey, setPortfolioKey] = useState(0);
  const [builderDemoTemplateId, setBuilderDemoTemplateId] = useState<string | null>(
    null,
  );
  const [builderSavedTemplateId, setBuilderSavedTemplateId] = useState<
    number | null
  >(null);
  const [builderKey, setBuilderKey] = useState(0);

  // Saved backtests state
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [savedRefreshKey, setSavedRefreshKey] = useState(0);
  const [savedDetailId, setSavedDetailId] = useState<number | null>(null);

  // Saved reports (Report Gallery) state
  const [savedReportsRefreshKey, setSavedReportsRefreshKey] = useState(0);
  const [savedReportDetailId, setSavedReportDetailId] = useState<number | null>(
    null,
  );

  // Backtest state
  const [strategy, setStrategy] = useState<StrategyType>("sma_crossover");
  const [smaParams, setSmaParams] = useState<BacktestRequest>(DEFAULT_SMA_PARAMS);
  const [rsiParams, setRsiParams] = useState<RsiBacktestRequest>(DEFAULT_RSI_PARAMS);
  const [bbParams, setBbParams] = useState<BbBacktestRequest>(DEFAULT_BB_PARAMS);
  const [momentumParams, setMomentumParams] = useState<MomentumBacktestRequest>(
    DEFAULT_MOMENTUM_PARAMS,
  );
  const [vbParams, setVbParams] = useState<VbBacktestRequest>(DEFAULT_VB_PARAMS);
  const [pairsParams, setPairsParams] = useState<PairsBacktestRequest>(
    DEFAULT_PAIRS_PARAMS,
  );
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Bumping this key remounts BacktestForm so its internal numeric string
  // states re-derive from the (settings-prefilled) param props.
  const [formKey, setFormKey] = useState(0);

  // Apply local settings once on startup: set the theme accent and prefill the
  // single-backtest forms' common fields (capital, cost, date range).  Runs in
  // an effect (client-only, post-hydration) so it never causes an SSR mismatch,
  // and only on mount so it never overrides edits the user makes afterwards.
  useEffect(() => {
    const s = loadSettings();
    applyAccent(s.accent_color);
    const { start_date, end_date } = resolveDateRange(s);
    const common = {
      initial_capital: s.default_initial_capital,
      transaction_cost_bps: s.default_transaction_cost_bps,
      start_date,
      end_date,
    };
    setSmaParams((p) => ({ ...p, ...common }));
    setRsiParams((p) => ({ ...p, ...common }));
    setBbParams((p) => ({ ...p, ...common }));
    setMomentumParams((p) => ({ ...p, ...common }));
    setVbParams((p) => ({ ...p, ...common }));
    setPairsParams((p) => ({ ...p, ...common }));
    setFormKey((k) => k + 1);
  }, []);

  async function handleRun() {
    if (loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setShowSaveForm(false);

    try {
      const data =
        strategy === "sma_crossover"
          ? await runBacktest(smaParams)
          : strategy === "rsi_mean_reversion"
            ? await runRsiBacktest(rsiParams)
            : strategy === "bollinger_band"
              ? await runBbBacktest(bbParams)
              : strategy === "momentum"
                ? await runMomentumBacktest(momentumParams)
                : strategy === "volatility_breakout"
                  ? await runVbBacktest(vbParams)
                  : await runPairsBacktest(pairsParams);
      setResult(data);
      setDemoNotice(null); // a real run replaces the "click Run" hint
      markChecklistStep("ran_backtest");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred.",
      );
    } finally {
      setLoading(false);
    }
  }

  function handleNav(next: View) {
    setView(next);
    setDemoNotice(null);
    setBuilderDemoTemplateId(null);
    if (next !== "saved") setSavedDetailId(null);
    if (next !== "reports") setSavedReportDetailId(null);
  }

  /**
   * Load a guided-demo preset: navigate to the right workspace and prefill the
   * form.  Never auto-runs — the real backend call only happens when the user
   * clicks Run.  No results are fabricated.
   */
  function handleDemo(id: DemoPresetId) {
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    switch (id) {
      case "sma_backtest":
        setStrategy("sma_crossover");
        setSmaParams(DEFAULT_SMA_PARAMS);
        setResult(null);
        setError(null);
        setFormKey((k) => k + 1);
        setDemoNotice(
          "Demo parameters loaded (SPY · SMA Crossover 20/100 · 2015–2023). Click Run to execute.",
        );
        setView("backtest");
        break;
      case "crypto_momentum":
        setStrategy("momentum");
        setMomentumParams(DEMO_CRYPTO_MOMENTUM_PARAMS);
        setResult(null);
        setError(null);
        setFormKey((k) => k + 1);
        setDemoNotice(
          "Demo parameters loaded (BTC-USD · Time-Series Momentum · 2015–2023). Click Run to execute.",
        );
        setView("backtest");
        break;
      case "portfolio_risk":
        setPortfolioTab("risk");
        setPortfolioKey((k) => k + 1);
        setDemoNotice(
          "Demo loaded: SPY, QQQ, GLD, TLT in the Risk Dashboard. Click Run to execute.",
        );
        setView("portfolio");
        break;
      case "efficient_frontier":
        setPortfolioTab("frontier");
        setPortfolioKey((k) => k + 1);
        setDemoNotice(
          "Demo loaded: efficient frontier for SPY, QQQ, GLD, TLT (2,000 portfolios). Click Run to execute.",
        );
        setView("portfolio");
        break;
      case "strategy_builder":
        setBuilderDemoTemplateId("sma-trend-filter");
        setBuilderSavedTemplateId(null);
        setBuilderKey((k) => k + 1);
        setDemoNotice(
          "Loading SMA Trend Filter demo template. When it appears below, click Run Strategy to execute.",
        );
        setView("builder");
        break;
    }
  }

  /** Open the Portfolio Lab on a specific sub-tab (shared by the palette). */
  function goToPortfolioTab(tab: PortfolioTab) {
    setSavedDetailId(null);
    setSavedReportDetailId(null);
    setDemoNotice(null);
    setPortfolioTab(tab);
    setPortfolioKey((k) => k + 1);
    setView("portfolio");
  }

  /** Download the current single-asset backtest as a Markdown report. */
  function exportCurrentReport() {
    if (!result) return;
    const tpl = loadSettings().default_report_template;
    const report = buildBacktestReport(result, {}, tpl);
    downloadTextFile(report.filename, report.content);
    markChecklistStep("exported_report");
  }

  /** Open a saved backtest's detail (shared by Home cards + palette search). */
  function openSavedBacktest(id: number) {
    setDemoNotice(null);
    setSavedReportDetailId(null);
    setSavedDetailId(id);
    setView("saved");
  }

  /** Open a saved report's detail (shared by Home cards + palette search). */
  function openSavedReport(id: number) {
    setDemoNotice(null);
    setSavedDetailId(null);
    setSavedReportDetailId(id);
    setView("reports");
  }

  /** Load a saved (My Templates) custom strategy into the builder. */
  function openSavedTemplate(id: number) {
    setBuilderSavedTemplateId(id);
    setBuilderDemoTemplateId(null);
    setBuilderKey((k) => k + 1);
    setDemoNotice(null);
    markChecklistStep("built_strategy");
    setView("builder");
  }

  /** Load a built-in gallery template into the builder. */
  function openGalleryTemplate(id: string) {
    setBuilderDemoTemplateId(id);
    setBuilderSavedTemplateId(null);
    setBuilderKey((k) => k + 1);
    setDemoNotice(null);
    markChecklistStep("built_strategy");
    setView("builder");
  }

  // Command palette entries — all reuse the same navigation / demo / portfolio
  // handlers as the sidebar and onboarding, so behaviour can never diverge.
  // Demo definitions come straight from DEMO_PRESETS (no duplication).
  const NAV_COMMANDS: { view: View; title: string; keywords: string }[] = [
    { view: "home", title: "Go to Home", keywords: "command center dashboard" },
    { view: "backtest", title: "Go to Backtest", keywords: "single asset run strategy" },
    { view: "csv", title: "Go to CSV Upload", keywords: "import upload data file" },
    { view: "builder", title: "Go to Custom Strategy Builder", keywords: "no code rules indicator" },
    { view: "portfolio", title: "Go to Portfolio Lab", keywords: "multi asset weights" },
    { view: "sweep", title: "Go to Research Tools", keywords: "sweep validation optimization research" },
    { view: "sweep", title: "Go to Parameter Sweep", keywords: "grid search sma fast slow" },
    { view: "train-test", title: "Go to Train/Test Validation", keywords: "in sample out of sample" },
    { view: "walk-forward", title: "Go to Walk-Forward Optimization", keywords: "rolling reoptimization" },
    { view: "comparison", title: "Go to Strategy Comparison", keywords: "compare strategies side by side" },
    { view: "saved", title: "Go to Saved Backtests", keywords: "history persisted sqlite" },
    { view: "reports", title: "Go to Saved Reports", keywords: "report gallery markdown" },
    { view: "settings", title: "Go to Settings", keywords: "preferences theme defaults" },
  ];

  const PORTFOLIO_COMMANDS: { tab: PortfolioTab; title: string; keywords: string }[] = [
    { tab: "backtest", title: "Open Portfolio Backtest", keywords: "equal weight rebalance" },
    { tab: "optimize", title: "Open Portfolio Optimization", keywords: "min volatility max sharpe weights" },
    { tab: "walk-forward", title: "Open Walk-Forward Portfolio Optimization", keywords: "rolling" },
    { tab: "frontier", title: "Open Efficient Frontier", keywords: "mean variance random portfolios" },
    { tab: "risk", title: "Open Risk Dashboard", keywords: "var drawdown correlation" },
    { tab: "stress", title: "Open Stress Test", keywords: "scenario crash shock" },
    { tab: "factor", title: "Open Factor Analysis", keywords: "regression exposure beta" },
  ];

  const DEMO_COMMAND_TITLES: Record<DemoPresetId, string> = {
    sma_backtest: "Load Demo Backtest",
    crypto_momentum: "Load Crypto Momentum Demo",
    portfolio_risk: "Load Portfolio Risk Demo",
    efficient_frontier: "Load Efficient Frontier Demo",
    strategy_builder: "Load Strategy Builder Demo",
  };

  const commands: Command[] = [
    ...NAV_COMMANDS.map((c) => ({
      id: `nav-${c.title}`,
      group: "Navigation",
      title: c.title,
      keywords: c.keywords,
      run: () => handleNav(c.view),
    })),
    ...DEMO_PRESETS.map((p) => ({
      id: `demo-${p.id}`,
      group: "Guided demos",
      title: DEMO_COMMAND_TITLES[p.id],
      keywords: `demo preset ${p.detail}`,
      hint: "prefill",
      run: () => handleDemo(p.id),
    })),
    ...PORTFOLIO_COMMANDS.map((c) => ({
      id: `pf-${c.tab}`,
      group: "Portfolio tools",
      title: c.title,
      keywords: c.keywords,
      run: () => goToPortfolioTab(c.tab),
    })),
    // Report actions are only offered when they actually work (a result exists).
    ...(result
      ? [
          {
            id: "report-export-current",
            group: "Report",
            title: "Export current backtest report (Markdown)",
            keywords: "download md save export report current result",
            hint: result.ticker,
            run: exportCurrentReport,
          },
        ]
      : []),
  ];

  const heading = STRATEGY_HEADINGS[strategy];
  const meta = VIEW_META[view];

  return (
    <AppShell
      active={view}
      onNav={handleNav}
      title={meta.title}
      subtitle={meta.subtitle}
    >
      <div className="space-y-8">
        {/* Guided-demo banner — shown in the target workspace after a demo is
            loaded; cleared on navigation or once a real run completes. */}
        {demoNotice && view !== "home" && (
          <div
            className="flex items-start gap-2.5 rounded-xl p-3 text-sm"
            style={{
              background: "var(--accent-softer)",
              border: "1px solid var(--accent-line)",
              color: "var(--accent-text)",
            }}
          >
            <span aria-hidden className="mt-0.5 flex-shrink-0">
              ⚡
            </span>
            <p className="flex-1">{demoNotice}</p>
            <button
              type="button"
              onClick={() => setDemoNotice(null)}
              aria-label="Dismiss demo hint"
              className="flex-shrink-0 px-1 text-slate-400 transition-colors hover:text-slate-200"
            >
              ✕
            </button>
          </div>
        )}

        {/* ── Home / Command Center ────────────────────────────────────── */}
        {view === "home" && (
          <HomeDashboard
            onNav={handleNav}
            onDemo={handleDemo}
            onOpenBacktest={openSavedBacktest}
            onOpenReport={openSavedReport}
          />
        )}

        {/* ── Backtest ─────────────────────────────────────────────────── */}
        {view === "backtest" && (
          <>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                {heading.title}
              </h1>
              <p className="mt-1 text-sm text-slate-500 max-w-2xl">
                {heading.description}
              </p>
            </div>

            <BacktestForm
              key={formKey}
              strategy={strategy}
              onStrategyChange={(s) => {
                setStrategy(s);
                setResult(null);
                setError(null);
              }}
              smaParams={smaParams}
              onSmaParamsChange={setSmaParams}
              rsiParams={rsiParams}
              onRsiParamsChange={setRsiParams}
              bbParams={bbParams}
              onBbParamsChange={setBbParams}
              momentumParams={momentumParams}
              onMomentumParamsChange={setMomentumParams}
              vbParams={vbParams}
              onVbParamsChange={setVbParams}
              pairsParams={pairsParams}
              onPairsParamsChange={setPairsParams}
              onSubmit={handleRun}
              loading={loading}
            />

            {/* Loading skeleton */}
            {loading && (
              <div className="card p-8 text-center">
                <div className="inline-flex items-center gap-3 text-slate-500">
                  <svg
                    className="animate-spin h-5 w-5 text-blue-600"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                    />
                  </svg>
                  <span className="text-sm font-medium">
                    Fetching data and running backtest…
                  </span>
                </div>
              </div>
            )}

            {/* Error banner */}
            {error && !loading && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
                <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
                <div>
                  <p className="text-sm font-semibold text-red-700">
                    Backtest failed
                  </p>
                  <p className="text-sm text-red-600 mt-0.5">{error}</p>
                </div>
              </div>
            )}

            {/* Results */}
            {result && !loading && (
              <>
                <div className="flex flex-wrap items-baseline gap-2">
                  <h2 className="text-lg font-bold text-slate-900">
                    {result.ticker}
                  </h2>
                  <span className="text-slate-400 text-sm">
                    {result.start_date} → {result.end_date}
                  </span>
                  <span className="text-xs text-slate-400">
                    {paramSummary(result)}
                  </span>
                  <span className="ml-auto flex items-center gap-2">
                    <ExportReportButton
                      getReport={(tpl) => buildBacktestReport(result, {}, tpl)}
                    />
                    {!showSaveForm && (
                      <button
                        type="button"
                        onClick={() => setShowSaveForm(true)}
                        className="px-3 py-1 rounded-lg text-xs font-semibold text-blue-700
                                   border border-blue-200 hover:bg-blue-50 transition-colors"
                      >
                        Save backtest
                      </button>
                    )}
                  </span>
                </div>

                {showSaveForm && (
                  <SaveBacktestModal
                    result={result}
                    onSaved={(id) => {
                      setShowSaveForm(false);
                      setSavedRefreshKey((k) => k + 1);
                      setSavedDetailId(id);
                      markChecklistStep("saved_backtest");
                      setView("saved");
                    }}
                    onCancel={() => setShowSaveForm(false)}
                  />
                )}

                <MetricsGrid
                  strategy={result.strategy_metrics}
                  benchmark={result.benchmark_metrics}
                  ticker={result.ticker}
                  strategyLabel={strategyLabel(result)}
                />

                <SignalDiagnostics
                  numTrades={result.num_trades}
                  strategy={result.strategy}
                  positionMode={result.position_mode}
                />

                {(result.position_mode === "short_only" ||
                  result.position_mode === "long_short") && (
                  <>
                    <ShortSellingWarning />
                    {result.diagnostics && (
                      <ShortModeDiagnostics
                        diagnostics={result.diagnostics}
                        mode={result.position_mode}
                      />
                    )}
                  </>
                )}

                <div className="card p-6">
                  <p className="section-title mb-4">Equity Curve</p>
                  <EquityCurveChart data={result.equity_curve} />
                </div>

                <div className="card p-6">
                  <p className="section-title mb-4">Drawdown</p>
                  <DrawdownChart data={result.equity_curve} />
                </div>

                <div className="card p-6">
                  <p className="section-title mb-4">
                    Trade Log{" "}
                    <span className="normal-case font-normal text-slate-400 ml-1">
                      ({result.num_trades} events)
                    </span>
                  </p>
                  <TradeTable trades={result.trades} />
                  <p className="mt-3 text-xs text-slate-400">
                    Most built-in strategies are <span className="font-medium text-slate-500">long-only</span>:
                    they hold cash when flat and can stay out of the market during
                    downtrends — staying flat is expected, not a bug. Use{" "}
                    <span className="font-medium text-slate-500">Pairs Trading</span>{" "}
                    for non-directional exposure.
                  </p>
                </div>
              </>
            )}
          </>
        )}

        {/* ── CSV Backtest ─────────────────────────────────────────────── */}
        {view === "csv" && (
          <>
            <SectionIntro title="CSV Upload Backtest">
              Upload your own historical price CSV and run any single-asset
              strategy on it. The file needs a date column (date / datetime /
              timestamp) and a close column (close / adj_close); optional OHLCV
              columns are ignored. Pairs Trading is not available for uploads.
            </SectionIntro>
            <CsvBacktestPanel />
          </>
        )}

        {/* ── Strategy Builder ─────────────────────────────────────────── */}
        {view === "builder" && (
          <>
            <SectionIntro title="Custom Strategy Builder">
              Compose a long-only, single-asset strategy from predefined
              indicator rules (SMA, RSI, Bollinger Bands, Momentum, close, and
              constants). Define when to enter and when to exit — no code, no
              short selling, no leverage. Rules are evaluated safely on the
              server with vectorised math.
            </SectionIntro>
            <StrategyBuilderPanel
              key={builderKey}
              initialGalleryTemplateId={builderDemoTemplateId ?? undefined}
              initialSavedTemplateId={builderSavedTemplateId ?? undefined}
            />
          </>
        )}

        {/* ── Portfolio Backtest ───────────────────────────────────────── */}
        {view === "portfolio" && (
          <>
            <SectionIntro title="Multi-Asset Portfolio">
              Backtest an equal-weight, long-only portfolio with optional
              rebalancing, or optimize long-only weights (minimum volatility or
              maximum Sharpe) over a historical window. Optimization is
              in-sample and can overfit — it is not investment advice.
            </SectionIntro>
            <PortfolioWorkspace key={portfolioKey} initialTab={portfolioTab} />
          </>
        )}

        {/* ── SMA Parameter Sweep ──────────────────────────────────────── */}
        {view === "sweep" && (
          <>
            <SectionIntro title="SMA Crossover Parameter Sweep">
              Test every combination of fast and slow SMA windows on the same
              asset and date range. Compare Sharpe ratio, CAGR, and max drawdown
              to identify robust parameter regions and avoid over-fitted
              outliers.
            </SectionIntro>
            <SmaSweepPanel />
          </>
        )}

        {/* ── SMA Train/Test Validation ────────────────────────────────── */}
        {view === "train-test" && (
          <>
            <SectionIntro title="SMA Train/Test Out-of-Sample Validation">
              Split your date range into in-sample (IS) and out-of-sample (OOS)
              periods. Run a parameter sweep on IS data only, select the best
              parameters by your chosen metric, then evaluate them on unseen OOS
              data. Reveals whether IS performance is genuine or a product of
              over-fitting.
            </SectionIntro>
            <SmaTrainTestPanel />
          </>
        )}

        {/* ── SMA Walk-Forward ─────────────────────────────────────────── */}
        {view === "walk-forward" && (
          <>
            <SectionIntro title="SMA Walk-Forward Optimization">
              Repeatedly roll a training window forward, sweep SMA parameters
              in-sample, select the best pair, and evaluate it on the
              immediately following out-of-sample window. The out-of-sample
              results are stitched together to form a realistic equity curve
              that avoids look-ahead bias. Parameter stability analysis shows
              whether the strategy requires stable parameters or adapts
              erratically.
            </SectionIntro>
            <SmaWalkForwardPanel />
          </>
        )}

        {/* ── Strategy Comparison ──────────────────────────────────────── */}
        {view === "comparison" && (
          <>
            <SectionIntro title="Strategy Comparison">
              Run five single-asset strategies on the same ticker and date range
              using fixed default parameters. Compare their equity curves,
              risk-adjusted returns, and drawdowns side-by-side to understand
              which strategy styles suited different market environments. Pairs
              Trading is excluded (requires two assets).
            </SectionIntro>
            <StrategyComparisonPanel />
          </>
        )}

        {/* ── Saved Backtests ──────────────────────────────────────────── */}
        {view === "saved" && (
          <>
            <SectionIntro title="Saved Backtests">
              Backtests you have saved are stored locally in a SQLite database.
              Click any row to view the full result, equity curve, and trade
              log.
            </SectionIntro>

            {savedDetailId !== null ? (
              <SavedBacktestDetail
                id={savedDetailId}
                onBack={() => setSavedDetailId(null)}
              />
            ) : (
              <SavedBacktestsList
                refreshKey={savedRefreshKey}
                onSelect={(id) => setSavedDetailId(id)}
              />
            )}
          </>
        )}

        {/* ── Saved Reports (Report Gallery) ───────────────────────────── */}
        {view === "reports" && (
          <>
            <SectionIntro title="Saved Reports">
              Research reports you save are stored locally in a SQLite database
              (Markdown text only — PDF files are not stored). Open any report to
              read it, download the Markdown, or print / save it as a PDF from
              your browser.
            </SectionIntro>

            {savedReportDetailId !== null ? (
              <SavedReportDetail
                id={savedReportDetailId}
                onBack={() => setSavedReportDetailId(null)}
                onDeleted={() => {
                  setSavedReportDetailId(null);
                  setSavedReportsRefreshKey((k) => k + 1);
                }}
              />
            ) : (
              <SavedReportsList
                refreshKey={savedReportsRefreshKey}
                onSelect={(id) => setSavedReportDetailId(id)}
              />
            )}
          </>
        )}

        {/* ── Settings ─────────────────────────────────────────────────── */}
        {view === "settings" && (
          <>
            <SectionIntro title="App Settings">
              Configure local defaults that prefill forms and control display
              conventions. Stored in your browser only — no account, no cloud
              sync.
            </SectionIntro>
            <SettingsPanel />
          </>
        )}
      </div>

      {/* Global command palette (Ctrl/Cmd + K) — overlays every workspace. */}
      <CommandPalette
        commands={commands}
        onOpenBacktest={openSavedBacktest}
        onOpenReport={openSavedReport}
        onOpenSavedTemplate={openSavedTemplate}
        onOpenGalleryTemplate={openGalleryTemplate}
      />
    </AppShell>
  );
}
