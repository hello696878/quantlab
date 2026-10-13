import { act, screen, within } from "@testing-library/react";
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
    await user.dblClick(screen.getByRole("button", { name: "Run Scanner" }));
    expect(api.runScanner).toHaveBeenCalledTimes(1);
    await user.clear(screen.getByLabelText("Cost (bps)"));
    await act(async () => resolve(scanner));
    expect(screen.queryByText("2.00%")).not.toBeInTheDocument();
  });
  it("retains useful backend failures", async () => {
    vi.mocked(api.validateScanner).mockRejectedValue(new Error("Backend offline; saved local data remains available after restart"));
    const { user } = renderWithUser(<ScannerLabPanel />);
    await user.click(screen.getByRole("button", { name: "Load validation parameters" }));
    await user.click(screen.getByRole("button", { name: "Validate scanner family" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend offline");
  });
});
