import type { PerformanceMetrics } from "@/lib/types";
import { fmtPct, fmtRatio, fmtInt } from "@/lib/format";

interface Props {
  strategy: PerformanceMetrics;
  benchmark: PerformanceMetrics;
  ticker: string;
  strategyLabel: string;
}

// Describes how each metric is displayed and compared.
interface MetricDef {
  key: keyof PerformanceMetrics;
  label: string;
  description: string;
  fmt: (v: number) => string;
  // "higher" = larger value is better, "lower" = smaller magnitude is better
  direction: "higher" | "lower";
}

const METRICS: MetricDef[] = [
  {
    key: "total_return",
    label: "Total Return",
    description: "Cumulative return over the full period",
    fmt: (v) => fmtPct(v),
    direction: "higher",
  },
  {
    key: "cagr",
    label: "CAGR",
    description: "Compound annual growth rate",
    fmt: (v) => fmtPct(v),
    direction: "higher",
  },
  {
    key: "sharpe_ratio",
    label: "Sharpe Ratio",
    description: "Annualised return / annualised volatility (rf = 0%)",
    fmt: (v) => fmtRatio(v),
    direction: "higher",
  },
  {
    key: "sortino_ratio",
    label: "Sortino Ratio",
    description: "Like Sharpe but penalises only downside volatility",
    fmt: (v) => fmtRatio(v),
    direction: "higher",
  },
  {
    key: "max_drawdown",
    label: "Max Drawdown",
    description: "Largest peak-to-trough decline in equity",
    fmt: (v) => fmtPct(v),
    // Less negative = better (so higher direction still works correctly)
    direction: "higher",
  },
  {
    key: "volatility",
    label: "Volatility",
    description: "Annualised standard deviation of daily returns",
    fmt: (v) => fmtPct(v),
    direction: "lower",
  },
  {
    key: "win_rate",
    label: "Win Rate",
    description: "Fraction of trading days with a positive return",
    fmt: (v) => fmtPct(v),
    direction: "higher",
  },
  {
    key: "num_days",
    label: "Trading Days",
    description: "Number of trading days in the backtest period",
    fmt: (v) => fmtInt(v),
    direction: "higher",
  },
];

function OutcomeTag({ better }: { better: boolean | null }) {
  if (better === null)
    return <span className="text-slate-300 text-xs ml-1">—</span>;
  return better ? (
    <span className="text-green-600 text-xs ml-1 font-semibold">▲</span>
  ) : (
    <span className="text-red-500 text-xs ml-1 font-semibold">▼</span>
  );
}

function isBetter(
  stratVal: number,
  benchVal: number,
  direction: "higher" | "lower",
): boolean | null {
  if (Math.abs(stratVal - benchVal) < 1e-9) return null; // tied
  if (direction === "higher") return stratVal > benchVal;
  return stratVal < benchVal; // lower is better (e.g. volatility)
}

export default function MetricsGrid({
  strategy,
  benchmark,
  ticker,
  strategyLabel,
}: Props) {
  return (
    <div className="card overflow-x-auto">
      <div className="min-w-[560px]">
      {/* Header row */}
      <div className="grid grid-cols-[1fr_auto_auto] items-center gap-0 border-b border-slate-100">
        <div className="px-6 py-3">
          <span className="section-title">Performance Summary</span>
        </div>
        <div className="px-6 py-3 text-center min-w-[130px]">
          <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full whitespace-nowrap">
            {strategyLabel}
          </span>
        </div>
        <div className="px-6 py-3 text-center min-w-[130px]">
          <span className="text-xs font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full whitespace-nowrap">
            {ticker} Buy &amp; Hold
          </span>
        </div>
      </div>

      {/* Metric rows */}
      {METRICS.map((m, i) => {
        const sv = strategy[m.key] as number;
        const bv = benchmark[m.key] as number;
        const better = isBetter(sv, bv, m.direction);

        return (
          <div
            key={m.key}
            className={
              "grid grid-cols-[1fr_auto_auto] items-center gap-0 " +
              (i % 2 === 0 ? "bg-white" : "bg-slate-50/60") +
              " border-b border-slate-100 last:border-b-0"
            }
          >
            {/* Metric label */}
            <div className="px-6 py-3">
              <p className="text-sm font-medium text-slate-800">{m.label}</p>
              <p className="text-xs text-slate-400 mt-0.5 hidden sm:block">
                {m.description}
              </p>
            </div>

            {/* Strategy value */}
            <div className="px-6 py-3 text-right min-w-[130px]">
              <span className="metric-value tabular text-sm font-semibold">
                {m.fmt(sv)}
              </span>
              <OutcomeTag better={better} />
            </div>

            {/* Benchmark value */}
            <div className="px-6 py-3 text-right min-w-[130px]">
              <span className="tabular text-sm text-slate-500">
                {m.fmt(bv)}
              </span>
            </div>
          </div>
        );
      })}

      {/* Legend */}
      <div className="px-6 py-3 bg-slate-50 flex gap-4 text-xs text-slate-400">
        <span>
          <span className="text-green-600 font-semibold">▲</span> strategy
          outperforms
        </span>
        <span>
          <span className="text-red-500 font-semibold">▼</span> strategy
          underperforms
        </span>
      </div>
      </div>
    </div>
  );
}
