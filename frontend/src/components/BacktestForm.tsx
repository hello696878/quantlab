"use client";

import type { BacktestRequest } from "@/lib/types";

// Quick-pick tickers shown as pill buttons
const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "GLD", "BTC-USD"];

interface Props {
  params: BacktestRequest;
  onChange: (p: BacktestRequest) => void;
  onSubmit: () => void;
  loading: boolean;
}

// Shared label + input wrapper
function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">
        {label}
        {hint && (
          <span className="ml-1 normal-case font-normal text-slate-400">
            {hint}
          </span>
        )}
      </label>
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

export default function BacktestForm({ params, onChange, onSubmit, loading }: Props) {
  function set<K extends keyof BacktestRequest>(key: K, value: BacktestRequest[K]) {
    onChange({ ...params, [key]: value });
  }

  // Inline validation
  const fastGeSlow = params.fast_window >= params.slow_window;
  const dateInvalid = params.start_date >= params.end_date;
  const canSubmit =
    !loading &&
    params.ticker.trim().length > 0 &&
    !fastGeSlow &&
    !dateInvalid;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="font-semibold text-slate-800">Parameters</h2>
        <span className="text-xs text-slate-400">
          Data via Yahoo Finance · Adjusted close prices
        </span>
      </div>

      {/* ── Ticker row ───────────────────────────────────────────────── */}
      <div className="mb-5">
        <Field label="Ticker symbol">
          <div className="flex gap-2 flex-wrap">
            <input
              type="text"
              className={`${inputCls} w-32 uppercase`}
              value={params.ticker}
              onChange={(e) => set("ticker", e.target.value.toUpperCase())}
              placeholder="SPY"
              disabled={loading}
              maxLength={12}
            />
            <div className="flex gap-1 flex-wrap">
              {POPULAR_TICKERS.map((t) => (
                <button
                  key={t}
                  type="button"
                  disabled={loading}
                  onClick={() => set("ticker", t)}
                  className={
                    "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors " +
                    (params.ticker === t
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-slate-600 border-slate-300 hover:border-blue-400 hover:text-blue-600")
                  }
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </Field>
      </div>

      {/* ── Main grid ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-5">
        <div className="col-span-2 sm:col-span-1 lg:col-span-1">
          <Field label="Start date">
            <input
              type="date"
              className={inputCls}
              value={params.start_date}
              onChange={(e) => set("start_date", e.target.value)}
              disabled={loading}
            />
          </Field>
        </div>
        <div className="col-span-2 sm:col-span-1 lg:col-span-1">
          <Field label="End date">
            <input
              type="date"
              className={inputCls}
              value={params.end_date}
              onChange={(e) => set("end_date", e.target.value)}
              disabled={loading}
            />
          </Field>
        </div>
        <Field label="Fast SMA" hint="days">
          <input
            type="number"
            className={inputCls}
            value={params.fast_window}
            min={2}
            max={params.slow_window - 1}
            step={1}
            onChange={(e) => set("fast_window", parseInt(e.target.value, 10) || 2)}
            disabled={loading}
          />
        </Field>
        <Field label="Slow SMA" hint="days">
          <input
            type="number"
            className={inputCls}
            value={params.slow_window}
            min={params.fast_window + 1}
            step={1}
            onChange={(e) => set("slow_window", parseInt(e.target.value, 10) || 2)}
            disabled={loading}
          />
        </Field>
        <Field label="Cost" hint="bps">
          <input
            type="number"
            className={inputCls}
            value={params.transaction_cost_bps}
            min={0}
            max={200}
            step={1}
            onChange={(e) =>
              set("transaction_cost_bps", parseFloat(e.target.value) || 0)
            }
            disabled={loading}
          />
        </Field>
        <Field label="Capital" hint="USD">
          <input
            type="number"
            className={inputCls}
            value={params.initial_capital}
            min={1}
            step={1000}
            onChange={(e) =>
              set("initial_capital", parseFloat(e.target.value) || 100_000)
            }
            disabled={loading}
          />
        </Field>
      </div>

      {/* ── Validation messages ───────────────────────────────────────── */}
      {(fastGeSlow || dateInvalid) && (
        <div className="mb-4 space-y-1">
          {fastGeSlow && (
            <p className="text-xs text-red-600">
              ⚠ Fast SMA window must be less than slow SMA window.
            </p>
          )}
          {dateInvalid && (
            <p className="text-xs text-red-600">
              ⚠ Start date must be before end date.
            </p>
          )}
        </div>
      )}

      {/* ── Submit ────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit}
          className={
            "flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold " +
            "transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 " +
            (canSubmit
              ? "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500 shadow-sm"
              : "bg-slate-200 text-slate-400 cursor-not-allowed")
          }
        >
          {loading ? (
            <>
              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              Running…
            </>
          ) : (
            "Run Backtest"
          )}
        </button>
        <span className="text-xs text-slate-400">
          One-way cost · signal shifted 1 day · adjusted close prices
        </span>
      </div>
    </div>
  );
}
