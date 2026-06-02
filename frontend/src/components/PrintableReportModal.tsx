"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { markdownToHtml } from "@/lib/printReport";
import type { Report } from "@/lib/reportExport";

/**
 * Full-screen preview of a research report rendered as clean, print-friendly
 * HTML.  The user reviews it and clicks "Print / Save as PDF", which calls
 * `window.print()`.  Print styling (white background, hidden app chrome, page
 * breaks) lives in `globals.css` under `@media print`.
 *
 * The modal is portalled to `document.body` so its `print-portal-root` marker
 * is a direct child of `<body>` — the print rules hide every other body child,
 * leaving only the report on the page.
 */
export default function PrintableReportModal({
  report,
  onClose,
}: {
  report: Report;
  onClose: () => void;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  if (!mounted) return null;

  const html = markdownToHtml(report.content);
  const handlePrint = () => {
    if (typeof window !== "undefined") window.print();
  };

  const node = (
    <div
      className="print-portal-root print-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Research report preview"
      onClick={onClose}
    >
      <div className="print-modal" onClick={(e) => e.stopPropagation()}>
        <div className="print-toolbar no-print">
          <span className="print-toolbar-title">Research report preview</span>
          <div className="print-toolbar-actions">
            <button
              type="button"
              className="print-btn print-btn-primary"
              onClick={handlePrint}
            >
              Print / Save as PDF
            </button>
            <button
              type="button"
              className="print-btn print-btn-ghost"
              onClick={onClose}
            >
              Close
            </button>
          </div>
        </div>

        <div
          className="print-report-root report-html"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </div>
    </div>
  );

  return createPortal(node, document.body);
}
