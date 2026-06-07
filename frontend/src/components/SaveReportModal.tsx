"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { classifyApiError, createSavedReport } from "@/lib/api";
import type { Report } from "@/lib/reportExport";
import type { SavedReportCreate } from "@/lib/types";
import { notifyBackendOffline, toast } from "@/lib/toast";

/**
 * Small modal that saves a generated report to the local Report Gallery.
 *
 * Only the title and notes are editable; the report's source metadata
 * (`sourceType`, tickers, strategy, date range, structured metadata) is carried
 * on the `Report` object built by the report generators and is mapped straight
 * onto the `SavedReportCreate` payload.  The full Markdown text is sent as
 * `markdown_content`.  No PDF binary is ever uploaded or stored.
 */

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm " +
  "text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none " +
  "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

function defaultTitle(report: Report): string {
  if (report.title && report.title.trim()) return report.title.trim();
  return report.filename.replace(/\.md$/i, "");
}

export default function SaveReportModal({
  report,
  onClose,
  onSaved,
}: {
  report: Report;
  onClose: () => void;
  onSaved?: (id: number) => void;
}) {
  const [mounted, setMounted] = useState(false);
  const [title, setTitle] = useState(defaultTitle(report));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const titleOk = title.trim().length > 0;

  async function handleSave() {
    if (!titleOk || saving) return;
    setSaving(true);
    setError(null);

    const payload: SavedReportCreate = {
      title: title.trim(),
      report_type: report.reportType ?? "markdown",
      source_type: report.sourceType ?? "manual",
      source_id: report.sourceId ?? null,
      tickers: report.tickers ?? [],
      strategy: report.strategy ?? null,
      date_range_start: report.dateRangeStart ?? null,
      date_range_end: report.dateRangeEnd ?? null,
      markdown_content: report.content,
      metadata: report.metadata ?? {},
      notes: notes.trim(),
    };

    try {
      const saved = await createSavedReport(payload);
      toast.success("Report saved", "Stored locally in the Report Gallery.");
      setSavedId(saved.id);
      onSaved?.(saved.id);
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Save failed", cls.message);
      setError(cls.message);
      setSaving(false);
    }
  }

  if (!mounted) return null;

  const node = (
    <div
      className="fixed inset-0 z-[120] flex items-start justify-center overflow-y-auto p-4 sm:p-8"
      style={{ background: "rgba(2,4,10,0.72)", backdropFilter: "blur(2px)" }}
      role="dialog"
      aria-modal="true"
      aria-label="Save report to gallery"
      onClick={onClose}
    >
      <div
        className="card my-auto w-full max-w-md p-5"
        onClick={(e) => e.stopPropagation()}
      >
        {savedId === null ? (
          <>
            <h3 className="text-base font-bold text-slate-100">
              Save to Report Gallery
            </h3>
            <p className="mt-1 text-xs text-slate-400">
              Stores the Markdown report locally in SQLite. PDF files are not
              stored — re-print to PDF any time from Saved Reports.
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-slate-300">
                  Title <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. SPY SMA Crossover — research note"
                  className={inputCls}
                  disabled={saving}
                />
                {!titleOk && (
                  <p className="mt-1 text-xs text-red-400">
                    Title cannot be empty.
                  </p>
                )}
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-slate-300">
                  Notes{" "}
                  <span className="font-normal text-slate-500">(optional)</span>
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  placeholder="Observations, hypotheses, follow-up ideas…"
                  className={inputCls + " resize-none"}
                  disabled={saving}
                />
              </div>

              <div className="flex flex-wrap gap-1.5 text-[11px] text-slate-400">
                <span className="rounded-full bg-slate-100 px-2 py-0.5">
                  {report.sourceType ?? "manual"}
                </span>
                {report.tickers && report.tickers.length > 0 && (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono">
                    {report.tickers.join(", ")}
                  </span>
                )}
                {report.dateRangeStart && report.dateRangeEnd && (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5">
                    {report.dateRangeStart} → {report.dateRangeEnd}
                  </span>
                )}
              </div>

              {error && (
                <p className="rounded bg-red-50 px-2 py-1 text-xs text-red-600">
                  {error}
                </p>
              )}

              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={saving}
                  className="rounded-lg border border-slate-300 px-4 py-1.5 text-sm
                             font-medium text-slate-600 transition-colors
                             hover:border-slate-400 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={!titleOk || saving}
                  className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-semibold
                             text-white transition-colors hover:bg-blue-700
                             disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save report"}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="py-2 text-center">
            <p className="text-sm font-semibold text-slate-100">Report saved ✓</p>
            <p className="mt-1 text-xs text-slate-400">
              Find it in the{" "}
              <span className="font-medium text-slate-200">Saved Reports</span>{" "}
              workspace.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-semibold
                         text-white transition-colors hover:bg-blue-700"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(node, document.body);
}
