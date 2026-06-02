"use client";

import { useState } from "react";
import { downloadTextFile, type Report } from "@/lib/reportExport";
import PrintableReportModal from "@/components/PrintableReportModal";
import SaveReportModal from "@/components/SaveReportModal";

/**
 * Report export controls shown wherever results are displayed.
 *
 * Renders three small buttons:
 *  - "Export Report" — downloads the report as a local Markdown (`.md`) file.
 *  - "Export PDF"    — opens a print-friendly preview modal; the user prints it
 *                      or chooses "Save as PDF" from the browser dialog.
 *  - "Save Report"   — saves the Markdown report to the local Report Gallery
 *                      (SQLite) so it can be reopened, downloaded, or re-printed
 *                      later from the Saved Reports workspace.
 *
 * The report is built lazily on click via `getReport` so large result sets are
 * not serialised on every render.
 */
export default function ExportReportButton({
  getReport,
  label = "Export Report",
  pdfLabel = "Export PDF",
  saveLabel = "Save Report",
  showPdf = true,
  showSave = true,
  className,
}: {
  getReport: () => Report;
  label?: string;
  pdfLabel?: string;
  saveLabel?: string;
  showPdf?: boolean;
  showSave?: boolean;
  className?: string;
}) {
  const [preview, setPreview] = useState<Report | null>(null);
  const [toSave, setToSave] = useState<Report | null>(null);

  const btnCls =
    className ??
    "px-3 py-1 rounded-lg text-xs font-semibold text-slate-600 " +
      "border border-slate-300 hover:border-slate-400 transition-colors";

  function handleMarkdown() {
    const { filename, content } = getReport();
    downloadTextFile(filename, content);
  }

  return (
    <>
      <span className="inline-flex items-center gap-2">
        <button
          type="button"
          onClick={handleMarkdown}
          title="Download a Markdown research report"
          className={btnCls}
        >
          {label}
        </button>
        {showPdf && (
          <button
            type="button"
            onClick={() => setPreview(getReport())}
            title="Preview a printable report, then save as PDF"
            className={btnCls}
          >
            {pdfLabel}
          </button>
        )}
        {showSave && (
          <button
            type="button"
            onClick={() => setToSave(getReport())}
            title="Save this report to the local Report Gallery"
            className={btnCls}
          >
            {saveLabel}
          </button>
        )}
      </span>

      {preview && (
        <PrintableReportModal
          report={preview}
          onClose={() => setPreview(null)}
        />
      )}

      {toSave && (
        <SaveReportModal report={toSave} onClose={() => setToSave(null)} />
      )}
    </>
  );
}
