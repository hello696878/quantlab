import { beforeEach, expect, it } from "vitest";
import { readReplayLink, writeReplayLink } from "./runReplay";

beforeEach(() => window.history.replaceState(null, "", "/"));
it("accepts only bounded full hashes and IDs, never config JSON", () => {
  expect(readReplayLink(`?view=runreplay&hash=${"a".repeat(64)}&context=2`)).toMatchObject({ active: true, location: { hash: "a".repeat(64), context: 2 } });
  for (const search of ["?view=runreplay&hash=abcdef", "?view=runreplay&context=2", `?view=runreplay&hash=${"a".repeat(64)}&context=2147483648`, "?view=runreplay&hash=a&hash=b"])
    expect(readReplayLink(search).error).toBeTruthy();
});
it("clears replay IDs on exit and preserves unrelated URL state", () => {
  window.history.replaceState(null, "", "/?theme=green&view=globe&market=us");
  writeReplayLink({ hash: "b".repeat(64), context: 3 });
  expect(window.location.search).toContain("context=3");
  expect(window.location.search).not.toContain("market");
  writeReplayLink(null);
  expect(window.location.search).toBe("?theme=green");
});
it("cleans stale replay query fields after a direct workspace destination sets its own view", () => {
  window.history.replaceState(null, "", `/?view=globe&market=us&hash=${"a".repeat(64)}&context=3`);
  writeReplayLink(null);
  expect(window.location.search).toBe("?view=globe&market=us");
});
