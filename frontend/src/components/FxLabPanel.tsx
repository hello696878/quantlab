"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Cell,
  Line,
  ReferenceLine,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import {
  BacktestApiError,
  computeFxCarry,
  computeFxExposure,
  computeFxForward,
  computeFxPpp,
  priceFxOption,
} from "@/lib/api";
import type {
  CarryDirection,
  FxCarryResponse,
  FxCompounding,
  FxExposureResponse,
  FxForwardResponse,
  FxOptionResponse,
  FxPppResponse,
} from "@/lib/types";
import MetricCard from "@/components/MetricCard";
import NeonTooltip from "@/components/charts/NeonTooltip";
import { CHART_AXIS, CHART_AXIS_LINE, CHART_GRID, CHART_REF_LINE, DANGER } from "@/components/charts/chartTheme";
import { seriesColor } from "@/lib/chartPalette";

type Tab = "forward" | "carry" | "ppp" | "exposure" | "options" | "education";

const inputCls = "ql-input px-2.5 py-1.5";
const labelCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400";

const POS_COLOR = "var(--emerald)";
const NEG_COLOR = DANGER;
const SPOT_COLOR = seriesColor(0); // cyan
const FWD_COLOR = seriesColor(4); // amber
const PPP_COLOR = seriesColor(2); // violet

const CAVEAT =
  "FX results depend on interest-rate conventions, funding/transaction costs, capital controls, " +
  "liquidity, inflation-data quality, and whether the quoted rates are actually investable. " +
  "Quote convention: domestic currency per 1 unit of foreign currency. Educational research only — " +
  "no live FX rates, not investment advice.";

