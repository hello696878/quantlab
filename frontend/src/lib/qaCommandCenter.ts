/**
 * Release Readiness, Smoke Test Matrix & QA Command Center API client
 * (Phase 36.0).
 *
 * Typed client for GET /api/qa-command-center/sample and
 * POST /api/qa-command-center/analyze. Everything is hand-maintained static
 * QA METADATA about QuantLab's own modules — verification commands are
 * listed, never run, and nothing here claims tests or builds were executed.
 * Educational only — not a compliance system, not investment or trading
 * advice.
 */

export type ReleaseStatus = "ready" | "needs_review" | "experimental" | "blocked";
export type QaPriority = "critical" | "high" | "medium" | "low";

export type QaDataMode =
  | "static_sample"
  | "delayed_sample"
  | "user_input"
  | "local_calculation"
  | "optional_external_provider";

export type QaSectionId =
  | "overview"
  | "readiness_summary"
  | "smoke_test_matrix"
  | "regression_checklist"
  | "command_checklist"
  | "known_limitations"
  | "release_notes"
  | "release_decision";

export type ReleaseDecision = "ready_for_demo" | "ready_with_limitations" | "needs_review" | "blocked";

export interface QAModuleRow {
  module_id: string;
  module_name: string;
  category: string;
  route: string;
  has_backend_endpoint: boolean;
  has_frontend_page: boolean;
  has_charts: boolean;
  has_interactive_controls: boolean;
  has_formula_panel: boolean;
  has_tests: boolean;
  demo_safe: boolean;
  data_mode: QaDataMode;
  release_status: ReleaseStatus;
  priority: QaPriority;
  smoke_test_steps: string[];
  manual_regression_steps: string[];
  known_limitations: string[];
}

export interface QACommandCenterRequest {
  selected_category?: string | null;
  selected_release_statuses?: ReleaseStatus[] | null;
  selected_priorities?: QaPriority[] | null;
  include_manual_steps: boolean;
  include_backend_checks: boolean;
  include_frontend_checks: boolean;
  include_known_limitations: boolean;
  report_sections: QaSectionId[];
}

export interface ReadinessSummary {
  module_count: number;
  ready_rate: number;
  smoke_coverage: number;
  test_coverage: number;
  interactive_coverage: number;
  chart_coverage: number;
  release_score: number;
  release_decision: ReleaseDecision;
  critical_blockers: string[];
  drivers: string[];
}

export interface SmokeTestRow {
  module_id: string;
  module_name: string;
  route: string;
  steps: string[];
  expected_result: string;
  status_label: ReleaseStatus;
}

export interface RegressionGroup {
  category: string;
  category_label: string;
  items: string[];
}

export interface CommandChecklist {
  backend_test_command: string;
  frontend_typecheck_command: string;
  frontend_build_command_for_user: string;
  backend_run_command: string;
  notes: string[];
}

export interface LimitationRow {
  module_id: string;
  module_name: string;
  data_mode: QaDataMode;
  limitations: string[];
}

export interface ReportSectionOut {
  section_id: QaSectionId;
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
  section_id: QaSectionId;
  section_title: string;
}

export interface CategoryCatalogEntry {
  category: string;
  category_label: string;
}

export interface QACommandCenterAnalysisResponse {
  data_status: "static_sample";
  qa_modules: QAModuleRow[];
  readiness_summary: ReadinessSummary;
  smoke_test_matrix: SmokeTestRow[];
  regression_checklist: RegressionGroup[];
  command_checklist: CommandChecklist;
  limitation_tracker: LimitationRow[];
  release_notes: string[];
  generated_report: GeneratedReport;
  export_payload: ExportPayload;
  notes: string[];
  disclaimer: string;
}

export interface QACommandCenterSampleResponse {
  qa_modules: QAModuleRow[];
  sections: SectionCatalogEntry[];
  categories: CategoryCatalogEntry[];
  release_statuses: ReleaseStatus[];
  priorities: QaPriority[];
  default_request: QACommandCenterRequest;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the QA Command Center.");
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
  return res.status >= 500 ? "Server error computing QA analytics." : `HTTP ${res.status}`;
}

/** GET /api/qa-command-center/sample */
export async function fetchQACommandCenterSample(
  signal?: AbortSignal,
): Promise<QACommandCenterSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/qa-command-center/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<QACommandCenterSampleResponse>;
}

/** POST /api/qa-command-center/analyze */
export async function analyzeQACommandCenter(
  request: QACommandCenterRequest,
  signal?: AbortSignal,
): Promise<QACommandCenterAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/qa-command-center/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<QACommandCenterAnalysisResponse>;
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

export const STATUS_LABELS: Record<ReleaseStatus, string> = {
  ready: "Ready",
  needs_review: "Needs review",
  experimental: "Experimental",
  blocked: "Blocked",
};

export const PRIORITY_LABELS: Record<QaPriority, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const DECISION_LABELS: Record<ReleaseDecision, string> = {
  ready_for_demo: "Ready for demo",
  ready_with_limitations: "Ready with limitations",
  needs_review: "Needs review",
  blocked: "Blocked",
};

export const QA_DATA_MODE_LABELS: Record<QaDataMode, string> = {
  static_sample: "Static sample",
  delayed_sample: "Delayed sample",
  user_input: "User input",
  local_calculation: "Local calculation",
  optional_external_provider: "Optional external provider",
};
