"use client";

/**
 * SafeMath — render a LaTeX string with KaTeX **locally** (no CDN, no MathJax,
 * no remote render API), with a hard guarantee that a malformed formula can
 * never crash the page.
 *
 * `katex.renderToString` is called with `throwOnError: false` and wrapped in a
 * try/catch; on any failure it falls back to a styled raw-LaTeX code block and
 * leaves the rest of the page fully usable. Long equations scroll horizontally
 * inside their own container (see the `.ql-math` rules in globals.css), so they
 * never cause full-page horizontal overflow.
 */

import katex from "katex";

export interface SafeMathProps {
  latex: string;
  /** Display (block) math when true (default); inline when false. */
  displayMode?: boolean;
}

export default function SafeMath({ latex, displayMode = true }: SafeMathProps) {
  let html: string | null = null;
  try {
    html = katex.renderToString(latex, {
      displayMode,
      throwOnError: false,
    });
  } catch {
    html = null;
  }

  if (html) {
    return (
      <div
        className="ql-math"
        style={{ color: "var(--text-hi)" }}
        // KaTeX output is generated locally from our own static LaTeX strings.
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }

  // Fallback: show the raw LaTeX in a readable, horizontally-scrollable block.
  return (
    <code
      className="mono block overflow-x-auto rounded px-2 py-1 text-[12px]"
      style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
    >
      {latex}
    </code>
  );
}
