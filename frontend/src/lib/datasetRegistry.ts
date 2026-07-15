/**
 * API client + types for the Data Provenance & Dataset Lineage registry
 * (Phase 49.0).  All requests go to /api/* which Next.js rewrites to the
 * FastAPI backend.  Reuses the shared BacktestApiError semantics.
 */

import { BacktestApiError } from "./api";

// ---------------------------------------------------------------------------
// Types (mirror backend Pydantic models)
// ---------------------------------------------------------------------------

export type ProvenanceStatus = "complete" | "partial" | "unknown" | "invalidated";
export type QualityStatus = "passed" | "warning" | "failed" | "skipped" | "unknown";
export type DriftClass = "none" | "compatible" | "potentially_breaking" | "breaking" | "unknown";

export interface DatasetSummary {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  domain: string;
  dataset_type: string;
  source_type: string;
  provider: string | null;
  format: string;
  frequency: string | null;
  asset_class: string | null;
  schema_version: string | null;
  current_version_id: number | null;
  tags: string[];
  is_demo: boolean;
  is_active: boolean;
  provenance_status: ProvenanceStatus;
  version_count: number;
  latest_quality_status: QualityStatus | null;
  latest_row_count: number | null;
  latest_date_range: string | null;
  latest_manifest_fingerprint: string | null;
  linked_experiment_count: number;
}

export interface DatasetFull extends DatasetSummary {
  description: string;
  source_reference: string | null;
  license_name: string | null;
  license_url: string | null;
  symbol_scope: string | null;
  timezone: string | null;
  metadata: Record<string, unknown>;
  notes: string;
}

export interface VersionSummary {
  id: number;
  dataset_id: number;
  dataset_name: string | null;
  version_label: string;
  created_at: string;
  row_count: number | null;
  column_count: number | null;
  start_time: string | null;
  end_time: string | null;
  format: string;
  deterministic: boolean;
  quality_status: QualityStatus;
  validation_status: string;
  manifest_fingerprint: string;
  schema_fingerprint: string | null;
  content_fingerprint: string | null;
  storage_locator_type: string;
  storage_locator: string;
  invalidated_at: string | null;
  is_current: boolean;
}

export interface VersionFull extends VersionSummary {
  effective_from: string | null;
  effective_to: string | null;
  source_fingerprint: string | null;
  file_size_bytes: number | null;
  compression: string | null;
  ingestion_method: string;
  schema_snapshot: { fields?: { name: string; type: string; nullable: boolean }[]; ordering_significant?: boolean };
  statistics_summary: Record<string, unknown>;
  provenance: Record<string, unknown>;
  invalidation_reason: string | null;
}

export interface LineageEdge {
  id: number;
  parent_version_id: number;
  child_version_id: number;
  relationship_type: string;
  transformation_name: string;
  transformation_version: string | null;
  parameters: Record<string, unknown>;
  code_reference: string | null;
  git_commit: string | null;
  created_at: string;
  notes: string;
}

export interface LineageNode {
  version_id: number;
  dataset_id: number;
  dataset_name: string;
  version_label: string;
  quality_status: QualityStatus;
  invalidated: boolean;
  is_demo: boolean;
  depth: number;
  direction: "self" | "ancestor" | "descendant";
}

export interface LineageGraph {
  root_version_id: number;
  nodes: LineageNode[];
  edges: LineageEdge[];
  truncated: boolean;
  max_depth: number;
  node_limit: number;
}

export interface QualityResult {
  id: number;
  dataset_version_id: number;
  check_name: string;
  check_category: string;
  status: QualityStatus;
  severity: string;
  observed_value: string | null;
  expected_value: string | null;
  message: string;
  checked_at: string;
  checker_version: string;
  details: Record<string, unknown>;
}

export interface ExperimentLink {
  id: number;
  experiment_id: number;
  experiment_name: string | null;
  dataset_version_id: number;
  dataset_name: string | null;
  version_label: string | null;
  role: string;
  created_at: string;
  notes: string;
  fingerprint_match: boolean | null;
}

