import { expect, it, vi } from "vitest";
import { loadWatchlist, MAX_WATCHLIST, MONITOR_WATCHLIST_KEY, parseWatchlist, saveWatchlist } from "./marketMonitorWatchlist";

it("preserves an explicitly empty list and never writes defaults on load", () => {
  const storage = { getItem: vi.fn(() => JSON.stringify({ version: 1, ids: [] })), setItem: vi.fn() };
  expect(loadWatchlist(storage, ["nvda"], ["nvda"]).ids).toEqual([]);
  expect(storage.setItem).not.toHaveBeenCalled();
});
it.each(["not JSON", "null", "[]", '{"version":2,"ids":[]}', '{"version":1,"ids":["bad"]}', '{"version":1,"ids":["nvda","nvda"]}', '{"version":1,"ids":null}', '{"version":1,"ids":[],"key":"secret"}'])("refuses malformed stored data %s", (raw) => {
  expect(() => parseWatchlist(raw, ["nvda"])).toThrow();
  expect(loadWatchlist({ getItem: () => raw }, ["nvda"], ["nvda"])).toMatchObject({ ids: ["nvda"], warning: expect.any(String) });
});
it("bounds lists and handles unavailable/quota-limited storage without losing in-memory choices", () => {
  const ids = Array.from({ length: MAX_WATCHLIST + 1 }, (_, i) => String(i));
  expect(() => parseWatchlist(JSON.stringify({ version: 1, ids }), ids)).toThrow();
  expect(loadWatchlist({ getItem: () => { throw new Error("denied"); } }, ["nvda"], ["nvda"]).ids).toEqual(["nvda"]);
  expect(saveWatchlist({ setItem: () => { throw new Error("quota"); } }, [])).toMatch(/this visit/);
});
it("writes only the Monitor preference key and minimal versioned shape", () => {
  const storage = { setItem: vi.fn() };
  expect(saveWatchlist(storage, ["nvda"])).toBeNull();
  expect(storage.setItem).toHaveBeenCalledExactlyOnceWith(MONITOR_WATCHLIST_KEY, '{"version":1,"ids":["nvda"]}');
});
