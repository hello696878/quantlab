import { act, screen, waitFor, within } from "@testing-library/react";
import { Blob as NodeBlob } from "node:buffer";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ScannerLabPanel from "./ScannerLabPanel";
import { renderWithUser } from "@/test/testUtils";
import * as api from "@/lib/api";
import type { ScannerResponse } from "@/lib/types";
import type { ScannerValidationResponse } from "@/lib/scannerAdvanced";

vi.mock("@/lib/api", async (original) => ({ ...await original<typeof import("@/lib/api")>(), runScanner: vi.fn(), validateScanner: vi.fn() }));
vi.mock("recharts", async (original) => ({ ...await original<typeof import("recharts")>(), ResponsiveContainer: () => null }));
// Test-only independent display values; production never imports this module.
const scanner: ScannerResponse = { strategy: "cross_sectional_reversal", summary: {
  total_return: .02, annualized_return: .03, annualized_volatility: .1, sharpe: .3, max_drawdown: -.01,
  average_turnover: .2, average_gross_exposure: 1, average_net_exposure: 0, average_num_longs: 2, average_num_shorts: 2 },
  equity_curve: [], returns: [], exposures: [], turnover: [], latest_ranking: [], latest_rebalance_date: null,
  diagnostics: { n_assets: 20, n_dates: 12, valid_rebalance_dates: 8, skipped_dates: 0, gross_exposure_target: 1,
    cost_bps: 5, rebalance_frequency: "daily", lookback_days: 1, warnings: ["Synthetic universe"] } };
const validation: ScannerValidationResponse = { schema_version: "scanner_validation_v1", input_fingerprint: "a".repeat(64),
  family_fingerprint: "b".repeat(64), result_fingerprint: "c".repeat(64), split_configuration_fingerprint: "d".repeat(64),
  samples: [], folds: [{ label: "purged-fold-0", train_ids: ["s1"], test_ids: ["s2"], purged_ids: ["s3"], embargoed_ids: [],
    fingerprint: "e".repeat(64), trained_parameters: [], training_used_for_fit: false,
    audit: { valid: true, remaining_overlap_count: 0, train_count: 1, test_count: 1, purged_count: 1, embargoed_count: 0 } }],
  candidates: [{ candidate_id: "dollar", status: "available", reason: null, mean_test_net_return: .001, outcomes: [],
    correction: { candidate_id: "dollar", raw_p_value: .01, bonferroni: .03, holm: .03, bh: .03, provenance_status: "declared",
      provenance: {}, state_raw: "below_threshold", state_bonferroni: "below_threshold", state_holm: "below_threshold", state_bh: "below_threshold" } },
    { candidate_id: "beta", status: "unavailable", reason: "Fold-specific frozen estimation unavailable", mean_test_net_return: null, outcomes: [],
      correction: { candidate_id: "beta", raw_p_value: null, bonferroni: null, holm: null, bh: null, provenance_status: "unavailable",
        provenance: {}, state_raw: "unavailable", state_bonferroni: "unavailable", state_holm: "unavailable", state_bh: "unavailable" } }],
  family: { declared_count: 3, included_count: 1, missing_ids: ["sector", "beta"], invalid_ids: [], alpha: .05,
    methods: ["bonferroni", "holm", "bh"], provenance: "declared only", invalid_policy: "reject invalid" },
  material: {}, conventions: {}, caveats: ["Synthetic universe; no validated alpha"], unavailable_statistics: { pbo: "unsupported", dsr: "trials unknown" } };

beforeEach(() => { vi.mocked(api.runScanner).mockResolvedValue(scanner); vi.mocked(api.validateScanner).mockResolvedValue(validation); });

