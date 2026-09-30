"use client";

import { useEffect, useRef, useState } from "react";
import type { View } from "@/components/AppShell";
import { classifyApiError } from "@/lib/api";
import * as api from "@/lib/mlLifecycle";
import { DataTable, StructuredData } from "@/components/StrategyEnsembleDetail";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import OfflineState from "@/components/ui/OfflineState";
import ErrorState from "@/components/ui/ErrorState";

const button = "rounded border px-3 py-2 text-xs disabled:opacity-40";
const control = { color: "var(--text-hi)", background: "var(--bg)", borderColor: "var(--line)" };
const destinations: Record<api.Adapter, View> = { validation: "modelvalidation", calibration: "metalabeling",
  features: "featurediagnostics", costs: "costdiagnostics", decay: "signaldecay" };
const hash = (value: string | null | undefined) => value ? <code className="block max-w-72 break-all select-all text-xs">{value}</code> : "Unavailable";
const display = (value: unknown) => typeof value === "object" ? JSON.stringify(value) : String(value ?? "Unavailable");

export default function MLLifecyclePanel({ onNav }: { onNav: (view: View) => void }) {
  const [listing, setListing] = useState<api.Listing | null>(null);
  const [run, setRun] = useState<api.Run | null>(null);
  const [comparison, setComparison] = useState<api.Comparison | null>(null);
  const [linked, setLinked] = useState<unknown>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [page, setPage] = useState(1);
  const [completeness, setCompleteness] = useState("");
  const [integrity, setIntegrity] = useState("");
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const mounted = useRef(true);
  const lock = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    let current = true;
    setLoading(true); setListing(null); setError(null);
    api.listRuns(page, completeness, integrity).then((data) => { if (current) setListing(data); })
      .catch((failure) => { if (current) setError(failure); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [page, completeness, integrity, revision]);
  async function action(operation: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(null); setNotice("");
    try { await operation(); }
    catch (failure) { if (mounted.current) setError(failure); }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function open(id: number) {
    setRun(null); setLinked(null); setComparison(null);
    const value = await api.getRun(id);
    if (mounted.current) setRun(value);
  }
  const failure = error ? classifyApiError(error) : null;
  const retry = () => run ? action(() => open(run.id)) : setRevision((v) => v + 1);
  return <div data-testid="ml-lifecycle-panel" className="min-w-0 max-w-full space-y-5" style={{ color: "var(--text)" }}>
    <header className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold" style={{ color: "var(--text-hi)" }}>ML Research Lifecycle</h2>
      <div className="flex flex-wrap gap-2">
        {(run || comparison) && <button className={button} style={control} disabled={busy} onClick={() => {
          setRun(null); setComparison(null); setLinked(null); setRevision((v) => v + 1);
        }}>Back to lifecycles</button>}
        <button className={button} style={control} disabled={busy || loading} onClick={() => action(async () => {
          const value = await api.loadDemo();
          if (mounted.current) { setRun(value); setLinked(null); setComparison(null);
            setNotice(value.completeness === "complete" ? "Synthetic lifecycle completed." : "Lifecycle stored with incomplete stages. Inspect adapter status before retrying."); }
        })}>{busy ? "Working..." : "Create / resume synthetic demo"}</button>
        {run && <button className={button} style={control} disabled={busy || run.integrity !== "intact"} onClick={() => action(async () => {
          const value = await api.exportRun(run.id);
          if (!mounted.current) return;
          const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
          const anchor = document.createElement("a"); anchor.href = url; anchor.download = `quantlab-ml-lifecycle-${run.id}.json`;
          document.body.appendChild(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
          setNotice("JSON download requested.");
        })}>Export JSON</button>}
      </div>
    </header>
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {failure && (failure.backendUnavailable ? <OfflineState onRetry={retry} /> : <ErrorState message={failure.message} onRetry={retry} />)}
    {!run && !comparison && <>
      <div className="flex flex-wrap gap-3 text-xs">
        <label>Completeness <select aria-label="Completeness" style={control} className="rounded border p-2" value={completeness} disabled={busy}
          onChange={(e) => { setCompleteness(e.target.value); setPage(1); setSelected([]); }}>
          <option value="">All</option><option value="complete">Complete</option><option value="incomplete">Incomplete</option>
        </select></label>
        <label>Integrity <select aria-label="Integrity" style={control} className="rounded border p-2" value={integrity} disabled={busy}
          onChange={(e) => { setIntegrity(e.target.value); setPage(1); setSelected([]); }}>
          <option value="">All</option><option value="intact">Intact</option><option value="changed">Changed</option>
        </select></label>
      </div>
      {loading ? <SkeletonTable rows={4} cols={5} /> : listing && !error && <>
        {listing.items.length === 0 ? <EmptyState title="No matching ML lifecycles" description="No matching research records are stored. No model has been trained by opening this workspace." /> :
          <DataTable title="Stored lifecycles" headers={["Compare", "Lifecycle", "Completeness", "Integrity", "Processing"]} rows={listing.items.map((row) => [
            <input type="checkbox" aria-label={`Compare ${row.name}`} checked={selected.includes(row.id)}
              disabled={busy || row.integrity !== "intact" || selected.length === 2 && !selected.includes(row.id)}
              onChange={() => setSelected((v) => v.includes(row.id) ? v.filter((id) => id !== row.id) : [...v, row.id])} />,
            <button className="text-left underline" disabled={busy} onClick={() => action(() => open(row.id))}>{row.name}</button>, row.completeness, row.integrity, row.processing_status,
          ])} />}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <button aria-label="Previous lifecycle page" disabled={busy || page === 1} onClick={() => setPage(page - 1)}>&larr;</button>
          <span>Page {page}; {listing.total} records</span>
          <button aria-label="Next lifecycle page" disabled={busy || page * listing.page_size >= listing.total} onClick={() => setPage(page + 1)}>&rarr;</button>
          <button className={button} style={control} disabled={busy || selected.length !== 2} onClick={() => action(async () => {
            const value = await api.compareRuns(selected[0], selected[1]); if (mounted.current) setComparison(value);
          })}>Compare lifecycles</button>
        </div>
      </>}
    </>}
    {run && <section data-testid="ml-lifecycle-detail" className="space-y-5 min-w-0">
      <h3 className="text-base font-semibold break-words">{run.name}</h3>
      <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries({ Stored: run.stored_status, Processing: run.processing_status, Completeness: run.completeness,
          Integrity: run.integrity, Validation: run.validation_state, Source: run.snapshot.origin }).map(([key, value]) =>
          <div key={key} className="min-w-0"><dt style={{ color: "var(--text-mut)" }}>{key}</dt><dd className="break-words">{value}</dd></div>)}
      </dl>
      {run.integrity_messages.map((message) => <p key={message} role="alert" style={{ color: "var(--neg)" }}>{message}</p>)}
      {run.snapshot.unavailable.length > 0 && <section><h4>Unavailable provenance</h4><ul className="list-disc pl-5 text-sm">
        {run.snapshot.unavailable.map((item) => <li key={item}>{item}</li>)}</ul></section>}
      <DataTable title="Artifact identities" headers={["Stage", "Content identity"]} rows={Object.entries(run.identities).map(([stage, value]) => [stage, hash(value)])} />
      <DataTable title="Diagnostic links" headers={["Adapter", "Record", "Processing", "Integrity", "Actions"]} rows={run.links.map((link) => [
        link.adapter, link.destination_id ?? "Unavailable", link.error ?? link.status, link.integrity,
        <div className="flex flex-wrap gap-2">
          <button className="underline" disabled={busy || link.integrity !== "intact"} onClick={() => action(async () => {
            setLinked(null); const value = await api.linkedRecord(run.id, link.adapter); if (mounted.current) setLinked(value);
          })}>Inspect {link.adapter} record</button>
          <button className="underline" disabled={busy} onClick={() => onNav(destinations[link.adapter])}>Open {link.adapter} lab</button>
        </div>,
      ])} />
      {linked !== null && <section data-testid="ml-linked-detail"><h4>Linked diagnostic record</h4><StructuredData title="Linked record content" value={linked} /></section>}
      {run.snapshot.models && <DataTable title="Fitted models" headers={["Role", "Model identity", "Train samples", "Outcome cutoff"]}
        rows={run.snapshot.models.map((m) => [m.role, hash(m.hash), m.train_ids.length, m.training_cutoff])} />}
      {run.snapshot.splits && <DataTable title="Split membership" headers={["Role", "Train", "Test", "Purged", "Embargoed"]}
        rows={run.snapshot.splits.map((s) => [s.role, s.membership.train.length, s.membership.test.length, s.membership.purged.length, s.membership.embargoed.length])} />}
      {run.snapshot.calibration && <DataTable title="Frozen calibration" headers={["Method", "Fit population", "Fit samples", "Frozen threshold"]}
        rows={[[run.snapshot.calibration.method, "Inner OOF (calibration-fit scores, not held-out)", run.snapshot.calibration.fit_ids.length, run.snapshot.calibration.threshold]]} />}
      {run.snapshot.predictions && <DataTable title="Prediction provenance" headers={["Sample", "Role", "Raw probability", "Calibrated probability", "Model"]}
        rows={run.snapshot.predictions.map((p) => [<span className="break-all">{p.sample_id}</span>, p.role,
          `${(p.raw_probability * 100).toFixed(2)}%`, p.calibrated_probability === undefined ? "Unavailable" : `${(p.calibrated_probability * 100).toFixed(2)}%`, hash(p.model_hash)])} />}
      <StructuredData title="Dataset binding" value={{ version_id: run.dataset_version_id, content: run.dataset_content_hash, manifest: run.dataset_manifest_hash }} />
      <StructuredData title="Source training environment" value={run.snapshot.source_environment} />
      {run.snapshot.inspection_environment !== undefined && <StructuredData title="Importer environment (not training provenance)" value={run.snapshot.inspection_environment} />}
      <StructuredData title="Features, labels and exact sample membership" value={{ feature_order: run.snapshot.feature_order, specs: run.snapshot.specs, splits: run.snapshot.splits, samples: run.snapshot.samples }} />
      <StructuredData title="Models and calibration artifacts" value={{ models: run.snapshot.models, calibration: run.snapshot.calibration }} />
      <StructuredData title="Held-out evaluation and cost policy" value={run.snapshot.evaluation ?? "Unavailable for legacy provenance"} />
    </section>}
    {comparison && <section className="min-w-0 space-y-3"><p>{comparison.note}</p>
      <DataTable title="Neutral lifecycle comparison" headers={["Field", "A", "B"]} rows={comparison.rows.map((row) =>
        [row.field, <span className="break-all">{display(row.a)}</span>, <span className="break-all">{display(row.b)}</span>])} />
      <StructuredData title="Evaluation metrics (no ranking)" value={comparison.metrics} />
    </section>}
  </div>;
}
