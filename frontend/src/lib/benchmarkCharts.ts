import type { BenchmarkAnalytics, EquityPoint } from "@/lib/types";

/**
 * Chart-ready series for benchmark visualization.
 *
 * The response `equity_curve[].benchmark` always carries the legacy same-asset
 * buy-and-hold values.  When a *custom* benchmark is configured, the block's
 * own `equity_curve` replaces those values via an inner join on dates (the
 * same alignment the active metrics use).  Selecting a benchmark never changes
 * the strategy series itself.
 */
export interface BenchmarkChartSeries {
  /** Points to chart — strategy untouched; benchmark possibly replaced. */
  data: EquityPoint[];
  /** Legend label, e.g. "Buy & Hold SPY" or "QQQ". */
  benchmarkLabel: string;
  /** False when benchmark mode is none or benchmark data is unavailable. */
  showBenchmark: boolean;
}

export function buildBenchmarkChartSeries(
  equityCurve: EquityPoint[],
  analytics: BenchmarkAnalytics | null | undefined,
): BenchmarkChartSeries {
  // No block ⇒ benchmark mode "none" (or analytics unavailable): strategy only.
  if (!analytics || analytics.mode === "none") {
    return { data: equityCurve, benchmarkLabel: "Benchmark", showBenchmark: false };
  }

  if (analytics.mode === "buy_and_hold_same_asset") {
    return {
      data: equityCurve,
      benchmarkLabel: analytics.display_name,
      showBenchmark: true,
    };
  }

  // custom_ticker — join the block's own curve onto the strategy dates.
  const curve = analytics.equity_curve;
  if (!curve || curve.length < 2 || !analytics.metrics) {
    return { data: equityCurve, benchmarkLabel: "Benchmark", showBenchmark: false };
  }
  const byDate = new Map(curve.map((p) => [p.date, p.equity]));
  const joined = equityCurve
    .filter((p) => byDate.has(p.date))
    .map((p) => ({ ...p, benchmark: byDate.get(p.date)! }));
  if (joined.length < 2) {
    return { data: equityCurve, benchmarkLabel: "Benchmark", showBenchmark: false };
  }
  return {
    data: joined,
    benchmarkLabel: analytics.ticker ?? analytics.display_name,
    showBenchmark: true,
  };
}
