import { expect, it, vi } from "vitest";
import { checkCapabilities, corpusPrecondition, loadCapabilities } from "./servingCapabilities";

export const local = { schema: "serving_capabilities_v1", mode: "local", policy: "local_v1", corpus_id: null, synthetic: false, capabilities: ["local_research"] };
export const demo = { schema: "serving_capabilities_v1", mode: "read_only_demo", policy: "read_only_demo_v1", corpus_id: "a".repeat(64), synthetic: true, capabilities: ["browse_saved_sma", "explain_saved_sma"] };

it("pins demo reads without changing ordinary requests or accepting partial IDs", () => {
  expect(corpusPrecondition()).toEqual({});
  expect(corpusPrecondition(demo.corpus_id)).toEqual({ cache: "no-store", headers: { "X-QuantLab-Expected-Corpus": demo.corpus_id } });
  expect(() => corpusPrecondition("prefix")).toThrow("identity unavailable");
});

it("accepts exact local and bounded public-demo contracts", () => {
  expect(checkCapabilities(local).mode).toBe("local");
  expect(checkCapabilities(demo).synthetic).toBe(true);
});

it.each([null, {}, { ...local, read_only: false }, { ...local, policy: "unknown" },
  { ...demo, synthetic: false }, { ...demo, corpus_id: "prefix" }, { ...demo, capabilities: ["local_research"] }])(
  "rejects missing, malformed and mixed capabilities %j", (value) => {
    expect(() => checkCapabilities(value)).toThrow();
  });

it("rejects explicit build/backend mismatch and invalid expected mode", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(demo))));
  vi.stubEnv("NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE", "local");
  await expect(loadCapabilities(new AbortController().signal)).rejects.toThrow("mismatch");
  vi.stubEnv("NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE", "true");
  await expect(loadCapabilities(new AbortController().signal)).rejects.toThrow("configuration");
});
