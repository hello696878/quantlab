"use client";

import { useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";
import type { EquityPoint } from "@/lib/types";
import { useAccentColors } from "@/lib/useAccentColors";
import NeonTooltip from "@/components/charts/NeonTooltip";
import {
  CHART_AXIS,
  CHART_AXIS_LINE,
  CHART_GRID,
  CHART_REF_LINE,
  GLOW_OPACITY,
  GLOW_WIDTH,
  MAIN_WIDTH,
} from "@/components/charts/chartTheme";

interface Props {
  /** Aligned points — benchmark values must already be the selected benchmark. */
  data: EquityPoint[];
  benchmarkLabel: string;
}

interface ExcessPoint {
  date: string;
  excess: number;
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(2)}%`;
}

function buildYearTicks(data: ExcessPoint[]): string[] {
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

/**
 * Cumulative excess return: strategy cumulative return − benchmark cumulative
 * return at each date (both measured from the first aligned point).  Simple
 * difference of cumulative returns — clearly labeled, deliberately not a
 * compounded "active equity" curve.
 */
export default function ExcessReturnChart({ data, benchmarkLabel }: Props) {
  const colors = useAccentColors();

  const points: ExcessPoint[] = useMemo(() => {
    if (data.length < 2) return [];
    const s0 = data[0].strategy;
    const b0 = data[0].benchmark;
    if (!(s0 > 0) || !(b0 > 0)) return [];
    return data.map((p) => ({
      date: p.date,
      excess: p.strategy / s0 - p.benchmark / b0,
    }));
  }, [data]);

  if (!points.length) {
    return (
      <div className="flex h-[220px] items-center justify-center text-sm text-slate-400">
        Not enough aligned data to compute cumulative excess return.
      </div>
    );
  }

  const yearTicks = buildYearTicks(points);
  const last = points[points.length - 1].excess;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={points} margin={{ top: 4, right: 16, bottom: 0, left: 16 }}>
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
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          tick={{ fontSize: 11, fill: CHART_AXIS }}
          axisLine={false}
          tickLine={false}
          width={52}
        />

        <Tooltip content={<NeonTooltip formatValue={fmtPct} />} />

        <Legend
          iconType="plainline"
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          payload={[
            {
              value: `Cumulative excess vs ${benchmarkLabel} (now ${fmtPct(last)})`,
              type: "plainline",
              id: "excess",
              color: colors.accent,
              payload: { strokeDasharray: "0" },
            },
          ]}
        />

        {/* Zero line — above = ahead of benchmark, below = behind */}
        <ReferenceLine
          y={0}
          stroke={CHART_REF_LINE}
          strokeDasharray="4 4"
          strokeWidth={1}
        />

        {/* Accent glow underlay */}
        <Line
          type="monotone"
          dataKey="excess"
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

        <Line
          type="monotone"
          dataKey="excess"
          name={`Excess vs ${benchmarkLabel}`}
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
