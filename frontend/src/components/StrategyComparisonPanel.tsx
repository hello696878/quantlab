"use client";

/**
 * Strategy Comparison panel.
 *
 * Runs five single-asset strategies on the same ticker/date range using fixed
 * default parameters and displays:
 *   1. Ranking cards  (Best Sharpe, Best CAGR, Best Calmar, Lowest Drawdown)
 *   2. Comparison table  (all strategies vs benchmark)
 *   3. Multi-line equity curve  (all 5 strategies + benchmark)
 *   4. Notes / disclaimer
 *
 * Default strategy params (fixed on the backend):
 *   SMA Crossover        fast=50, slow=200
 *   RSI Mean Reversion   window=14, OB=30, exit=50
 *   Bollinger Band       window=20, 2σ, exit=middle
 *   Momentum             window=126, thresholds=0
 *   Volatility Breakout  lookback=20, mult=1.0, exit=10
 */

import { useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { BacktestApiError, runStrategyComparison } from "@/lib/api";
import type { StrategyComparisonRequest, StrategyComparisonResponse } from "@/lib/types";
import {
  fmtPct,
  fmtRatio,
  fmtDollarTick,
  fmtDollar,
  fmtMonthYear,
} from "@/lib/format";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_PARAMS: StrategyComparisonRequest = {
  ticker: "SPY",
  start_date: "2015-01-01",
  end_date: "2023-12-31",
  initial_capital: 100_000,
  transaction_cost_bps: 10,
};

const POPULAR_TICKERS = ["SPY", "QQQ", "AAPL", "GLD", "BTC-USD"];

/** Display order and visual styling for each strategy. */
const STRATEGY_META: Record<
  string,
  { color: string; dash?: string; width?: number }
> = {
  sma_crossover:      { color: "#2563eb", width: 2 },
  rsi_mean_reversion: { color: "#059669", width: 2 },
  bollinger_band:     { color: "#7c3aed", width: 2 },
  momentum:           { color: "#d97706", width: 2 },
  volatility_breakout:{ color: "#dc2626", width: 2 },
};

const BENCHMARK_COLOR = "#94a3b8";

// ---------------------------------------------------------------------------
// Styling
// ---------------------------------------------------------------------------

const inputCls =
  "w-full px-3 py-2 text-sm border border-slate-300 rounded-lg " +
  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 bg-white";

const labelCls = "block text-xs font-medium text-slate-600 mb-1";

// ---------------------------------------------------------------------------
// Multi-strategy equity curve chart
// ---------------------------------------------------------------------------

type MultiStrategyPoint = Record<string, string | number>;

function buildChartData(result: StrategyComparisonResponse): MultiStrategyPoint[] {
  // All equity curves share the same dates (same ticker + date range).
  return result.benchmark.map((pt, i) => {
    const row: MultiStrategyPoint = { date: pt.date };
    for (const s of result.strategies) {
      row[s.strategy] = s.equity_curve[i]?.strategy ?? 0;
    }
    row["benchmark"] = pt.strategy;
    return row;
  });
}

function buildYearTicks(data: MultiStrategyPoint[]): string[] {
  const seen = new Set<string>();
  const ticks: string[] = [];
  for (const d of data) {
    const year = String(d.date).slice(0, 4);
    if (!seen.has(year)) {
      seen.add(year);
      ticks.push(String(d.date));
    }
  }
  return ticks;
}

function MultiStrategyTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const sorted = [...payload].sort((a, b) => b.value - a.value);
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg px-3 py-2 text-xs min-w-[160px]">
      <p className="font-semibold text-slate-600 mb-1.5">
        {label ? fmtMonthYear(String(label)) : ""}
      </p>
      {sorted.map((p) => (
        <div key={p.name} className="flex justify-between gap-4 py-0.5">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-semibold tabular-nums">{fmtDollar(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

interface MultiStrategyChartProps {
  result: StrategyComparisonResponse;
}

function MultiStrategyChart({ result }: MultiStrategyChartProps) {
  const data = buildChartData(result);
  if (!data.length) return null;
  const yearTicks = buildYearTicks(data);

  return (
    <ResponsiveContainer width="100%" height={380}>
      <LineChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="date"
          ticks={yearTicks}
          tickFormatter={(v: string) => v.slice(0, 4)}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          axisLine={{ stroke: "#e2e8f0" }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={fmtDollarTick}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          axisLine={false}
          tickLine={false}
          width={64}
        />
        <Tooltip content={<MultiStrategyTooltip />} />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />

        {/* Benchmark — dashed, behind strategies */}
        <Line
          type="monotone"
          dataKey="benchmark"
          name="Benchmark"
          stroke={BENCHMARK_COLOR}
          strokeWidth={1.5}
          strokeDasharray="5 3"
          dot={false}
          activeDot={{ r: 3 }}
        />

        {/* One line per strategy */}
        {result.strategies.map((s) => (
          <Line
            key={s.strategy}
            type="monotone"
            dataKey={s.strategy}
            name={s.display_name}
            stroke={STRATEGY_META[s.strategy]?.color ?? "#64748b"}
            strokeWidth={STRATEGY_META[s.strategy]?.width ?? 2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Ranking card
// ---------------------------------------------------------------------------

interface RankingCardProps {
  label: string;
  winner: string;
  color: string;
}

function RankingCard({ label, winner, color }: RankingCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-1">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm font-bold" style={{ color }}>
        {winner}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Comparison table
// ---------------------------------------------------------------------------

interface TableRowProps {
  name: string;
  metrics: StrategyComparisonResponse["strategies"][0]["metrics"];
  numTrades: number;
  isBest: boolean;
  color: string;
}

function ComparisonTableRow({
  name,
  metrics,
  numTrades,
  isBest,
  color,
}: TableRowProps) {
  return (
    <tr
      className={
        "border-b border-slate-100 hover:bg-slate-50 " +
        (isBest ? "bg-blue-50/40" : "")
      }
    >
      <td className="px-3 py-2 text-sm font-medium" style={{ color }}>
        {name}
      </td>
      <td className="px-3 py-2 text-sm text-right tabular-nums">
        {fmtPct(metrics.cagr)}
      </td>
      <td className="px-3 py-2 text-sm text-right tabular-nums">
        {fmtPct(metrics.total_return)}
      </td>
      <td
        className={
          "px-3 py-2 text-sm text-right tabular-nums font-medium " +
          (metrics.sharpe_ratio >= 0 ? "text-emerald-700" : "text-red-600")
        }
      >
        {fmtRatio(metrics.sharpe_ratio)}
      </td>
      <td className="px-3 py-2 text-sm text-right tabular-nums">
        {fmtRatio(metrics.sortino_ratio)}
      </td>
      <td className="px-3 py-2 text-sm text-right tabular-nums">
        {fmtRatio(metrics.calmar_ratio)}
      </td>
      <td
        className={
          "px-3 py-2 text-sm text-right tabular-nums " +
          (metrics.max_drawdown < -0.2 ? "text-red-600" : "text-slate-700")
        }
      >
        {fmtPct(metrics.max_drawdown)}
      </td>
      <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
        {fmtPct(metrics.volatility)}
      </td>
      <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
        {numTrades}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function StrategyComparisonPanel() {
  const [ticker, setTicker] = useState(DEFAULT_PARAMS.ticker);
  const [startDate, setStartDate] = useState(DEFAULT_PARAMS.start_date);
  const [endDate, setEndDate] = useState(DEFAULT_PARAMS.end_date);
  const [capitalStr, setCapitalStr] = useState(String(DEFAULT_PARAMS.initial_capital));
  const [costBpsStr, setCostBpsStr] = useState(String(DEFAULT_PARAMS.transaction_cost_bps));

  // Derived numbers — parsed at render time so the input can hold partial strings
  const capital = parseFloat(capitalStr);
  const costBps = parseFloat(costBpsStr);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StrategyComparisonResponse | null>(null);

  // ── Validation ────────────────────────────────────────────────────────
  const datesOk = startDate < endDate;
  const moneyOk = !isNaN(costBps) && costBps >= 0 && costBps < 10_000 && !isNaN(capital) && capital > 0;
  const formInvalid = !ticker.trim() || !datesOk || !moneyOk || loading;

  let validationMsg: string | null = null;
  if (!ticker.trim()) {
    validationMsg = "Ticker is required.";
  } else if (startDate >= endDate) {
    validationMsg = "Start date must be before end date.";
  } else if (isNaN(costBps)) {
    validationMsg = "Transaction cost must be a valid number (≥ 0 bps).";
  } else if (costBps < 0 || costBps >= 10_000) {
    validationMsg = "Transaction cost must be between 0 and 9,999 bps.";
  } else if (isNaN(capital)) {
    validationMsg = "Initial capital must be a valid number (> 0).";
  } else if (capital <= 0) {
    validationMsg = "Initial capital must be greater than 0.";
  }

  // ── Submit ────────────────────────────────────────────────────────────
  async function handleRun() {
    if (formInvalid) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await runStrategyComparison({
        ticker: ticker.trim().toUpperCase(),
        start_date: startDate,
        end_date: endDate,
        initial_capital: capital,
        transaction_cost_bps: costBps,
      });
      setResult(data);
    } catch (err) {
      setError(
        err instanceof BacktestApiError || err instanceof Error
          ? err.message
          : "An unexpected error occurred.",
      );
    } finally {
      setLoading(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* ── Form card ──────────────────────────────────────────────────── */}
      <div className="card p-6 space-y-5">

        {/* Ticker */}
        <div>
          <label className={labelCls}>Ticker</label>
          <div className="flex gap-2 flex-wrap items-center">
            <input
              type="text"
              className={`${inputCls} uppercase w-36`}
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="SPY"
              disabled={loading}
              maxLength={12}
            />
            <div className="flex gap-1.5 flex-wrap">
              {POPULAR_TICKERS.map((t) => (
                <button
                  key={t}
                  type="button"
                  disabled={loading}
                  onClick={() => setTicker(t)}
                  className={
                    "px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors " +
                    (ticker === t
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-slate-600 border-slate-300 hover:border-blue-400 hover:text-blue-600")
                  }
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Dates */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Start Date</label>
            <input
              type="date"
              className={inputCls}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              disabled={loading}
            />
          </div>
          <div>
            <label className={labelCls}>End Date</label>
            <input
              type="date"
              className={inputCls}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        {/* Cost + Capital */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Transaction Cost (bps, one-way)</label>
            <input
              type="number"
              className={inputCls}
              value={costBpsStr}
              min={0}
              max={9999}
              step={1}
              onChange={(e) => setCostBpsStr(e.target.value)}
              disabled={loading}
            />
          </div>
          <div>
            <label className={labelCls}>Initial Capital ($)</label>
            <input
              type="number"
              className={inputCls}
              value={capitalStr}
              min={1}
              step={10000}
              onChange={(e) => setCapitalStr(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        {/* Fixed-params note */}
        <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-xs text-slate-500 space-y-0.5">
          <p className="font-medium text-slate-600">Fixed default parameters</p>
          <p>SMA Crossover — fast=50, slow=200</p>
          <p>RSI Mean Reversion — window=14, oversold=30, exit=50</p>
          <p>Bollinger Band — window=20, 2σ, exit=middle band</p>
          <p>Momentum — window=126, entry/exit threshold=0</p>
          <p>Volatility Breakout — lookback=20, multiplier=1.0×, exit=10-day mean</p>
        </div>

        {validationMsg && (
          <p className="text-xs text-red-600 font-medium">{validationMsg}</p>
        )}

        <button
          type="button"
          disabled={formInvalid}
          onClick={handleRun}
          className={
            "w-full py-2.5 px-4 rounded-xl font-semibold text-sm transition-colors " +
            (formInvalid
              ? "bg-slate-100 text-slate-400 cursor-not-allowed"
              : "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800")
          }
        >
          {loading ? "Running comparison…" : "Run Comparison"}
        </button>
      </div>

      {/* ── Loading ──────────────────────────────────────────────────────── */}
      {loading && (
        <div className="card p-8 text-center">
          <div className="inline-flex items-center gap-3 text-slate-500">
            <svg className="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span className="text-sm font-medium">Fetching data and running all five strategies…</span>
          </div>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────────────── */}
      {error && !loading && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex gap-3">
          <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
          <div>
            <p className="text-sm font-semibold text-red-700">Comparison failed</p>
            <p className="text-sm text-red-600 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────────── */}
      {result && !loading && (
        <div className="space-y-6">

          {/* ── Header ─────────────────────────────────────────────────── */}
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="text-lg font-bold text-slate-900">{result.ticker}</h2>
            <span className="text-slate-400 text-sm">
              {result.start_date} → {result.end_date}
            </span>
            <span className="ml-auto text-xs text-slate-400">
              {result.transaction_cost_bps} bps · $
              {result.initial_capital.toLocaleString()}
            </span>
          </div>

          {/* ── Ranking cards ──────────────────────────────────────────── */}
          <div>
            <p className="section-title mb-3">Rankings</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <RankingCard
                label="Best Sharpe Ratio"
                winner={result.ranking.best_by_sharpe}
                color={
                  STRATEGY_META[
                    result.strategies.find(
                      (s) => s.display_name === result.ranking.best_by_sharpe,
                    )?.strategy ?? ""
                  ]?.color ?? "#2563eb"
                }
              />
              <RankingCard
                label="Best CAGR"
                winner={result.ranking.best_by_cagr}
                color={
                  STRATEGY_META[
                    result.strategies.find(
                      (s) => s.display_name === result.ranking.best_by_cagr,
                    )?.strategy ?? ""
                  ]?.color ?? "#2563eb"
                }
              />
              <RankingCard
                label="Best Calmar Ratio"
                winner={result.ranking.best_by_calmar}
                color={
                  STRATEGY_META[
                    result.strategies.find(
                      (s) => s.display_name === result.ranking.best_by_calmar,
                    )?.strategy ?? ""
                  ]?.color ?? "#2563eb"
                }
              />
              <RankingCard
                label="Lowest Max Drawdown"
                winner={result.ranking.lowest_drawdown}
                color={
                  STRATEGY_META[
                    result.strategies.find(
                      (s) => s.display_name === result.ranking.lowest_drawdown,
                    )?.strategy ?? ""
                  ]?.color ?? "#2563eb"
                }
              />
            </div>
          </div>

          {/* ── Comparison table ───────────────────────────────────────── */}
          <div className="card p-6 space-y-3">
            <p className="section-title">Strategy Comparison</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b-2 border-slate-200">
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">
                      Strategy
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">CAGR</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">
                      Total Return
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Sharpe</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Sortino</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Calmar</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Max DD</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Vol</th>
                    <th className="px-3 py-2 text-right font-semibold text-slate-600">Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {result.strategies.map((s) => (
                    <ComparisonTableRow
                      key={s.strategy}
                      name={s.display_name}
                      metrics={s.metrics}
                      numTrades={s.num_trades}
                      isBest={s.display_name === result.ranking.best_by_sharpe}
                      color={STRATEGY_META[s.strategy]?.color ?? "#64748b"}
                    />
                  ))}
                  {/* Benchmark row */}
                  <tr className="border-b border-slate-100 bg-slate-50/60 hover:bg-slate-100/60">
                    <td className="px-3 py-2 text-sm font-medium text-slate-400">
                      Benchmark (buy &amp; hold)
                    </td>
                    <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
                      {fmtPct(result.benchmark_metrics.cagr)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
                      {fmtPct(result.benchmark_metrics.total_return)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
                      {fmtRatio(result.benchmark_metrics.sharpe_ratio)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
                      {fmtRatio(result.benchmark_metrics.sortino_ratio)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
                      {fmtRatio(result.benchmark_metrics.calmar_ratio)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
                      {fmtPct(result.benchmark_metrics.max_drawdown)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
                      {fmtPct(result.benchmark_metrics.volatility)}
                    </td>
                    <td className="px-3 py-2 text-sm text-right tabular-nums text-slate-500">
                      —
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-400">
              Highlighted row = best Sharpe ratio.  Max DD in red when below −20%.
            </p>
          </div>

          {/* ── Multi-strategy equity curve ────────────────────────────── */}
          <div className="card p-6">
            <p className="section-title mb-4">Equity Curves</p>
            <MultiStrategyChart result={result} />
          </div>

          {/* ── Default params reference ───────────────────────────────── */}
          <div className="card p-6 space-y-3">
            <p className="section-title">Default Parameters Used</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {result.strategies.map((s) => (
                <div
                  key={s.strategy}
                  className="rounded-lg border border-slate-200 p-3 space-y-1"
                >
                  <p
                    className="text-xs font-semibold"
                    style={{ color: STRATEGY_META[s.strategy]?.color ?? "#64748b" }}
                  >
                    {s.display_name}
                  </p>
                  {Object.entries(s.params).map(([k, v]) => (
                    <p key={k} className="text-xs text-slate-500">
                      <span className="font-medium text-slate-600">{k}</span>:{" "}
                      {String(v)}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* ── Disclaimer ─────────────────────────────────────────────── */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-1.5 text-xs text-slate-500">
            <p className="font-semibold text-slate-600 text-sm">Important Notes</p>
            <p>
              This comparison uses a single in-sample period with fixed default parameters.
              Results are sensitive to the chosen date range and parameters — a strategy that
              ranks first here may underperform with different settings or in a different period.
            </p>
            <p>
              Trend-following strategies (SMA Crossover, Momentum, Volatility Breakout) tend to
              outperform in persistent directional markets.  Mean-reversion strategies (RSI,
              Bollinger Band) tend to do better in range-bound or high-volatility environments.
            </p>
            <p>
              This comparison does not constitute a recommendation.  Always validate results
              out-of-sample before drawing conclusions — use the SMA Train/Test or Walk-Forward
              tools for that purpose.
            </p>
          </div>

        </div>
      )}
    </div>
  );
}
