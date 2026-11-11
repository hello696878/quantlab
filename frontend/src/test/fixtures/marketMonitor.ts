// Clearly synthetic fixtures for deterministic UI tests only.
import type { MonitorCatalog, MonitorSource, MonitorSnapshot } from "@/lib/marketMonitor";
export const monitorCatalog: MonitorCatalog = { max_watchlist: 16, refresh_seconds: 300, default_ids: ["sp500", "nvda"], instruments: [
  ...[["sp500", "S&P 500", "index", "^GSPC"], ["nvda", "NVIDIA", "company", "NVDA"], ["aapl", "Apple", "company", "AAPL"]].map(([id, name, kind, symbol]) => ({ id, name, kind, symbol, source: "yahoo", region: "US", unit: "USD/share", currency: "USD", source_url: "https://finance.yahoo.com/", note: "Synthetic test observation; no session-completion claim." })),
  ...["treasury2y", "treasury10y", "treasury30y", "treasury10y2y"].map((id) => ({ id, name: id, kind: "rates", region: "US", unit: id.endsWith("2y") && id.includes("10y") ? "bps" : "%", currency: null, source: "treasury", symbol: id, source_url: "https://home.treasury.gov/", note: "Synthetic rate." })),
] };
export function monitorSource(values: Partial<MonitorSource>): MonitorSource {
  return { id: "fed", label: "Federal Reserve", category: "official", cadence: "event", source_url: "https://www.federalreserve.gov/", status: "ready",
    retrieved_at: "2026-11-10T10:00:00Z", checked_at: "2026-11-10T10:00:00Z", message: null, observations: [], items: [], filings: [], events: [], ...values };
}
export function monitorSnapshot(company = "nvda"): MonitorSnapshot {
  return { generated_at: "2026-11-10T10:00:00Z", company_id: company, eia_schedule_url: "https://www.eia.gov/petroleum/supply/weekly/schedule.php", sources: [
    monitorSource({ id: "market:sp500", label: "S&P 500", category: "market", cadence: "daily", observations: [{ instrument_id: "sp500", value: 100, unit: "index points", observation_date: "2026-11-09", change: null, change_unit: "%", previous_date: null, timezone: "America/New_York", session_complete: null }] }),
    monitorSource({ id: `market:${company}`, label: company, category: "market", cadence: "daily", observations: [{ instrument_id: company, value: company === "aapl" ? 222 : 123, unit: "USD/share", observation_date: "2026-11-09", change: 2.5, change_unit: "%", previous_date: "2026-11-06", timezone: "America/New_York", session_complete: null }] }),
    monitorSource({ id: "treasury", label: "US Treasury", category: "rates", observations: [{ instrument_id: "treasury10y2y", value: -50, unit: "bps", observation_date: "2026-11-09", change: -10, change_unit: "bps", previous_date: "2026-11-06", timezone: null, session_complete: null }] }),
    monitorSource({ items: [{ id: "fed:1", title: "Fed statement", url: "https://www.federalreserve.gov/new.htm", published_at: "2026-11-09T19:00:00Z" }] }),
    monitorSource({ id: "bbc", label: "BBC World", category: "news", items: [{ id: "bbc:1", title: "Apple company headline", url: "https://www.bbc.com/news/example", published_at: null }] }),
    monitorSource({ id: `sec:${company}`, label: "SEC", category: "filings", status: "not_configured", retrieved_at: null, checked_at: null, message: "Set MARKET_MONITOR_SEC_USER_AGENT on the server." }),
    monitorSource({ id: "fomc", label: "FOMC", category: "calendar", events: [{ id: "fomc:1", title: "FOMC meeting", start_date: "2026-12-08", end_date: "2026-12-09", url: "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm" }] }),
  ] };
}
