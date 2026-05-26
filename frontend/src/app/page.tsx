"use client";

import { useState } from "react";
import BacktestForm from "@/components/BacktestForm";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";
import { runBacktest } from "@/lib/api";
import type { BacktestRequest, BacktestResponse } from "@/lib/types";

// Default parameters shown in the form on first load.
const DEFAULT_PARAMS: BacktestRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  fast_window: 50,
  slow_window: 200,
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

export default function HomePage() {
  const [params, setParams] = useState<BacktestRequest>(DEFAULT_PARAMS);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await runBacktest(params);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* ── Strategy heading ─────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          SMA Crossover Backtest
        </h1>
        <p className="mt-1 text-sm text-slate-500 max-w-2xl">
          Long-only strategy that buys when the fast SMA crosses above the slow
          SMA and exits when it crosses below. Signal is shifted one day forward
          to prevent lookahead bias.
        </p>
      </div>

      {/* ── Parameter form ───────────────────────────────────────────── */}
      <BacktestForm
        params={params}
        onChange={setParams}
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
            <h2 className="text-lg font-bold text-slate-900">
              {result.ticker}
            </h2>
            <span className="text-slate-400 text-sm">
              {result.start_date} → {result.end_date}
            </span>
            <span className="ml-auto text-xs text-slate-400">
              SMA {result.fast_window}/{result.slow_window} ·{" "}
              {result.transaction_cost_bps} bps cost ·{" "}
              {result.num_trades} trade events
            </span>
          </div>

          {/* Metric cards */}
          <MetricsGrid
            strategy={result.strategy_metrics}
            benchmark={result.benchmark_metrics}
            ticker={result.ticker}
            fastWindow={result.fast_window}
            slowWindow={result.slow_window}
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
