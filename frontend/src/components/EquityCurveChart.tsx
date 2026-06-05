"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";
import type { EquityPoint } from "@/lib/types";
import { fmtDollarTick, fmtDollar, fmtMonthYear } from "@/lib/format";
import { useAccentColors } from "@/lib/useAccentColors";

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

// Custom tooltip
function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-slate-600 mb-1">{label ? fmtMonthYear(label) : ""}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-semibold tabular">{fmtDollar(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export default function EquityCurveChart({ data }: Props) {
  const colors = useAccentColors();

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
      <LineChart
        data={data}
        margin={{ top: 4, right: 16, bottom: 0, left: 16 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />

        <XAxis
          dataKey="date"
          ticks={yearTicks}
          tickFormatter={(v: string) => v.slice(0, 4)}
          tick={{ fontSize: 11, fill: "#79839a" }}
          axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
          tickLine={false}
        />

        <YAxis
          tickFormatter={fmtDollarTick}
          tick={{ fontSize: 11, fill: "#79839a" }}
          axisLine={false}
          tickLine={false}
          width={64}
        />

        <Tooltip content={<CustomTooltip />} />

        <Legend
          iconType="plainline"
          wrapperStyle={{ fontSize: 12, paddingTop: 12 }}
        />

        {/* Initial capital reference line */}
        <ReferenceLine
          y={initialCapital}
          stroke="rgba(255,255,255,0.18)"
          strokeDasharray="4 4"
          strokeWidth={1}
        />

        {/* Benchmark — accent-2 (harmonized partner), dashed + subordinate */}
        <Line
          type="monotone"
          dataKey="benchmark"
          name="Benchmark"
          stroke={colors.accent2}
          strokeWidth={1.5}
          strokeDasharray="5 3"
          dot={false}
          activeDot={{ r: 3 }}
        />

        {/* Strategy — primary accent line, rendered on top */}
        <Line
          type="monotone"
          dataKey="strategy"
          name="Strategy"
          stroke={colors.accent}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: colors.accent }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
