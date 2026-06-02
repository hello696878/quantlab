"use client";

import { useState } from "react";
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
import PortfolioWorkspace from "@/components/PortfolioWorkspace";
import SaveBacktestModal from "@/components/SaveBacktestModal";
import ExportReportButton from "@/components/ExportReportButton";
import { buildBacktestReport } from "@/lib/reportExport";
import SavedBacktestsList from "@/components/SavedBacktestsList";
import SavedBacktestDetail from "@/components/SavedBacktestDetail";
import SavedReportsList from "@/components/SavedReportsList";
import SavedReportDetail from "@/components/SavedReportDetail";
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

const DEFAULT_SMA_PARAMS: BacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  fast_window: 50,
  slow_window: 200,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

const DEFAULT_RSI_PARAMS: RsiBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  rsi_window: 14,
  oversold_threshold: 30,
  exit_threshold: 50,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

const DEFAULT_BB_PARAMS: BbBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  bb_window: 20,
  num_std: 2.0,
  exit_band: "middle",
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

const DEFAULT_MOMENTUM_PARAMS: MomentumBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  momentum_window: 126,
  entry_threshold: 0.0,
  exit_threshold: 0.0,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

const DEFAULT_VB_PARAMS: VbBacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  lookback_window: 20,
  breakout_multiplier: 1.0,
  exit_window: 10,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

const DEFAULT_PAIRS_PARAMS: PairsBacktestRequest = {
  asset_y: "KO",
  asset_x: "PEP",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  lookback_window: 60,
  entry_z_score: 2.0,
  exit_z_score: 0.5,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
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
    return `BB(${r.bb_window ?? 20}, ${r.bb_num_std ?? 2}σ) exit:${exit}`;
  }
  if (r.strategy === "momentum") {
    const entry = r.momentum_entry_threshold ?? 0;
    const exit = r.momentum_exit_threshold ?? 0;
    return `Momentum(${r.momentum_window ?? 126}) entry:${entry} exit:${exit}`;
  }
  if (r.strategy === "volatility_breakout") {
    return (
      `VolBreakout(${r.vb_lookback_window ?? 20}, ` +
      `${r.vb_breakout_multiplier ?? 1}x range, exit:${r.vb_exit_window ?? 10})`
    );
  }
  if (r.strategy === "pairs") {
    return (
      `Pairs ${r.pairs_asset_y ?? ""}/${r.pairs_asset_x ?? ""} ` +
      `Z(${r.pairs_lookback_window ?? 60}) ` +
      `entry:${r.pairs_entry_z_score ?? 2} exit:${r.pairs_exit_z_score ?? 0.5}`
    );
  }
  return r.strategy;
}

/** Build a compact param summary shown beside the ticker in the results header. */
function paramSummary(r: BacktestResponse): string {
  const cost = `${r.transaction_cost_bps} bps`;
  const trades = `${r.num_trades} trade events`;
  if (r.strategy === "sma_crossover") {
    return `SMA ${r.fast_window}/${r.slow_window} · ${cost} · ${trades}`;
  }
  if (r.strategy === "rsi_mean_reversion") {
    return (
      `RSI(${r.rsi_window ?? 14}) OB=${r.oversold_threshold} ` +
      `Exit=${r.exit_threshold} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "bollinger_band") {
    return (
      `BB(${r.bb_window ?? 20}, ${r.bb_num_std ?? 2}σ) ` +
      `exit:${r.bb_exit_band ?? "middle"} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "momentum") {
    return (
      `Momentum(${r.momentum_window ?? 126}) ` +
      `entry:${r.momentum_entry_threshold ?? 0} ` +
      `exit:${r.momentum_exit_threshold ?? 0} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "volatility_breakout") {
    return (
      `VolBreakout lookback:${r.vb_lookback_window ?? 20} ` +
      `mult:${r.vb_breakout_multiplier ?? 1}x range ` +
      `exit mean:${r.vb_exit_window ?? 10} · ${cost} · ${trades}`
    );
  }
  if (r.strategy === "pairs") {
    return (
      `Spread ${r.pairs_asset_y ?? ""}/${r.pairs_asset_x ?? ""} ` +
      `lookback:${r.pairs_lookback_window ?? 60} ` +
      `entry:|z|>${r.pairs_entry_z_score ?? 2} ` +
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
  const [view, setView] = useState<View>("backtest");

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
    if (next !== "saved") setSavedDetailId(null);
    if (next !== "reports") setSavedReportDetailId(null);
  }

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
                    <ExportReportButton getReport={() => buildBacktestReport(result)} />
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
            <StrategyBuilderPanel />
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
            <PortfolioWorkspace />
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
      </div>
    </AppShell>
  );
}
