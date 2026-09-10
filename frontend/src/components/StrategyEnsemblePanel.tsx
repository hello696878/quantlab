"use client";

import { useEffect, useRef, useState } from "react";
import { classifyApiError } from "@/lib/api";
import * as api from "@/lib/strategyEnsemble";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import StrategyEnsembleDetail, { DataTable } from "@/components/StrategyEnsembleDetail";

const button = "rounded border px-3 py-2 text-xs font-medium disabled:opacity-40 hover:brightness-125";
const control = { background: "var(--bg)", color: "var(--text-hi)", borderColor: "var(--line)" };

export default function StrategyEnsemblePanel() {
  const [listing, setListing] = useState<api.Listing | null>(null);
  const [run, setRun] = useState<api.Run | null>(null);
  const [comparison, setComparison] = useState<api.Comparison | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const [input, setInput] = useState("");
  const [reason, setReason] = useState("");
  const [recordExperiment, setRecordExperiment] = useState(false);
  const lock = useRef(false);
  const mounted = useRef(true);
  const reload = () => setRevision((v) => v+1);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    api.listRuns(page).then((data) => { if (active) setListing(data); })
      .catch((err) => { if (active) setError(err); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page, revision]);

  async function action(operation: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(null); setNotice("");
    try { await operation(); }
    catch (err) { if (mounted.current) setError(err); }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function open(id: number) {
    setRun(null); setComparison(null);
    const data = await api.getRun(id);
    if (mounted.current) { setRun(data); setReason(""); }
  }
  async function exportJson() {
    if (!run) return;
    const data = await api.exportRun(run.id);
    if (!mounted.current) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `quantlab-strategy-ensemble-${run.id}.json`;
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice("JSON download requested.");
  }
  const failure = error ? classifyApiError(error) : null;
  const retry = () => run ? action(() => open(run.id)) : reload();
  return <div className="min-w-0 max-w-full space-y-5" style={{ color: "var(--text)" }} data-testid="strategy-ensemble-panel">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold" style={{ color: "var(--text-hi)" }}>{run ? run.name : "Strategy return streams"}</h2>
      <div className="flex flex-wrap gap-2">
        {run && <button className={button} style={control} disabled={busy} onClick={() => { setRun(null); setComparison(null); setError(null); reload(); }}>&larr; Runs</button>}
        <button className={button} style={control} disabled={busy || loading} onClick={() => action(async () => {
          const seeded = await api.seedDemo();
          if (mounted.current) { setNotice(`${seeded.created_count} demo runs created; ${seeded.skipped_count} already present.`); setPage(1); reload(); }
        })}>{busy ? "Working..." : "Load demo runs"}</button>
        {run && <button className={button} style={control} disabled={busy} onClick={() => action(exportJson)}>Export JSON</button>}
      </div>
    </header>
    <p className="text-xs" style={{ color: "var(--text-mut)" }}>Local-first research. Strategy returns are not signals. Fixed user-configured weights only; no selection, investment advice or execution.</p>
    {notice && <p role="status" className="text-sm" style={{ color: "var(--pos)" }}>{notice}</p>}
    {failure && (failure.backendUnavailable ? <OfflineState onRetry={retry} /> : <ErrorState message={failure.message} onRetry={retry} />)}
    {!run && !comparison && <>
      {loading ? <SkeletonTable rows={5} cols={4} /> : listing && !error && <>
        <p className="text-xs">Saved runs: {listing.total}. Page {listing.page}. Baselines on this page: {listing.items.filter((r) => r.is_baseline).length}.</p>
        {listing.items.length === 0 ? <EmptyState title="No strategy ensemble runs" description="No return-stream analyses have been saved." /> :
          <DataTable title="Saved strategy ensemble runs" headers={["Compare", "Run", "Status", "Reference"]} rows={listing.items.map((r) => [
            <input type="checkbox" aria-label={`Compare ${r.name}`} disabled={busy || r.status !== "completed" || (selected.length === 2 && !selected.includes(r.id))}
              checked={selected.includes(r.id)} onChange={() => setSelected((s) => s.includes(r.id) ? s.filter((id) => id !== r.id) : [...s, r.id])} />,
            <button className="text-left underline break-words" disabled={busy} onClick={() => action(() => open(r.id))}>{r.name}</button>, r.status, r.is_baseline ? "Baseline" : "None",
          ])} />}
        <div className="flex gap-2 items-center">
          <button className={button} style={control} aria-label="Previous runs page" disabled={busy || page === 1} onClick={() => setPage(page-1)}>&larr;</button>
          <button className={button} style={control} aria-label="Next runs page" disabled={busy || page * listing.page_size >= listing.total} onClick={() => setPage(page+1)}>&rarr;</button>
          <button className={button} style={control} disabled={busy || selected.length !== 2} onClick={() => action(async () => { const data = await api.compareRuns(selected[0], selected[1]); if (mounted.current) setComparison(data); })}>Compare runs</button>
        </div>
      </>}
      <details className="border-t pt-4" style={{ borderColor: "var(--line)" }}>
        <summary className="cursor-pointer text-sm">Create supplied return-stream run</summary>
        <form className="mt-3 space-y-3" onSubmit={(event) => { event.preventDefault(); action(async () => {
          if (input.length > 12_000_000) throw new Error("Run definition exceeds 12 MB.");
          let body: unknown;
          try { body = JSON.parse(input); } catch { throw new Error("Run definition must be valid JSON."); }
          const created = await api.createRun(body);
          if (mounted.current) { setRun(created); setNotice("Run created. No analysis has been executed."); reload(); }
        }); }}>
          <label className="block text-xs">Run definition (JSON)<textarea aria-label="Run definition (JSON)" value={input} onChange={(e) => setInput(e.target.value)} spellCheck={false} rows={10}
            className="mt-1 block w-full rounded border p-3 font-mono text-xs" style={control} /></label>
          <button className={button} style={control} disabled={busy || !input.trim()}>Create run</button>
        </form>
      </details>
    </>}
    {run && <>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <span>Status: {run.status}. Reference: {run.is_baseline ? "Baseline" : "None"}.</span>
        <label className="flex gap-2 items-center"><input type="checkbox" checked={recordExperiment} onChange={(e) => setRecordExperiment(e.target.checked)} />Record experiment</label>
        <button className={button} style={control} disabled={busy || run.status === "invalidated"} onClick={() => action(async () => {
          const data = await api.executeRun(run.id, recordExperiment); if (mounted.current) { setRun(data); setNotice("Analysis completed."); }
        })}>Execute run</button>
        <button className={button} style={control} disabled={busy || run.status !== "completed" || !run.results?.baseline_eligible} onClick={() => action(async () => {
          const data = await api.markBaseline(run.id); if (mounted.current) { setRun(data); setNotice("Comparison baseline updated."); }
        })}>Mark baseline</button>
        <button className={button} style={control} disabled={busy} onClick={() => { setInput(JSON.stringify(run.request, null, 2)); setRun(null); }}>Use inputs for new run</button>
      </div>
      <StrategyEnsembleDetail key={run.id} run={run} />
      <details><summary className="cursor-pointer text-xs">Invalidate run</summary>
        <form className="mt-2 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); action(async () => { const data = await api.invalidateRun(run.id, reason); if (mounted.current) setRun(data); }); }}>
          <input aria-label="Invalidation reason" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} className="rounded border p-2 text-xs min-w-0" style={control} />
          <button className={button} style={control} disabled={busy || !reason.trim() || run.status === "invalidated"}>Invalidate</button>
        </form>
      </details>
    </>}
    {comparison && <>
      <button className={button} style={control} onClick={() => setComparison(null)}>&larr; Runs</button>
      <p>{comparison.reason}</p>
      <DataTable title="Neutral run comparison" headers={["Run", "N", "Mean per period", "Volatility per period", "Cost basis"]}
        rows={comparison.runs.map((r) => [r.name, r.ensemble.n, api.percent(r.ensemble.mean_return), api.percent(r.ensemble.volatility_per_period), r.ensemble.costs.basis])} />
    </>}
  </div>;
}
