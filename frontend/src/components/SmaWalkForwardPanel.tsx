"use client";

/**
 * SMA Walk-Forward Optimization panel.
 *
 * Rolls a training window through the full date range, runs an SMA
 * parameter sweep on each training period, selects the best params, then
 * evaluates them on the following out-of-sample test window.  The test
 * windows are stitched into one continuous OOS equity curve.
 *
 * Displays:
 *   - Aggregate OOS metrics
 *   - Stitched OOS equity curve vs benchmark
 *   - Parameter stability summary + instability warning
 *   - Per-window results table
 */

import { useState } from "react";
import { BacktestApiError, runSmaWalkForward } from "@/lib/api";
import type {
  SmaWalkForwardRequest,
  SmaWalkForwardResponse,
} from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";
import EquityCurveChart from "./EquityCurveChart";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PARAMS: SmaWalkForwardRequest = {
  ticker: "SPY",
  start_date: "2010-01-01",
  end_date: "2023-12-31",
  train_window_days: 756,
  test_window_days: 126,
  step_days: 126,
  fast_windows: [10, 20, 30, 40, 50],
  slow_windows: [100, 150, 200, 250],
  selection_metric: "sharpe_ratio",
  initial_capital: 100_000,
  transaction_cost_bps: 10,
};

const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "GLD", "BTC-USD"];

// ---------------------------------------------------------------------------
// Styling
// ---------------------------------------------------------------------------

const inputCls =
  "w-full px-3 py-2 text-sm border border-slate-300 rounded-lg " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 bg-white";

const labelCls = "block text-xs font-medium text-slate-600 mb-1";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

