import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ResearchExplanationPanel from "./ResearchExplanationPanel";
import { checkExplanation, resolveFact, type ResearchExplanation } from "@/lib/researchExplainer";

function fixture(id = 1): ResearchExplanation {
  return { schema_version: "research_explanation_v1", adapter_version: "saved_sma_v1", template_version: "saved_sma_en_v1",
    policy_version: "stored_facts_policy_v1", locale: "en-US", identity: { source_kind: "saved_backtest", source_schema: "saved_backtests_row_v1",
      saved_backtest_id: id, created_at: "2020-01-01T00:00:00Z", material_hash: "a".repeat(64), trust: "legacy_unverified", context: null },
    evidence: { saved: { metrics: { total_return: -.12 } } }, facts: [{ id: "total_return", source: "saved", path: "/metrics/total_return", state: "available", value: -.12,
      unit: "decimal_return", rule: "percent_2", display: "-12.00%" }], statements: [{ template_id: "total_return", text: "The stored total return is -12.00%.", facts: ["total_return"], policy_id: null },
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

it("blocks duplicate requests and ignores old selected/unmounted responses", async () => {
  let finish!: (r: Response) => void;
  const fetch = vi.fn().mockReturnValue(new Promise<Response>((resolve) => { finish = resolve; })); vi.stubGlobal("fetch", fetch);
  const { rerender, unmount } = render(<ResearchExplanationPanel id={1} />);
  const button = screen.getByRole("button", { name: "Explain stored result" });
  act(() => { button.click(); button.click(); }); expect(fetch).toHaveBeenCalledTimes(1);
  rerender(<ResearchExplanationPanel id={2} />);
  await act(async () => finish(new Response(JSON.stringify(fixture()))));
  expect(screen.queryByText("The stored total return is -12.00%.")).not.toBeInTheDocument();
  unmount();
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
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture()))); vi.stubGlobal("fetch", fetch);
  const create = vi.fn().mockReturnValue("blob:test"); vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<ResearchExplanationPanel id={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain stored result" }));
  fireEvent.click(await screen.findByRole("button", { name: "Download explanation JSON" }));
  expect(fetch).toHaveBeenCalledTimes(1);
  const blob = create.mock.calls[0][0] as Blob;
  const text = await new Promise<string>((resolve) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
  expect(JSON.parse(text)).toEqual(fixture());
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
