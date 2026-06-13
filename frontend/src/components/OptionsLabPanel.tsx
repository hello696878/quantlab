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
  priceBlackScholes,
  solveImpliedVolatility,
} from "@/lib/api";
import type {
  BlackScholesResponse,
  ImpliedVolResponse,
  OptionType,
  PayoffLeg,
  PayoffResponse,
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

type Tab = "pricing" | "implied_vol" | "payoff" | "education";

const inputCls = "ql-input px-2.5 py-1.5";
const labelCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400";

function num(s: string): number {
  return parseFloat(s);
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
  "Black–Scholes is a simplified European model: it does not model early " +
  "exercise (American options), discrete dividends, transaction costs, " +
  "liquidity, volatility smile, or term structure. Educational only — not a " +
  "fair value, a recommendation, or a trading system. No live option chains.";

export default function OptionsLabPanel({ initialTab = "pricing" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-600">
          The Options Lab prices simple European options, inspects Greeks, solves
          implied volatility, and visualizes expiration payoff diagrams — a
          deterministic, educational calculator.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      <div className="inline-flex flex-wrap overflow-hidden rounded-lg border border-slate-300">
        {(
          [
            ["pricing", "Pricing"],
            ["implied_vol", "Implied Vol"],
            ["payoff", "Payoff Builder"],
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
    num(S) > 0 && num(K) > 0 && num(T) > 0 && num(sigma) > 0 && !isNaN(num(r)) && !isNaN(num(q));

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
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

  const valid = num(mktPrice) > 0 && num(S) > 0 && num(K) > 0 && num(T) > 0;

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
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
    setLoading(true);
    setError(null);
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
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
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
