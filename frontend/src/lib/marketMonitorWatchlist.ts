export const MONITOR_WATCHLIST_KEY = "quantlab.monitor.watchlist.v1";
export const MAX_WATCHLIST = 16;
export function parseWatchlist(raw: string, allowed: readonly string[]): string[] {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid watchlist");
  const record = value as Record<string, unknown>;
  if (Object.keys(record).sort().join(",") !== "ids,version" || record.version !== 1 || !Array.isArray(record.ids)
    || record.ids.length > MAX_WATCHLIST || new Set(record.ids).size !== record.ids.length
    || record.ids.some((id) => typeof id !== "string" || !allowed.includes(id))) throw new Error("Invalid watchlist");
  return [...record.ids] as string[];
}
export function loadWatchlist(storage: Pick<Storage, "getItem">, allowed: readonly string[], defaults: readonly string[]) {
  try {
    const raw = storage.getItem(MONITOR_WATCHLIST_KEY);
    return { ids: raw === null ? [...defaults] : parseWatchlist(raw, allowed), warning: null };
  } catch { return { ids: [...defaults], warning: "Saved watchlist could not be loaded. Preferences are kept in memory until you make a change." }; }
}
export function saveWatchlist(storage: Pick<Storage, "setItem">, ids: string[]) {
  try { storage.setItem(MONITOR_WATCHLIST_KEY, JSON.stringify({ version: 1, ids })); return null; }
  catch { return "Watchlist updated for this visit, but browser storage is unavailable or full."; }
}