function num(s: string): number {
  return s.trim() === "" ? NaN : Number(s);
}
function finite(s: string): boolean {
  return Number.isFinite(num(s));
}
function fmt(v: number | null | undefined, d = 4): string {
  return v == null || !Number.isFinite(v) ? "—" : v.toFixed(d);
}
function pct(v: number | null | undefined, d = 2): string {
  return v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`;
}
function money(v: number | null | undefined, d = 0): string {
  return v == null || !Number.isFinite(v)
    ? "—"
    : v.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className={labelCls}>{label}</span>
      {children}
    </label>
  );
}

function runButton(valid: boolean, loading: boolean, label: string, busy: string) {
  return (
    "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
    (valid && !loading
      ? "bg-[var(--accent)] text-[var(--on-accent)] shadow-[var(--accent-glow)] hover:brightness-110"
      : "cursor-not-allowed border border-[var(--line)] bg-[var(--glass)] text-slate-500")
  );
}

const COMPOUNDINGS: FxCompounding[] = ["continuous", "annual"];

export default function FxLabPanel({ initialTab = "forward" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-300">
          The FX Lab explores currency analytics — spot/forward via interest rate parity, FX carry,
          purchasing power parity (PPP) deviation, currency exposure, and Garman-Kohlhagen FX option
          pricing.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      <div className="ql-segmented">
        {(
          [
            ["forward", "Forward / IRP"],
            ["carry", "Carry"],
            ["ppp", "PPP"],
            ["exposure", "Exposure"],
            ["options", "FX Options"],
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

      {tab === "forward" && <ForwardTab />}
      {tab === "carry" && <CarryTab />}
      {tab === "ppp" && <PppTab />}
      {tab === "exposure" && <ExposureTab />}
      {tab === "options" && <FxOptionsTab />}
      {tab === "education" && <FxEducationTab />}
    </div>
  );
}

// ── Forward / IRP ────────────────────────────────────────────────────────────

function ForwardTab() {
  const [spot, setSpot] = useState("150");
  const [domestic, setDomestic] = useState("1");
  const [foreign, setForeign] = useState("5");
  const [maturity, setMaturity] = useState("1");
  const [compounding, setCompounding] = useState<FxCompounding>("continuous");
  const [result, setResult] = useState<FxForwardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid = num(spot) > 0 && finite(domestic) && finite(foreign) && num(maturity) > 0;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await computeFxForward({
          spot_rate: num(spot),
          domestic_rate: num(domestic) / 100,
          foreign_rate: num(foreign) / 100,
          time_to_maturity: num(maturity),
          compounding,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = result
    ? [
        { name: "Spot", value: result.spot_rate },
        { name: "Forward", value: result.forward_rate },
      ]
    : [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Forward / Interest Rate Parity</p>
      <p className="text-xs text-slate-500">
        Covered interest rate parity: continuous F = S·e^((r_d−r_f)·T), annual F = S·((1+r_d)/(1+r_f))^T.
        S is domestic currency per 1 unit of foreign currency.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Field label="Spot rate (dom/foreign)"><input type="number" className={inputCls} value={spot} onChange={(e) => setSpot(e.target.value)} /></Field>
        <Field label="Domestic rate (%)"><input type="number" className={inputCls} value={domestic} step={0.25} onChange={(e) => setDomestic(e.target.value)} /></Field>
        <Field label="Foreign rate (%)"><input type="number" className={inputCls} value={foreign} step={0.25} onChange={(e) => setForeign(e.target.value)} /></Field>
        <Field label="Maturity (yrs)"><input type="number" className={inputCls} value={maturity} step={0.25} onChange={(e) => setMaturity(e.target.value)} /></Field>
        <Field label="Compounding">
          <select className={inputCls} value={compounding} onChange={(e) => setCompounding(e.target.value as FxCompounding)}>
            {COMPOUNDINGS.map((c) => (<option key={c} value={c}>{c}</option>))}
          </select>
        </Field>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runButton(valid, loading, "", "")}>
        {loading ? "Computing…" : "Compute forward"}
      </button>
      {!valid && <p className="text-[11px] text-slate-400">Spot &gt; 0, finite rates, maturity &gt; 0.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <MetricCard label="Forward rate" value={fmt(result.forward_rate)} tone="accent" />
            <MetricCard label="Forward points" value={fmt(result.forward_points)} tone={result.forward_points >= 0 ? "positive" : "danger"} />
            <MetricCard label="Rate differential (r_d − r_f)" value={pct(result.rate_differential)} />
          </div>
          <div>
            <p className="section-title mb-1">Spot vs forward</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={56} domain={["auto", "auto"]} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(4)} />} />
                <Bar dataKey="value" name="Rate" isAnimationActive={false}>
                  <Cell fill={SPOT_COLOR} />
                  <Cell fill={FWD_COLOR} />
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: SPOT_COLOR }}>● Spot</span>{"  "}
              <span style={{ color: FWD_COLOR }}>● Forward</span> — convention: {result.convention}.
            </p>
          </div>
          {result.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
        </>
      )}
    </div>
  );
}

// ── Carry ────────────────────────────────────────────────────────────────────

const DIRECTIONS: [CarryDirection, string][] = [
  ["long_foreign", "Long foreign / short domestic"],
  ["long_domestic", "Long domestic / short foreign"],
];

function CarryTab() {
  const [spot, setSpot] = useState("150");
  const [domestic, setDomestic] = useState("1");
  const [foreign, setForeign] = useState("5");
  const [expected, setExpected] = useState("152");
  const [horizon, setHorizon] = useState("1");
  const [notional, setNotional] = useState("1000000");
  const [direction, setDirection] = useState<CarryDirection>("long_foreign");
  const [result, setResult] = useState<FxCarryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid =
    num(spot) > 0 && finite(domestic) && finite(foreign) && num(expected) > 0 && num(horizon) > 0 && finite(notional);

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await computeFxCarry({
          spot_rate: num(spot),
          domestic_rate: num(domestic) / 100,
          foreign_rate: num(foreign) / 100,
          expected_spot: num(expected),
          horizon_years: num(horizon),
          notional: num(notional),
          direction,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = result
    ? [
        { name: "Carry", value: result.carry_return },
        { name: "FX move", value: result.expected_fx_return },
        { name: "Total", value: result.total_expected_return },
      ]
    : [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">FX Carry</p>
      <p className="text-xs text-slate-500">
        Simplified decomposition into the interest differential (carry) and the expected spot move.
        Carry is not free money — currency moves can offset or exceed the differential.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Spot rate"><input type="number" className={inputCls} value={spot} onChange={(e) => setSpot(e.target.value)} /></Field>
        <Field label="Domestic rate (%)"><input type="number" className={inputCls} value={domestic} step={0.25} onChange={(e) => setDomestic(e.target.value)} /></Field>
        <Field label="Foreign rate (%)"><input type="number" className={inputCls} value={foreign} step={0.25} onChange={(e) => setForeign(e.target.value)} /></Field>
        <Field label="Expected spot"><input type="number" className={inputCls} value={expected} onChange={(e) => setExpected(e.target.value)} /></Field>
        <Field label="Horizon (yrs)"><input type="number" className={inputCls} value={horizon} step={0.25} onChange={(e) => setHorizon(e.target.value)} /></Field>
        <Field label="Notional (domestic)"><input type="number" className={inputCls} value={notional} step={100000} onChange={(e) => setNotional(e.target.value)} /></Field>
        <Field label="Direction">
          <select className={inputCls} value={direction} onChange={(e) => setDirection(e.target.value as CarryDirection)}>
            {DIRECTIONS.map(([id, label]) => (<option key={id} value={id}>{label}</option>))}
          </select>
        </Field>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runButton(valid, loading, "", "")}>
        {loading ? "Computing…" : "Compute carry"}
      </button>
      {!valid && <p className="text-[11px] text-slate-400">Spot/expected/horizon &gt; 0, finite rates and notional.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <MetricCard label="Interest differential" value={pct(result.interest_differential)} />
            <MetricCard label="Carry return" value={pct(result.carry_return)} tone={result.carry_return >= 0 ? "positive" : "danger"} />
            <MetricCard label="Expected FX return" value={pct(result.expected_fx_return)} tone={result.expected_fx_return >= 0 ? "positive" : "danger"} />
            <MetricCard label="Total expected return" value={pct(result.total_expected_return)} tone={result.total_expected_return >= 0 ? "positive" : "danger"} />
            <MetricCard label="P&L estimate" value={money(result.pnl_estimate)} tone={result.pnl_estimate >= 0 ? "positive" : "danger"} />
          </div>
          <div>
            <p className="section-title mb-1">Return breakdown</p>
            <ResponsiveContainer width="100%" height={190}>
              <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(2)}%`} />} />
                <ReferenceLine y={0} stroke={CHART_REF_LINE} />
                <Bar dataKey="value" name="Return" isAnimationActive={false}>
                  {chartData.map((d, i) => (<Cell key={i} fill={d.value >= 0 ? POS_COLOR : NEG_COLOR} />))}
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {result.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
        </>
      )}
    </div>
  );
}

