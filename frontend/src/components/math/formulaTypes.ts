/**
 * Shared types for QuantLab's LaTeX formula reference system (Phase 25.1).
 *
 * Used by every lab's "Formulas & notes" section so that formulas render as
 * locally-rendered KaTeX (no CDN, no MathJax, no remote script) instead of raw
 * monospaced text. See `FormulaReference` + `SafeMath`.
 */

/** A single rendered formula row. */
export interface FormulaRow {
  /** Short human label shown above the equation. */
  label: string;
  /** KaTeX LaTeX source (no surrounding $…$). */
  latex: string;
  /** Optional one-line explanation shown beneath the equation. */
  note?: string;
  /** Display math (block) when true (default); inline when false. */
  displayMode?: boolean;
}

/** A titled group of related formulas. */
export interface FormulaGroup {
  title: string;
  description?: string;
  formulas: FormulaRow[];
}

/** Props for the shared `FormulaReference` component. */
export interface FormulaReferenceProps {
  /** Optional section heading (rendered as a `section-title`). */
  title?: string;
  /** Optional sub-heading beneath the title. */
  subtitle?: string;
  /** The grouped formulas to render. */
  groups: FormulaGroup[];
  /** Optional disclaimer rendered at the bottom of the block. */
  disclaimer?: string;
  /** Show the "Copy LaTeX" button (default true). */
  copyable?: boolean;
  /** Number of responsive columns for groups (default 2). */
  columns?: 1 | 2;
}
