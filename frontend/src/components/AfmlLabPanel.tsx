"use client";

import { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Bar,
  Cell,
  Line,
  Scatter,
  ReferenceLine,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { BacktestApiError, runLabelingDemo, runPurgedCvDemo, runSequentialBootstrapDemo } from "@/lib/api";
import type { LabelingDemoResponse, PurgedCvResponse, SequentialBootstrapResponse, ThresholdMode } from "@/lib/types";
import MetricCard from "@/components/MetricCard";
import NeonTooltip from "@/components/charts/NeonTooltip";
import { CHART_AXIS, CHART_AXIS_LINE, CHART_GRID, CHART_REF_LINE, DANGER } from "@/components/charts/chartTheme";
import { seriesColor } from "@/lib/chartPalette";

type Tab = "cusum" | "labeling" | "uniqueness" | "purgedcv" | "seqboot" | "education";

// Purged-CV role colors (distinct: train blue, test violet, purged amber, embargo red).
const TRAIN_COLOR = seriesColor(1); // blue
const TEST_COLOR = seriesColor(2); // violet
const PURGE_COLOR = seriesColor(4); // amber
const EMBARGO_COLOR = DANGER; // red

const inputCls = "ql-input px-2.5 py-1.5";
const labelCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400";

const PRICE_COLOR = seriesColor(0); // cyan
const POS_COLOR = "var(--emerald)";
const NEG_COLOR = DANGER;
const NEUTRAL_COLOR = seriesColor(4); // amber
const CONC_COLOR = seriesColor(2); // violet
const UNIQ_COLOR = seriesColor(0);

const CAVEAT =
  "Financial ML results depend on correct event definitions, barrier choices, volatility estimates, " +
  "data quality, purging/embargo, and out-of-sample validation. Synthetic demo data — not live market " +
  "data, not a trained model, not investment advice.";

function num(s: string): number {
  return s.trim() === "" ? NaN : Number(s);
}
function fmt(v: number | null | undefined, d = 3): string {
  return v == null || !Number.isFinite(v) ? "—" : v.toFixed(d);
}
function pct(v: number | null | undefined, d = 2): string {
  return v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`;
}
function labelColor(l: number): string {
  return l > 0 ? POS_COLOR : l < 0 ? NEG_COLOR : NEUTRAL_COLOR;
}
const toTs = (d: string) => Date.parse(d);
const fmtTs = (ms: number) => (Number.isFinite(ms) ? new Date(ms).toISOString().slice(0, 10) : "");

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className={labelCls}>{label}</span>
      {children}
    </label>
  );
}

interface UiInputs {
  nDays: string;
  startPrice: string;
  driftPct: string;
  volPct: string;
  thresholdPct: string;
  thresholdMode: ThresholdMode;
  volWindow: string;
  profitTake: string;
  stopLoss: string;
  verticalDays: string;
  seed: string;
}
const DEFAULTS: UiInputs = {
  nDays: "500",
  startPrice: "100",
  driftPct: "0.02",
  volPct: "1.5",
  thresholdPct: "2",
  thresholdMode: "fixed",
  volWindow: "20",
  profitTake: "1.5",
  stopLoss: "1.0",
  verticalDays: "10",
  seed: "42",
};

export default function AfmlLabPanel({ initialTab = "cusum" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [inp, setInp] = useState<UiInputs>(DEFAULTS);
  const [result, setResult] = useState<LabelingDemoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<number | null>(null);

  // Purged CV (own inputs + result, reuses the shared labeling params above).
  const [nSplits, setNSplits] = useState("5");
  const [embargoPct, setEmbargoPct] = useState("0.01");
  const [cvResult, setCvResult] = useState<PurgedCvResponse | null>(null);
  const [cvError, setCvError] = useState<string | null>(null);
  const [cvLoading, setCvLoading] = useState(false);
  const [selectedFold, setSelectedFold] = useState(0);

  // Sequential bootstrap (own inputs + result, reuses the shared labeling params).
  const [sampleSize, setSampleSize] = useState("25");
  const [randomTrials, setRandomTrials] = useState("200");
  const [withReplacement, setWithReplacement] = useState(false);
  const [sbResult, setSbResult] = useState<SequentialBootstrapResponse | null>(null);
  const [sbError, setSbError] = useState<string | null>(null);
  const [sbLoading, setSbLoading] = useState(false);

  function set<K extends keyof UiInputs>(key: K, value: UiInputs[K]) {
    setInp((s) => ({ ...s, [key]: value }));
    setError(null);
    setCvError(null);
  }

  async function runCv() {
    if (cvLoading) return;
    const ns = num(nSplits);
    const emb = num(embargoPct);
    if (!valid) {
      setCvError("Fix the shared Setup values before running purged CV.");
      return;
    }
    if (!Number.isInteger(ns) || ns < 2 || ns > 20) {
      setCvError("Number of folds must be a whole number between 2 and 20.");
      return;
    }
    if (!Number.isFinite(emb) || emb < 0 || emb > 0.2) {
      setCvError("Embargo fraction must be between 0 and 0.2.");
      return;
    }
    setCvLoading(true);
    setCvError(null);
    setCvResult(null);
    setSelectedFold(0);
    try {
      const res = await runPurgedCvDemo({
        n_days: num(inp.nDays),
        start_price: num(inp.startPrice),
        drift: num(inp.driftPct) / 100,
        volatility: num(inp.volPct) / 100,
        seed: inp.seed.trim() === "" ? null : num(inp.seed),
        cusum_threshold:
          inp.thresholdMode === "fixed" ? num(inp.thresholdPct) / 100 : num(inp.thresholdPct),
        threshold_mode: inp.thresholdMode,
        volatility_window: num(inp.volWindow),
        profit_take_multiple: num(inp.profitTake),
        stop_loss_multiple: num(inp.stopLoss),
        vertical_barrier_days: num(inp.verticalDays),
        n_splits: ns,
        embargo_pct: emb,
      });
      setCvResult(res);
    } catch (e) {
      setCvError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setCvLoading(false);
    }
  }

  async function runSb() {
    if (sbLoading) return;
    const ss = num(sampleSize);
    const rt = num(randomTrials);
    if (!valid || !Number.isInteger(ss) || ss < 1 || !Number.isInteger(rt) || rt < 1 || rt > 1000) return;
    setSbLoading(true);
    setSbError(null);
    setSbResult(null);
    try {
      const res = await runSequentialBootstrapDemo({
        n_days: num(inp.nDays),
        start_price: num(inp.startPrice),
        drift: num(inp.driftPct) / 100,
        volatility: num(inp.volPct) / 100,
        seed: inp.seed.trim() === "" ? null : num(inp.seed),
        cusum_threshold: num(inp.thresholdPct) / 100,
        threshold_mode: inp.thresholdMode,
        volatility_window: num(inp.volWindow),
        profit_take_multiple: num(inp.profitTake),
        stop_loss_multiple: num(inp.stopLoss),
        vertical_barrier_days: num(inp.verticalDays),
        sample_size: ss,
        random_trials: rt,
        with_replacement: withReplacement,
      });
      setSbResult(res);
    } catch (e) {
      setSbError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setSbLoading(false);
    }
  }

  const thresholdRaw = num(inp.thresholdPct);
  const seedValue = num(inp.seed);
  const seedValid = inp.seed.trim() === "" || (Number.isInteger(seedValue) && seedValue >= 0);
  const nDays = num(inp.nDays);
  const valid =
    Number.isInteger(num(inp.nDays)) && num(inp.nDays) >= 50 && num(inp.nDays) <= 5000 &&
    num(inp.startPrice) > 0 && num(inp.startPrice) <= 1_000_000_000 &&
    Number.isFinite(num(inp.driftPct)) && Math.abs(num(inp.driftPct)) <= 100 &&
    num(inp.volPct) > 0 && num(inp.volPct) <= 100 &&
    thresholdRaw > 0 && (inp.thresholdMode === "fixed" ? thresholdRaw <= 1000 : thresholdRaw <= 10) &&
    Number.isInteger(num(inp.volWindow)) && num(inp.volWindow) >= 2 && num(inp.volWindow) < nDays &&
    num(inp.profitTake) > 0 && num(inp.profitTake) <= 100 &&
    num(inp.stopLoss) > 0 && num(inp.stopLoss) <= 100 &&
    Number.isInteger(num(inp.verticalDays)) && num(inp.verticalDays) >= 1 && num(inp.verticalDays) < nDays &&
    seedValid;
  const cvNSplits = num(nSplits);
  const cvEmbargo = num(embargoPct);
  const cvValid =
    valid && Number.isInteger(cvNSplits) && cvNSplits >= 2 && cvNSplits <= 20 &&
    Number.isFinite(cvEmbargo) && cvEmbargo >= 0 && cvEmbargo <= 0.2;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedEvent(null);
    try {
      const res = await runLabelingDemo({
        n_days: num(inp.nDays),
        start_price: num(inp.startPrice),
        drift: num(inp.driftPct) / 100,
        volatility: num(inp.volPct) / 100,
        seed: inp.seed.trim() === "" ? null : num(inp.seed),
        cusum_threshold: inp.thresholdMode === "fixed" ? thresholdRaw / 100 : thresholdRaw,
        threshold_mode: inp.thresholdMode,
        volatility_window: num(inp.volWindow),
        profit_take_multiple: num(inp.profitTake),
        stop_loss_multiple: num(inp.stopLoss),
        vertical_barrier_days: num(inp.verticalDays),
      });
      setResult(res);
      if (res.labels.length) setSelectedEvent(res.labels[0].event_id);
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  // Single time-indexed data array: close line + positive/negative event markers.
  const priceChartData = useMemo(() => {
    if (!result) return [];
    const map = new Map<number, Record<string, number>>();
    for (const p of result.price_series) map.set(toTs(p.date), { t: toTs(p.date), close: p.close });
    for (const e of result.events) {
      const t = toTs(e.date);
      const row = map.get(t) ?? { t };
      row[e.side_hint === "positive" ? "posEvent" : "negEvent"] = e.price_at_event;
      map.set(t, row);
    }
    return Array.from(map.values()).sort((a, b) => a.t - b.t);
  }, [result]);

  const concData = useMemo(
    () => (result ? result.concurrency.map((c) => ({ t: toTs(c.date), concurrency: c.concurrency })) : []),
    [result],
  );

  const labelDist = result
    ? [
        { name: "Profit-take (+1)", count: result.summary.positive_labels, color: POS_COLOR },
        { name: "Stop-loss (−1)", count: result.summary.negative_labels, color: NEG_COLOR },
        { name: "Vertical / 0", count: result.summary.zero_labels, color: NEUTRAL_COLOR },
      ]
    : [];

  // Uniqueness histogram (10 bins over [0, 1]).
  const uniqHist = useMemo(() => {
    if (!result) return [];
    const bins = new Array(10).fill(0);
    for (const w of result.weights) {
      const b = Math.min(9, Math.max(0, Math.floor(w.average_uniqueness * 10)));
      bins[b] += 1;
    }
    return bins.map((count, i) => ({ bucket: `${(i / 10).toFixed(1)}`, count }));
  }, [result]);

  const selected = result?.labels.find((l) => l.event_id === selectedEvent) ?? null;

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-300">
          The AFML Methodology Lab demonstrates the <span className="font-medium">labeling and validation-splitting pipeline</span>{" "}
          that must come before financial-ML model training: CUSUM event sampling, triple-barrier
          labeling, sample concurrency, overlap-aware uniqueness weights, and purged K-fold with embargo.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      {/* Shared setup */}
      <div className="card space-y-4 p-5">
        <p className="section-title">Setup</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Field label="Days"><input type="number" className={inputCls} value={inp.nDays} step={50} onChange={(e) => set("nDays", e.target.value)} /></Field>
          <Field label="Start price"><input type="number" className={inputCls} value={inp.startPrice} onChange={(e) => set("startPrice", e.target.value)} /></Field>
          <Field label="Daily drift (%)"><input type="number" className={inputCls} value={inp.driftPct} step={0.01} onChange={(e) => set("driftPct", e.target.value)} /></Field>
          <Field label="Daily vol (%)"><input type="number" className={inputCls} value={inp.volPct} step={0.25} onChange={(e) => set("volPct", e.target.value)} /></Field>
          <Field label={inp.thresholdMode === "fixed" ? "CUSUM threshold (%)" : "CUSUM vol multiplier"}>
            <input type="number" className={inputCls} value={inp.thresholdPct} step={0.5} onChange={(e) => set("thresholdPct", e.target.value)} />
          </Field>
          <Field label="Threshold mode">
            <select className={inputCls} value={inp.thresholdMode} onChange={(e) => set("thresholdMode", e.target.value as ThresholdMode)}>
              <option value="fixed">fixed</option>
              <option value="vol_scaled">vol-scaled</option>
            </select>
          </Field>
          <Field label="Vol window"><input type="number" className={inputCls} value={inp.volWindow} step={1} onChange={(e) => set("volWindow", e.target.value)} /></Field>
          <Field label="Profit-take ×"><input type="number" className={inputCls} value={inp.profitTake} step={0.25} onChange={(e) => set("profitTake", e.target.value)} /></Field>
          <Field label="Stop-loss ×"><input type="number" className={inputCls} value={inp.stopLoss} step={0.25} onChange={(e) => set("stopLoss", e.target.value)} /></Field>
          <Field label="Vertical days"><input type="number" className={inputCls} value={inp.verticalDays} step={1} onChange={(e) => set("verticalDays", e.target.value)} /></Field>
          <Field label="Seed"><input type="number" className={inputCls} value={inp.seed} step={1} onChange={(e) => set("seed", e.target.value)} /></Field>
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
          {loading ? "Running…" : "Run labeling demo"}
        </button>
        {!valid && (
          <p className="text-[11px] text-slate-400">
            Days 50–5000, start price &gt; 0, drift within ±100%, daily vol 0–100%,
            fixed CUSUM threshold 0–1000% or vol multiplier 0–10, vol window 2–days,
            positive barrier multiples ≤ 100, vertical days 1–days, optional seed ≥ 0.
          </p>
        )}
        {error && <p className="text-xs text-red-400">⚠ {error}</p>}
        {result && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            <MetricCard label="Days" value={String(result.summary.n_days)} />
            <MetricCard label="Events" value={String(result.summary.n_events)} tone="accent" />
            <MetricCard label="Profit-take (+1)" value={String(result.summary.positive_labels)} tone="positive" />
            <MetricCard label="Stop-loss (−1)" value={String(result.summary.negative_labels)} tone="danger" />
            <MetricCard label="Vertical / 0" value={String(result.summary.zero_labels)} tone="warn" />
            <MetricCard label="Mean uniqueness" value={fmt(result.summary.mean_uniqueness)} />
            <MetricCard label="Avg holding (days)" value={fmt(result.summary.average_holding_period, 1)} />
          </div>
        )}
      </div>

      <div className="ql-segmented">
        {(
          [
            ["cusum", "CUSUM Sampling"],
            ["labeling", "Triple-Barrier"],
            ["uniqueness", "Sample Uniqueness"],
            ["purgedcv", "Purged CV"],
            ["seqboot", "Sequential Bootstrap"],
            ["education", "Education"],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id)} className={"ql-segmented-option " + (tab === id ? "active" : "")}>
            {label}
          </button>
        ))}
      </div>

      {/* CUSUM */}
      {tab === "cusum" && result && (
        <div className="card space-y-2 p-5">
          <p className="section-title">Synthetic path with CUSUM event markers — {result.summary.n_events} events</p>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={priceChartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
              <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} scale="time" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={fmtTs} minTickGap={48} />
              <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} domain={["auto", "auto"]} />
              <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(2)} formatLabel={(l) => (typeof l === "number" ? fmtTs(l) : "")} />} />
              <Line type="monotone" dataKey="close" name="Close" stroke={PRICE_COLOR} strokeWidth={1.6} dot={false} connectNulls isAnimationActive={false} />
              <Scatter dataKey="posEvent" name="Up event" fill={POS_COLOR} isAnimationActive={false} />
              <Scatter dataKey="negEvent" name="Down event" fill={NEG_COLOR} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <p className="text-[11px] text-slate-400">
            <span style={{ color: POS_COLOR }}>● Up-side CUSUM event</span>{"  "}
            <span style={{ color: NEG_COLOR }}>● Down-side CUSUM event</span> — events fire only when cumulative movement breaches the threshold.
          </p>
          <div className="max-h-72 overflow-auto">
            <table className="w-full max-w-xl text-xs">
              <thead><tr className="text-slate-400">
                <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">#</th>
                <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Date</th>
                <th className="px-2 py-1 text-center font-medium uppercase tracking-wide">Side</th>
                <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Return</th>
                <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Price</th>
              </tr></thead>
              <tbody>
                {result.events.map((e) => (
                  <tr key={e.event_id} className="border-t border-[var(--line)]">
                    <td className="px-2 py-1 text-right mono">{e.event_id}</td>
                    <td className="px-2 py-1 text-left mono">{e.date}</td>
                    <td className="px-2 py-1 text-center font-semibold" style={{ color: e.side_hint === "positive" ? POS_COLOR : NEG_COLOR }}>{e.side_hint}</td>
                    <td className="px-2 py-1 text-right mono">{pct(e.return_at_event)}</td>
                    <td className="px-2 py-1 text-right mono">{e.price_at_event.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Triple-Barrier */}
      {tab === "labeling" && result && (
        <>
          <div className="card space-y-2 p-5">
            <p className="section-title">Label distribution</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={labelDist} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={44} allowDecimals={false} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => String(v)} />} />
                <Bar dataKey="count" name="Labels" isAnimationActive={false}>
                  {labelDist.map((d, i) => (<Cell key={i} fill={d.color} />))}
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {selected && (
            <div className="card space-y-2 p-5">
              <p className="section-title">
                Barriers for event #{selected.event_id} — {selected.touched_barrier} → label{" "}
                <span style={{ color: labelColor(selected.label) }}>{selected.label > 0 ? "+1" : selected.label}</span>
              </p>
              <ResponsiveContainer width="100%" height={240}>
                <ComposedChart data={priceChartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} scale="time" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={fmtTs} minTickGap={48} />
                  <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} domain={["auto", "auto"]} />
                  <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(2)} formatLabel={(l) => (typeof l === "number" ? fmtTs(l) : "")} />} />
                  <Line type="monotone" dataKey="close" name="Close" stroke={PRICE_COLOR} strokeWidth={1.4} dot={false} connectNulls isAnimationActive={false} />
                  <ReferenceLine y={selected.upper_barrier} stroke={POS_COLOR} strokeDasharray="5 4" />
                  <ReferenceLine y={selected.lower_barrier} stroke={NEG_COLOR} strokeDasharray="5 4" />
                  <ReferenceLine x={toTs(selected.start_date)} stroke={CHART_REF_LINE} />
                  <ReferenceLine x={toTs(selected.end_date)} stroke={NEUTRAL_COLOR} strokeDasharray="3 3" />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="text-[11px] text-slate-400">
                <span style={{ color: POS_COLOR }}>– – Upper (profit-take)</span>{"  "}
                <span style={{ color: NEG_COLOR }}>– – Lower (stop-loss)</span>{"  "}
                <span style={{ color: NEUTRAL_COLOR }}>– – Vertical / end</span>. Click a row below to inspect another event.
              </p>
            </div>
          )}

          <div className="card space-y-2 p-5">
            <p className="section-title">Labels</p>
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-xs">
                <thead><tr className="text-slate-400">
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">#</th>
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Start</th>
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">End</th>
                  <th className="px-2 py-1 text-center font-medium uppercase tracking-wide">Label</th>
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Touched</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Realized</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Hold</th>
                </tr></thead>
                <tbody>
                  {result.labels.map((l) => (
                    <tr
                      key={l.event_id}
                      onClick={() => setSelectedEvent(l.event_id)}
                      className={"cursor-pointer border-t border-[var(--line)] " + (l.event_id === selectedEvent ? "bg-[var(--accent-softer)]" : "")}
                    >
                      <td className="px-2 py-1 text-right mono">{l.event_id}</td>
                      <td className="px-2 py-1 text-left mono">{l.start_date}</td>
                      <td className="px-2 py-1 text-left mono">{l.end_date}</td>
                      <td className="px-2 py-1 text-center font-semibold" style={{ color: labelColor(l.label) }}>{l.label > 0 ? "+1" : l.label}</td>
                      <td className="px-2 py-1 text-left">{l.touched_barrier}</td>
                      <td className="px-2 py-1 text-right mono">{pct(l.realized_return)}</td>
                      <td className="px-2 py-1 text-right mono">{l.holding_period_days}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Sample Uniqueness */}
      {tab === "uniqueness" && result && (
        <>
          <div className="card space-y-2 p-5">
            <p className="section-title">Label concurrency over time (overlapping labels)</p>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={concData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} scale="time" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={fmtTs} minTickGap={48} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={40} allowDecimals={false} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => String(v)} formatLabel={(l) => (typeof l === "number" ? fmtTs(l) : "")} />} />
                <Area type="stepAfter" dataKey="concurrency" name="Concurrency" stroke={CONC_COLOR} fill={CONC_COLOR} fillOpacity={0.18} strokeWidth={1.5} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">Higher concurrency → more overlapping labels → lower per-sample uniqueness.</p>
          </div>

          <div className="card space-y-2 p-5">
            <p className="section-title">Average-uniqueness distribution</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={uniqHist} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="bucket" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={40} allowDecimals={false} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => String(v)} />} />
                <Bar dataKey="count" name="Events" fill={UNIQ_COLOR} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="card space-y-2 p-5">
            <p className="section-title">Sample weights (uniqueness, normalized to mean 1)</p>
            <div className="max-h-80 overflow-auto">
              <table className="w-full max-w-lg text-xs">
                <thead><tr className="text-slate-400">
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Event</th>
                  <th className="px-2 py-1 text-center font-medium uppercase tracking-wide">Label</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Avg uniqueness</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Sample weight</th>
                </tr></thead>
                <tbody>
                  {result.weights.map((w) => (
                    <tr key={w.event_id} className="border-t border-[var(--line)]">
                      <td className="px-2 py-1 text-right mono">{w.event_id}</td>
                      <td className="px-2 py-1 text-center font-semibold" style={{ color: labelColor(w.label) }}>{w.label > 0 ? "+1" : w.label}</td>
                      <td className="px-2 py-1 text-right mono">{fmt(w.average_uniqueness)}</td>
                      <td className="px-2 py-1 text-right mono">{fmt(w.sample_weight)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Purged CV */}
      {tab === "purgedcv" && (
        <>
          <div className="card space-y-3 p-5">
            <p className="section-title">Purged K-Fold + Embargo CV</p>
            <p className="text-xs text-slate-500">
              Reuses the synthetic path and triple-barrier labels from the Setup above, then forms
              purged K-fold splits with an embargo. Purging removes train labels whose intervals
              overlap the test fold; the embargo also removes train labels starting just after it.
              “Overlap before” is the leakage-prone, contiguous standard K-fold baseline: no shuffle,
              purging, or embargo.
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Number of folds"><input type="number" className={inputCls + " w-28"} value={nSplits} step={1} onChange={(e) => { setNSplits(e.target.value); setCvError(null); }} /></Field>
              <Field label="Embargo (fraction)"><input type="number" className={inputCls + " w-28"} value={embargoPct} step={0.005} onChange={(e) => { setEmbargoPct(e.target.value); setCvError(null); }} /></Field>
              <button
                type="button"
                onClick={runCv}
                disabled={!cvValid || cvLoading}
                className={
                  "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
                  (cvValid && !cvLoading
                    ? "bg-[var(--accent)] text-[var(--on-accent)] shadow-[var(--accent-glow)] hover:brightness-110"
                    : "cursor-not-allowed border border-[var(--line)] bg-[var(--glass)] text-slate-500")
                }
              >
                {cvLoading ? "Running…" : "Run purged CV"}
              </button>
            </div>
            <p className="text-[11px] text-slate-400">
              Folds 2–20. Embargo is 0–0.2 of the full synthetic history and is rounded up to whole trading observations. Other parameters come from Setup.
            </p>
            {!cvValid && (
              <p className="text-[11px] text-amber-400">
                Enter valid Setup values, a whole-number fold count from 2 to 20, and an embargo fraction from 0 to 0.2.
              </p>
            )}
            {cvError && <p className="text-xs text-red-400">⚠ {cvError}</p>}
          </div>

          {cvResult && (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
                <MetricCard label="Labeled events" value={String(cvResult.summary.n_events)} />
                <MetricCard label="Folds" value={String(cvResult.summary.n_splits)} tone="accent" />
                <MetricCard label="Total purged" value={String(cvResult.summary.total_purged)} tone="warn" />
                <MetricCard label="Total embargoed" value={String(cvResult.summary.total_embargoed)} tone="danger" />
                <MetricCard label="Overlaps (before)" value={String(cvResult.summary.total_overlap_before_purge)} tone="warn" />
                <MetricCard label="Overlaps (after purge)" value={String(cvResult.summary.total_overlap_after_purge)} tone={cvResult.summary.total_overlap_after_purge === 0 ? "positive" : "danger"} />
                <MetricCard label="Avg train remaining" value={pct(cvResult.summary.average_train_fraction_remaining, 1)} />
              </div>

              {/* Fold timeline */}
              <div className="card space-y-2 p-5">
                <p className="section-title">
                  Fold timeline — fold {selectedFold + 1} of {cvResult.summary.n_splits}
                </p>
                {(() => {
                  const fold = cvResult.folds[selectedFold];
                  if (!fold) return null;
                  const maxIdx = Math.max(
                    ...cvResult.timeline.map((t) => t.end_index),
                    fold.embargo_end_index ?? 0,
                    1,
                  );
                  const trainSet = new Set(fold.train_event_ids);
                  const testSet = new Set(fold.test_event_ids);
                  const purgedSet = new Set(fold.purged_event_ids);
                  const embSet = new Set(fold.embargoed_event_ids);
                  const n = cvResult.timeline.length;
                  const rowH = Math.max(1.5, Math.min(5, 360 / Math.max(1, n)));
                  const H = n * rowH;
                  const roleColor = (id: number) =>
                    testSet.has(id) ? TEST_COLOR : purgedSet.has(id) ? PURGE_COLOR : embSet.has(id) ? EMBARGO_COLOR : trainSet.has(id) ? TRAIN_COLOR : CHART_AXIS_LINE;
                  return (
                    <svg viewBox={`0 0 1000 ${H}`} preserveAspectRatio="none" className="w-full" style={{ height: Math.min(380, Math.max(120, H)) }}>
                      {fold.embargo_start_index != null && fold.embargo_end_index != null && (
                        <rect
                          x={(fold.embargo_start_index / maxIdx) * 1000}
                          y={0}
                          width={Math.max(2, ((fold.embargo_end_index - fold.embargo_start_index + 1) / maxIdx) * 1000)}
                          height={H}
                          fill={EMBARGO_COLOR}
                          opacity={0.08}
                        />
                      )}
                      {cvResult.timeline.map((ev, i) => {
                        const x = (ev.start_index / maxIdx) * 1000;
                        const w = Math.max(2, ((ev.end_index - ev.start_index) / maxIdx) * 1000);
                        return <rect key={ev.event_id} x={x} y={i * rowH} width={w} height={Math.max(1, rowH - 0.5)} fill={roleColor(ev.event_id)} />;
                      })}
                    </svg>
                  );
                })()}
                <p className="text-[11px] text-slate-400">
                  <span style={{ color: TRAIN_COLOR }}>● Train</span>{"  "}
                  <span style={{ color: TEST_COLOR }}>● Test</span>{"  "}
                  <span style={{ color: PURGE_COLOR }}>● Purged</span>{"  "}
                  <span style={{ color: EMBARGO_COLOR }}>● Embargoed</span> — the faint red band is the embargo window; each row is one label interval. Click a fold row below.
                </p>
              </div>

              {/* Per-fold counts */}
              <div className="card space-y-2 p-5">
                <p className="section-title">Train / test / purged / embargo — fold {selectedFold + 1}</p>
                {(() => {
                  const f = cvResult.folds[selectedFold];
                  if (!f) return null;
                  const data = [
                    { name: "Train (after)", value: f.train_count_after, color: TRAIN_COLOR },
                    { name: "Test", value: f.test_count, color: TEST_COLOR },
                    { name: "Purged", value: f.purged_count, color: PURGE_COLOR },
                    { name: "Embargoed", value: f.embargoed_count, color: EMBARGO_COLOR },
                  ];
                  return (
                    <ResponsiveContainer width="100%" height={170}>
                      <ComposedChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                        <XAxis dataKey="name" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                        <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={40} allowDecimals={false} />
                        <Tooltip content={<NeonTooltip formatValue={(v: number) => String(v)} />} />
                        <Bar dataKey="value" name="Events" isAnimationActive={false}>
                          {data.map((d, i) => (<Cell key={i} fill={d.color} />))}
                        </Bar>
                      </ComposedChart>
                    </ResponsiveContainer>
                  );
                })()}
              </div>

              {/* Fold table */}
              <div className="card space-y-2 p-5">
                <p className="section-title">Folds (click a row to inspect its timeline)</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead><tr className="text-slate-400">
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Fold</th>
                      <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Test range</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Train before</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Train after</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Test</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Purged</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Embargo</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Overlap before</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Overlap after</th>
                    </tr></thead>
                    <tbody>
                      {cvResult.folds.map((f) => (
                        <tr
                          key={f.fold_id}
                          onClick={() => setSelectedFold(f.fold_id)}
                          className={"cursor-pointer border-t border-[var(--line)] " + (f.fold_id === selectedFold ? "bg-[var(--accent-softer)]" : "")}
                        >
                          <td className="px-2 py-1 text-right mono">{f.fold_id + 1}</td>
                          <td className="px-2 py-1 text-left mono">{f.test_start_date} → {f.test_end_date}</td>
                          <td className="px-2 py-1 text-right mono">{f.train_count_before}</td>
                          <td className="px-2 py-1 text-right mono">{f.train_count_after}</td>
                          <td className="px-2 py-1 text-right mono">{f.test_count}</td>
                          <td className="px-2 py-1 text-right mono" style={{ color: PURGE_COLOR }}>{f.purged_count}</td>
                          <td className="px-2 py-1 text-right mono" style={{ color: EMBARGO_COLOR }}>{f.embargoed_count}</td>
                          <td className="px-2 py-1 text-right mono" style={{ color: f.standard_train_overlap_count > 0 ? PURGE_COLOR : undefined }}>{f.standard_train_overlap_count}</td>
                          <td className="px-2 py-1 text-right mono" style={{ color: f.purged_overlap_count_after_purge === 0 ? "var(--emerald)" : DANGER }}>{f.purged_overlap_count_after_purge}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <p className="text-[11px] text-slate-400">
                This run converted the embargo fraction to {cvResult.summary.embargo_bars} trading observation(s). Purged and embargo totals are fold-level removals, so one event may contribute in different folds.
              </p>

              {cvResult.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
            </>
          )}
          {!cvResult && !cvError && (
            <div className="card p-5 text-sm text-slate-400">Run the purged CV demo to populate this tab.</div>
          )}
        </>
      )}

      {/* Sequential Bootstrap */}
      {tab === "seqboot" && (
        <>
          <div className="card space-y-3 p-5">
            <p className="section-title">Sequential Bootstrap</p>
            <p className="text-xs text-slate-500">
              Reuses the synthetic path and triple-barrier labels from the Setup above. Draws a sample
              of events one at a time with probability proportional to the marginal average uniqueness
              they add, then compares its uniqueness to a uniform random-bootstrap baseline.
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Sample size"><input type="number" className={inputCls + " w-28"} value={sampleSize} step={1} onChange={(e) => setSampleSize(e.target.value)} /></Field>
              <Field label="Random trials"><input type="number" className={inputCls + " w-28"} value={randomTrials} step={50} onChange={(e) => setRandomTrials(e.target.value)} /></Field>
              <label className="flex items-center gap-2 pb-1.5 text-xs text-slate-300">
                <input type="checkbox" checked={withReplacement} onChange={(e) => setWithReplacement(e.target.checked)} />
                With replacement
              </label>
              <button
                type="button"
                onClick={runSb}
                disabled={sbLoading}
                className={
                  "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
                  (!sbLoading
                    ? "bg-[var(--accent)] text-[var(--on-accent)] shadow-[var(--accent-glow)] hover:brightness-110"
                    : "cursor-not-allowed border border-[var(--line)] bg-[var(--glass)] text-slate-500")
                }
              >
                {sbLoading ? "Running…" : "Run sequential bootstrap"}
              </button>
            </div>
            <p className="text-[11px] text-slate-400">Sample size ≥ 1 (≤ events when without replacement); random trials 1–1000. Other parameters come from the Setup section above.</p>
            {sbError && <p className="text-xs text-red-600">⚠ {sbError}</p>}
          </div>

          {sbResult && (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
                <MetricCard label="Labeled events" value={String(sbResult.summary.n_events)} />
                <MetricCard label="Sample size" value={String(sbResult.summary.sample_size)} tone="accent" />
                <MetricCard label="Sequential uniqueness" value={pct(sbResult.summary.sequential_average_uniqueness, 1)} tone="positive" />
                <MetricCard label="Random uniqueness" value={pct(sbResult.summary.random_average_uniqueness, 1)} />
                <MetricCard label="Improvement vs random" value={pct(sbResult.summary.improvement_vs_random, 2)} tone={sbResult.summary.improvement_vs_random >= 0 ? "positive" : "warn"} />
                <MetricCard label="With replacement" value={sbResult.summary.with_replacement ? "Yes" : "No"} />
              </div>
              <p className="text-[11px] text-slate-400">{sbResult.summary.overlap_reduction_note}</p>

              <div className="card space-y-2 p-5">
                <p className="section-title">Average uniqueness after each sequential draw</p>
                <ResponsiveContainer width="100%" height={200}>
                  <ComposedChart data={sbResult.uniqueness_path} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                    <XAxis dataKey="draw" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={48} domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                    <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(2)}%`} formatLabel={(l) => (typeof l === "number" ? `Draw ${l}` : "")} />} />
                    <ReferenceLine y={sbResult.summary.random_average_uniqueness} stroke={NEUTRAL_COLOR} strokeDasharray="6 4" />
                    <Line type="monotone" dataKey="sequential_uniqueness" name="Sequential" stroke={POS_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
                <p className="text-[11px] text-slate-400">
                  <span style={{ color: POS_COLOR }}>— Sequential sample uniqueness</span>{"  "}
                  <span style={{ color: NEUTRAL_COLOR }}>– – Random-bootstrap mean</span>.
                </p>
              </div>

              <div className="card space-y-2 p-5">
                <p className="section-title">Sequential vs random uniqueness</p>
                <ResponsiveContainer width="100%" height={170}>
                  <ComposedChart
                    data={[
                      { name: "Sequential", value: sbResult.summary.sequential_average_uniqueness, color: POS_COLOR },
                      { name: "Random mean", value: sbResult.summary.random_average_uniqueness, color: NEUTRAL_COLOR },
                    ]}
                    margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={48} domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                    <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(2)}%`} />} />
                    <Bar dataKey="value" name="Avg uniqueness" isAnimationActive={false}>
                      <Cell fill={POS_COLOR} />
                      <Cell fill={NEUTRAL_COLOR} />
                    </Bar>
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              <div className="card space-y-2 p-5">
                <p className="section-title">Random-bootstrap baseline ({sbResult.random_baseline.n_trials} trials)</p>
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
                  <MetricCard label="Mean" value={pct(sbResult.random_baseline.mean, 1)} />
                  <MetricCard label="Median" value={pct(sbResult.random_baseline.median, 1)} />
                  <MetricCard label="p25" value={pct(sbResult.random_baseline.p25, 1)} />
                  <MetricCard label="p75" value={pct(sbResult.random_baseline.p75, 1)} />
                  <MetricCard label="Min" value={pct(sbResult.random_baseline.min, 1)} />
                  <MetricCard label="Max" value={pct(sbResult.random_baseline.max, 1)} />
                </div>
              </div>

              <div className="card space-y-2 p-5">
                <p className="section-title">Selected events (sequential sample)</p>
                <div className="max-h-80 overflow-auto">
                  <table className="w-full text-xs">
                    <thead><tr className="text-slate-400">
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Draw</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Event</th>
                      <th className="px-2 py-1 text-center font-medium uppercase tracking-wide">Label</th>
                      <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Start</th>
                      <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">End</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Realized</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Uniq after</th>
                      <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Sel. prob</th>
                    </tr></thead>
                    <tbody>
                      {sbResult.selected_events.map((s) => (
                        <tr key={s.draw_order} className="border-t border-[var(--line)]">
                          <td className="px-2 py-1 text-right mono">{s.draw_order}</td>
                          <td className="px-2 py-1 text-right mono">{s.event_id}</td>
                          <td className="px-2 py-1 text-center font-semibold" style={{ color: s.label > 0 ? POS_COLOR : s.label < 0 ? NEG_COLOR : NEUTRAL_COLOR }}>{s.label > 0 ? "+1" : s.label}</td>
                          <td className="px-2 py-1 text-left mono">{s.start_date}</td>
                          <td className="px-2 py-1 text-left mono">{s.end_date}</td>
                          <td className="px-2 py-1 text-right mono">{pct(s.realized_return)}</td>
                          <td className="px-2 py-1 text-right mono">{fmt(s.average_uniqueness_after_draw)}</td>
                          <td className="px-2 py-1 text-right mono">{fmt(s.selection_probability, 4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {sbResult.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
            </>
          )}
          {!sbResult && !sbError && (
            <div className="card p-5 text-sm text-slate-400">Run the sequential bootstrap demo to populate this tab.</div>
          )}
        </>
      )}

      {(tab === "cusum" || tab === "labeling" || tab === "uniqueness") && !result && (
        <div className="card p-5 text-sm text-slate-400">Run the labeling demo to populate this tab.</div>
      )}

      {result && (tab === "cusum" || tab === "labeling" || tab === "uniqueness") &&
        result.warnings.map((w, i) => (
          <p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>
        ))}

      {/* Education */}
      {tab === "education" && (
        <div className="card space-y-3 p-5 text-sm text-slate-400">
          <p className="section-title">Why financial-ML labeling is different</p>
          <ul className="space-y-2">
            <li><span className="font-semibold text-slate-200">Random train/test splits leak:</span> financial labels look forward in time and overlap, so a naive shuffle puts near-duplicate, time-adjacent samples in both train and test — inflating measured skill. A plain split does not fix this.</li>
            <li><span className="font-semibold text-slate-200">Purged K-fold (built):</span> the Purged CV tab keeps the K-fold time order but <em>purges</em> training labels whose intervals overlap the test fold, so train and test no longer share outcomes — the per-fold "overlap after purge" should be 0.</li>
            <li><span className="font-semibold text-slate-200">Embargo (built):</span> beyond purging, an embargo removes training labels that start just after the test fold, where serial correlation still leaks. It is applied after purging.</li>
            <li><span className="font-semibold text-slate-200">Sequential bootstrap (built):</span> a uniform bootstrap repeatedly samples overlapping (dependent) labels; the Sequential Bootstrap tab draws events with probability proportional to the marginal uniqueness they add, yielding a less-overlapping sample. It reduces dependence but does not guarantee better model performance — the benefit grows with how much the labels overlap.</li>
            <li><span className="font-semibold text-slate-200">Event sampling (CUSUM):</span> sampling on a fixed clock oversamples quiet periods. CUSUM samples only when cumulative movement is large, focusing labels on informative moments. Fixed mode uses a percentage-return threshold; vol-scaled mode uses a rolling-volatility multiplier.</li>
            <li><span className="font-semibold text-slate-200">Triple-barrier labeling:</span> a label is set by which barrier (profit-take / stop-loss / vertical-time) is hit first — a path-dependent, risk-aware label, unlike a fixed-horizon return sign.</li>
            <li><span className="font-semibold text-slate-200">Timing:</span> events are sampled using information available up to the event date. Future prices are used only to assign supervised-learning labels, not as trade signals or recommendations.</li>
            <li><span className="font-semibold text-slate-200">Overlapping labels → dependence:</span> labels whose holding windows overlap share outcomes and are not independent. Concurrency counts the overlap at each bar.</li>
            <li><span className="font-semibold text-slate-200">Sample uniqueness:</span> each label's uniqueness is the average of 1/concurrency over its life; using these as sample weights stops crowded periods from dominating training.</li>
            <li><span className="font-semibold text-slate-200">Not a model:</span> this is the labeling + validation-splitting stage only — no features, no fitted model, synthetic data. Purged K-fold + embargo reduce overlap leakage but do not guarantee a good model. Meta-labeling, information-driven bars, sequential bootstrap, fractional differentiation, and Combinatorial Purged CV (CPCV) are planned. Not investment advice.</li>
          </ul>
          <p className="text-[11px] text-slate-400">{CAVEAT}</p>
        </div>
      )}
    </div>
  );
}
