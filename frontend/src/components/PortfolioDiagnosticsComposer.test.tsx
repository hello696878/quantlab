import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { renderWithUser } from "@/test/testUtils";
import { diagnosticRun, returnInput } from "@/test/fixtures/portfolioDiagnosticsComposer";
import * as api from "@/lib/portfolioDiagnostics";
import { BacktestApiError } from "@/lib/api";
import PortfolioDiagnosticsComposer from "./PortfolioDiagnosticsComposer";

vi.mock("@/lib/portfolioDiagnostics", async (original) => ({ ...await original<typeof api>(), createRun: vi.fn(), executeRun: vi.fn(), getRun: vi.fn() }));
const onOpen = vi.fn(), onBack = vi.fn();
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (err: unknown) => void;
  const promise = new Promise<T>((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}
beforeEach(() => {
  [api.createRun, api.executeRun, api.getRun, onOpen, onBack].forEach((fn) => vi.mocked(fn).mockReset());
  vi.mocked(api.createRun).mockResolvedValue(diagnosticRun({ status: "pending" }));
  vi.mocked(api.executeRun).mockResolvedValue(diagnosticRun());
  vi.mocked(api.getRun).mockResolvedValue(diagnosticRun({ status: "failed" }));
});
const setup = () => renderWithUser(<PortfolioDiagnosticsComposer onOpen={onOpen} onBack={onBack} />);
async function prepare(user: ReturnType<typeof setup>["user"]) {
  fireEvent.change(screen.getByLabelText("Return JSON"), { target: { value: JSON.stringify(returnInput()) } });
  await user.click(screen.getByRole("button", { name: "Validate return data" }));
  await user.type(screen.getByLabelText("Run name"), "My supplied portfolio");
  await user.type(screen.getByLabelText("Weight for a (%)"), "70");
  await user.type(screen.getByLabelText("Weight for b (%)"), "30");
}

it("previews only a bounded sample, records explicit weights and opens actual execution result", async () => {
  const { user } = setup(); await prepare(user);
  expect(screen.getByText(/Entered total: 100%/)).toBeVisible();
  expect(screen.getByText(/first effective date: 2024-01-21/)).toBeVisible();
  expect(screen.getByText(/first 3 observations only/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(api.createRun).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ weights: { a: 0.7, b: 0.3 }, normalization: "none", weight_provenance: { basis: "declared" } }));
  expect(api.executeRun).toHaveBeenCalledExactlyOnceWith(51);
  expect(onOpen).toHaveBeenCalledExactlyOnceWith(diagnosticRun());
});
it("invalidates preview and weights on pasted input edits", async () => {
  const { user } = setup(); await prepare(user);
  fireEvent.change(screen.getByLabelText("Return JSON"), { target: { value: "{" } });
  expect(screen.queryByLabelText("Weight for a (%)")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Validate return data" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Invalid JSON");
});
it("keeps numeric editing raw including empty, explicit zero and trailing decimals", async () => {
  const { user } = setup(); await prepare(user);
  await user.clear(screen.getByLabelText("Weight for a (%)"));
  expect(screen.getByLabelText("Weight for a (%)")).toHaveValue("");
  expect(screen.getByRole("button", { name: "Create and run" })).toBeDisabled();
  await user.type(screen.getByLabelText("Weight for a (%)"), "0.");
  await user.clear(screen.getByLabelText("Weight for b (%)")); await user.type(screen.getByLabelText("Weight for b (%)"), "100");
  expect(screen.getByLabelText("Weight for a (%)")).toHaveValue("0.");
  await user.clear(screen.getByLabelText("Rolling lookback"));
  expect(screen.getByLabelText("Rolling lookback")).toHaveValue("");
  await user.type(screen.getByLabelText("Rolling lookback"), "3");
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(api.createRun).toHaveBeenCalledWith(expect.objectContaining({ weights: { a: 0, b: 1 } }));
});
it("ignores an older file read after newer selection or paste and invalidates preview immediately", async () => {
  const { user } = setup(); await prepare(user);
  const old = deferred<string>();
  const file = (text: () => Promise<string>) => ({ size: 100, text });
  fireEvent.change(screen.getByLabelText("Local JSON file"), { target: { files: [file(() => old.promise)] } });
  expect(screen.queryByLabelText("Weight for a (%)")).not.toBeInTheDocument();
  const newer = JSON.stringify(returnInput(25));
  fireEvent.change(screen.getByLabelText("Local JSON file"), { target: { files: [file(async () => newer)] } });
  await waitFor(() => expect(screen.getByLabelText("Return JSON")).toHaveValue(newer));
  await act(async () => old.resolve("stale"));
  expect(screen.getByLabelText("Return JSON")).toHaveValue(newer);
  await user.click(screen.getByRole("button", { name: "Validate return data" }));
  expect(screen.getByLabelText("Validated return preview")).toHaveTextContent("25 observations");
  const staleFailure = deferred<string>();
  fireEvent.change(screen.getByLabelText("Local JSON file"), { target: { files: [file(() => staleFailure.promise)] } });
  fireEvent.change(screen.getByLabelText("Return JSON"), { target: { value: "new paste" } });
  await act(async () => staleFailure.reject(new Error("obsolete")));
  expect(screen.getByLabelText("Return JSON")).toHaveValue("new paste");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
it("refuses oversized files before reading and displays read errors", async () => {
  setup(); const text = vi.fn();
  fireEvent.change(screen.getByLabelText("Local JSON file"), { target: { files: [{ size: 2097153, text }] } });
  expect(text).not.toHaveBeenCalled(); expect(screen.getByRole("alert")).toHaveTextContent("2 MiB");
  fireEvent.change(screen.getByLabelText("Local JSON file"), { target: { files: [{ size: 10, text: async () => { throw new Error("File unavailable"); } }] } });
  expect(await screen.findByRole("alert")).toHaveTextContent("File unavailable");
});
it("locks request inputs and synchronously prevents rapid submissions", async () => {
  const pending = deferred<api.RunFull>(); vi.mocked(api.createRun).mockReturnValue(pending.promise);
  const { user } = setup(); await prepare(user);
  const form = screen.getByRole("button", { name: "Create and run" }).closest("form")!;
  act(() => { fireEvent.submit(form); fireEvent.submit(form); });
  expect(api.createRun).toHaveBeenCalledOnce();
  for (const label of ["Run name", "Return JSON", "Local JSON file", "Weight for a (%)", "Rolling lookback"]) expect(screen.getByLabelText(label)).toBeDisabled();
  await act(async () => pending.resolve(diagnosticRun({ status: "pending" })));
  expect(api.executeRun).toHaveBeenCalledOnce();
});
it.each([new BacktestApiError(0, "offline"), new BacktestApiError(500, "server"), new Error("lost response")])("never retries uncertain creation: %s", async (error) => {
  vi.mocked(api.createRun).mockRejectedValue(error);
  const { user } = setup(); await prepare(user); await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Creation outcome is unknown");
  expect(screen.queryByRole("button", { name: "Create and run" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Inspect run list" })); expect(onBack).toHaveBeenCalledOnce();
  expect(api.createRun).toHaveBeenCalledOnce(); expect(api.executeRun).not.toHaveBeenCalled();
});
it("leaves rejected validation editable and rejects missing/invalid create IDs as unknown", async () => {
  vi.mocked(api.createRun).mockRejectedValueOnce(new BacktestApiError(422, "Invalid name"));
  const { user } = setup(); await prepare(user); await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Invalid name"); expect(screen.getByLabelText("Run name")).toBeEnabled();
  vi.mocked(api.createRun).mockResolvedValueOnce(diagnosticRun({ id: 0 }));
  await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Creation outcome is unknown"); expect(api.executeRun).not.toHaveBeenCalled();
});
it("retains the created ID after a lost execution and requires refresh then explicit same-ID recovery", async () => {
  vi.mocked(api.executeRun).mockRejectedValueOnce(new Error("Lost execution response"));
  const { user } = setup(); await prepare(user); await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Run #51 is retained");
  expect(screen.getByRole("button", { name: "Retry execution of this run" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Refresh stored run" }));
  expect(screen.getByRole("button", { name: "Retry execution of this run" })).toBeEnabled();
  await user.click(screen.getByRole("button", { name: "Retry execution of this run" }));
  expect(api.getRun).toHaveBeenCalledTimes(2); expect(api.executeRun).toHaveBeenCalledTimes(2);
  expect(api.executeRun).toHaveBeenLastCalledWith(51); expect(api.createRun).toHaveBeenCalledOnce();
  expect(onOpen).toHaveBeenCalledWith(diagnosticRun());
});
it.each(["running", "invalidated", "completed"] as const)("does not execute refreshed %s records", async (status) => {
  vi.mocked(api.getRun).mockResolvedValue(diagnosticRun({ status }));
  const { user } = renderWithUser(<PortfolioDiagnosticsComposer initialRun={diagnosticRun({ status: "pending" })} onOpen={onOpen} onBack={onBack} />);
  await user.click(screen.getByRole("button", { name: "Refresh stored run" }));
  expect(api.executeRun).not.toHaveBeenCalled(); expect(api.createRun).not.toHaveBeenCalled();
  if (status === "completed") expect(onOpen).toHaveBeenCalledWith(diagnosticRun({ status }));
  else expect(screen.getByRole("button", { name: "Retry execution of this run" })).toBeDisabled();
});
it("rechecks status immediately before retry so a concurrent completion is not rerun", async () => {
  vi.mocked(api.getRun).mockResolvedValueOnce(diagnosticRun({ status: "pending" })).mockResolvedValueOnce(diagnosticRun());
  const { user } = renderWithUser(<PortfolioDiagnosticsComposer initialRun={diagnosticRun({ status: "pending" })} onOpen={onOpen} onBack={onBack} />);
  await user.click(screen.getByRole("button", { name: "Refresh stored run" })); await user.click(screen.getByRole("button", { name: "Retry execution of this run" }));
  expect(api.executeRun).not.toHaveBeenCalled(); expect(onOpen).toHaveBeenCalledWith(diagnosticRun());
});
it("rejects mismatched execute and refresh identities without losing the known ID", async () => {
  vi.mocked(api.executeRun).mockResolvedValue(diagnosticRun({ id: 999 }));
  vi.mocked(api.getRun).mockResolvedValue(diagnosticRun({ id: 998 }));
  const { user } = setup(); await prepare(user); await user.click(screen.getByRole("button", { name: "Create and run" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("identity mismatch");
  await user.click(screen.getByRole("button", { name: "Refresh stored run" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Run #51 is retained"); expect(onOpen).not.toHaveBeenCalled();
});
it("does not execute or open obsolete creation responses after unmount", async () => {
  const pending = deferred<api.RunFull>(); vi.mocked(api.createRun).mockReturnValue(pending.promise);
  const view = setup(); await prepare(view.user); await view.user.click(screen.getByRole("button", { name: "Create and run" }));
  view.unmount(); await act(async () => pending.resolve(diagnosticRun({ status: "pending" })));
  expect(api.executeRun).not.toHaveBeenCalled(); expect(onOpen).not.toHaveBeenCalled();
});
