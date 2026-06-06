"use client";

import { useEffect, useState } from "react";
import {
  classifyApiError,
  deleteSavedBacktest,
  listSavedBacktests,
} from "@/lib/api";
import type { SavedBacktestSummary } from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";
import BackendOfflinePanel from "@/components/BackendOfflinePanel";

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

function strategyLabel(s: string): string {
  return STRATEGY_LABELS[s] ?? s;
}

function fmtDate(iso: string): string {
  // "2024-01-15T10:30:45.123456Z" → "2024-01-15 10:30"
  return iso.replace("T", " ").slice(0, 16);
}

function metricCell(
  value: number | null | undefined,
  formatter: (v: number) => string,
  positiveGreen = true,
): React.ReactNode {
  if (value == null) return <span className="text-slate-400">—</span>;
  const formatted = formatter(value);
  const color =
    value > 0
      ? positiveGreen
        ? "text-green-700"
        : "text-red-700"
      : value < 0
        ? positiveGreen
          ? "text-red-700"
          : "text-green-700"
        : "text-slate-500";
  return <span className={color}>{formatted}</span>;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface SavedBacktestsListProps {
  onSelect: (id: number) => void;
  refreshKey: number;
  onGoHome?: () => void;
}

export default function SavedBacktestsList({
  onSelect,
  refreshKey,
  onGoHome,
}: SavedBacktestsListProps) {
  const [rows, setRows] = useState<SavedBacktestSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    listSavedBacktests()
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [refreshKey, retryTick]);

  async function handleDelete(id: number, name: string) {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    setDeletingId(id);
    setDeleteError(null);
    try {
      await deleteSavedBacktest(id);
      setRows((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Delete failed. Please try again.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  // ── States ──────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="card p-8 text-center text-sm text-slate-500">
        Loading saved backtests…
      </div>
    );
  }

  if (error) {
    const cls = classifyApiError(error);
    if (cls.backendUnavailable) {
      return (
        <BackendOfflinePanel
          resource="saved backtests"
          capabilities="view, open, or delete"
          detail={cls.message}
          onRetry={() => setRetryTick((k) => k + 1)}
          onGoHome={onGoHome}
        />
      );
    }
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        ⚠ {cls.message}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="card p-10 text-center">
        <p className="text-slate-500 text-sm">No saved backtests yet.</p>
        <p className="text-slate-400 text-xs mt-1">
          Run a backtest and click{" "}
          <span className="font-medium text-slate-600">Save backtest</span> to
          store it here.
        </p>
      </div>
    );
  }

  // ── Table ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-3">
      {deleteError && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {deleteError}
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50 text-xs font-semibold text-slate-500 uppercase tracking-wide">
              <th className="px-4 py-3 text-left">Name</th>
              <th className="px-4 py-3 text-left">Ticker</th>
              <th className="px-4 py-3 text-left">Strategy</th>
              <th className="px-4 py-3 text-left">Dates</th>
              <th className="px-4 py-3 text-left">Saved</th>
              <th className="px-4 py-3 text-right">CAGR</th>
              <th className="px-4 py-3 text-right">Sharpe</th>
              <th className="px-4 py-3 text-right">Max DD</th>
              <th className="px-4 py-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-slate-50 hover:bg-slate-50 transition-colors"
              >
                <td className="px-4 py-3 font-medium text-slate-800 max-w-[200px] truncate">
                  {row.name}
                  {row.notes && (
                    <span
                      className="ml-1.5 text-slate-400 font-normal text-xs"
                      title={row.notes}
                    >
                      ✎
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 font-mono text-slate-700">
                  {row.ticker}
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {strategyLabel(row.strategy)}
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">
                  {row.start_date} → {row.end_date}
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                  {fmtDate(row.created_at)}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {metricCell(row.cagr, (v) => fmtPct(v, 1))}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {metricCell(row.sharpe_ratio, (v) => fmtRatio(v, 2))}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  {metricCell(
                    row.max_drawdown,
                    (v) => fmtPct(v, 1),
                    false /* negative = green for drawdown */,
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <button
                      type="button"
                      onClick={() => onSelect(row.id)}
                      className="text-xs px-2.5 py-1 rounded-md border border-blue-200
                                 text-blue-700 hover:bg-blue-50 transition-colors font-medium"
                    >
                      View
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(row.id, row.name)}
                      disabled={deletingId === row.id}
                      className="text-xs px-2.5 py-1 rounded-md border border-red-200
                                 text-red-600 hover:bg-red-50 transition-colors font-medium
                                 disabled:opacity-50"
                    >
                      {deletingId === row.id ? "…" : "Delete"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
          </table>
        </div>
        <div className="px-4 py-2 text-xs text-slate-400 border-t border-slate-50">
          {rows.length} saved {rows.length === 1 ? "backtest" : "backtests"}
        </div>
      </div>
    </div>
  );
}
