"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { classifyApiError } from "@/lib/api";
import { createRun, executeRun, getRun, type PortfolioConstructionMethod, type PortfolioReturnInput, type RunFull } from "@/lib/portfolioDiagnostics";
import { buildPortfolioRun, enteredWeightTotal, MAX_IMPORT_BYTES, parsePortfolioReturns, weightText, type PortfolioReuseDraft } from "@/lib/portfolioDiagnosticsComposer";
import { creationOutcomeUnknown } from "@/lib/portfolioStressComposer";

type Props = {
  onBack: () => void;
  onOpen: (run: RunFull) => void;
} & ({ initialRun: RunFull; reuseDraft?: never } | { initialRun?: never; reuseDraft?: PortfolioReuseDraft });

export default function PortfolioDiagnosticsComposer({ onBack, onOpen, initialRun, reuseDraft }: Props) {
  const [name, setName] = useState("");
  const [raw, setRaw] = useState(reuseDraft?.raw ?? "");
  const [preview, setPreview] = useState<PortfolioReturnInput | null>(reuseDraft?.data ?? null);
  const [attribution, setAttribution] = useState(reuseDraft ? { id: reuseDraft.sourceId, name: reuseDraft.sourceName } : null);
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [method, setMethod] = useState<PortfolioConstructionMethod>("user_supplied");
  const [lookback, setLookback] = useState("20");
  const [reading, setReading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unknownCreation, setUnknownCreation] = useState(false);
  const [createdId, setCreatedId] = useState<number | null>(initialRun?.id ?? null);
  const [stored, setStored] = useState<RunFull | null>(initialRun ?? null);
  const [recoveryChecked, setRecoveryChecked] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  const inputRevision = useRef(0);
  const locked = busy || createdId !== null || unknownCreation;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; inputRevision.current += 1; };
  }, []);

  function invalidate(clearAttribution = true) {
    inputRevision.current += 1;
    setPreview(null);
    setWeights({});
    setError(null);
    setReading(false);
    if (clearAttribution) setAttribution(null);
  }

  async function loadFile(file?: File) {
    invalidate();
    if (!file) return;
    if (file.size > MAX_IMPORT_BYTES) { setError("Return JSON exceeds the Composer limit of 2 MiB."); return; }
    const revision = inputRevision.current;
    setReading(true);
    try {
      const value = await file.text();
      if (!mounted.current || revision !== inputRevision.current) return;
      if (new TextEncoder().encode(value).byteLength > MAX_IMPORT_BYTES) throw new Error("Return JSON exceeds the Composer limit of 2 MiB.");
      setRaw(value);
    } catch (err) {
      if (mounted.current && revision === inputRevision.current) setError(err instanceof Error ? err.message : "Could not read the selected JSON file.");
    } finally {
      if (mounted.current && revision === inputRevision.current) setReading(false);
    }
  }

  function validateImport() {
    if (inFlight.current || locked || reading) return;
    invalidate(false);
    try { setPreview(parsePortfolioReturns(raw)); }
    catch (err) { setError(err instanceof Error ? err.message : "Invalid return data."); }
  }

  const validation = useMemo(() => {
    if (!preview) return { payload: null, message: "Validate return data before creating a run." };
    try { return { payload: buildPortfolioRun(preview, name, weights, lookback, method), message: null }; }
    catch (err) { return { payload: null, message: err instanceof Error ? err.message : "Check the inputs." }; }
  }, [preview, name, weights, lookback, method]);
  const total = preview ? enteredWeightTotal(preview, weights) : null;
  const windowLength = /^\d+$/.test(lookback.trim()) ? Number(lookback) : NaN;
  const validWindow = preview && windowLength >= 3 && windowLength <= Math.min(500, preview.timestamps.length - 1);

  function accept(run: RunFull, id: number) {
    if (run.id !== id) throw new Error("Stored run identity mismatch. Refresh the known run before recovery.");
    setStored(run);
    if (run.status === "completed") onOpen(run);
    else setError(run.error_message || `Run #${id} is ${run.status}. Refresh stored status before any explicit retry.`);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current || locked || !validation.payload) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    let id: number | null = null;
    try {
      const created = await createRun(validation.payload);
      if (!mounted.current) return;
      if (!Number.isSafeInteger(created.id) || created.id <= 0) throw new Error("Creation returned no usable positive run ID.");
      if (reuseDraft && created.id === reuseDraft.sourceId) throw new Error("Creation returned the source run ID instead of a new run. Inspect the run list before continuing.");
      id = created.id;
      setCreatedId(id);
      setStored(created);
      if (created.status !== "pending") { accept(created, id); return; }
      const result = await executeRun(id);
      if (mounted.current) accept(result, id);
    } catch (err) {
      if (!mounted.current) return;
      const message = classifyApiError(err).message;
      if (id !== null) {
        setRecoveryChecked(false);
        setError(`Run #${id} is retained. Execution outcome must be checked before retrying. ${message}`);
      } else if (creationOutcomeUnknown(err)) {
        setUnknownCreation(true);
        setError(`Creation outcome is unknown; a run may already be saved. Inspect the run list before creating another. ${message}`);
      } else setError(message);
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  async function recover(action: "refresh" | "open" | "execute") {
    if (inFlight.current || createdId === null || (action === "execute" && !recoveryChecked)) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setRecoveryChecked(false);
    try {
      const run = await getRun(createdId);
      if (!mounted.current) return;
      if (run.id !== createdId) throw new Error("Stored run identity mismatch.");
      setStored(run);
      if (action === "open" || run.status === "completed") { onOpen(run); return; }
      if (!["pending", "failed"].includes(run.status)) {
        setError(`Run #${createdId} is ${run.status}; execution recovery is unavailable. Inspect or refresh this record.`);
        return;
      }
      if (action === "refresh") {
        setRecoveryChecked(true);
        if (run.error_message) setError(run.error_message);
        return;
      }
      const result = await executeRun(createdId);
      if (mounted.current) accept(result, createdId);
    } catch (err) {
      if (mounted.current) setError(`Run #${createdId} is retained. Refresh before recovery. ${classifyApiError(err).message}`);
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  return <section className="space-y-4" aria-labelledby="portfolio-composer-title">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <h2 id="portfolio-composer-title" className="text-lg font-semibold text-[var(--text-hi)]">{initialRun ? "Recover portfolio run" : "New portfolio run"}</h2>
      <button type="button" className="btn-secondary" disabled={busy} onClick={onBack}>{unknownCreation ? "Inspect run list" : "Back to runs"}</button>
    </div>
    {attribution && <p className="text-sm text-[var(--text-mut)]">Return data copied from run #{attribution.id}, &quot;{attribution.name}&quot;. Construction settings are reset for this new run. This is a data snapshot, not a clone or replay; no source link is saved.</p>}
    {!initialRun && <form onSubmit={submit} noValidate className="space-y-4">
      <fieldset disabled={locked} className="space-y-4 disabled:opacity-70">
        <legend className="font-medium">Portfolio construction</legend>
        <label className="block space-y-1 text-sm">Run name<input className="ql-input w-full" value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="block space-y-1 text-sm">Construction method<select className="ql-input w-full" value={method} onChange={(e) => setMethod(e.target.value as PortfolioConstructionMethod)}>
          <option value="user_supplied">Manual weights</option>
          <option value="equal_weight">Equal weight</option>
          <option value="inverse_volatility">Inverse volatility</option>
        </select></label>
        <p className="text-sm text-[var(--text-mut)]">{method === "user_supplied"
          ? "User-declared weights are preserved without rescaling."
          : method === "equal_weight"
            ? "The backend constructs equal allocations, scaled to sum to one."
            : "The backend constructs weights proportional to inverse trailing-window sample volatility, scaled to sum to one. This is not equal risk contribution, an optimal allocation or guaranteed risk reduction. No volatility floor: unusable assets may receive reported zero weights; construction can fail if none are usable."}</p>
        <label className="block space-y-1 text-sm">Return JSON<textarea rows={7} className="ql-input w-full font-mono text-xs" value={raw}
          onChange={(e) => { invalidate(); setRaw(e.target.value); }} /></label>
        <label className="block space-y-1 text-sm">Local JSON file<input type="file" accept=".json,application/json" className="block max-w-full" onChange={(e) => { void loadFile(e.target.files?.[0]); e.target.value = ""; }} /></label>
        <p className="text-sm text-[var(--text-mut)]">2 MiB limit. Root: frequency, timestamps, assets. Each asset: asset_id, returns; optional name, asset_type, group, currency. 2-20 assets and 24-2,000 aligned observations. Dates: exact YYYY-MM-DD only. Return units: 0.01 means a 1% period return. No price conversion, filling or row removal.</p>
        <button type="button" className="btn-secondary" disabled={reading} onClick={validateImport}>Validate return data</button>
        {reading && <p role="status">Reading local JSON...</p>}
        {preview && <div className="space-y-3 border-y border-[var(--line)] py-3" aria-label="Validated return preview">
          <p>{preview.assets.length} assets; {preview.timestamps.length} observations; declared frequency: {preview.frequency}; {preview.timestamps[0]} to {preview.timestamps.at(-1)}.</p>
          <p className="text-sm text-[var(--text-mut)]">Frequency and observations are self-declared, not a verified calendar or historical data certification. Sample: first 3 observations only.</p>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr><th className="text-left">Asset / metadata</th><th className="text-left">Period return sample</th>{method === "user_supplied" && <th className="text-right">Weight (%)</th>}</tr></thead>
            <tbody>{preview.assets.map((asset) => <tr key={asset.asset_id} className="border-t border-[var(--line)]">
              <th scope="row" className="py-2 text-left font-normal break-all">{asset.asset_id}<span className="block text-xs text-[var(--text-mut)]">{[asset.name, asset.asset_type, asset.group, asset.currency].filter(Boolean).join(" / ")}</span></th>
              <td className="px-2 font-mono text-xs">{asset.returns.slice(0, 3).map(String).join(", ")}</td>
              {method === "user_supplied" && <td className="py-2 text-right"><input type="text" inputMode="decimal" className="ql-input w-28 max-w-full text-right" aria-label={`Weight for ${asset.asset_id} (%)`}
                value={weightText(weights, asset.asset_id)} onChange={(e) => setWeights((old) => ({ ...old, [asset.asset_id]: e.target.value }))} /></td>}
            </tr>)}</tbody>
          </table></div>
          {method === "user_supplied" && <p role="status">Entered total: {total === null ? "incomplete or invalid" : `${total}%`}. Required: 100% (fractional tolerance 1e-6); manual weights are never rescaled.</p>}
          <label className="block space-y-1 text-sm">Rolling lookback<input type="text" inputMode="numeric" className="ql-input w-28" value={lookback} onChange={(e) => setLookback(e.target.value)} /></label>
          {validWindow && <p className="text-sm">Estimation window: {preview.timestamps[0]} to {preview.timestamps[windowLength - 1]}; first effective date: {preview.timestamps[windowLength]} (index {windowLength}, lag 1). Earlier portfolio returns are unavailable; subsequent weights drift, not daily rebalance.</p>}
        </div>}
        <p className="text-sm text-[var(--text-mut)]">Long-only, fully invested at one decision; sample per-period covariance, no repair. Volatility is per-period. Stored backend weights and solver results are authoritative. Integrity labels describe estimation policy, not independent certification of imported historical data. No prior book or cost model: turnover/cost information remains unavailable, not evidence of zero costs. Research only, not allocation advice.</p>
      </fieldset>
      {!locked && validation.message && <p role="status" className="text-sm text-[var(--text-mut)]">{validation.message}</p>}
      {createdId === null && !unknownCreation && <button type="submit" className="btn-primary" disabled={busy || !validation.payload}>{busy ? "Creating and executing..." : "Create and run"}</button>}
    </form>}
    {error && <p role="alert" className="text-sm text-[var(--risk)]">{error}</p>}
    {createdId !== null && <div className="space-y-2 border-t border-[var(--line)] pt-3">
      <p role="status">Stored run #{createdId}: {stored?.status ?? "unknown"}; solver: {stored?.solver_status ?? "unavailable"}. {busy ? "Checking or executing..." : ""}</p>
      {stored?.warnings?.length ? <ul className="list-disc pl-5 text-sm text-[var(--warn)]">{stored.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" disabled={busy} onClick={() => recover("refresh")}>Refresh stored run</button>
        <button type="button" className="btn-secondary" disabled={busy} onClick={() => recover("open")}>Open stored run</button>
        <button type="button" className="btn-secondary" disabled={busy || !recoveryChecked || !["pending", "failed"].includes(stored?.status ?? "")} onClick={() => recover("execute")}>Retry execution of this run</button>
      </div>
    </div>}
  </section>;
}
