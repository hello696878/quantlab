"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import {
  BacktestApiError,
  buildCurve,
  fetchSampleCurve,
  priceBond,
  shockCurve,
} from "@/lib/api";
import type {
  BondResponse,
  CompoundingConvention,
  CurvePoint,
  CurveResponse,
  InterpolationMethod,
  PricingMode,
  ShockResponse,
  ShockType,
} from "@/lib/types";
import NeonTooltip from "@/components/charts/NeonTooltip";
import { CHART_AXIS, CHART_AXIS_LINE, CHART_GRID } from "@/components/charts/chartTheme";
import { seriesColor } from "@/lib/chartPalette";

type Tab = "builder" | "shocks" | "bond" | "education";

const inputCls = "ql-input px-2.5 py-1.5";
const labelCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400";

const SPOT_COLOR = seriesColor(0); // cyan
const SHOCK_COLOR = seriesColor(4); // amber — distinct from spot
const DF_COLOR = seriesColor(2); // violet
const FWD_COLOR = seriesColor(5); // emerald
const PV_COLOR = seriesColor(0);

function num(s: string): number {
  return s.trim() === "" ? NaN : Number(s);
}
function pct(v: number | null | undefined, d = 3): string {
  return v == null ? "—" : `${(v * 100).toFixed(d)}%`;
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
    <div className="rounded-lg bg-slate-50 px-3 py-2 text-center">
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mono mt-0.5 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}

interface UiCurveRow {
  maturity: string;
  rate: string; // percent
}

const DEFAULT_CURVE: UiCurveRow[] = [
  { maturity: "0.25", rate: "5.25" },
  { maturity: "1", rate: "4.90" },
  { maturity: "2", rate: "4.50" },
  { maturity: "5", rate: "4.10" },
  { maturity: "10", rate: "4.00" },
];

const COMPOUNDINGS: CompoundingConvention[] = ["continuous", "annual", "semiannual"];
const CAVEAT =
  "Yield-curve results depend on curve construction, compounding convention, interpolation " +
  "method, and day-count assumptions. Synthetic/manual curves only — no live rates feed, no " +
  "swap-curve bootstrapping. Educational, not investment advice.";

