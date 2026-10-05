import { useState } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import RunReplayPanel from "./RunReplayPanel";
import type { ReplayLocation, ReplayPreflight, ReplayResolution, ReplayRestore } from "@/lib/runReplay";
import * as api from "@/lib/runReplay";

vi.mock("@/lib/runReplay", () => ({ resolveReplay: vi.fn(), preflightReplay: vi.fn(), createReplayDemo: vi.fn(), downloadReplay: vi.fn(), verifyReplayCSV: vi.fn() }));
const hash = "a".repeat(64);
const resolution: ReplayResolution = { config_hash_full: hash, config_hash: hash.slice(0, 12), canonical_config: {},
  contexts: [{ id: 1, saved_backtest_id: 2, name: "Actual saved run", created_at: "2026-10-05", input_hash: hash, result_hash: hash, environment_hash: null, execution_hash: hash }], total: 1, page: 1, page_size: 20, selection_required: true, ambiguous: false };
const preflight: ReplayPreflight = { schema_version: "replay_preflight_v1", context_id: 1, config_hash_full: hash,
  canonical_config: { data_provider: "csv_upload" }, input_hash: hash, environment_hash: null, result_hash: hash, execution_hash: hash,
  original_request: null, restore_request: { ticker: "SPY", fast_window: 5, slow_window: 20, start_date: "2020-01-01", end_date: "2021-01-01", initial_capital: 100000, transaction_cost_bps: 10 },
  restore_level: "config_only", dataset: null, artifact: null, data_availability: "retained_verified", integrity: "intact", ready_with_retained_data: true,
  environment_comparison: [{ field: "node", recorded: null, current: null, state: "unknown" }], limitations: ["Matching manifests do not guarantee identical results"] };
beforeEach(() => { vi.clearAllMocks(); vi.mocked(api.resolveReplay).mockResolvedValue(resolution); vi.mocked(api.preflightReplay).mockResolvedValue(preflight); });
function Host({ restore = vi.fn() }: { restore?: (restored: ReplayRestore) => void }) {
  const [location, setLocation] = useState<ReplayLocation>({ hash });
  return <RunReplayPanel location={location} onLocation={setLocation} onRestore={restore} />;
}
it("requires explicit context and confirmation; opening, filtering and cancel never restore", async () => {
  const restore = vi.fn(); render(<Host restore={restore} />);
  await screen.findByText(/Actual saved run/);
  expect(api.preflightReplay).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText(/Actual saved run/));
  await screen.findByRole("table", { name: "Environment comparison" });
  expect(screen.getAllByText("Unknown")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Restore configuration" }));
  expect(screen.getByRole("dialog", { name: "Confirm configuration restore" })).toHaveTextContent("Unsaved edits");
  expect(restore).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(restore).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Restore configuration" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply and open Backtest Studio" }));
  await waitFor(() => expect(restore).toHaveBeenCalledExactlyOnceWith({ preflight, request: preflight.restore_request, csvText: undefined }));
  expect(api.createReplayDemo).not.toHaveBeenCalled();
});