// ── PPP ──────────────────────────────────────────────────────────────────────

function PppTab() {
  const [current, setCurrent] = useState("150");
  const [base, setBase] = useState("120");
  const [domIndex, setDomIndex] = useState("110");
  const [forIndex, setForIndex] = useState("105");
  const [result, setResult] = useState<FxPppResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid = num(current) > 0 && num(base) > 0 && num(domIndex) > 0 && num(forIndex) > 0;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await computeFxPpp({
          current_spot: num(current),
          base_spot: num(base),
          domestic_price_index: num(domIndex),
          foreign_price_index: num(forIndex),
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = result
    ? [
        { name: "Current spot", value: result.current_spot },
        { name: "PPP-implied", value: result.ppp_implied_spot },
      ]
    : [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">PPP Deviation</p>
      <p className="text-xs text-slate-500">
        Relative PPP: S_ppp = S_base · (domestic index / foreign index). PPP deviation suggests
        relative valuation under this simplified input, not a timing signal.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Current spot"><input type="number" className={inputCls} value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>
        <Field label="Base-period spot"><input type="number" className={inputCls} value={base} onChange={(e) => setBase(e.target.value)} /></Field>
        <Field label="Domestic price index"><input type="number" className={inputCls} value={domIndex} onChange={(e) => setDomIndex(e.target.value)} /></Field>
        <Field label="Foreign price index"><input type="number" className={inputCls} value={forIndex} onChange={(e) => setForIndex(e.target.value)} /></Field>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runButton(valid, loading, "", "")}>
        {loading ? "Computing…" : "Compute PPP"}
      </button>
      {!valid && <p className="text-[11px] text-slate-400">All inputs must be positive.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <MetricCard label="PPP-implied spot" value={fmt(result.ppp_implied_spot)} tone="accent" />
            <MetricCard label="Deviation" value={pct(result.deviation)} tone={Math.abs(result.deviation) <= 0.01 ? "default" : "warn"} />
            <MetricCard label="Valuation" value={result.valuation.includes("overvalued") ? "Overvalued" : result.valuation.includes("undervalued") ? "Undervalued" : "Near fair value"} tone="warn" />
          </div>
          <p className="text-[11px] text-slate-400">{result.valuation}.</p>
          <div>
            <p className="section-title mb-1">Current vs PPP-implied spot</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={56} domain={["auto", "auto"]} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(4)} />} />
                <Bar dataKey="value" name="Spot" isAnimationActive={false}>
                  <Cell fill={SPOT_COLOR} />
                  <Cell fill={PPP_COLOR} />
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: SPOT_COLOR }}>● Current spot</span>{"  "}
              <span style={{ color: PPP_COLOR }}>● PPP-implied</span>.
            </p>
          </div>
          {result.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
        </>
      )}
    </div>
  );
}

