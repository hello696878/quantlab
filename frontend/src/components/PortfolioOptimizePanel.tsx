"use client";

import { useMemo, useState } from "react";
import { runPortfolioOptimize } from "@/lib/api";
import type {
  PortfolioObjective,
  PortfolioOptimizeResponse,
} from "@/lib/types";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import ExportReportButton from "@/components/ExportReportButton";
import { buildPortfolioOptimizeReport } from "@/lib/reportExport";
import { fmtPct, fmtRatio } from "@/lib/format";

const OBJECTIVES: { id: PortfolioObjective; label: string }[] = [
  { id: "max_sharpe", label: "Maximum Sharpe" },
  { id: "min_volatility", label: "Minimum Volatility" },
  { id: "equal_weight", label: "Equal Weight" },
];

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

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

function WeightBar({ ticker, weight }: { ticker: string; weight: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="mono text-xs text-slate-600 w-16 flex-shrink-0">{ticker}</span>
      <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
        <div
          className="h-full bg-blue-600"
          style={{ width: `${Math.min(100, Math.max(0, weight * 100))}%` }}
        />
      </div>
      <span className="mono text-xs text-slate-500 w-12 text-right flex-shrink-0">
        {(weight * 100).toFixed(1)}%
      </span>
    </div>
  );
}

export default function PortfolioOptimizePanel() {
  const [tickersStr, setTickersStr] = useState("SPY, QQQ, GLD, TLT");
  const [startDate, setStartDate] = useState("2015-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [objective, setObjective] = useState<PortfolioObjective>("max_sharpe");
  const [rfStr, setRfStr] = useState("0.02");
  const [capitalStr, setCapitalStr] = useState("100000");
  const [costStr, setCostStr] = useState("10");

  const [result, setResult] = useState<PortfolioOptimizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { request, validationMsg } = useMemo(() => {
    const parsed = parseTickers(tickersStr);
    if (!parsed.ok) return { request: null, validationMsg: parsed.msg ?? null };
    if (!startDate || !endDate || startDate >= endDate) {
      return { request: null, validationMsg: "Start date must be before end date." };
    }
    const rf = parseNum(rfStr);
    const capital = parseNum(capitalStr);
    const cost = parseNum(costStr);
    if (rf === null || rf < 0) {
      return { request: null, validationMsg: "Risk-free rate must be ≥ 0 (decimal)." };
    }
    if (capital === null || capital <= 0) {
      return { request: null, validationMsg: "Initial capital must be > 0." };
    }
    if (cost === null || cost < 0) {
      return { request: null, validationMsg: "Transaction cost must be ≥ 0 bps." };
    }
    return {
      request: {
        tickers: parsed.tickers,
        start_date: startDate,
        end_date: endDate,
        initial_capital: capital,
        risk_free_rate: rf,
        transaction_cost_bps: cost,
        objective,
      },
      validationMsg: null as string | null,
    };
  }, [tickersStr, startDate, endDate, objective, rfStr, capitalStr, costStr]);

  async function handleRun() {
    if (!request || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runPortfolioOptimize(request);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Optimization failed.");
    } finally {
      setLoading(false);
    }
  }

  // Zip optimized + equal-weight equity curves into the chart's expected shape.
  const chartData = useMemo(() => {
    if (!result) return [];
    return result.equity_curve.map((p, i) => ({
      date: p.date,
      strategy: p.value,
      benchmark: result.equal_weight_equity_curve[i]?.value ?? p.value,
    }));
  }, [result]);

  return (
    <div className="space-y-6">
      {/* In-sample warning (always visible) */}
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex gap-3">
        <span className="text-amber-500 mt-0.5 flex-shrink-0">⚠</span>
        <p className="text-sm text-amber-800">
          <span className="font-semibold">In-sample optimization.</span> Weights
          are optimized and backtested on the <em>same</em> historical period.
          This can overfit and does not predict future performance. v1 does not
          deduct allocation or turnover costs from the static buy-and-hold
          comparison. Not investment advice.
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

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <Field label="Objective">
            <select
              className={inputCls}
              value={objective}
              onChange={(e) => setObjective(e.target.value as PortfolioObjective)}
              disabled={loading}
            >
              {OBJECTIVES.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Start">
            <input
              type="date"
              className={inputCls}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="End">
            <input
              type="date"
              className={inputCls}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="Risk-Free Rate" hint="annual decimal">
            <input
              type="number"
              step="0.01"
              className={inputCls}
              value={rfStr}
              onChange={(e) => setRfStr(e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="Initial Capital" hint="USD">
            <input
              type="number"
              className={inputCls}
              value={capitalStr}
              onChange={(e) => setCapitalStr(e.target.value)}
              disabled={loading}
            />
          </Field>
          <Field label="Transaction Cost" hint="bps">
            <input
              type="number"
              className={inputCls}
              value={costStr}
              onChange={(e) => setCostStr(e.target.value)}
              disabled={loading}
            />
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
            {loading ? "Optimizing…" : "Run Optimization"}
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
            <p className="text-sm font-semibold text-red-700">Optimization failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="flex justify-end">
            <ExportReportButton getReport={() => buildPortfolioOptimizeReport(result)} />
          </div>

          {/* Portfolio scalar stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="card p-5">
              <p className="uplabel">Expected Annual Return</p>
              <p className="mono text-2xl font-bold text-slate-900 mt-1">
                {fmtPct(result.portfolio_expected_return, 1)}
              </p>
            </div>
            <div className="card p-5">
              <p className="uplabel">Annual Volatility</p>
              <p className="mono text-2xl font-bold text-slate-900 mt-1">
                {fmtPct(result.portfolio_volatility, 1)}
              </p>
            </div>
            <div className="card p-5">
              <p className="uplabel">Sharpe Ratio</p>
              <p className="mono text-2xl font-bold text-slate-900 mt-1">
                {fmtRatio(result.portfolio_sharpe, 2)}
              </p>
            </div>
          </div>

          {/* Weights + expected returns */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card p-6">
              <p className="section-title mb-4">
                Optimized Weights{" "}
                <span className="normal-case font-normal text-slate-400 ml-1">
                  (
                  {OBJECTIVES.find((o) => o.id === result.objective)?.label ??
                    result.objective}
                  )
                </span>
              </p>
              <div className="space-y-2">
                {Object.entries(result.weights)
                  .sort((a, b) => b[1] - a[1])
                  .map(([t, w]) => (
                    <WeightBar key={t} ticker={t} weight={w} />
                  ))}
              </div>
            </div>

            <div className="card p-6">
              <p className="section-title mb-4">Expected Annual Returns</p>
              <table className="w-full text-sm">
                <tbody className="mono">
                  {Object.entries(result.expected_returns).map(([t, r]) => (
                    <tr key={t} className="border-b border-slate-50 last:border-0">
                      <td className="py-1.5 text-slate-600">{t}</td>
                      <td className="py-1.5 text-right text-slate-800">
                        {fmtPct(r, 1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Metrics comparison: optimized vs equal weight */}
          <MetricsGrid
            strategy={result.metrics}
            benchmark={result.equal_weight_metrics}
            ticker="Equal Weight"
            strategyLabel="Optimized"
          />

          <div className="card p-6">
            <p className="section-title mb-4">Optimized vs Equal-Weight Equity</p>
            <EquityCurveChart data={chartData} />
          </div>

          <div className="card p-6">
            <p className="section-title mb-4">Drawdown</p>
            <DrawdownChart data={chartData} />
          </div>
        </>
      )}
    </div>
  );
}
