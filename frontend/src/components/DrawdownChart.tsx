"use client";

import { useMemo } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { EquityPoint } from "@/lib/types";
import { fmtMonthYear } from "@/lib/format";

interface Props {
  data: EquityPoint[];
}

interface DrawdownPoint {
  date: string;
  strategy: number;  // fraction ≤ 0
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
      <p className="font-semibold text-slate-600 mb-1">
        {label ? fmtMonthYear(label) : ""}
      </p>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-semibold tabular">
            {(p.value * 100).toFixed(2)}%
          </span>
        </div>
      ))}
    </div>
  );
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

export default function DrawdownChart({ data }: Props) {
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

  // Y-axis domain: slightly below the minimum drawdown for padding
  const minDD = Math.min(...drawdown.map((d) => Math.min(d.strategy, d.benchmark)));
  const yMin = Math.min(minDD * 1.1, -0.01); // at least -1% for scale

  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart
        data={drawdown}
        margin={{ top: 4, right: 16, bottom: 0, left: 16 }}
      >
        <defs>
          <linearGradient id="ddStrategy" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.35} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="ddBenchmark" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f97316" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#f97316" stopOpacity={0.02} />
          </linearGradient>
        </defs>

        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />

        <XAxis
          dataKey="date"
          ticks={yearTicks}
          tickFormatter={(v: string) => v.slice(0, 4)}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          axisLine={{ stroke: "#e2e8f0" }}
          tickLine={false}
        />

        <YAxis
          domain={[yMin, 0]}
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          axisLine={false}
          tickLine={false}
          width={48}
        />

        <Tooltip content={<CustomTooltip />} />

        <Legend
          iconType="plainline"
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
        />

        {/* Benchmark drawdown — drawn first (behind) */}
        <Area
          type="monotone"
          dataKey="benchmark"
          name="Benchmark DD"
          stroke="#f97316"
          strokeWidth={1.5}
          strokeDasharray="4 3"
          fill="url(#ddBenchmark)"
          dot={false}
        />

        {/* Strategy drawdown — drawn on top */}
        <Area
          type="monotone"
          dataKey="strategy"
          name="Strategy DD"
          stroke="#ef4444"
          strokeWidth={2}
          fill="url(#ddStrategy)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
