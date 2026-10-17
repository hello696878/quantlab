import { act, fireEvent, render, screen } from "@testing-library/react";
import { Blob as NodeBlob } from "node:buffer";
import { afterEach, expect, it, vi } from "vitest";
import ResearchExplanationPanel from "./ResearchExplanationPanel";
import { checkExplanation, downloadExplanation, explainSavedBacktest, resolveFact, type ResearchExplanation } from "@/lib/researchExplainer";

function fixture(id = 1, value = -.12, display = "-12.00%"): ResearchExplanation {
  return { schema_version: "research_explanation_v1", adapter_version: "saved_sma_v1", template_version: "saved_sma_en_v1",
    policy_version: "stored_facts_policy_v1", locale: "en-US", identity: { source_kind: "saved_backtest", source_schema: "saved_backtests_row_v1",
      saved_backtest_id: id, created_at: "2020-01-01T00:00:00Z", material_hash: "a".repeat(64), trust: "legacy_unverified", context: null },
    evidence: { saved: { metrics: { total_return: value } } }, facts: [{ id: "total_return", source: "saved", path: "/metrics/total_return", state: "available", value,
      unit: "decimal_return", rule: "percent_2", display }], statements: [{ template_id: "total_return", text: `The stored total return is ${display}.`, facts: ["total_return"], policy_id: null },
      { template_id: "legacy", text: "This stored record has no replay context; execution integrity remains unverified.", facts: [], policy_id: "stored_facts_policy_v1" }], fingerprint: "b".repeat(64) };
}
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("does not fetch automatically; explicit read binds exact raw fact and path", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture()))); vi.stubGlobal("fetch", fetch);
  render(<ResearchExplanationPanel id={1} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  expect(await screen.findByText("The stored total return is -12.00%.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Inspect source total_return" }));
  expect(screen.getByRole("region", { name: "Evidence reference" })).toHaveTextContent("saved/metrics/total_return");
  expect(screen.getByRole("region", { name: "Evidence reference" })).toHaveTextContent("-0.12");
  expect(fetch).toHaveBeenCalledWith("/api/research-explainer/saved-backtests/1", { cache: "no-store" });
});

it("blocks batched duplicate reads and keeps B when A completes after B", async () => {
  let finishA!: (r: Response) => void, finishB!: (r: Response) => void;
  const fetch = vi.fn()
    .mockReturnValueOnce(new Promise<Response>((resolve) => { finishA = resolve; }))
    .mockReturnValueOnce(new Promise<Response>((resolve) => { finishB = resolve; })); vi.stubGlobal("fetch", fetch);
  const { rerender } = render(<ResearchExplanationPanel id={1} />);
  const button = screen.getByRole("button", { name: "Explain stored result" });
  act(() => { button.click(); expect(button).not.toBeDisabled(); button.click(); }); expect(fetch).toHaveBeenCalledTimes(1);
  rerender(<ResearchExplanationPanel id={2} />);
  expect(fetch).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  await act(async () => finishB(new Response(JSON.stringify(fixture(2, .25, "25.00%")))));
  fireEvent.click(screen.getByRole("button", { name: "Inspect source total_return" }));
  await act(async () => finishA(new Response(JSON.stringify(fixture()))));
  expect(screen.queryByText("The stored total return is -12.00%.")).not.toBeInTheDocument();
  expect(screen.getByText("The stored total return is 25.00%.")).toBeVisible();
  expect(screen.getByRole("region", { name: "Evidence reference" })).toHaveTextContent("0.25");
  expect(screen.getByRole("button", { name: "Download explanation JSON" })).toBeEnabled();
  expect(fetch.mock.calls.map((call) => call[0])).toEqual([
    "/api/research-explainer/saved-backtests/1", "/api/research-explainer/saved-backtests/2",
  ]);
});

