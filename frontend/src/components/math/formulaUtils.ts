/**
 * Helpers for the shared formula reference system (Phase 25.1).
 *
 * `buildFormulaLatexText` produces a clean, grouped, copyable **LaTeX source**
 * string (never rendered HTML) for the "Copy LaTeX" button.
 */

import type { FormulaGroup } from "@/components/math/formulaTypes";

/**
 * Build a plain-text, grouped LaTeX dump suitable for copying to the clipboard.
 * Groups are separated by a horizontal rule; each row is `label:` then its LaTeX
 * on the next line. An optional leading title is prepended.
 */
export function buildFormulaLatexText(groups: FormulaGroup[], title?: string): string {
  const body = groups
    .map((group) => {
      const rows = group.formulas
        .map((f) => `${f.label}:\n${f.latex}`)
        .join("\n\n");
      const head = group.description ? `${group.title}\n${group.description}` : group.title;
      return `${head}\n\n${rows}`;
    })
    .join("\n\n---\n\n");
  return title ? `${title}\n\n${body}` : body;
}