export default function YieldCurveLabPanel({ initialTab = "builder" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  // Shared curve across Builder / Shocks / Bond (curve mode).
  const [rows, setRows] = useState<UiCurveRow[]>(DEFAULT_CURVE);
  const [compounding, setCompounding] = useState<CompoundingConvention>("continuous");
  const [interpolation, setInterpolation] = useState<InterpolationMethod>("linear_zero");

  const apiPoints = (): CurvePoint[] =>
    rows
      .filter((r) => num(r.maturity) > 0 && Number.isFinite(num(r.rate)))
      .map((r) => ({ maturity_years: num(r.maturity), zero_rate: num(r.rate) / 100 }));

  const curveValid = apiPoints().length >= 2;

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-600">
          The Yield Curve Lab explores interest-rate curves — zero rates, discount factors, forward
          rates, curve shocks, and basic bond duration / convexity.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      <div className="inline-flex flex-wrap overflow-hidden rounded-lg border border-slate-300">
        {(
          [
            ["builder", "Curve Builder"],
            ["shocks", "Curve Shocks"],
            ["bond", "Bond Pricing"],
            ["education", "Education"],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={
              "px-3.5 py-1.5 text-xs font-medium transition-colors " +
              (tab === id ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50")
            }
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "builder" && (
        <CurveBuilderTab
          rows={rows}
          setRows={setRows}
          compounding={compounding}
          setCompounding={setCompounding}
          interpolation={interpolation}
          setInterpolation={setInterpolation}
          apiPoints={apiPoints}
          curveValid={curveValid}
        />
      )}
      {tab === "shocks" && (
        <CurveShocksTab compounding={compounding} apiPoints={apiPoints} curveValid={curveValid} />
      )}
      {tab === "bond" && (
        <BondPricingTab compounding={compounding} interpolation={interpolation} apiPoints={apiPoints} curveValid={curveValid} />
      )}
      {tab === "education" && <EducationTab />}
    </div>
  );
}

// ── Curve Builder ────────────────────────────────────────────────────────────

function CurveBuilderTab({
  rows,
  setRows,
  compounding,
  setCompounding,
  interpolation,
  setInterpolation,
  apiPoints,
  curveValid,
}: {
  rows: UiCurveRow[];
  setRows: (f: (r: UiCurveRow[]) => UiCurveRow[]) => void;
  compounding: CompoundingConvention;
  setCompounding: (c: CompoundingConvention) => void;
  interpolation: InterpolationMethod;
  setInterpolation: (m: InterpolationMethod) => void;
  apiPoints: () => CurvePoint[];
  curveValid: boolean;
}) {
  const [result, setResult] = useState<CurveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sampleLoading, setSampleLoading] = useState(false);

  function setRow(i: number, patch: Partial<UiCurveRow>) {
    setRows((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }
  function addRow() {
    setRows((ls) => [...ls, { maturity: "20", rate: "4.10" }]);
  }
  function removeRow(i: number) {
    setRows((ls) => (ls.length > 2 ? ls.filter((_, idx) => idx !== i) : ls));
  }

  async function loadSample() {
    setSampleLoading(true);
    setError(null);
    try {
      const s = await fetchSampleCurve();
      setRows(() => s.curve_points.map((p) => ({ maturity: String(p.maturity_years), rate: (p.zero_rate * 100).toFixed(2) })));
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setSampleLoading(false);
    }
  }

  async function build() {
    if (!curveValid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await buildCurve({ curve_points: apiPoints(), compounding, interpolation }));
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const spotData = result?.curve.map((c) => ({ t: c.maturity_years, rate: c.zero_rate })) ?? [];
  const dfData = result?.curve.map((c) => ({ t: c.maturity_years, df: c.discount_factor })) ?? [];
  const fwdData = result?.forward_rates.map((f) => ({ t: f.end_year, fwd: f.forward_rate })) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Curve Builder</p>
      <div className="flex flex-wrap items-end gap-3">
        <button type="button" onClick={loadSample} disabled={sampleLoading} className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:border-blue-400">
          {sampleLoading ? "Loading…" : "Load sample curve"}
        </button>
        <Field label="Compounding">
          <select className={inputCls} value={compounding} onChange={(e) => setCompounding(e.target.value as CompoundingConvention)}>
            {COMPOUNDINGS.map((c) => (<option key={c} value={c}>{c}</option>))}
          </select>
        </Field>
        <Field label="Interpolation">
          <select className={inputCls} value={interpolation} onChange={(e) => setInterpolation(e.target.value as InterpolationMethod)}>
            <option value="linear_zero">linear on zero rates</option>
            <option value="linear_discount">linear on discount factors</option>
          </select>
        </Field>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full max-w-md text-xs">
          <thead>
            <tr className="text-slate-400">
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Maturity (yrs)</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Zero rate (%)</th>
              <th className="px-2 py-1"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-2 py-1"><input type="number" className={inputCls + " w-24"} value={r.maturity} onChange={(e) => setRow(i, { maturity: e.target.value })} /></td>
                <td className="px-2 py-1"><input type="number" className={inputCls + " w-24"} value={r.rate} step={0.05} onChange={(e) => setRow(i, { rate: e.target.value })} /></td>
                <td className="px-2 py-1"><button type="button" onClick={() => removeRow(i)} className="text-slate-400 hover:text-red-600" title="Remove">✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" onClick={addRow} className="mt-1 rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:border-blue-400">+ Add point</button>
      </div>

      <button
        type="button"
        onClick={build}
        disabled={!curveValid || loading}
        className={
          "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
          (curveValid && !loading ? "bg-blue-600 text-white hover:bg-blue-700" : "cursor-not-allowed bg-slate-100 text-slate-400")
        }
      >
        {loading ? "Building…" : "Build curve"}
      </button>
      {!curveValid && <p className="text-[11px] text-slate-400">At least two valid curve points (maturity &gt; 0) are required.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div>
            <p className="section-title mb-1">Spot (zero) curve</p>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={spotData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={(v: number) => `${v}y`} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(3)}%`} formatLabel={(l) => (typeof l === "number" ? `${l}y` : "")} />} />
                <Line type="monotone" dataKey="rate" name="Zero rate" stroke={SPOT_COLOR} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div>
            <p className="section-title mb-1">Discount factor curve</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={dfData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={(v: number) => `${v}y`} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} domain={["auto", 1]} tickFormatter={(v: number) => v.toFixed(2)} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(4)} formatLabel={(l) => (typeof l === "number" ? `${l}y` : "")} />} />
                <Line type="monotone" dataKey="df" name="Discount factor" stroke={DF_COLOR} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div>
            <p className="section-title mb-1">Forward rate curve (continuously compounded)</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={fwdData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={(v: number) => `${v}y`} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(3)}%`} formatLabel={(l) => (typeof l === "number" ? `to ${l}y` : "")} />} />
                <Line type="stepAfter" dataKey="fwd" name="Forward rate" stroke={FWD_COLOR} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full max-w-lg text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Maturity</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Zero rate</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Discount factor</th>
                </tr>
              </thead>
              <tbody>
                {result.curve.map((c) => (
                  <tr key={c.maturity_years} className="border-t border-slate-100">
                    <td className="px-2 py-1 text-right mono">{c.maturity_years}y</td>
                    <td className="px-2 py-1 text-right mono">{pct(c.zero_rate)}</td>
                    <td className="px-2 py-1 text-right mono">{c.discount_factor.toFixed(5)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.warnings.map((w, i) => (
            <p key={i} className="text-[11px] text-slate-400">{w}</p>
          ))}
        </>
      )}
    </div>
  );
}

// ── Curve Shocks ───────────────────────────────────────────────────────────

const SHOCK_TYPES: ShockType[] = ["parallel", "steepener", "flattener", "butterfly"];

function CurveShocksTab({
  compounding,
  apiPoints,
  curveValid,
}: {
  compounding: CompoundingConvention;
  apiPoints: () => CurvePoint[];
  curveValid: boolean;
}) {
  const [shockType, setShockType] = useState<ShockType>("parallel");
  const [shockBps, setShockBps] = useState("100");
  const [result, setResult] = useState<ShockResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid = curveValid && Number.isFinite(num(shockBps));

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await shockCurve({ curve_points: apiPoints(), shock_type: shockType, shock_bps: num(shockBps), compounding }));
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData =
    result?.original_curve.map((o, i) => ({
      t: o.maturity_years,
      original: o.zero_rate,
      shocked: result.shocked_curve[i]?.zero_rate ?? null,
    })) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Curve Shocks</p>
      <p className="text-xs text-slate-500">
        Educational curve shocks applied to the curve from the Builder tab — not a realistic
        scenario-generation model.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Shock type">
          <select className={inputCls} value={shockType} onChange={(e) => setShockType(e.target.value as ShockType)}>
            {SHOCK_TYPES.map((s) => (<option key={s} value={s}>{s}</option>))}
          </select>
        </Field>
        <Field label="Shock size (bps)"><input type="number" className={inputCls + " w-28"} value={shockBps} step={25} onChange={(e) => setShockBps(e.target.value)} /></Field>
        <button
          type="button"
          onClick={run}
          disabled={!valid || loading}
          className={
            "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
            (valid && !loading ? "bg-blue-600 text-white hover:bg-blue-700" : "cursor-not-allowed bg-slate-100 text-slate-400")
          }
        >
          {loading ? "Shocking…" : "Run shock"}
        </button>
      </div>
      {!curveValid && <p className="text-[11px] text-slate-400">Build a valid curve in the Curve Builder tab first.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div>
            <p className="section-title mb-1">Original vs shocked curve</p>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={(v: number) => `${v}y`} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(3)}%`} formatLabel={(l) => (typeof l === "number" ? `${l}y` : "")} />} />
                <Line type="monotone" dataKey="original" name="Original" stroke={SPOT_COLOR} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
                <Line type="monotone" dataKey="shocked" name="Shocked" stroke={SHOCK_COLOR} strokeWidth={2} strokeDasharray="5 4" dot={{ r: 2 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: SPOT_COLOR }}>● Original</span>{"  "}
              <span style={{ color: SHOCK_COLOR }}>— Shocked</span> (dashed).
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full max-w-lg text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Maturity</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Original</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Shocked</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Δ (bps)</th>
                </tr>
              </thead>
              <tbody>
                {result.changes.map((c) => (
                  <tr key={c.maturity_years} className="border-t border-slate-100">
                    <td className="px-2 py-1 text-right mono">{c.maturity_years}y</td>
                    <td className="px-2 py-1 text-right mono">{pct(c.original_rate)}</td>
                    <td className="px-2 py-1 text-right mono">{pct(c.shocked_rate)}</td>
                    <td className="px-2 py-1 text-right mono">{c.change_bps >= 0 ? "+" : ""}{c.change_bps.toFixed(1)}</td>
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

// ── Bond Pricing ─────────────────────────────────────────────────────────────

function BondPricingTab({
  compounding,
  interpolation,
  apiPoints,
  curveValid,
}: {
  compounding: CompoundingConvention;
  interpolation: InterpolationMethod;
  apiPoints: () => CurvePoint[];
  curveValid: boolean;
}) {
  const [face, setFace] = useState("1000");
  const [coupon, setCoupon] = useState("5");
  const [maturity, setMaturity] = useState("5");
  const [freq, setFreq] = useState("2");
  const [mode, setMode] = useState<PricingMode>("ytm");
  const [ytm, setYtm] = useState("4.5");
  const [result, setResult] = useState<BondResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const freqValid = [1, 2, 4, 12].includes(num(freq));
  const valid =
    num(face) > 0 &&
    Number.isFinite(num(coupon)) &&
    num(coupon) >= 0 &&
    num(maturity) > 0 &&
    freqValid &&
    (mode === "curve" ? curveValid : Number.isFinite(num(ytm)));

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await priceBond({
          face_value: num(face),
          coupon_rate: num(coupon) / 100,
          maturity_years: num(maturity),
          coupon_frequency: num(freq),
          pricing_mode: mode,
          yield_to_maturity: mode === "ytm" ? num(ytm) / 100 : null,
          curve_points: mode === "curve" ? apiPoints() : null,
          compounding,
          interpolation,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const pvData = result?.cash_flows.map((c) => ({ t: c.time_years, pv: c.present_value })) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Bond Pricing</p>
      <p className="text-xs text-slate-500">
        Simplified clean-price approximation for a fixed-rate bond — no accrued interest, day-count,
        or settlement conventions. Curve mode discounts cash flows on the Builder-tab curve.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Face value"><input type="number" className={inputCls} value={face} onChange={(e) => setFace(e.target.value)} /></Field>
        <Field label="Coupon rate (%)"><input type="number" className={inputCls} value={coupon} step={0.25} onChange={(e) => setCoupon(e.target.value)} /></Field>
        <Field label="Maturity (yrs)"><input type="number" className={inputCls} value={maturity} onChange={(e) => setMaturity(e.target.value)} /></Field>
        <Field label="Frequency / yr">
          <select className={inputCls} value={freq} onChange={(e) => setFreq(e.target.value)}>
            {[1, 2, 4, 12].map((f) => (<option key={f} value={f}>{f}</option>))}
          </select>
        </Field>
        <Field label="Pricing mode">
          <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value as PricingMode)}>
            <option value="ytm">Yield to maturity</option>
            <option value="curve">Curve discounting</option>
          </select>
        </Field>
        {mode === "ytm" && (
          <Field label="YTM (%)"><input type="number" className={inputCls} value={ytm} step={0.1} onChange={(e) => setYtm(e.target.value)} /></Field>
        )}
      </div>
      <button
        type="button"
        onClick={run}
        disabled={!valid || loading}
        className={
          "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
          (valid && !loading ? "bg-blue-600 text-white hover:bg-blue-700" : "cursor-not-allowed bg-slate-100 text-slate-400")
        }
      >
        {loading ? "Pricing…" : "Price bond"}
      </button>
      {!valid && (
        <p className="text-[11px] text-slate-400">
          Face/maturity positive, frequency 1/2/4/12, and either a YTM or a valid Builder curve.
        </p>
      )}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Price" value={result.price.toFixed(2)} />
            <Stat label="Macaulay duration" value={result.macaulay_duration != null ? `${result.macaulay_duration.toFixed(3)} y` : "—"} />
            <Stat label="Modified duration" value={result.modified_duration != null ? result.modified_duration.toFixed(3) : "—"} />
            <Stat label="DV01" value={result.dv01 != null ? result.dv01.toFixed(4) : "—"} />
            <Stat label="Convexity" value={result.convexity != null ? result.convexity.toFixed(3) : "—"} />
          </div>
          <div>
            <p className="section-title mb-1">Cash-flow present values</p>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={pvData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={(v: number) => `${v}y`} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(2)} formatLabel={(l) => (typeof l === "number" ? `${l}y` : "")} />} />
                <Bar dataKey="pv" name="PV of cash flow" fill={PV_COLOR} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full max-w-lg text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Time</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Cash flow</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">DF</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">PV</th>
                </tr>
              </thead>
              <tbody>
                {result.cash_flows.map((c) => (
                  <tr key={c.time_years} className="border-t border-slate-100">
                    <td className="px-2 py-1 text-right mono">{c.time_years}y</td>
                    <td className="px-2 py-1 text-right mono">{c.cash_flow.toFixed(2)}</td>
                    <td className="px-2 py-1 text-right mono">{c.discount_factor.toFixed(5)}</td>
                    <td className="px-2 py-1 text-right mono">{c.present_value.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.warnings.map((w, i) => (
            <p key={i} className="text-[11px] text-slate-400">{w}</p>
          ))}
        </>
      )}
    </div>
  );
}

// ── Education ──────────────────────────────────────────────────────────────

function EducationTab() {
  const items: [string, string][] = [
    ["Spot vs par yields", "A zero (spot) rate discounts a single cash flow at one maturity; a par yield is the coupon that prices a bond at par. They differ whenever the curve is not flat."],
    ["Discount factors", "DF(T) is the present value of $1 paid at T. For positive rates DFs fall with maturity; they encode the whole curve."],
    ["Forward rates", "Forwards are the future rates implied by today's curve between two maturities — here continuously compounded from the discount factors."],
    ["Duration", "Macaulay duration is the PV-weighted average time to cash flows; modified duration ≈ the % price change per 1% yield move."],
    ["Convexity", "Convexity captures the curvature of the price/yield relationship — duration alone underestimates price for large moves."],
    ["DV01", "Dollar value of a 1 bp yield move (≈ modified duration × price × 0.0001)."],
    ["Interpolation", "Rates between curve points are interpolated; the method (zero rates vs discount factors) changes intermediate values."],
    ["Assumption sensitivity", "Compounding, day count, interpolation, and curve construction all shift the numbers — fixed-income analytics are assumption-driven."],
  ];
  return (
    <div className="card space-y-3 p-5 text-sm text-slate-600">
      <p className="section-title">How to read the Yield Curve Lab</p>
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
