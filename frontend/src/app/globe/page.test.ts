import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";
import GlobeRedirect, { dynamic } from "./page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(() => { throw new Error("NEXT_REDIRECT"); }),
}));

describe("globe convenience route", () => {
  it("waits for Next's asynchronous query before redirecting", async () => {
    let resolveQuery!: (query: { market: string }) => void;
    const searchParams = new Promise<{ market: string }>((resolve) => { resolveQuery = resolve; });
    const result = GlobeRedirect({ searchParams });
    expect(redirect).not.toHaveBeenCalled();
    resolveQuery({ market: "tw" });
    await expect(result).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledExactlyOnceWith("/?view=globe&market=tw");
    expect(dynamic).toBe("force-dynamic");
  });

  it("preserves first-value, trimming and URL-encoding behavior", async () => {
    await expect(GlobeRedirect({ searchParams: Promise.resolve({
      market: [" unknown & market ", "us"],
      tour: " asia ",
      presentation: [" 1 ", "0"],
    }) })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledExactlyOnceWith(
      "/?view=globe&market=unknown+%26+market&tour=asia&presentation=1",
    );
  });

  it.each([undefined, {}, { market: "  ", tour: [], presentation: "true" }])(
    "keeps missing/empty queries on the canonical globe workspace (%j)", async (query) => {
      await expect(GlobeRedirect({
        searchParams: query === undefined ? undefined : Promise.resolve(query),
      })).rejects.toThrow("NEXT_REDIRECT");
      expect(redirect).toHaveBeenCalledExactlyOnceWith("/?view=globe");
    },
  );
});
