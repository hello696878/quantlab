"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import {
  BacktestApiError,
  buildSampleVolSurface,
  buildVolSurface,
  computeOptionPayoff,
  computeTreeConvergence,
  priceBinomialTree,
  priceBlackScholes,
  priceHeston,
  priceMonteCarlo,
  solveImpliedVolatility,
} from "@/lib/api";
import type {
  BinomialTreeResponse,
  BlackScholesResponse,
  ExerciseStyle,
  ImpliedVolResponse,
  HestonResponse,
  MonteCarloPayoffType,
  MonteCarloResponse,
  OptionType,
  PayoffLeg,
  PayoffResponse,
  SurfaceResponse,
  SurfaceRowInput,
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
import {
  OPTIONS_CHART_PALETTE,
  SMILE_RAW_COLOR as CHART_SMILE_RAW_COLOR,
  SMILE_FIT_COLOR,
  TERM_STRUCTURE_COLOR,
  heatColor as paletteHeatColor,
  seriesColor,
} from "@/lib/chartPalette";
import {
  OPTIONS_SCENARIOS,
  getOptionsScenario,
  type OptionsScenarioPreset,
} from "@/lib/optionsScenarioRegistry";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";

const OPTIONS_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Black-Scholes pricing",
    formulas: [
      { label: "Call price", latex: "C = S e^{-qT} N(d_1) - K e^{-rT} N(d_2)" },
      { label: "Put price", latex: "P = K e^{-rT} N(-d_2) - S e^{-qT} N(-d_1)" },
      { label: "d₁, d₂", latex: "d_1 = \\frac{\\ln(S/K) + (r - q + \\tfrac{1}{2}\\sigma^2)T}{\\sigma\\sqrt{T}}, \\quad d_2 = d_1 - \\sigma\\sqrt{T}" },
    ],
  },
  {
    title: "Greeks",
    formulas: [
      { label: "Delta (call)", latex: "\\Delta = e^{-qT} N(d_1)" },
      { label: "Gamma", latex: "\\Gamma = \\frac{e^{-qT}\\varphi(d_1)}{S\\sigma\\sqrt{T}}" },
      { label: "Vega", latex: "\\nu = S e^{-qT}\\varphi(d_1)\\sqrt{T}" },
      { label: "Theta (call)", latex: "\\Theta = -\\frac{S e^{-qT}\\varphi(d_1)\\sigma}{2\\sqrt{T}} - rKe^{-rT}N(d_2) + qSe^{-qT}N(d_1)" },
      { label: "Rho (call)", latex: "\\rho = KTe^{-rT}N(d_2)" },
    ],
  },
];

/** Props every model tab accepts so an applied scenario preset can seed it. */
interface TabProps {
  scenario?: OptionsScenarioPreset | null;
}

/** Preset value → input string, falling back to the tab's own default. */
function pstr(value: number | undefined, fallback: string): string {
  return value == null ? fallback : String(value);
}

type Tab =
  | "pricing"
  | "implied_vol"
  | "payoff"
  | "tree"
  | "monte_carlo"
  | "surface"
  | "heston"
  | "compare"
  | "education";

// Grouped tab layout so the (now many) tools read as a coherent product.
const TAB_GROUPS: { label: string; tabs: [Tab, string][] }[] = [
  {
    label: "Core Pricing",
    tabs: [
      ["pricing", "Black–Scholes"],
      ["implied_vol", "Implied Vol"],
      ["tree", "Tree Pricing"],
    ],
  },
  {
    label: "Payoffs & Simulation",
    tabs: [
      ["payoff", "Payoff Builder"],
      ["monte_carlo", "Monte Carlo"],
      ["heston", "Heston"],
    ],
  },
  {
    label: "Volatility & Compare",
    tabs: [
      ["surface", "Vol Surface"],
      ["compare", "Model Compare"],
    ],
  },
  { label: "Learn", tabs: [["education", "Education"]] },
];

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
  "sampling error) for European, Asian, and simple barrier options; Vol Surface " +
  "builds an implied-vol surface from a manual/synthetic chain with an SVI " +
  "research fit; Heston adds a stochastic-volatility Monte Carlo (Euler, biased). " +
  "The lab does not model assignment, transaction costs, liquidity, or live " +
  "option chains, does not produce an arbitrage-free surface, and is not " +
  "calibrated to any market. Educational only — not a fair value, a " +
  "recommendation, or a trading system.";

