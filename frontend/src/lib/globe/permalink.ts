/**
 * Global Markets Globe — dossier permalink helpers (Phase 20.6).
 *
 * QuantLab is a single-page workspace switcher (one Next.js route at `/` whose
 * visible workspace is React `view` state), so a shareable country-dossier link
 * is encoded as query params on the existing page:
 *
 *     /?view=globe&market=tw
 *
 * The convenience path `/globe?market=tw` is also accepted — a thin redirect
 * route (`app/globe/page.tsx`) normalises it to the canonical query form above.
 *
 * These helpers centralise the read/write of that URL state so the page and the
 * globe panel stay consistent. They are all browser-only (guarded for SSR) and
 * never trigger a full page reload — they use the History API directly.
 */

/** Param value that selects the Global Markets Globe workspace. */
export const GLOBE_VIEW = "globe";

/** Default market when a permalink omits or names an unknown market. */
export const DEFAULT_MARKET_ID = "us";

/** Build the canonical query string for a globe permalink (no origin/path). */
export function buildGlobeQuery(marketId: string | null | undefined): string {
  return marketId
    ? `?view=${GLOBE_VIEW}&market=${encodeURIComponent(marketId)}`
    : `?view=${GLOBE_VIEW}`;
}

/**
 * Update the address bar to the globe permalink for `marketId` without a page
 * reload. `push` adds a history entry (user navigations); `replace` rewrites the
 * current entry (normalisation, deep-link entry, invalid-id fallback).
 */
export function writeGlobeUrl(
  marketId: string | null | undefined,
  mode: "push" | "replace",
): void {
  if (typeof window === "undefined") return;
  const url = window.location.pathname + buildGlobeQuery(marketId);
  if (mode === "push") window.history.pushState(null, "", url);
  else window.history.replaceState(null, "", url);
}

/** Drop all globe query params (used when navigating away from the globe). */
export function clearGlobeUrl(mode: "push" | "replace"): void {
  if (typeof window === "undefined") return;
  const url = window.location.pathname;
  if (mode === "push") window.history.pushState(null, "", url);
  else window.history.replaceState(null, "", url);
}

/** Absolute, shareable permalink for a market dossier (origin + path + query). */
export function buildGlobeShareUrl(marketId: string): string {
  if (typeof window === "undefined") return buildGlobeQuery(marketId);
  const { origin, pathname } = window.location;
  return `${origin}${pathname}${buildGlobeQuery(marketId)}`;
}

/** Read the current globe URL state from `window.location.search`. */
export function readGlobeParams(): { isGlobe: boolean; market: string | null } {
  if (typeof window === "undefined") return { isGlobe: false, market: null };
  const params = new URLSearchParams(window.location.search);
  const market = params.get("market");
  return {
    isGlobe: params.get("view") === GLOBE_VIEW,
    market: market && market.trim() ? market.trim() : null,
  };
}

/**
 * Resolve a requested market id against the set of known ids. Matching is
 * case-insensitive and the canonical (known) id is returned, so a link like
 * `?market=TW` selects Taiwan and normalises to `?market=tw`.
 *  - empty / null request → no selection (`{ id: null, notFound: false }`)
 *  - known id             → that id (canonical casing)
 *  - unknown id           → the default market, flagged `notFound` so the UI can
 *                           show "Market not found; showing default market."
 */
export function resolveMarketId(
  requestedId: string | null | undefined,
  knownIds: readonly string[],
): { id: string | null; notFound: boolean } {
  const normalized = requestedId?.trim().toLowerCase();
  if (!normalized) return { id: null, notFound: false };
  const match = knownIds.find((known) => known.toLowerCase() === normalized);
  if (match) return { id: match, notFound: false };
  const fallback = knownIds.includes(DEFAULT_MARKET_ID)
    ? DEFAULT_MARKET_ID
    : knownIds[0] ?? null;
  return { id: fallback, notFound: true };
}
