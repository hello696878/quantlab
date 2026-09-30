import { beforeEach, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MLLifecyclePanel from "./MLLifecyclePanel";
import * as api from "@/lib/mlLifecycle";
import { BacktestApiError } from "@/lib/api";
import { WORKSPACE_BY_ID, WORKSPACE_COMMANDS } from "@/lib/workspaceRegistry";
import { isMLLifecycleLink, writeMLLifecycleLink } from "@/lib/mlLifecycleLink";

vi.mock("@/lib/mlLifecycle", () => ({ listRuns: vi.fn(), getRun: vi.fn(), loadDemo: vi.fn(), compareRuns: vi.fn(), exportRun: vi.fn(), linkedRecord: vi.fn() }));
const base: api.Run = {
  id: 1, name: "Fixture lifecycle", created_at: "2024-01-01T00:00:00Z", lifecycle_hash: "a".repeat(64), dataset_version_id: 1,
  stored_status: "stored", processing_status: "idle", completeness: "incomplete", integrity: "intact", validation_state: "unverified",
  dataset_content_hash: "b".repeat(64), dataset_manifest_hash: "c".repeat(64), integrity_messages: [], identities: { lifecycle: "a".repeat(64), models: null },
  links: [], snapshot: { schema_version: 1, origin: "experiment_store", source: {}, source_environment: { classification: "unknown" }, unavailable: ["feature payload"] },
};

beforeEach(() => {
  vi.clearAllMocks();
  for (const fn of Object.values(api)) vi.mocked(fn).mockRejectedValue(new Error("Unexpected API call"));
  vi.mocked(api.listRuns).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
});

it("registers the workspace and preserves a valid narrow permalink", () => {
  expect(WORKSPACE_BY_ID.mllifecycle?.publicWorkspace).toBe(true);
  expect(WORKSPACE_COMMANDS.some((c) => c.view === "mllifecycle")).toBe(true);
  expect(isMLLifecycleLink("?view=unknown")).toBe(false);
  writeMLLifecycleLink(true); expect(isMLLifecycleLink()).toBe(true);
  writeMLLifecycleLink(false); expect(isMLLifecycleLink()).toBe(false);
});

it("opens read-only, with a real empty state and no demo mutation", async () => {
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByText("No matching ML lifecycles");
  expect(api.listRuns).toHaveBeenCalledWith(1, "", "");
  expect(api.loadDemo).not.toHaveBeenCalled();
  expect(api.getRun).not.toHaveBeenCalled();
});

it("shows offline recovery without claiming records were lost", async () => {
  vi.mocked(api.listRuns).mockRejectedValueOnce(new BacktestApiError(0, "Offline"));
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByRole("button", { name: /retry/i });
  await userEvent.click(screen.getByRole("button", { name: /retry/i }));
  await screen.findByText("No matching ML lifecycles");
  expect(api.loadDemo).not.toHaveBeenCalled();
});

it("opens an incomplete legacy record without invented models", async () => {
  vi.mocked(api.listRuns).mockResolvedValue({ items: [base], total: 1, page: 1, page_size: 20 });
  vi.mocked(api.getRun).mockResolvedValue(base);
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await userEvent.click(await screen.findByRole("button", { name: base.name }));
  await screen.findByTestId("ml-lifecycle-detail");
  expect(screen.getByText("feature payload")).toBeVisible();
  expect(screen.queryByRole("table", { name: "Fitted models" })).not.toBeInTheDocument();
  expect(api.loadDemo).not.toHaveBeenCalled();
});

it("requires an explicit demo action and prevents duplicate clicks", async () => {
  let finish!: (run: api.Run) => void;
  vi.mocked(api.loadDemo).mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByText("No matching ML lifecycles");
  const button = screen.getByRole("button", { name: /create.*synthetic demo/i });
  await userEvent.dblClick(button);
  expect(api.loadDemo).toHaveBeenCalledTimes(1);
  finish(base);
  await screen.findByTestId("ml-lifecycle-detail");
  expect(screen.getByRole("status")).toHaveTextContent("incomplete");
});

it("filters by both independent states", async () => {
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByText("No matching ML lifecycles");
  await userEvent.selectOptions(screen.getByLabelText("Completeness"), "incomplete");
  await userEvent.selectOptions(screen.getByLabelText("Integrity"), "changed");
  await waitFor(() => expect(api.listRuns).toHaveBeenLastCalledWith(1, "incomplete", "changed"));
});

it("inspects a pinned linked record and uses canonical lab navigation", async () => {
  const onNav = vi.fn();
  const run: api.Run = { ...base, links: [{ adapter: "validation", destination_id: 9, status: "completed", content_hash: "d".repeat(64), error: null, integrity: "intact", workspace: "model-validation" }] };
  vi.mocked(api.loadDemo).mockResolvedValue(run);
  vi.mocked(api.linkedRecord).mockResolvedValue({ record: { id: 9, name: "Linked fixture" } });
  render(<MLLifecyclePanel onNav={onNav} />);
  await screen.findByText("No matching ML lifecycles");
  await userEvent.click(screen.getByRole("button", { name: /create.*synthetic demo/i }));
  await userEvent.click(await screen.findByRole("button", { name: "Inspect validation record" }));
  await screen.findByTestId("ml-linked-detail");
  expect(api.linkedRecord).toHaveBeenCalledWith(1, "validation");
  await userEvent.click(screen.getByRole("button", { name: "Open validation lab" }));
  expect(onNav).toHaveBeenCalledWith("modelvalidation");
});

it("blocks exports for changed provenance", async () => {
  vi.mocked(api.loadDemo).mockResolvedValue({ ...base, integrity: "changed", integrity_messages: ["Dataset invalidated"] });
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByText("No matching ML lifecycles");
  await userEvent.click(screen.getByRole("button", { name: /create.*synthetic demo/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Dataset invalidated");
  expect(screen.getByRole("button", { name: "Export JSON" })).toBeDisabled();
  expect(api.exportRun).not.toHaveBeenCalled();
});

it("compares selected real records without ranking or mutation", async () => {
  const second = { ...base, id: 2, name: "Second fixture" };
  vi.mocked(api.listRuns).mockResolvedValue({ items: [base, second], total: 2, page: 1, page_size: 20 });
  vi.mocked(api.compareRuns).mockResolvedValue({ schema_version: 1, note: "Neutral comparison; no ranking or promotion.", rows: [{ field: "completeness", a: "incomplete", b: "incomplete" }], metrics: [null, null] });
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await userEvent.click(await screen.findByLabelText("Compare Fixture lifecycle"));
  await userEvent.click(screen.getByLabelText("Compare Second fixture"));
  await userEvent.click(screen.getByRole("button", { name: "Compare lifecycles" }));
  await screen.findByRole("table", { name: "Neutral lifecycle comparison" });
  expect(api.compareRuns).toHaveBeenCalledWith(1, 2);
  expect(api.loadDemo).not.toHaveBeenCalled();
});

it("clears successful detail and linked evidence before a failed demo retry", async () => {
  const run: api.Run = { ...base, completeness: "complete", links: [{ adapter: "validation", destination_id: 9,
    status: "completed", content_hash: "d".repeat(64), error: null, integrity: "intact", workspace: "model-validation" }] };
  vi.mocked(api.loadDemo).mockResolvedValueOnce(run).mockRejectedValueOnce(new BacktestApiError(422, "Adapter retry failed"));
  vi.mocked(api.linkedRecord).mockResolvedValue({ record: { id: 9 } });
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByText("No matching ML lifecycles");
  await userEvent.click(screen.getByRole("button", { name: /create.*synthetic demo/i }));
  await userEvent.click(await screen.findByRole("button", { name: "Inspect validation record" }));
  await screen.findByTestId("ml-linked-detail");
  await userEvent.click(screen.getByRole("button", { name: /create.*synthetic demo/i }));
  await screen.findByText("Adapter retry failed");
  expect(screen.queryByTestId("ml-lifecycle-detail")).not.toBeInTheDocument();
  expect(screen.queryByTestId("ml-linked-detail")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Export JSON" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /retry/i }));
  await screen.findByText("No matching ML lifecycles");
  expect(api.loadDemo).toHaveBeenCalledTimes(2);
});

it("ignores an older list response after the filter changes", async () => {
  let finish!: (value: api.Listing) => void;
  vi.mocked(api.listRuns).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await userEvent.selectOptions(screen.getByLabelText("Completeness"), "incomplete");
  await screen.findByText("No matching ML lifecycles");
  await act(async () => { finish({ items: [base], total: 1, page: 1, page_size: 20 }); });
  expect(screen.queryByRole("button", { name: base.name })).not.toBeInTheDocument();
  expect(screen.getByText("No matching ML lifecycles")).toBeVisible();
});

it("does not replace a newly mounted workspace with an old detail response", async () => {
  let finish!: (value: api.Run) => void;
  vi.mocked(api.listRuns).mockResolvedValueOnce({ items: [base], total: 1, page: 1, page_size: 20 });
  vi.mocked(api.getRun).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  const first = render(<MLLifecyclePanel onNav={vi.fn()} />);
  await userEvent.click(await screen.findByRole("button", { name: base.name }));
  first.unmount();
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByText("No matching ML lifecycles");
  await act(async () => { finish(base); });
  expect(screen.queryByTestId("ml-lifecycle-detail")).not.toBeInTheDocument();
});

it("downloads only the fresh strict export response and removes its temporary link", async () => {
  vi.mocked(api.loadDemo).mockResolvedValue(base);
  const exported = { schema_version: 1, source: "Fresh checked snapshot" };
  vi.mocked(api.exportRun).mockResolvedValue(exported);
  const created = vi.fn().mockReturnValue("blob:unit-lifecycle");
  const revoked = vi.fn();
  vi.stubGlobal("URL", class extends URL { static createObjectURL = created; static revokeObjectURL = revoked; });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    expect(this.download).toBe("quantlab-ml-lifecycle-1.json");
    expect(this.href).toBe("blob:unit-lifecycle");
  });
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByText("No matching ML lifecycles");
  await userEvent.click(screen.getByRole("button", { name: /create.*synthetic demo/i }));
  await userEvent.click(await screen.findByRole("button", { name: "Export JSON" }));
  await screen.findByText("JSON download requested.");
  expect(api.exportRun).toHaveBeenCalledWith(1);
  expect(click).toHaveBeenCalledTimes(1);
  expect(document.querySelector("a[download]")).toBeNull();
  const blob = created.mock.calls[0][0] as Blob;
  expect(blob.type).toBe("application/json");
  const content = await new Promise<string>((resolve) => {
    const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob);
  });
  expect(JSON.parse(content)).toEqual(exported);
  await waitFor(() => expect(revoked).toHaveBeenCalledWith("blob:unit-lifecycle"), { timeout: 1500 });
});

it("does not download stale detail when strict export refuses changed content", async () => {
  vi.mocked(api.loadDemo).mockResolvedValue(base);
  vi.mocked(api.exportRun).mockRejectedValue(new BacktestApiError(409, "Stored content changed"));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<MLLifecyclePanel onNav={vi.fn()} />);
  await screen.findByText("No matching ML lifecycles");
  await userEvent.click(screen.getByRole("button", { name: /create.*synthetic demo/i }));
  await userEvent.click(await screen.findByRole("button", { name: "Export JSON" }));
  await screen.findByText("Stored content changed");
  expect(click).not.toHaveBeenCalled();
  expect(screen.queryByText("JSON download requested.")).not.toBeInTheDocument();
});
