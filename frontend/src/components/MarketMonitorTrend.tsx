"use client";

import { useEffect, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import NeonTooltip from "@/components/charts/NeonTooltip";
import { CHART_AXIS, CHART_AXIS_LINE, CHART_GRID } from "@/components/charts/chartTheme";
import { getMonitorHistory, sourceLink, type MonitorHistory, type MonitorInstrument } from "@/lib/marketMonitor";

const control = "rounded border border-[var(--line)] px-3 py-1.5 text-xs text-[var(--text-hi)] hover:border-[var(--accent)] disabled:opacity-50";
const tickValue = new Intl.NumberFormat("en-US", { notation: "compact", maximumSignificantDigits: 4 });
const closeValue = new Intl.NumberFormat("en-US", { maximumSignificantDigits: 17 });
const timestamp = (value: string | null) => value ? new Date(value).toLocaleString() : "Not available";

// The parent keys this panel by catalog ID, so a new selection owns a new series.
export default function MarketMonitorTrend({ instrument, onClose }: { instrument: MonitorInstrument; onClose: () => void }) {
  const [history, setHistory] = useState<MonitorHistory | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const section = useRef<HTMLElement>(null);

  useEffect(() => { section.current?.focus(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timer = setTimeout(() => controller.abort(), 90_000);
    setLoading(true);
    setError(null);
    getMonitorHistory(instrument, controller.signal).then((result) => {
      if (!active) return;
      if (controller.signal.aborted) throw new Error("Trend request timed out.");
      setHistory((previous) => {
        if (result.status === "unavailable" && previous?.points.length) {
          const message = result.message ? result.message + " " : "";
          return { ...previous, status: "stale", checked_at: result.checked_at,
            message: message + "Showing the last successful trend for this instrument." };
        }
        return result;
      });
    }).catch((failure: unknown) => {
      if (active) setError(controller.signal.aborted ? "Trend request timed out." :
        failure instanceof Error ? failure.message : "Trend request failed.");
    }).finally(() => {
      clearTimeout(timer);
      if (active) setLoading(false);
    });
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [instrument, attempt]);

  const points = history?.points ?? [];
  const url = sourceLink(instrument.source_url);
  const status = error ? (points.length ? "Stale" : "Unavailable") :
    history?.status === "ready" ? "Ready" : history?.status === "stale" ? "Stale" : "Unavailable";

  return (
    <section ref={section} tabIndex={-1} aria-label={`Trend for ${instrument.name}`}
      className="mt-4 min-w-0 space-y-3 border-t border-[var(--line)] pt-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-semibold text-[var(--text-hi)]">{instrument.name} trend</h4>
          <p className="mt-1 text-xs text-[var(--text-mut)]">{instrument.symbol} / {instrument.kind.replaceAll("_", " ")} / {instrument.unit}{instrument.currency ? ` / ${instrument.currency}` : ""}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={control} disabled={loading} onClick={() => { setLoading(true); setAttempt(n => n + 1); }}>Refresh trend</button>
          <button type="button" className={control} onClick={onClose}>Close trend</button>
        </div>
      </header>
      <div className="space-y-1 text-xs text-[var(--text-mut)]">
        <p>3 months / Daily / Provider-adjusted close</p>
        <p>{url ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-[var(--accent)] underline underline-offset-4">Yahoo Finance</a> : "Yahoo Finance"}
          {history?.timezone ? ` / ${history.timezone}` : ""}</p>
        {instrument.kind === "futures_reference" && <p>Provider futures reference, not spot, a specific expiry, a CFD, or a verified continuous contract.</p>}
        <p>Not realtime or total return; session completion and delay are not established.</p>
      </div>
      {loading && <p role="status" className="text-xs text-[var(--text-mut)]">{history ? "Refreshing trend..." : "Loading trend..."}</p>}
      {error && <p role="alert" className="text-xs text-[var(--neg)]">{error}{points.length > 0 && " Showing the last successful trend for this instrument."}</p>}
      {(history || error) && <div className="space-y-1 text-xs">
        <p style={{ color: status === "Ready" ? "var(--pos)" : status === "Stale" ? "var(--warn)" : "var(--neg)" }}>{status}</p>
        {history?.message && <p>{history.message}</p>}
        {history && <p className="text-[var(--text-mut)]">Retrieved: {timestamp(history.retrieved_at)} / Checked: {timestamp(history.checked_at)}</p>}
      </div>}
      {!loading && !points.length && <p className="text-sm text-[var(--text-mut)]">No daily closes available.</p>}
      {points.length > 0 && <>
        <p className="text-xs text-[var(--text-mut)]">Observed dates: {points[0].date} to {points[points.length - 1].date}</p>
        {points.length === 1 && <p className="text-xs text-[var(--text-mut)]">Only one daily close is available; insufficient history for a trend.</p>}
        <div role="img" aria-label={`Daily closes of ${instrument.name} in ${instrument.unit}`} className="h-64 min-w-0">
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <LineChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
              <CartesianGrid stroke={CHART_GRID} vertical={false} />
              <XAxis dataKey="date" minTickGap={24} tickFormatter={(day: string) => day.slice(5)}
                tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
              <YAxis domain={["auto", "auto"]} width={48} tickFormatter={(value: number) => tickValue.format(value)}
                tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} />
              <Tooltip content={<NeonTooltip formatLabel={String} formatValue={value => `${closeValue.format(value)} ${instrument.unit}`} />} />
              <Line type="linear" dataKey="value" name="Adjusted close" stroke="var(--accent)" strokeWidth={2}
                dot={points.length === 1 ? { r: 4, fill: "var(--accent)" } : false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <details className="border-t border-[var(--line)] pt-2">
          <summary className="cursor-pointer text-xs">Daily values ({points.length})</summary>
          <div className="mt-2 max-h-64 overflow-auto">
            <table aria-label={`Daily values for ${instrument.name}`} className="w-full text-left text-xs tabular-nums">
              <thead><tr><th scope="col">Date</th><th scope="col" className="text-right">Adjusted close ({instrument.unit})</th></tr></thead>
              <tbody>{points.map(point => <tr key={point.date} className="border-t border-[var(--line)]">
                <th scope="row" className="py-2 font-normal">{point.date}</th>
                <td className="py-2 text-right font-mono">{closeValue.format(point.value)}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </details>
      </>}
    </section>
  );
}
