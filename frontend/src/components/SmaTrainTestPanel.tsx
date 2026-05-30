"use client";

/**
 * SMA Train/Test Out-of-Sample Validation panel.
 *
 * Splits the date range at a user-defined split_date:
 *   • In-sample  (IS):  [start_date, split_date)  — used for parameter selection
 *   • Out-of-sample (OOS): [split_date, end_date]  — evaluation only
 *
 * Displays:
 *   - Best IS parameters
 *   - IS vs OOS metrics comparison table
 *   - Degradation summary (colour-coded)
 *   - Warning banner when OOS performance collapses
 *   - OOS equity curve chart
 *   - Full IS parameter sweep table (for context)
 */

import { useState } from "react";
import { BacktestApiError, runSmaTrainTest } from "@/lib/api";
import type { SmaTrainTestRequest, SmaTrainTestResponse } from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";
import EquityCurveChart from "./EquityCurveChart";
import SmaSweepTable from "./SmaSweepTable";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PARAMS: SmaTrainTestRequest = {
  ticker: "SPY",
  start_date: "2010-01-01",
  split_date: "2018-01-01",
  end_date: "2023-12-31",
  fast_windows: [10, 20, 30, 50],
  slow_windows: [100, 150, 200],
  transaction_cost_bps: 10,
  initial_capital: 100_000,
  selection_metric: "sharpe_ratio",
};

const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "GLD", "BTC-USD"];

// ---------------------------------------------------------------------------
// Styling constants
// ---------------------------------------------------------------------------

const inputCls =
  "w-full px-3 py-2 text-sm border border-slate-300 rounded-lg " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 bg-white";

const labelCls = "block text-xs font-medium text-slate-600 mb-1";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Parse a comma-separated string into a sorted unique array of ints >= 2. */
function parseWindows(raw: string): number[] | null {
  const parts = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length === 0 || parts.length > 10) return null;
  const nums: number[] = [];
  for (const p of parts) {
    const n = parseInt(p, 10);
    if (isNaN(n) || n < 2 || String(n) !== p) return null;
    nums.push(n);
  }
  return Array.from(new Set(nums)).sort((a, b) => a - b);
}

function windowsToString(arr: number[]): string {
  return arr.join(", ");
}

// ---------------------------------------------------------------------------
// Metric comparison row
// ---------------------------------------------------------------------------

interface MetricRowProps {
  label: string;
  isValue: number;
  oosValue: number;
  fmt: (v: number) => string;
  /** Higher is better (true for Sharpe, CAGR; false for max_drawdown, volatility). */
  higherBetter?: boolean;
}