const METRIC_LABEL: Record<string, string> = {
  sharpe_ratio: "Sharpe Ratio",
  cagr: "CAGR",
  calmar_ratio: "Calmar Ratio",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SmaWalkForwardPanel() {
  const [ticker, setTicker] = useState(DEFAULT_PARAMS.ticker);
  const [startDate, setStartDate] = useState(DEFAULT_PARAMS.start_date);
  const [endDate, setEndDate] = useState(DEFAULT_PARAMS.end_date);
  const [trainDaysStr, setTrainDaysStr] = useState(String(DEFAULT_PARAMS.train_window_days));
  const [testDaysStr, setTestDaysStr] = useState(String(DEFAULT_PARAMS.test_window_days));
  const [stepDaysStr, setStepDaysStr] = useState(String(DEFAULT_PARAMS.step_days));
  const [fastRaw, setFastRaw] = useState(windowsToString(DEFAULT_PARAMS.fast_windows));
  const [slowRaw, setSlowRaw] = useState(windowsToString(DEFAULT_PARAMS.slow_windows));
  const [selectionMetric, setSelectionMetric] = useState<
    SmaWalkForwardRequest["selection_metric"]
  >(DEFAULT_PARAMS.selection_metric);
  const [costBpsStr, setCostBpsStr] = useState(String(DEFAULT_PARAMS.transaction_cost_bps));
  const [capitalStr, setCapitalStr] = useState(String(DEFAULT_PARAMS.initial_capital));

  // Derived numbers — parsed at render time so inputs can hold partial strings
  const trainDays = parseInt(trainDaysStr, 10);
  const testDays = parseInt(testDaysStr, 10);
  const stepDays = parseInt(stepDaysStr, 10);
  const costBps = parseFloat(costBpsStr);
  const capital = parseFloat(capitalStr);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SmaWalkForwardResponse | null>(null);

  // ── Validation ──────────────────────────────────────────────────────────
  const fastWindows = parseWindows(fastRaw);
  const slowWindows = parseWindows(slowRaw);
  const datesOk = startDate < endDate;
  const windowsOk = !isNaN(trainDays) && trainDays >= 10 && !isNaN(testDays) && testDays >= 5 && !isNaN(stepDays) && stepDays >= 1;
  const combsOk =
    fastWindows !== null &&
    slowWindows !== null &&
    fastWindows.length * slowWindows.length <= 100;
  const moneyOk = !isNaN(costBps) && costBps >= 0 && costBps < 10_000 && !isNaN(capital) && capital > 0;

  const formInvalid =
    !ticker.trim() ||
    !datesOk ||
    !windowsOk ||
    fastWindows === null ||
    slowWindows === null ||
    !combsOk ||
    !moneyOk ||
    loading;

  let validationMsg: string | null = null;
  if (!ticker.trim()) {
    validationMsg = "Ticker is required.";
  } else if (!datesOk) {
    validationMsg = "Start date must be before end date.";
  } else if (isNaN(trainDays)) {
    validationMsg = "Train window must be a valid number.";
  } else if (trainDays < 10) {
    validationMsg = "Train window must be at least 10 days.";
  } else if (isNaN(testDays)) {
    validationMsg = "Test window must be a valid number.";
  } else if (testDays < 5) {
    validationMsg = "Test window must be at least 5 days.";
  } else if (isNaN(stepDays)) {
    validationMsg = "Step must be a valid number.";
  } else if (stepDays < 1) {
    validationMsg = "Step must be at least 1 day.";
  } else if (fastWindows === null) {
    validationMsg = "Fast windows must be 1–10 comma-separated integers, each ≥ 2.";
  } else if (slowWindows === null) {
    validationMsg = "Slow windows must be 1–10 comma-separated integers, each ≥ 2.";
  } else if (!combsOk) {
    const total = (fastWindows?.length ?? 0) * (slowWindows?.length ?? 0);
    validationMsg = `Too many combinations (${total}). Maximum is 100.`;
  } else if (isNaN(costBps)) {
    validationMsg = "Transaction cost must be a valid number (≥ 0 bps).";
  } else if (costBps < 0 || costBps >= 10_000) {
    validationMsg = "Transaction cost must be 0 to < 10,000 bps.";
  } else if (isNaN(capital)) {
    validationMsg = "Initial capital must be a valid number (> 0).";
  } else if (capital <= 0) {
    validationMsg = "Initial capital must be greater than 0.";
  }

  const combCount =
    fastWindows !== null && slowWindows !== null
      ? fastWindows.length * slowWindows.length
      : null;

  // ── Submit ───────────────────────────────────────────────────────────────
  async function handleRun() {
    if (formInvalid || fastWindows === null || slowWindows === null) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runSmaWalkForward({
        ticker: ticker.trim().toUpperCase(),
        start_date: startDate,
        end_date: endDate,
        train_window_days: trainDays,
        test_window_days: testDays,
        step_days: stepDays,
        fast_windows: fastWindows,
        slow_windows: slowWindows,
        selection_metric: selectionMetric,
        initial_capital: capital,
        transaction_cost_bps: costBps,
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

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* ── Form card ──────────────────────────────────────────────────────── */}
      <div className="card p-6 space-y-5">

        {/* Ticker */}
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

        {/* Date range */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className={labelCls}>Start Date</label>
            <input type="date" className={inputCls} value={startDate}
              onChange={(e) => setStartDate(e.target.value)} disabled={loading} />
          </div>
          <div>
            <label className={labelCls}>End Date</label>
            <input type="date" className={inputCls} value={endDate}
              onChange={(e) => setEndDate(e.target.value)} disabled={loading} />
          </div>
        </div>

        {/* Window settings */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className={labelCls}>Train Window (days)</label>
            <input type="number" className={inputCls} value={trainDaysStr} min={10} step={63}
              onChange={(e) => setTrainDaysStr(e.target.value)} disabled={loading} />
            <p className="text-xs text-slate-400 mt-1">Min 10. Default 756 ≈ 3 yrs.</p>
          </div>
          <div>
            <label className={labelCls}>Test Window (days)</label>
            <input type="number" className={inputCls} value={testDaysStr} min={5} step={21}
              onChange={(e) => setTestDaysStr(e.target.value)} disabled={loading} />
            <p className="text-xs text-slate-400 mt-1">Min 5. Default 126 ≈ 6 mo.</p>
          </div>
          <div>
            <label className={labelCls}>Step (days)</label>
            <input type="number" className={inputCls} value={stepDaysStr} min={1} step={21}
              onChange={(e) => setStepDaysStr(e.target.value)} disabled={loading} />
            <p className="text-xs text-slate-400 mt-1">How far to roll each step.</p>
          </div>
        </div>

        {/* Window grids */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className={labelCls}>Fast Windows (comma-separated)</label>
            <input type="text" className={`${inputCls} font-mono`} value={fastRaw}
              onChange={(e) => setFastRaw(e.target.value)} placeholder="10, 20, 30, 40, 50"
              disabled={loading} />
            <p className="text-xs text-slate-400 mt-1">1–10 values, each ≥ 2</p>
          </div>
          <div>
            <label className={labelCls}>Slow Windows (comma-separated)</label>
            <input type="text" className={`${inputCls} font-mono`} value={slowRaw}
              onChange={(e) => setSlowRaw(e.target.value)} placeholder="100, 150, 200, 250"
              disabled={loading} />
            <p className="text-xs text-slate-400 mt-1">1–10 values, each ≥ 2</p>
          </div>
        </div>

        {combCount !== null && (
          <p className="text-xs text-slate-500">
            Grid size:{" "}
            <span className={combCount > 100 ? "text-red-600 font-semibold" : "font-medium"}>
              {fastWindows?.length ?? 0} fast × {slowWindows?.length ?? 0} slow
              = {combCount} combinations per window
            </span>
            {combCount > 100 && " — reduce to ≤ 100."}
          </p>
        )}

        {/* Selection metric + cost + capital */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label className={labelCls}>Selection Metric</label>
            <select className={inputCls} value={selectionMetric} disabled={loading}
              onChange={(e) =>
                setSelectionMetric(e.target.value as SmaWalkForwardRequest["selection_metric"])
              }>
              <option value="sharpe_ratio">Sharpe Ratio</option>
              <option value="cagr">CAGR</option>
              <option value="calmar_ratio">Calmar Ratio</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>Transaction Cost (bps, one-way)</label>
            <input type="number" className={inputCls} value={costBpsStr} min={0} max={9999} step={1}
              onChange={(e) => setCostBpsStr(e.target.value)} disabled={loading} />
          </div>
          <div>
            <label className={labelCls}>Initial Capital ($)</label>
            <input type="number" className={inputCls} value={capitalStr} min={1} step={10000}
              onChange={(e) => setCapitalStr(e.target.value)} disabled={loading} />
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
          {loading ? "Running walk-forward…" : "Run Walk-Forward Optimization"}
        </button>
      </div>

      {/* ── Loading ────────────────────────────────────────────────────────── */}
      {loading && (
        <div className="card p-8 text-center">
          <div className="inline-flex items-center gap-3 text-slate-500">
            <svg className="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span className="text-sm font-medium">Fetching data and running walk-forward…</span>
          </div>
        </div>
      )}

      {/* ── Error ──────────────────────────────────────────────────────────── */}
      {error && !loading && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
          <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-700">Walk-forward failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* ── Results ────────────────────────────────────────────────────────── */}
      {result && !loading && (
        <div className="space-y-6">

          {/* ── Parameter instability warning ─────────────────────────────── */}
          {result.parameter_stability.parameters_unstable && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex gap-3">
              <span className="text-amber-500 mt-0.5 flex-shrink-0 text-lg">⚠</span>
              <div>
                <p className="text-sm font-semibold text-amber-800">
                  Unstable Parameter Selection
                </p>
                <p className="text-sm text-amber-700 mt-0.5">
                  No single (fast, slow) parameter set was chosen in more than 50% of windows.
                  The strategy selected{" "}
                  <span className="font-semibold">
                    {result.parameter_stability.unique_parameter_sets} different configurations
                  </span>{" "}
                  across {result.num_windows} windows. OOS performance may vary significantly
                  depending on which training period is used.
                </p>
              </div>
            </div>
          )}

          {/* ── Summary header ────────────────────────────────────────────── */}
          <div className="card p-6 space-y-4">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="text-lg font-bold text-slate-900">{result.ticker}</h2>
              <span className="text-slate-400 text-sm">
                {result.start_date} → {result.end_date}
              </span>
              <span className="ml-auto text-xs text-slate-400">
                {result.num_windows} windows · {result.transaction_cost_bps} bps ·
                ${result.initial_capital.toLocaleString()}
              </span>
            </div>
            <div className="flex flex-wrap gap-6 text-sm">
              {[
                { label: "Train window", value: `${result.train_window_days} days` },
                { label: "Test window", value: `${result.test_window_days} days` },
                { label: "Step", value: `${result.step_days} days` },
                {
                  label: "Selected by",
                  value: METRIC_LABEL[result.selection_metric] ?? result.selection_metric,
                },
              ].map(({ label, value }) => (
                <div key={label}>
                  <span className="text-slate-500">{label}: </span>
                  <span className="font-semibold text-slate-700">{value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* ── Aggregate OOS metrics ─────────────────────────────────────── */}
          <div className="card p-6 space-y-3">
            <p className="section-title">Aggregate Out-of-Sample Metrics</p>
            <p className="text-xs text-slate-500">
              Computed on the full stitched OOS equity curve — all test windows
              compounded together. Overlapping dates are included once; gaps are
              left out when the step is larger than the test window. Benchmark is
              buy-and-hold for the same stitched OOS dates.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b-2 border-slate-200">
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Metric</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Strategy (OOS)</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Benchmark (B&H)</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: "Sharpe Ratio", strat: fmtRatio(result.aggregate_metrics.sharpe_ratio), bench: fmtRatio(result.aggregate_benchmark_metrics.sharpe_ratio) },
                    { label: "CAGR", strat: fmtPct(result.aggregate_metrics.cagr), bench: fmtPct(result.aggregate_benchmark_metrics.cagr) },
                    { label: "Sortino Ratio", strat: fmtRatio(result.aggregate_metrics.sortino_ratio), bench: fmtRatio(result.aggregate_benchmark_metrics.sortino_ratio) },
                    { label: "Max Drawdown", strat: fmtPct(result.aggregate_metrics.max_drawdown), bench: fmtPct(result.aggregate_benchmark_metrics.max_drawdown) },
                    { label: "Volatility", strat: fmtPct(result.aggregate_metrics.volatility), bench: fmtPct(result.aggregate_benchmark_metrics.volatility) },
                    { label: "Calmar Ratio", strat: fmtRatio(result.aggregate_metrics.calmar_ratio), bench: fmtRatio(result.aggregate_benchmark_metrics.calmar_ratio) },
                    { label: "Win Rate", strat: fmtPct(result.aggregate_metrics.win_rate), bench: fmtPct(result.aggregate_benchmark_metrics.win_rate) },
                  ].map(({ label, strat, bench }) => (
                    <tr key={label} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="px-3 py-1.5 text-sm text-slate-600">{label}</td>
                      <td className="px-3 py-1.5 text-sm text-right tabular-nums font-semibold text-slate-800">{strat}</td>
                      <td className="px-3 py-1.5 text-sm text-right tabular-nums text-slate-500">{bench}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Stitched equity curve ─────────────────────────────────────── */}
          <div className="card p-6">
            <p className="section-title mb-4">Stitched Out-of-Sample Equity Curve</p>
            <EquityCurveChart data={result.stitched_equity_curve} />
          </div>

          {/* ── Parameter stability ───────────────────────────────────────── */}
          <div className="card p-6 space-y-3">
            <p className="section-title">Parameter Stability</p>
            <div className="flex flex-wrap gap-6 text-sm">
              {[
                {
                  label: "Most common fast",
                  value: `${result.parameter_stability.most_common_fast_window} days`,
                },
                {
                  label: "Most common slow",
                  value: `${result.parameter_stability.most_common_slow_window} days`,
                },
                {
                  label: "Most common wins",
                  value: `${result.parameter_stability.most_common_count} / ${result.num_windows} windows`,
                },
                {
                  label: "Unique param sets",
                  value: String(result.parameter_stability.unique_parameter_sets),
                },
              ].map(({ label, value }) => (
                <div key={label} className="text-center min-w-[120px]">
                  <p className="text-xs text-slate-500 mb-0.5">{label}</p>
                  <p className="text-lg font-bold text-blue-600">{value}</p>
                </div>
              ))}
            </div>
            {/* Parameter sequence */}
            <div>
              <p className="text-xs font-medium text-slate-500 mb-2">
                Selected parameters per window
              </p>
              <div className="flex flex-wrap gap-1.5">
                {result.parameter_stability.all_selected_params.map((p, i) => {
                  const isCommon =
                    p.fast_window === result.parameter_stability.most_common_fast_window &&
                    p.slow_window === result.parameter_stability.most_common_slow_window;
                  return (
                    <span
                      key={i}
                      title={`Window ${i}`}
                      className={
                        "inline-block px-2 py-0.5 rounded text-xs font-mono " +
                        (isCommon
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                          : "bg-slate-100 text-slate-600 border border-slate-200")
                      }
                    >
                      {p.fast_window}/{p.slow_window}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ── Per-window results table ──────────────────────────────────── */}
          <div className="card p-6 space-y-3">
            <p className="section-title">
              Walk-Forward Windows{" "}
              <span className="normal-case font-normal text-slate-400 ml-1">
                ({result.num_windows} completed)
              </span>
            </p>
            <p className="text-xs text-slate-500">
              Each row shows one train/test cycle. Params are selected on the train
              period only and then applied to the test period (no future data leakage).
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b-2 border-slate-200">
                    {[
                      "#", "Train period", "Test period",
                      "Fast", "Slow",
                      "Train Sharpe", "Test Sharpe",
                      "Test CAGR", "Test Max DD",
                      "Trades",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-3 py-2 text-right text-xs font-semibold text-slate-600 whitespace-nowrap first:text-left"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.windows.map((w) => (
                    <tr
                      key={w.window_index}
                      className={
                        "border-b border-slate-100 " +
                        (w.window_index % 2 === 0 ? "bg-white" : "bg-slate-50") +
                        " hover:bg-blue-50 transition-colors"
                      }
                    >
                      <td className="px-3 py-1.5 text-sm text-left font-medium text-slate-700">
                        {w.window_index + 1}
                      </td>
                      <td className="px-3 py-1.5 text-xs text-right text-slate-500 whitespace-nowrap">
                        {w.train_start_date.slice(0, 7)} – {w.train_end_date.slice(0, 7)}
                      </td>
                      <td className="px-3 py-1.5 text-xs text-right text-slate-500 whitespace-nowrap">
                        {w.test_start_date.slice(0, 7)} – {w.test_end_date.slice(0, 7)}
                      </td>
                      <td className="px-3 py-1.5 text-sm text-right tabular-nums font-medium text-slate-700">
                        {w.best_fast_window}
                      </td>
                      <td className="px-3 py-1.5 text-sm text-right tabular-nums font-medium text-slate-700">
                        {w.best_slow_window}
                      </td>
                      <td className="px-3 py-1.5 text-sm text-right tabular-nums text-slate-600">
                        {fmtRatio(w.train_metrics.sharpe_ratio)}
                      </td>
                      <td
                        className={
                          "px-3 py-1.5 text-sm text-right tabular-nums font-semibold " +
                          (w.test_metrics.sharpe_ratio >= 0
                            ? "text-emerald-700"
                            : "text-red-600")
                        }
                      >
                        {fmtRatio(w.test_metrics.sharpe_ratio)}
                      </td>
                      <td className="px-3 py-1.5 text-sm text-right tabular-nums text-slate-600">
                        {fmtPct(w.test_metrics.cagr)}
                      </td>
                      <td className="px-3 py-1.5 text-sm text-right tabular-nums text-slate-600">
                        {fmtPct(w.test_metrics.max_drawdown)}
                      </td>
                      <td className="px-3 py-1.5 text-sm text-right tabular-nums text-slate-600">
                        {w.num_trades}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
