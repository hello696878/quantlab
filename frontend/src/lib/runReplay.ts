import { BacktestApiError } from "./api";
import { useEffect, useRef } from "react";
import type { BacktestRequest, BacktestResponse } from "./types";

export interface ReplayCapture {
  schema_version: "replay_capture_v1";
  original_request: Record<string, unknown>;
  request_provenance?: string;
  execution_environment: EnvironmentManifest;
  dataset_version_id?: number;
  csv_text?: string;
  parent_context_id?: number;
}
export interface EnvironmentManifest {
  schema_version: string;
  classification: string;
  collection: string;
  fields: Record<string, string | boolean | null>;
}
export interface ReplayResolution {
  config_hash_full: string;
  config_hash: string;
  canonical_config: Record<string, unknown>;
  contexts: { id: number; saved_backtest_id: number; name: string; created_at: string; input_hash: string; environment_hash: string | null; result_hash: string; execution_hash: string }[];
  total: number;
  page: number;
  page_size: number;
  selection_required: boolean;
  ambiguous: boolean;
}
export interface ReplayPreflight {
  schema_version: string;
  context_id: number;
  config_hash_full: string;
  canonical_config: Record<string, unknown>;
  input_hash: string;
  environment_hash: string | null;
  result_hash: string;
  execution_hash: string;
  original_request: Record<string, unknown> | null;
  restore_request: BacktestRequest | null;
  restore_level: "recorded_settings" | "config_only";
  dataset: { version_id: number; material_hash: string } | null;
  artifact: { run_id: number; role: string; material_hash: string } | null;
  data_availability: string;
  integrity: "intact" | "changed";
  ready_with_retained_data: boolean;
  environment_comparison: { field: string; recorded: string | boolean | null; current: string | boolean | null; state: "same" | "different" | "unknown" | "not_applicable" }[];
  limitations: string[];
}
export interface ReplayRestore { preflight: ReplayPreflight; request: BacktestRequest; csvText?: string }
export interface ReplayLocation { hash?: string; context?: number }

export function readReplayLink(search?: string): { active: boolean; location: ReplayLocation; error?: string } {
  const value = search ?? (typeof window === "undefined" ? "" : window.location.search);
  const params = new URLSearchParams(value);
  if (params.get("view") !== "runreplay") return { active: false, location: {} };
  const hash = params.get("hash"), context = params.get("context");
  if (value.length > 512 || params.getAll("hash").length > 1 || params.getAll("context").length > 1 ||
      hash && !/^[0-9a-f]{64}$/.test(hash) || context && !/^[1-9][0-9]{0,9}$/.test(context) ||
      context && Number(context) > 2147483647 || context && !hash) {
    return { active: true, location: {}, error: "Invalid replay link. Use a full hash and bounded context ID." };
  }
  return { active: true, location: { hash: hash ?? undefined, context: context ? Number(context) : undefined } };
}
export function writeReplayLink(location: ReplayLocation | null): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (location) {
    for (const key of ["market", "tour", "presentation"]) url.searchParams.delete(key);
    url.searchParams.set("view", "runreplay");
    url.searchParams.delete("hash"); url.searchParams.delete("context");
    if (location.hash) url.searchParams.set("hash", location.hash);
    if (location.context) url.searchParams.set("context", String(location.context));
  } else {
    if (url.searchParams.get("view") === "runreplay") url.searchParams.delete("view");
    for (const key of ["hash", "context"]) url.searchParams.delete(key);
  }
  const next = url.pathname + url.search + url.hash;
  if (next !== window.location.pathname + window.location.search + window.location.hash) window.history.pushState(null, "", next);
}

export function useReplayLinkCleanup(view: string): void {
  const previous = useRef(view);
  useEffect(() => {
    if (previous.current === "runreplay" && view !== previous.current) writeReplayLink(null);
    previous.current = view;
  }, [view]);
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/run-replay/${path}`, body === undefined ? { cache: "no-store" } :
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch { throw new BacktestApiError(503, "Backend unavailable. Start FastAPI and retry; saved local data has not been deleted."); }
  const result = await response.json().catch(() => null);
  if (!response.ok) throw new BacktestApiError(response.status, typeof result?.detail === "string" ? result.detail : "Replay request failed. Retry with a valid full hash/context.");
  return result as T;
}
export const resolveReplay = (hash: string, page = 1) => call<ReplayResolution>(`hash/${encodeURIComponent(hash)}?page=${page}`);
export const preflightReplay = (id: number) => call<ReplayPreflight>(`contexts/${id}`);
export const registerReplay = (id: number) => call<ReplayPreflight>(`register/${id}`, {});
export const createReplayDemo = () => call<{ config_hash_full: string; context_id: number; saved_backtest_id: number }>("demo", {});
export const verifyReplayCSV = (id: number, csv_text: string) => call<{ matched: boolean }>(`contexts/${id}/check-input`, { csv_text });
export const executeLocalReplay = (id: number, request: BacktestRequest, csv_text?: string) => call<BacktestResponse>(`contexts/${id}/execute-local`, { request, csv_text });
export async function downloadReplay(id: number): Promise<void> {
  const result = await call<ReplayPreflight>(`contexts/${id}/export`);
  const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a"); anchor.href = url;
  anchor.download = `quantlab-replay-${id}.json`;
  document.body.appendChild(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
