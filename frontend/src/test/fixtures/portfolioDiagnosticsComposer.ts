import type { RunFull } from "@/lib/portfolioDiagnostics";

// Deterministic test inputs, never imported by production components.
export function returnInput(count = 24, ids = ["a", "b"]) {
  return { frequency: "daily", timestamps: Array.from({ length: count }, (_, i) => new Date(Date.UTC(2024, 0, i + 1)).toISOString().slice(0, 10)),
    assets: ids.map((asset_id, j) => ({ asset_id, returns: Array.from({ length: count }, (_, i) => ((i * (j + 3) % 11) - 5) / 1000) })) };
}

export function diagnosticRun(overrides: Partial<RunFull> = {}): RunFull {
  return { id: 51, name: "My supplied portfolio", status: "completed", method: "user_supplied", covariance_method: "sample",
    integrity_status: "declared", solver_status: "closed_form", asset_count: 2, observation_count: 24, rebalance_count: 1,
    constraint_violation_count: 0, warnings: ["Weights are self-declared."], configuration: { user_provenance: { basis: "declared", lag: null } },
    universe: { ...returnInput(), assets: [{ asset_id: "a", name: "Asset A", group: null }, { asset_id: "b", name: "Asset B", group: null }] },
    portfolio_volatility: null, effective_positions: null, max_budget_deviation: null, mean_turnover: null,
    risk: null, budget: null, concentration: null, covariance: null, regimes: null,
    is_baseline: false, error_message: null, universe_fingerprint: "u", constraint_fingerprint: "c", configuration_fingerprint: "f",
    result_fingerprint: "r", created_at: "2024-01-24", updated_at: "2024-01-24", notes: "", description: "",
    ...overrides } as RunFull;
}