// ── Exposure ───────────────────────────────────────────────────────────────

interface UiExpRow {
  currency: string;
  amount: string;
  spotToBase: string;
}
const DEFAULT_EXP: UiExpRow[] = [
  { currency: "USD", amount: "100000", spotToBase: "1.0" },
  { currency: "JPY", amount: "1000000", spotToBase: "0.0067" },
  { currency: "EUR", amount: "50000", spotToBase: "1.08" },
];

function ExposureTab() {
  const [rows, setRows] = useState<UiExpRow[]>(DEFAULT_EXP);
  const [baseCurrency, setBaseCurrency] = useState("USD");
  const [shockPct, setShockPct] = useState("10");
  const [result, setResult] = useState<FxExposureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function setRow(i: number, patch: Partial<UiExpRow>) {
    setRows((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }
  function addRow() {
    setRows((ls) => (ls.length >= 100 ? ls : [...ls, { currency: "GBP", amount: "25000", spotToBase: "1.27" }]));
  }
  function removeRow(i: number) {
    setRows((ls) => (ls.length > 1 ? ls.filter((_, idx) => idx !== i) : ls));
  }

  const rowsValid =
    rows.length >= 1 &&
    rows.every((r) => r.currency.trim() !== "" && finite(r.amount) && num(r.spotToBase) > 0);
  const valid = rowsValid && baseCurrency.trim() !== "" && num(shockPct) >= 0 && num(shockPct) <= 100;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await computeFxExposure({
          exposures: rows.map((r) => ({ currency: r.currency.trim(), amount: num(r.amount), spot_to_base: num(r.spotToBase) })),
          base_currency: baseCurrency.trim(),
          shock_pct: num(shockPct) / 100,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const expData = result?.rows.map((r, i) => ({ currency: r.currency, base_value: r.base_value, color: seriesColor(i) })) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Currency Exposure</p>
      <p className="text-xs text-slate-500">
        Translates exposures to a base currency and applies a uniform symmetric FX shock (all
        non-base currencies move together). Educational translation, not a covariance risk model.
        spot-to-base = base currency per 1 unit of the exposure currency.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Base currency"><input type="text" className={inputCls + " w-24"} value={baseCurrency} onChange={(e) => setBaseCurrency(e.target.value)} /></Field>
        <Field label="Stress shock (%)"><input type="number" className={inputCls + " w-24"} value={shockPct} step={1} onChange={(e) => setShockPct(e.target.value)} /></Field>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full max-w-xl text-xs">
          <thead>
            <tr className="text-slate-400">
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Currency</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Amount</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Spot to base</th>
              <th className="px-2 py-1"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-[var(--line)]">
                <td className="px-2 py-1"><input type="text" className={inputCls + " w-20"} value={r.currency} onChange={(e) => setRow(i, { currency: e.target.value })} /></td>
                <td className="px-2 py-1"><input type="number" className={inputCls + " w-28"} value={r.amount} onChange={(e) => setRow(i, { amount: e.target.value })} /></td>
                <td className="px-2 py-1"><input type="number" className={inputCls + " w-24"} value={r.spotToBase} step={0.01} onChange={(e) => setRow(i, { spotToBase: e.target.value })} /></td>
                <td className="px-2 py-1"><button type="button" onClick={() => removeRow(i)} className="text-slate-400 hover:text-red-600" title="Remove">✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" onClick={addRow} disabled={rows.length >= 100} className="mt-1 rounded-lg border border-[var(--line-strong)] px-2.5 py-1 text-xs font-medium text-slate-300 hover:border-[var(--accent-border)] disabled:cursor-not-allowed disabled:text-slate-500">
          + Add currency
        </button>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runButton(valid, loading, "", "")}>
        {loading ? "Computing…" : "Compute exposure"}
      </button>
      {!valid && <p className="text-[11px] text-slate-400">Each row needs a currency, finite amount, positive spot-to-base; shock 0–100%.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <MetricCard label={`Total exposure (${result.base_currency})`} value={money(result.total_exposure)} tone="accent" />
            <MetricCard label={`Stress +${pct(result.shock_pct, 0)} P&L`} value={money(result.stress_pnl_up)} tone={result.stress_pnl_up >= 0 ? "positive" : "danger"} />
            <MetricCard label={`Stress −${pct(result.shock_pct, 0)} P&L`} value={money(result.stress_pnl_down)} tone={result.stress_pnl_down >= 0 ? "positive" : "danger"} />
          </div>
          <div>
            <p className="section-title mb-1">Exposure by currency ({result.base_currency})</p>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={expData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="currency" tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={64} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => money(v)} />} />
                <ReferenceLine y={0} stroke={CHART_REF_LINE} />
                <Bar dataKey="base_value" name="Base value" isAnimationActive={false}>
                  {expData.map((d, i) => (<Cell key={i} fill={d.base_value >= 0 ? d.color : NEG_COLOR} />))}
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full max-w-2xl text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Currency</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Base value</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Weight</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Stress + P&L</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Stress − P&L</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.currency} className="border-t border-[var(--line)]">
                    <td className="px-2 py-1 text-left mono">{r.currency}</td>
                    <td className="px-2 py-1 text-right mono">{money(r.base_value)}</td>
                    <td className="px-2 py-1 text-right mono">{pct(r.weight_pct, 1)}</td>
                    <td className="px-2 py-1 text-right mono">{money(r.stress_pnl_up)}</td>
                    <td className="px-2 py-1 text-right mono">{money(r.stress_pnl_down)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
        </>
      )}
    </div>
  );
}

