"use client";

import { useEffect, useMemo, useState } from "react";
import { deleteSavedReport, getSavedReport } from "@/lib/api";
import type { SavedReportFull } from "@/lib/types";
import { markdownToHtml } from "@/lib/printReport";
import { downloadTextFile, type Report } from "@/lib/reportExport";
import PrintableReportModal from "@/components/PrintableReportModal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SOURCE_LABELS: Record<string, string> = {
  backtest: "Backtest",
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
  return iso.replace("T", " ").slice(0, 16) + " UTC";
}

function filenameFor(record: SavedReportFull): string {
  const base =
    record.title.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(
      /^-+|-+$/g,
      "",
    ) || "report";
  return `quantlab-report-${base}.md`;
}

/** Turn a saved record into the lightweight Report the print modal expects. */
function toReport(record: SavedReportFull): Report {
  return { filename: filenameFor(record), content: record.markdown_content };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface SavedReportDetailProps {
  id: number;
  onBack: () => void;
  onDeleted: () => void;
}

export default function SavedReportDetail({
  id,
  onBack,
  onDeleted,
}: SavedReportDetailProps) {
  const [record, setRecord] = useState<SavedReportFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPrint, setShowPrint] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRecord(null);

    getSavedReport(id)
      .then((data) => {
        if (!cancelled) setRecord(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Failed to load saved report.",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  // `markdownToHtml` fully HTML-escapes every piece of report text before
  // emitting its own fixed tag grammar, so embedded HTML/script in the saved
  // Markdown is rendered as inert text and never executed.  This makes the
  // string safe to inject below.
  const html = useMemo(
    () => (record ? markdownToHtml(record.markdown_content) : ""),
    [record],
  );

  async function handleDelete() {
    if (!record || deleting) return;
    if (!confirm(`Delete "${record.title}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteSavedReport(record.id);
      onDeleted();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Delete failed. Please try again.",
      );
      setDeleting(false);
    }
  }

  // ── States ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="card p-8 text-center text-sm text-slate-500">Loading…</div>
    );
  }

  if (error && !record) {
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

  const tickers = record.tickers.length > 0 ? record.tickers.join(", ") : "—";
  const dates =
    record.date_range_start && record.date_range_end
      ? `${record.date_range_start} → ${record.date_range_end}`
      : "—";

  return (
    <div className="space-y-6">
      {/* Back link */}
      <button
        type="button"
        onClick={onBack}
        className="text-sm text-blue-600 hover:underline"
      >
        ← Back to saved reports
      </button>

      {/* Header */}
      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{record.title}</h2>
            <p className="mt-0.5 text-sm text-slate-500">
              {sourceLabel(record.source_type)}
              {record.strategy ? ` · ${record.strategy}` : ""} · {tickers}
            </p>
            <p className="mt-0.5 text-xs text-slate-400">
              {dates} · saved {fmtDate(record.created_at)}
              {record.updated_at !== record.created_at && (
                <> · updated {fmtDate(record.updated_at)}</>
              )}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => downloadTextFile(filenameFor(record), record.markdown_content)}
              className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold
                         text-slate-600 transition-colors hover:border-slate-400"
            >
              Download Markdown
            </button>
            <button
              type="button"
              onClick={() => setShowPrint(true)}
              className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-semibold
                         text-slate-600 transition-colors hover:border-slate-400"
            >
              Print / Save as PDF
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-lg border border-red-200 px-3 py-1 text-xs font-semibold
                         text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
            >
              {deleting ? "Deleting…" : "Delete"}
            </button>
          </div>
        </div>

        {record.notes && (
          <div className="mt-3 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-slate-600">
            {record.notes}
          </div>
        )}

        {error && (
          <p className="mt-3 rounded bg-red-50 px-2 py-1 text-xs text-red-600">
            {error}
          </p>
        )}
      </div>

      {/* Rendered report (safe: content is HTML-escaped by markdownToHtml) */}
      <div className="report-surface">
        <div
          className="report-html"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>

      {showPrint && (
        <PrintableReportModal
          report={toReport(record)}
          onClose={() => setShowPrint(false)}
        />
      )}
    </div>
  );
}
