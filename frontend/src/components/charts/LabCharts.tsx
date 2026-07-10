"use client";

/**
 * Shared lightweight chart components for the lab panels (Phase 31 UX upgrade).
 *
 * Thin, typed wrappers around recharts (already a project dependency) using the
 * shared neon chart theme + NeonTooltip. All inputs are deterministic values
 * computed from static sample data — no live data, no randomness. Non-finite
 * values are dropped before rendering (no NaN/Infinity on screen) and every
 * chart renders a graceful empty state when nothing plottable remains.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import NeonTooltip from "@/components/charts/NeonTooltip";
import { CHART_AXIS, CHART_AXIS_LINE, CHART_GRID, CHART_REF_LINE } from "@/components/charts/chartTheme";
import { seriesColor } from "@/lib/chartPalette";

const fin = (v: number | null | undefined): v is number =>
  typeof v === "number" && Number.isFinite(v);

function EmptyState({ note }: { note?: string }) {
  return (
    <p className="py-8 text-center text-xs" style={{ color: "var(--text-faint)" }}>
      {note ?? "No plottable data for the current inputs."}
    </p>
  );
}

const AXIS_TICK = { fill: CHART_AXIS, fontSize: 10 };

// --------------------------------------------------------------------------- //
// ScenarioBarChart — horizontal bars, one per (long-named) scenario/category.
// --------------------------------------------------------------------------- //
export interface BarDatum {
  label: string;
  value: number;
  color?: string;
}

export function ScenarioBarChart({
  data,
  format,
  height,
  defaultColor = seriesColor(0),
  emptyNote,
  ariaLabel,
}: {
  data: BarDatum[];
  format: (v: number) => string;
  height?: number;
  defaultColor?: string;
  emptyNote?: string;
  /** Specific accessible name for the chart (falls back to a generic label). */
  ariaLabel?: string;
}) {
  const rows = data.filter((d) => fin(d.value));
  if (!rows.length) return <EmptyState note={emptyNote} />;
  const h = height ?? Math.max(120, rows.length * 26 + 40);
  return (
    <div style={{ width: "100%", height: h }} aria-label={ariaLabel ?? "Scenario bar chart"} role="img">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 0 }}>
          <CartesianGrid stroke={CHART_GRID} horizontal={false} />
          <XAxis
            type="number"
            tick={AXIS_TICK}
            tickFormatter={(v: number) => format(v)}
            stroke={CHART_AXIS_LINE}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={150}
            tick={AXIS_TICK}
            stroke={CHART_AXIS_LINE}
            tickLine={false}
            interval={0}
          />
          <ReferenceLine x={0} stroke={CHART_REF_LINE} />
          <Tooltip
            content={<NeonTooltip formatValue={format} formatLabel={(l) => String(l)} />}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
          />
          <Bar dataKey="value" name="value" isAnimationActive={false} radius={[0, 3, 3, 0]} barSize={14}>
            {rows.map((d) => (
              <Cell key={d.label} fill={d.color ?? defaultColor} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// GroupedBarChart — short category labels, 1–3 series side by side.
// --------------------------------------------------------------------------- //
export interface SeriesDef {
  key: string;
  label: string;
  color?: string;
}

export function GroupedBarChart({
  data,
  series,
  format,
  height = 200,
  emptyNote,
  ariaLabel,
}: {
  data: Array<Record<string, number | string>>;
  series: SeriesDef[];
  format: (v: number) => string;
  height?: number;
  emptyNote?: string;
  /** Specific accessible name for the chart (falls back to a generic label). */
  ariaLabel?: string;
}) {
  const rows = data.filter((d) => series.some((s) => fin(d[s.key] as number)));
  if (!rows.length || !series.length) return <EmptyState note={emptyNote} />;
  return (
    <div style={{ width: "100%", height }} aria-label={ariaLabel ?? `Grouped bar chart: ${series.map((s) => s.label).join(", ")}`} role="img">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART_GRID} vertical={false} />
          <XAxis dataKey="label" tick={AXIS_TICK} stroke={CHART_AXIS_LINE} tickLine={false} interval={0} />
          <YAxis tick={AXIS_TICK} tickFormatter={(v: number) => format(v)} stroke={CHART_AXIS_LINE} tickLine={false} width={58} />
          <ReferenceLine y={0} stroke={CHART_REF_LINE} />
          <Tooltip
            content={<NeonTooltip formatValue={format} formatLabel={(l) => String(l)} />}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
          />
          {series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={s.color ?? seriesColor(i)}
              fillOpacity={0.85}
              isAnimationActive={false}
              radius={[3, 3, 0, 0]}
              barSize={18}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// SimpleLineChart — numeric x-axis, 1–3 line series.
// --------------------------------------------------------------------------- //
export function SimpleLineChart({
  data,
  series,
  format,
  xLabel,
  formatX = (v) => String(v),
  height = 200,
  emptyNote,
  ariaLabel,
}: {
  data: Array<Record<string, number | string | null>>;
  series: SeriesDef[];
  format: (v: number) => string;
  xLabel?: string;
  formatX?: (v: unknown) => string;
  height?: number;
  emptyNote?: string;
  /** Specific accessible name for the chart (falls back to a generic label). */
  ariaLabel?: string;
}) {
  const rows = data.filter((d) => series.some((s) => fin(d[s.key] as number)));
  if (!rows.length || !series.length) return <EmptyState note={emptyNote} />;
  return (
    <div style={{ width: "100%", height }} aria-label={ariaLabel ?? (xLabel ? `Line chart by ${xLabel}` : `Line chart: ${series.map((s) => s.label).join(", ")}`)} role="img">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART_GRID} vertical={false} />
          <XAxis dataKey="x" tick={AXIS_TICK} stroke={CHART_AXIS_LINE} tickLine={false} tickFormatter={(v) => formatX(v)} />
          <YAxis tick={AXIS_TICK} tickFormatter={(v: number) => format(v)} stroke={CHART_AXIS_LINE} tickLine={false} width={58} />
          <ReferenceLine y={0} stroke={CHART_REF_LINE} />
          <Tooltip
            content={<NeonTooltip formatValue={format} formatLabel={(l) => formatX(l)} />}
            cursor={{ stroke: CHART_REF_LINE }}
          />
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color ?? seriesColor(i)}
              strokeWidth={2}
              dot={{ r: 2.5 }}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// BarLineChart — composed bars (left axis) + line (right axis), e.g. the
// unlock schedule (tokens per event + cumulative % of circulating).
// --------------------------------------------------------------------------- //
export function BarLineChart({
  data,
  bar,
  line,
  formatBar,
  formatLine,
  height = 220,
  emptyNote,
  ariaLabel,
}: {
  data: Array<Record<string, number | string>>;
  bar: SeriesDef;
  line: SeriesDef;
  formatBar: (v: number) => string;
  formatLine: (v: number) => string;
  height?: number;
  emptyNote?: string;
  /** Specific accessible name for the chart (falls back to a generic label). */
  ariaLabel?: string;
}) {
  const rows = data.filter((d) => fin(d[bar.key] as number) || fin(d[line.key] as number));
  if (!rows.length) return <EmptyState note={emptyNote} />;
  return (
    <div style={{ width: "100%", height }} aria-label={ariaLabel ?? `Bar and line chart: ${bar.label}, ${line.label}`} role="img">
      <ResponsiveContainer>
        <ComposedChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART_GRID} vertical={false} />
          <XAxis dataKey="label" tick={AXIS_TICK} stroke={CHART_AXIS_LINE} tickLine={false} interval={0} />
          <YAxis yAxisId="bar" tick={AXIS_TICK} tickFormatter={(v: number) => formatBar(v)} stroke={CHART_AXIS_LINE} tickLine={false} width={54} />
          <YAxis yAxisId="line" orientation="right" tick={AXIS_TICK} tickFormatter={(v: number) => formatLine(v)} stroke={CHART_AXIS_LINE} tickLine={false} width={48} />
          <Tooltip
            content={
              <NeonTooltip
                formatValue={(v) => formatBar(v)}
                formatLabel={(l) => String(l)}
              />
            }
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
          />
          <Bar yAxisId="bar" dataKey={bar.key} name={bar.label} fill={bar.color ?? seriesColor(0)} fillOpacity={0.8} isAnimationActive={false} radius={[3, 3, 0, 0]} barSize={20} />
          <Line yAxisId="line" type="monotone" dataKey={line.key} name={line.label} stroke={line.color ?? seriesColor(4)} strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
