"use client";

/**
 * FormulaReference — QuantLab's shared, reusable LaTeX formula reference block
 * (Phase 25.1). Renders grouped formulas as locally-rendered KaTeX (no CDN, no
 * MathJax, no remote script) with a built-in "Copy LaTeX" button that copies the
 * clean grouped LaTeX **source** (not rendered HTML).
 *
 * Designed to live inside an existing card (it does not render its own card
 * wrapper), so each lab keeps its surrounding notes / limitations. Long
 * equations scroll horizontally inside their own row (`.ql-math` in globals.css)
 * and never cause full-page horizontal overflow.
 *
 * Premium quant-terminal look, dark-mode readable, mobile responsive, accessible
 * headings, and a focus-visible, labelled copy button.
 */

import { useState } from "react";
import SafeMath from "@/components/math/SafeMath";
import { buildFormulaLatexText } from "@/components/math/formulaUtils";
import type { FormulaReferenceProps, FormulaRow as FormulaRowType } from "@/components/math/formulaTypes";

function FormulaRow({ item }: { item: FormulaRowType }) {
  return (
    <div
      className="rounded-lg px-3 py-2"
      style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
    >
      <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
        {item.label}
      </p>
      <div className="mt-0.5">
        <SafeMath latex={item.latex} displayMode={item.displayMode ?? true} />
      </div>
      {item.note && (
        <p className="text-[11px]" style={{ color: "var(--text-mut)" }}>
          {item.note}
        </p>
      )}
    </div>
  );
}

export default function FormulaReference({
  title,
  subtitle,
  groups,
  disclaimer,
  copyable = true,
  columns = 2,
}: FormulaReferenceProps) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);

  async function copyFormulas() {
    setCopyFailed(false);
    const text = buildFormulaLatexText(groups, title);
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2500);
        return;
      }
    } catch {
      // fall through to the failure state
    }
    setCopyFailed(true);
    window.setTimeout(() => setCopyFailed(false), 3000);
  }

  const gridCols = columns === 1 ? "grid-cols-1" : "grid-cols-1 lg:grid-cols-2";

  return (
    <div>
      {(title || copyable) && (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            {title && <p className="section-title">{title}</p>}
            {subtitle && (
              <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
                {subtitle}
              </p>
            )}
          </div>
          {copyable && (
            <div className="flex items-center gap-2">
              {copied && (
                <span role="status" aria-live="polite" className="text-[11px]" style={{ color: "var(--accent-text)" }}>
                  Copied LaTeX formulas.
                </span>
              )}
              {copyFailed && (
                <span role="status" aria-live="polite" className="text-[11px]" style={{ color: "var(--warn)" }}>
                  Could not copy formulas automatically.
                </span>
              )}
              <button
                type="button"
                onClick={copyFormulas}
                aria-label="Copy the LaTeX formula reference"
                className="rounded-md px-2.5 py-1 text-xs font-semibold transition-colors"
                style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
              >
                {copied ? "Copied ✓" : "📋 Copy LaTeX"}
              </button>
            </div>
          )}
        </div>
      )}

      <div className={`grid gap-4 ${gridCols}`}>
        {groups.map((group) => (
          <section key={group.title} aria-label={group.title}>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
              {group.title}
            </p>
            {group.description && (
              <p className="mb-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                {group.description}
              </p>
            )}
            <div className="space-y-2">
              {group.formulas.map((item) => (
                <FormulaRow key={item.label} item={item} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {disclaimer && (
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {disclaimer}
        </p>
      )}
    </div>
  );
}
