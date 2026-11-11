"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { getMonitorCatalog, getMonitorSnapshot, sourceLink, type MonitorCatalog, type MonitorObservation, type MonitorSnapshot, type MonitorSource } from "@/lib/marketMonitor";
import { loadWatchlist, saveWatchlist } from "@/lib/marketMonitorWatchlist";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";

const labels = { ready: "Ready", stale: "Stale", unavailable: "Unavailable", not_configured: "Setup required" };
const stateColor = { ready: "var(--pos)", stale: "var(--warn)", unavailable: "var(--neg)", not_configured: "var(--text-mut)" };
const numeric = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const command = "rounded border border-[var(--line)] px-3 py-1.5 text-xs text-[var(--text-hi)] hover:border-[var(--accent)] disabled:opacity-50";
function timestamp(value: string | null) { return value ? new Date(value).toLocaleString() : "Not provided"; }
function Link({ url, children }: { url: string; children: ReactNode }) {
  const safe = sourceLink(url);
  return safe ? <a className="underline decoration-[var(--line)] underline-offset-4 hover:text-[var(--accent)]" href={safe} target="_blank" rel="noopener noreferrer">{children}<span aria-hidden> {"\u2197"}</span></a> : <span>{children}</span>;
}
function SourceState({ source }: { source: MonitorSource }) {
  return <span style={{ color: stateColor[source.status] }}>{labels[source.status]}</span>;
}
function Observation({ value }: { value?: MonitorObservation }) {
  if (!value) return <span className="text-xs text-[var(--text-mut)]">No observation</span>;
  return <><span className="font-mono tabular-nums">{numeric.format(value.value)} <span className="text-xs text-[var(--text-mut)]">{value.unit}</span></span>
    <span className="ml-3 whitespace-nowrap text-xs" style={{ color: value.change === null ? "var(--text-mut)" : value.change >= 0 ? "var(--pos)" : "var(--neg)" }}>
      {value.change === null ? "Change unavailable" : `${value.change > 0 ? "+" : ""}${numeric.format(value.change)} ${value.change_unit}`}
    </span><div className="mt-1 text-xs text-[var(--text-mut)]">Observed {value.observation_date}{value.previous_date ? ` / prior ${value.previous_date}` : ""}</div></>;
}

