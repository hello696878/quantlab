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
} from "recharts";
import {
  BacktestApiError,
  computeCds,
  computeHazard,
  computeMerton,
  priceRiskyBond,
} from "@/lib/api";
import type {
  CdsResponse,
  HazardResponse,
  MertonResponse,
  RiskyBondResponse,
} from "@/lib/types";
import MetricCard from "@/components/MetricCard";
import NeonTooltip from "@/components/charts/NeonTooltip";
import { CHART_AXIS, CHART_AXIS_LINE, CHART_GRID, DANGER } from "@/components/charts/chartTheme";
import { seriesColor } from "@/lib/chartPalette";

type Tab = "merton" | "hazard" | "cds" | "bond" | "education";

const inputCls = "ql-input px-2.5 py-1.5";
const labelCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400";

const SURVIVAL_COLOR = "var(--emerald)";
const DEFAULT_COLOR = DANGER;
const EQUITY_COLOR = seriesColor(0); // cyan
const DEBT_COLOR = seriesColor(2); // violet
const PROT_COLOR = seriesColor(4); // amber
const PREM_COLOR = seriesColor(0); // cyan
const RISKY_COLOR = seriesColor(4); // amber
const RISKFREE_COLOR = seriesColor(0); // cyan
const PV_COLOR = seriesColor(0);

const CAVEAT =
  "Credit models depend heavily on assumptions about asset value, asset volatility, recovery rate, " +
  "capital structure, liquidity, seniority, covenants, and calibration quality. Educational research " +
  "only — no live CDS spreads, no live bond prices, no full CVA, not investment advice.";