it.each([200, 404])("a late source-check response (%s) for A cannot replace B's newer result or evidence drawer", async (status) => {
  let finishCheck!: (r: Response) => void;
  const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(fixture())))
    .mockReturnValueOnce(new Promise<Response>((resolve) => { finishCheck = resolve; }))
    .mockResolvedValueOnce(new Response(JSON.stringify(fixture(2, .25, "25.00%")))); vi.stubGlobal("fetch", fetch);
  const { rerender } = render(<ResearchExplanationPanel id={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  const check = await screen.findByRole("button", { name: "Check pinned source" });
  fireEvent.click(screen.getByRole("button", { name: "Inspect source total_return" }));
  act(() => { check.click(); expect(check).not.toBeDisabled(); check.click(); });
  expect(fetch).toHaveBeenCalledTimes(2);
  rerender(<ResearchExplanationPanel id={2} />);
  expect(screen.queryByRole("region", { name: "Evidence reference" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Download explanation JSON" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  await screen.findByText("The stored total return is 25.00%.");
  fireEvent.click(screen.getByRole("button", { name: "Inspect source total_return" }));
  await act(async () => finishCheck(new Response(JSON.stringify(status === 200 ? fixture() : { detail: "Old source deleted" }), { status })));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Evidence reference" })).toHaveTextContent("0.25");
  expect(screen.getByRole("button", { name: "Download explanation JSON" })).toBeEnabled();
  expect(fetch).toHaveBeenCalledTimes(3);
});

it("unmounting a pending check clears its drawer and does not explain automatically on remount", async () => {
  let finishCheck!: (r: Response) => void;
  const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(fixture())))
    .mockReturnValueOnce(new Promise<Response>((resolve) => { finishCheck = resolve; })); vi.stubGlobal("fetch", fetch);
  const first = render(<ResearchExplanationPanel id={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  await screen.findByRole("button", { name: "Check pinned source" });
  fireEvent.click(screen.getByRole("button", { name: "Inspect source total_return" }));
  fireEvent.click(screen.getByRole("button", { name: "Check pinned source" }));
  first.unmount();
  render(<ResearchExplanationPanel id={1} />);
  await act(async () => finishCheck(new Response(JSON.stringify(fixture()))));
  expect(screen.queryByRole("region", { name: "Evidence reference" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Download explanation JSON" })).not.toBeInTheDocument();
  expect(screen.queryByText("The stored total return is -12.00%.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Explain stored result" })).toBeEnabled();
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("changed or deleted source removes currentness claim while keeping useful error", async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(fixture())))
    .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Stored source changed or failed integrity checks" }), { status: 409 })); vi.stubGlobal("fetch", fetch);
  render(<ResearchExplanationPanel id={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  fireEvent.click(await screen.findByRole("button", { name: "Check pinned source" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Stored source changed");
  expect(screen.queryByRole("button", { name: "Download explanation JSON" })).not.toBeInTheDocument();
  expect(fetch.mock.calls[1][0]).toContain(`expected=${"b".repeat(64)}`);
});

it("exports the exact displayed bundle without another request", async () => {
  const originalText = JSON.stringify(fixture());
  const fetch = vi.fn().mockResolvedValue(new Response(originalText)); vi.stubGlobal("fetch", fetch);
  vi.stubGlobal("Blob", NodeBlob);
  const create = vi.fn((_blob: NodeBlob) => "blob:test"), revoke = vi.fn();
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<ResearchExplanationPanel id={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  const download = await screen.findByRole("button", { name: "Download explanation JSON" });
  vi.useFakeTimers();
  fireEvent.click(download);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(await create.mock.calls[0][0].text()).toBe(originalText);
  expect(JSON.parse(await create.mock.calls[0][0].text())).toEqual(fixture());
  vi.runAllTimers();
  expect(revoke).toHaveBeenCalledWith("blob:test");
  vi.useRealTimers();
});

it.each(["0.0", "-0.0"])("preserves the exact server numeric token %s in the rendered download", async (token) => {
  // Literal server-style number spelling is independent of JS serialization.
  const wireText = JSON.stringify(fixture()).replaceAll("-0.12", token).replaceAll("-12.00%", "0.00%");
  const fetch = vi.fn().mockResolvedValue(new Response(wireText)); vi.stubGlobal("fetch", fetch);
  vi.stubGlobal("Blob", NodeBlob);
  const create = vi.fn((_blob: NodeBlob) => "blob:wire");
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<ResearchExplanationPanel id={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  const download = await screen.findByRole("button", { name: "Download explanation JSON" });
  expect(screen.getByText("The stored total return is 0.00%.")).toBeVisible();
  vi.useFakeTimers();
  fireEvent.click(download);
  expect(await create.mock.calls[0][0].text()).toBe(wireText);
  expect(fetch).toHaveBeenCalledTimes(1);
  vi.runAllTimers();
  vi.useRealTimers();
});

it("refuses copied bundles and mutations even when fact bindings still agree", async () => {
  const wireText = JSON.stringify(fixture()).replaceAll("-0.12", "-0.0").replaceAll("-12.00%", "0.00%");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(wireText)));
  const create = vi.fn(); vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: vi.fn() });
  const bundle = await explainSavedBacktest(1);
  expect(() => downloadExplanation(structuredClone(bundle))).toThrow("no retained response");
  // Ordinary JS equality considers -0 and 0 equal; the retained snapshot does not.
  const metrics = (bundle.evidence.saved as { metrics: { total_return: number } }).metrics;
  metrics.total_return = 0; bundle.facts[0].value = 0;
  expect(() => checkExplanation(bundle, 1)).not.toThrow();
  expect(() => downloadExplanation(bundle)).toThrow("Pinned explanation changed");
  metrics.total_return = -0; bundle.facts[0].value = -0;
  bundle.statements[0].text = "A coherently bound but changed statement.";
  expect(() => checkExplanation(bundle, 1)).not.toThrow();
  expect(() => downloadExplanation(bundle)).toThrow("Pinned explanation changed");
  expect(create).not.toHaveBeenCalled();
});

it("offline and unsupported results are not replaced by fabricated narrative", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Backend unavailable")));
  render(<ResearchExplanationPanel id={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Backend unavailable");
  expect(screen.queryByText("Stored SMA explanation")).not.toBeInTheDocument();
});

it("binding validation refuses malformed pointers, mismatched IDs/values and unknown statements", () => {
  const bundle = fixture(); expect(checkExplanation(bundle, 1)).toEqual(bundle);
  expect(() => checkExplanation(bundle, 2)).toThrow();
  const bad = structuredClone(bundle); bad.facts[0].value = 0; expect(() => checkExplanation(bad, 1)).toThrow();
  bad.facts[0].path = "/bad~2key"; expect(() => resolveFact(bad, bad.facts[0])).toThrow();
  const extra = structuredClone(bundle); extra.statements[0].facts = ["secret"]; expect(() => checkExplanation(extra, 1)).toThrow();
});

it("resolves escaped object keys but accepts only canonical bounded array indices", () => {
  const bundle = fixture();
  bundle.evidence.saved = { "a/b": { "~c": -7 }, items: [11, 22], keyed: { "01": 33, length: 44 }, scalar: 1 };
  const lookup = (path: string) => resolveFact(bundle, { ...bundle.facts[0], path });
  expect(lookup("/a~1b/~0c")).toEqual({ present: true, value: -7 });
  expect(lookup("/items/0")).toEqual({ present: true, value: 11 });
  expect(lookup("/items/1")).toEqual({ present: true, value: 22 });
  expect(lookup("/keyed/01")).toEqual({ present: true, value: 33 });
  expect(lookup("/keyed/length")).toEqual({ present: true, value: 44 });
  for (const path of ["/items/length", "/items/01", "/items/-1", "/items/1.0", "/items/2", "/items/123456789", "/items/-", "/absent"]) {
    expect(lookup(path)).toEqual({ present: false, value: null });
  }
  for (const path of ["/a~3b", "/absent/bad~3token", "/scalar/bad~3token", "/items/8/bad~2token"]) {
    expect(() => lookup(path)).toThrow("Invalid evidence reference");
  }
});