export default function MarketMonitorPanel() {
  const [catalog, setCatalog] = useState<MonitorCatalog | null>(null);
  const [ids, setIds] = useState<string[]>([]);
  const [company, setCompany] = useState<string | null>(null);
  const [add, setAdd] = useState("");
  const [storageWarning, setStorageWarning] = useState<string | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [setupRetry, setSetupRetry] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [record, setRecord] = useState<{ key: string; data: MonitorSnapshot } | null>(null);
  const [newsSource, setNewsSource] = useState("all");
  const [category, setCategory] = useState("all");
  const [companyOnly, setCompanyOnly] = useState(false);
  const refresh = useRef<() => void>(() => {});
  const key = JSON.stringify([ids, company]);
  const data = record?.key === key ? record.data : null;

  useEffect(() => {
    const controller = new AbortController(); let active = true;
    setSetupError(null);
    getMonitorCatalog(controller.signal).then((value) => {
      if (!active) return;
      let prefs;
      try { prefs = loadWatchlist(window.localStorage, value.instruments.map((item) => item.id), value.default_ids); }
      catch { prefs = { ids: value.default_ids, warning: "Browser storage is unavailable; preferences are kept for this visit." }; }
      setIds(prefs.ids); setStorageWarning(prefs.warning);
      setCompany(prefs.ids.find((id) => value.instruments.find((item) => item.id === id)?.kind === "company") ?? null);
      setCatalog(value);
    }).catch((err: unknown) => { if (active) setSetupError(err instanceof Error ? err.message : "Monitor catalog is unavailable."); });
    return () => { active = false; controller.abort(); };
  }, [setupRetry]);

  useEffect(() => {
    if (!catalog) return;
    let active = true, running = false, lastAttempt = 0;
    let controller: AbortController | null = null;
    const interval = Math.max(300, catalog.refresh_seconds) * 1000;
    async function load() {
      if (!active || running || document.visibilityState === "hidden") return;
      running = true; lastAttempt = Date.now(); controller = new AbortController();
      const current = controller;
      const timeout = setTimeout(() => current.abort(), 90_000);
      setLoading(true); setError(null);
      try {
        const next = await getMonitorSnapshot(ids, company, current.signal);
        if (active && !current.signal.aborted) setRecord({ key, data: next });
      } catch (err) {
        if (active) setError(current.signal.aborted ? "Monitor refresh timed out. Previous results, if any, are retained." : err instanceof Error ? err.message : "Refresh failed; previous results are retained.");
      } finally { clearTimeout(timeout); running = false; if (active) setLoading(false); }
    }
    const visible = () => { if (Date.now() - lastAttempt >= interval) void load(); };
    refresh.current = () => { void load(); };
    void load();
    const timer = setInterval(() => { void load(); }, interval);
    document.addEventListener("visibilitychange", visible);
    return () => { active = false; clearInterval(timer); controller?.abort(); document.removeEventListener("visibilitychange", visible); refresh.current = () => {}; };
    // The key is the serialized request identity; catalog arrives only after preference hydration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog, key]);

  function update(next: string[]) {
    setIds(next);
    try { setStorageWarning(saveWatchlist(window.localStorage, next)); }
    catch { setStorageWarning("Watchlist updated for this visit; browser storage is unavailable."); }
  }
  function move(index: number, direction: number) {
    const next = [...ids]; const other = index + direction;
    if (other < 0 || other >= next.length) return;
    [next[index], next[other]] = [next[other], next[index]]; update(next);
  }
  if (setupError) return <section role="alert" className="space-y-3"><h2 className="text-xl font-semibold">Monitor unavailable</h2><p>{setupError}</p><button className={command} onClick={() => setSetupRetry((value) => value + 1)}>Retry catalog</button></section>;
  if (!catalog) return <div aria-label="Loading Monitor catalog"><SkeletonTable rows={5} cols={3} /></div>;
  const byId = new Map(catalog.instruments.map((item) => [item.id, item]));
  const sources = data?.sources ?? [];
  const sourceFor = (id: string) => sources.find((source) => source.observations.some((observation) => observation.instrument_id === id))
    ?? sources.find((source) => source.id === (byId.get(id)?.source === "yahoo" ? `market:${id}` : byId.get(id)?.source));
  const observation = (id: string) => sourceFor(id)?.observations.find((value) => value.instrument_id === id);
  const companyEntry = company ? byId.get(company) : null;
  const sec = sources.find((source) => source.id === `sec:${company}`);
  const news = sources.flatMap((source) => source.items.map((item) => ({ ...item, source })))
    .filter((item) => (newsSource === "all" || item.source.id === newsSource) && (category === "all" || item.source.category === category)
      && (!companyOnly || !!companyEntry && [companyEntry.name, companyEntry.symbol].some((token) => new RegExp(`\\b${token}\\b`, "i").test(item.title))))
    .sort((a, b) => (b.published_at ? Date.parse(b.published_at) : 0) - (a.published_at ? Date.parse(a.published_at) : 0));
  return <div className="min-w-0 space-y-5 text-sm text-[var(--text)]">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-2xl font-semibold text-[var(--text-hi)]">Monitor</h2><p className="mt-1 text-xs text-[var(--text-mut)]">Daily observations and source announcements. Not realtime. Visible-tab refresh every 5 minutes.</p></div>
      <button type="button" className={command} disabled={loading} onClick={() => refresh.current()}>{loading ? "Refreshing..." : "Refresh"}</button>
    </header>
    {storageWarning && <p role="status" className="text-[var(--warn)]">{storageWarning}</p>}
    {error && <p role="alert" className="border-l-2 border-[var(--neg)] pl-3 text-[var(--neg)]">{error} {data ? "Displayed data are from the previous successful snapshot." : ""}</p>}
    <details className="border-y border-[var(--line)] py-3 text-xs">
      <summary className="cursor-pointer">Source status: {data ? Object.entries(labels).map(([state, label]) => `${sources.filter((source) => source.status === state).length} ${label.toLowerCase()}`).join(" / ") : loading ? "Checking sources" : "Waiting"}</summary>
      <ul className="mt-3 grid gap-3 sm:grid-cols-2">{sources.map((source) => <li key={source.id} className="min-w-0">
        <Link url={source.source_url}>{source.label}</Link> / <SourceState source={source} /> / {source.cadence}
        <div className="mt-1 text-[var(--text-mut)]">Retrieved: {timestamp(source.retrieved_at)} / Checked: {timestamp(source.checked_at)}</div>
        {source.message && <p className="mt-1 break-words">{source.message}</p>}
      </li>)}</ul>
    </details>
    <div className="grid min-w-0 gap-x-7 gap-y-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <section aria-label="Personal watchlist" className="min-w-0">
        <h3 className="mb-3 font-semibold text-[var(--text-hi)]">Watchlist</h3>
        <div className="mb-3 flex gap-2"><select aria-label="Add instrument" className="ql-input min-w-0 flex-1" value={add} onChange={(event) => setAdd(event.target.value)}><option value="">Select instrument</option>{catalog.instruments.filter((item) => !ids.includes(item.id)).map((item) => <option key={item.id} value={item.id}>{item.name} / {item.kind}</option>)}</select>
          <button className={command} disabled={!add || ids.length >= catalog.max_watchlist} onClick={() => { update([...ids, add]); setAdd(""); }}>Add</button></div>
        {!ids.length ? <p className="py-5 text-[var(--text-mut)]">Your watchlist is empty.</p> : <div className="overflow-x-auto"><table className="w-full text-left"><thead className="text-xs text-[var(--text-mut)]"><tr><th className="py-2">Instrument</th><th>Observation</th><th><span className="sr-only">Watchlist controls</span></th></tr></thead><tbody>{ids.map((id, index) => {
          const item = byId.get(id)!; const source = sourceFor(id);
          return <tr key={id} className="border-t border-[var(--line)] align-top"><td className="py-3 pr-3">
            {item.kind === "company" ? <button className="text-left font-medium text-[var(--accent)]" onClick={() => setCompany(id)}>{item.name}</button> : <Link url={item.source_url}>{item.name}</Link>}
            <p className="mt-1 text-xs text-[var(--text-mut)]">{item.symbol} / {item.kind} / {item.region}</p>
            <span className="text-xs">{source ? <><SourceState source={source} /> / {source.label}</> : loading ? "Loading" : "Unavailable"}</span>
          </td><td className="py-3 pr-2"><Observation value={observation(id)} />{observation(id)?.timezone && <p className="mt-1 text-xs text-[var(--text-mut)]">{observation(id)?.timezone}</p>}</td>
          <td className="whitespace-nowrap py-3">{[-1, 1, 0].map((direction) => <button key={direction} type="button" title={direction === 0 ? "Remove" : direction < 0 ? "Move up" : "Move down"} aria-label={`${direction === 0 ? "Remove" : direction < 0 ? "Move up" : "Move down"} ${item.name}`} disabled={direction < 0 && index === 0 || direction > 0 && index === ids.length - 1} className="h-7 w-7 disabled:opacity-25 hover:text-[var(--accent)]" onClick={() => direction === 0 ? update(ids.filter((value) => value !== id)) : move(index, direction)}>{direction === 0 ? "\u00d7" : direction < 0 ? "\u2191" : "\u2193"}</button>)}</td></tr>;
        })}</tbody></table></div>}
        {loading && !data && <div role="status" className="mt-3 text-xs text-[var(--text-mut)]">Loading observations...</div>}
      </section>
      <section aria-label="Treasury rates" className="border-t border-[var(--line)] pt-4 xl:border-t-0 xl:pt-0"><h3 className="mb-3 font-semibold text-[var(--text-hi)]">US Treasury par yields</h3>{["treasury2y", "treasury10y", "treasury30y", "treasury10y2y"].map((id) => <div key={id} className="border-t border-[var(--line)] py-3"><h4 className="mb-1 text-xs">{byId.get(id)?.name}</h4><Observation value={observation(id)} /></div>)}
        <p className="text-xs text-[var(--text-mut)]">Changes in basis points. Spread uses same-date yields, not the Fed policy rate.</p></section>
      <section aria-label="News and official announcements" className="min-w-0 border-t border-[var(--line)] pt-4">
        <h3 className="mb-3 font-semibold text-[var(--text-hi)]">News &amp; official announcements</h3>
        <div className="mb-3 flex flex-wrap gap-2"><select aria-label="News source" className="ql-input sm:!w-auto" value={newsSource} onChange={(event) => setNewsSource(event.target.value)}><option value="all">All sources</option>{sources.filter((source) => ["official", "news"].includes(source.category)).map((source) => <option key={source.id} value={source.id}>{source.label}</option>)}</select><select aria-label="News category" className="ql-input sm:!w-auto" value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option><option value="official">Official</option><option value="news">Publisher news</option></select>
          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={companyOnly} disabled={!company} onChange={(event) => setCompanyOnly(event.target.checked)} />Company name/ticker text match</label></div>
        {!news.length && <p className="py-4 text-[var(--text-mut)]">No available items in this selection.</p>}
        <ul className="divide-y divide-[var(--line)]">{news.slice(0, 30).map((item) => <li className="py-3" key={`${item.source.id}:${item.id}`}><Link url={item.url}>{item.title}</Link><p className="mt-1 text-xs text-[var(--text-mut)]">{item.source.label} / {item.source.category === "official" ? "Official announcement" : "Publisher news"} / Published {timestamp(item.published_at)}</p></li>)}</ul>
      </section>
      <div className="min-w-0 space-y-6">
        <section aria-label="Selected company" className="border-t border-[var(--line)] pt-4"><h3 className="mb-3 font-semibold text-[var(--text-hi)]">Company detail</h3>
          <select aria-label="Selected company" className="ql-input mb-3 w-full" value={company ?? ""} onChange={(event) => { setCompany(event.target.value || null); if (!event.target.value) setCompanyOnly(false); }}><option value="">Select company</option>{catalog.instruments.filter((item) => item.kind === "company").map((item) => <option key={item.id} value={item.id}>{item.name} ({item.symbol})</option>)}</select>
          {companyEntry && <><h4 className="mb-2 font-medium"><Link url={companyEntry.source_url}>{companyEntry.name}</Link></h4><Observation value={observation(companyEntry.id)} /><p className="my-3 text-xs text-[var(--text-mut)]">{companyEntry.note}</p>
            <h4 className="font-medium">SEC filings</h4>{sec && <p className="my-2 text-xs"><SourceState source={sec} /> / checked {timestamp(sec.checked_at)}{sec.message && <span className="mt-2 block">{sec.message}</span>}</p>}
            {sec?.status === "ready" && sec.filings.length === 0 && <p className="text-xs">No recent annual, quarterly or current reports returned.</p>}
            <ul className="divide-y divide-[var(--line)]">{sec?.filings.map((filing) => <li key={filing.accession} className="py-2 text-xs"><Link url={filing.url}>{filing.form} / {filing.filing_date}</Link><p className="mt-1 break-all text-[var(--text-mut)]">{filing.accession}</p>{filing.accepted_at && <p>Accepted {timestamp(filing.accepted_at)}</p>}</li>)}</ul></>}
        </section>
        <section aria-label="Upcoming calendar" className="border-t border-[var(--line)] pt-4"><h3 className="mb-2 font-semibold text-[var(--text-hi)]">Upcoming</h3>
          {sources.find((source) => source.id === "fomc")?.events.map((event) => <div key={event.id} className="border-b border-[var(--line)] py-3"><Link url={event.url}>{event.title}</Link><p className="mt-1 text-xs">{event.start_date}{event.start_date !== event.end_date ? ` to ${event.end_date}` : ""}</p></div>)}
          {!sources.some((source) => source.events.length) && <p className="my-3 text-xs text-[var(--text-mut)]">Upcoming schedule unavailable.</p>}
          <p className="mt-3 text-xs"><Link url={data?.eia_schedule_url ?? "https://www.eia.gov/petroleum/supply/weekly/schedule.php"}>Official EIA release schedule</Link></p>
        </section>
      </div>
    </div>
    <footer className="border-t border-[var(--line)] pt-3 text-xs text-[var(--text-mut)]">Yahoo futures references are not spot prices or identified expiring contracts. Monitor checks sources only while open; it is not a background collector or alerting service.</footer>
  </div>;
}
