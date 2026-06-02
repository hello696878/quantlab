"use client";

import { useMemo, useRef, useState } from "react";
import { runCsvBacktest } from "@/lib/api";
import type { BacktestResponse } from "@/lib/types";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";
import ExportReportButton from "@/components/ExportReportButton";
import { buildBacktestReport } from "@/lib/reportExport";

// ---------------------------------------------------------------------------
// Strategy + field configuration (single-asset strategies only — no pairs)
// ---------------------------------------------------------------------------

type CsvStrategy =
  | "sma_crossover"
  | "rsi_mean_reversion"
  | "bollinger_band"
  | "momentum"
  | "volatility_breakout";

const STRATEGIES: { id: CsvStrategy; label: string; description: string }[] = [
  { id: "sma_crossover", label: "SMA Crossover", description: "Long when fast SMA > slow SMA." },
  { id: "rsi_mean_reversion", label: "RSI Mean Reversion", description: "Buy oversold, exit on recovery." },
  { id: "bollinger_band", label: "Bollinger Band", description: "Buy below lower band; exit at band." },
  { id: "momentum", label: "Momentum", description: "Long when trailing return is positive." },
  { id: "volatility_breakout", label: "Vol Breakout", description: "Enter above the prior range." },
];

interface FieldSpec {
  key: string;
  label: string;
  hint?: string;
  kind: "int" | "float" | "select";
  options?: string[];
}

const FIELD_SPECS: Record<CsvStrategy, FieldSpec[]> = {
  sma_crossover: [
    { key: "fast_window", label: "Fast Window", hint: "days", kind: "int" },
    { key: "slow_window", label: "Slow Window", hint: "days", kind: "int" },
  ],
  rsi_mean_reversion: [
    { key: "rsi_window", label: "RSI Window", hint: "days", kind: "int" },
    { key: "oversold_threshold", label: "Oversold", kind: "float" },
    { key: "exit_threshold", label: "Exit Level", kind: "float" },
  ],
  bollinger_band: [
    { key: "bb_window", label: "BB Window", hint: "days", kind: "int" },
    { key: "num_std", label: "Std Devs", kind: "float" },
    { key: "exit_band", label: "Exit Band", kind: "select", options: ["middle", "upper"] },
  ],
  momentum: [
    { key: "momentum_window", label: "Momentum Window", hint: "days", kind: "int" },
    { key: "entry_threshold", label: "Entry Threshold", hint: "decimal", kind: "float" },
    { key: "exit_threshold", label: "Exit Threshold", hint: "decimal", kind: "float" },
  ],
  volatility_breakout: [
    { key: "lookback_window", label: "Lookback", hint: "days", kind: "int" },
    { key: "breakout_multiplier", label: "Breakout ×", kind: "float" },
    { key: "exit_window", label: "Exit Window", hint: "days", kind: "int" },
  ],
};

const DEFAULTS: Record<CsvStrategy, Record<string, string>> = {
  sma_crossover: { fast_window: "50", slow_window: "200" },
  rsi_mean_reversion: { rsi_window: "14", oversold_threshold: "30", exit_threshold: "50" },
  bollinger_band: { bb_window: "20", num_std: "2", exit_band: "middle" },
  momentum: { momentum_window: "126", entry_threshold: "0", exit_threshold: "0" },
  volatility_breakout: { lookback_window: "20", breakout_multiplier: "1", exit_window: "10" },
};

const STRATEGY_LABELS: Record<string, string> = {
  sma_crossover: "SMA Crossover",
  rsi_mean_reversion: "RSI Mean Reversion",
  bollinger_band: "Bollinger Band",
  momentum: "Momentum",
  volatility_breakout: "Volatility Breakout",
};

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

// ---------------------------------------------------------------------------
// Small pieces
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

