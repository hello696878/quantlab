/**
 * Data Mode Registry, Offline Fixtures & API Reliability Center API client
 * (Phase 35.0).
 *
 * Typed client for GET /api/data-reliability/sample and
 * POST /api/data-reliability/analyze. Everything is hand-maintained static
 * reliability METADATA about QuantLab's own modules, providers, and fixtures
 * — this layer never calls the providers it describes and never guarantees
 * external availability. Educational only — not investment, trading, or
 * compliance advice.
 */

export type DataMode =
  | "static_sample"
  | "delayed_sample"
  | "user_input"
  | "local_calculation"
  | "optional_external_provider";

export type ProviderType = "market_data" | "macro_data" | "static_fixture" | "local_calculation" | "user_input";
export type FailureMode = "fallback_to_fixture" | "friendly_error" | "disabled_in_tests" | "static_only";
export type FixtureType = "price_series" | "macro_series" | "scenario_template" | "lab_sample" | "report_sample";

export type ReliabilitySectionId =
  | "overview"
  | "module_modes"
  | "providers"
  | "offline_fixtures"
  | "test_safety"
  | "limitations"
  | "recommendations";

export interface ModuleDataModeRow {
  module_id: string;
  module_name: string;
  category: string;
  route: string;
  data_mode: DataMode;
  demo_safe: boolean;
  test_safe: boolean;
  external_provider_required: boolean;
  offline_fallback_available: boolean;
  default_demo_deterministic: boolean;
  provider_names: string[];
  fixture_names: string[];
  failure_behavior: string;
  user_visible_label: string;
  limitations: string[];
  recommended_handling: string;
}

export interface ProviderRow {
  provider_id: string;
  provider_name: string;
  provider_type: ProviderType;
  used_by_modules: string[];
  is_external: boolean;
  requires_network: boolean;
  requires_api_key: boolean;
  allowed_in_tests: boolean;
  has_offline_fallback: boolean;
  default_failure_mode: FailureMode;
  limitations: string[];
  user_message: string;
}

export interface OfflineFixtureRow {
  fixture_id: string;
  fixture_name: string;
  fixture_type: FixtureType;
  used_by_modules: string[];
  observation_count: number;
  date_range_label: string;
  deterministic: boolean;
  test_safe: boolean;
  description: string;
  limitations: string[];
}

export interface DataReliabilityRequest {
  selected_category?: string | null;
  include_external_providers: boolean;
  include_static_fixtures: boolean;
  include_test_safety: boolean;
  selected_modules?: string[] | null;
  report_sections: ReliabilitySectionId[];
}

export interface ReliabilitySummary {
  module_count: number;
  demo_safe_rate: number;
  test_safe_rate: number;
  fallback_coverage: number;
  external_provider_exposure: number;
  reliability_score: number;
  reliability_bucket: string;
  drivers: string[];
}

export interface TestSafetyRow {
  module_id: string;
  module_name: string;
  test_safe: boolean;
  external_provider_required: boolean;
  notes: string;
}

export interface FallbackRow {
  module_id: string;
  module_name: string;
  external_provider_required: boolean;
  offline_fallback_available: boolean;
  failure_behavior: string;
}

export interface ReportSectionOut {
  section_id: ReliabilitySectionId;
  section_title: string;
  included: boolean;
  markdown: string;
}

export interface GeneratedReport {
  title: string;
  subtitle: string;
  sections: ReportSectionOut[];
  markdown: string;
}

export interface ExportPayload {
  markdown: string;
  json_payload: string;
}

export interface SectionCatalogEntry {
  section_id: ReliabilitySectionId;
  section_title: string;
}

export interface CategoryCatalogEntry {
  category: string;
  category_label: string;
}

export interface DataReliabilityAnalysisResponse {
  data_status: "static_sample";
  module_modes: ModuleDataModeRow[];
  providers: ProviderRow[];
  offline_fixtures: OfflineFixtureRow[];
  reliability_summary: ReliabilitySummary;
  test_safety_matrix: TestSafetyRow[];
  fallback_matrix: FallbackRow[];
  generated_report: GeneratedReport;
  export_payload: ExportPayload;
  notes: string[];
  disclaimer: string;
}

export interface DataReliabilitySampleResponse {
  module_modes: ModuleDataModeRow[];
  providers: ProviderRow[];
  offline_fixtures: OfflineFixtureRow[];
  sections: SectionCatalogEntry[];
  categories: CategoryCatalogEntry[];
  default_request: DataReliabilityRequest;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Data Reliability Center.");
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
  return res.status >= 500 ? "Server error computing data-reliability analytics." : `HTTP ${res.status}`;
}

/** GET /api/data-reliability/sample */
export async function fetchDataReliabilitySample(
  signal?: AbortSignal,
): Promise<DataReliabilitySampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/data-reliability/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<DataReliabilitySampleResponse>;
}

/** POST /api/data-reliability/analyze */
export async function analyzeDataReliability(
  request: DataReliabilityRequest,
  signal?: AbortSignal,
): Promise<DataReliabilityAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/data-reliability/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<DataReliabilityAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function num(value: number, digits = 2): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function pct(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export const DATA_MODE_LABELS: Record<DataMode, string> = {
  static_sample: "Static sample",
  delayed_sample: "Delayed sample",
  user_input: "User input",
  local_calculation: "Local calculation",
  optional_external_provider: "Optional external provider",
};

export const FAILURE_MODE_LABELS: Record<FailureMode, string> = {
  fallback_to_fixture: "Falls back to fixture",
  friendly_error: "Friendly error",
  disabled_in_tests: "Disabled in tests",
  static_only: "Static only",
};

export const FIXTURE_TYPE_LABELS: Record<FixtureType, string> = {
  price_series: "Price series",
  macro_series: "Macro series",
  scenario_template: "Scenario template",
  lab_sample: "Lab sample",
  report_sample: "Report sample",
};

export const BUCKET_LABELS: Record<string, string> = {
  highly_deterministic: "Highly deterministic",
  mostly_deterministic: "Mostly deterministic",
  mixed: "Mixed",
  external_dependent: "External-dependent",
};
