export type Availability = "ready" | "stale" | "unavailable" | "not_configured";
export interface MonitorInstrument {
  id: string; name: string; kind: string; region: string; unit: string; currency: string | null;
  source: string; symbol: string; source_url: string; note: string;
}
export interface MonitorCatalog { instruments: MonitorInstrument[]; default_ids: string[]; max_watchlist: number; refresh_seconds: number }
export interface MonitorObservation {
  instrument_id: string; value: number; observation_date: string; unit: string; change: number | null;
  change_unit: string | null; previous_date: string | null; timezone: string | null; session_complete: boolean | null;
}
export interface MonitorSource {
  id: string; label: string; category: string; cadence: string; source_url: string; status: Availability;
  retrieved_at: string | null; checked_at: string | null; message: string | null;
  observations: MonitorObservation[];
  items: { id: string; title: string; url: string; published_at: string | null }[];
  filings: { accession: string; form: string; filing_date: string; accepted_at: string | null; url: string }[];
  events: { id: string; title: string; start_date: string; end_date: string; url: string }[];
}
export interface MonitorSnapshot { generated_at: string; sources: MonitorSource[]; company_id: string | null; eia_schedule_url: string }

async function get<T>(path: string, signal: AbortSignal): Promise<T> {
  let response: Response;
  try { response = await fetch(path, { signal, cache: "no-store" }); }
  catch (error) {
    if (signal.aborted) throw error;
    throw new Error("Monitor could not reach the backend. Check FastAPI and try again.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `Monitor request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}
export const getMonitorCatalog = (signal: AbortSignal) => get<MonitorCatalog>("/api/market-monitor/catalog", signal);
export const getMonitorSnapshot = (ids: string[], company: string | null, signal: AbortSignal) => {
  const params = new URLSearchParams({ ids: ids.join(",") });
  if (company) params.set("company", company);
  return get<MonitorSnapshot>(`/api/market-monitor/snapshot?${params}`, signal);
};
export function sourceLink(value: string): string | undefined {
  try { const url = new URL(value); return url.protocol === "https:" && !url.username && !url.password ? url.href : undefined; }
  catch { return undefined; }
}
