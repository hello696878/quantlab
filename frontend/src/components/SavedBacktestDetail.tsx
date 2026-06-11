"use client";

import { useEffect, useState } from "react";
import { classifyApiError, getSavedBacktest } from "@/lib/api";
import type {
  BenchmarkAnalytics,
  DataQuality,
  EquityPoint,
  Reproducibility,
  RobustnessResult,
  SavedBacktestFull,
  TradeRecord,
} from "@/lib/types";
import { buildBenchmarkChartSeries } from "@/lib/benchmarkCharts";
import { copyText } from "@/components/ReproducibilityCard";
import RobustnessLabCard from "@/components/RobustnessLabCard";
import { notifyBackendOffline } from "@/lib/toast";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import DataQualityCard from "@/components/DataQualityCard";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";
import ExportReportButton from "@/components/ExportReportButton";
import { buildSavedBacktestReport } from "@/lib/reportExport";
import { fmtPct, fmtRatio, fmtDollar } from "@/lib/format";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STRATEGY_LABELS: Record<string, string> = {
  sma_crossover: "SMA Crossover",
  rsi_mean_reversion: "RSI Mean Reversion",
  bollinger_band: "Bollinger Band",
  momentum: "Momentum",
  volatility_breakout: "Volatility Breakout",
  pairs: "Pairs Trading",
};

function stratLabel(s: string): string {
  return STRATEGY_LABELS[s] ?? s;
}

function fmtSavedDate(iso: string): string {
  return iso.replace("T", " ").slice(0, 16) + " UTC";
}

function formatParamValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "object") {
    const record = value as { label?: unknown };
    if (typeof record.label === "string") return record.label;
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function isDataQuality(value: unknown): value is DataQuality {
  if (!value || typeof value !== "object") return false;
  const q = value as Partial<DataQuality>;
  return (
    typeof q.provider === "string" &&
    typeof q.ticker === "string" &&
    typeof q.requested_start_date === "string" &&
    typeof q.requested_end_date === "string" &&
    typeof q.row_count === "number" &&
    typeof q.missing_value_count === "number" &&
    typeof q.duplicate_date_count === "number" &&
    typeof q.inferred_frequency === "string" &&
    typeof q.calendar_gap_count === "number" &&
    typeof q.price_column_used === "string" &&
    typeof q.adjusted === "boolean" &&
    Array.isArray(q.warnings)
  );
}

interface MetricRowProps {
  label: string;
  value: number | null | undefined;
  formatter?: (v: number) => string;
  positiveGood?: boolean;
}

function MetricRow({
  label,
  value,
  formatter = (v) => String(v),
  positiveGood = true,
}: MetricRowProps) {
  if (value == null) return null;
  const color =
    value > 0
      ? positiveGood
        ? "text-green-700"
        : "text-red-700"
      : value < 0
        ? positiveGood
          ? "text-red-700"
          : "text-green-700"
        : "text-slate-600";

  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-slate-50 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`text-sm font-mono font-medium ${color}`}>
        {formatter(value)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface SavedBacktestDetailProps {
  id: number;
  onBack: () => void;
  onGoHome?: () => void;
}

export default function SavedBacktestDetail({
  id,
  onBack,
  onGoHome,
}: SavedBacktestDetailProps) {
  const [record, setRecord] = useState<SavedBacktestFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRecord(null);

    getSavedBacktest(id)
      .then((data) => {
        if (!cancelled) setRecord(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
        if (classifyApiError(err).backendUnavailable) {
          notifyBackendOffline({ onRetry: () => setRetryTick((k) => k + 1) });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id, retryTick]);

  // ── States ──────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-4 w-28" />
        <div className="card space-y-3 p-5">
          <Skeleton className="h-5 w-2/5" />
          <Skeleton className="h-3 w-3/5" />
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (error) {
    const cls = classifyApiError(error);
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-blue-600 hover:underline"
        >
          ← Back to list
        </button>
        {cls.backendUnavailable ? (
          <OfflineState
            detail={cls.message}
            onRetry={() => setRetryTick((k) => k + 1)}
            onGoHome={onGoHome}
          />
        ) : (
          <ErrorState
            title="Couldn’t load this backtest"
            message={cls.message}
            onRetry={() => setRetryTick((k) => k + 1)}
          />
        )}
      </div>
    );
  }

  if (!record) return null;

  const m = record.metrics as Record<string, number>;
  const equityCurve = record.equity_curve as EquityPoint[];
  const trades = record.trades as TradeRecord[];

  // Strategy params as key-value pairs for display.  data_quality and
  // benchmark_analytics are nested objects — summarized as compact pills, not
  // raw JSON.
  const paramEntries = Object.entries(record.params).filter(
    ([k, v]) =>
      v != null &&
      k !== "data_quality" &&
      k !== "data_provider" &&
      k !== "benchmark_analytics" &&
      k !== "reproducibility" &&
      k !== "robustness",
  );
  const savedQuality = isDataQuality(record.params?.data_quality)
    ? record.params.data_quality
    : undefined;
  const savedProvider =
    typeof record.params?.data_provider === "string"
      ? record.params.data_provider
      : savedQuality?.provider;
  const savedBenchmarkRaw = record.params?.benchmark_analytics;
  const savedBenchmarkBlock =
    savedBenchmarkRaw &&
    typeof savedBenchmarkRaw === "object" &&
    typeof (savedBenchmarkRaw as { mode?: unknown }).mode === "string"
      ? (savedBenchmarkRaw as BenchmarkAnalytics)
      : undefined;
  const savedBenchmarkName = savedBenchmarkBlock?.display_name;
  const savedReproRaw = record.params?.reproducibility;
  const savedRepro =
    savedReproRaw &&
    typeof savedReproRaw === "object" &&
    typeof (savedReproRaw as { config_hash?: unknown }).config_hash === "string"
      ? (savedReproRaw as Reproducibility)
      : undefined;
  const savedRobustnessRaw = record.params?.robustness;
  const savedRobustness =
    savedRobustnessRaw &&
    typeof savedRobustnessRaw === "object" &&
    typeof (savedRobustnessRaw as { n_simulations?: unknown }).n_simulations ===
      "number"
      ? (savedRobustnessRaw as RobustnessResult)
      : undefined;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <button
        type="button"
        onClick={onBack}
        className="text-sm text-blue-600 hover:underline"
      >
        ← Back to saved backtests
      </button>

      {/* Header */}
      <div className="card p-5">
        <div className="flex flex-wrap items-start gap-4 justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{record.name}</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              {record.ticker.toUpperCase()} · {stratLabel(record.strategy)} ·{" "}
              {record.start_date} → {record.end_date}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="text-xs text-slate-400">
              Saved {fmtSavedDate(record.created_at)}
            </div>
            <ExportReportButton
              getReport={(tpl) => buildSavedBacktestReport(record, tpl)}
            />
          </div>
        </div>

        {/* Params pill row */}
        {paramEntries.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {paramEntries.map(([k, v]) => (
              <span
                key={k}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                           bg-slate-100 text-slate-600 text-xs"
              >
                <span className="text-slate-400">{k}:</span>
                <span className="font-mono font-medium">{formatParamValue(v)}</span>
              </span>
            ))}
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                         bg-slate-100 text-slate-600 text-xs"
            >
              <span className="text-slate-400">capital:</span>
              <span className="font-mono font-medium">
                {fmtDollar(record.initial_capital)}
              </span>
            </span>
            {savedQuality && typeof savedQuality.row_count === "number" && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                           bg-slate-100 text-slate-600 text-xs"
                title={
                  savedQuality.actual_start_date && savedQuality.actual_end_date
                    ? `Actual data range ${savedQuality.actual_start_date} → ${savedQuality.actual_end_date}`
                    : undefined
                }
              >
                <span className="text-slate-400">data:</span>
                <span className="font-mono font-medium">
                  {savedQuality.row_count.toLocaleString("en-US")} rows
                </span>
              </span>
            )}
            {savedBenchmarkName && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                           bg-slate-100 text-slate-600 text-xs"
              >
                <span className="text-slate-400">benchmark:</span>
                <span className="font-mono font-medium">{savedBenchmarkName}</span>
              </span>
            )}
            {savedRepro ? (
              <button
                type="button"
                onClick={() =>
                  copyText(savedRepro.config_hash_full, "Config hash copied")
                }
                title={`${savedRepro.config_hash_full} — click to copy`}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                           bg-slate-100 text-slate-600 text-xs transition-colors
                           hover:bg-slate-200"
              >
                <span className="text-slate-400">config:</span>
                <span className="font-mono font-medium">{savedRepro.config_hash}</span>
              </button>
            ) : (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                           bg-slate-100 text-slate-400 text-xs"
                title="Config hash unavailable for older saved backtests."
              >
                config: —
              </span>
            )}
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                         bg-slate-100 text-slate-600 text-xs"
            >
              <span className="text-slate-400">cost:</span>
              <span className="font-mono font-medium">
                {record.transaction_cost_bps} bps
              </span>
            </span>
          </div>
        )}

        {/* Notes */}
        {record.notes && (
          <div className="mt-3 text-sm text-slate-600 bg-amber-50 rounded-lg px-3 py-2 border border-amber-100">
            {record.notes}
          </div>
        )}
      </div>

      {savedQuality && (
        <DataQualityCard provider={savedProvider} quality={savedQuality} />
      )}

      {/* Metrics */}
      {Object.keys(m).length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-3">Performance Metrics</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6">
            <div>
              <MetricRow
                label="Total Return"
                value={m.total_return}
                formatter={(v) => fmtPct(v, 1)}
              />
              <MetricRow
                label="CAGR"
                value={m.cagr}
                formatter={(v) => fmtPct(v, 1)}
              />
              <MetricRow
                label="Volatility"
                value={m.volatility}
                formatter={(v) => fmtPct(v, 1)}
                positiveGood={false}
              />
            </div>
            <div>
              <MetricRow
                label="Sharpe Ratio"
                value={m.sharpe_ratio}
                formatter={(v) => fmtRatio(v, 2)}
              />
              <MetricRow
                label="Sortino Ratio"
                value={m.sortino_ratio}
                formatter={(v) => fmtRatio(v, 2)}
              />
              <MetricRow
                label="Calmar Ratio"
                value={m.calmar_ratio}
                formatter={(v) => fmtRatio(v, 2)}
              />
            </div>
            <div>
              <MetricRow
                label="Max Drawdown"
                value={m.max_drawdown}
                formatter={(v) => fmtPct(v, 1)}
                positiveGood={false}
              />
              <MetricRow
                label="Win Rate"
                value={m.win_rate}
                formatter={(v) => fmtPct(v, 1)}
              />
              <MetricRow
                label="Trading Days"
                value={m.num_days}
                formatter={(v) => String(Math.round(v))}
                positiveGood={true}
              />
            </div>
          </div>
        </div>
      )}

      {/* Equity curve (+ benchmark overlay when this record saved a benchmark
          block; old records without one keep the legacy rendering) */}
      {savedBenchmarkBlock ? (
        (() => {
          const bench = buildBenchmarkChartSeries(equityCurve, savedBenchmarkBlock);
          return (
            <>
              <div className="card p-6">
                <p className="section-title mb-4">
                  Equity Curve
                  {bench.showBenchmark && (
                    <span className="normal-case font-normal text-slate-400 ml-1">
                      vs {bench.benchmarkLabel}
                    </span>
                  )}
                </p>
                <EquityCurveChart
                  data={bench.data}
                  benchmarkLabel={bench.benchmarkLabel}
                  showBenchmark={bench.showBenchmark}
                />
              </div>
              <div className="card p-6">
                <p className="section-title mb-4">Drawdown</p>
                <DrawdownChart
                  data={bench.data}
                  benchmarkLabel={bench.benchmarkLabel}
                  showBenchmark={bench.showBenchmark}
                />
              </div>
            </>
          );
        })()
      ) : (
        <>
          <div className="card p-6">
            <p className="section-title mb-4">Equity Curve</p>
            <EquityCurveChart data={equityCurve} />
          </div>
          <div className="card p-6">
            <p className="section-title mb-4">Drawdown</p>
            <DrawdownChart data={equityCurve} />
          </div>
        </>
      )}

      {/* Robustness Lab (only when this record saved an analysis) */}
      {savedRobustness ? (
        <RobustnessLabCard robustness={savedRobustness} />
      ) : (
        <p className="text-xs text-slate-400">
          Robustness analysis was not run for this saved backtest.
        </p>
      )}

      {/* Trades */}
      <div className="card p-6">
        <p className="section-title mb-4">
          Trade Log{" "}
          <span className="normal-case font-normal text-slate-400 ml-1">
            ({trades.length} events)
          </span>
        </p>
        <TradeTable trades={trades} />
      </div>
    </div>
  );
}