describe("ScannerLabPanel", () => {
  it("keeps the legacy default and computes only after an explicit Run", async () => {
    const { user } = renderWithUser(<ScannerLabPanel />);
    expect(screen.getByLabelText("Portfolio policy")).toHaveValue("legacy");
    expect(api.runScanner).not.toHaveBeenCalled(); expect(api.validateScanner).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Run Scanner" }));
    expect(await screen.findByText("2.00%")).toBeInTheDocument();
    expect(vi.mocked(api.runScanner).mock.calls[0][0].advanced_policy).toBeUndefined();
  });
  it("prefills bounded parameters and declared values without running research", async () => {
    const { user } = renderWithUser(<ScannerLabPanel />);
    await user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    expect(screen.getByLabelText("Universe size (assets)")).toHaveValue(20);
    expect(screen.getByLabelText("Portfolio policy")).toHaveValue("sector");
    await user.click(screen.getByRole("button", { name: "Load declared-p fixture" }));
    expect(screen.getByLabelText("Declared p-values (dollar, sector, beta)")).toHaveValue("0.01,0.04,0.20");
    expect(api.runScanner).not.toHaveBeenCalled(); expect(api.validateScanner).not.toHaveBeenCalled();
  });
  it("sends actual policies, renders corrections/audit, and invalidates edited verdicts", async () => {
    const { user } = renderWithUser(<ScannerLabPanel />);
    await user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    await user.click(screen.getByRole("button", { name: "Load declared-p fixture" }));
    await user.click(screen.getByRole("button", { name: "Validate scanner family" }));
    const table = await screen.findByRole("table", { name: "Scanner candidate corrections" });
    expect(within(table).getByText("0.0100")).toBeInTheDocument();
    expect(within(table).getByText("0.10%")).toBeInTheDocument();
    expect(within(table).getByText("beta: unavailable")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Scanner purged fold audit" })).toBeInTheDocument();
    expect(api.validateScanner).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api.validateScanner).mock.calls[0][0].candidates.map((c) => c.policy.mode)).toEqual(["dollar", "sector", "beta"]);
    await user.clear(screen.getByLabelText("Embargo (calendar days)"));
    expect(screen.queryByTestId("scanner-validation-results")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download validation JSON" })).not.toBeInTheDocument();
  });
  it("allows cleared numeric inputs and rejects malformed p-value tokens", async () => {
    const { user } = renderWithUser(<ScannerLabPanel />);
    await user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    const cap = screen.getByLabelText("Gross / leverage cap");
    await user.clear(cap); expect(cap).toHaveDisplayValue("");
    expect(screen.getByRole("button", { name: "Run Scanner" })).toBeDisabled();
    await user.type(cap, "1");
    await user.type(screen.getByLabelText("Declared p-values (dollar, sector, beta)"), "0.01,abc,0.2");
    expect(screen.getByRole("alert")).toHaveTextContent("three declared p-values");
    expect(screen.getByRole("button", { name: "Validate scanner family" })).toBeDisabled();
    expect(api.validateScanner).not.toHaveBeenCalled();
  });
  it("prevents duplicates and ignores responses after input edits", async () => {
    let resolve!: (value: ScannerResponse) => void;
    vi.mocked(api.runScanner).mockReturnValue(new Promise((done) => { resolve = done; }));
    const { user } = renderWithUser(<ScannerLabPanel />);
    const button = screen.getByRole("button", { name: "Run Scanner" });
    act(() => {
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(button).not.toBeDisabled();
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(api.runScanner).toHaveBeenCalledTimes(1);
    await user.clear(screen.getByLabelText("Cost (bps)"));
    await act(async () => resolve(scanner));
    expect(screen.queryByText("2.00%")).not.toBeInTheDocument();
  });
  it("guards batched duplicate Validate actions and discards the result after a policy edit", async () => {
    let resolve!: (value: ScannerValidationResponse) => void;
    vi.mocked(api.validateScanner).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const { user } = renderWithUser(<ScannerLabPanel />);
    await user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    const button = screen.getByRole("button", { name: "Validate scanner family" });
    act(() => {
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(button).not.toBeDisabled();
      button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(api.validateScanner).toHaveBeenCalledTimes(1);
    expect(api.runScanner).not.toHaveBeenCalled();
    await user.selectOptions(screen.getByLabelText("Portfolio policy"), "beta");
    await act(async () => resolve(validation));
    expect(screen.queryByTestId("scanner-validation-results")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download validation JSON" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validate scanner family" })).toBeEnabled();
  });
  it("does not apply a pending validation failure after leaving and reopening the scanner", async () => {
    let reject!: (reason: Error) => void;
    vi.mocked(api.validateScanner).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
    const first = renderWithUser(<ScannerLabPanel />);
    await first.user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    await first.user.click(screen.getByRole("button", { name: "Validate scanner family" }));
    first.unmount();
    const reopened = renderWithUser(<ScannerLabPanel />);
    await act(async () => reject(new Error("Old request failed")));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByTestId("scanner-validation-results")).not.toBeInTheDocument();
    expect(api.validateScanner).toHaveBeenCalledTimes(1);
    expect(api.runScanner).not.toHaveBeenCalled();
    await reopened.user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    await reopened.user.click(screen.getByRole("button", { name: "Validate scanner family" }));
    expect(await screen.findByTestId("scanner-validation-results")).toBeInTheDocument();
    expect(api.validateScanner).toHaveBeenCalledTimes(2);
  });
  it("downloads the exact completed response through its rendered action and removes export on edits", async () => {
    vi.stubGlobal("Blob", NodeBlob);
    const create = vi.fn((_blob: NodeBlob) => "blob:scanner-completed");
    const revoke = vi.fn();
    vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: create, revokeObjectURL: revoke }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const completed: ScannerValidationResponse = { ...validation,
      material: { request: { scanner: { seed: 42, cost_bps: 5 }, n_folds: 3, embargo_days: 1 },
        panel: { asset_ids: ["SYN001", "SYN002"], source: "synthetic" } },
      conventions: { training_used_for_fit: false, costs: "one-way turnover charged once" } };
    vi.mocked(api.validateScanner).mockResolvedValueOnce(completed);
    const before = JSON.stringify(completed);
    const { user } = renderWithUser(<ScannerLabPanel />);
    await user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    await user.click(screen.getByRole("button", { name: "Validate scanner family" }));
    await user.click(await screen.findByRole("button", { name: "Download validation JSON" }));
    expect(create).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:scanner-completed"));
    expect(JSON.parse(await create.mock.calls[0][0].text())).toEqual(completed);
    expect(JSON.stringify(completed)).toBe(before);
    expect(api.validateScanner).toHaveBeenCalledTimes(1);
    expect(api.runScanner).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText("Seed"));
    await user.type(screen.getByLabelText("Seed"), "43");
    expect(screen.queryByRole("button", { name: "Download validation JSON" })).not.toBeInTheDocument();
    expect(create).toHaveBeenCalledTimes(1);
    expect(api.validateScanner).toHaveBeenCalledTimes(1);
  });
  it("renders a final cash ranking and unavailable sector explicitly", async () => {
    vi.mocked(api.runScanner).mockResolvedValueOnce({ ...scanner, latest_rebalance_date: "2023-06-30",
      latest_ranking: [{ ticker: "SYN001", rank: 1, score: .2, sector: null, side: "neutral", weight: 0 }],
      advanced: { policy: { mode: "sector" }, input_fingerprint: "f".repeat(64), exposure_provenance: "declared",
        factor_provenance: "unavailable", timing: "one execution lag", support_policy: "selected names",
        failed_rebalance: "cash", diagnostics: [], total_rebalances: 1, diagnostics_truncated: false,
        latest_scores: [{ asset_id: "SYN001", raw_score: .2, transformed_score: null, weight: 0, sector: null }],
        realized_net_volatility: 0, caveats: ["Synthetic only"] } });
    const { user } = renderWithUser(<ScannerLabPanel />);
    await user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    await user.click(screen.getByRole("button", { name: "Run Scanner" }));
    const ranking = await screen.findByRole("table", { name: "Latest scanner ranking" });
    expect(within(ranking).getByText("Not available")).toBeInTheDocument();
    expect(within(ranking).getByText("neutral")).toBeInTheDocument();
    expect(within(ranking).getByText("0.0000")).toBeInTheDocument();
    expect(screen.getByText("Latest ranking (raw score) — 2023-06-30")).toBeInTheDocument();
    expect(screen.getByText(/Advanced final gross exposure can differ/)).toBeInTheDocument();
  });
  it("retains useful backend failures", async () => {
    vi.mocked(api.validateScanner).mockRejectedValue(new Error("Backend offline; saved local data remains available after restart"));
    const { user } = renderWithUser(<ScannerLabPanel />);
    await user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    await user.click(screen.getByRole("button", { name: "Validate scanner family" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend offline");
  });
});