// ── FX Options (Garman-Kohlhagen) ────────────────────────────────────────────

function FxOptionsTab() {
  const [optionType, setOptionType] = useState<"call" | "put">("call");
  const [spot, setSpot] = useState("1.10");
  const [strike, setStrike] = useState("1.10");
  const [domestic, setDomestic] = useState("4");
  const [foreign, setForeign] = useState("2");
  const [vol, setVol] = useState("12");
  const [maturity, setMaturity] = useState("1");
  const [result, setResult] = useState<FxOptionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid = num(spot) > 0 && num(strike) > 0 && finite(domestic) && finite(foreign) && num(vol) > 0 && num(maturity) > 0;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await priceFxOption({
          option_type: optionType,
          spot_rate: num(spot),
          strike: num(strike),
          domestic_rate: num(domestic) / 100,
          foreign_rate: num(foreign) / 100,
          volatility: num(vol) / 100,
          time_to_expiry: num(maturity),
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  // Client-side intrinsic payoff at expiry (visual only, no extra backend call).
  const payoffData = (() => {
    if (!result) return [];
    const K = num(strike);
    const S0 = num(spot);
    const lo = S0 * 0.7;
    const hi = S0 * 1.3;
    const n = 41;
    const pts: { s: number; payoff: number }[] = [];
    for (let i = 0; i < n; i++) {
      const s = lo + ((hi - lo) * i) / (n - 1);
      const payoff = optionType === "call" ? Math.max(s - K, 0) : Math.max(K - s, 0);
      pts.push({ s, payoff });
    }
    return pts;
  })();

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">FX Options (Garman-Kohlhagen)</p>
      <p className="text-xs text-slate-500">
        Garman-Kohlhagen is Black-Scholes for FX (the foreign rate acts like a dividend yield).
        Constant volatility — no FX volatility surface, smile, or skew.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <Field label="Type">
          <select className={inputCls} value={optionType} onChange={(e) => setOptionType(e.target.value as "call" | "put")}>
            <option value="call">Call</option>
            <option value="put">Put</option>
          </select>
        </Field>
        <Field label="Spot (S)"><input type="number" className={inputCls} value={spot} step={0.01} onChange={(e) => setSpot(e.target.value)} /></Field>
        <Field label="Strike (K)"><input type="number" className={inputCls} value={strike} step={0.01} onChange={(e) => setStrike(e.target.value)} /></Field>
        <Field label="Domestic rate (%)"><input type="number" className={inputCls} value={domestic} step={0.25} onChange={(e) => setDomestic(e.target.value)} /></Field>
        <Field label="Foreign rate (%)"><input type="number" className={inputCls} value={foreign} step={0.25} onChange={(e) => setForeign(e.target.value)} /></Field>
        <Field label="Volatility (%)"><input type="number" className={inputCls} value={vol} step={1} onChange={(e) => setVol(e.target.value)} /></Field>
        <Field label="Expiry (yrs)"><input type="number" className={inputCls} value={maturity} step={0.25} onChange={(e) => setMaturity(e.target.value)} /></Field>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runButton(valid, loading, "", "")}>
        {loading ? "Pricing…" : "Price FX option"}
      </button>
      {!valid && <p className="text-[11px] text-slate-400">Spot/strike/vol/expiry &gt; 0, finite rates.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="Price" value={fmt(result.price, 6)} tone="accent" />
            <MetricCard label="d1" value={fmt(result.d1)} />
            <MetricCard label="d2" value={fmt(result.d2)} />
            <MetricCard label="Delta" value={fmt(result.delta)} tone={result.delta >= 0 ? "positive" : "danger"} />
            <MetricCard label="Gamma" value={fmt(result.gamma)} />
            <MetricCard label="Vega" value={fmt(result.vega)} />
          </div>
          <div>
            <p className="section-title mb-1">Payoff at expiry (intrinsic)</p>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={payoffData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="s" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={(v: number) => v.toFixed(2)} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(4)} formatLabel={(l) => (typeof l === "number" ? `S=${l.toFixed(3)}` : "")} />} />
                <ReferenceLine x={num(strike)} stroke={CHART_REF_LINE} strokeDasharray="4 3" />
                <Line type="monotone" dataKey="payoff" name="Payoff" stroke={seriesColor(5)} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">Intrinsic payoff at expiry vs spot; dashed line = strike. Theta/rho available via the API.</p>
          </div>
          {result.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
        </>
      )}
    </div>
  );
}

