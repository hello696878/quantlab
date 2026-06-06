"use client";

import { useState } from "react";
import {
  downloadTextFile,
  REPORT_TEMPLATES,
  type Report,
  type ReportTemplate,
} from "@/lib/reportExport";
import PrintableReportModal from "@/components/PrintableReportModal";
import SaveReportModal from "@/components/SaveReportModal";
import { loadSettings } from "@/lib/settings";
import { markChecklistStep } from "@/lib/onboarding";

/**
 * Report export controls shown wherever results are displayed.
 *
 * A template selector chooses the branded layout (Standard / Executive Summary
 * / Quant Tear Sheet / Risk Report); the selection applies to all three
 * actions:
 *  - "Export Report" — downloads the report as a local Markdown (`.md`) file.
 *  - "Export PDF"    — opens a print-friendly preview modal (Save as PDF).
 *  - "Save Report"   — saves the Markdown report to the local Report Gallery.
 *
 * The report is built lazily on click via `getReport(template)` so large result
 * sets are not serialised on every render.  `templates` restricts the offered
 * layouts for analyses that cannot meaningfully fill a given template.
 */
export default function ExportReportButton({
  getReport,
  label = "Export Report",
  pdfLabel = "Export PDF",
  saveLabel = "Save Report",
  showPdf = true,
  showSave = true,
  templates,
  className,
}: {
  getReport: (template: ReportTemplate) => Report;
  label?: string;
  pdfLabel?: string;
  saveLabel?: string;
  showPdf?: boolean;
  showSave?: boolean;
  templates?: ReportTemplate[];
  className?: string;
}) {
  const options =
    templates && templates.length
      ? REPORT_TEMPLATES.filter((t) => templates.includes(t.id))
      : REPORT_TEMPLATES;

  const [template, setTemplate] = useState<ReportTemplate>(() => {
    const preferred = loadSettings().default_report_template;
    return options.some((o) => o.id === preferred)
      ? preferred
      : options[0]?.id ?? "standard";
  });
  const [preview, setPreview] = useState<Report | null>(null);
  const [toSave, setToSave] = useState<Report | null>(null);

  const btnCls =
    className ??
    "px-3 py-1 rounded-lg text-xs font-semibold text-slate-600 " +
      "border border-slate-300 hover:border-slate-400 transition-colors";

  const selCls =
    "px-2 py-1 rounded-lg text-xs font-semibold text-slate-700 bg-white " +
    "border border-slate-300 hover:border-slate-400 transition-colors " +
    "focus:outline-none focus:ring-2 focus:ring-blue-500";

  function handleMarkdown() {
    const { filename, content } = getReport(template);
    downloadTextFile(filename, content);
    markChecklistStep("exported_report");
  }

  return (
    <>
      <span className="inline-flex items-center gap-2">
        {options.length > 1 && (
          <select
            value={template}
            onChange={(e) => setTemplate(e.target.value as ReportTemplate)}
            title="Report template"
            aria-label="Report template"
            className={selCls}
          >
            {options.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        )}
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
            onClick={() => {
              setPreview(getReport(template));
              markChecklistStep("exported_report");
            }}
            title="Preview a printable report, then save as PDF"
            className={btnCls}
          >
            {pdfLabel}
          </button>
        )}
        {showSave && (
          <button
            type="button"
            onClick={() => setToSave(getReport(template))}
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
