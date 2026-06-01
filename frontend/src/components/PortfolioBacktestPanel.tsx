"use client";

import { useMemo, useState } from "react";
import { runPortfolioBacktest } from "@/lib/api";
import type {
  PortfolioBacktestResponse,
  PortfolioRebalanceFrequency,
} from "@/lib/types";
import MetricsGrid from "@/components/MetricsGrid";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import { fmtPct, fmtDollar } from "@/lib/format";

const REBALANCE_OPTIONS: { id: PortfolioRebalanceFrequency; label: string }[] = [
  { id: "none", label: "None (buy & hold)" },
  { id: "monthly", label: "Monthly" },
  { id: "quarterly", label: "Quarterly" },
  { id: "yearly", label: "Yearly" },
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

/** Parse the comma-separated tickers field; returns null if invalid. */
function parseTickers(raw: string): { ok: boolean; tickers: string[]; msg?: string } {
  const parts = raw
    .split(",")
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);
  if (parts.length === 0) {
    return { ok: false, tickers: [], msg: "Enter at least one ticker." };
  }
  if (parts.length > 20) {
    return { ok: false, tickers: [], msg: "At most 20 tickers." };
  }
  const seen = new Set<string>();
  for (const p of parts) {
    if (seen.has(p)) {
      return { ok: false, tickers: [], msg: `Duplicate ticker: ${p}.` };
    }
    seen.add(p);
  }
  return { ok: true, tickers: parts };
}

/** Render a single asset's weight as a labelled bar. */
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

export default function PortfolioBacktestPanel() {
  const [tickersStr, setTickersStr] = useState("SPY, QQQ, GLD, TLT");
  const [startDate, setStartDate] = useState("2015-01-01");
  const [endDate, setEndDate] = useState("2023-12-31");
  const [capitalStr, setCapitalStr] = useState("100000");
  const [rebalance, setRebalance] = useState<PortfolioRebalanceFrequency>("monthly");
  const [costStr, setCostStr] = useState("10");

  const [result, setResult] = useState<PortfolioBacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { request, validationMsg } = useMemo(() => {
    const parsed = parseTickers(tickersStr);
    if (!parsed.ok) return { request: null, validationMsg: parsed.msg ?? null };
    if (!startDate || !endDate || startDate >= endDate) {
      return { request: null, validationMsg: "Start date must be before end date." };
    }
    const capital = parseNum(capitalStr);
    const cost = parseNum(costStr);
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
        rebalance_frequency: rebalance,
        transaction_cost_bps: cost,
      },
      validationMsg: null as string | null,
    };
  }, [tickersStr, startDate, endDate, capitalStr, costStr, rebalance]);

  async function handleRun() {
    if (!request || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runPortfolioBacktest(request);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Portfolio backtest failed.");
    } finally {
      setLoading(false);
    }
  }

  // Map portfolio equity → the {strategy, benchmark} shape the charts expect.
  const chartData = useMemo(
    () =>
      result
        ? result.equity_curve.map((p) => ({
            date: p.date,
            strategy: p.portfolio,
            benchmark: p.benchmark,
          }))
        : [],
    [result],
  );

  const finalWeights = result?.weights.at(-1)?.weights ?? null;
  const initialWeights = result?.weights[0]?.weights ?? null;

  return (
    <div className="space-y-6">
      {/* Inputs */}
      <div className="card p-6 space-y-5">
        <Field label="Tickers" hint="comma-separated · equal weight · max 20">
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

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Field label="Rebalance">
            <select
              className={inputCls}
              value={rebalance}
              onChange={(e) =>
                setRebalance(e.target.value as PortfolioRebalanceFrequency)
              }
              disabled={loading}
            >
              {REBALANCE_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
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
            {loading ? "Running…" : "Run Portfolio Backtest"}
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
            <p className="text-sm font-semibold text-red-700">
              Portfolio backtest failed
            </p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-lg font-bold text-slate-900">
              Equal-Weight Portfolio
            </h2>
            <span className="text-slate-400 text-sm">
              {result.start_date} → {result.end_date}
            </span>
            <span className="text-xs text-slate-400">
              {result.tickers.join(" · ")} · rebalance: {result.rebalance_frequency} ·{" "}
              {result.transaction_cost_bps} bps · {result.rebalance_events.length}{" "}
              rebalances
            </span>
          </div>

          <MetricsGrid
            strategy={result.metrics}
            benchmark={result.benchmark_metrics}
            ticker={result.benchmark_ticker}
            strategyLabel="Equal-Weight Portfolio"
          />

          <div className="card p-6">
            <p className="section-title mb-4">
              Portfolio vs {result.benchmark_ticker} Benchmark
            </p>
            <EquityCurveChart data={chartData} />
          </div>

          <div className="card p-6">
            <p className="section-title mb-4">Drawdown</p>
            <DrawdownChart data={chartData} />
          </div>

          {/* Weights */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {initialWeights && (
              <div className="card p-6">
                <p className="section-title mb-4">Initial Weights (equal)</p>
                <div className="space-y-2">
                  {Object.entries(initialWeights).map(([t, w]) => (
                    <WeightBar key={t} ticker={t} weight={w} />
                  ))}
                </div>
              </div>
            )}
            {finalWeights && (
              <div className="card p-6">
                <p className="section-title mb-4">
                  Final Weights{" "}
                  <span className="normal-case font-normal text-slate-400 ml-1">
                    (after drift)
                  </span>
                </p>
                <div className="space-y-2">
                  {Object.entries(finalWeights).map(([t, w]) => (
                    <WeightBar key={t} ticker={t} weight={w} />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Rebalance events */}
          <div className="card p-6">
            <p className="section-title mb-4">
              Rebalance Events{" "}
              <span className="normal-case font-normal text-slate-400 ml-1">
                ({result.rebalance_events.length})
              </span>
            </p>
            {result.rebalance_events.length === 0 ? (
              <p className="text-sm text-slate-400">
                No rebalancing — weights drift for the full period (buy &amp; hold).
              </p>
            ) : (
              <div className="overflow-x-auto max-h-80">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-400 border-b border-slate-100">
                      <th className="py-2 pr-4">Date</th>
                      <th className="py-2 pr-4 text-right">Turnover</th>
                      <th className="py-2 text-right">Cost</th>
                    </tr>
                  </thead>
                  <tbody className="mono">
                    {result.rebalance_events.map((ev) => (
                      <tr key={ev.date} className="border-b border-slate-50">
                        <td className="py-1.5 pr-4 text-slate-600">{ev.date}</td>
                        <td className="py-1.5 pr-4 text-right text-slate-700">
                          {fmtPct(ev.turnover, 1)}
                        </td>
                        <td className="py-1.5 text-right text-slate-500">
                          {fmtDollar(ev.cost)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