it("rechecks preflight at confirmation and refuses content changed since inspection", async () => {
  const restore = vi.fn();
  vi.mocked(api.preflightReplay).mockResolvedValueOnce(preflight).mockResolvedValueOnce({ ...preflight, integrity: "changed" });
  render(<Host restore={restore} />);
  fireEvent.click(await screen.findByText(/Actual saved run/));
  fireEvent.click(await screen.findByRole("button", { name: "Restore configuration" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply and open Backtest Studio" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("changed or is incomplete");
  expect(restore).not.toHaveBeenCalled();
  expect(api.createReplayDemo).not.toHaveBeenCalled();
  expect(api.preflightReplay).toHaveBeenCalledTimes(2);
});

it("coalesces rapid Apply clicks into one fresh preflight and one restore without execution or save", async () => {
  const restore = vi.fn();
  const actualApi = await vi.importActual<typeof import("@/lib/runReplay")>("@/lib/runReplay");
  let finish!: (response: Response) => void;
  const fetch = vi.fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(new Response(JSON.stringify(preflight), { status: 200 }))
    .mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  vi.stubGlobal("fetch", fetch);
  vi.mocked(api.preflightReplay).mockImplementation(actualApi.preflightReplay);
  render(<Host restore={restore} />);
  fireEvent.click(await screen.findByText(/Actual saved run/));
  fireEvent.click(await screen.findByRole("button", { name: "Restore configuration" }));
  expect(fetch).toHaveBeenCalledTimes(1); // Initial inspection only.
  const apply = screen.getByRole("button", { name: "Apply and open Backtest Studio" });
  await act(async () => {
    fireEvent.click(apply);
    // Keep both real handlers in one batch: disabled DOM state must not hide
    // a missing synchronous action guard from the second click.
    expect(apply).toBeEnabled();
    fireEvent.click(apply);
  });
  expect(fetch).toHaveBeenCalledTimes(2); // Exactly one fresh confirmation GET.
  expect(restore).not.toHaveBeenCalled();
  await act(async () => finish(new Response(JSON.stringify(preflight), { status: 200 })));
  expect(restore).toHaveBeenCalledExactlyOnceWith({ preflight, request: preflight.restore_request, csvText: undefined });
  // All actual network calls were read-only preflight; no engine/provider/save.
  expect(fetch.mock.calls).toEqual([
    ["/api/run-replay/contexts/1", { cache: "no-store" }],
    ["/api/run-replay/contexts/1", { cache: "no-store" }],
  ]);
  expect(api.createReplayDemo).not.toHaveBeenCalled();
});

it("does not apply a delayed confirmation over a newer hash selection", async () => {
  const restore = vi.fn();
  let finish!: (value: ReplayPreflight) => void;
  vi.mocked(api.preflightReplay).mockResolvedValueOnce(preflight).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  render(<Host restore={restore} />);
  fireEvent.click(await screen.findByText(/Actual saved run/));
  fireEvent.click(await screen.findByRole("button", { name: "Restore configuration" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply and open Backtest Studio" }));
  fireEvent.change(screen.getByLabelText("Full configuration hash"), { target: { value: "b".repeat(64) } });
  await act(async () => finish(preflight));
  expect(restore).not.toHaveBeenCalled();
});
it("ignores stale preflight over a new input selection", async () => {
  let complete!: (value: ReplayPreflight) => void;
  vi.mocked(api.preflightReplay).mockReturnValue(new Promise((resolve) => { complete = resolve; }));
  render(<Host />);
  fireEvent.click(await screen.findByText(/Actual saved run/));
  await waitFor(() => expect(api.preflightReplay).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText("Full configuration hash"), { target: { value: "b".repeat(64) } });
  await act(async () => complete(preflight));
  expect(screen.queryByRole("button", { name: "Restore configuration" })).toBeNull();
});
it("shows changed provenance and disables restoration", async () => {
  vi.mocked(api.preflightReplay).mockResolvedValue({ ...preflight, integrity: "changed", limitations: ["Dataset material changed"] });
  render(<Host />); fireEvent.click(await screen.findByText(/Actual saved run/));
  await screen.findByText("Dataset material changed");
  expect(screen.getByRole("button", { name: "Restore configuration" })).toBeDisabled();
});
it("reports unknown/offline errors without seeding demo data", async () => {
  vi.mocked(api.resolveReplay).mockRejectedValue(new Error("Backend unavailable"));
  render(<Host />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Backend unavailable");
  expect(api.createReplayDemo).not.toHaveBeenCalled();
});
it("missing CSV requires successful content comparison before restoration", async () => {
  vi.mocked(api.preflightReplay).mockResolvedValue({ ...preflight, data_availability: "reselection_required" });
  vi.mocked(api.verifyReplayCSV).mockRejectedValue(new Error("CSV content differs"));
  render(<Host />); fireEvent.click(await screen.findByText(/Actual saved run/));
  const input = await screen.findByLabelText(/Reselect original CSV/);
  expect(screen.getByRole("button", { name: "Restore configuration" })).toBeDisabled();
  fireEvent.change(input, { target: { files: [{ size: 5, text: async () => "wrong" }] } });
  expect(await screen.findByRole("alert")).toHaveTextContent("CSV content differs");
  expect(screen.getByRole("button", { name: "Restore configuration" })).toBeDisabled();
});
