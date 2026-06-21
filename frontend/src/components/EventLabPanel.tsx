"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Cell,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import {
  BacktestApiError,
  computeMergerArb,
  fetchSampleEvents,
  runEventStudy,
  runMultiEventStudy,
} from "@/lib/api";
import type {
  AbnormalReturnModel,
  EventStudyResponse,
  MergerArbResponse,
  MultiEventStudyResponse,
} from "@/lib/types";
import NeonTooltip from "@/components/charts/NeonTooltip";
import {
  CHART_AXIS,
  CHART_AXIS_LINE,
  CHART_GRID,
  CHART_REF_LINE,
} from "@/components/charts/chartTheme";
import { seriesColor } from "@/lib/chartPalette";

type Tab = "study" | "multi" | "merger" | "education";

const inputCls = "ql-input px-2.5 py-1.5";
const labelCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400";

const ASSET_COLOR = seriesColor(0); // cyan
const BENCH_COLOR = seriesColor(2); // violet
const CAR_COLOR = seriesColor(4); // amber
const AR_POS = "#34d399"; // emerald
const AR_NEG = "#f87171"; // red

function num(s: string): number {
  return s.trim() === "" ? NaN : Number(s);
}
function intNum(s: string): number {
  const value = num(s);
  return Number.isInteger(value) ? value : NaN;
}
function finite(s: string): boolean {
  return Number.isFinite(num(s));
}
function pct(v: number | null | undefined, digits = 2): string {
  return v == null ? "—" : `${(v * 100).toFixed(digits)}%`;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className={labelCls}>{label}</span>
      {children}
    </label>
  );
}
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass px-3 py-2 text-center">
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="metric-value mono mt-0.5 text-sm font-semibold">{value}</p>
    </div>
  );
}

const MODEL_OPTIONS: { value: AbnormalReturnModel; label: string }[] = [
  { value: "market_adjusted", label: "Market-adjusted" },
  { value: "mean_adjusted", label: "Mean-adjusted" },
  { value: "market_model", label: "Market model (α, β)" },
];

const CAVEAT =
  "Event studies depend on clean point-in-time event dates, benchmark choice, leakage before " +
  "the announcement, confounding events, liquidity, transaction costs, and survivorship bias. " +
  "Research diagnostic only — no live filings, not investment advice.";