/** Parse a numeric string; return null when empty / not finite. */
function parseNum(raw: string, kind: "int" | "float"): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const v = Number(trimmed);
  if (!Number.isFinite(v)) return null;
  if (kind === "int" && !Number.isInteger(v)) return null;
  return v;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CsvBacktestPanel() {
  const [strategy, setStrategy] = useState<CsvStrategy>("sma_crossover");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // Strategy params as raw strings (so fields can be cleared / partially typed).
  const [params, setParams] = useState<Record<string, string>>(
    DEFAULTS["sma_crossover"],
  );
  const [costStr, setCostStr] = useState("10");
  const [capitalStr, setCapitalStr] = useState("100000");

  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const specs = FIELD_SPECS[strategy];

  function selectStrategy(next: CsvStrategy) {
    setStrategy(next);
    setParams(DEFAULTS[next]);
    setResult(null);
    setError(null);
  }

  function setParam(key: string, value: string) {
    setParams((p) => ({ ...p, [key]: value }));
  }

  function pickFile(f: File | null) {
    setFile(f);
    setResult(null);
    setError(null);
  }

  // ── Validation ──────────────────────────────────────────────────────────
  const { canRun, validationMsg } = useMemo(() => {
    if (!file) return { canRun: false, validationMsg: "Upload a CSV file to begin." };

    for (const spec of specs) {
      if (spec.kind === "select") continue;
      const v = parseNum(params[spec.key] ?? "", spec.kind);
      if (v === null) {
        return { canRun: false, validationMsg: `${spec.label} must be a valid number.` };
      }
    }
    const cost = parseNum(costStr, "float");
    const capital = parseNum(capitalStr, "float");
    if (cost === null || cost < 0) {
      return { canRun: false, validationMsg: "Transaction cost must be ≥ 0 bps." };
    }
    if (capital === null || capital <= 0) {
      return { canRun: false, validationMsg: "Initial capital must be greater than 0." };
    }

    // Cheap cross-field checks (the backend re-validates authoritatively).
    if (strategy === "sma_crossover") {
      const fast = parseNum(params.fast_window, "int")!;
      const slow = parseNum(params.slow_window, "int")!;
      if (fast >= slow) {
        return { canRun: false, validationMsg: "Fast window must be less than slow window." };
      }
    }
    if (strategy === "rsi_mean_reversion") {
      const ob = parseNum(params.oversold_threshold, "float")!;
      const ex = parseNum(params.exit_threshold, "float")!;
      if (ob >= ex) {
        return { canRun: false, validationMsg: "Oversold must be less than the exit level." };
      }
    }
    return { canRun: true, validationMsg: null as string | null };
  }, [file, specs, params, costStr, capitalStr, strategy]);

  // ── Run ─────────────────────────────────────────────────────────────────
  async function handleRun() {
    if (!file || !canRun || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const payload: Record<string, unknown> = {
      transaction_cost_bps: parseNum(costStr, "float"),
      initial_capital: parseNum(capitalStr, "float"),
    };
    for (const spec of specs) {
      payload[spec.key] =
        spec.kind === "select" ? params[spec.key] : parseNum(params[spec.key], spec.kind);
    }

    try {
      const data = await runCsvBacktest(file, strategy, payload);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "CSV backtest failed.");
    } finally {
      setLoading(false);
    }
  }

  const resultLabel = result ? STRATEGY_LABELS[result.strategy] ?? result.strategy : "";

  return (
    <div className="space-y-6">
      {/* ── Upload + parameters card ─────────────────────────────────────── */}
      <div className="card p-6 space-y-5">
        {/* File dropzone */}
        <Field label="Price CSV" hint="date + close columns required">
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) pickFile(f);
            }}
            className={
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors " +
              (dragOver
                ? "border-blue-500 bg-blue-50"
                : "border-slate-300 hover:border-slate-400")
            }
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            />
            <svg
              width="26"
              height="26"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-slate-400"
            >
              <path d="M12 16V4m0 0L7 9m5-5 5 5M5 20h14" />
            </svg>
            {file ? (
              <span className="text-sm font-medium text-slate-800">{file.name}</span>
            ) : (
              <span className="text-sm text-slate-500">
                Drag &amp; drop a CSV here, or click to browse
              </span>
            )}
            <span className="text-xs text-slate-400">
              Accepted date: date / datetime / timestamp · close: close / adj_close
            </span>
          </label>
        </Field>

        {/* Strategy selector */}
        <Field label="Strategy">
          <div className="flex flex-wrap gap-2">
            {STRATEGIES.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => selectStrategy(s.id)}
                title={s.description}
                className={
                  "px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors " +
                  (strategy === s.id
                    ? "bg-blue-600 text-white border-blue-600"
                    : "border-slate-300 text-slate-600 hover:border-slate-400")
                }
              >
                {s.label}
              </button>
            ))}
          </div>
        </Field>

        {/* Strategy-specific params */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {specs.map((spec) => (
            <Field key={spec.key} label={spec.label} hint={spec.hint}>
              {spec.kind === "select" ? (
                <select
                  className={inputCls}
                  value={params[spec.key] ?? ""}
                  onChange={(e) => setParam(spec.key, e.target.value)}
                  disabled={loading}
                >
                  {spec.options!.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="number"
                  className={inputCls}
                  value={params[spec.key] ?? ""}
                  onChange={(e) => setParam(spec.key, e.target.value)}
                  disabled={loading}
                />
              )}
            </Field>
          ))}
        </div>

        {/* Common params */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Transaction Cost" hint="bps">
            <input
              type="number"
              className={inputCls}
              value={costStr}
              onChange={(e) => setCostStr(e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="Initial Capital" hint="USD">
            <input
              type="number"
              className={inputCls}
              value={capitalStr}
              onChange={(e) => setCapitalStr(e.target.value)}
              disabled={loading}
            />
          </Field>
        </div>

        {/* Run */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRun}
            disabled={!canRun || loading}
            className="px-5 py-2 rounded-lg text-sm font-semibold text-white bg-blue-600
                       hover:bg-blue-700 transition-colors disabled:opacity-50
                       disabled:cursor-not-allowed"
          >
            {loading ? "Running…" : "Run CSV Backtest"}
          </button>
          {validationMsg && !loading && (
            <span className="text-xs text-slate-400">{validationMsg}</span>
          )}
        </div>
      </div>

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {error && !loading && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
          <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-700">CSV backtest failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────────── */}
      {result && !loading && (
        <>
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-lg font-bold text-slate-900">{result.ticker}</h2>
            <span className="text-slate-400 text-sm">
              {result.start_date} → {result.end_date}
            </span>
            <span className="text-xs text-slate-400">
              {resultLabel} · {result.transaction_cost_bps} bps · {result.num_trades}{" "}
              trade events
            </span>
            <span className="ml-auto">
              <ExportReportButton
                getReport={() =>
                  buildBacktestReport(result, {
                    analysisType: "CSV Upload Backtest",
                    dataSource: "csv",
                  })
                }
              />
            </span>
          </div>

          <MetricsGrid
            strategy={result.strategy_metrics}
            benchmark={result.benchmark_metrics}
            ticker={result.ticker}
            strategyLabel={resultLabel}
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
    </div>
  );
}
