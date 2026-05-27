"use client";

/**
 * Self-contained SMA Parameter Sweep panel.
 *
 * Contains the input form, validation, loading state, error display,
 * and the SmaSweepTable results.
 */

import { useState } from "react";
import { BacktestApiError, runSmaSweep } from "@/lib/api";
import type { SmaSweepRequest, SmaSweepResponse } from "@/lib/types";
import SmaSweepTable from "./SmaSweepTable";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PARAMS: SmaSweepRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  fast_windows: [10, 20, 30, 50],
  slow_windows: [50, 100, 150, 200],
  transaction_cost_bps: 10,
  initial_capital: 100_000,
};

const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "GLD", "BTC-USD"];

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
// Styling constants (match BacktestForm palette)
// ---------------------------------------------------------------------------

const inputCls =
  "w-full px-3 py-2 text-sm border border-slate-300 rounded-lg " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 bg-white";

const labelCls = "block text-xs font-medium text-slate-600 mb-1";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SmaSweepPanel() {
  const [ticker, setTicker] = useState(DEFAULT_PARAMS.ticker);
  const [startDate, setStartDate] = useState(DEFAULT_PARAMS.start_date);
  const [endDate, setEndDate] = useState(DEFAULT_PARAMS.end_date);
  const [fastRaw, setFastRaw] = useState(
    windowsToString(DEFAULT_PARAMS.fast_windows),
  );
  const [slowRaw, setSlowRaw] = useState(
    windowsToString(DEFAULT_PARAMS.slow_windows),
  );
  const [costBps, setCostBps] = useState(DEFAULT_PARAMS.transaction_cost_bps);
  const [capital, setCapital] = useState(DEFAULT_PARAMS.initial_capital);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SmaSweepResponse | null>(null);

  // ------------------------------------------------------------------
  // Validation
  // ------------------------------------------------------------------

  const fastWindows = parseWindows(fastRaw);
  const slowWindows = parseWindows(slowRaw);
  const datesOk = startDate < endDate;
  const combsOk =
    fastWindows !== null &&
    slowWindows !== null &&
    fastWindows.length * slowWindows.length <= 100;

  const formInvalid =
    !ticker.trim() ||
    !datesOk ||
    fastWindows === null ||
    slowWindows === null ||
    !combsOk ||
    loading;

  // Human-readable validation messages
  let validationMsg: string | null = null;
  if (!ticker.trim()) {
    validationMsg = "Ticker is required.";
  } else if (!datesOk) {
    validationMsg = "Start date must be before end date.";
  } else if (fastWindows === null) {
    validationMsg =
      "Fast windows must be 1–10 comma-separated integers, each ≥ 2.";
  } else if (slowWindows === null) {
    validationMsg =
      "Slow windows must be 1–10 comma-separated integers, each ≥ 2.";
  } else if (!combsOk) {
    validationMsg = `Too many combinations (${fastWindows.length} × ${slowWindows.length} = ${fastWindows.length * slowWindows.length}).  Maximum is 100.`;
  }

  // ------------------------------------------------------------------
  // Submit
  // ------------------------------------------------------------------

  async function handleRun() {
    if (formInvalid || fastWindows === null || slowWindows === null) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runSmaSweep({
        ticker: ticker.trim().toUpperCase(),
        start_date: startDate,
        end_date: endDate,
        fast_windows: fastWindows,
        slow_windows: slowWindows,
        transaction_cost_bps: costBps,
        initial_capital: capital,
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

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  const combCount =
    fastWindows !== null && slowWindows !== null
      ? fastWindows.length * slowWindows.length
      : null;

  return (
    <div className="space-y-6">
      {/* ── Form card ─────────────────────────────────────────────── */}
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
            {/* Quick-picks */}
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
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Start Date</label>
            <input
              type="date"
              className={inputCls}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              disabled={loading}
            />
          </div>
          <div>
            <label className={labelCls}>End Date</label>
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
        <div className="grid grid-cols-2 gap-4">
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
            <p className="text-xs text-slate-400 mt-1">
              1–10 values, each ≥ 2 (e.g. 10, 20, 30, 50)
            </p>
          </div>
          <div>
            <label className={labelCls}>Slow Windows (days, comma-separated)</label>
            <input
              type="text"
              className={`${inputCls} font-mono`}
              value={slowRaw}
              onChange={(e) => setSlowRaw(e.target.value)}
              placeholder="50, 100, 150, 200"
              disabled={loading}
            />
            <p className="text-xs text-slate-400 mt-1">
              1–10 values, each ≥ 2 (e.g. 50, 100, 150, 200)
            </p>
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

        {/* Cost / capital */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Transaction Cost (bps, one-way)</label>
            <input
              type="number"
              className={inputCls}
              value={costBps}
              min={0}
              step={1}
              onChange={(e) => setCostBps(parseFloat(e.target.value) || 0)}
              disabled={loading}
            />
          </div>
          <div>
            <label className={labelCls}>Initial Capital ($)</label>
            <input
              type="number"
              className={inputCls}
              value={capital}
              min={1}
              step={10000}
              onChange={(e) => setCapital(parseFloat(e.target.value) || 100_000)}
              disabled={loading}
            />
          </div>
        </div>

        {/* Validation message */}
        {validationMsg && (
          <p className="text-xs text-red-600 font-medium">{validationMsg}</p>
        )}

        {/* Run button */}
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
          {loading ? "Running sweep…" : "Run Parameter Sweep"}
        </button>
      </div>

      {/* ── Loading ──────────────────────────────────────────────── */}
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
              Fetching data and running {combCount ?? "…"} backtests…
            </span>
          </div>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────── */}
      {error && !loading && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
          <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-700">Sweep failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────── */}
      {result && !loading && (
        <div className="card p-6 space-y-4">
          {/* Summary header */}
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="text-lg font-bold text-slate-900">{result.ticker}</h2>
            <span className="text-slate-400 text-sm">
              {result.start_date} → {result.end_date}
            </span>
            <span className="ml-auto text-xs text-slate-400">
              {result.num_combinations} valid combinations ·{" "}
              {result.transaction_cost_bps} bps · $
              {result.initial_capital.toLocaleString()}
            </span>
          </div>

          {/* Legend */}
          <p className="text-xs text-slate-500">
            Click any column header to sort. The{" "}
            <span className="font-semibold text-slate-700">Sharpe</span> column
            is heat-coloured: amber = lowest, green = highest.
          </p>

          <SmaSweepTable rows={result.results} />
        </div>
      )}
    </div>
  );
}
