"use client";

import { useState } from "react";
import BacktestForm from "@/components/BacktestForm";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";
import {
  runBacktest,
  runBbBacktest,
  runMomentumBacktest,
  runRsiBacktest,
  runVbBacktest,
} from "@/lib/api";
import type {
  BacktestRequest,
  BacktestResponse,
  BbBacktestRequest,
  MomentumBacktestRequest,
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
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const [strategy, setStrategy] = useState<StrategyType>("sma_crossover");
  const [smaParams, setSmaParams] = useState<BacktestRequest>(DEFAULT_SMA_PARAMS);
  const [rsiParams, setRsiParams] = useState<RsiBacktestRequest>(DEFAULT_RSI_PARAMS);
  const [bbParams, setBbParams] = useState<BbBacktestRequest>(DEFAULT_BB_PARAMS);
  const [momentumParams, setMomentumParams] = useState<MomentumBacktestRequest>(
    DEFAULT_MOMENTUM_PARAMS,
  );
  const [vbParams, setVbParams] = useState<VbBacktestRequest>(DEFAULT_VB_PARAMS);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    if (loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

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
                : await runVbBacktest(vbParams);
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred.",
      );
    } finally {
      setLoading(false);
    }
  }

  const heading = STRATEGY_HEADINGS[strategy];

  return (
    <div className="space-y-8">
      {/* ── Strategy heading ─────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{heading.title}</h1>
        <p className="mt-1 text-sm text-slate-500 max-w-2xl">
          {heading.description}
        </p>
      </div>

      {/* ── Parameter form ───────────────────────────────────────────── */}
      <BacktestForm
        strategy={strategy}
        onStrategyChange={(s) => {
          setStrategy(s);
          // Clear stale results when the strategy changes.
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
        onSubmit={handleRun}
        loading={loading}
      />

      {/* ── Loading skeleton ─────────────────────────────────────────── */}
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

      {/* ── Error banner ─────────────────────────────────────────────── */}
      {error && !loading && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
          <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-700">Backtest failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────── */}
      {result && !loading && (
        <>
          {/* Summary header */}
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-lg font-bold text-slate-900">{result.ticker}</h2>
            <span className="text-slate-400 text-sm">
              {result.start_date} → {result.end_date}
            </span>
            <span className="ml-auto text-xs text-slate-400">
              {paramSummary(result)}
            </span>
          </div>

          {/* Metric cards */}
          <MetricsGrid
            strategy={result.strategy_metrics}
            benchmark={result.benchmark_metrics}
            ticker={result.ticker}
            strategyLabel={strategyLabel(result)}
          />

          {/* Equity curve */}
          <div className="card p-6">
            <p className="section-title mb-4">Equity Curve</p>
            <EquityCurveChart data={result.equity_curve} />
          </div>

          {/* Drawdown */}
          <div className="card p-6">
            <p className="section-title mb-4">Drawdown</p>
            <DrawdownChart data={result.equity_curve} />
          </div>

          {/* Trade log */}
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
    </div>
  );
}