export default function OptionsLabPanel({
  initialTab = "pricing",
  initialPresetId = null,
}: {
  initialTab?: Tab;
  initialPresetId?: string | null;
}) {
  const [tab, setTab] = useState<Tab>(() => {
    if (initialPresetId) {
      const p = getOptionsScenario(initialPresetId);
      if (p) return p.primaryTab;
    }
    return initialTab;
  });
  // Applied scenario preset (seeds the tabs). `presetNonce` keys the tab content
  // so re-applying a preset always re-seeds, even if the tab is already open.
  const [scenario, setScenario] = useState<OptionsScenarioPreset | null>(() =>
    initialPresetId ? getOptionsScenario(initialPresetId) ?? null : null,
  );
  const [presetNonce, setPresetNonce] = useState(0);
  const [notice, setNotice] = useState<string | null>(
    initialPresetId && getOptionsScenario(initialPresetId)
      ? `Scenario applied: ${getOptionsScenario(initialPresetId)!.name}`
      : null,
  );

  function applyScenario(preset: OptionsScenarioPreset) {
    setScenario(preset);
    setPresetNonce((n) => n + 1);
    setNotice(`Scenario applied: ${preset.name}`);
    setTab(preset.primaryTab);
  }

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-600">
          The Options Lab prices options with Black–Scholes, binomial trees, and
          Monte Carlo simulation, inspects Greeks, solves implied volatility,
          visualizes payoff diagrams, builds an implied-volatility surface with
          an SVI research fit, and simulates Heston stochastic volatility — a
          reproducible, educational calculator.
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      {/* Unified scenario presets — apply once, every tab seeds from it. */}
      <div className="card space-y-2 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className={labelCls + " mb-0"}>Scenario preset</span>
          <select
            className={inputCls}
            value={scenario?.id ?? ""}
            onChange={(e) => {
              if (!e.target.value) {
                setScenario(null);
                setNotice(null);
                return;
              }
              const preset = getOptionsScenario(e.target.value);
              if (preset) applyScenario(preset);
            }}
          >
            <option value="">Custom (no preset)</option>
            {OPTIONS_SCENARIOS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          {notice && (
            <span className="rounded-md bg-emerald-50 px-2 py-1 text-[11px] font-medium text-emerald-700">
              ✓ {notice}
            </span>
          )}
        </div>
        <p className="text-[11px] text-slate-400">
          {scenario?.description ??
            "Educational scenarios and model demonstrations — not trading recommendations. Applying one seeds S / K / T / r / q / σ (and relevant model defaults) across the tabs."}
        </p>
        {scenario?.educationalNotes && (
          <p className="text-[11px] text-slate-400">{scenario.educationalNotes}</p>
        )}
        {scenario?.warnings && scenario.warnings.length > 0 && (
          <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-[11px] font-medium text-amber-200">
            {scenario.warnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
          </div>
        )}
      </div>

      {/* Grouped tab navigation */}
      <div className="flex flex-wrap items-stretch gap-x-4 gap-y-2">
        {TAB_GROUPS.map((group) => (
          <div key={group.label} className="flex flex-col gap-1">
            <span className="px-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              {group.label}
            </span>
            <div className="inline-flex flex-wrap overflow-hidden rounded-lg border border-slate-300">
              {group.tabs.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className={
                    "px-3 py-1.5 text-xs font-medium transition-colors " +
                    (tab === id
                      ? "bg-blue-600 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50")
                  }
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div key={presetNonce}>
        <div hidden={tab !== "pricing"} aria-hidden={tab !== "pricing"}>
          <PricingTab scenario={scenario} />
        </div>
        <div hidden={tab !== "implied_vol"} aria-hidden={tab !== "implied_vol"}>
          <ImpliedVolTab scenario={scenario} />
        </div>
        <div hidden={tab !== "payoff"} aria-hidden={tab !== "payoff"}>
          <PayoffTab scenario={scenario} />
        </div>
        <div hidden={tab !== "tree"} aria-hidden={tab !== "tree"}>
          <TreePricingTab scenario={scenario} />
        </div>
        <div hidden={tab !== "monte_carlo"} aria-hidden={tab !== "monte_carlo"}>
          <MonteCarloTab scenario={scenario} />
        </div>
        <div hidden={tab !== "surface"} aria-hidden={tab !== "surface"}>
          <SurfaceTab scenario={scenario} />
        </div>
        <div hidden={tab !== "heston"} aria-hidden={tab !== "heston"}>
          <HestonTab scenario={scenario} />
        </div>
        <div hidden={tab !== "compare"} aria-hidden={tab !== "compare"}>
          <CompareTab scenario={scenario} />
        </div>
        <div hidden={tab !== "education"} aria-hidden={tab !== "education"}>
          <EducationTab />
        </div>
      </div>
    </div>
  );
}

// ── Pricing ──────────────────────────────────────────────────────────────────

function PricingTab({ scenario }: TabProps) {
  const b = scenario?.baseInputs;
  const [optionType, setOptionType] = useState<OptionType>(b?.option_type ?? "call");
  const [S, setS] = useState(pstr(b?.underlying_price, "100"));
  const [K, setK] = useState(pstr(b?.strike, "100"));
  const [T, setT] = useState(pstr(b?.time_to_expiry, "1"));
  const [r, setR] = useState(pstr(b?.risk_free_rate, "0.05"));
  const [sigma, setSigma] = useState(pstr(b?.volatility, "0.20"));
  const [q, setQ] = useState(pstr(b?.dividend_yield, "0"));
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

function ImpliedVolTab({ scenario }: TabProps) {
  const b = scenario?.baseInputs;
  const [optionType, setOptionType] = useState<OptionType>(b?.option_type ?? "call");
  const [mktPrice, setMktPrice] = useState("10.45");
  const [S, setS] = useState(pstr(b?.underlying_price, "100"));
  const [K, setK] = useState(pstr(b?.strike, "100"));
  const [T, setT] = useState(pstr(b?.time_to_expiry, "1"));
  const [r, setR] = useState(pstr(b?.risk_free_rate, "0.05"));
  const [q, setQ] = useState(pstr(b?.dividend_yield, "0"));
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

function PayoffTab({ scenario }: TabProps) {
  const colors = useAccentColors();
  const initialPresetId =
    (scenario?.payoffPresetId && PRESETS.some((p) => p.id === scenario.payoffPresetId)
      ? scenario.payoffPresetId
      : null) ?? "long_call";
  const [preset, setPreset] = useState(initialPresetId);
  const [legs, setLegs] = useState<UiLeg[]>(
    (PRESETS.find((p) => p.id === initialPresetId) ?? PRESETS[0]).legs(),
  );
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

function TreePricingTab({ scenario }: TabProps) {
  const colors = useAccentColors();
  const b = scenario?.baseInputs;
  const [optionType, setOptionType] = useState<OptionType>(b?.option_type ?? "call");
  const [exerciseStyle, setExerciseStyle] = useState<ExerciseStyle>(
    scenario?.treeInputs?.exercise_style ?? "european",
  );
  const [S, setS] = useState(pstr(b?.underlying_price, "100"));
  const [K, setK] = useState(pstr(b?.strike, "100"));
  const [T, setT] = useState(pstr(b?.time_to_expiry, "1"));
  const [r, setR] = useState(pstr(b?.risk_free_rate, "0.05"));
  const [sigma, setSigma] = useState(pstr(b?.volatility, "0.20"));
  const [q, setQ] = useState(pstr(b?.dividend_yield, "0"));
  const [steps, setSteps] = useState(pstr(scenario?.treeInputs?.steps, "100"));
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
        option chains, no calibrated surface input, no production risk engine.
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

function monteCarloPathColor(pathId: number): string {
  return seriesColor(pathId);
}

interface ConvRow {
  simulations: number;
  price: number;
  standard_error: number;
}

function MonteCarloTab({ scenario }: TabProps) {
  const b = scenario?.baseInputs;
  const mc = scenario?.monteCarloInputs;
  const [payoffType, setPayoffType] = useState<MonteCarloPayoffType>(
    mc?.payoff_type ?? "european_call",
  );
  const [S, setS] = useState(pstr(b?.underlying_price, "100"));
  const [K, setK] = useState(pstr(b?.strike, "100"));
  const [T, setT] = useState(pstr(b?.time_to_expiry, "1"));
  const [r, setR] = useState(pstr(b?.risk_free_rate, "0.05"));
  const [sigma, setSigma] = useState(pstr(b?.volatility, "0.20"));
  const [q, setQ] = useState(pstr(b?.dividend_yield, "0"));
  const [steps, setSteps] = useState(pstr(mc?.steps, "252"));
  const [simulations, setSimulations] = useState(pstr(mc?.simulations, "10000"));
  const [seed, setSeed] = useState(pstr(mc?.seed, "42"));
  const [antithetic, setAntithetic] = useState(false);
  const [barrier, setBarrier] = useState(pstr(mc?.barrier_price, "120"));
  const [result, setResult] = useState<MonteCarloResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [convRows, setConvRows] = useState<ConvRow[] | null>(null);
  const [convLoading, setConvLoading] = useState(false);

  const isBarrier = MC_PAYOFFS.find((p) => p.value === payoffType)?.barrier ?? false;
  const stepsNum = num(steps);
  const simsNum = num(simulations);
  const seedNum = num(seed);
  const stepsInt = Number.isInteger(stepsNum) ? stepsNum : NaN;
  const simsInt = Number.isInteger(simsNum) ? simsNum : NaN;
  const seedInt = Number.isInteger(seedNum) ? seedNum : NaN;
  const valid =
    num(S) > 0 &&
    num(K) > 0 &&
    num(T) > 0 &&
    num(sigma) > 0 &&
    finite(r) &&
    finite(q) &&
    Number.isInteger(stepsNum) &&
    stepsInt >= 1 &&
    stepsInt <= 2000 &&
    Number.isInteger(simsNum) &&
    simsInt >= 100 &&
    simsInt <= 200000 &&
    Number.isInteger(seedNum) &&
    seedInt >= 0 &&
    seedInt <= 4294967295 &&
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
    setError(null);
    setConvRows(null);
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
          seed must be a non-negative integer; barrier required for barrier payoffs.
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
                  <Tooltip
                    content={
                      <NeonTooltip
                        formatValue={(v: number) => v.toFixed(2)}
                        formatLabel={(l) => (typeof l === "number" ? `t=${l.toFixed(2)} yr` : "")}
                      />
                    }
                  />
                  {preview.map((p, idx) => {
                    const highlighted = idx < 2;
                    return (
                      <Line
                        key={p.path_id}
                        type="monotone"
                        dataKey={`p${p.path_id}`}
                        name={`Path ${p.path_id + 1}`}
                        stroke={monteCarloPathColor(p.path_id)}
                        strokeWidth={highlighted ? 2 : 1.15}
                        strokeOpacity={highlighted ? 0.88 : 0.46}
                        dot={false}
                        isAnimationActive={false}
                      />
                    );
                  })}
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
        stochastic volatility or calibrated surface input, no live option chains, no production
        exotic pricing.
      </p>
    </div>
  );
}

// ── Vol Surface ──────────────────────────────────────────────────────────────

// Per-expiry / per-path colours come from the centralized Options Lab palette
// (see lib/chartPalette.ts) so every chart in the lab is deterministic + distinct.
const SURFACE_PALETTE = OPTIONS_CHART_PALETTE;
const SMILE_RAW_COLOR = CHART_SMILE_RAW_COLOR; // raw IV points
const SMILE_SVI_COLOR = SMILE_FIT_COLOR; // SVI fitted curve (distinct from raw)
const TERM_COLOR = TERM_STRUCTURE_COLOR;
const HESTON_UNDERLYING_PALETTE = OPTIONS_CHART_PALETTE;
const HESTON_VOLATILITY_PALETTE = [
  "#fbbf24", // amber highlight, intentionally distinct from price chart
  "#22d3ee",
  "#f472b6",
  "#34d399",
  "#818cf8",
  "#fb923c",
  "#bef264",
  "#60a5fa",
];
function _heatTextColor(value: number | null, min: number, max: number): string {
  if (value == null || !Number.isFinite(value)) return "#64748b";
  const t = max > min ? Math.min(1, Math.max(0, (value - min) / (max - min))) : 0.5;
  return t >= 0.38 && t <= 0.82 ? "#0b1220" : "#f8fafc";
}

interface UiSurfaceRow {
  option_type: OptionType;
  strike: string;
  time_to_expiry: string;
  market_price: string;
}

const DEFAULT_MANUAL_ROWS: UiSurfaceRow[] = [
  { option_type: "put", strike: "90", time_to_expiry: "0.25", market_price: "1.20" },
  { option_type: "put", strike: "95", time_to_expiry: "0.25", market_price: "2.30" },
  { option_type: "call", strike: "100", time_to_expiry: "0.25", market_price: "4.60" },
  { option_type: "call", strike: "105", time_to_expiry: "0.25", market_price: "2.60" },
  { option_type: "call", strike: "110", time_to_expiry: "0.25", market_price: "1.30" },
];

function SurfaceHeatmap({ surface, spot }: { surface: SurfaceResponse["surface"]; spot: number }) {
  const { grid, summary } = surface;
  const min = summary.min_iv ?? 0;
  const max = summary.max_iv ?? 1;
  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th className="px-1 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-400">
              Exp \ M
            </th>
            {grid.moneyness_values.map((m) => (
              <th key={m} className="px-1 py-0.5 text-[10px] font-medium text-slate-400">
                {m.toFixed(2)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grid.surface_matrix.map((row, i) => (
            <tr key={grid.expiries[i]}>
              <td className="px-1 py-0.5 text-right text-[10px] font-medium text-slate-400">
                {grid.expiry_days[i].toFixed(0)}d
              </td>
              {row.map((cell, j) => (
                <td
                  key={j}
                  className="h-8 w-12 rounded text-center text-[9px] font-semibold"
                  style={{
                    backgroundColor: paletteHeatColor(cell, min, max),
                    color: _heatTextColor(cell, min, max),
                  }}
                  title={
                    `Expiry ${grid.expiry_days[i].toFixed(0)}d · moneyness ${grid.moneyness_values[j].toFixed(2)}` +
                    ` · approx strike ${(grid.moneyness_values[j] * spot).toFixed(2)}` +
                    (cell == null ? " · no IV" : ` · IV ${(cell * 100).toFixed(1)}%`)
                  }
                >
                  {cell == null ? "—" : (cell * 100).toFixed(0)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-[11px] text-slate-400">
        Cells show implied volatility (%) by expiry (rows) × moneyness K/S (columns); colour scales
        from low (blue) to high (red). Grey = no valid IV.
      </p>
    </div>
  );
}

function SurfaceTab({ scenario }: TabProps) {
  const b = scenario?.baseInputs;
  const sf = scenario?.surfaceInputs;
  const [source, setSource] = useState<"sample" | "manual">("sample");
  const [S, setS] = useState(pstr(b?.underlying_price, "100"));
  const [r, setR] = useState(pstr(b?.risk_free_rate, "0.05"));
  const [q, setQ] = useState(pstr(b?.dividend_yield, "0"));
  const [baseVol, setBaseVol] = useState(pstr(sf?.base_vol, "0.20"));
  const [skew, setSkew] = useState(pstr(sf?.skew, "0.15"));
  const [smile, setSmile] = useState(pstr(sf?.smile, "0.30"));
  const [term, setTerm] = useState(pstr(sf?.term, "0.02"));
  const [fitSvi, setFitSvi] = useState(true);
  const [rows, setRows] = useState<UiSurfaceRow[]>(DEFAULT_MANUAL_ROWS);
  const [result, setResult] = useState<SurfaceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expiryIdx, setExpiryIdx] = useState(0);

  const manualValid = rows.every(
    (l) => num(l.strike) > 0 && num(l.time_to_expiry) > 0 && num(l.market_price) > 0,
  );
  const sampleValid =
    num(baseVol) > 0 &&
    num(baseVol) <= 5 &&
    finite(skew) &&
    finite(smile) &&
    finite(term) &&
    Math.abs(num(skew)) <= 5 &&
    Math.abs(num(smile)) <= 5 &&
    Math.abs(num(term)) <= 5;
  const valid =
    num(S) > 0 &&
    finite(r) &&
    finite(q) &&
    (source === "sample" ? sampleValid : rows.length >= 1 && rows.length <= 1000 && manualValid);

  function setRow(i: number, patch: Partial<UiSurfaceRow>) {
    setRows((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }
  function addRow() {
    setRows((ls) =>
      ls.length >= 1000
        ? ls
        : [...ls, { option_type: "call", strike: "100", time_to_expiry: "0.25", market_price: "4.00" }],
    );
  }
  function removeRow(i: number) {
    setRows((ls) => (ls.length > 1 ? ls.filter((_, idx) => idx !== i) : ls));
  }

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let res: SurfaceResponse;
      if (source === "sample") {
        res = await buildSampleVolSurface({
          underlying_price: num(S),
          risk_free_rate: num(r),
          dividend_yield: num(q),
          base_vol: num(baseVol),
          skew: num(skew),
          smile: num(smile),
          term: num(term),
          fit_svi: fitSvi,
        });
      } else {
        const apiRows: SurfaceRowInput[] = rows.map((l) => ({
          option_type: l.option_type,
          strike: num(l.strike),
          time_to_expiry: num(l.time_to_expiry),
          market_price: num(l.market_price),
        }));
        res = await buildVolSurface({
          underlying_price: num(S),
          risk_free_rate: num(r),
          dividend_yield: num(q),
          rows: apiRows,
          fit_svi: fitSvi,
        });
      }
      setResult(res);
      setExpiryIdx(0);
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const surface = result?.surface;
  const smiles = surface?.smiles ?? [];
  const selected = smiles[Math.min(expiryIdx, smiles.length - 1)];
  const smileData =
    selected?.points.map((p) => ({
      moneyness: p.moneyness,
      iv: p.implied_volatility,
      svi: p.fitted_svi_iv,
    })) ?? [];
  const termData =
    surface?.term_structure.map((t) => ({ expiry_days: t.expiry_days, atm_iv: t.atm_iv })) ?? [];
  const failedRows = surface?.rows.filter((r) => r.implied_volatility == null) ?? [];

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Volatility Surface &amp; SVI</p>
      <p className="text-xs text-slate-500">
        Extracts implied volatility from a sample or manual option chain, then visualizes the
        smile, skew, ATM term structure, and a per-expiry SVI research fit. Surface quality depends
        on the option prices, strike/expiry coverage, dividends, rates, and solver stability.
        Educational research tool — no live chains, not an arbitrage-free calibration.
      </p>

      {/* Setup */}
      <div className="flex flex-wrap items-center gap-2">
        <span className={labelCls + " mb-0"}>Source</span>
        <div className="inline-flex overflow-hidden rounded-lg border border-slate-300">
          {(
            [
              ["sample", "Sample Chain"],
              ["manual", "Manual Rows"],
            ] as [typeof source, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                setSource(id);
                setResult(null);
              }}
              className={
                "px-3 py-1.5 text-xs font-medium transition-colors " +
                (source === id ? "bg-blue-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50")
              }
            >
              {label}
            </button>
          ))}
        </div>
        <label className="ml-2 flex items-center gap-2 text-xs text-slate-600">
          <input type="checkbox" checked={fitSvi} onChange={(e) => setFitSvi(e.target.checked)} />
          Fit SVI
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Underlying S"><input type="number" className={inputCls} value={S} onChange={(e) => setS(e.target.value)} /></Field>
        <Field label="Rate r"><input type="number" className={inputCls} value={r} step={0.01} onChange={(e) => setR(e.target.value)} /></Field>
        <Field label="Dividend q"><input type="number" className={inputCls} value={q} step={0.01} onChange={(e) => setQ(e.target.value)} /></Field>
        {source === "sample" && (
          <>
            <Field label="Base vol"><input type="number" className={inputCls} value={baseVol} step={0.01} onChange={(e) => setBaseVol(e.target.value)} /></Field>
            <Field label="Skew"><input type="number" className={inputCls} value={skew} step={0.01} onChange={(e) => setSkew(e.target.value)} /></Field>
            <Field label="Smile"><input type="number" className={inputCls} value={smile} step={0.05} onChange={(e) => setSmile(e.target.value)} /></Field>
            <Field label="Term slope"><input type="number" className={inputCls} value={term} step={0.01} onChange={(e) => setTerm(e.target.value)} /></Field>
          </>
        )}
      </div>

      {source === "manual" && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-400">
                <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Type</th>
                <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Strike</th>
                <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">T (yrs)</th>
                <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Market price</th>
                <th className="px-2 py-1"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((l, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="px-2 py-1">
                    <select className={inputCls} value={l.option_type} onChange={(e) => setRow(i, { option_type: e.target.value as OptionType })}>
                      <option value="call">call</option>
                      <option value="put">put</option>
                    </select>
                  </td>
                  <td className="px-2 py-1"><input type="number" className={inputCls + " w-20"} value={l.strike} onChange={(e) => setRow(i, { strike: e.target.value })} /></td>
                  <td className="px-2 py-1"><input type="number" className={inputCls + " w-20"} value={l.time_to_expiry} step={0.05} onChange={(e) => setRow(i, { time_to_expiry: e.target.value })} /></td>
                  <td className="px-2 py-1"><input type="number" className={inputCls + " w-24"} value={l.market_price} step={0.1} onChange={(e) => setRow(i, { market_price: e.target.value })} /></td>
                  <td className="px-2 py-1">
                    <button type="button" onClick={() => removeRow(i)} className="text-slate-400 hover:text-red-600" title="Remove row">✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" onClick={addRow} className="mt-1 rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:border-blue-400">
            + Add row
          </button>
        </div>
      )}

      <button
        type="button"
        onClick={run}
        disabled={!valid || loading}
        className={
          "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
          (valid && !loading ? "bg-blue-600 text-white hover:bg-blue-700" : "cursor-not-allowed bg-slate-100 text-slate-400")
        }
      >
        {loading ? "Building…" : source === "sample" ? "Generate Sample Surface" : "Build Surface"}
      </button>
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}
      {!valid && (
        <p className="text-[11px] text-slate-400">
          Use positive S and finite rates. Sample surfaces require positive base vol and finite
          skew/smile/term inputs within ±5; manual rows require positive strike, expiry, and price
          with at most 1,000 rows.
        </p>
      )}

      {surface && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Valid IV rows" value={String(surface.summary.valid_row_count)} />
            <Stat label="Failed rows" value={String(surface.summary.failed_row_count)} />
            <Stat label="Min IV" value={surface.summary.min_iv != null ? `${(surface.summary.min_iv * 100).toFixed(1)}%` : "—"} />
            <Stat label="Max IV" value={surface.summary.max_iv != null ? `${(surface.summary.max_iv * 100).toFixed(1)}%` : "—"} />
            <Stat label="ATM IV" value={surface.summary.atm_iv_nearest != null ? `${(surface.summary.atm_iv_nearest * 100).toFixed(1)}%` : "—"} />
            <Stat label="Expiries" value={String(surface.summary.expiries_count)} />
            <Stat label="Strikes" value={String(surface.summary.strikes_count)} />
            <Stat label="SVI fitted" value={`${surface.summary.svi_fitted_count} / ${surface.svi_fits.length}`} />
          </div>

          {/* Smile */}
          {smiles.length > 0 && (
            <div>
              <p className="section-title mb-1">Smile by expiry</p>
              <div className="mb-2 flex flex-wrap gap-1.5">
                {smiles.map((sm, i) => (
                  <button
                    key={sm.expiry_days}
                    type="button"
                    onClick={() => setExpiryIdx(i)}
                    className={
                      "rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors " +
                      (i === expiryIdx ? "text-white" : "bg-white text-slate-600 hover:border-blue-400")
                    }
                    style={
                      i === expiryIdx
                        ? { backgroundColor: SURFACE_PALETTE[i % SURFACE_PALETTE.length], borderColor: SURFACE_PALETTE[i % SURFACE_PALETTE.length] }
                        : { borderColor: SURFACE_PALETTE[i % SURFACE_PALETTE.length] }
                    }
                  >
                    {sm.expiry_days.toFixed(0)}d
                  </button>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <ComposedChart data={smileData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey="moneyness"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    axisLine={{ stroke: CHART_AXIS_LINE }}
                    tickLine={false}
                    tickFormatter={(v: number) => v.toFixed(2)}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    axisLine={false}
                    tickLine={false}
                    width={52}
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                  />
                  <ReferenceLine x={1.0} stroke={CHART_REF_LINE} strokeDasharray="5 4" />
                  <Tooltip
                    content={
                      <NeonTooltip
                        formatValue={(v: number) => `${(v * 100).toFixed(2)}%`}
                        formatLabel={(l) => (typeof l === "number" ? `Moneyness ${l.toFixed(2)}` : "")}
                      />
                    }
                  />
                  <Scatter dataKey="iv" name="Implied vol" fill={SMILE_RAW_COLOR} isAnimationActive={false} />
                  <Line type="monotone" dataKey="svi" name="SVI fit" stroke={SMILE_SVI_COLOR} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="text-[11px] text-slate-400">
                <span style={{ color: SMILE_RAW_COLOR }}>● Raw IV</span>{"   "}
                <span style={{ color: SMILE_SVI_COLOR }}>— SVI fit (research approximation)</span>. Dashed line = ATM (moneyness 1.0).
                {selected && surface.svi_fits[expiryIdx]?.rmse != null && (
                  <> SVI RMSE: {(surface.svi_fits[expiryIdx].rmse! * 100).toFixed(2)} vol pts.</>
                )}
              </p>
            </div>
          )}

          {/* Term structure */}
          {termData.length > 0 && (
            <div>
              <p className="section-title mb-1">ATM term structure</p>
              <ResponsiveContainer width="100%" height={200}>
                <ComposedChart data={termData} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis
                    dataKey="expiry_days"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    axisLine={{ stroke: CHART_AXIS_LINE }}
                    tickLine={false}
                    tickFormatter={(v: number) => `${v.toFixed(0)}d`}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    axisLine={false}
                    tickLine={false}
                    width={52}
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip
                    content={
                      <NeonTooltip
                        formatValue={(v: number) => `${(v * 100).toFixed(2)}%`}
                        formatLabel={(l) => (typeof l === "number" ? `${l.toFixed(0)} days` : "")}
                      />
                    }
                  />
                  <Line type="monotone" dataKey="atm_iv" name="ATM IV" stroke={TERM_COLOR} strokeWidth={2} dot={{ r: 3 }} connectNulls isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Heatmap */}
          <div>
            <p className="section-title mb-1">Surface heatmap</p>
            <SurfaceHeatmap surface={surface} spot={num(S)} />
          </div>

          {/* Diagnostics */}
          {(failedRows.length > 0 || surface.warnings.length > 0) && (
            <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
              {surface.warnings.map((w, i) => (
                <p key={`w${i}`}>{w}</p>
              ))}
              {failedRows.slice(0, 8).map((r, i) => (
                <p key={`f${i}`}>
                  {r.option_type} K={r.strike} ({r.expiry_days.toFixed(0)}d): {r.warning}
                </p>
              ))}
              {failedRows.length > 8 && <p>…and {failedRows.length - 8} more failed rows.</p>}
            </div>
          )}
        </>
      )}

      <p className="text-[11px] text-slate-400">
        SVI is a least-squares research fit (enforces b ≥ 0, |ρ| &lt; 1, σ &gt; 0) — it is not a
        guaranteed arbitrage-free surface. No live option chains, no stochastic volatility, no
        production calibration.
      </p>
    </div>
  );
}

// ── Heston ───────────────────────────────────────────────────────────────────

function HestonPathChart({
  times,
  paths,
  field,
  yLabel,
  yPercent,
}: {
  times: number[];
  paths: HestonResponse["path_preview"];
  field: "underlying" | "volatility";
  yLabel: string;
  yPercent?: boolean;
}) {
  const data = times.map((t, i) => {
    const row: Record<string, number> = { time: t };
    for (const p of paths) row[`p${p.path_id}`] = p[field][i];
    return row;
  });
  const palette = field === "volatility" ? HESTON_VOLATILITY_PALETTE : HESTON_UNDERLYING_PALETTE;
  const tooltipLabel = `${yLabel} path`;
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
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
        <YAxis
          tick={{ fontSize: 11, fill: CHART_AXIS }}
          axisLine={false}
          tickLine={false}
          width={52}
          tickFormatter={(v: number) => (yPercent ? `${(v * 100).toFixed(0)}%` : v.toFixed(0))}
        />
        <Tooltip
          content={
            <NeonTooltip
              formatValue={(v: number) => (yPercent ? `${(v * 100).toFixed(1)}%` : v.toFixed(2))}
              formatLabel={(l) => (typeof l === "number" ? `t = ${l.toFixed(2)} yr` : "")}
            />
          }
        />
        {paths.map((p) => (
          <Line
            key={p.path_id}
            type="monotone"
            dataKey={`p${p.path_id}`}
            name={`${tooltipLabel} ${p.path_id + 1}`}
            stroke={palette[p.path_id % palette.length]}
            strokeWidth={p.path_id === 0 ? 2.5 : 1}
            strokeOpacity={p.path_id === 0 ? 1 : 0.5}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function HestonTab({ scenario }: TabProps) {
  const b = scenario?.baseInputs;
  const h = scenario?.hestonInputs;
  const [optionType, setOptionType] = useState<OptionType>(b?.option_type ?? "call");
  const [S, setS] = useState(pstr(b?.underlying_price, "100"));
  const [K, setK] = useState(pstr(b?.strike, "100"));
  const [T, setT] = useState(pstr(b?.time_to_expiry, "1"));
  const [r, setR] = useState(pstr(b?.risk_free_rate, "0.05"));
  const [q, setQ] = useState(pstr(b?.dividend_yield, "0"));
  const [initVol, setInitVol] = useState(pstr(h?.initial_volatility, "0.20"));
  const [lrVol, setLrVol] = useState(pstr(h?.long_run_volatility, "0.20"));
  const [kappa, setKappa] = useState(pstr(h?.kappa, "2.0"));
  const [volOfVol, setVolOfVol] = useState(pstr(h?.vol_of_vol, "0.5"));
  const [rho, setRho] = useState(pstr(h?.rho, "-0.7"));
  const [steps, setSteps] = useState(pstr(h?.steps, "252"));
  const [simulations, setSimulations] = useState(pstr(h?.simulations, "10000"));
  const [seed, setSeed] = useState(pstr(h?.seed, "42"));
  const [result, setResult] = useState<HestonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const stepsNum = num(steps);
  const simsNum = num(simulations);
  const seedNum = num(seed);
  const stepsInt = Number.isInteger(stepsNum) ? stepsNum : NaN;
  const simsInt = Number.isInteger(simsNum) ? simsNum : NaN;
  const seedInt = Number.isInteger(seedNum) ? seedNum : NaN;
  const valid =
    num(S) > 0 &&
    num(K) > 0 &&
    num(T) > 0 &&
    finite(r) &&
    num(q) >= 0 &&
    num(initVol) > 0 &&
    num(lrVol) > 0 &&
    num(kappa) > 0 &&
    num(volOfVol) >= 0 &&
    num(rho) >= -0.999 &&
    num(rho) <= 0.999 &&
    Number.isInteger(stepsInt) &&
    stepsInt >= 1 &&
    stepsInt <= 2000 &&
    Number.isInteger(simsInt) &&
    simsInt >= 100 &&
    simsInt <= 200000 &&
    Number.isInteger(seedInt) &&
    seedInt >= 0 &&
    seedInt <= 4294967295;

  async function run() {
    if (!valid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await priceHeston({
          option_type: optionType,
          underlying_price: num(S),
          strike: num(K),
          time_to_expiry: num(T),
          risk_free_rate: num(r),
          dividend_yield: num(q),
          // UI takes volatility; Heston uses variance internally.
          initial_variance: num(initVol) ** 2,
          long_run_variance: num(lrVol) ** 2,
          kappa: num(kappa),
          vol_of_vol: num(volOfVol),
          rho: num(rho),
          steps: stepsInt,
          simulations: simsInt,
          seed: seedInt,
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  const bs = result?.black_scholes_reference;

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Heston Stochastic Volatility</p>
      <p className="text-xs text-slate-500">
        Heston lets volatility itself vary randomly and be correlated with price moves, capturing
        skew that constant-volatility Black–Scholes cannot. This prices European options with a
        full-truncation Euler Monte Carlo simulation. Results depend on the parameters,
        discretization, simulation count, seed, and variance handling — Euler is biased and the
        model is not calibrated to any market surface.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Option type">
          <OptionTypeToggle value={optionType} onChange={setOptionType} />
        </Field>
        <Field label="Underlying S"><input type="number" className={inputCls} value={S} onChange={(e) => setS(e.target.value)} /></Field>
        <Field label="Strike K"><input type="number" className={inputCls} value={K} onChange={(e) => setK(e.target.value)} /></Field>
        <Field label="Expiry T (years)"><input type="number" className={inputCls} value={T} onChange={(e) => setT(e.target.value)} /></Field>
        <Field label="Rate r"><input type="number" className={inputCls} value={r} step={0.01} onChange={(e) => setR(e.target.value)} /></Field>
        <Field label="Dividend q"><input type="number" className={inputCls} value={q} step={0.01} onChange={(e) => setQ(e.target.value)} /></Field>
        <Field label="Initial vol σ₀"><input type="number" className={inputCls} value={initVol} step={0.01} onChange={(e) => setInitVol(e.target.value)} /></Field>
        <Field label="Long-run vol √θ"><input type="number" className={inputCls} value={lrVol} step={0.01} onChange={(e) => setLrVol(e.target.value)} /></Field>
        <Field label="κ mean-reversion"><input type="number" className={inputCls} value={kappa} step={0.1} onChange={(e) => setKappa(e.target.value)} /></Field>
        <Field label="Vol of vol ξ"><input type="number" className={inputCls} value={volOfVol} step={0.05} onChange={(e) => setVolOfVol(e.target.value)} /></Field>
        <Field label="ρ correlation"><input type="number" className={inputCls} value={rho} step={0.05} onChange={(e) => setRho(e.target.value)} /></Field>
        <Field label="Steps (1–2000)"><input type="number" className={inputCls} value={steps} min={1} max={2000} step={1} onChange={(e) => setSteps(e.target.value)} /></Field>
        <Field label="Simulations"><input type="number" className={inputCls} value={simulations} min={100} max={200000} step={1000} onChange={(e) => setSimulations(e.target.value)} /></Field>
        <Field label="Seed"><input type="number" className={inputCls} value={seed} min={0} step={1} onChange={(e) => setSeed(e.target.value)} /></Field>
      </div>

      <button
        type="button"
        onClick={run}
        disabled={!valid || loading}
        className={
          "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
          (valid && !loading ? "bg-blue-600 text-white hover:bg-blue-700" : "cursor-not-allowed bg-slate-800 text-slate-500")
        }
      >
        {loading ? "Simulating…" : "Run Heston"}
      </button>
      {!valid && (
        <p className="text-[11px] text-slate-400">
          σ₀, √θ, κ positive; ξ ≥ 0; ρ between −0.999 and 0.999; steps 1–2000 and simulations
          100–200,000 whole numbers.
        </p>
      )}
      {error && <p className="text-xs text-red-400">⚠ {error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Heston MC price" value={result.price.toFixed(4)} />
            <Stat label="Standard error" value={result.standard_error.toFixed(4)} />
            <Stat
              label="95% CI"
              value={`${result.confidence_interval_95.lower.toFixed(3)} – ${result.confidence_interval_95.upper.toFixed(3)}`}
            />
            <Stat label="Feller condition" value={result.feller.satisfied ? "Satisfied" : "Violated"} />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label={`BS ref (σ=${bs ? bs.volatility_used.toFixed(2) : "—"})`} value={bs ? bs.price.toFixed(4) : "—"} />
            <Stat label="Diff vs BS" value={bs ? bs.difference.toFixed(4) : "—"} />
            <Stat label="Mean terminal price" value={result.summary.mean_terminal_price.toFixed(2)} />
            <Stat label="Mean terminal vol" value={`${(result.summary.mean_terminal_volatility * 100).toFixed(1)}%`} />
          </div>

          {result.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-200">
              {result.warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          )}

          {result.path_preview.length > 0 && (
            <>
              <div>
                <p className="section-title mb-1">Underlying paths</p>
                <HestonPathChart times={result.preview_times} paths={result.path_preview} field="underlying" yLabel="price" />
              </div>
              <div>
                <p className="section-title mb-1">Volatility paths (√variance)</p>
                <HestonPathChart times={result.preview_times} paths={result.path_preview} field="volatility" yLabel="vol" yPercent />
                <p className="text-[11px] text-slate-400">
                  Variance mean-reverts toward √θ = {bs ? bs.volatility_used.toFixed(2) : ""}; the
                  bold path is the first simulation. Observed variance ranged{" "}
                  {(result.summary.min_variance_observed * 100).toFixed(1)}% –{" "}
                  {(result.summary.max_variance_observed * 100).toFixed(1)}% (as variance).
                </p>
              </div>
            </>
          )}

          <p className="glass px-3 py-2 text-[11px]" style={{ color: "var(--text-mut)" }}>
            The Black–Scholes reference assumes constant volatility and is{" "}
            <span className="font-medium">not</span> a benchmark for correctness when volatility is
            stochastic — it is shown only for orientation.
          </p>
        </>
      )}

      <div className="glass px-3 py-2 text-[11px]" style={{ color: "var(--text-mut)" }}>
        <span className="font-medium" style={{ color: "var(--text-hi)" }}>How to read the parameters:</span> κ is the
        speed variance reverts to its long-run level; θ (here √θ) is that long-run variance/vol; ξ
        (vol of vol) is how randomly volatility itself moves; ρ is the price/variance correlation
        (negative ρ produces the equity leverage effect and skew); v₀ (σ₀) is the starting
        variance/vol. Calibration to a market IV surface is planned, not implemented.
      </div>
    </div>
  );
}

// ── Model Comparison ─────────────────────────────────────────────────────────

interface CompareRow {
  model: string;
  price: number | null;
  diff: number | null;
  settings: string;
  notes: string;
}

function CompareTab({ scenario }: TabProps) {
  const b = scenario?.baseInputs;
  const h = scenario?.hestonInputs;
  const [optionType, setOptionType] = useState<OptionType>(b?.option_type ?? "call");
  const [S, setS] = useState(pstr(b?.underlying_price, "100"));
  const [K, setK] = useState(pstr(b?.strike, "100"));
  const [T, setT] = useState(pstr(b?.time_to_expiry, "1"));
  const [r, setR] = useState(pstr(b?.risk_free_rate, "0.05"));
  const [sigma, setSigma] = useState(pstr(b?.volatility, "0.20"));
  const [q, setQ] = useState(pstr(b?.dividend_yield, "0"));
  const [rows, setRows] = useState<CompareRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const scenarioPayoffType = scenario?.monteCarloInputs?.payoff_type;
  const isPathDependentScenario =
    scenarioPayoffType != null && !scenarioPayoffType.startsWith("european_");

  const valid =
    num(S) > 0 && num(K) > 0 && num(T) > 0 && num(sigma) > 0 && finite(r) && finite(q);

  async function run() {
    if (!valid || loading) return; // guard against duplicate clicks
    setLoading(true);
    setError(null);
    setRows(null);
    const base = {
      underlying_price: num(S),
      strike: num(K),
      time_to_expiry: num(T),
      risk_free_rate: num(r),
      dividend_yield: num(q),
    };
    try {
      const bs = await priceBlackScholes({ option_type: optionType, ...base, volatility: num(sigma) });
      const bsPrice = bs.price;
      const out: CompareRow[] = [
        {
          model: "Black–Scholes (European)",
          price: bsPrice,
          diff: 0,
          settings: "closed form",
          notes: "Constant-vol European reference",
        },
      ];

      const treeSteps = scenario?.treeInputs?.steps ?? 200;
      const treeEur = await priceBinomialTree({
        option_type: optionType,
        exercise_style: "european",
        ...base,
        volatility: num(sigma),
        steps: treeSteps,
        include_lattice: false,
      });
      out.push({
        model: `Binomial CRR · European`,
        price: treeEur.price,
        diff: treeEur.price - bsPrice,
        settings: `${treeSteps} steps`,
        notes: "Lattice; converges to BS",
      });

      const treeAmer = await priceBinomialTree({
        option_type: optionType,
        exercise_style: "american",
        ...base,
        volatility: num(sigma),
        steps: treeSteps,
        include_lattice: false,
      });
      out.push({
        model: "Binomial CRR · American",
        price: treeAmer.price,
        diff: treeAmer.price - bsPrice,
        settings: `${treeSteps} steps`,
        notes:
          treeAmer.early_exercise.detected
            ? "Early exercise optimal (≥ European)"
            : "No early exercise (= European)",
      });

      const mcSteps = scenario?.monteCarloInputs?.steps ?? 252;
      const mcSims = scenario?.monteCarloInputs?.simulations ?? 20000;
      const mcSeed = scenario?.monteCarloInputs?.seed ?? 42;
      const mc = await priceMonteCarlo({
        payoff_type: optionType === "call" ? "european_call" : "european_put",
        ...base,
        volatility: num(sigma),
        steps: mcSteps,
        simulations: mcSims,
        seed: mcSeed,
      });
      out.push({
        model: "Monte Carlo GBM",
        price: mc.price,
        diff: mc.price - bsPrice,
        settings: `${mcSims.toLocaleString()} sims · ${mcSteps} steps · seed ${mcSeed}`,
        notes: `±${mc.standard_error.toFixed(3)} SE — sampling error`,
      });

      const hInit = h?.initial_volatility ?? num(sigma);
      const hLong = h?.long_run_volatility ?? num(sigma);
      const hestonSteps = h?.steps ?? 252;
      const hestonSims = h?.simulations ?? 12000;
      const hestonSeed = h?.seed ?? 42;
      const heston = await priceHeston({
        option_type: optionType,
        ...base,
        initial_variance: hInit * hInit,
        long_run_variance: hLong * hLong,
        kappa: h?.kappa ?? 2.0,
        vol_of_vol: h?.vol_of_vol ?? 0.5,
        rho: h?.rho ?? -0.7,
        steps: hestonSteps,
        simulations: hestonSims,
        seed: hestonSeed,
      });
      out.push({
        model: "Heston MC (stochastic vol)",
        price: heston.price,
        diff: heston.price - bsPrice,
        settings: `${hestonSims.toLocaleString()} sims · ${hestonSteps} steps · seed ${hestonSeed}`,
        notes: `ξ=${(h?.vol_of_vol ?? 0.5)}, ρ=${(h?.rho ?? -0.7)}; ±${heston.standard_error.toFixed(3)} SE`,
      });

      setRows(out);
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card space-y-4 p-5">
      <p className="section-title">Model Comparison</p>
      <p className="text-xs text-slate-500">
        Prices the same European option across every model on demand. Model outputs differ because
        their <span className="font-medium">assumptions differ</span> — none is automatically
        “correct”. Monte Carlo and Heston are simulations and carry sampling error. Runs only when
        you click; it does not recompute on every keystroke.
      </p>
      {isPathDependentScenario && (
        <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-200">
          The active scenario is path-dependent ({scenarioPayoffType?.replace(/_/g, " ")}), while
          Model Compare prices the matching European vanilla {optionType}. Use the Monte Carlo tab
          for the path-dependent payoff itself.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Option type"><OptionTypeToggle value={optionType} onChange={setOptionType} /></Field>
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
        {loading ? "Running models…" : "Run Comparison"}
      </button>
      {error && <p className="text-xs text-red-600">⚠ {error}</p>}

      {rows && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-400">
                <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Model</th>
                <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Price</th>
                <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Δ vs BS</th>
                <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Settings</th>
                <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.model} className="border-t border-slate-100">
                  <td className="px-2 py-1 font-medium text-slate-700">{row.model}</td>
                  <td className="px-2 py-1 text-right mono">{row.price == null ? "—" : row.price.toFixed(4)}</td>
                  <td className="px-2 py-1 text-right mono">{row.diff == null ? "—" : (row.diff >= 0 ? "+" : "") + row.diff.toFixed(4)}</td>
                  <td className="px-2 py-1 text-slate-500">{row.settings}</td>
                  <td className="px-2 py-1 text-slate-500">{row.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[11px] text-slate-400">
        Model outputs differ because assumptions differ. Differences vs Black–Scholes are expected,
        not errors. Simulation models (Monte Carlo, Heston) are reproducible by seed and carry the
        reported standard error.
      </p>
    </div>
  );
}

// ── Education ────────────────────────────────────────────────────────────────

function EducationTab() {
  return (
    <div className="card space-y-3 p-5 text-sm text-slate-600">
      <p className="section-title">How to read the Options Lab</p>
      <FormulaReference title="Key formulas" groups={OPTIONS_FORMULA_GROUPS} />
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
