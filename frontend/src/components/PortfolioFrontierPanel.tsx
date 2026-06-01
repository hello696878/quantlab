"use client";

import { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { runEfficientFrontier } from "@/lib/api";
import type {
  EfficientFrontierResponse,
  FrontierPortfolioPoint,
} from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

// Highlight colours for the three special portfolios.
const C_RANDOM = "rgba(148,163,184,0.45)";
const C_FRONTIER = "#22d3ee";
const C_EQUAL = "#a78bfa";
const C_MINVOL = "#34d399";
const C_MAXSHARPE = "#fbbf24";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-600 uppercase tracking-wide">
        {label}
        {hint && (
          <span className="ml-1 normal-case font-normal text-slate-400">{hint}</span>
        )}
      </label>
      {children}
    </div>
  );
}

function parseNum(raw: string): number | null {
  const t = raw.trim();
  if (t === "") return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

function parseInt_(raw: string): number | null {
  const v = parseNum(raw);
  return v !== null && Number.isInteger(v) ? v : null;
}

function parseTickers(raw: string): { ok: boolean; tickers: string[]; msg?: string } {
  const parts = raw
    .split(",")
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);
  if (parts.length === 0) return { ok: false, tickers: [], msg: "Enter at least one ticker." };
  if (parts.length > 20) return { ok: false, tickers: [], msg: "At most 20 tickers." };
  const seen = new Set<string>();
  for (const p of parts) {
    if (seen.has(p)) return { ok: false, tickers: [], msg: `Duplicate ticker: ${p}.` };
    seen.add(p);
  }
  return { ok: true, tickers: parts };
}

const pctTick = (v: number) => `${(v * 100).toFixed(0)}%`;

interface ScatterDatum {
  volatility: number;
  expected_return: number;
  sharpe?: number;
  z: number;
  label: string;
  weights?: Record<string, number>;
}

function FrontierTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: ScatterDatum }[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-slate-700 mb-1">{d.label}</p>
      <div className="flex justify-between gap-4">
        <span className="text-slate-500">Return</span>
        <span className="tabular">{fmtPct(d.expected_return, 1)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-slate-500">Volatility</span>
        <span className="tabular">{fmtPct(d.volatility, 1)}</span>
      </div>
      {d.sharpe !== undefined && (
        <div className="flex justify-between gap-4">
          <span className="text-slate-500">Sharpe</span>
          <span className="tabular">{fmtRatio(d.sharpe, 2)}</span>
        </div>
      )}
      {d.weights && (
        <div className="mt-1 pt-1 border-t border-slate-100">
          {Object.entries(d.weights)
            .sort((a, b) => b[1] - a[1])
            .map(([t, w]) => (
              <div key={t} className="flex justify-between gap-4">
                <span className="text-slate-400">{t}</span>
                <span className="tabular">{(w * 100).toFixed(1)}%</span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

/** A small weights table for a special portfolio card. */
function SpecialCard({
  title,
  color,
  point,
}: {
  title: string;
  color: string;
  point: FrontierPortfolioPoint;
}) {
  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
        <p className="text-sm font-semibold text-slate-800">{title}</p>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="uplabel">Return</p>
          <p className="mono text-sm font-semibold text-slate-900">
            {fmtPct(point.expected_return, 1)}
          </p>
        </div>
        <div>
          <p className="uplabel">Vol</p>
          <p className="mono text-sm font-semibold text-slate-900">
            {fmtPct(point.volatility, 1)}
          </p>
        </div>
        <div>
          <p className="uplabel">Sharpe</p>
          <p className="mono text-sm font-semibold text-slate-900">
            {fmtRatio(point.sharpe, 2)}
          </p>
        </div>
      </div>
      <div className="space-y-1">
        {Object.entries(point.weights)
          .sort((a, b) => b[1] - a[1])
          .map(([t, w]) => (
            <div key={t} className="flex items-center gap-2">
              <span className="mono text-xs text-slate-600 w-14 flex-shrink-0">{t}</span>
              <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full"
                  style={{ width: `${Math.min(100, w * 100)}%`, background: color }}
                />
              </div>
              <span className="mono text-xs text-slate-500 w-11 text-right flex-shrink-0">
                {(w * 100).toFixed(1)}%
              </span>
            </div>
          ))}
      </div>
    </div>
  );
}

export default function PortfolioFrontierPanel() {
  const [tickersStr, setTickersStr] = useState("SPY, QQQ, GLD, TLT");
  const [startDate, setStartDate] = useState("2015-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [rfStr, setRfStr] = useState("0.02");
  const [numStr, setNumStr] = useState("2000");

  const [result, setResult] = useState<EfficientFrontierResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { request, validationMsg } = useMemo(() => {
    const parsed = parseTickers(tickersStr);
    if (!parsed.ok) return { request: null, validationMsg: parsed.msg ?? null };
    if (!startDate || !endDate || startDate >= endDate) {
      return { request: null, validationMsg: "Start date must be before end date." };
    }
    const rf = parseNum(rfStr);
    const num = parseInt_(numStr);
    if (rf === null || rf < 0) return { request: null, validationMsg: "Risk-free rate must be ≥ 0." };
    if (num === null || num < 100 || num > 10000) {
      return { request: null, validationMsg: "Number of portfolios must be 100–10000." };
    }
    return {
      request: {
        tickers: parsed.tickers,
        start_date: startDate,
        end_date: endDate,
        risk_free_rate: rf,
        num_portfolios: num,
      },
      validationMsg: null as string | null,
    };
  }, [tickersStr, startDate, endDate, rfStr, numStr]);

  async function handleRun() {
    if (!request || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runEfficientFrontier(request);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Efficient frontier failed.");
    } finally {
      setLoading(false);
    }
  }

  const randomData: ScatterDatum[] = useMemo(
    () =>
      result
        ? result.random_portfolios.map((p) => ({
            volatility: p.volatility,
            expected_return: p.expected_return,
            sharpe: p.sharpe,
            z: 1,
            label: "Random portfolio",
          }))
        : [],
    [result],
  );

  const frontierData: ScatterDatum[] = useMemo(
    () =>
      result
        ? result.frontier_points.map((p) => ({
            volatility: p.volatility,
            expected_return: p.expected_return,
            z: 1,
            label: "Efficient frontier",
          }))
        : [],
    [result],
  );

  function special(point: FrontierPortfolioPoint, label: string): ScatterDatum[] {
    return [
      {
        volatility: point.volatility,
        expected_return: point.expected_return,
        sharpe: point.sharpe,
        z: 6,
        label,
        weights: point.weights,
      },
    ];
  }

  return (
    <div className="space-y-6">
      {/* Historical / in-sample warning */}
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex gap-3">
        <span className="text-amber-500 mt-0.5 flex-shrink-0">⚠</span>
        <p className="text-sm text-amber-800">
          <span className="font-semibold">Historical, in-sample analysis.</span>{" "}
          Expected returns and covariance are estimated from past data over the
          selected window and may not persist. This is descriptive — not a
          forecast or investment advice.
        </p>
      </div>

      {/* Inputs */}
      <div className="card p-6 space-y-5">
        <Field label="Tickers" hint="comma-separated · long-only · max 20">
          <input
            className={inputCls}
            value={tickersStr}
            onChange={(e) => setTickersStr(e.target.value)}
            placeholder="SPY, QQQ, GLD, TLT"
            disabled={loading}
          />
        </Field>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Field label="Start">
            <input type="date" className={inputCls} value={startDate} onChange={(e) => setStartDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="End">
            <input type="date" className={inputCls} value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Risk-Free Rate" hint="annual decimal">
            <input type="number" step="0.01" className={inputCls} value={rfStr} onChange={(e) => setRfStr(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Random Portfolios" hint="100–10000">
            <input type="number" className={inputCls} value={numStr} onChange={(e) => setNumStr(e.target.value)} disabled={loading} />
          </Field>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRun}
            disabled={!request || loading}
            className="px-5 py-2 rounded-lg text-sm font-semibold text-white bg-blue-600
                       hover:bg-blue-700 transition-colors disabled:opacity-50
                       disabled:cursor-not-allowed"
          >
            {loading ? "Computing…" : "Run Efficient Frontier"}
          </button>
          {validationMsg && !loading && (
            <span className="text-xs text-slate-400">{validationMsg}</span>
          )}
        </div>
      </div>

      {/* Error */}
      {error && !loading && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
          <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-700">Efficient frontier failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="card p-6">
            <p className="section-title mb-4">
              Risk–Return Space{" "}
              <span className="normal-case font-normal text-slate-400 ml-1">
                ({result.random_portfolios.length} random long-only portfolios)
              </span>
            </p>
            <ResponsiveContainer width="100%" height={440}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 16, left: 8 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  type="number"
                  dataKey="volatility"
                  name="Volatility"
                  tickFormatter={pctTick}
                  tick={{ fontSize: 11, fill: "#79839a" }}
                  domain={["auto", "auto"]}
                  label={{
                    value: "Annualised Volatility",
                    position: "insideBottom",
                    offset: -8,
                    fill: "#79839a",
                    fontSize: 12,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="expected_return"
                  name="Expected Return"
                  tickFormatter={pctTick}
                  tick={{ fontSize: 11, fill: "#79839a" }}
                  domain={["auto", "auto"]}
                  width={52}
                />
                <ZAxis type="number" dataKey="z" range={[18, 240]} />
                <Tooltip content={<FrontierTooltip />} cursor={{ strokeDasharray: "3 3" }} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />

                <Scatter
                  name="Random"
                  data={randomData}
                  fill={C_RANDOM}
                  isAnimationActive={false}
                />
                <Scatter
                  name="Efficient frontier"
                  data={frontierData}
                  fill={C_FRONTIER}
                  line={{ stroke: C_FRONTIER, strokeWidth: 1.5 }}
                  lineType="joint"
                  isAnimationActive={false}
                />
                <Scatter
                  name="Equal weight"
                  data={special(result.equal_weight, "Equal weight")}
                  fill={C_EQUAL}
                  shape="diamond"
                />
                <Scatter
                  name="Min volatility"
                  data={special(result.min_volatility, "Min volatility")}
                  fill={C_MINVOL}
                  shape="triangle"
                />
                <Scatter
                  name="Max Sharpe"
                  data={special(result.max_sharpe, "Max Sharpe")}
                  fill={C_MAXSHARPE}
                  shape="star"
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <SpecialCard title="Equal Weight" color={C_EQUAL} point={result.equal_weight} />
            <SpecialCard title="Minimum Volatility" color={C_MINVOL} point={result.min_volatility} />
            <SpecialCard title="Maximum Sharpe" color={C_MAXSHARPE} point={result.max_sharpe} />
          </div>
        </>
      )}
    </div>
  );
}
