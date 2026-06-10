"use client";

import type { BenchmarkAnalytics, PerformanceMetrics } from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";

interface Props {
  analytics: BenchmarkAnalytics;
  strategyMetrics: PerformanceMetrics;
}

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 text-center">
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p
        className={
          "mono mt-0.5 text-sm font-semibold " +
          (accent ? "text-blue-700" : "text-slate-800")
        }
      >
        {value}
      </p>
    </div>
  );
}

const dash = "—";
const pct = (v?: number | null) => (typeof v === "number" ? fmtPct(v) : dash);
const ratio = (v?: number | null) => (typeof v === "number" ? fmtRatio(v) : dash);

/**
 * Benchmark + active-performance summary for a single backtest result.
 * Comparison only — selecting a benchmark never changes strategy trades.
 */
export default function BenchmarkComparisonCard({ analytics, strategyMetrics }: Props) {
  const m = analytics.metrics;
  const a = analytics.active_metrics;

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="section-title">Benchmark Comparison</p>
        <span className="text-xs text-slate-500">
          vs {analytics.display_name}
          {analytics.mode === "custom_ticker" && analytics.data_provider
            ? ` · ${analytics.data_provider}`
            : ""}
        </span>
      </div>

      {m ? (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="Strategy return" value={pct(strategyMetrics.total_return)} />
            <Stat label="Benchmark return" value={pct(m.total_return)} />
            <Stat
              label="Excess return"
              value={pct(a?.excess_total_return)}
              accent
            />
            <Stat label="Strategy Sharpe" value={ratio(strategyMetrics.sharpe_ratio)} />
            <Stat label="Benchmark Sharpe" value={ratio(m.sharpe)} />
            <Stat label="Benchmark max DD" value={pct(m.max_drawdown)} />
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-5">
            <Stat label="Alpha (ann.)" value={pct(a?.alpha)} accent />
            <Stat label="Beta" value={ratio(a?.beta)} />
            <Stat label="Correlation" value={ratio(a?.correlation)} />
            <Stat label="Tracking error" value={pct(a?.tracking_error)} />
            <Stat label="Info ratio" value={ratio(a?.information_ratio)} />
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          Benchmark analytics are unavailable for this run.
        </p>
      )}

      {analytics.warnings.length > 0 && (
        <ul className="mt-3 list-disc space-y-0.5 pl-4 text-xs text-amber-700">
          {analytics.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-[11px] text-slate-400">
        Benchmark analytics are based on aligned historical returns (risk-free
        rate 0). They are sensitive to data quality, date alignment, the
        annualization convention, and the chosen benchmark — and they never
        change strategy trades.
      </p>
    </div>
  );
}
