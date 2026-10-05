import { beforeEach, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { executeSmaRequest, readReplayLink, useReplayLinkCleanup, writeReplayLink, type ReplayRestore } from "./runReplay";
import { writeMLLifecycleLink } from "./mlLifecycleLink";
import type { BacktestRequest } from "./types";

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

it("cleans destination query fields without inserting another history entry", () => {
  window.history.replaceState(null, "", `/?view=runreplay&hash=${"a".repeat(64)}&context=3`);
  const { rerender } = renderHook(({ view }) => useReplayLinkCleanup(view), { initialProps: { view: "runreplay" } });
  const push = vi.spyOn(history, "pushState");
  const replace = vi.spyOn(history, "replaceState");
  writeMLLifecycleLink(true);
  rerender({ view: "mllifecycle" });
  expect(push).toHaveBeenCalledTimes(1);
  expect(replace).toHaveBeenCalledTimes(1);
  expect(location.search).toBe("?view=mllifecycle");
});

const providerRequest: BacktestRequest = { ticker: " spy ", start_date: "2020-01-01", end_date: "2021-01-01",
  fast_window: 7, slow_window: 31, initial_capital: 100000, transaction_cost_bps: 10 };
const providerConfig = { schema_version: "backtest_config_v1", strategy: "sma_crossover", ticker: "SPY",
  start_date: "2020-01-01", end_date: "2021-01-01", data_provider: "yfinance" };
const providerRestore: ReplayRestore = {
  request: providerRequest,
  preflight: {
    schema_version: "replay_preflight_v1", context_id: 19,
    config_hash_full: "a".repeat(64), canonical_config: providerConfig,
    input_hash: "b".repeat(64), environment_hash: null,
    result_hash: "c".repeat(64), execution_hash: "d".repeat(64),
    original_request: { ...providerRequest }, restore_request: providerRequest, restore_level: "recorded_settings",
    dataset: null, artifact: null, data_availability: "provider_refetch_required",
    integrity: "intact", ready_with_retained_data: false, environment_comparison: [], limitations: [],
  },
};
const providerCapture = { schema_version: "replay_capture_v1", original_request: providerRequest,
  execution_environment: { schema_version: "environment_manifest_v1", classification: "execution", collection: "test", fields: {} } };

it("fails closed for unsupported restored input rather than requesting a provider", async () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const restored: ReplayRestore = { ...providerRestore,
    preflight: { ...providerRestore.preflight, canonical_config: { ...providerConfig, data_provider: "missing" } } };
  await expect(executeSmaRequest(restored.request, restored)).rejects.toThrow("Unsupported restored data source");
  expect(fetch).not.toHaveBeenCalled();
});

it("links a provider rerun once using its actual same-input canonical result", async () => {
  const response = { execution_context: providerCapture,
    reproducibility: { canonical_config_json: JSON.stringify({ ...providerConfig, strategy_params: { fast_window: 7, slow_window: 31 } }) } };
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 })); vi.stubGlobal("fetch", fetch);
  const result = await executeSmaRequest(providerRequest, providerRestore);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe("/api/backtest/sma-crossover");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(providerRequest);
  expect(result.execution_context).toEqual({ ...providerCapture, parent_context_id: 19 });
});

it.each([
  { ticker: "QQQ" }, { start_date: "2020-02-01" }, { end_date: "2021-02-01" },
  { dataset_fingerprint: "b".repeat(64) },
])("omits provider parent when the executed input identity changes (%j)", async (change) => {
  const response = { execution_context: { ...providerCapture, parent_context_id: 99 },
    reproducibility: { canonical_config_json: JSON.stringify({ ...providerConfig, ...change }) } };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 })));
  const result = await executeSmaRequest({ ...providerRequest, ...change }, providerRestore);
  expect(result.execution_context).toEqual(providerCapture);
});

it("omits provider parent when a dataset pin cannot be carried into the new execution", async () => {
  const response = { execution_context: providerCapture,
    reproducibility: { canonical_config_json: JSON.stringify(providerConfig) } };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 })));
  const restored = { ...providerRestore, preflight: { ...providerRestore.preflight, dataset: { version_id: 8, material_hash: "a".repeat(64) } } };
  const result = await executeSmaRequest(providerRequest, restored);
  expect(result.execution_context).toEqual(providerCapture);
});

it("does not invent a capture or parent if provider execution metadata are unavailable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 200 })));
  const result = await executeSmaRequest(providerRequest, providerRestore);
  expect(result.execution_context).toBeUndefined();
});

it("keeps the backend's CSV parent binding without a provider request", async () => {
  const response = { execution_context: { ...providerCapture, parent_context_id: 19, dataset_version_id: 8 } };
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200 })); vi.stubGlobal("fetch", fetch);
  const restored = { ...providerRestore, preflight: { ...providerRestore.preflight, canonical_config: { ...providerConfig, data_provider: "csv_upload" } } };
  const result = await executeSmaRequest(providerRequest, restored);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe("/api/run-replay/contexts/19/execute-local");
  expect(result.execution_context).toEqual(response.execution_context);
});
