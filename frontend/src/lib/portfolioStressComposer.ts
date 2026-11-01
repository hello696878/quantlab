import { BacktestApiError } from "./api";
import type { RebalanceRow, RunFull as PortfolioRun } from "./portfolioDiagnostics";
import type { AssetShockRunCreate, MissingShockPolicy } from "./portfolioStress";

export interface ComposerSource {
  portfolio: PortfolioRun;
  rebalance: RebalanceRow;
}

export interface ComposerDraft {
  name: string;
  shocks: Record<string, string>;
  missingPolicy: MissingShockPolicy;
  notional: string;
}

export function shockText(shocks: Record<string, string>, assetId: string): string {
  return Object.prototype.hasOwnProperty.call(shocks, assetId) ? shocks[assetId] : "";
}

function finiteNumber(raw: string, label: string): number {
  const text = raw.trim();
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(text) || !Number.isFinite(Number(text))) {
    throw new Error(`${label} must be a finite number.`);
  }
  return Number(text);
}

export function buildAssetShockRun(source: ComposerSource | null, draft: ComposerDraft): AssetShockRunCreate {
  if (!source || source.portfolio.status !== "completed" || !Number.isInteger(source.portfolio.id) || source.portfolio.id <= 0 ||
      !Number.isInteger(source.rebalance.rebalance_id) || source.rebalance.rebalance_id < 0 ||
      !source.rebalance.weights || !Object.keys(source.rebalance.weights).length) {
    throw new Error("Select a completed portfolio and a rebalance with stored weights.");
  }
  const name = draft.name.trim();
  if (!name || name.length > 200) throw new Error("Name must contain 1 to 200 characters after trimming.");
  if (draft.missingPolicy !== "zero" && draft.missingPolicy !== "unavailable") throw new Error("Choose a missing-shock policy.");
  const assets = new Set(source.portfolio.universe.assets.map((asset) => asset.asset_id));
  if (Object.keys(draft.shocks).some((id) => !assets.has(id))) throw new Error("Shocks contain an asset outside the selected portfolio.");
  const entries = source.portfolio.universe.assets.flatMap(({ asset_id }) => {
    const raw = shockText(draft.shocks, asset_id);
    if (!raw.trim()) return [];
    const value = finiteNumber(raw, `Shock for ${asset_id}`);
    if (value < -100 || value > 100) throw new Error(`Shock for ${asset_id} must be between -100% and +100%.`);
    return [[asset_id, { value, unit: "percent" as const }] as const];
  });
  if (!entries.length) throw new Error("Supply at least one asset shock; blank is not zero.");
  const payload: AssetShockRunCreate = {
    name,
    portfolio_run_id: source.portfolio.id,
    portfolio_rebalance_id: source.rebalance.rebalance_id,
    scenario: { scenario_definition_id: "ui_asset_shock_v1", name, scenario_type: "hypothetical_asset_shock",
      source: "user", missing_shock_policy: draft.missingPolicy, asset_shocks: Object.fromEntries(entries) },
  };
  if (draft.notional.trim()) {
    const notional = finiteNumber(draft.notional, "Notional");
    if (notional <= 0) throw new Error("Notional must be greater than zero.");
    payload.notional = notional;
  }
  return payload;
}

/** A lost write response cannot establish whether persistence happened. */
export function creationOutcomeUnknown(error: unknown): boolean {
  return !(error instanceof BacktestApiError && [400, 401, 403, 404, 409, 422].includes(error.status));
}
