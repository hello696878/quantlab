"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { classifyApiError } from "@/lib/api";
import * as portfolios from "@/lib/portfolioDiagnostics";
import { createRun, executeRun, getRun, fmtPct, type MissingShockPolicy, type RunFull } from "@/lib/portfolioStress";
import { buildAssetShockRun, creationOutcomeUnknown, shockText } from "@/lib/portfolioStressComposer";
import EmptyState from "./ui/EmptyState";
import ErrorState from "./ui/ErrorState";
import OfflineState from "./ui/OfflineState";
import { SkeletonTable } from "./ui/LoadingSkeleton";

interface Props {
  onBack: () => void;
  onOpen: (run: RunFull) => void;
  onOpenPortfolio?: () => void;
  initialRun?: RunFull;
}

type SourceData = { portfolio: portfolios.RunFull; rebalances: portfolios.RebalanceRow[] };
type Listing = Awaited<ReturnType<typeof portfolios.listRuns>>;

export default function PortfolioStressComposer({ onBack, onOpen, onOpenPortfolio, initialRun }: Props) {
  const recoveryOnly = initialRun !== undefined;
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [listing, setListing] = useState<Listing | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<unknown>(null);
  const [portfolioId, setPortfolioId] = useState("");
  const [rebalanceId, setRebalanceId] = useState("");
  const [source, setSource] = useState<SourceData | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState<unknown>(null);
  const [name, setName] = useState("");
  const [shocks, setShocks] = useState<Record<string, string>>({});
  const [missingPolicy, setMissingPolicy] = useState<MissingShockPolicy>("unavailable");
  const [notional, setNotional] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unknownCreation, setUnknownCreation] = useState(false);
  const [createdId, setCreatedId] = useState<number | null>(initialRun?.id ?? null);
  const [stored, setStored] = useState<RunFull | null>(initialRun ?? null);
  const [recoveryChecked, setRecoveryChecked] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  const locked = busy || createdId !== null || unknownCreation;

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (recoveryOnly) return;
    let active = true;
    setListLoading(true);
    setListError(null);
    portfolios.listRuns({ status: "completed", page, page_size: 20 }).then((value) => {
      if (active) setListing(value);
    }).catch((err: unknown) => { if (active) setListError(err); })
      .finally(() => { if (active) setListLoading(false); });
    return () => { active = false; };
  }, [page, refresh, recoveryOnly]);

  useEffect(() => {
    let active = true;
    if (recoveryOnly || !portfolioId) return;
    setSourceLoading(true);
    setSourceError(null);
    const id = Number(portfolioId);
    Promise.all([portfolios.getRun(id), portfolios.getRebalances(id)]).then(([portfolio, rows]) => {
      if (!active) return;
      if (portfolio.id !== id || portfolio.status !== "completed") throw new Error("The selected portfolio is no longer completed. Refresh the source list.");
      setSource({ portfolio, rebalances: rows.items });
    }).catch((err: unknown) => { if (active) setSourceError(err); })
      .finally(() => { if (active) setSourceLoading(false); });
    return () => { active = false; };
  }, [portfolioId, refresh, recoveryOnly]);

  function selectPortfolio(id: string) {
    setPortfolioId(id);
    setSource(null);
    setRebalanceId("");
    setShocks({});
    setSourceError(null);
    setSourceLoading(!!id);
    setError(null);
  }

  const current = source?.portfolio.id === Number(portfolioId) ? source : null;
  const candidates = current?.rebalances.filter((row) => row.weights && Object.keys(row.weights).length > 0) ?? [];
  const rebalance = candidates.find((row) => String(row.rebalance_id) === rebalanceId);
  const validation = useMemo(() => {
    try {
      return { payload: buildAssetShockRun(current && rebalance ? { portfolio: current.portfolio, rebalance } : null,
        { name, shocks, missingPolicy, notional }), message: null };
    } catch (err) {
      return { payload: null, message: err instanceof Error ? err.message : "Check the scenario inputs." };
    }
  }, [current, rebalance, name, shocks, missingPolicy, notional]);

  function acceptResult(run: RunFull, id: number) {
    if (run.id !== id) throw new Error("The response does not match the created run. Refresh its stored status.");
    setStored(run);
    if (run.status === "completed") onOpen(run);
    else setError(run.error_message || `Run #${id} is ${run.status}; analysis is not complete. Refresh its stored status.`);
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
      if (!Number.isInteger(created.id) || created.id <= 0) throw new Error("Creation returned no usable run ID.");
      id = created.id;
      setCreatedId(id);
      setStored(created);
      const result = await executeRun(id);
      if (mounted.current) acceptResult(result, id);
    } catch (err) {
      if (!mounted.current) return;
      const message = classifyApiError(err).message;
      if (id !== null) {
        setRecoveryChecked(false);
        setError(`Run #${id} was created. Execution outcome must be checked before retrying. ${message}`);
      } else if (creationOutcomeUnknown(err)) {
        setUnknownCreation(true);
        setError(`Creation outcome is unknown; a run may have been saved. Inspect the run list before another creation. ${message}`);
      } else setError(message);
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  async function recover(action: "refresh" | "open" | "execute") {
    if (inFlight.current || createdId === null) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setRecoveryChecked(false);
    try {
      // Even an explicit retry reads persisted status first; a lost response
      // must not cause a second execution of a run already completed/running.
      const run = await getRun(createdId);
      if (!mounted.current) return;
      if (run.id !== createdId) throw new Error("Stored run identity mismatch.");
      setStored(run);
      if (action === "open" || run.status === "completed") { onOpen(run); return; }
      if (run.status !== "pending" && run.status !== "failed") {
        setError(`Run #${createdId} is ${run.status}; execution recovery is unavailable. Refresh or inspect the stored run.`);
        return;
      }
      if (action === "refresh") {
        setRecoveryChecked(true);
        if (run.status === "failed") setError(run.error_message || `Run #${createdId} is failed. Review it before retrying.`);
        return;
      }
      const result = await executeRun(createdId);
      if (mounted.current) acceptResult(result, createdId);
    } catch (err) {
      if (mounted.current) setError(`Run #${createdId} is retained. Refresh its stored status before recovery. ${classifyApiError(err).message}`);
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  function fetchError(value: unknown) {
    const info = classifyApiError(value);
    return info.backendUnavailable
      ? <OfflineState detail={info.message} onRetry={() => { selectPortfolio(""); setRefresh((v) => v + 1); }} />
      : <ErrorState message={info.message} onRetry={() => { selectPortfolio(""); setRefresh((v) => v + 1); }} />;
  }

  return <section className="space-y-4" aria-labelledby="stress-composer-title">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 id="stress-composer-title" className="text-lg font-semibold text-[var(--text-hi)]">{recoveryOnly ? "Recover stress run" : "New stress run"}</h2>
        <p className="text-sm text-[var(--text-mut)]">{recoveryOnly
          ? "Check the stored status before retrying this same run. No replacement run is created."
          : "Explicit shock assumptions applied to stored portfolio weights. Research only, not predictions or advice."}</p>
      </div>
      <button type="button" className="btn-secondary" disabled={busy} onClick={onBack}>{unknownCreation ? "Inspect run list" : "Back to runs"}</button>
    </div>
    {!recoveryOnly && <form onSubmit={submit} noValidate className="space-y-4">
      <fieldset disabled={locked} className="space-y-4 disabled:opacity-70">
        <legend className="mb-2 font-medium">Stored portfolio</legend>
        {listLoading ? <SkeletonTable rows={2} cols={3} caption="Loading completed portfolios..." />
          : listError ? fetchError(listError)
          : !listing?.items.length ? <EmptyState title="No completed portfolios on this page" description="Choose another page or open Portfolio Diagnostics to create a source portfolio. No demo runs are created automatically."
            actions={onOpenPortfolio ? [{ label: "Open Portfolio Diagnostics", onClick: onOpenPortfolio }] : undefined} />
          : <label className="block space-y-1 text-sm">Completed portfolio
            <select className="ql-input w-full" value={portfolioId} onChange={(e) => selectPortfolio(e.target.value)}>
              <option value="">Select a portfolio</option>
              {listing.items.map((run) => <option key={run.id} value={run.id}>#{run.id} - {run.name}</option>)}
            </select>
          </label>}
        {listing && !listLoading && <div className="flex flex-wrap items-center gap-3 text-sm">
          <span>{listing.total} completed portfolios; page {listing.page} of {listing.total_pages}</span>
          <button type="button" className="btn-secondary" disabled={listing.page <= 1} onClick={() => { selectPortfolio(""); setPage(page - 1); }}>Previous portfolios</button>
          <button type="button" className="btn-secondary" disabled={listing.page >= listing.total_pages} onClick={() => { selectPortfolio(""); setPage(page + 1); }}>Next portfolios</button>
          <button type="button" className="btn-secondary" onClick={() => { selectPortfolio(""); setRefresh((v) => v + 1); }}>Refresh portfolios</button>
        </div>}
        {sourceLoading && <p role="status">Loading selected portfolio and rebalances...</p>}
        {sourceError != null && fetchError(sourceError)}
        {current && <>
          <p className="text-sm text-[var(--text-mut)]">Source integrity: {current.portfolio.integrity_status || "Unknown"}. Earlier rebalances may have unavailable risk diagnostics.</p>
          {current.portfolio.warnings?.length > 0 && <ul className="list-disc pl-5 text-sm text-[var(--warn)]" aria-label="Source warnings">{current.portfolio.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}
          {!candidates.length ? <EmptyState title="No stored solved weights" description="This portfolio has no selectable rebalance. Choose another completed portfolio." />
            : <label className="block space-y-1 text-sm">Stored rebalance
              <select className="ql-input w-full" value={rebalanceId} onChange={(e) => { setRebalanceId(e.target.value); setShocks({}); }}>
                <option value="">Select a rebalance</option>
                {candidates.map((row) => <option key={row.rebalance_id} value={row.rebalance_id}>#{row.rebalance_id} - {row.decision_timestamp}</option>)}
              </select>
            </label>}
        </>}
        {current && rebalance && <>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div><dt className="text-[var(--text-mut)]">Decision timestamp</dt><dd className="break-words">{rebalance.decision_timestamp}</dd></div>
            <div><dt className="text-[var(--text-mut)]">Effective timestamp</dt><dd className="break-words">{rebalance.effective_timestamp ?? "Unavailable"}</dd></div>
          </dl>
          <label className="block space-y-1 text-sm">Run name<input className="ql-input w-full" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Selected rebalance weights and percent shocks">
              <thead><tr><th className="text-left">Asset ID</th><th className="text-right">Stored weight</th><th className="text-right">Shock (%)</th></tr></thead>
              <tbody>{current.portfolio.universe.assets.map((asset) => <tr key={asset.asset_id} className="border-t border-[var(--line)]">
                <th scope="row" className="py-2 text-left font-normal break-all">{asset.asset_id}<span className="block text-xs text-[var(--text-mut)]">{asset.name}</span></th>
                <td className="text-right font-mono">{Number.isFinite(rebalance.weights?.[asset.asset_id]) ? fmtPct(rebalance.weights![asset.asset_id]) : "Unavailable"}</td>
                <td className="py-2 pl-3 text-right"><input aria-label={`Shock for ${asset.asset_id} (%)`} type="text" inputMode="decimal" className="ql-input w-32 max-w-full text-right"
                  value={shockText(shocks, asset.asset_id)} onChange={(e) => setShocks((values) => ({ ...values, [asset.asset_id]: e.target.value }))} /></td>
              </tr>)}</tbody>
            </table>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block space-y-1 text-sm">Omitted asset shocks
              <select className="ql-input w-full" value={missingPolicy} onChange={(e) => setMissingPolicy(e.target.value as MissingShockPolicy)}>
                <option value="unavailable">Unspecified - partial coverage (unavailable)</option>
                <option value="zero">Explicitly assume no shock (zero)</option>
              </select>
            </label>
            <label className="block space-y-1 text-sm">Notional (optional)<input type="text" inputMode="decimal" className="ql-input w-full" value={notional} onChange={(e) => setNotional(e.target.value)} /></label>
          </div>
          <p className="text-xs text-[var(--text-mut)]">Percent units: -10 means -10%. Blank shocks are omitted; explicit 0 is retained. Without notional, monetary P&amp;L remains unavailable.</p>
        </>}
      </fieldset>
      {validation.message && !locked && <p role="status" className="text-sm text-[var(--text-mut)]">{validation.message}</p>}
      {error && <p role="alert" className="text-sm text-[var(--risk)]">{error}</p>}
      {createdId === null && !unknownCreation && <button type="submit" className="btn-primary" disabled={busy || !validation.payload}>{busy ? "Creating and executing..." : "Create and run"}</button>}
    </form>}
    {recoveryOnly && error && <p role="alert" className="text-sm text-[var(--risk)]">{error}</p>}
    {createdId !== null && <div className="space-y-2 border-t border-[var(--line)] pt-3">
      <p role="status">Stored run #{createdId}: {stored?.status ?? "unknown"}. {busy ? "Checking or executing..." : ""}</p>
      {stored?.warnings?.length ? <ul className="list-disc pl-5 text-sm text-[var(--warn)]">{stored.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" disabled={busy} onClick={() => recover("refresh")}>Refresh stored run</button>
        <button type="button" className="btn-secondary" disabled={busy} onClick={() => recover("open")}>Open stored run</button>
        <button type="button" className="btn-secondary" disabled={busy || !recoveryChecked || !["pending", "failed"].includes(stored?.status ?? "")} onClick={() => recover("execute")}>Retry execution of this run</button>
      </div>
    </div>}
  </section>;
}
