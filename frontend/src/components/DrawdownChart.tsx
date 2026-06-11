"use client";

import { useId, useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { EquityPoint } from "@/lib/types";
import NeonTooltip from "@/components/charts/NeonTooltip";
import {
  CHART_AXIS,
  CHART_AXIS_LINE,
  CHART_GRID,
  DANGER,
  DANGER_SOFT,
} from "@/components/charts/chartTheme";

interface Props {
  data: EquityPoint[];
  /** Legend label for the benchmark drawdown (e.g. "Buy & Hold SPY DD"). */
  benchmarkLabel?: string;
  /** Hide the benchmark drawdown (benchmark mode "none" / unavailable). */
  showBenchmark?: boolean;
}

interface DrawdownPoint {
  date: string;
  strategy: number; // fraction ≤ 0
  benchmark: number; // fraction ≤ 0
}

/** Compute running peak-to-trough drawdown for one equity series. */
function drawdownSeries(values: number[]): number[] {
  let peak = values[0];
  return values.map((v) => {
    if (v > peak) peak = v;
    return peak > 0 ? (v - peak) / peak : 0;
  });
}

function fmtDdPct(v: number): string {
  return `${(v * 100).toFixed(2)}%`;
}

function buildYearTicks(data: DrawdownPoint[]): string[] {
  const seen = new Set<string>();
  const ticks: string[] = [];
  for (const d of data) {
    const year = d.date.slice(0, 4);
    if (!seen.has(year)) {
      seen.add(year);
      ticks.push(d.date);
    }
  }
  return ticks;
}

export default function DrawdownChart({
  data,
  benchmarkLabel = "Benchmark",
  showBenchmark = true,
}: Props) {
  const uid = useId().replace(/:/g, "");
  const strokeId = `ddStrategy-${uid}`;
  const benchId = `ddBenchmark-${uid}`;

  const drawdown: DrawdownPoint[] = useMemo(() => {
    const stratValues = data.map((d) => d.strategy);
    const benchValues = data.map((d) => d.benchmark);
    const stratDD = drawdownSeries(stratValues);
    const benchDD = drawdownSeries(benchValues);
    return data.map((d, i) => ({
      date: d.date,
      strategy: stratDD[i],
      benchmark: benchDD[i],
    }));
  }, [data]);

  if (!drawdown.length) {
    return (
      <div className="flex h-[240px] items-center justify-center text-sm text-slate-400">
        No equity curve data is available to compute drawdown.
      </div>
    );
  }

  const yearTicks = buildYearTicks(drawdown);

  // Y-axis domain: slightly below the minimum drawdown for padding (only the
  // visible series count toward the scale).
  const minDD = Math.min(
    ...drawdown.map((d) =>
      showBenchmark ? Math.min(d.strategy, d.benchmark) : d.strategy,
    ),
  );
  const yMin = Math.min(minDD * 1.1, -0.01); // at least -1% for scale

  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={drawdown} margin={{ top: 4, right: 16, bottom: 0, left: 16 }}>
        <defs>
          <linearGradient id={strokeId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={DANGER} stopOpacity={0.38} />
            <stop offset="95%" stopColor={DANGER} stopOpacity={0.04} />
          </linearGradient>
          <linearGradient id={benchId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={DANGER_SOFT} stopOpacity={0.2} />
            <stop offset="95%" stopColor={DANGER_SOFT} stopOpacity={0.02} />
          </linearGradient>
        </defs>

        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />

        <XAxis
          dataKey="date"
          ticks={yearTicks}
          tickFormatter={(v: string) => v.slice(0, 4)}
          tick={{ fontSize: 11, fill: CHART_AXIS }}
          axisLine={{ stroke: CHART_AXIS_LINE }}
          tickLine={false}
        />

        <YAxis
          domain={[yMin, 0]}
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          tick={{ fontSize: 11, fill: CHART_AXIS }}
          axisLine={false}
          tickLine={false}
          width={48}
        />

        <Tooltip
          content={
            <NeonTooltip
              formatValue={fmtDdPct}
              borderColor="rgba(239,68,68,0.6)"
              glow="0 0 20px -6px rgba(239,68,68,0.55)"
            />
          }
        />

        <Legend
          iconType="plainline"
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          payload={[
            {
              value: "Strategy DD",
              type: "plainline",
              id: "strategy",
              color: DANGER,
              payload: { strokeDasharray: "0" },
            },
            ...(showBenchmark
              ? [
                  {
                    value: `${benchmarkLabel} DD`,
                    type: "plainline" as const,
                    id: "benchmark",
                    color: DANGER_SOFT,
                    payload: { strokeDasharray: "4 3" },
                  },
                ]
              : []),
          ]}
        />

        {/* Benchmark drawdown — drawn first (behind) */}
        {showBenchmark && (
          <Area
            type="monotone"
            dataKey="benchmark"
            name={`${benchmarkLabel} DD`}
            stroke={DANGER_SOFT}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            strokeOpacity={0.7}
            fill={`url(#${benchId})`}
            dot={false}
            isAnimationActive={false}
          />
        )}

        {/* Subtle red glow underlay behind the strategy drawdown line */}
        <Line
          type="monotone"
          dataKey="strategy"
          name="_glow"
          legendType="none"
          stroke={DANGER}
          strokeWidth={6}
          strokeOpacity={0.14}
          strokeLinecap="round"
          dot={false}
          activeDot={false}
          isAnimationActive={false}
        />

        {/* Strategy drawdown — semantic red area */}
        <Area
          type="monotone"
          dataKey="strategy"
          name="Strategy DD"
          stroke={DANGER}
          strokeWidth={2}
          fill={`url(#${strokeId})`}
          dot={false}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
