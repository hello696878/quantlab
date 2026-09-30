import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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
