import { describe, expect, it, vi } from "vitest";
import { ALL_VIEW_IDS } from "@/lib/workspaceRegistry";
import { buildGlobeQuery, buildGlobeShareUrl, clearGlobeUrl, readGlobeParams, resolveMarketId, writeGlobeUrl } from "./permalink";

describe("existing globe-only permalink contract", () => {
  it("accepts the canonical globe workspace and round-trips its query", () => {
    expect(ALL_VIEW_IDS).toContain("globe");
    writeGlobeUrl({ market: "tw", tour: "macro & fx", presentation: true }, "replace");
    expect(readGlobeParams()).toEqual({ isGlobe: true, market: "tw", tour: "macro & fx", presentation: true });
    expect(buildGlobeShareUrl({ market: "tw" })).toContain("?view=globe&market=tw");
  });

  it.each(["unknown", "backtest", "internal-fixture", "Globe", ""])("does not promote %j into a general workspace deep link", (view) => {
    window.history.replaceState(null, "", `/?view=${view}`);
    expect(readGlobeParams().isGlobe).toBe(false);
    // page.tsx keeps initial Home state when isGlobe is false.
  });

  it("uses the exact existing unknown-market fallback", () => {
    expect(resolveMarketId(" TW ", ["us", "tw"])).toEqual({ id: "tw", notFound: false });
    expect(resolveMarketId("bad", ["tw", "us"])).toEqual({ id: "us", notFound: true });
    expect(resolveMarketId("bad", ["tw"])).toEqual({ id: "tw", notFound: true });
    expect(resolveMarketId("bad", [])).toEqual({ id: null, notFound: true });
  });

  it("uses History API without a page reload and clears globe-only state", () => {
    const push = vi.spyOn(history, "pushState");
    const replace = vi.spyOn(history, "replaceState");
    writeGlobeUrl({ market: "us" }, "push");
    expect(push).toHaveBeenCalledWith(null, "", "/?view=globe&market=us");
    clearGlobeUrl("replace");
    expect(replace).toHaveBeenCalledWith(null, "", "/");
    expect(readGlobeParams().isGlobe).toBe(false);
  });

  it("is safe without browser globals", () => {
    vi.stubGlobal("window", undefined);
    expect(readGlobeParams()).toEqual({ isGlobe: false, market: null, tour: null, presentation: false });
    expect(buildGlobeShareUrl({ market: "us" })).toBe(buildGlobeQuery({ market: "us" }));
    expect(() => writeGlobeUrl({ market: "us" }, "push")).not.toThrow();
    expect(() => clearGlobeUrl("push")).not.toThrow();
  });
});
