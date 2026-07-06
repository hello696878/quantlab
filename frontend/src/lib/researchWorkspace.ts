/**
 * Research Workspace, Saved Presets & Experiment Journal API client
 * (Phase 33.0).
 *
 * Typed client for GET /api/research-workspace/sample and
 * POST /api/research-workspace/analyze. All data is deterministic static
 * illustrative sample data — no live data, no login, no cloud sync;
 * educational only, not investment, trading, asset-allocation, or compliance
 * advice.
 */

export type WorkspaceModuleId =
  | "macro_regime"
  | "portfolio_risk"
  | "scenario_studio"
  | "crypto_derivatives"
  | "defi_risk"
  | "tokenomics"
  | "onchain_analytics"
  | "alternative_data"
  | "market_microstructure";

export type WorkspaceSectionId =
  | "overview"
  | "assumptions"
  | "experiment_summary"
  | "run_comparison"
  | "methodology"
  | "limitations"
  | "next_steps";

export type ConfidenceLabel = "low" | "medium" | "high";
export type SeverityBucket = "low" | "moderate" | "elevated" | "high" | "severe";
export type TimelineStatus = "complete" | "in_progress" | "planned";

export interface ExperimentRunInput {
  run_id: string;
  run_name: string;
  module_id: WorkspaceModuleId;
  scenario_name: string;
  created_at: string;
  key_metric_name: string;
  baseline_value: number;
  stressed_value: number;
  severity_score: number;
  confidence_label: ConfidenceLabel;
  notes: string;
  chart_points?: number[] | null;
}

export interface ResearchWorkspacePreset {
  preset_id: string;
  preset_name: string;
  description: string;
  primary_module: WorkspaceModuleId;
  linked_modules: WorkspaceModuleId[];
  created_at: string;
  tags: string[];
  assumptions: string[];
  limitations: string[];
  experiment_runs: ExperimentRunInput[];
}

export interface WorkspaceAnalysisRequest {
  selected_preset_id: string;
  included_run_ids?: string[] | null;
  user_note?: string | null;
  report_sections: WorkspaceSectionId[];
}

export interface RunComparisonRow {
  run_id: string;
  run_name: string;
  module_id: WorkspaceModuleId;
  scenario_name: string;
  key_metric_name: string;
  baseline_value: number;
  stressed_value: number;
  change: number;
  percent_change: number;
  severity_score: number;
  confidence_label: ConfidenceLabel;
  notes: string;
}

export interface SeveritySummary {
  average_severity: number;
  max_severity: number;
  highest_severity_run_id: string;
  severity_bucket: SeverityBucket;
  workspace_regime: string;
  regime_label: string;
  coverage_score: number;
  reproducibility_score: number;
  drivers: string[];
}

export interface WorkflowTimelineItem {
  step_id: string;
  step_title: string;
  step_description: string;
  status: TimelineStatus;
  linked_module?: WorkspaceModuleId | null;
}

export interface MethodologyChecklistItem {
  item_id: string;
  label: string;
  passed: boolean;
  notes: string;
}

export interface ReportSectionOut {
  section_id: WorkspaceSectionId;
  section_title: string;
  included: boolean;
  markdown: string;
}

export interface ReportPreview {
  title: string;
  subtitle: string;
  sections: ReportSectionOut[];
  markdown: string;
}

export interface ExportPayload {
  markdown: string;
  json_payload: string;
}

export interface ModuleCatalogEntry {
  module_id: WorkspaceModuleId;
  module_label: string;
}

export interface SectionCatalogEntry {
  section_id: WorkspaceSectionId;
  section_title: string;
}

export interface ResearchWorkspaceAnalysisResponse {
  data_status: "static_sample";
  selected_preset: ResearchWorkspacePreset;
  run_comparison: RunComparisonRow[];
  severity_summary: SeveritySummary;
  workflow_timeline: WorkflowTimelineItem[];
  methodology_checklist: MethodologyChecklistItem[];
  report_preview: ReportPreview;
  export_payload: ExportPayload;
  notes: string[];
  disclaimer: string;
}

export interface ResearchWorkspaceSampleResponse {
  presets: ResearchWorkspacePreset[];
  modules: ModuleCatalogEntry[];
  sections: SectionCatalogEntry[];
  default_request: WorkspaceAnalysisRequest;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Research Workspace.");
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
  return res.status >= 500 ? "Server error computing research-workspace analytics." : `HTTP ${res.status}`;
}

/** GET /api/research-workspace/sample */
export async function fetchResearchWorkspaceSample(
  signal?: AbortSignal,
): Promise<ResearchWorkspaceSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/research-workspace/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<ResearchWorkspaceSampleResponse>;
}

/** POST /api/research-workspace/analyze */
export async function analyzeResearchWorkspace(
  request: WorkspaceAnalysisRequest,
  signal?: AbortSignal,
): Promise<ResearchWorkspaceAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/research-workspace/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<ResearchWorkspaceAnalysisResponse>;
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

/** Percentage change display; "—" when the baseline is ~zero (guarded on the backend). */
export function pctChange(value: number, baseline: number, digits = 1): string {
  if (Math.abs(baseline) < 1e-9) return "—";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}