export default function EventLabPanel({ initialTab = "study" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-600">
          The Event Lab studies how assets behave around specific dates — earnings, announcements,
          merger news, index changes, or macro events — via benchmark-adjusted abnormal returns,
          and includes a simplified merger-arbitrage calculator.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      <div className="ql-segmented">
        {(
          [
            ["study", "Event Study"],
            ["multi", "Multi-Event"],
            ["merger", "Merger Arb"],
            ["education", "Education"],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={"ql-segmented-option " + (tab === id ? "active" : "")}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "study" && <EventStudyTab />}
      {tab === "multi" && <MultiEventTab />}
      {tab === "merger" && <MergerArbTab />}
      {tab === "education" && <EducationTab />}
    </div>
  );
}

// ── Event Study ────────────────────────────────────────────────────────────

function EventStudyTab() {
  const [ticker, setTicker] = useState("AAPL");
  const [benchmark, setBenchmark] = useState("SPY");
  const [eventDate, setEventDate] = useState("2024-05-02");
  const [eventName, setEventName] = useState("Sample earnings event");
  const [model, setModel] = useState<AbnormalReturnModel>("market_adjusted");
  const [estWindow, setEstWindow] = useState("120");
  const [preDays, setPreDays] = useState("10");
  const [postDays, setPostDays] = useState("10");
  const [result, setResult] = useState<EventStudyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const estDaysNum = intNum(estWindow);
  const preDaysNum = intNum(preDays);
  const postDaysNum = intNum(postDays);

  const valid =
    ticker.trim() !== "" &&
    benchmark.trim() !== "" &&
    /^\d{4}-\d{2}-\d{2}$/.test(eventDate) &&
    estDaysNum >= 1 &&
    estDaysNum <= 500 &&
    preDaysNum >= 0 &&
    preDaysNum <= 120 &&
    postDaysNum >= 0 &&
    postDaysNum <= 120;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await runEventStudy({
          ticker: ticker.trim(),
          benchmark_ticker: benchmark.trim(),
          event_date: eventDate,
          event_name: eventName,
          model,
          estimation_window_days: estDaysNum,
          pre_event_days: preDaysNum,
          post_event_days: postDaysNum,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const rows = result?.rows ?? [];
  const arData = rows.map((r) => ({ rel: r.relative_day, ar: r.abnormal_return ?? 0 }));
  const carData = rows.map((r) => ({ rel: r.relative_day, car: r.cumulative_abnormal_return ?? 0 }));
  // Cumulative compounded asset vs benchmark return across the window.
  let cumA = 1;
  let cumB = 1;
  const cumData = rows.map((r) => {
    cumA *= 1 + (r.asset_return ?? 0);
    cumB *= 1 + (r.benchmark_return ?? 0);
    return { rel: r.relative_day, asset: cumA - 1, bench: cumB - 1 };
  });

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Event Study</p>
      <p className="text-xs text-slate-500">
        Abnormal return = asset return minus the model baseline (benchmark / estimation mean / market
        model). Cumulative abnormal return (CAR) sums abnormal returns across the window.
        Event windows are measured in trading observations around the event date.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Ticker"><input className={inputCls} value={ticker} onChange={(e) => setTicker(e.target.value)} /></Field>
        <Field label="Benchmark"><input className={inputCls} value={benchmark} onChange={(e) => setBenchmark(e.target.value)} /></Field>
        <Field label="Event date"><input type="date" className={inputCls} value={eventDate} onChange={(e) => setEventDate(e.target.value)} /></Field>
        <Field label="Event name"><input className={inputCls} value={eventName} onChange={(e) => setEventName(e.target.value)} /></Field>
        <Field label="Model">
          <select className={inputCls} value={model} onChange={(e) => setModel(e.target.value as AbnormalReturnModel)}>
            {MODEL_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </Field>
        <Field label="Estimation days"><input type="number" className={inputCls} value={estWindow} min={1} max={500} step={1} onChange={(e) => setEstWindow(e.target.value)} /></Field>
        <Field label="Pre-event days"><input type="number" className={inputCls} value={preDays} min={0} max={120} step={1} onChange={(e) => setPreDays(e.target.value)} /></Field>
        <Field label="Post-event days"><input type="number" className={inputCls} value={postDays} min={0} max={120} step={1} onChange={(e) => setPostDays(e.target.value)} /></Field>
      </div>

      <button
        type="button"
        onClick={run}
        disabled={!valid || loading}
        className={
          "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
          (valid && !loading
            ? "bg-[var(--accent)] text-[var(--on-accent)] shadow-[var(--accent-glow)] hover:brightness-110"
            : "cursor-not-allowed border border-[var(--line)] bg-[var(--glass)] text-slate-500")
        }
      >
        {loading ? "Running…" : "Run event study"}
      </button>
      <p className="text-[11px] text-slate-400">
        Sample events are for demo workflow only. Verify event dates before research use.
        Post-event CAR excludes day 0; event-day abnormal return is shown separately.
      </p>
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Event-day AR" value={pct(result.summary.event_day_abnormal_return)} />
            <Stat label="Pre-event CAR" value={pct(result.summary.pre_event_car)} />
            <Stat label="Post-event CAR (excl. day 0)" value={pct(result.summary.post_event_car)} />
            <Stat label="Total CAR" value={pct(result.summary.total_car)} />
            <Stat label="Model used" value={result.model_used.replace(/_/g, " ")} />
            <Stat label="Actual event date" value={result.summary.actual_event_date ?? "—"} />
            {result.alpha != null && <Stat label="Alpha (est.)" value={result.alpha.toFixed(5)} />}
            {result.beta != null && <Stat label="Beta (est.)" value={result.beta.toFixed(3)} />}
          </div>

          {result.warnings.length > 0 && (
            <div className="rounded-lg border border-[color-mix(in_oklch,var(--warn)_35%,transparent)] bg-[var(--warn-soft)] px-3 py-2 text-xs font-medium text-[var(--warn)]">
              {result.warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          )}

          {/* Abnormal return bars */}
          <div>
            <p className="section-title mb-1">Abnormal return by relative day</p>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={arData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="rel" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={56} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                <ReferenceLine y={0} stroke={CHART_REF_LINE} />
                <ReferenceLine x={0} stroke={CHART_REF_LINE} strokeDasharray="4 4" />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(3)}%`} formatLabel={(l) => (typeof l === "number" ? `Day ${l}` : "")} />} />
                <Bar dataKey="ar" name="Abnormal return" isAnimationActive={false}>
                  {arData.map((d) => (
                    <Cell key={d.rel} fill={d.ar >= 0 ? AR_POS : AR_NEG} />
                  ))}
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* CAR line */}
          <div>
            <p className="section-title mb-1">Cumulative abnormal return (CAR)</p>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={carData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="rel" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={56} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                <ReferenceLine y={0} stroke={CHART_REF_LINE} />
                <ReferenceLine x={0} stroke={CHART_REF_LINE} strokeDasharray="4 4" />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(2)}%`} formatLabel={(l) => (typeof l === "number" ? `Day ${l}` : "")} />} />
                <Line type="monotone" dataKey="car" name="CAR" stroke={CAR_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Asset vs benchmark cumulative */}
          <div>
            <p className="section-title mb-1">Asset vs benchmark cumulative return</p>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={cumData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="rel" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={56} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                <ReferenceLine y={0} stroke={CHART_REF_LINE} />
                <ReferenceLine x={0} stroke={CHART_REF_LINE} strokeDasharray="4 4" />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(2)}%`} formatLabel={(l) => (typeof l === "number" ? `Day ${l}` : "")} />} />
                <Line type="monotone" dataKey="asset" name={`${result.ticker} cumulative`} stroke={ASSET_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="bench" name={`${result.benchmark_ticker} cumulative`} stroke={BENCH_COLOR} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: ASSET_COLOR }}>● {result.ticker}</span>{"  "}
              <span style={{ color: BENCH_COLOR }}>— {result.benchmark_ticker}</span> (dashed). Day 0 = event.
            </p>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Day</th>
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Date</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Asset</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Benchmark</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Abnormal</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">CAR</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.relative_day} className={"border-t border-[var(--line)]" + (r.relative_day === 0 ? " bg-[var(--accent-softer)]" : "")}>
                    <td className="px-2 py-1 text-right mono">{r.relative_day}</td>
                    <td className="px-2 py-1">{r.date}</td>
                    <td className="px-2 py-1 text-right mono">{pct(r.asset_return, 2)}</td>
                    <td className="px-2 py-1 text-right mono">{pct(r.benchmark_return, 2)}</td>
                    <td className="px-2 py-1 text-right mono">{pct(r.abnormal_return, 2)}</td>
                    <td className="px-2 py-1 text-right mono">{pct(r.cumulative_abnormal_return, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ── Multi-Event ────────────────────────────────────────────────────────────

interface UiEventRow {
  event_name: string;
  ticker: string;
  event_date: string;
}

const DEFAULT_MULTI_ROWS: UiEventRow[] = [
  { event_name: "Event A", ticker: "AAPL", event_date: "2024-05-02" },
  { event_name: "Event B", ticker: "MSFT", event_date: "2024-04-25" },
];

function MultiEventTab() {
  const [rows, setRows] = useState<UiEventRow[]>(DEFAULT_MULTI_ROWS);
  const [benchmark, setBenchmark] = useState("SPY");
  const [model, setModel] = useState<AbnormalReturnModel>("market_adjusted");
  const [estWindow, setEstWindow] = useState("120");
  const [preDays, setPreDays] = useState("10");
  const [postDays, setPostDays] = useState("10");
  const [result, setResult] = useState<MultiEventStudyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sampleNote, setSampleNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sampleLoading, setSampleLoading] = useState(false);
  const estDaysNum = intNum(estWindow);
  const preDaysNum = intNum(preDays);
  const postDaysNum = intNum(postDays);

  const valid =
    rows.length >= 1 &&
    rows.length <= 20 &&
    rows.every((r) => r.ticker.trim() !== "" && /^\d{4}-\d{2}-\d{2}$/.test(r.event_date)) &&
    benchmark.trim() !== "" &&
    estDaysNum >= 1 &&
    estDaysNum <= 500 &&
    preDaysNum >= 0 &&
    preDaysNum <= 120 &&
    postDaysNum >= 0 &&
    postDaysNum <= 120;

  function setRow(i: number, patch: Partial<UiEventRow>) {
    setRows((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }
  function addRow() {
    setRows((ls) =>
      ls.length >= 20
        ? ls
        : [...ls, { event_name: `Event ${ls.length + 1}`, ticker: "AAPL", event_date: "2024-05-02" }],
    );
  }
  function removeRow(i: number) {
    setRows((ls) => (ls.length > 1 ? ls.filter((_, idx) => idx !== i) : ls));
  }

  async function loadSample() {
    setSampleLoading(true);
    setError(null);
    try {
      const s = await fetchSampleEvents();
      setRows(s.events.map((e) => ({ event_name: e.event_name, ticker: e.ticker, event_date: e.event_date })));
      if (s.events[0]) setBenchmark(s.events[0].benchmark_ticker);
      setSampleNote(s.note);
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setSampleLoading(false);
    }
  }

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await runMultiEventStudy({
          events: rows.map((r) => ({ event_name: r.event_name, ticker: r.ticker.trim(), event_date: r.event_date })),
          benchmark_ticker: benchmark.trim(),
          model,
          estimation_window_days: estDaysNum,
          pre_event_days: preDaysNum,
          post_event_days: postDaysNum,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const caarData =
    result?.aar_curve.map((p) => ({
      rel: p.relative_day,
      aar: p.average_abnormal_return ?? 0,
      caar: p.average_cumulative_abnormal_return ?? 0,
    })) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Multi-Event Study (CAAR)</p>
      <p className="text-xs text-slate-500">
        Aligns several events by relative day and averages the abnormal returns — average abnormal
        return (AAR) and cumulative average abnormal return (CAAR). Event windows are measured in
        trading observations around each event date.
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={loadSample}
          disabled={sampleLoading}
          className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:border-blue-400"
        >
          {sampleLoading ? "Loading…" : "Load sample events"}
        </button>
        <Field label="Benchmark"><input className={inputCls + " w-24"} value={benchmark} onChange={(e) => setBenchmark(e.target.value)} /></Field>
        <Field label="Model">
          <select className={inputCls} value={model} onChange={(e) => setModel(e.target.value as AbnormalReturnModel)}>
            {MODEL_OPTIONS.map((m) => (<option key={m.value} value={m.value}>{m.label}</option>))}
          </select>
        </Field>
        <Field label="Estimation days"><input type="number" className={inputCls + " w-24"} value={estWindow} min={1} max={500} step={1} onChange={(e) => setEstWindow(e.target.value)} /></Field>
        <Field label="Pre days"><input type="number" className={inputCls + " w-20"} value={preDays} min={0} max={120} step={1} onChange={(e) => setPreDays(e.target.value)} /></Field>
        <Field label="Post days"><input type="number" className={inputCls + " w-20"} value={postDays} min={0} max={120} step={1} onChange={(e) => setPostDays(e.target.value)} /></Field>
      </div>
      {sampleNote && <p className="text-[11px] text-slate-400">{sampleNote}</p>}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400">
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Event name</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Ticker</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Event date</th>
              <th className="px-2 py-1"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-[var(--line)]">
                <td className="px-2 py-1"><input className={inputCls} value={r.event_name} onChange={(e) => setRow(i, { event_name: e.target.value })} /></td>
                <td className="px-2 py-1"><input className={inputCls + " w-24"} value={r.ticker} onChange={(e) => setRow(i, { ticker: e.target.value })} /></td>
                <td className="px-2 py-1"><input type="date" className={inputCls} value={r.event_date} onChange={(e) => setRow(i, { event_date: e.target.value })} /></td>
                <td className="px-2 py-1"><button type="button" onClick={() => removeRow(i)} className="text-slate-400 hover:text-red-600" title="Remove">✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          type="button"
          onClick={addRow}
          disabled={rows.length >= 20}
          className={
            "mt-1 rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium " +
            (rows.length >= 20 ? "cursor-not-allowed text-slate-400" : "text-slate-600 hover:border-blue-400")
          }
        >
          + Add event
        </button>
      </div>

      <button
        type="button"
        onClick={run}
        disabled={!valid || loading}
        className={
          "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
            (valid && !loading
              ? "bg-[var(--accent)] text-[var(--on-accent)] shadow-[var(--accent-glow)] hover:brightness-110"
              : "cursor-not-allowed border border-[var(--line)] bg-[var(--glass)] text-slate-500")
        }
      >
        {loading ? "Running…" : "Run multi-event study"}
      </button>
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat label="Events" value={String(result.event_count)} />
            <Stat label="Average total CAR" value={pct(result.average_total_car)} />
            <Stat label="Window points" value={String(result.aar_curve.length)} />
          </div>
          {result.warnings.length > 0 && (
            <div className="rounded-lg border border-[color-mix(in_oklch,var(--warn)_35%,transparent)] bg-[var(--warn-soft)] px-3 py-2 text-xs font-medium text-[var(--warn)]">
              {result.warnings.map((w, i) => (<p key={i}>{w}</p>))}
            </div>
          )}
          <div>
            <p className="section-title mb-1">CAAR — average cumulative abnormal return</p>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={caarData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="rel" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={56} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                <ReferenceLine y={0} stroke={CHART_REF_LINE} />
                <ReferenceLine x={0} stroke={CHART_REF_LINE} strokeDasharray="4 4" />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(2)}%`} formatLabel={(l) => (typeof l === "number" ? `Day ${l}` : "")} />} />
                <Bar dataKey="aar" name="AAR" fill={ASSET_COLOR} fillOpacity={0.35} isAnimationActive={false} />
                <Line type="monotone" dataKey="caar" name="CAAR" stroke={CAR_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {result.per_event.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-400">
                    <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Event</th>
                    <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Ticker</th>
                    <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Event date</th>
                    <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Total CAR</th>
                  </tr>
                </thead>
                <tbody>
                  {result.per_event.map((e, i) => (
                    <tr key={i} className="border-t border-[var(--line)]">
                      <td className="px-2 py-1">{e.event_name}</td>
                      <td className="px-2 py-1">{e.ticker}</td>
                      <td className="px-2 py-1">{e.actual_event_date ?? "—"}</td>
                      <td className="px-2 py-1 text-right mono">{e.error ? `⚠ ${e.error}` : pct(e.total_car)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Merger Arb ─────────────────────────────────────────────────────────────

function MergerArbTab() {
  const [current, setCurrent] = useState("90");
  const [offer, setOffer] = useState("100");
  const [downside, setDownside] = useState("70");
  const [prob, setProb] = useState("0.8");
  const [days, setDays] = useState("180");
  const [result, setResult] = useState<MergerArbResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid =
    num(current) > 0 &&
    num(offer) > 0 &&
    num(downside) >= 0 &&
    finite(prob) &&
    num(prob) >= 0 &&
    num(prob) <= 1 &&
    num(days) > 0;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await computeMergerArb({
          current_price: num(current),
          offer_price: num(offer),
          downside_price: num(downside),
          probability_close: num(prob),
          expected_days_to_close: num(days),
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Merger Arbitrage Calculator</p>
      <p className="text-xs text-slate-500">
        Simplified expected-value economics for a cash deal. Ignores borrow/financing costs,
        regulatory timing, competing bids, taxes, liquidity, and detailed deal terms — not a full
        merger-arbitrage model and not investment advice.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Field label="Current price"><input type="number" className={inputCls} value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>
        <Field label="Offer price"><input type="number" className={inputCls} value={offer} onChange={(e) => setOffer(e.target.value)} /></Field>
        <Field label="Downside price"><input type="number" className={inputCls} value={downside} onChange={(e) => setDownside(e.target.value)} /></Field>
        <Field label="P(close) 0–1"><input type="number" className={inputCls} value={prob} step={0.05} onChange={(e) => setProb(e.target.value)} /></Field>
        <Field label="Days to close"><input type="number" className={inputCls} value={days} onChange={(e) => setDays(e.target.value)} /></Field>
      </div>

      <button
        type="button"
        onClick={run}
        disabled={!valid || loading}
        className={
          "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
          (valid && !loading
            ? "bg-[var(--accent)] text-[var(--on-accent)] shadow-[var(--accent-glow)] hover:brightness-110"
            : "cursor-not-allowed border border-[var(--line)] bg-[var(--glass)] text-slate-500")
        }
      >
        {loading ? "Computing…" : "Compute"}
      </button>
      {!valid && (
        <p className="text-[11px] text-slate-400">
          Prices positive (downside ≥ 0), probability between 0 and 1, days &gt; 0.
        </p>
      )}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Spread" value={result.spread.toFixed(2)} />
            <Stat label="Gross upside" value={pct(result.gross_upside_pct)} />
            <Stat label="Expected return" value={pct(result.expected_return)} />
            <Stat label="Annualized exp. return" value={pct(result.annualized_expected_return)} />
            <Stat label="Expected exit price" value={result.expected_exit_price.toFixed(2)} />
            <Stat label="Downside loss" value={pct(result.downside_loss_pct)} />
            <Stat label="Breakeven P(close)" value={pct(result.breakeven_probability)} />
          </div>
          <div className="rounded-lg border border-[color-mix(in_oklch,var(--warn)_35%,transparent)] bg-[var(--warn-soft)] px-3 py-2 text-[11px] text-[var(--warn)]">
            {result.warnings.map((w, i) => (<p key={i}>{w}</p>))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Education ──────────────────────────────────────────────────────────────

function EducationTab() {
  const items: [string, string][] = [
    ["Event leakage", "Prices often move before the announcement as information leaks; the event date may understate the true reaction."],
    ["Look-ahead bias", "Use point-in-time event dates. Backfilled or restated dates can contaminate the study."],
    ["Sample selection bias", "Cherry-picking events (e.g. only big movers) inflates apparent abnormal returns."],
    ["Benchmark choice", "Abnormal return depends on the benchmark/model; a poor benchmark biases the result."],
    ["Confounding events", "Other news in the window (guidance, macro prints) contaminates the measured reaction."],
    ["Transaction costs & liquidity", "Spreads, slippage, and limited liquidity can erase paper abnormal returns."],
    ["Deal-break risk", "Merger spreads exist because deals can break; the downside is real and often sudden."],
    ["Regulatory & timing risk", "Antitrust review, financing, and shareholder votes shift both probability and timing of close."],
  ];
  return (
    <div className="card space-y-3 p-5 text-sm text-slate-600">
      <p className="section-title">How to read the Event Lab</p>
      <p>
        An <span className="font-semibold text-slate-700">event study</span> measures the return a
        stock earned around an event beyond what its benchmark/model predicted (the abnormal
        return), then accumulates it (CAR). Across many events, averaging gives the CAAR.
      </p>
      <ul className="space-y-2">
        {items.map(([title, body]) => (
          <li key={title}>
            <span className="font-semibold text-slate-700">{title}:</span> {body}
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-slate-400">{CAVEAT}</p>
    </div>
  );
}
