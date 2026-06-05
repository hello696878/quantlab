"use client";

import { useId } from "react";
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
  ReferenceLine,
} from "recharts";
import type { EquityPoint } from "@/lib/types";
import { fmtDollarTick, fmtDollar } from "@/lib/format";
import { useAccentColors } from "@/lib/useAccentColors";
import NeonTooltip from "@/components/charts/NeonTooltip";
import {
  BENCHMARK_MUTED,
  CHART_AXIS,
  CHART_AXIS_LINE,
  CHART_GRID,
  CHART_REF_LINE,
  GLOW_OPACITY,
  GLOW_WIDTH,
  MAIN_WIDTH,
} from "@/components/charts/chartTheme";

interface Props {
  data: EquityPoint[];
}

// Show year ticks: keep only the first data point of each calendar year.
function buildYearTicks(data: EquityPoint[]): string[] {
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

export default function EquityCurveChart({ data }: Props) {
  const colors = useAccentColors();
  const gradId = useId().replace(/:/g, "");
  const fillId = `equityFill-${gradId}`;

  if (!data.length) {
    return (
      <div className="flex h-[340px] items-center justify-center text-sm text-slate-400">
        No equity curve data was returned for this backtest.
      </div>
    );
  }

  const yearTicks = buildYearTicks(data);
  const initialCapital = data[0].strategy; // both start at same value

  return (
    <ResponsiveContainer width="100%" height={340}>
      <ComposedChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 16 }}>
        <defs>
          {/* Subtle accent area fill — fades to transparent so gridlines show */}
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={colors.accent} stopOpacity={0.28} />
            <stop offset="55%" stopColor={colors.accent} stopOpacity={0.08} />
            <stop offset="100%" stopColor={colors.accent} stopOpacity={0} />
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
          tickFormatter={fmtDollarTick}
          tick={{ fontSize: 11, fill: CHART_AXIS }}
          axisLine={false}
          tickLine={false}
          width={64}
        />

        <Tooltip content={<NeonTooltip formatValue={fmtDollar} />} />

        <Legend
          iconType="plainline"
          wrapperStyle={{ fontSize: 12, paddingTop: 12 }}
          payload={[
            {
              value: "Strategy",
              type: "plainline",
              id: "strategy",
              color: colors.accent,
              payload: { strokeDasharray: "0" },
            },
            {
              value: "Benchmark",
              type: "plainline",
              id: "benchmark",
              color: BENCHMARK_MUTED,
              payload: { strokeDasharray: "5 3" },
            },
          ]}
        />

        {/* Initial capital reference line */}
        <ReferenceLine
          y={initialCapital}
          stroke={CHART_REF_LINE}
          strokeDasharray="4 4"
          strokeWidth={1}
        />

        {/* Accent area fill under the strategy curve */}
        <Area
          type="monotone"
          dataKey="strategy"
          name="_area"
          legendType="none"
          stroke="none"
          fill={`url(#${fillId})`}
          fillOpacity={1}
          dot={false}
          activeDot={false}
          isAnimationActive={false}
        />

        {/* Benchmark — muted slate, dashed, subordinate (no strong glow) */}
        <Line
          type="monotone"
          dataKey="benchmark"
          name="Benchmark"
          stroke={BENCHMARK_MUTED}
          strokeWidth={1.5}
          strokeDasharray="5 3"
          strokeOpacity={0.6}
          dot={false}
          activeDot={{ r: 3 }}
          isAnimationActive={false}
        />

        {/* Strategy glow underlay — wide + low opacity accent halo */}
        <Line
          type="monotone"
          dataKey="strategy"
          name="_glow"
          legendType="none"
          stroke={colors.accent}
          strokeWidth={GLOW_WIDTH}
          strokeOpacity={GLOW_OPACITY}
          strokeLinecap="round"
          dot={false}
          activeDot={false}
          isAnimationActive={false}
        />

        {/* Strategy — crisp accent line on top */}
        <Line
          type="monotone"
          dataKey="strategy"
          name="Strategy"
          stroke={colors.accent}
          strokeWidth={MAIN_WIDTH}
          dot={false}
          activeDot={{ r: 4, fill: colors.accent, stroke: colors.accent }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
