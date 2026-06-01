"use client";

import { useMemo, useState } from "react";
import { runPortfolioWalkForward } from "@/lib/api";
import type {
  PortfolioObjective,
  PortfolioWalkForwardResponse,
} from "@/lib/types";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import { fmtPct, fmtRatio, fmtDollar } from "@/lib/format";

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

/** Compact "SPY 40% · QQQ 30% · …" summary of the top weights. */
function weightsSummary(weights: Record<string, number>): string {
  return Object.entries(weights)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([t, w]) => `${t} ${(w * 100).toFixed(0)}%`)
    .join(" · ");
}

export default function PortfolioWalkForwardPanel() {
  const [tickersStr, setTickersStr] = useState("SPY, QQQ, GLD, TLT");
  const [startDate, setStartDate] = useState("2010-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [trainStr, setTrainStr] = useState("756");
  const [testStr, setTestStr] = useState("126");
  const [stepStr, setStepStr] = useState("126");
  const [objective, setObjective] = useState<PortfolioObjective>("max_sharpe");
  const [rfStr, setRfStr] = useState("0.02");
  const [capitalStr, setCapitalStr] = useState("100000");
  const [costStr, setCostStr] = useState("10");

  const [result, setResult] = useState<PortfolioWalkForwardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { request, validationMsg } = useMemo(() => {
    const parsed = parseTickers(tickersStr);
    if (!parsed.ok) return { request: null, validationMsg: parsed.msg ?? null };
    if (!startDate || !endDate || startDate >= endDate) {
      return { request: null, validationMsg: "Start date must be before end date." };
    }
    const train = parseInt_(trainStr);
    const test = parseInt_(testStr);
    const step = parseInt_(stepStr);
    if (train === null || train < 1) return { request: null, validationMsg: "Train window must be a positive integer." };
    if (test === null || test < 1) return { request: null, validationMsg: "Test window must be a positive integer." };
    if (step === null || step < 1) return { request: null, validationMsg: "Step must be a positive integer." };
    const rf = parseNum(rfStr);
    const capital = parseNum(capitalStr);
    const cost = parseNum(costStr);
    if (rf === null || rf < 0) return { request: null, validationMsg: "Risk-free rate must be ≥ 0." };
    if (capital === null || capital <= 0) return { request: null, validationMsg: "Initial capital must be > 0." };
    if (cost === null || cost < 0) return { request: null, validationMsg: "Transaction cost must be ≥ 0 bps." };
    return {
      request: {
        tickers: parsed.tickers,
        start_date: startDate,
        end_date: endDate,
        train_window_days: train,
        test_window_days: test,
        step_days: step,
        objective,
        risk_free_rate: rf,
        initial_capital: capital,
        transaction_cost_bps: cost,
      },
      validationMsg: null as string | null,
    };
  }, [tickersStr, startDate, endDate, trainStr, testStr, stepStr, objective, rfStr, capitalStr, costStr]);

  async function handleRun() {
    if (!request || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runPortfolioWalkForward(request);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Walk-forward optimization failed.");
    } finally {
      setLoading(false);
    }
  }

  const chartData = useMemo(() => {
    if (!result) return [];
    return result.stitched_equity_curve.map((p, i) => ({
      date: p.date,
      strategy: p.value,
      benchmark: result.benchmark_equity_curve[i]?.value ?? p.value,
    }));
  }, [result]);

  return (
    <div className="space-y-6">
      {/* OOS note */}
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex gap-3">
        <span className="text-amber-500 mt-0.5 flex-shrink-0">⚠</span>
        <p className="text-sm text-amber-800">
          <span className="font-semibold">Walk-forward (out-of-sample).</span>{" "}
          Weights are estimated only on past training windows and applied to the
          following unseen test window — this reduces overfitting versus static
          optimization, but still relies on historical assumptions and does not
          predict future performance. Not investment advice.
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
            <input type="date" className={inputCls} value={startDate} onChange={(e) => setStartDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="End">
            <input type="date" className={inputCls} value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Risk-Free Rate" hint="annual decimal">
            <input type="number" step="0.01" className={inputCls} value={rfStr} onChange={(e) => setRfStr(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Train Window" hint="days">
            <input type="number" className={inputCls} value={trainStr} onChange={(e) => setTrainStr(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Test Window" hint="days">
            <input type="number" className={inputCls} value={testStr} onChange={(e) => setTestStr(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Step" hint="days">
            <input type="number" className={inputCls} value={stepStr} onChange={(e) => setStepStr(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Initial Capital" hint="USD">
            <input type="number" className={inputCls} value={capitalStr} onChange={(e) => setCapitalStr(e.target.value)} disabled={loading} />
          </Field>
          <Field label="Transaction Cost" hint="bps">
            <input type="number" className={inputCls} value={costStr} onChange={(e) => setCostStr(e.target.value)} disabled={loading} />
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
            {loading ? "Optimizing…" : "Run Walk-Forward Optimization"}
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
            <p className="text-sm font-semibold text-red-700">Walk-forward optimization failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-lg font-bold text-slate-900">
              Walk-Forward {OBJECTIVES.find((o) => o.id === result.objective)?.label}
            </h2>
            <span className="text-slate-400 text-sm">
              {result.start_date} → {result.end_date}
            </span>
            <span className="text-xs text-slate-400">
              {result.tickers.join(" · ")} · {result.num_windows} windows · train{" "}
              {result.train_window_days}d / test {result.test_window_days}d / step{" "}
              {result.step_days}d
            </span>
          </div>

          {/* Aggregate OOS metrics: optimized vs equal-weight */}
          <MetricsGrid
            strategy={result.metrics}
            benchmark={result.benchmark_metrics}
            ticker="Equal Weight"
            strategyLabel="Walk-Forward"
          />

          <div className="card p-6">
            <p className="section-title mb-4">
              Stitched Out-of-Sample Equity vs Equal-Weight
            </p>
            <EquityCurveChart data={chartData} />
          </div>

          <div className="card p-6">
            <p className="section-title mb-4">Drawdown</p>
            <DrawdownChart data={chartData} />
          </div>

          {/* Weight stability */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card p-6">
              <p className="section-title mb-4">Average Weight by Asset</p>
              <div className="space-y-2">
                {Object.entries(result.weight_stability.average_weight_by_asset)
                  .sort((a, b) => b[1] - a[1])
                  .map(([t, w]) => (
                    <WeightBar key={t} ticker={t} weight={w} />
                  ))}
              </div>
            </div>
            <div className="card p-6">
              <p className="section-title mb-4">Weight Stability</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Average turnover (rebalances)</span>
                  <span className="mono text-slate-800">
                    {fmtPct(result.weight_stability.average_turnover, 1)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Max turnover</span>
                  <span className="mono text-slate-800">
                    {fmtPct(result.weight_stability.max_turnover, 1)}
                  </span>
                </div>
                <p className="text-xs text-slate-400 pt-2">
                  Turnover = Σ|new weight − previous weight| between consecutive
                  optimizations (the entry-from-cash window is excluded).
                </p>
              </div>
            </div>
          </div>

          {/* Window table */}
          <div className="card p-6">
            <p className="section-title mb-4">
              Walk-Forward Windows{" "}
              <span className="normal-case font-normal text-slate-400 ml-1">
                ({result.num_windows})
              </span>
            </p>
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-400 border-b border-slate-100">
                    <th className="py-2 pr-3">Train</th>
                    <th className="py-2 pr-3">Test</th>
                    <th className="py-2 pr-3">Weights</th>
                    <th className="py-2 pr-3 text-right">Test Sharpe</th>
                    <th className="py-2 pr-3 text-right">Test CAGR</th>
                    <th className="py-2 pr-3 text-right">Turnover</th>
                    <th className="py-2 text-right">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {result.windows.map((w, i) => (
                    <tr key={i} className="border-b border-slate-50">
                      <td className="py-1.5 pr-3 text-slate-500 text-xs whitespace-nowrap mono">
                        {w.train_start_date} → {w.train_end_date}
                      </td>
                      <td className="py-1.5 pr-3 text-slate-500 text-xs whitespace-nowrap mono">
                        {w.test_start_date} → {w.test_end_date}
                      </td>
                      <td className="py-1.5 pr-3 text-slate-600 text-xs">
                        {weightsSummary(w.weights)}
                      </td>
                      <td className="py-1.5 pr-3 text-right mono text-slate-700">
                        {fmtRatio(w.test_metrics.sharpe_ratio, 2)}
                      </td>
                      <td className="py-1.5 pr-3 text-right mono text-slate-700">
                        {fmtPct(w.test_metrics.cagr, 1)}
                      </td>
                      <td className="py-1.5 pr-3 text-right mono text-slate-600">
                        {fmtPct(w.turnover, 1)}
                      </td>
                      <td className="py-1.5 text-right mono text-slate-500">
                        {fmtDollar(w.transaction_cost)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
