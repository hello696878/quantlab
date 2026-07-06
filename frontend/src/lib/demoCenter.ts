/**
 * Product Demo Center, Guided Walkthroughs & Module Health Dashboard API
 * client (Phase 34.0).
 *
 * Typed client for GET /api/demo-center/sample and
 * POST /api/demo-center/analyze. Everything is hand-written static demo
 * METADATA about QuantLab's own modules — no live data, no telemetry, no
 * login; educational only, not investment, trading, asset-allocation, or
 * compliance advice.
 */

export type AudienceId =
  | "founder"
  | "investor"
  | "quant_researcher"
  | "recruiter"
  | "student"
  | "general";

export type ScriptSectionId =
  | "opening"
  | "product_overview"
  | "guided_steps"
  | "module_highlights"
  | "limitations"
  | "closing";

export type ModuleStatus = "stable_demo" | "review_needed" | "experimental" | "static_sample_only";
export type DataMode = "static_sample" | "delayed_sample" | "user_input" | "local_calculation";

export interface DemoStep {
  step_id: string;
  title: string;
  description: string;
  linked_module: string;
  route: string;
  expected_user_action: string;
  expected_output: string;
  demo_tip: string;
}

export interface DemoPath {
  path_id: string;
  title: string;
  audience: AudienceId;
  estimated_minutes: number;
  summary: string;
  modules: string[];
  steps: DemoStep[];
  learning_goals: string[];
  suggested_talking_points: string[];
  limitations: string[];
  output_artifacts: string[];
}

export interface ModuleHealthRow {
  module_id: string;
  module_name: string;
  category: string;
  route: string;
  status: ModuleStatus;
  data_mode: DataMode;
  has_backend_endpoint: boolean;
  has_charts: boolean;
  has_interactive_controls: boolean;
  has_formula_panel: boolean;
  has_report_export: boolean;
  limitations: string[];
  recommended_demo_path: string;
  last_review_label: string;
}

export interface DemoCenterRequest {
  selected_path_id: string;
  selected_audience: AudienceId;
  included_modules?: string[] | null;
  script_sections: ScriptSectionId[];
  time_budget_minutes: number;
  include_limitations: boolean;
  include_technical_notes: boolean;
}

export interface PathSummary {
  path_id: string;
  title: string;
  audience: AudienceId;
  estimated_minutes: number;
  module_count: number;
  step_count: number;
  talking_point_count: number;
  fits_time_budget: boolean;
  time_note: string;
}

export interface CapabilityMatrixRow {
  module_id: string;
  module_name: string;
  category: string;
  has_backend_endpoint: boolean;
  has_charts: boolean;
  has_interactive_controls: boolean;
  has_formula_panel: boolean;
  has_report_export: boolean;
  capability_score: number;
}

export interface ReadinessSummary {
  included_module_count: number;
  category_coverage: number;
  readiness_score: number;
  demo_complexity_score: number;
  script_coverage: number;
  top_ready_modules: string[];
  review_needed_modules: string[];
}

export interface CompletionChecklistItem {
  item_id: string;
  label: string;
  passed: boolean;
  notes: string;
}

export interface ScriptSectionOut {
  section_id: ScriptSectionId;
  section_title: string;
  included: boolean;
  markdown: string;
}

export interface GeneratedScript {
  title: string;
  subtitle: string;
  sections: ScriptSectionOut[];
  markdown: string;
}

export interface ExportPayload {
  markdown: string;
  json_payload: string;
}

export interface SectionCatalogEntry {
  section_id: ScriptSectionId;
  section_title: string;
}

export interface DemoCenterAnalysisResponse {
  data_status: "static_sample";
  selected_path: DemoPath;
  demo_paths: DemoPath[];
  module_health: ModuleHealthRow[];
  path_summary: PathSummary;
  readiness_summary: ReadinessSummary;
  capability_matrix: CapabilityMatrixRow[];
  completion_checklist: CompletionChecklistItem[];
  generated_script: GeneratedScript;
  export_payload: ExportPayload;
  notes: string[];
  disclaimer: string;
}

export interface DemoCenterSampleResponse {
  demo_paths: DemoPath[];
  module_health: ModuleHealthRow[];
  script_sections: SectionCatalogEntry[];
  audiences: AudienceId[];
  default_request: DemoCenterRequest;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Demo Center.");
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
  return res.status >= 500 ? "Server error computing demo-center analytics." : `HTTP ${res.status}`;
}

/** GET /api/demo-center/sample */
export async function fetchDemoCenterSample(
  signal?: AbortSignal,
): Promise<DemoCenterSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/demo-center/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<DemoCenterSampleResponse>;
}

/** POST /api/demo-center/analyze */
export async function analyzeDemoCenter(
  request: DemoCenterRequest,
  signal?: AbortSignal,
): Promise<DemoCenterAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/demo-center/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<DemoCenterAnalysisResponse>;
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

export const STATUS_LABELS: Record<ModuleStatus, string> = {
  stable_demo: "Stable demo",
  review_needed: "Review needed",
  experimental: "Experimental",
  static_sample_only: "Static sample only",
};

export const DATA_MODE_LABELS: Record<DataMode, string> = {
  static_sample: "Static sample",
  delayed_sample: "Delayed sample",
  user_input: "User input",
  local_calculation: "Local calculation",
};

export const AUDIENCE_LABELS: Record<AudienceId, string> = {
  founder: "Founder",
  investor: "Investor",
  quant_researcher: "Quant researcher",
  recruiter: "Recruiter",
  student: "Student",
  general: "General",
};
