// ---------------------------------------------------------------------------
// Lightweight client-side search for the command palette.
//
// No external dependency: simple case-insensitive token matching against a
// pre-lowercased "haystack" string built per item.  Every search token must be
// present (AND semantics).  Items keep their original (grouped) order so the
// palette can render contiguous category headers.
// ---------------------------------------------------------------------------

export interface SearchableItem {
  /** Stable unique id (also the React key). */
  id: string;
  /** Category header this item is listed under. */
  group: string;
  /** Primary line. */
  title: string;
  /** Optional secondary line (e.g. ticker · strategy · metrics). */
  subtitle?: string;
  /** Optional right-aligned tag (e.g. "saved", "gallery"). */
  hint?: string;
  /** Pre-lowercased text matched against the query (never displayed). */
  haystack: string;
  /** Action to run.  Must be safe: navigate / prefill only — never auto-run. */
  run: () => void;
}

/** Split a raw query into lowercased, non-empty tokens. */
export function tokenize(query: string): string[] {
  return query.toLowerCase().split(/\s+/).filter(Boolean);
}

/** True when every token is a substring of the item's haystack. */
export function matchesItem(item: SearchableItem, tokens: string[]): boolean {
  if (tokens.length === 0) return true;
  return tokens.every((t) => item.haystack.includes(t));
}

/** Filter items by a raw query string, preserving input order. */
export function searchItems(
  items: SearchableItem[],
  query: string,
): SearchableItem[] {
  const tokens = tokenize(query);
  if (tokens.length === 0) return items;
  return items.filter((it) => matchesItem(it, tokens));
}

/**
 * Build a lowercased search haystack from arbitrary parts.  Null / undefined /
 * empty parts are skipped, so records with missing optional fields are safe.
 */
export function buildHaystack(
  ...parts: Array<string | number | null | undefined>
): string {
  return parts
    .filter((p): p is string | number => p != null && p !== "")
    .map((p) => String(p).toLowerCase())
    .join(" ");
}
