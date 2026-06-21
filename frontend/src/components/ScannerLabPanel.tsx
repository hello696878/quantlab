"use client";

import { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Bar,
  Line,
  ReferenceLine,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { BacktestApiError, runScanner } from "@/lib/api";
import type { ScannerResponse, ScannerStrategy, RebalanceFrequency } from "@/lib/types";
import MetricCard from "@/components/MetricCard";
import NeonTooltip from "@/components/charts/NeonTooltip";
import { CHART_AXIS, CHART_AXIS_LINE, CHART_GRID, CHART_REF_LINE, DANGER } from "@/components/charts/chartTheme";
import { seriesColor } from "@/lib/chartPalette";

const inputCls = "ql-input px-2.5 py-1.5";
const labelCls = "mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400";

const EQUITY_COLOR = seriesColor(0); // cyan
const DD_COLOR = DANGER;
const LONG_COLOR = "var(--emerald)";
const SHORT_COLOR = DANGER;
const TURNOVER_COLOR = seriesColor(4); // amber
const NET_COLOR = seriesColor(5); // emerald-ish

const STRATEGIES: [ScannerStrategy, string][] = [
  ["cross_sectional_reversal", "Cross-sectional reversal"],
  ["cross_sectional_momentum", "Cross-sectional momentum"],
];
const FREQUENCIES: [RebalanceFrequency, string][] = [
  ["daily", "Daily"],
  ["weekly", "Weekly"],
  ["monthly", "Monthly"],
];

const CAVEAT =
  "Cross-sectional results depend on universe construction, survivorship bias, point-in-time data, " +
  "liquidity, transaction costs, rebalance timing, and lookahead-safe signal timing. Synthetic " +
  "sample universe for workflow demonstration — not live market data, not investment advice.";

function num(s: string): number {
  return s.trim() === "" ? NaN : Number(s);
}
function pct(v: number | null | undefined, d = 2): string {
  return v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`;
}
function fmt(v: number | null | undefined, d = 2): string {
  return v == null || !Number.isFinite(v) ? "—" : v.toFixed(d);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className={labelCls}>{label}</span>
      {children}
    </label>
  );
}

function sideColor(side: string): string {
  return side === "long" ? "var(--emerald)" : side === "short" ? DANGER : "var(--text-mut)";
}

interface UiInputs {
  strategy: ScannerStrategy;
  nAssets: string;
  startDate: string;
  endDate: string;
  lookback: string;
  longQuantile: string;
  shortQuantile: string;
  rebalance: RebalanceFrequency;
  grossExposure: string;
  costBps: string;
  minLiquidity: string;
  seed: string;
}

const DEFAULTS: UiInputs = {
  strategy: "cross_sectional_reversal",
  nAssets: "50",
  startDate: "2022-01-01",
  endDate: "2024-12-31",
  lookback: "5",
  longQuantile: "0.2",
  shortQuantile: "0.2",
  rebalance: "daily",
  grossExposure: "1.0",
  costBps: "5",
  minLiquidity: "0",
  seed: "42",
};

export default function ScannerLabPanel({ initialStrategy }: { initialStrategy?: ScannerStrategy } = {}) {
  const [inp, setInp] = useState<UiInputs>(
    initialStrategy ? { ...DEFAULTS, strategy: initialStrategy } : DEFAULTS,
  );
  const [result, setResult] = useState<ScannerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function set<K extends keyof UiInputs>(key: K, value: UiInputs[K]) {
    setInp((s) => ({ ...s, [key]: value }));
  }

  const lq = num(inp.longQuantile);
  const sq = num(inp.shortQuantile);
  const seedValue = num(inp.seed);
  const seedValid = inp.seed.trim() === "" || (Number.isInteger(seedValue) && seedValue >= 0);
  const valid =
    Number.isInteger(num(inp.nAssets)) && num(inp.nAssets) >= 5 && num(inp.nAssets) <= 500 &&
    Number.isInteger(num(inp.lookback)) && num(inp.lookback) >= 1 && num(inp.lookback) <= 252 &&
    lq > 0 && lq < 0.5 && sq > 0 && sq < 0.5 &&
    num(inp.grossExposure) > 0 && num(inp.grossExposure) <= 10 &&
    num(inp.costBps) >= 0 && num(inp.costBps) <= 1000 &&
    num(inp.minLiquidity) >= 0 && num(inp.minLiquidity) <= 1 &&
    seedValid &&
    inp.startDate < inp.endDate;

  async function run(strategyOverride?: ScannerStrategy) {
    if (loading) return;
    const strategy = strategyOverride ?? inp.strategy;
    if (strategyOverride) set("strategy", strategyOverride);
    if (!valid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await runScanner({
          strategy,
          universe_source: "synthetic",
          n_assets: num(inp.nAssets),
          start_date: inp.startDate,
          end_date: inp.endDate,
          lookback_days: num(inp.lookback),
          long_quantile: lq,
          short_quantile: sq,
          rebalance_frequency: inp.rebalance,
          gross_exposure: num(inp.grossExposure),
          cost_bps: num(inp.costBps),
          min_liquidity: num(inp.minLiquidity),
          seed: inp.seed.trim() === "" ? null : num(inp.seed),
        }),
      );
    } catch (e) {
      setError(e instanceof BacktestApiError || e instanceof Error ? e.message : "Failed.");
    } finally {
      setLoading(false);
    }
  }

  // Backend already returns a capped top/middle/bottom preview so long, neutral,
  // and short examples remain visible even for large universes.
  const ranking = result?.latest_ranking ?? [];

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <p className="text-sm text-slate-300">
          The Cross-Sectional Scanner is a <span className="font-medium">second engine</span>: it
          ranks a whole universe of assets every rebalance date, forms dollar-neutral long/short
          baskets, and runs a portfolio-level, lookahead-safe backtest. (The single-asset Backtest
          Studio is unchanged.)
        </p>
        <p className="mt-2 text-[11px] text-slate-400">{CAVEAT}</p>
      </div>

      {/* Setup */}
      <div className="card space-y-4 p-5">
        <p className="section-title">Setup</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <Field label="Strategy">
            <select className={inputCls} value={inp.strategy} onChange={(e) => set("strategy", e.target.value as ScannerStrategy)}>
              {STRATEGIES.map(([id, label]) => (<option key={id} value={id}>{label}</option>))}
            </select>
          </Field>
          <Field label="Universe size (assets)"><input type="number" className={inputCls} value={inp.nAssets} step={10} onChange={(e) => set("nAssets", e.target.value)} /></Field>
          <Field label="Start date"><input type="date" className={inputCls} value={inp.startDate} onChange={(e) => set("startDate", e.target.value)} /></Field>
          <Field label="End date"><input type="date" className={inputCls} value={inp.endDate} onChange={(e) => set("endDate", e.target.value)} /></Field>
          <Field label="Lookback (days)"><input type="number" className={inputCls} value={inp.lookback} step={1} onChange={(e) => set("lookback", e.target.value)} /></Field>
          <Field label="Long quantile"><input type="number" className={inputCls} value={inp.longQuantile} step={0.05} onChange={(e) => set("longQuantile", e.target.value)} /></Field>
          <Field label="Short quantile"><input type="number" className={inputCls} value={inp.shortQuantile} step={0.05} onChange={(e) => set("shortQuantile", e.target.value)} /></Field>
          <Field label="Rebalance">
            <select className={inputCls} value={inp.rebalance} onChange={(e) => set("rebalance", e.target.value as RebalanceFrequency)}>
              {FREQUENCIES.map(([id, label]) => (<option key={id} value={id}>{label}</option>))}
            </select>
          </Field>
          <Field label="Gross exposure"><input type="number" className={inputCls} value={inp.grossExposure} step={0.5} onChange={(e) => set("grossExposure", e.target.value)} /></Field>
          <Field label="Cost (bps)"><input type="number" className={inputCls} value={inp.costBps} step={1} onChange={(e) => set("costBps", e.target.value)} /></Field>
          <Field label="Min liquidity (0–1)"><input type="number" className={inputCls} value={inp.minLiquidity} step={0.1} onChange={(e) => set("minLiquidity", e.target.value)} /></Field>
          <Field label="Seed"><input type="number" className={inputCls} value={inp.seed} step={1} onChange={(e) => set("seed", e.target.value)} /></Field>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => run()}
            disabled={!valid || loading}
            className={
              "rounded-lg px-4 py-2 text-sm font-semibold transition-colors " +
              (valid && !loading
                ? "bg-[var(--accent)] text-[var(--on-accent)] shadow-[var(--accent-glow)] hover:brightness-110"
                : "cursor-not-allowed border border-[var(--line)] bg-[var(--glass)] text-slate-500")
            }
          >
            {loading ? "Running scanner…" : "Run Scanner"}
          </button>
          <button type="button" onClick={() => run("cross_sectional_reversal")} disabled={loading} className="rounded-lg border border-[var(--line-strong)] px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:border-[var(--accent-border)]">
            Reversal demo
          </button>
          <button type="button" onClick={() => run("cross_sectional_momentum")} disabled={loading} className="rounded-lg border border-[var(--line-strong)] px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:border-[var(--accent-border)]">
            Momentum demo
          </button>
        </div>
        {!valid && (
          <p className="text-[11px] text-slate-400">
            Universe 5–500 assets, lookback 1–252, quantiles in (0, 0.5), gross 0–10,
            cost 0–1000 bps, liquidity 0–1, optional seed ≥ 0, start before end.
          </p>
        )}
        {error && <p className="text-xs text-red-600">⚠ {error}</p>}
      </div>

      {result && (
        <>
          {/* Metric cards */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            <MetricCard label="Total return" value={pct(result.summary.total_return)} tone={result.summary.total_return >= 0 ? "positive" : "danger"} />
            <MetricCard label="Annualized return" value={pct(result.summary.annualized_return)} tone={result.summary.annualized_return >= 0 ? "positive" : "danger"} />
            <MetricCard label="Sharpe" value={fmt(result.summary.sharpe, 2)} tone="accent" />
            <MetricCard label="Max drawdown" value={pct(result.summary.max_drawdown)} tone="warn" />
            <MetricCard label="Avg turnover" value={fmt(result.summary.average_turnover, 3)} />
            <MetricCard label="Avg gross exposure" value={fmt(result.summary.average_gross_exposure, 2)} />
            <MetricCard label="Avg net exposure" value={fmt(result.summary.average_net_exposure, 3)} />
          </div>

          {/* Equity curve */}
          <div className="card space-y-1 p-5">
            <p className="section-title mb-1">Equity curve (net of costs)</p>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={result.equity_curve} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} minTickGap={48} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => v.toFixed(2)} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(4)} />} />
                <ReferenceLine y={1} stroke={CHART_REF_LINE} strokeDasharray="2 2" />
                <Line type="monotone" dataKey="equity" name="Equity" stroke={EQUITY_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Drawdown */}
          <div className="card space-y-1 p-5">
            <p className="section-title mb-1">Drawdown</p>
            <ResponsiveContainer width="100%" height={160}>
              <ComposedChart data={result.equity_curve} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} minTickGap={48} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => `${(v * 100).toFixed(2)}%`} />} />
                <Area type="monotone" dataKey="drawdown" name="Drawdown" stroke={DD_COLOR} fill={DD_COLOR} fillOpacity={0.18} strokeWidth={1.5} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Exposure */}
          <div className="card space-y-1 p-5">
            <p className="section-title mb-1">Long / short exposure</p>
            <ResponsiveContainer width="100%" height={180}>
              <ComposedChart data={result.exposures} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} minTickGap={48} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => v.toFixed(1)} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(3)} />} />
                <ReferenceLine y={0} stroke={CHART_REF_LINE} />
                <Line type="monotone" dataKey="long" name="Long" stroke={LONG_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="short" name="Short" stroke={SHORT_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="net" name="Net" stroke={seriesColor(2)} strokeWidth={1.4} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-[11px] text-slate-400">
              <span style={{ color: LONG_COLOR }}>● Long (+)</span>{"  "}
              <span style={{ color: SHORT_COLOR }}>● Short (−)</span>{"  "}
              <span style={{ color: seriesColor(2) }}>– – Net (≈ 0, dollar-neutral)</span>.
            </p>
          </div>

          {/* Turnover */}
          <div className="card space-y-1 p-5">
            <p className="section-title mb-1">Turnover per rebalance</p>
            <ResponsiveContainer width="100%" height={150}>
              <ComposedChart data={result.turnover} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={{ stroke: CHART_AXIS_LINE }} tickLine={false} minTickGap={48} />
                <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => v.toFixed(1)} />
                <Tooltip content={<NeonTooltip formatValue={(v: number) => v.toFixed(3)} />} />
                <Bar dataKey="turnover" name="Turnover" fill={TURNOVER_COLOR} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Latest ranking */}
          <div className="card space-y-2 p-5">
            <p className="section-title">
              Latest ranking{result.latest_rebalance_date ? ` — ${result.latest_rebalance_date}` : ""}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full max-w-2xl text-xs">
                <thead>
                  <tr className="text-slate-400">
                    <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Rank</th>
                    <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Ticker</th>
                    <th className="px-2 py-1 text-left font-medium uppercase tracking-wide">Sector</th>
                    <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Score</th>
                    <th className="px-2 py-1 text-center font-medium uppercase tracking-wide">Side</th>
                    <th className="px-2 py-1 text-right font-medium uppercase tracking-wide">Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {ranking.map((row) => (
                    <tr key={row.ticker} className="border-t border-[var(--line)]">
                      <td className="px-2 py-1 text-right mono">{row.rank}</td>
                      <td className="px-2 py-1 text-left mono">{row.ticker}</td>
                      <td className="px-2 py-1 text-left">{row.sector}</td>
                      <td className="px-2 py-1 text-right mono">{fmt(row.score, 4)}</td>
                      <td className="px-2 py-1 text-center font-semibold" style={{ color: sideColor(row.side) }}>{row.side}</td>
                      <td className="px-2 py-1 text-right mono">{fmt(row.weight, 4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Diagnostics */}
          <div className="card space-y-2 p-5">
            <p className="section-title">Diagnostics</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricCard label="Assets" value={String(result.diagnostics.n_assets)} />
              <MetricCard label="Dates" value={String(result.diagnostics.n_dates)} />
              <MetricCard label="Valid rebalances" value={String(result.diagnostics.valid_rebalance_dates)} tone="positive" />
              <MetricCard label="Skipped dates" value={String(result.diagnostics.skipped_dates)} tone={result.diagnostics.skipped_dates > 0 ? "warn" : "default"} />
            </div>
            {result.diagnostics.warnings.map((w, i) => (
              <p key={i} className="text-[11px] text-slate-400">⚠ {w}</p>
            ))}
          </div>
        </>
      )}

      {/* Education */}
      <div className="card space-y-3 p-5 text-sm text-slate-400">
        <p className="section-title">How the scanner engine works</p>
        <ul className="space-y-2">
          <li><span className="font-semibold text-slate-900">Universe → matrices:</span> instead of one price series, the engine builds a price matrix (date × asset), a signal/score matrix, and a dollar-neutral weight matrix, then collapses them to one portfolio return series.</li>
          <li><span className="font-semibold text-slate-900">Rank & bucket:</span> each rebalance date, assets are ranked by their cross-sectional score; the top quantile is the long basket, the bottom quantile the short basket.</li>
          <li><span className="font-semibold text-slate-900">Dollar-neutral:</span> longs sum to +gross/2 and shorts to −gross/2, so net exposure ≈ 0 and gross exposure = the target (default 1.0).</li>
          <li><span className="font-semibold text-slate-900">Lookahead-safe:</span> signals use information through date t; weights are shifted forward one period before P&L, so weights at t earn the return from t to t+1 — never the same-day return.</li>
          <li><span className="font-semibold text-slate-900">Costs & turnover:</span> turnover = Σ|wₜ − wₜ₋₁|; cost = turnover × bps/10000 is deducted from the gross return the position earns.</li>
          <li><span className="font-semibold text-slate-900">Limitations:</span> synthetic universe (no survivorship/point-in-time issues modeled), no market impact, borrow, or capacity; sector/beta neutralization, live universes, and ML selection are planned. Educational, not investment advice.</li>
        </ul>
        <p className="text-[11px] text-slate-400">{CAVEAT}</p>
      </div>
    </div>
  );
}
