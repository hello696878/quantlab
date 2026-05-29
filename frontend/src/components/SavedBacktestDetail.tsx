"use client";

import { useEffect, useState } from "react";
import { getSavedBacktest } from "@/lib/api";
import type { EquityPoint, SavedBacktestFull, TradeRecord } from "@/lib/types";
import EquityCurveChart from "@/components/EquityCurveChart";
import DrawdownChart from "@/components/DrawdownChart";
import TradeTable from "@/components/TradeTable";
import { fmtPct, fmtRatio, fmtDollar } from "@/lib/format";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STRATEGY_LABELS: Record<string, string> = {
  sma_crossover: "SMA Crossover",
  rsi_mean_reversion: "RSI Mean Reversion",
  bollinger_band: "Bollinger Band",
  momentum: "Momentum",
  volatility_breakout: "Volatility Breakout",
  pairs: "Pairs Trading",
};

function stratLabel(s: string): string {
  return STRATEGY_LABELS[s] ?? s;
}

function fmtSavedDate(iso: string): string {
  return iso.replace("T", " ").slice(0, 16) + " UTC";
}

interface MetricRowProps {
  label: string;
  value: number | null | undefined;
  formatter?: (v: number) => string;
  positiveGood?: boolean;
}

function MetricRow({
  label,
  value,
  formatter = (v) => String(v),
  positiveGood = true,
}: MetricRowProps) {
  if (value == null) return null;
  const color =
    value > 0
      ? positiveGood
        ? "text-green-700"
        : "text-red-700"
      : value < 0
        ? positiveGood
          ? "text-red-700"
          : "text-green-700"
        : "text-slate-600";

  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-slate-50 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`text-sm font-mono font-medium ${color}`}>
        {formatter(value)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface SavedBacktestDetailProps {
  id: number;
  onBack: () => void;
}

export default function SavedBacktestDetail({
  id,
  onBack,
}: SavedBacktestDetailProps) {
  const [record, setRecord] = useState<SavedBacktestFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRecord(null);

    getSavedBacktest(id)
      .then((data) => {
        if (!cancelled) setRecord(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load saved backtest.",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  // ── States ──────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="card p-8 text-center text-sm text-slate-500">
        Loading…
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-blue-600 hover:underline"
        >
          ← Back to list
        </button>
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          ⚠ {error}
        </div>
      </div>
    );
  }

  if (!record) return null;

  const m = record.metrics as Record<string, number>;
  const equityCurve = record.equity_curve as EquityPoint[];
  const trades = record.trades as TradeRecord[];
  const hasEquity = equityCurve.length > 1;
  const hasTrades = trades.length > 0;

  // Strategy params as key-value pairs for display
  const paramEntries = Object.entries(record.params).filter(
    ([, v]) => v != null,
  );

  return (
    <div className="space-y-6">
      {/* Back link */}
      <button
        type="button"
        onClick={onBack}
        className="text-sm text-blue-600 hover:underline"
      >
        ← Back to saved backtests
      </button>

      {/* Header */}
      <div className="card p-5">
        <div className="flex flex-wrap items-start gap-4 justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{record.name}</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              {record.ticker.toUpperCase()} · {stratLabel(record.strategy)} ·{" "}
              {record.start_date} → {record.end_date}
            </p>
          </div>
          <div className="text-xs text-slate-400">
            Saved {fmtSavedDate(record.created_at)}
          </div>
        </div>

        {/* Params pill row */}
        {paramEntries.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {paramEntries.map(([k, v]) => (
              <span
                key={k}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                           bg-slate-100 text-slate-600 text-xs"
              >
                <span className="text-slate-400">{k}:</span>
                <span className="font-mono font-medium">{String(v)}</span>
              </span>
            ))}
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                         bg-slate-100 text-slate-600 text-xs"
            >
              <span className="text-slate-400">capital:</span>
              <span className="font-mono font-medium">
                {fmtDollar(record.initial_capital)}
              </span>
            </span>
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full
                         bg-slate-100 text-slate-600 text-xs"
            >
              <span className="text-slate-400">cost:</span>
              <span className="font-mono font-medium">
                {record.transaction_cost_bps} bps
              </span>
            </span>
          </div>
        )}

        {/* Notes */}
        {record.notes && (
          <div className="mt-3 text-sm text-slate-600 bg-amber-50 rounded-lg px-3 py-2 border border-amber-100">
            {record.notes}
          </div>
        )}
      </div>

      {/* Metrics */}
      {Object.keys(m).length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-3">Performance Metrics</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6">
            <div>
              <MetricRow
                label="Total Return"
                value={m.total_return}
                formatter={(v) => fmtPct(v, 1)}
              />
              <MetricRow
                label="CAGR"
                value={m.cagr}
                formatter={(v) => fmtPct(v, 1)}
              />
              <MetricRow
                label="Volatility"
                value={m.volatility}
                formatter={(v) => fmtPct(v, 1)}
                positiveGood={false}
              />
            </div>
            <div>
              <MetricRow
                label="Sharpe Ratio"
                value={m.sharpe_ratio}
                formatter={(v) => fmtRatio(v, 2)}
              />
              <MetricRow
                label="Sortino Ratio"
                value={m.sortino_ratio}
                formatter={(v) => fmtRatio(v, 2)}
              />
              <MetricRow
                label="Calmar Ratio"
                value={m.calmar_ratio}
                formatter={(v) => fmtRatio(v, 2)}
              />
            </div>
            <div>
              <MetricRow
                label="Max Drawdown"
                value={m.max_drawdown}
                formatter={(v) => fmtPct(v, 1)}
                positiveGood={false}
              />
              <MetricRow
                label="Win Rate"
                value={m.win_rate}
                formatter={(v) => fmtPct(v, 1)}
              />
              <MetricRow
                label="Trading Days"
                value={m.num_days}
                formatter={(v) => String(Math.round(v))}
                positiveGood={true}
              />
            </div>
          </div>
        </div>
      )}

      {/* Equity curve */}
      {hasEquity && (
        <>
          <div className="card p-6">
            <p className="section-title mb-4">Equity Curve</p>
            <EquityCurveChart data={equityCurve} />
          </div>
          <div className="card p-6">
            <p className="section-title mb-4">Drawdown</p>
            <DrawdownChart data={equityCurve} />
          </div>
        </>
      )}

      {/* Trades */}
      {hasTrades && (
        <div className="card p-6">
          <p className="section-title mb-4">
            Trade Log{" "}
            <span className="normal-case font-normal text-slate-400 ml-1">
              ({trades.length} events)
            </span>
          </p>
          <TradeTable trades={trades} />
        </div>
      )}
    </div>
  );
}
