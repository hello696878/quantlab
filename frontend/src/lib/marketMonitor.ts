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
export interface MonitorHistory {
  instrument: MonitorInstrument;
  period: "3mo";
  interval: "1d";
  adjustment: "provider_adjusted_close";
  points: { date: string; value: number }[];
  timezone: string | null;
  status: Exclude<Availability, "not_configured">;
  message: string | null;
  retrieved_at: string | null;
  checked_at: string;
}

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
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
    Number.isFinite(Date.parse(value));
}

function validPoints(points: unknown): points is MonitorHistory["points"] {
  if (!Array.isArray(points) || points.length > 100) return false;
  let previous = "";
  for (const point of points) {
    if (!isRecord(point) || typeof point.date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(point.date) ||
        point.date <= previous || typeof point.value !== "number" || !Number.isFinite(point.value) || point.value <= 0) {
      return false;
    }
    const date = new Date(point.date + "T00:00:00Z");
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== point.date) return false;
    previous = point.date;
  }
  return true;
}

export async function getMonitorHistory(instrument: MonitorInstrument, signal: AbortSignal): Promise<MonitorHistory> {
  const params = new URLSearchParams({ instrument_id: instrument.id });
  const result = await get<unknown>("/api/market-monitor/history?" + params, signal);
  if (!isRecord(result) || !isRecord(result.instrument) || instrument.source !== "yahoo" ||
      result.instrument.id !== instrument.id || result.instrument.source !== instrument.source ||
      result.instrument.symbol !== instrument.symbol || result.instrument.kind !== instrument.kind ||
      result.instrument.unit !== instrument.unit || result.instrument.currency !== instrument.currency ||
      result.period !== "3mo" || result.interval !== "1d" || result.adjustment !== "provider_adjusted_close") {
    throw new Error("Trend response did not match the selected instrument and daily history policy.");
  }

  const { points, status, timezone, message, retrieved_at, checked_at } = result;
  if (!validPoints(points) || !isTimestamp(checked_at) || (retrieved_at !== null && !isTimestamp(retrieved_at)) ||
      (timezone !== null && (typeof timezone !== "string" || timezone.length > 128)) ||
      (message !== null && typeof message !== "string") ||
      (status !== "ready" && status !== "stale" && status !== "unavailable") ||
      (status === "unavailable" ? points.length !== 0 || retrieved_at !== null : points.length === 0 || retrieved_at === null)) {
    throw new Error("Trend response contained invalid daily history.");
  }
  return { instrument, period: "3mo", interval: "1d", adjustment: "provider_adjusted_close",
    points, status, timezone, message, retrieved_at, checked_at };
}
export const getMonitorSnapshot = (ids: string[], company: string | null, signal: AbortSignal) => {
  const params = new URLSearchParams({ ids: ids.join(",") });
  if (company) params.set("company", company);
  return get<MonitorSnapshot>(`/api/market-monitor/snapshot?${params}`, signal);
};
export function sourceLink(value: string): string | undefined {
  try { const url = new URL(value); return url.protocol === "https:" && !url.username && !url.password ? url.href : undefined; }
  catch { return undefined; }
}
