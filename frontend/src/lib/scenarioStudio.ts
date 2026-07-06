/**
 * Unified Scenario Studio & Cross-Lab Report Builder API client (Phase 32.0).
 *
 * Typed client for GET /api/scenario-studio/sample and
 * POST /api/scenario-studio/analyze. All data is deterministic static
 * illustrative sample data — no live macro, market, crypto, or news data;
 * educational only, not investment, trading, or asset-allocation advice.
 */

export type ScenarioModuleId =
  | "macro_regime"
  | "portfolio_risk"
  | "crypto_derivatives"
  | "defi_risk"
  | "tokenomics"
  | "onchain_analytics"
  | "alternative_data"
  | "market_microstructure";

export type ReportSectionId =
  | "executive_summary"
  | "macro"
  | "portfolio"
  | "crypto"
  | "defi"
  | "tokenomics"
  | "onchain"
  | "alternative_data"
  | "limitations";

export type ImpactBucket = "low" | "moderate" | "elevated" | "high" | "severe";

export interface ScenarioTemplateInput {
  scenario_id: string;
  scenario_name: string;
  description: string;
  growth_shock: number;
  inflation_shock: number;
  policy_shock: number;
  liquidity_shock: number;
  credit_shock: number;
  usd_shock: number;
  equity_shock: number;
  rate_shock: number;
  credit_spread_shock: number;
  crypto_price_shock: number;
  funding_rate_shock: number;
  defi_liquidity_shock: number;
  stablecoin_depeg_shock: number;
  whale_concentration_shock: number;
  sentiment_shock: number;
  volatility_multiplier: number;
  token_unlock_multiplier: number;
  exchange_inflow_multiplier: number;
  publication_lag_shock: number;
}

/** The 19 editable shock keys on a template (everything except the id/name/description). */
export type ShockKey = Exclude<
  keyof ScenarioTemplateInput,
  "scenario_id" | "scenario_name" | "description"
>;

export type ScenarioShockOverrides = Partial<Record<ShockKey, number>>;

export interface ScenarioStudioRequest {
  selected_scenario_id: string;
  custom_overrides?: ScenarioShockOverrides | null;
  included_modules: ScenarioModuleId[];
  report_sections: ReportSectionId[];
}

export interface ModuleImpactRow {
  module_id: ScenarioModuleId;
  module_label: string;
  baseline_score: number;
  stressed_score: number;
  impact_score: number;
  impact_bucket: ImpactBucket;
  drivers: string[];
  notes: string[];
}

export interface ScenarioRegime {
  regime_id: string;
  regime_label: string;
  severity_score: number;
  drivers: string[];
  explanation: string;
  notes: string[];
}

export interface BaselineStressRow {
  metric_name: string;
  baseline_value: number;
  stressed_value: number;
  change: number;
  module_id: ScenarioModuleId;
}

export interface HeatmapCell {
  row_label: string;
  column_label: string;
  value: number;
  bucket: ImpactBucket;
}

export interface ReportSection {
  section_id: ReportSectionId;
  section_title: string;
  included: boolean;
  markdown: string;
}

export interface GeneratedReport {
  title: string;
  subtitle: string;
  sections: ReportSection[];
  markdown: string;
  limitations: string[];
}

export interface ReportBuilderSummary {
  available_sections: ReportSectionId[];
  included_sections: ReportSectionId[];
  section_coverage: number;
  notes: string[];
}

export interface GlobalShockRow {
  shock_id: string;
  shock_label: string;
  value: number;
  neutral_value: number;
  overridden: boolean;
}

export interface ModuleCatalogEntry {
  module_id: ScenarioModuleId;
  module_label: string;
}

export interface SectionCatalogEntry {
  section_id: ReportSectionId;
  section_title: string;
}

export interface ScenarioStudioAnalysisResponse {
  data_status: "static_sample";
  selected_scenario: ScenarioTemplateInput;
  global_shocks: GlobalShockRow[];
  module_impacts: ModuleImpactRow[];
  composite_severity: number;
  scenario_regime: ScenarioRegime;
  baseline_vs_stress: BaselineStressRow[];
  heatmap: HeatmapCell[];
  report_builder: ReportBuilderSummary;
  generated_report: GeneratedReport;
  notes: string[];
  disclaimer: string;
}

export interface ScenarioStudioSampleResponse {
  templates: ScenarioTemplateInput[];
  modules: ModuleCatalogEntry[];
  sections: SectionCatalogEntry[];
  default_request: ScenarioStudioRequest;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Scenario Studio.");
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  } catch {
    // ignore — fall through to status text
  }
  return res.status >= 500 ? "Server error computing scenario-studio analytics." : `HTTP ${res.status}`;
}

/** GET /api/scenario-studio/sample */
export async function fetchScenarioStudioSample(
  signal?: AbortSignal,
): Promise<ScenarioStudioSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/scenario-studio/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<ScenarioStudioSampleResponse>;
}

/** POST /api/scenario-studio/analyze */
export async function analyzeScenarioStudio(
  request: ScenarioStudioRequest,
  signal?: AbortSignal,
): Promise<ScenarioStudioAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/scenario-studio/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<ScenarioStudioAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function num(value: number, digits = 2): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signedNum(value: number, digits = 2): string {
  return `${value >= 0 ? "+" : ""}${num(value, digits)}`;
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number, digits = 1): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}
