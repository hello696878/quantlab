"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import {
  BacktestApiError,
  computeOptionPayoff,
  computeTreeConvergence,
  priceBinomialTree,
  priceBlackScholes,
  priceMonteCarlo,
  solveImpliedVolatility,
} from "@/lib/api";
import type {
  BinomialTreeResponse,
  BlackScholesResponse,
  ExerciseStyle,
  ImpliedVolResponse,
  MonteCarloPayoffType,
  MonteCarloResponse,
  OptionType,
  PayoffLeg,
  PayoffResponse,
  TreeConvergenceResponse,
} from "@/lib/types";
import { useAccentColors } from "@/lib/useAccentColors";
import NeonTooltip from "@/components/charts/NeonTooltip";
import {
  CHART_AXIS,
  CHART_AXIS_LINE,
  CHART_GRID,
  CHART_REF_LINE,
  DANGER,
} from "@/components/charts/chartTheme";

type Tab = "pricing" | "implied_vol" | "payoff" | "tree" | "monte_carlo" | "education";

const inputCls = "ql-input px-2.5 py-1.5";
const labelCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400";

function num(s: string): number {
  return s.trim() === "" ? NaN : Number(s);
}

function finite(s: string): boolean {
  return Number.isFinite(num(s));
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

function OptionTypeToggle({
  value,
  onChange,
}: {
  value: OptionType;
  onChange: (v: OptionType) => void;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-lg border border-slate-300">
      {(["call", "put"] as OptionType[]).map((t) => (
        <button
          key={t}
          type="button"
          onClick={() => onChange(t)}
          className={
            "px-3 py-1.5 text-xs font-medium capitalize transition-colors " +
            (value === t ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50")
          }
        >
          {t}
        </button>
      ))}
    </div>
  );
}

const CAVEAT =
  "Black–Scholes is a simplified European model; Tree Pricing adds a simplified " +
  "CRR lattice for American exercise; Monte Carlo simulates GBM paths (with " +
  "sampling error) for European, Asian, and simple barrier options. The lab does " +
  "not model discrete dividends, assignment, transaction costs, liquidity, " +
  "volatility smile, term structure, stochastic volatility, or live option " +
  "chains. Educational only — not a fair value, a recommendation, or a trading " +
  "system.";

export default function OptionsLabPanel({ initialTab = "pricing" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-600">
          The Options Lab prices options with Black–Scholes, binomial trees, and
          Monte Carlo simulation, inspects Greeks, solves implied volatility, and
          visualizes expiration payoff diagrams — a reproducible, educational
          calculator.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      <div className="inline-flex flex-wrap overflow-hidden rounded-lg border border-slate-300">
        {(
          [
            ["pricing", "Pricing"],
            ["implied_vol", "Implied Vol"],
            ["payoff", "Payoff Builder"],
            ["tree", "Tree Pricing"],
            ["monte_carlo", "Monte Carlo"],
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

      {tab === "pricing" && <PricingTab />}
      {tab === "implied_vol" && <ImpliedVolTab />}
      {tab === "payoff" && <PayoffTab />}
      {tab === "tree" && <TreePricingTab />}
      {tab === "monte_carlo" && <MonteCarloTab />}
      {tab === "education" && <EducationTab />}
    </div>
  );
}

// ── Pricing ──────────────────────────────────────────────────────────────────

function PricingTab() {
  const [optionType, setOptionType] = useState<OptionType>("call");
  const [S, setS] = useState("100");
  const [K, setK] = useState("100");
  const [T, setT] = useState("1");
  const [r, setR] = useState("0.05");
  const [sigma, setSigma] = useState("0.20");
  const [q, setQ] = useState("0");
  const [result, setResult] = useState<BlackScholesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid =
    num(S) > 0 &&
    num(K) > 0 &&
    num(T) > 0 &&
    num(sigma) > 0 &&
    finite(r) &&
    finite(q);

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await priceBlackScholes({
        option_type: optionType,
        underlying_price: num(S),
        strike: num(K),
        time_to_expiry: num(T),
        risk_free_rate: num(r),
        volatility: num(sigma),
        dividend_yield: num(q),
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Black–Scholes Calculator</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Option type">
          <OptionTypeToggle value={optionType} onChange={setOptionType} />
        </Field>
        <Field label="Underlying S"><input type="number" className={inputCls} value={S} onChange={(e) => setS(e.target.value)} /></Field>
        <Field label="Strike K"><input type="number" className={inputCls} value={K} onChange={(e) => setK(e.target.value)} /></Field>
        <Field label="Expiry T (years)"><input type="number" className={inputCls} value={T} onChange={(e) => setT(e.target.value)} /></Field>
        <Field label="Rate r"><input type="number" className={inputCls} value={r} step={0.01} onChange={(e) => setR(e.target.value)} /></Field>
        <Field label="Volatility σ"><input type="number" className={inputCls} value={sigma} step={0.01} onChange={(e) => setSigma(e.target.value)} /></Field>
        <Field label="Dividend q"><input type="number" className={inputCls} value={q} step={0.01} onChange={(e) => setQ(e.target.value)} /></Field>
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
        {loading ? "Pricing…" : "Price option"}
      </button>
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}
      {result && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Price" value={result.price.toFixed(4)} />
          <Stat label="Delta" value={result.delta.toFixed(4)} />
          <Stat label="Gamma" value={result.gamma.toFixed(5)} />
          <Stat label="Vega (per 100%)" value={result.vega.toFixed(3)} />
          <Stat label="Theta (daily)" value={result.theta_daily.toFixed(4)} />
          <Stat label="Theta (annual)" value={result.theta_annual.toFixed(3)} />
          <Stat label="Rho (per 100%)" value={result.rho.toFixed(3)} />
          <Stat label="d1 / d2" value={`${result.d1.toFixed(3)} / ${result.d2.toFixed(3)}`} />
        </div>
      )}
      <p className="text-[11px] text-slate-400">
        Greeks: delta/gamma per 1.0 of the underlying; vega/rho raw, per 1.0
        (100%) move; theta shown per day and per year. Educational, not a fair
        value.
      </p>
    </div>
  );
}

// ── Implied Vol ──────────────────────────────────────────────────────────────

function ImpliedVolTab() {
  const [optionType, setOptionType] = useState<OptionType>("call");
  const [mktPrice, setMktPrice] = useState("10.45");
  const [S, setS] = useState("100");
  const [K, setK] = useState("100");
  const [T, setT] = useState("1");
  const [r, setR] = useState("0.05");
  const [q, setQ] = useState("0");
  const [result, setResult] = useState<ImpliedVolResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid =
    num(mktPrice) > 0 &&
    num(S) > 0 &&
    num(K) > 0 &&
    num(T) > 0 &&
    finite(r) &&
    finite(q);

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await solveImpliedVolatility({
          option_type: optionType,
          market_price: num(mktPrice),
          underlying_price: num(S),
          strike: num(K),
          time_to_expiry: num(T),
          risk_free_rate: num(r),
          dividend_yield: num(q),
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
      <p className="section-title">Implied Volatility Solver</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Option type"><OptionTypeToggle value={optionType} onChange={setOptionType} /></Field>
        <Field label="Market price"><input type="number" className={inputCls} value={mktPrice} step={0.01} onChange={(e) => setMktPrice(e.target.value)} /></Field>
        <Field label="Underlying S"><input type="number" className={inputCls} value={S} onChange={(e) => setS(e.target.value)} /></Field>
        <Field label="Strike K"><input type="number" className={inputCls} value={K} onChange={(e) => setK(e.target.value)} /></Field>
        <Field label="Expiry T (years)"><input type="number" className={inputCls} value={T} onChange={(e) => setT(e.target.value)} /></Field>
        <Field label="Rate r"><input type="number" className={inputCls} value={r} step={0.01} onChange={(e) => setR(e.target.value)} /></Field>
        <Field label="Dividend q"><input type="number" className={inputCls} value={q} step={0.01} onChange={(e) => setQ(e.target.value)} /></Field>
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
        {loading ? "Solving…" : "Solve implied vol"}
      </button>
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}
      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Stat
              label="Implied volatility"
              value={typeof result.implied_volatility === "number" ? `${(result.implied_volatility * 100).toFixed(2)}%` : "—"}
            />
            <Stat label="Converged" value={result.converged ? "Yes" : "No"} />
            <Stat label="Iterations" value={String(result.iterations)} />
          </div>
          {result.warning && (
            <p className="rounded-lg bg-amber-100 px-3 py-2 text-xs font-medium text-amber-700">
              {result.warning}
            </p>
          )}
        </>
      )}
      <p className="text-[11px] text-slate-400">
        Robust bisection solver. Prices outside the no-arbitrage bounds return a
        warning rather than a number — they have no valid implied volatility.
      </p>
    </div>
  );
}

// ── Payoff Builder ───────────────────────────────────────────────────────────

interface UiLeg {
  instrument: "option" | "stock";
  option_type: OptionType;
  side: "long" | "short";
  strike: string;
  premium: string;
  entry_price: string;
  quantity: string;
}

function optLeg(option_type: OptionType, side: "long" | "short", strike: number, premium: number): UiLeg {
  return { instrument: "option", option_type, side, strike: String(strike), premium: String(premium), entry_price: "100", quantity: "1" };
}
function stockLeg(side: "long" | "short", entry: number): UiLeg {
  return { instrument: "stock", option_type: "call", side, strike: "100", premium: "0", entry_price: String(entry), quantity: "1" };
}

const PRESETS: { id: string; label: string; legs: () => UiLeg[] }[] = [
  { id: "long_call", label: "Long Call", legs: () => [optLeg("call", "long", 100, 5)] },
  { id: "long_put", label: "Long Put", legs: () => [optLeg("put", "long", 100, 5)] },
  { id: "covered_call", label: "Covered Call", legs: () => [stockLeg("long", 100), optLeg("call", "short", 110, 3)] },
  { id: "protective_put", label: "Protective Put", legs: () => [stockLeg("long", 100), optLeg("put", "long", 95, 3)] },
  { id: "bull_call", label: "Bull Call Spread", legs: () => [optLeg("call", "long", 100, 5), optLeg("call", "short", 110, 2)] },
  { id: "bear_put", label: "Bear Put Spread", legs: () => [optLeg("put", "long", 110, 6), optLeg("put", "short", 100, 2)] },
  { id: "long_straddle", label: "Long Straddle", legs: () => [optLeg("call", "long", 100, 6), optLeg("put", "long", 100, 6)] },
  { id: "long_strangle", label: "Long Strangle", legs: () => [optLeg("call", "long", 110, 3), optLeg("put", "long", 90, 3)] },
  { id: "short_straddle", label: "Short Straddle", legs: () => [optLeg("call", "short", 100, 6), optLeg("put", "short", 100, 6)] },
  { id: "short_strangle", label: "Short Strangle", legs: () => [optLeg("call", "short", 110, 3), optLeg("put", "short", 90, 3)] },
];

function PayoffTab() {
  const colors = useAccentColors();
  const [preset, setPreset] = useState("long_call");
  const [legs, setLegs] = useState<UiLeg[]>(PRESETS[0].legs());
  const [priceMin, setPriceMin] = useState("50");
  const [priceMax, setPriceMax] = useState("150");
  const [result, setResult] = useState<PayoffResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const valid =
    num(priceMin) > 0 &&
    num(priceMax) > num(priceMin) &&
    legs.every((l) =>
      l.instrument === "stock"
        ? num(l.entry_price) > 0 && num(l.quantity) > 0
        : num(l.strike) > 0 && num(l.premium) >= 0 && num(l.quantity) > 0,
    );

  function applyPreset(id: string) {
    setPreset(id);
    const p = PRESETS.find((x) => x.id === id);
    if (p) setLegs(p.legs());
    setResult(null);
  }

  function setLeg(i: number, patch: Partial<UiLeg>) {
    setLegs((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const apiLegs: PayoffLeg[] = legs.map((l) =>
        l.instrument === "stock"
          ? { instrument: "stock", side: l.side, entry_price: num(l.entry_price), quantity: num(l.quantity) }
          : {
              instrument: "option",
              option_type: l.option_type,
              side: l.side,
              strike: num(l.strike),
              premium: num(l.premium),
              quantity: num(l.quantity),
            },
      );
      setResult(
        await computeOptionPayoff({
          legs: apiLegs,
          price_min: num(priceMin),
          price_max: num(priceMax),
          points: 121,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = result
    ? result.payoff_curve.map((p) => ({ price: p.underlying_price, payoff: p.payoff }))
    : [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Payoff Builder</p>
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => applyPreset(p.id)}
            className={
              "rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors " +
              (preset === p.id ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300 bg-white text-slate-600 hover:border-blue-400")
            }
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Editable legs */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-400">
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Instrument</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Type</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Side</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Strike</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Premium / Entry</th>
              <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Qty</th>
            </tr>
          </thead>
          <tbody>
            {legs.map((l, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-2 py-1">{l.instrument}</td>
                <td className="px-2 py-1">{l.instrument === "option" ? l.option_type : "—"}</td>
                <td className="px-2 py-1 capitalize">{l.side}</td>
                <td className="px-2 py-1">
                  {l.instrument === "option" ? (
                    <input type="number" className={inputCls + " w-20"} value={l.strike} onChange={(e) => setLeg(i, { strike: e.target.value })} />
                  ) : "—"}
                </td>
                <td className="px-2 py-1">
                  {l.instrument === "option" ? (
                    <input type="number" className={inputCls + " w-20"} value={l.premium} step={0.5} onChange={(e) => setLeg(i, { premium: e.target.value })} />
                  ) : (
                    <input type="number" className={inputCls + " w-20"} value={l.entry_price} onChange={(e) => setLeg(i, { entry_price: e.target.value })} />
                  )}
                </td>
                <td className="px-2 py-1">
                  <input type="number" className={inputCls + " w-16"} value={l.quantity} min={1} onChange={(e) => setLeg(i, { quantity: e.target.value })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-slate-400">
        Premiums are manual inputs for payoff education — not live quotes.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Price min"><input type="number" className={inputCls + " w-24"} value={priceMin} onChange={(e) => setPriceMin(e.target.value)} /></Field>
        <Field label="Price max"><input type="number" className={inputCls + " w-24"} value={priceMax} onChange={(e) => setPriceMax(e.target.value)} /></Field>
        <button
          type="button"
          onClick={run}
          disabled={!valid || loading}
          className={
            "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
            (valid && !loading ? "bg-blue-600 text-white hover:bg-blue-700" : "cursor-not-allowed bg-slate-100 text-slate-400")
          }
        >
          {loading ? "Computing…" : "Plot payoff"}
        </button>
      </div>
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-3 gap-2">
            <Stat label="Max profit" value={result.max_profit == null ? "Unbounded" : result.max_profit.toFixed(2)} />
            <Stat label="Max loss" value={result.max_loss == null ? "Unbounded" : result.max_loss.toFixed(2)} />
            <Stat label="Breakevens (approx.)" value={result.breakevens.length ? result.breakevens.map((b) => b.toFixed(1)).join(", ") : "—"} />
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
              <XAxis
                dataKey="price"
                type="number"
                domain={["dataMin", "dataMax"]}
                tick={{ fontSize: 11, fill: CHART_AXIS }}
                axisLine={{ stroke: CHART_AXIS_LINE }}
                tickLine={false}
              />
              <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} />
              <Tooltip
                content={
                  <NeonTooltip
                    formatValue={(v: number) => v.toFixed(2)}
                    formatLabel={(l) => (typeof l === "number" ? `Underlying ${l.toFixed(1)}` : "")}
                  />
                }
              />
              <ReferenceLine y={0} stroke={CHART_REF_LINE} strokeDasharray="4 4" />
              {result.breakevens.map((b, i) => (
                <ReferenceLine key={i} x={b} stroke={DANGER} strokeDasharray="3 3" strokeOpacity={0.5} />
              ))}
              <Area type="monotone" dataKey="payoff" name="Payoff at expiry" stroke={colors.accent} strokeWidth={2} fill={colors.accent} fillOpacity={0.12} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="payoff" name="_line" legendType="none" stroke={colors.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <p className="text-[11px] text-slate-400">
            Payoff at expiration (x = underlying price, y = profit/loss). This is
            the terminal payoff, not path-dependent mark-to-market PnL.
            Breakevens are approximate (interpolated from the sampled curve).
          </p>
        </>
      )}
    </div>
  );
}

// ── Tree Pricing ─────────────────────────────────────────────────────────────

function ExerciseStyleToggle({
  value,
  onChange,
}: {
  value: ExerciseStyle;
  onChange: (v: ExerciseStyle) => void;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-lg border border-slate-300">
      {(["european", "american"] as ExerciseStyle[]).map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onChange(s)}
          className={
            "px-3 py-1.5 text-xs font-medium capitalize transition-colors " +
            (value === s ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50")
          }
        >
          {s}
        </button>
      ))}
    </div>
  );
}

// Fixed, safe step list for the convergence sweep (independent of the chosen N).
const CONVERGENCE_STEPS = [5, 10, 25, 50, 100, 200];

function TreeLatticeView({ result }: { result: BinomialTreeResponse }) {
  const colors = useAccentColors();
  if (!result.lattice) {
    return (
      <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
        {result.lattice_note ??
          "Tree visualization is limited to small step counts for readability."}
      </p>
    );
  }

  // Group nodes into columns by step; within a column, highest underlying on top.
  const columns = new Map<number, typeof result.lattice.nodes>();
  for (const node of result.lattice.nodes) {
    const col = columns.get(node.step) ?? [];
    col.push(node);
    columns.set(node.step, col);
  }
  const steps = Array.from(columns.keys()).sort((a, b) => a - b);
  const dt = result.tree_params.dt;

  return (
    <div>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {steps.map((step) => {
          const nodes = (columns.get(step) ?? []).slice().sort((a, b) => b.index - a.index);
          return (
            <div key={step} className="flex min-w-[88px] flex-col items-stretch gap-1.5">
              <div className="text-center text-[10px] font-medium uppercase tracking-wide text-slate-400">
                Step {step}
                <span className="block text-[9px] normal-case text-slate-300">
                  t={(step * dt).toFixed(3)}
                </span>
              </div>
              <div className="flex flex-1 flex-col justify-center gap-1.5">
                {nodes.map((n) => (
                  <div
                    key={n.index}
                    className={
                      "rounded-md border px-1.5 py-1 text-center " +
                      (n.early_exercise
                        ? "border-amber-400 bg-amber-50"
                        : "border-slate-200 bg-white")
                    }
                    title={
                      `Underlying ${n.underlying_price.toFixed(2)} · option ${n.option_value.toFixed(2)}` +
                      ` · intrinsic ${n.intrinsic_value.toFixed(2)}` +
                      (n.early_exercise ? " · early exercise optimal" : "")
                    }
                  >
                    <div className="mono text-[11px] font-semibold text-slate-700">
                      {n.underlying_price.toFixed(2)}
                    </div>
                    <div className="mono text-[10px]" style={{ color: colors.accent }}>
                      {n.option_value.toFixed(2)}
                    </div>
                    {n.early_exercise && (
                      <div className="text-[8px] font-bold uppercase text-amber-600">EX</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-1 text-[11px] text-slate-400">
        Each node shows the <span className="font-medium text-slate-600">underlying price</span>{" "}
        (top) and <span style={{ color: colors.accent }}>option value</span> (bottom). Amber{" "}
        <span className="font-bold text-amber-600">EX</span> nodes are where early exercise is
        optimal (American only).
      </p>
    </div>
  );
}

function TreePricingTab() {
  const colors = useAccentColors();
  const [optionType, setOptionType] = useState<OptionType>("call");
  const [exerciseStyle, setExerciseStyle] = useState<ExerciseStyle>("european");
  const [S, setS] = useState("100");
  const [K, setK] = useState("100");
  const [T, setT] = useState("1");
  const [r, setR] = useState("0.05");
  const [sigma, setSigma] = useState("0.20");
  const [q, setQ] = useState("0");
  const [steps, setSteps] = useState("100");
  const [result, setResult] = useState<BinomialTreeResponse | null>(null);
  const [convergence, setConvergence] = useState<TreeConvergenceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [convergenceError, setConvergenceError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const stepsNum = num(steps);
  const stepsInt = Number.isInteger(stepsNum) ? stepsNum : NaN;
  const valid =
    num(S) > 0 &&
    num(K) > 0 &&
    num(T) > 0 &&
    num(sigma) > 0 &&
    finite(r) &&
    finite(q) &&
    Number.isInteger(stepsNum) &&
    stepsInt >= 1 &&
    stepsInt <= 1000;

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
    setConvergenceError(null);
    setResult(null);
    setConvergence(null);
    const base = {
      option_type: optionType,
      underlying_price: num(S),
      strike: num(K),
      time_to_expiry: num(T),
      risk_free_rate: num(r),
      volatility: num(sigma),
      dividend_yield: num(q),
    };
    try {
      const priced = await priceBinomialTree({ ...base, exercise_style: exerciseStyle, steps: stepsInt });
      setResult(priced);
      try {
        const conv = await computeTreeConvergence({
          ...base,
          exercise_style: exerciseStyle,
          step_values: CONVERGENCE_STEPS,
        });
        setConvergence(conv);
      } catch (e) {
        setConvergence(null);
        const message = e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.";
        setConvergenceError(`Price calculated, but the convergence sweep was unavailable: ${message}`);
      }
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const isAmerican = exerciseStyle === "american";
  const refLabel = isAmerican ? "European reference (BS)" : "Black–Scholes";
  const convChartData =
    convergence?.points.map((p) => ({ steps: p.steps, price: p.price })) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Tree Pricing — Binomial Lattice</p>
      <p className="text-xs text-slate-500">
        Binomial trees approximate option values by stepping through possible up/down price
        paths. American exercise is handled by checking, at each node, whether exercising early
        is better than continuing. European tree prices converge to Black–Scholes as the step
        count grows. Educational lattice model — a numerical approximation, not a fair value.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Model">
          <div className="rounded-lg border border-slate-300 bg-slate-50 px-2.5 py-1.5 text-xs font-medium text-slate-600">
            Binomial (CRR)
            <span className="ml-1 text-[10px] text-slate-400">· Trinomial planned</span>
          </div>
        </Field>
        <Field label="Option type">
          <OptionTypeToggle value={optionType} onChange={setOptionType} />
        </Field>
        <Field label="Exercise style">
          <ExerciseStyleToggle value={exerciseStyle} onChange={setExerciseStyle} />
        </Field>
        <Field label="Steps N (1–1000)">
          <input type="number" className={inputCls} value={steps} min={1} max={1000} step={1} onChange={(e) => setSteps(e.target.value)} />
        </Field>
        <Field label="Underlying S"><input type="number" className={inputCls} value={S} onChange={(e) => setS(e.target.value)} /></Field>
        <Field label="Strike K"><input type="number" className={inputCls} value={K} onChange={(e) => setK(e.target.value)} /></Field>
        <Field label="Expiry T (years)"><input type="number" className={inputCls} value={T} onChange={(e) => setT(e.target.value)} /></Field>
        <Field label="Rate r"><input type="number" className={inputCls} value={r} step={0.01} onChange={(e) => setR(e.target.value)} /></Field>
        <Field label="Volatility σ"><input type="number" className={inputCls} value={sigma} step={0.01} onChange={(e) => setSigma(e.target.value)} /></Field>
        <Field label="Dividend q"><input type="number" className={inputCls} value={q} step={0.01} onChange={(e) => setQ(e.target.value)} /></Field>
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
        {loading ? "Pricing…" : "Price on tree"}
      </button>
      {!valid && (
        <p className="text-[11px] text-slate-400">
          Steps must be a whole number between 1 and 1000; S, K, T, σ must be positive.
        </p>
      )}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label={`Tree price (${result.exercise_style})`} value={result.price.toFixed(4)} />
            <Stat label={refLabel} value={result.convergence.black_scholes_price.toFixed(4)} />
            <Stat label="Difference" value={result.convergence.difference.toFixed(4)} />
            <Stat
              label="Early exercise"
              value={result.early_exercise.detected ? "Detected" : "None"}
            />
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Up factor u" value={result.tree_params.up_factor.toFixed(4)} />
            <Stat label="Down factor d" value={result.tree_params.down_factor.toFixed(4)} />
            <Stat label="Risk-neutral p" value={result.tree_params.risk_neutral_prob.toFixed(4)} />
            <Stat label="dt" value={result.tree_params.dt.toFixed(4)} />
          </div>

          {isAmerican && (
            <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
              {result.early_exercise.detected ? (
                <>
                  Early exercise first becomes optimal at step{" "}
                  <span className="font-semibold">{result.early_exercise.first_step}</span>{" "}
                  (t ≈ {result.early_exercise.first_time?.toFixed(3)} yr).{" "}
                  {optionType === "put"
                    ? "Early exercise can be optimal when the put is sufficiently deep in the money."
                    : "Dividends can make early call exercise optimal."}
                </>
              ) : optionType === "call" && num(q) === 0 ? (
                "Early exercise is usually not optimal for non-dividend-paying American calls in this simplified model."
              ) : (
                "No early-exercise node was optimal for these parameters."
              )}
            </div>
          )}

          {result.warnings.length > 0 && (
            <div className="rounded-lg bg-amber-100 px-3 py-2 text-xs font-medium text-amber-700">
              {result.warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          )}

          {convergenceError && (
            <div className="rounded-lg bg-amber-100 px-3 py-2 text-xs font-medium text-amber-700">
              {convergenceError}
            </div>
          )}

          {/* Convergence panel */}
          {convergence && (
            <div>
              <p className="section-title mb-1">Convergence vs steps</p>
              <p className="mb-2 text-[11px] text-slate-400">
                {isAmerican
                  ? "American tree price across step counts; the dashed line is the Black–Scholes European reference (no early-exercise value)."
                  : "Tree price converges toward the dashed Black–Scholes line as the step count grows."}
              </p>
              <ResponsiveContainer width="100%" height={220}>
                <ComposedChart data={convChartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey="steps"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    axisLine={{ stroke: CHART_AXIS_LINE }}
                    tickLine={false}
                    label={{ value: "steps", position: "insideBottom", offset: -2, fontSize: 10, fill: CHART_AXIS }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    axisLine={false}
                    tickLine={false}
                    width={56}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    content={
                      <NeonTooltip
                        formatValue={(v: number) => v.toFixed(4)}
                        formatLabel={(l) => (typeof l === "number" ? `${l} steps` : "")}
                      />
                    }
                  />
                  <ReferenceLine
                    y={convergence.black_scholes_price}
                    stroke={CHART_REF_LINE}
                    strokeDasharray="5 4"
                  />
                  <Line type="monotone" dataKey="price" name="Tree price" stroke={colors.accent} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="text-[11px] text-slate-400">
                {refLabel}: {convergence.black_scholes_price.toFixed(4)}
              </p>
            </div>
          )}

          {/* Tree visualization */}
          <div>
            <p className="section-title mb-1">Lattice</p>
            <TreeLatticeView result={result} />
          </div>
        </>
      )}

      <p className="text-[11px] text-slate-400">
        Tree models are numerical approximations: results depend on the step count, the
        volatility input, the (continuous) dividend assumption, and the exercise style. No live
        option chains, no volatility surface, no production risk engine.
      </p>
    </div>
  );
}

// ── Monte Carlo ──────────────────────────────────────────────────────────────

const MC_PAYOFFS: { value: MonteCarloPayoffType; label: string; barrier: boolean }[] = [
  { value: "european_call", label: "European Call", barrier: false },
  { value: "european_put", label: "European Put", barrier: false },
  { value: "asian_call", label: "Asian Call (avg)", barrier: false },
  { value: "asian_put", label: "Asian Put (avg)", barrier: false },
  { value: "up_and_out_call", label: "Up-and-Out Call", barrier: true },
  { value: "down_and_out_put", label: "Down-and-Out Put", barrier: true },
];

const MC_CONVERGENCE_SIMS = [1000, 5000, 10000, 25000];

interface ConvRow {
  simulations: number;
  price: number;
  standard_error: number;
}

function MonteCarloTab() {
  const colors = useAccentColors();
  const [payoffType, setPayoffType] = useState<MonteCarloPayoffType>("european_call");
  const [S, setS] = useState("100");
  const [K, setK] = useState("100");
  const [T, setT] = useState("1");
  const [r, setR] = useState("0.05");
  const [sigma, setSigma] = useState("0.20");
  const [q, setQ] = useState("0");
  const [steps, setSteps] = useState("252");
  const [simulations, setSimulations] = useState("10000");
  const [seed, setSeed] = useState("42");
  const [antithetic, setAntithetic] = useState(false);
  const [barrier, setBarrier] = useState("120");
  const [result, setResult] = useState<MonteCarloResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [convRows, setConvRows] = useState<ConvRow[] | null>(null);
  const [convLoading, setConvLoading] = useState(false);

  const isBarrier = MC_PAYOFFS.find((p) => p.value === payoffType)?.barrier ?? false;
  const stepsInt = Math.trunc(num(steps));
  const simsInt = Math.trunc(num(simulations));
  const seedInt = Math.trunc(num(seed));
  const valid =
    num(S) > 0 &&
    num(K) > 0 &&
    num(T) > 0 &&
    num(sigma) > 0 &&
    finite(r) &&
    finite(q) &&
    Number.isInteger(stepsInt) &&
    stepsInt >= 1 &&
    stepsInt <= 2000 &&
    Number.isInteger(simsInt) &&
    simsInt >= 100 &&
    simsInt <= 200000 &&
    Number.isInteger(seedInt) &&
    seedInt >= 0 &&
    (!isBarrier || num(barrier) > 0);

  function baseRequest(sims: number) {
    return {
      payoff_type: payoffType,
      underlying_price: num(S),
      strike: num(K),
      time_to_expiry: num(T),
      risk_free_rate: num(r),
      volatility: num(sigma),
      dividend_yield: num(q),
      steps: stepsInt,
      simulations: sims,
      seed: seedInt,
      antithetic,
      ...(isBarrier ? { barrier_price: num(barrier) } : {}),
    };
  }

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setConvRows(null);
    try {
      setResult(await priceMonteCarlo(baseRequest(simsInt)));
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  async function runConvergence() {
    if (!valid) return;
    setConvLoading(true);
    try {
      const rows: ConvRow[] = [];
      for (const sims of MC_CONVERGENCE_SIMS) {
        const res = await priceMonteCarlo(baseRequest(sims));
        rows.push({ simulations: sims, price: res.price, standard_error: res.standard_error });
      }
      setConvRows(rows);
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setConvLoading(false);
    }
  }

  const hasBsRef = result?.black_scholes_reference != null;
  const preview = result?.path_preview ?? [];
  const pathChartData = preview.length
    ? preview[0].points.map((pt, i) => {
        const row: Record<string, number> = { time: pt.time };
        for (const p of preview) row[`p${p.path_id}`] = p.points[i]?.price ?? NaN;
        return row;
      })
    : [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Monte Carlo Pricing — GBM Simulation</p>
      <p className="text-xs text-slate-500">
        Prices options by simulating many risk-neutral price paths under Geometric Brownian
        Motion and averaging the discounted payoff. More simulations shrink the standard error
        roughly like 1/√N; more steps refine path discretization for path-dependent payoffs.
        Educational stochastic simulation with sampling error — not a fair value.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Payoff type">
          <select
            className={inputCls}
            value={payoffType}
            onChange={(e) => {
              setPayoffType(e.target.value as MonteCarloPayoffType);
              setResult(null);
              setConvRows(null);
            }}
          >
            {MC_PAYOFFS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Underlying S"><input type="number" className={inputCls} value={S} onChange={(e) => setS(e.target.value)} /></Field>
        <Field label="Strike K"><input type="number" className={inputCls} value={K} onChange={(e) => setK(e.target.value)} /></Field>
        {isBarrier && (
          <Field label="Barrier"><input type="number" className={inputCls} value={barrier} onChange={(e) => setBarrier(e.target.value)} /></Field>
        )}
        <Field label="Expiry T (years)"><input type="number" className={inputCls} value={T} onChange={(e) => setT(e.target.value)} /></Field>
        <Field label="Rate r"><input type="number" className={inputCls} value={r} step={0.01} onChange={(e) => setR(e.target.value)} /></Field>
        <Field label="Volatility σ"><input type="number" className={inputCls} value={sigma} step={0.01} onChange={(e) => setSigma(e.target.value)} /></Field>
        <Field label="Dividend q"><input type="number" className={inputCls} value={q} step={0.01} onChange={(e) => setQ(e.target.value)} /></Field>
        <Field label="Steps (1–2000)"><input type="number" className={inputCls} value={steps} min={1} max={2000} step={1} onChange={(e) => setSteps(e.target.value)} /></Field>
        <Field label="Simulations (100–200k)"><input type="number" className={inputCls} value={simulations} min={100} max={200000} step={1000} onChange={(e) => setSimulations(e.target.value)} /></Field>
        <Field label="Seed"><input type="number" className={inputCls} value={seed} min={0} step={1} onChange={(e) => setSeed(e.target.value)} /></Field>
        <Field label="Variance reduction">
          <label className="flex items-center gap-2 py-1.5 text-xs text-slate-600">
            <input type="checkbox" checked={antithetic} onChange={(e) => setAntithetic(e.target.checked)} />
            Antithetic variates
          </label>
        </Field>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={run}
          disabled={!valid || loading}
          className={
            "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
            (valid && !loading ? "bg-blue-600 text-white hover:bg-blue-700" : "cursor-not-allowed bg-slate-100 text-slate-400")
          }
        >
          {loading ? "Simulating…" : "Run Monte Carlo"}
        </button>
        <button
          type="button"
          onClick={runConvergence}
          disabled={!valid || convLoading}
          className={
            "rounded-lg border px-3 py-2 text-xs font-medium transition-colors " +
            (valid && !convLoading ? "border-slate-300 bg-white text-slate-600 hover:border-blue-400" : "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400")
          }
        >
          {convLoading ? "Running…" : "Run convergence (1k–25k)"}
        </button>
      </div>
      {!valid && (
        <p className="text-[11px] text-slate-400">
          Steps 1–2000 and simulations 100–200,000 must be whole numbers; S, K, T, σ positive;
          barrier required for barrier payoffs.
        </p>
      )}
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Monte Carlo price" value={result.price.toFixed(4)} />
            <Stat label="Standard error" value={result.standard_error.toFixed(4)} />
            <Stat
              label="95% CI"
              value={`${result.confidence_interval_95.lower.toFixed(3)} – ${result.confidence_interval_95.upper.toFixed(3)}`}
            />
            {hasBsRef ? (
              <Stat label="Black–Scholes ref." value={result.black_scholes_reference!.toFixed(4)} />
            ) : (
              <Stat label="Average type" value={result.average_type ?? "—"} />
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {hasBsRef && (
              <Stat label="Diff vs BS" value={result.difference_vs_black_scholes!.toFixed(4)} />
            )}
            <Stat label="Simulations" value={result.simulations.toLocaleString()} />
            <Stat label="Steps" value={String(result.steps)} />
            <Stat label="Seed" value={`${result.seed}${result.antithetic ? " · antithetic" : ""}`} />
          </div>

          {result.warnings.length > 0 && (
            <div className="rounded-lg bg-amber-100 px-3 py-2 text-xs font-medium text-amber-700">
              {result.warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          )}

          {/* Path preview */}
          {pathChartData.length > 0 && (
            <div>
              <p className="section-title mb-1">Path preview</p>
              <p className="mb-2 text-[11px] text-slate-400">
                A small sample of simulated paths (the engine never returns all paths). x = time
                (years), y = simulated underlying price.
              </p>
              <ResponsiveContainer width="100%" height={240}>
                <ComposedChart data={pathChartData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey="time"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    axisLine={{ stroke: CHART_AXIS_LINE }}
                    tickLine={false}
                    tickFormatter={(v: number) => v.toFixed(2)}
                  />
                  <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} />
                  <ReferenceLine y={num(K)} stroke={CHART_REF_LINE} strokeDasharray="5 4" />
                  {preview.map((p) => (
                    <Line
                      key={p.path_id}
                      type="monotone"
                      dataKey={`p${p.path_id}`}
                      stroke={colors.accent}
                      strokeWidth={1}
                      strokeOpacity={0.45}
                      dot={false}
                      isAnimationActive={false}
                    />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
              <p className="text-[11px] text-slate-400">
                Dashed line = strike {num(K)}. Paths are a representative, reproducible sample for
                the chosen seed.
              </p>
            </div>
          )}
        </>
      )}

      {/* Convergence table */}
      {convRows && (
        <div>
          <p className="section-title mb-1">Convergence (standard error shrinks with N)</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-400">
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Simulations</th>
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Price</th>
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Std error</th>
                  <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">95% CI half-width</th>
                </tr>
              </thead>
              <tbody>
                {convRows.map((row) => (
                  <tr key={row.simulations} className="border-t border-slate-100">
                    <td className="px-2 py-1 mono">{row.simulations.toLocaleString()}</td>
                    <td className="px-2 py-1 mono">{row.price.toFixed(4)}</td>
                    <td className="px-2 py-1 mono">{row.standard_error.toFixed(4)}</td>
                    <td className="px-2 py-1 mono">±{(1.96 * row.standard_error).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            Standard error falls roughly like 1/√N — quartering it takes ~4× the simulations.
          </p>
        </div>
      )}

      <p className="text-[11px] text-slate-400">
        Monte Carlo carries sampling error and assumes GBM with constant volatility. Barrier
        monitoring is discrete over the simulated steps; Asian averaging is arithmetic. No
        stochastic volatility, no volatility surface, no live option chains, no production exotic
        pricing.
      </p>
    </div>
  );
}

// ── Education ────────────────────────────────────────────────────────────────

function EducationTab() {
  return (
    <div className="card space-y-3 p-5 text-sm text-slate-600">
      <p className="section-title">How to read the Options Lab</p>
      <p>
        <span className="font-semibold text-slate-700">Black–Scholes</span> prices
        a European option assuming lognormal prices with constant volatility and
        a continuous dividend yield. It is a model, not a market — real options
        deviate from it through smiles, term structure, and early-exercise value.
      </p>
      <p>
        <span className="font-semibold text-slate-700">Greeks</span> are
        sensitivities: delta (to the underlying), gamma (to delta), vega (to
        volatility), theta (to the passage of time), rho (to rates). They are
        local, instantaneous estimates that change as the inputs move.
      </p>
      <p>
        <span className="font-semibold text-slate-700">Implied volatility</span>{" "}
        is the volatility that makes the model price match a market price — a
        re-expression of price, not a forecast.
      </p>
      <p>
        <span className="font-semibold text-slate-700">Payoff diagrams</span> show
        profit/loss at expiration across underlying prices. They ignore the path
        the price took, financing, assignment, and the mark-to-market swings
        before expiry — a short option can show a small bounded payoff yet carry
        large interim losses (see the Volmageddon case in Quant Disasters).
      </p>
      <p className="text-[11px] text-slate-400">{CAVEAT}</p>
    </div>
  );
}
