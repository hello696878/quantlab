"use client";

import { downloadTextFile, type Report } from "@/lib/reportExport";

/**
 * Small "Export Report" button.  The report is built lazily on click via
 * ``getReport`` (so large result sets aren't serialised on every render) and
 * downloaded as a local Markdown file.
 */
export default function ExportReportButton({
  getReport,
  label = "Export Report",
  className,
}: {
  getReport: () => Report;
  label?: string;
  className?: string;
}) {
  function handleClick() {
    const { filename, content } = getReport();
    downloadTextFile(filename, content);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      title="Download a Markdown research report"
      className={
        className ??
        "px-3 py-1 rounded-lg text-xs font-semibold text-slate-600 " +
          "border border-slate-300 hover:border-slate-400 transition-colors"
      }
    >
      {label}
    </button>
  );
}