function MetricRow({ label, isValue, oosValue, fmt, higherBetter = true }: MetricRowProps) {
  const diff = oosValue - isValue;
  const improved = higherBetter ? diff >= 0 : diff <= 0;
  const diffColor = improved ? "text-emerald-600" : "text-red-600";
  const diffSign = diff >= 0 ? "+" : "";

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="px-3 py-1.5 text-sm text-slate-600">{label}</td>
      <td className="px-3 py-1.5 text-sm text-right tabular-nums font-medium text-slate-700">
        {fmt(isValue)}
      </td>
      <td className="px-3 py-1.5 text-sm text-right tabular-nums font-medium text-slate-700">
        {fmt(oosValue)}
      </td>
      <td className={`px-3 py-1.5 text-sm text-right tabular-nums font-semibold ${diffColor}`}>
        {diffSign}{fmt(diff)}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SmaTrainTestPanel() {
  const [ticker, setTicker] = useState(DEFAULT_PARAMS.ticker);
  const [startDate, setStartDate] = useState(DEFAULT_PARAMS.start_date);
  const [splitDate, setSplitDate] = useState(DEFAULT_PARAMS.split_date);
  const [endDate, setEndDate] = useState(DEFAULT_PARAMS.end_date);
  const [fastRaw, setFastRaw] = useState(windowsToString(DEFAULT_PARAMS.fast_windows));
  const [slowRaw, setSlowRaw] = useState(windowsToString(DEFAULT_PARAMS.slow_windows));
  const [costBpsStr, setCostBpsStr] = useState(String(DEFAULT_PARAMS.transaction_cost_bps));
  const [capitalStr, setCapitalStr] = useState(String(DEFAULT_PARAMS.initial_capital));

  // Derived numbers — parsed at render time so the input can hold partial strings
  const costBps = parseFloat(costBpsStr);
  const capital = parseFloat(capitalStr);

  const [selectionMetric, setSelectionMetric] = useState<SmaTrainTestRequest["selection_metric"]>(
    DEFAULT_PARAMS.selection_metric,
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SmaTrainTestResponse | null>(null);

  // ── Validation ────────────────────────────────────────────────────────
  const fastWindows = parseWindows(fastRaw);
  const slowWindows = parseWindows(slowRaw);
  const datesOk = startDate < splitDate && splitDate < endDate;
  const combsOk =
    fastWindows !== null &&
    slowWindows !== null &&
    fastWindows.length * slowWindows.length <= 100;
  const moneyOk = !isNaN(costBps) && costBps >= 0 && costBps < 10_000 && !isNaN(capital) && capital > 0;

  const formInvalid =
    !ticker.trim() ||
    !datesOk ||
    fastWindows === null ||
    slowWindows === null ||
    !combsOk ||
    !moneyOk ||
    loading;

  let validationMsg: string | null = null;
  if (!ticker.trim()) {
    validationMsg = "Ticker is required.";
  } else if (startDate >= splitDate) {
    validationMsg = "Start date must be before split date.";
  } else if (splitDate >= endDate) {
    validationMsg = "Split date must be before end date.";
  } else if (fastWindows === null) {
    validationMsg = "Fast windows must be 1–10 comma-separated integers, each ≥ 2.";
  } else if (slowWindows === null) {
    validationMsg = "Slow windows must be 1–10 comma-separated integers, each ≥ 2.";
  } else if (!combsOk) {
    validationMsg = `Too many combinations (${fastWindows?.length ?? 0} × ${slowWindows?.length ?? 0} = ${(fastWindows?.length ?? 0) * (slowWindows?.length ?? 0)}).  Maximum is 100.`;
  } else if (isNaN(costBps)) {
    validationMsg = "Transaction cost must be a valid number (≥ 0 bps).";
  } else if (costBps < 0 || costBps >= 10_000) {
    validationMsg = "Transaction cost must be at least 0 and less than 10,000 bps.";
  } else if (isNaN(capital)) {
    validationMsg = "Initial capital must be a valid number (> 0).";
  } else if (capital <= 0) {
    validationMsg = "Initial capital must be greater than 0.";
  }

  // ── Submit ────────────────────────────────────────────────────────────
  async function handleRun() {
    if (formInvalid || fastWindows === null || slowWindows === null) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runSmaTrainTest({
        ticker: ticker.trim().toUpperCase(),
        start_date: startDate,
        split_date: splitDate,
        end_date: endDate,
        fast_windows: fastWindows,
        slow_windows: slowWindows,
        transaction_cost_bps: costBps,
        initial_capital: capital,
        selection_metric: selectionMetric,
      });
      setResult(data);
    } catch (err) {
      setError(
        err instanceof BacktestApiError || err instanceof Error
          ? err.message
          : "An unexpected error occurred.",
      );
    } finally {
      setLoading(false);
    }
  }

  const combCount =
    fastWindows !== null && slowWindows !== null
      ? fastWindows.length * slowWindows.length
      : null;

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* ── Form card ──────────────────────────────────────────────────── */}
      <div className="card p-6 space-y-5">

        {/* Ticker row */}
        <div>
          <label className={labelCls}>Ticker</label>
          <div className="flex gap-2 flex-wrap items-center">
            <input
              type="text"
              className={`${inputCls} uppercase w-36`}
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="SPY"
              disabled={loading}
              maxLength={12}
            />
            <div className="flex gap-1.5 flex-wrap">
              {POPULAR_TICKERS.map((t) => (
                <button
                  key={t}
                  type="button"
                  disabled={loading}
                  onClick={() => setTicker(t)}
                  className={
                    "px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors " +
                    (ticker === t
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-slate-600 border-slate-300 hover:border-blue-400 hover:text-blue-600")
                  }
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Date range — 3 columns */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className={labelCls}>Start Date (IS begins)</label>
            <input
              type="date"
              className={inputCls}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              disabled={loading}
            />
          </div>
          <div>
            <label className={labelCls}>Split Date (IS → OOS)</label>
            <input
              type="date"
              className={inputCls}
              value={splitDate}
              onChange={(e) => setSplitDate(e.target.value)}
              disabled={loading}
            />
          </div>
          <div>
            <label className={labelCls}>End Date (OOS ends)</label>
            <input
              type="date"
              className={inputCls}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        {/* Window grids */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className={labelCls}>Fast Windows (days, comma-separated)</label>
            <input
              type="text"
              className={`${inputCls} font-mono`}
              value={fastRaw}
              onChange={(e) => setFastRaw(e.target.value)}
              placeholder="10, 20, 30, 50"
              disabled={loading}
            />
            <p className="text-xs text-slate-400 mt-1">1–10 values, each ≥ 2</p>
          </div>
          <div>
            <label className={labelCls}>Slow Windows (days, comma-separated)</label>
            <input
              type="text"
              className={`${inputCls} font-mono`}
              value={slowRaw}
              onChange={(e) => setSlowRaw(e.target.value)}
              placeholder="100, 150, 200"
              disabled={loading}
            />
            <p className="text-xs text-slate-400 mt-1">1–10 values, each ≥ 2</p>
          </div>
        </div>

        {/* Combination count hint */}
        {combCount !== null && (
          <p className="text-xs text-slate-500">
            Grid size:{" "}
            <span className={combCount > 100 ? "text-red-600 font-semibold" : "font-medium"}>
              {fastWindows?.length ?? 0} fast × {slowWindows?.length ?? 0} slow
              = {combCount} combinations
            </span>
            {combCount > 100 && " — reduce to ≤ 100."}
          </p>
        )}

        {/* Selection metric + cost + capital */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className={labelCls}>Selection Metric</label>
            <select
              className={inputCls}
              value={selectionMetric}
              onChange={(e) =>
                setSelectionMetric(e.target.value as SmaTrainTestRequest["selection_metric"])
              }
              disabled={loading}
            >
              <option value="sharpe_ratio">Sharpe Ratio</option>
              <option value="cagr">CAGR</option>
              <option value="calmar_ratio">Calmar Ratio</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>Transaction Cost (bps, one-way)</label>
            <input
              type="number"
              className={inputCls}
              value={costBpsStr}
              min={0}
              max={9999}
              step={1}
              onChange={(e) => setCostBpsStr(e.target.value)}
              disabled={loading}
            />
          </div>
          <div>
            <label className={labelCls}>Initial Capital ($)</label>
            <input
              type="number"
              className={inputCls}
              value={capitalStr}
              min={1}
              step={10000}
              onChange={(e) => setCapitalStr(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        {validationMsg && (
          <p className="text-xs text-red-600 font-medium">{validationMsg}</p>
        )}

        <button
          type="button"
          disabled={formInvalid}
          onClick={handleRun}
          className={
            "w-full py-2.5 px-4 rounded-xl font-semibold text-sm transition-colors " +
            (formInvalid
              ? "bg-slate-100 text-slate-400 cursor-not-allowed"
              : "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800")
          }
        >
          {loading ? "Running validation…" : "Run Train/Test Validation"}
        </button>
      </div>

      {/* ── Loading ──────────────────────────────────────────────────────── */}
      {loading && (
        <div className="card p-8 text-center">
          <div className="inline-flex items-center gap-3 text-slate-500">
            <svg className="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span className="text-sm font-medium">Fetching data and running sweep…</span>
          </div>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {error && !loading && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
          <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-700">Validation failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────────── */}
      {result && !loading && (
        <div className="space-y-6">

          {/* ── OOS Collapsed warning ──────────────────────────────────── */}
          {result.oos_collapsed && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex gap-3">
              <span className="text-amber-500 mt-0.5 flex-shrink-0 text-lg">⚠</span>
              <div>
                <p className="text-sm font-semibold text-amber-800">
                  Out-of-Sample Performance Collapsed
                </p>
                <p className="text-sm text-amber-700 mt-0.5">
                  The OOS Sharpe ratio (
                  <span className="font-semibold">
                    {fmtRatio(result.out_of_sample_metrics.sharpe_ratio)}
                  </span>
                  ) is{" "}
                  {result.out_of_sample_metrics.sharpe_ratio < 0
                    ? "negative"
                    : "less than 50% of the in-sample Sharpe"}
                  . This suggests the selected parameters may be over-fitted to the
                  in-sample period and do not generalise well.
                </p>
              </div>
            </div>
          )}

          {/* ── Summary header ─────────────────────────────────────────── */}
          <div className="card p-6 space-y-4">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="text-lg font-bold text-slate-900">{result.ticker}</h2>
              <span className="text-slate-400 text-sm">
                {result.start_date} → {result.split_date} → {result.end_date}
              </span>
              <span className="ml-auto text-xs text-slate-400">
                {result.transaction_cost_bps} bps · $
                {result.initial_capital.toLocaleString()}
              </span>
            </div>

            {/* Best parameters */}
            <div className="flex flex-wrap gap-6">
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-0.5">Best Fast Window</p>
                <p className="text-2xl font-bold text-blue-600">
                  {result.best_fast_window}
                </p>
                <p className="text-xs text-slate-400">days</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-0.5">Best Slow Window</p>
                <p className="text-2xl font-bold text-blue-600">
                  {result.best_slow_window}
                </p>
                <p className="text-xs text-slate-400">days</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-0.5">Selected by</p>
                <p className="text-sm font-semibold text-slate-700">
                  {{
                    sharpe_ratio: "Sharpe Ratio",
                    cagr: "CAGR",
                    calmar_ratio: "Calmar Ratio",
                  }[result.selection_metric] ?? result.selection_metric}
                </p>
              </div>
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-0.5">IS period</p>
                <p className="text-sm font-semibold text-slate-700">
                  {result.in_sample_days} days
                </p>
              </div>
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-0.5">OOS period</p>
                <p className="text-sm font-semibold text-slate-700">
                  {result.out_of_sample_days} days
                </p>
              </div>
            </div>
          </div>

          {/* ── IS vs OOS metrics comparison ───────────────────────────── */}
          <div className="card p-6 space-y-3">
            <p className="section-title">In-Sample vs Out-of-Sample Metrics</p>
            <p className="text-xs text-slate-500">
              Parameters selected on in-sample data only.  OOS column shows true
              out-of-sample performance.  Δ = OOS − IS.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b-2 border-slate-200">
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Metric</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">
                      In-Sample
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">
                      Out-of-Sample
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  <MetricRow
                    label="Sharpe Ratio"
                    isValue={result.in_sample_metrics.sharpe_ratio}
                    oosValue={result.out_of_sample_metrics.sharpe_ratio}
                    fmt={fmtRatio}
                  />
                  <MetricRow
                    label="CAGR"
                    isValue={result.in_sample_metrics.cagr}
                    oosValue={result.out_of_sample_metrics.cagr}
                    fmt={fmtPct}
                  />
                  <MetricRow
                    label="Sortino Ratio"
                    isValue={result.in_sample_metrics.sortino_ratio}
                    oosValue={result.out_of_sample_metrics.sortino_ratio}
                    fmt={fmtRatio}
                  />
                  <MetricRow
                    label="Max Drawdown"
                    isValue={result.in_sample_metrics.max_drawdown}
                    oosValue={result.out_of_sample_metrics.max_drawdown}
                    fmt={fmtPct}
                    higherBetter={false}
                  />
                  <MetricRow
                    label="Volatility"
                    isValue={result.in_sample_metrics.volatility}
                    oosValue={result.out_of_sample_metrics.volatility}
                    fmt={fmtPct}
                    higherBetter={false}
                  />
                  <MetricRow
                    label="Calmar Ratio"
                    isValue={result.in_sample_metrics.calmar_ratio}
                    oosValue={result.out_of_sample_metrics.calmar_ratio}
                    fmt={fmtRatio}
                  />
                  <MetricRow
                    label="Win Rate"
                    isValue={result.in_sample_metrics.win_rate}
                    oosValue={result.out_of_sample_metrics.win_rate}
                    fmt={fmtPct}
                  />
                </tbody>
              </table>
            </div>

            {/* Degradation summary */}
            <div className="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-2 md:grid-cols-4">
              {[
                {
                  label: "Sharpe degradation",
                  value: fmtRatio(result.sharpe_degradation),
                  bad: result.sharpe_degradation < 0,
                },
                {
                  label: "CAGR degradation",
                  value: fmtPct(result.cagr_degradation),
                  bad: result.cagr_degradation < 0,
                },
                {
                  label: "Calmar degradation",
                  value: fmtRatio(result.calmar_degradation),
                  bad: result.calmar_degradation < 0,
                },
                {
                  label: "Drawdown worsening",
                  value: fmtPct(result.max_drawdown_worsening),
                  bad: result.max_drawdown_worsening > 0,
                },
              ].map(({ label, value, bad }) => (
                <div key={label} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">{label}</p>
                  <p className={`text-sm font-semibold ${bad ? "text-red-600" : "text-emerald-600"}`}>
                    {value}
                  </p>
                </div>
              ))}
            </div>

            {/* OOS benchmark comparison */}
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-xs font-medium text-slate-500 mb-2">
                OOS Buy-and-Hold Benchmark
              </p>
              <div className="flex flex-wrap gap-6 text-sm">
                {[
                  {
                    label: "Sharpe",
                    value: fmtRatio(result.out_of_sample_benchmark_metrics.sharpe_ratio),
                  },
                  {
                    label: "CAGR",
                    value: fmtPct(result.out_of_sample_benchmark_metrics.cagr),
                  },
                  {
                    label: "Max DD",
                    value: fmtPct(result.out_of_sample_benchmark_metrics.max_drawdown),
                  },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <span className="text-slate-500">{label}: </span>
                    <span className="font-semibold text-slate-700">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── OOS equity curve ───────────────────────────────────────── */}
          <div className="card p-6">
            <p className="section-title mb-4">Out-of-Sample Equity Curve</p>
            <EquityCurveChart data={result.out_of_sample_equity_curve} />
          </div>

          {/* ── Full IS sweep table ────────────────────────────────────── */}
          <div className="card p-6 space-y-3">
            <p className="section-title">
              In-Sample Parameter Sweep Results{" "}
              <span className="normal-case font-normal text-slate-400 ml-1">
                ({result.all_in_sample_results.length} valid combinations)
              </span>
            </p>
            <p className="text-xs text-slate-500">
              All valid (fast &lt; slow) combinations evaluated on in-sample data.
              The{" "}
              <span className="font-semibold text-slate-700">
                best row (
                {result.best_fast_window}/{result.best_slow_window})
              </span>{" "}
              was selected by{" "}
              {{
                sharpe_ratio: "Sharpe Ratio",
                cagr: "CAGR",
                calmar_ratio: "Calmar Ratio",
              }[result.selection_metric] ?? result.selection_metric}
              .
            </p>
            <SmaSweepTable rows={result.all_in_sample_results} />
          </div>

        </div>
      )}
    </div>
  );
}
