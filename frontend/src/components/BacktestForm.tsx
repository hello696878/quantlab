"use client";

import type {
  BacktestRequest,
  RsiBacktestRequest,
  StrategyType,
} from "@/lib/types";

// Quick-pick tickers
const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "GLD", "BTC-USD"];

interface Props {
  strategy: StrategyType;
  onStrategyChange: (s: StrategyType) => void;
  smaParams: BacktestRequest;
  onSmaParamsChange: (p: BacktestRequest) => void;
  rsiParams: RsiBacktestRequest;
  onRsiParamsChange: (p: RsiBacktestRequest) => void;
  onSubmit: () => void;
  loading: boolean;
}

// ---------------------------------------------------------------------------
// Small reusable pieces
// ---------------------------------------------------------------------------

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
          <span className="ml-1 normal-case font-normal text-slate-400">{hint}</span>
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

// ---------------------------------------------------------------------------
// Strategy tab definitions
// ---------------------------------------------------------------------------

const STRATEGIES: { id: StrategyType; label: string; description: string }[] = [
  {
    id: "sma_crossover",
    label: "SMA Crossover",
    description:
      "Long when fast SMA > slow SMA. Classic trend-following approach.",
  },
  {
    id: "rsi_mean_reversion",
    label: "RSI Mean Reversion",
    description:
      "Long when RSI drops below an oversold level; exits above recovery.",
  },
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function BacktestForm({
  strategy,
  onStrategyChange,
  smaParams,
  onSmaParamsChange,
  rsiParams,
  onRsiParamsChange,
  onSubmit,
  loading,
}: Props) {
  // Active params (common fields) come from whichever strategy is selected.
  const active = strategy === "sma_crossover" ? smaParams : rsiParams;

  function setCommon<K extends keyof typeof active>(
    key: K,
    value: (typeof active)[K],
  ) {
    // Update both request objects so common fields stay in sync when switching.
    onSmaParamsChange({ ...smaParams, [key]: value } as BacktestRequest);
    onRsiParamsChange({ ...rsiParams, [key]: value } as RsiBacktestRequest);
  }

  function setSma<K extends keyof BacktestRequest>(
    key: K,
    value: BacktestRequest[K],
  ) {
    onSmaParamsChange({ ...smaParams, [key]: value });
  }

  function setRsi<K extends keyof RsiBacktestRequest>(
    key: K,
    value: RsiBacktestRequest[K],
  ) {
    onRsiParamsChange({ ...rsiParams, [key]: value });
  }

  // Validation
  const dateInvalid = active.start_date >= active.end_date;
  const smaInvalid =
    strategy === "sma_crossover" &&
    smaParams.fast_window >= smaParams.slow_window;
  const rsiInvalid =
    strategy === "rsi_mean_reversion" &&
    rsiParams.oversold_threshold >= rsiParams.exit_threshold;

  const canSubmit =
    !loading &&
    active.ticker.trim().length > 0 &&
    !dateInvalid &&
    !smaInvalid &&
    !rsiInvalid;

  return (
    <div className="card overflow-hidden">
      {/* ── Strategy tab bar ─────────────────────────────────────────── */}
      <div className="flex border-b border-slate-200 bg-slate-50">
        {STRATEGIES.map((s) => (
          <button
            key={s.id}
            type="button"
            disabled={loading}
            onClick={() => onStrategyChange(s.id)}
            className={
              "flex-1 px-5 py-3.5 text-sm font-medium transition-colors " +
              "focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 " +
              (strategy === s.id
                ? "bg-white text-blue-700 border-b-2 border-blue-600 shadow-sm"
                : "text-slate-500 hover:text-slate-800 hover:bg-white/60")
            }
          >
            <span className="block">{s.label}</span>
            <span className="hidden sm:block text-xs font-normal text-slate-400 mt-0.5 leading-tight">
              {s.description}
            </span>
          </button>
        ))}
      </div>

      <div className="p-6">
        {/* ── Ticker ───────────────────────────────────────────────────── */}
        <div className="mb-5">
          <Field label="Ticker symbol">
            <div className="flex gap-2 flex-wrap">
              <input
                type="text"
                className={`${inputCls} w-32 uppercase`}
                value={active.ticker}
                onChange={(e) => setCommon("ticker", e.target.value.toUpperCase())}
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
                    onClick={() => setCommon("ticker", t)}
                    className={
                      "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors " +
                      (active.ticker === t
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

        {/* ── Common fields ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
          <Field label="Start date">
            <input
              type="date"
              className={inputCls}
              value={active.start_date}
              onChange={(e) => setCommon("start_date", e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="End date">
            <input
              type="date"
              className={inputCls}
              value={active.end_date}
              onChange={(e) => setCommon("end_date", e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="Cost" hint="bps">
            <input
              type="number"
              className={inputCls}
              value={active.transaction_cost_bps}
              min={0}
              max={200}
              step={1}
              onChange={(e) =>
                setCommon("transaction_cost_bps", parseFloat(e.target.value) || 0)
              }
              disabled={loading}
            />
          </Field>
          <Field label="Capital" hint="USD">
            <input
              type="number"
              className={inputCls}
              value={active.initial_capital}
              min={1}
              step={1000}
              onChange={(e) =>
                setCommon("initial_capital", parseFloat(e.target.value) || 100_000)
              }
              disabled={loading}
            />
          </Field>
        </div>

        {/* ── Strategy-specific fields ───────────────────────────────────── */}
        <div className="mb-5 p-4 rounded-lg bg-blue-50/60 border border-blue-100">
          {strategy === "sma_crossover" ? (
            <div className="grid grid-cols-2 gap-4">
              <Field label="Fast SMA" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={smaParams.fast_window}
                  min={2}
                  max={smaParams.slow_window - 1}
                  step={1}
                  onChange={(e) =>
                    setSma("fast_window", parseInt(e.target.value, 10) || 2)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Slow SMA" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={smaParams.slow_window}
                  min={smaParams.fast_window + 1}
                  step={1}
                  onChange={(e) =>
                    setSma("slow_window", parseInt(e.target.value, 10) || 2)
                  }
                  disabled={loading}
                />
              </Field>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              <Field label="RSI window" hint="days">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiParams.rsi_window}
                  min={2}
                  max={100}
                  step={1}
                  onChange={(e) =>
                    setRsi("rsi_window", parseInt(e.target.value, 10) || 14)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Oversold" hint="enter <">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiParams.oversold_threshold}
                  min={1}
                  max={rsiParams.exit_threshold - 1}
                  step={1}
                  onChange={(e) =>
                    setRsi("oversold_threshold", parseFloat(e.target.value) || 30)
                  }
                  disabled={loading}
                />
              </Field>
              <Field label="Exit" hint="exit >">
                <input
                  type="number"
                  className={inputCls}
                  value={rsiParams.exit_threshold}
                  min={rsiParams.oversold_threshold + 1}
                  max={100}
                  step={1}
                  onChange={(e) =>
                    setRsi("exit_threshold", parseFloat(e.target.value) || 50)
                  }
                  disabled={loading}
                />
              </Field>
            </div>
          )}
        </div>

        {/* ── Inline validation ─────────────────────────────────────────── */}
        {(dateInvalid || smaInvalid || rsiInvalid) && (
          <div className="mb-4 space-y-1">
            {dateInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Start date must be before end date.
              </p>
            )}
            {smaInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Fast SMA window must be less than slow SMA window.
              </p>
            )}
            {rsiInvalid && (
              <p className="text-xs text-red-600">
                ⚠ Oversold threshold must be less than exit threshold.
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
    </div>
  );
}
