"use client";

import { useEffect, useState } from "react";
import {
  classifyApiError,
  deleteSavedReport,
  listSavedReports,
} from "@/lib/api";
import type { SavedReportSummary } from "@/lib/types";
import { notifyBackendOffline, toast } from "@/lib/toast";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SOURCE_LABELS: Record<string, string> = {
  backtest: "Backtest",
  csv_backtest: "CSV Backtest",
  custom_strategy: "Custom Strategy",
  portfolio_backtest: "Portfolio Backtest",
  portfolio_optimization: "Optimization",
  risk_dashboard: "Risk Dashboard",
  stress_test: "Stress Test",
  factor_analysis: "Factor Analysis",
  manual: "Manual",
};

function sourceLabel(s: string): string {
  return SOURCE_LABELS[s] ?? s;
}

function fmtDate(iso: string): string {
  return iso.replace("T", " ").slice(0, 16);
}

function dateRange(row: SavedReportSummary): string {
  if (row.date_range_start && row.date_range_end) {
    return `${row.date_range_start} → ${row.date_range_end}`;
  }
  return "—";
}

function tickerLabel(tickers: unknown): string {
  return Array.isArray(tickers) && tickers.length > 0
    ? tickers.join(", ")
    : "—";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface SavedReportsListProps {
  onSelect: (id: number) => void;
  refreshKey: number;
  onGoHome?: () => void;
  /** Navigate to the Backtest workspace (empty-state action). */
  onRunBacktest?: () => void;
}

export default function SavedReportsList({
  onSelect,
  refreshKey,
  onGoHome,
  onRunBacktest,
}: SavedReportsListProps) {
  const [rows, setRows] = useState<SavedReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    listSavedReports()
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err);
        if (classifyApiError(err).backendUnavailable) {
          notifyBackendOffline({ onRetry: () => setRetryTick((k) => k + 1) });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [refreshKey, retryTick]);

  async function handleDelete(id: number, title: string) {
    if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;
    setDeletingId(id);
    setDeleteError(null);
    try {
      await deleteSavedReport(id);
      setRows((prev) => prev.filter((r) => r.id !== id));
      toast.success("Report deleted", `"${title}" removed.`);
    } catch (err) {
      const cls = classifyApiError(err);
      setDeleteError(cls.message);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Delete failed", cls.message);
    } finally {
      setDeletingId(null);
    }
  }

  // ── States ────────────────────────────────────────────────────────────────

  if (loading) {
    return <SkeletonTable rows={5} cols={6} caption="Loading saved reports…" />;
  }

  if (error) {
    const cls = classifyApiError(error);
    if (cls.backendUnavailable) {
      return (
        <OfflineState
          detail={cls.message}
          onRetry={() => setRetryTick((k) => k + 1)}
          onGoHome={onGoHome}
        />
      );
    }
    return (
      <ErrorState
        title="Couldn’t load saved reports"
        message={cls.message}
        onRetry={() => setRetryTick((k) => k + 1)}
      />
    );
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        title="No saved reports yet"
        description="Export or save a research report to see it here."
        actions={
          onRunBacktest
            ? [{ label: "Run a Backtest", onClick: onRunBacktest }]
            : undefined
        }
      />
    );
  }

  // ── Table ─────────────────────────────────────────────────────────────────

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
              <tr className="border-b border-slate-100 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3 text-left">Title</th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Tickers</th>
                <th className="px-4 py-3 text-left">Dates</th>
                <th className="px-4 py-3 text-left">Saved</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-slate-50 transition-colors hover:bg-slate-50"
                >
                  <td className="max-w-[220px] truncate px-4 py-3 font-medium text-slate-800">
                    {row.title}
                    {row.notes && (
                      <span
                        className="ml-1.5 text-xs font-normal text-slate-400"
                        title={row.notes}
                      >
                        ✎
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {sourceLabel(row.source_type)}
                  </td>
                  <td className="max-w-[180px] truncate px-4 py-3 font-mono text-slate-700">
                    {tickerLabel(row.tickers)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                    {dateRange(row)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-400">
                    {fmtDate(row.created_at)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        type="button"
                        onClick={() => onSelect(row.id)}
                        className="rounded-md border border-blue-200 px-2.5 py-1 text-xs
                                   font-medium text-blue-700 transition-colors hover:bg-blue-50"
                      >
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(row.id, row.title)}
                        disabled={deletingId === row.id}
                        className="rounded-md border border-red-200 px-2.5 py-1 text-xs
                                   font-medium text-red-600 transition-colors hover:bg-red-50
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
        <div className="border-t border-slate-50 px-4 py-2 text-xs text-slate-400">
          {rows.length} saved {rows.length === 1 ? "report" : "reports"}
        </div>
      </div>
    </div>
  );
}