function num(s: string): number {
  return s.trim() === "" ? NaN : Number(s);
}
function finite(s: string): boolean {
  return Number.isFinite(num(s));
}
function wholePeriods(maturity: string, frequency: string): boolean {
  const raw = num(maturity) * num(frequency);
  return Number.isFinite(raw) && Math.abs(raw - Math.round(raw)) < 1e-9;
}
function fmt(v: number | null | undefined, d = 2): string {
  return v == null || !Number.isFinite(v) ? "—" : v.toFixed(d);
}
function pct(v: number | null | undefined, d = 2): string {
  return v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`;
}
function bps(v: number | null | undefined, d = 1): string {
  return v == null || !Number.isFinite(v) ? "—" : `${v.toFixed(d)} bps`;
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

function runBtnCls(valid: boolean, loading: boolean) {
  return (
    "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
    (valid && !loading
      ? "bg-[var(--accent)] text-[var(--on-accent)] shadow-[var(--accent-glow)] hover:brightness-110"
      : "cursor-not-allowed border border-[var(--line)] bg-[var(--glass)] text-slate-500")
  );
}

const FREQUENCIES = [1, 2, 4, 12];

export default function CreditLabPanel({ initialTab = "merton" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-300">
          The Credit Risk Lab explores structural and reduced-form credit models — the Merton model,
          distance to default, hazard rates and survival curves, CDS spread approximation, and risky
          bond pricing.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      <div className="ql-segmented">
        {(
          [
            ["merton", "Merton Model"],
            ["hazard", "Hazard / Survival"],
            ["cds", "CDS Spread"],
            ["bond", "Risky Bond"],
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

      {tab === "merton" && <MertonTab />}
      {tab === "hazard" && <HazardTab />}
      {tab === "cds" && <CdsTab />}
      {tab === "bond" && <RiskyBondTab />}
      {tab === "education" && <CreditEducationTab />}
    </div>
  );
}

// ── Merton ──────────────────────────────────────────────────────────────────

function MertonTab() {
  const [assetValue, setAssetValue] = useState("120");
  const [debtFace, setDebtFace] = useState("100");
  const [assetVol, setAssetVol] = useState("25");
  const [rfRate, setRfRate] = useState("4");
  const [maturity, setMaturity] = useState("1");
  const [recovery, setRecovery] = useState("40");
  const [result, setResult] = useState<MertonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid =
    num(assetValue) > 0 &&
    num(debtFace) > 0 &&
    num(assetVol) > 0 &&
    finite(rfRate) &&
    num(maturity) > 0 &&
    num(recovery) >= 0 &&
    num(recovery) <= 100;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await computeMerton({
          asset_value: num(assetValue),
          debt_face_value: num(debtFace),
          asset_volatility: num(assetVol) / 100,
          risk_free_rate: num(rfRate) / 100,
          time_to_maturity: num(maturity),
          recovery_rate: num(recovery) / 100,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const breakdown = result
    ? [
        { name: "Equity", value: result.equity_value },
        { name: "Debt", value: result.debt_value },
      ]
    : [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Merton Structural Model</p>
      <p className="text-xs text-slate-500">
        Equity is a call option on firm assets: E = V·N(d1) − D·e^(−rT)·N(d2). Risk-neutral default
        probability = N(−d2); credit spread from the implied risky debt yield.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Field label="Asset value (V)"><input type="number" className={inputCls} value={assetValue} onChange={(e) => setAssetValue(e.target.value)} /></Field>
        <Field label="Debt face (D)"><input type="number" className={inputCls} value={debtFace} onChange={(e) => setDebtFace(e.target.value)} /></Field>
        <Field label="Asset vol (%)"><input type="number" className={inputCls} value={assetVol} step={1} onChange={(e) => setAssetVol(e.target.value)} /></Field>
        <Field label="Risk-free rate (%)"><input type="number" className={inputCls} value={rfRate} step={0.25} onChange={(e) => setRfRate(e.target.value)} /></Field>
        <Field label="Maturity (yrs)"><input type="number" className={inputCls} value={maturity} step={0.5} onChange={(e) => setMaturity(e.target.value)} /></Field>
        <Field label="Recovery (%)"><input type="number" className={inputCls} value={recovery} step={5} onChange={(e) => setRecovery(e.target.value)} /></Field>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runBtnCls(valid, loading)}>
        {loading ? "Computing…" : "Run Merton model"}
      </button>
      {!valid && <p className="text-[11px] text-slate-400">Asset/debt/vol/maturity &gt; 0, recovery 0–100%.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="Equity value" value={fmt(result.equity_value)} tone="accent" />
            <MetricCard label="Debt value" value={fmt(result.debt_value)} />
            <MetricCard label="Distance to default" value={fmt(result.distance_to_default, 3)} tone={result.distance_to_default >= 0 ? "positive" : "danger"} />
            <MetricCard label="Default prob. (risk-neutral)" value={pct(result.risk_neutral_default_probability)} tone={result.risk_neutral_default_probability > 0.1 ? "warn" : "default"} />
            <MetricCard label="Credit spread" value={bps(result.credit_spread_bps)} tone="warn" />
            <MetricCard label="Expected loss" value={fmt(result.expected_loss)} tone="warn" />
          </div>
          <div>
            <p className="section-title mb-1">Capital structure (assets = equity + debt)</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={breakdown} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={56} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(2)} />} />
                <Bar dataKey="value" name="Value" isAnimationActive={false}>
                  <Cell fill={EQUITY_COLOR} />
                  <Cell fill={DEBT_COLOR} />
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: EQUITY_COLOR }}>● Equity (call on assets)</span>{"  "}
              <span style={{ color: DEBT_COLOR }}>● Risky debt</span> — distance to default uses the {result.dd_drift_used.replace(/_/g, " ")}.
            </p>
          </div>
          {result.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
        </>
      )}
    </div>
  );
}

// ── Hazard / Survival ────────────────────────────────────────────────────────

function HazardTab() {
  const [hazard, setHazard] = useState("2");
  const [recovery, setRecovery] = useState("40");
  const [maturity, setMaturity] = useState("5");
  const [rfRate, setRfRate] = useState("4");
  const [result, setResult] = useState<HazardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid = num(hazard) >= 0 && num(recovery) >= 0 && num(recovery) <= 100 && num(maturity) > 0 && finite(rfRate);

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await computeHazard({
          hazard_rate: num(hazard) / 100,
          recovery_rate: num(recovery) / 100,
          maturity_years: num(maturity),
          risk_free_rate: num(rfRate) / 100,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const curve = result?.curve.map((p) => ({ t: p.time, survival: p.survival_probability, def: p.default_probability })) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Hazard / Survival</p>
      <p className="text-xs text-slate-500">
        Constant-hazard reduced-form model: survival Q(t) = e^(−λt), cumulative default 1 − Q(t),
        expected loss (1 − R)·PD(t). The hazard rate is an assumption, not calibrated to market data.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Hazard rate λ (%)"><input type="number" className={inputCls} value={hazard} step={0.5} onChange={(e) => setHazard(e.target.value)} /></Field>
        <Field label="Recovery (%)"><input type="number" className={inputCls} value={recovery} step={5} onChange={(e) => setRecovery(e.target.value)} /></Field>
        <Field label="Maturity (yrs)"><input type="number" className={inputCls} value={maturity} step={1} onChange={(e) => setMaturity(e.target.value)} /></Field>
        <Field label="Risk-free rate (%)"><input type="number" className={inputCls} value={rfRate} step={0.25} onChange={(e) => setRfRate(e.target.value)} /></Field>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runBtnCls(valid, loading)}>
        {loading ? "Computing…" : "Build survival curve"}
      </button>
      {!valid && <p className="text-[11px] text-slate-400">λ ≥ 0, recovery 0–100%, maturity &gt; 0.</p>}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <MetricCard label="Survival at maturity" value={pct(result.survival_probability_at_maturity)} tone="positive" />
            <MetricCard label="Default prob. at maturity" value={pct(result.default_probability_at_maturity)} tone="warn" />
            <MetricCard label="Expected loss at maturity" value={pct(result.expected_loss_at_maturity)} tone="warn" />
            <MetricCard label="Simple CDS approx (λ·LGD)" value={bps(result.simple_cds_spread_bps)} tone="accent" />
          </div>
          <div>
            <p className="section-title mb-1">Survival vs cumulative default</p>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={curve} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(1)}y`} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={48} domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(2)}%`} formatLabel={(l) => (typeof l === "number" ? `${l.toFixed(2)}y` : "")} />} />
                <Line type="monotone" dataKey="survival" name="Survival" stroke={SURVIVAL_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="def" name="Cumulative default" stroke={DEFAULT_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: SURVIVAL_COLOR }}>● Survival Q(t)</span>{"  "}
              <span style={{ color: DEFAULT_COLOR }}>● Cumulative default 1 − Q(t)</span>.
            </p>
          </div>
          {result.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
        </>
      )}
    </div>
  );
}

// ── CDS Spread ───────────────────────────────────────────────────────────────

function CdsTab() {
  const [hazard, setHazard] = useState("2");
  const [recovery, setRecovery] = useState("40");
  const [maturity, setMaturity] = useState("5");
  const [rfRate, setRfRate] = useState("4");
  const [freq, setFreq] = useState("4");
  const [notional, setNotional] = useState("1000000");
  const [result, setResult] = useState<CdsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const scheduleValid = wholePeriods(maturity, freq);
  const valid =
    num(hazard) >= 0 &&
    num(recovery) >= 0 &&
    num(recovery) <= 100 &&
    num(maturity) > 0 &&
    finite(rfRate) &&
    num(notional) > 0 &&
    scheduleValid;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await computeCds({
          hazard_rate: num(hazard) / 100,
          recovery_rate: num(recovery) / 100,
          maturity_years: num(maturity),
          risk_free_rate: num(rfRate) / 100,
          payment_frequency: num(freq),
          notional: num(notional),
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const legData = result
    ? [
        { name: "Protection leg PV", value: result.protection_leg_pv },
        { name: "Premium leg PV (at fair spread)", value: result.fair_spread * result.risky_pv01 },
      ]
    : [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">CDS Spread</p>
      <p className="text-xs text-slate-500">
        Simplified par CDS spread: fair spread = protection-leg PV / risky PV01. The credit-triangle
        approximation is λ·(1 − R). Not ISDA pricing and not a tradable quote.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Field label="Hazard rate λ (%)"><input type="number" className={inputCls} value={hazard} step={0.5} onChange={(e) => setHazard(e.target.value)} /></Field>
        <Field label="Recovery (%)"><input type="number" className={inputCls} value={recovery} step={5} onChange={(e) => setRecovery(e.target.value)} /></Field>
        <Field label="Maturity (yrs)"><input type="number" className={inputCls} value={maturity} step={1} onChange={(e) => setMaturity(e.target.value)} /></Field>
        <Field label="Risk-free rate (%)"><input type="number" className={inputCls} value={rfRate} step={0.25} onChange={(e) => setRfRate(e.target.value)} /></Field>
        <Field label="Frequency / yr">
          <select className={inputCls} value={freq} onChange={(e) => setFreq(e.target.value)}>
            {FREQUENCIES.map((f) => (<option key={f} value={f}>{f}</option>))}
          </select>
        </Field>
        <Field label="Notional"><input type="number" className={inputCls} value={notional} step={100000} onChange={(e) => setNotional(e.target.value)} /></Field>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runBtnCls(valid, loading)}>
        {loading ? "Computing…" : "Compute CDS spread"}
      </button>
      {!valid && (
        <p className="text-[11px] text-slate-400">
          λ ≥ 0, recovery 0–100%, maturity &gt; 0, notional &gt; 0, and maturity ×
          frequency must be a whole number of payment periods.
        </p>
      )}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            <MetricCard label="Fair spread" value={bps(result.fair_spread_bps)} tone="accent" />
            <MetricCard label="Simple approx (λ·LGD)" value={bps(result.simple_spread_bps)} />
            <MetricCard label="Protection leg PV" value={money(result.protection_leg_pv)} tone="warn" />
            <MetricCard label="Risky PV01" value={money(result.risky_pv01)} />
            <MetricCard label="Survival at maturity" value={pct(result.survival_probability_at_maturity)} tone="positive" />
          </div>
          <div>
            <p className="section-title mb-1">Leg balance (equal at the fair spread)</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={legData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={64} tickFormatter={(v: number) => money(v)} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => money(v)} />} />
                <Bar dataKey="value" name="PV" isAnimationActive={false}>
                  <Cell fill={PROT_COLOR} />
                  <Cell fill={PREM_COLOR} />
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: PROT_COLOR }}>● Protection leg PV</span>{"  "}
              <span style={{ color: PREM_COLOR }}>● Premium leg PV</span> — equal by construction at the fair spread.
            </p>
          </div>
          {result.warnings.map((w, i) => (<p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>))}
        </>
      )}
    </div>
  );
}

// ── Risky Bond ───────────────────────────────────────────────────────────────

function RiskyBondTab() {
  const [face, setFace] = useState("1000");
  const [coupon, setCoupon] = useState("5");
  const [maturity, setMaturity] = useState("5");
  const [freq, setFreq] = useState("2");
  const [rfRate, setRfRate] = useState("4");
  const [hazard, setHazard] = useState("2");
  const [recovery, setRecovery] = useState("40");
  const [result, setResult] = useState<RiskyBondResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const scheduleValid = wholePeriods(maturity, freq);
  const valid =
    num(face) > 0 &&
    num(coupon) >= 0 &&
    num(maturity) > 0 &&
    finite(rfRate) &&
    num(hazard) >= 0 &&
    num(recovery) >= 0 &&
    num(recovery) <= 100 &&
    scheduleValid;

  async function run() {
    if (!valid || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await priceRiskyBond({
          face_value: num(face),
          coupon_rate: num(coupon) / 100,
          maturity_years: num(maturity),
          coupon_frequency: num(freq),
          risk_free_rate: num(rfRate) / 100,
          hazard_rate: num(hazard) / 100,
          recovery_rate: num(recovery) / 100,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const priceData = result
    ? [
        { name: "Risky", value: result.risky_bond_price },
        { name: "Risk-free", value: result.risk_free_bond_price },
      ]
    : [];
  const pvData = result?.cash_flows.map((c) => ({ t: c.time, pv: c.present_value })) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Risky Bond Pricing</p>
      <p className="text-xs text-slate-500">
        Reduced-form risky bond: survival-weighted promised cash flows plus a recovery leg. Credit
        spread is a flat-yield approximation, not an OAS or a market quote.
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <Field label="Face value"><input type="number" className={inputCls} value={face} onChange={(e) => setFace(e.target.value)} /></Field>
        <Field label="Coupon (%)"><input type="number" className={inputCls} value={coupon} step={0.25} onChange={(e) => setCoupon(e.target.value)} /></Field>
        <Field label="Maturity (yrs)"><input type="number" className={inputCls} value={maturity} step={1} onChange={(e) => setMaturity(e.target.value)} /></Field>
        <Field label="Frequency / yr">
          <select className={inputCls} value={freq} onChange={(e) => setFreq(e.target.value)}>
            {FREQUENCIES.map((f) => (<option key={f} value={f}>{f}</option>))}
          </select>
        </Field>
        <Field label="Risk-free rate (%)"><input type="number" className={inputCls} value={rfRate} step={0.25} onChange={(e) => setRfRate(e.target.value)} /></Field>
        <Field label="Hazard rate λ (%)"><input type="number" className={inputCls} value={hazard} step={0.5} onChange={(e) => setHazard(e.target.value)} /></Field>
        <Field label="Recovery (%)"><input type="number" className={inputCls} value={recovery} step={5} onChange={(e) => setRecovery(e.target.value)} /></Field>
      </div>
      <button type="button" onClick={run} disabled={!valid || loading} className={runBtnCls(valid, loading)}>
        {loading ? "Pricing…" : "Price risky bond"}
      </button>
      {!valid && (
        <p className="text-[11px] text-slate-400">
          Face/maturity &gt; 0, coupon ≥ 0, λ ≥ 0, recovery 0–100%, and maturity ×
          frequency must be a whole number of coupon periods.
        </p>
      )}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            <MetricCard label="Risky bond price" value={fmt(result.risky_bond_price)} tone="accent" />
            <MetricCard label="Risk-free bond price" value={fmt(result.risk_free_bond_price)} />
            <MetricCard label="Credit spread" value={bps(result.credit_spread_bps)} tone="warn" />
            <MetricCard label="Expected loss" value={fmt(result.expected_loss)} tone="warn" />
            <MetricCard label="Survival at maturity" value={pct(result.survival_probability_at_maturity)} tone="positive" />
          </div>
          <div>
            <p className="section-title mb-1">Risky vs risk-free price</p>
            <ResponsiveContainer width="100%" height={160}>
              <ComposedChart data={priceData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={56} domain={["auto", "auto"]} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(2)} />} />
                <Bar dataKey="value" name="Price" isAnimationActive={false}>
                  <Cell fill={RISKY_COLOR} />
                  <Cell fill={RISKFREE_COLOR} />
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: RISKY_COLOR }}>● Risky</span>{"  "}
              <span style={{ color: RISKFREE_COLOR }}>● Risk-free</span> — the gap is the credit discount.
            </p>
          </div>
          <div>
            <p className="section-title mb-1">Survival-weighted cash-flow PV</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={pvData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(1)}y`} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(2)} formatLabel={(l) => (typeof l === "number" ? `${l.toFixed(2)}y` : "")} />} />
                <Bar dataKey="pv" name="PV" fill={PV_COLOR} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full max-w-2xl text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Time</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Cash flow</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Survival</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">DF</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">PV</th>
                  <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Recovery PV</th>
                </tr>
              </thead>
              <tbody>
                {result.cash_flows.map((c) => (
                  <tr key={c.time} className="border-t border-[var(--line)]">
                    <td className="px-2 py-1 text-right mono">{c.time.toFixed(2)}y</td>
                    <td className="px-2 py-1 text-right mono">{c.cash_flow.toFixed(2)}</td>
                    <td className="px-2 py-1 text-right mono">{pct(c.survival_probability)}</td>
                    <td className="px-2 py-1 text-right mono">{c.discount_factor.toFixed(5)}</td>
                    <td className="px-2 py-1 text-right mono">{c.present_value.toFixed(2)}</td>
                    <td className="px-2 py-1 text-right mono">{c.recovery_pv.toFixed(2)}</td>
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

// ── Education ──────────────────────────────────────────────────────────────

function CreditEducationTab() {
  const items: [string, string][] = [
    ["Structural vs reduced-form", "Structural models (Merton) derive default from the firm's capital structure — equity is a call on assets and default happens when assets fall below debt. Reduced-form models treat default as a random event with a hazard rate, calibrated to market prices rather than balance sheets."],
    ["Distance to default", "DD = [ln(V/D) + (drift − ½σ²)T] / (σ√T): how many asset-volatility standard deviations the firm is from the default point. With drift = r it equals d2, and the risk-neutral default probability is N(−DD)."],
    ["Hazard rate & survival", "A constant hazard λ gives survival Q(t) = e^(−λt) and cumulative default 1 − Q(t). Real hazard curves are not flat and are calibrated to CDS or bond prices."],
    ["Recovery rate", "Recovery R is the fraction of face value recovered on default; loss given default is 1 − R. It is highly uncertain and depends on seniority, collateral, and the workout process."],
    ["CDS spread approximation", "The credit triangle gives par spread ≈ λ·(1 − R); the discrete version equates the protection leg PV and the premium-leg risky PV01. Real CDS use ISDA conventions, accrual-on-default, and a calibrated hazard term structure."],
    ["Credit spread is not only default probability", "Observed credit spreads also compensate for liquidity, taxes, risk premia, recovery uncertainty, and supply/demand — not just expected default loss. Structural models often under-predict short-dated spreads (the 'credit spread puzzle')."],
    ["Limitations", "Everything here is educational: stylized assumptions, no live CDS or bond data, no full CVA, no credit-portfolio or rating-transition model, no calibration. Not investment advice."],
  ];
  return (
    <div className="card space-y-3 p-5 text-sm text-slate-400">
      <p className="section-title">How to read the Credit Risk Lab</p>
      <ul className="space-y-2">
        {items.map(([title, body]) => (
          <li key={title}>
            <span className="font-semibold text-slate-900">{title}:</span> {body}
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-slate-400">{CAVEAT}</p>
    </div>
  );
}