export interface DatasetListResponse {
  items: DatasetSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface RegistrySummary {
  datasets: number;
  versions: number;
  derived_versions: number;
  quality_failures: number;
  unknown_provenance: number;
  linked_experiments: number;
  source_types: Record<string, number>;
  domains: string[];
  formats: string[];
  tags: string[];
}

export interface DriftEntry {
  kind: string;
  field: string | null;
  a: unknown;
  b: unknown;
  note: string;
}

export interface VersionComparison {
  a_id: number;
  b_id: number;
  identity: DriftEntry[];
  schema_drift: DriftEntry[];
  drift_class: DriftClass;
  metrics: DriftEntry[];
  fingerprints: Record<string, boolean>;
  quality: Record<string, string[]>;
  provenance_changes: DriftEntry[];
}

export interface DatasetExport {
  schema_version: string;
  exported_at: string;
  filters: Record<string, unknown>;
  datasets: DatasetFull[];
  versions: VersionFull[];
  lineage: LineageEdge[];
  quality_results: QualityResult[];
  experiment_links: ExperimentLink[];
}

export interface DemoSeedResponse {
  created_datasets: number;
  created_versions: number;
  created_edges: number;
  created_quality_results: number;
  created_links: number;
  skipped_existing: number;
}

export interface DatasetFilters {
  source_type?: string;
  domain?: string;
  asset_class?: string;
  format?: string;
  frequency?: string;
  demo?: boolean;
  active?: boolean;
  provenance_status?: string;
  quality_status?: string;
  tag?: string;
  query?: string;
}

export interface ListParams extends DatasetFilters {
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

function backendUnavailableMessage(status: number): string {
  return (
    `Backend request failed (HTTP ${status}). ` +
    "Make sure the FastAPI backend is running at BACKEND_URL, " +
    "or http://localhost:8000 by default."
  );
}

function formatDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => {
        if (!d || typeof d !== "object") return null;
        const item = d as { loc?: unknown[]; msg?: unknown };
        if (typeof item.msg !== "string") return null;
        const field =
          Array.isArray(item.loc) && item.loc.length > 0
            ? String(item.loc[item.loc.length - 1])
            : null;
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .filter((m): m is string => Boolean(m));
    if (msgs.length > 0) return msgs.join("; ");
  }
  return fallback;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new BacktestApiError(0, backendUnavailableMessage(0));
  }
  if (!res.ok) {
    let message =
      res.status >= 500 ? backendUnavailableMessage(res.status) : `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = formatDetail(body?.detail, message);
    } catch {
      // keep status message
    }
    throw new BacktestApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

function toQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export function getDatasetSummary(): Promise<RegistrySummary> {
  return request<RegistrySummary>("/datasets/summary");
}

export function listDatasets(params: ListParams = {}): Promise<DatasetListResponse> {
  return request<DatasetListResponse>(`/datasets${toQuery(params as Record<string, unknown>)}`);
}

export function getDataset(id: number): Promise<DatasetFull> {
  return request<DatasetFull>(`/datasets/${id}`);
}

export function listDatasetVersions(datasetId: number): Promise<VersionSummary[]> {
  return request<VersionSummary[]>(`/datasets/${datasetId}/versions`);
}

export function getDatasetVersion(versionId: number): Promise<VersionFull> {
  return request<VersionFull>(`/dataset-versions/${versionId}`);
}

export function getLineage(
  versionId: number,
  params: { max_depth?: number; node_limit?: number } = {},
): Promise<LineageGraph> {
  return request<LineageGraph>(
    `/dataset-versions/${versionId}/lineage${toQuery(params as Record<string, unknown>)}`,
  );
}

export function listVersionQuality(versionId: number): Promise<QualityResult[]> {
  return request<QualityResult[]>(`/dataset-versions/${versionId}/quality`);
}

export function listVersionExperiments(versionId: number): Promise<ExperimentLink[]> {
  return request<ExperimentLink[]>(`/dataset-versions/${versionId}/experiments`);
}

export function listExperimentDatasets(experimentId: number): Promise<ExperimentLink[]> {
  return request<ExperimentLink[]>(`/experiment-registry/experiments/${experimentId}/datasets`);
}

export function compareVersions(a: number, b: number): Promise<VersionComparison> {
  return request<VersionComparison>(`/dataset-versions/compare?a=${a}&b=${b}`);
}

export function exportDatasets(filters: DatasetFilters = {}): Promise<DatasetExport> {
  return request<DatasetExport>(`/datasets/export${toQuery(filters as Record<string, unknown>)}`);
}

export function seedDemoLineage(): Promise<DemoSeedResponse> {
  return request<DemoSeedResponse>("/datasets/demo-seed", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  deterministic_fixture: "Fixture",
  local_file: "Local file",
  generated: "Generated",
  derived: "Derived",
  optional_provider: "Provider (opt-in)",
  manual: "Manual",
  unknown: "Unknown",
};

export const DRIFT_LABELS: Record<DriftClass, string> = {
  none: "No drift",
  compatible: "Compatible",
  potentially_breaking: "Potentially breaking",
  breaking: "Breaking",
  unknown: "Unknown",
};

export function shortFp(value: string | null | undefined): string {
  return value ? value.slice(0, 12) : "—";
}

export function fmtTs(iso: string | null | undefined): string {
  return iso ? iso.replace("T", " ").slice(0, 19) : "—";
}

export function fmtRange(a: string | null, b: string | null): string {
  if (!a && !b) return "—";
  return `${(a ?? "?").slice(0, 10)} → ${(b ?? "?").slice(0, 10)}`;
}

export function fmtBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}