// ── Education ──────────────────────────────────────────────────────────────

function FxEducationTab() {
  const items: [string, string][] = [
    ["Quote convention", "Here the spot S is domestic currency per 1 unit of foreign currency (e.g. 150 JPY per USD → domestic = JPY, foreign = USD). Forward, carry, and PPP all use this convention."],
    ["Interest rate parity", "Covered interest rate parity sets the forward from the rate differential: continuous F = S·e^((r_d−r_f)T). If domestic rates are below foreign, the foreign currency trades at a forward discount — this is parity, not free profit."],
    ["FX carry", "Carry earns the interest differential of the high-yield leg over the low-yield funding leg, but bears currency risk: the spot can move against you. Carry is not free money — the differential often compensates for that risk."],
    ["Purchasing power parity", "Relative PPP implies a spot from inflation differentials: S_ppp = S_base·(domestic index / foreign index). Deviations suggest relative valuation under simplified inputs, not a timing signal; PPP gaps can persist for years."],
    ["Currency exposure", "Exposures are translated to a base currency and stressed with a uniform symmetric shock. This is an educational translation, not a covariance-based VaR model, and uses no live FX rates."],
    ["Garman-Kohlhagen", "The FX analogue of Black-Scholes: the foreign risk-free rate enters like a continuous dividend yield. Assumes constant volatility and lognormal spot — no smile, skew, or vol surface."],
    ["Limitations", "Everything here ignores bid/ask, funding/transaction costs, liquidity, capital controls, and whether the quoted rates are actually investable. Educational research only — not investment advice."],
  ];
  return (
    <div className="card space-y-3 p-5 text-sm text-slate-400">
      <p className="section-title">How to read the FX Lab</p>
      <ul className="space-y-2">
        {items.map(([title, body]) => (
          <li key={title}>
            <span className="font-semibold text-slate-200">{title}:</span> {body}
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-slate-400">{CAVEAT}</p>
    </div>
  );
}
