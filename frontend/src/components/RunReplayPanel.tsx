"use client";

import { useEffect, useRef, useState } from "react";
import { createReplayDemo, downloadReplay, preflightReplay, resolveReplay, verifyReplayCSV } from "@/lib/runReplay";
import type { ReplayLocation, ReplayPreflight, ReplayResolution, ReplayRestore } from "@/lib/runReplay";

interface Props {
  location: ReplayLocation;
  linkError?: string;
  onLocation: (location: ReplayLocation) => void;
  onRestore: (restored: ReplayRestore) => void;
}
const button = "rounded border border-[var(--line)] bg-[var(--bg)] text-[var(--text-hi)] px-3 py-2 text-xs disabled:opacity-40";

export default function RunReplayPanel({ location, linkError, onLocation, onRestore }: Props) {
  const [hash, setHash] = useState(location.hash ?? "");
  const [resolution, setResolution] = useState<ReplayResolution | null>(null);
  const [preflight, setPreflight] = useState<ReplayPreflight | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [csvText, setCsvText] = useState<string>();
  const [retry, setRetry] = useState(0);
  const sequence = useRef(0);
  const action = useRef(false);

  useEffect(() => {
    const ticket = ++sequence.current;
    setHash(location.hash ?? ""); setResolution(null); setPreflight(null); setConfirm(false); setCsvText(undefined); setError(null);
    if (!location.hash) { setLoading(false); return; }
    setLoading(true);
    resolveReplay(location.hash).then(async (result) => {
      if (sequence.current !== ticket) return;
      setResolution(result);
      if (location.context) {
        const pre = await preflightReplay(location.context);
        if (pre.config_hash_full !== result.config_hash_full) throw new Error("Context does not belong to this configuration hash");
        if (sequence.current === ticket) setPreflight(pre);
      }
    }).catch((err: unknown) => { if (sequence.current === ticket) setError(err instanceof Error ? err.message : "Replay inspection failed"); })
      .finally(() => { if (sequence.current === ticket) setLoading(false); });
    return () => { sequence.current++; };
  }, [location.hash, location.context, retry]);

  async function explicitAction(run: () => Promise<void>) {
    if (action.current) return;
    action.current = true; setLoading(true); setError(null);
    const ticket = sequence.current;
    try { await run(); }
    catch (err) { if (sequence.current === ticket) setError(err instanceof Error ? err.message : "Replay action failed"); }
    finally { action.current = false; if (sequence.current === ticket) setLoading(false); }
  }
  const canRestore = preflight?.restore_request && preflight.integrity === "intact" &&
    (preflight.data_availability !== "reselection_required" || csvText !== undefined);
  return (
    <section data-testid="run-replay-panel" className="space-y-4 min-w-0 max-w-full" style={{ color: "var(--text)" }}>
      <h2 className="text-xl font-semibold">Run Replay</h2>
      <form className="flex flex-wrap gap-2" onSubmit={(event) => {
        event.preventDefault();
        if (!/^[0-9a-f]{64}$/.test(hash)) { setError("Enter the full lowercase 64-character hash, not a display prefix."); return; }
        onLocation({ hash });
        if (hash === location.hash && !location.context) setRetry((n) => n + 1);
      }}>
        <label className="flex-1 min-w-0">Full configuration hash
          <input aria-label="Full configuration hash" className="w-full rounded border border-[var(--line)] bg-[var(--bg)] text-[var(--text-hi)] px-2 py-2 font-mono text-xs" value={hash} maxLength={64}
            onChange={(event) => { sequence.current++; setHash(event.target.value); setResolution(null); setPreflight(null); setConfirm(false); setCsvText(undefined); setLoading(false); }} />
        </label>
        <button className={`${button} self-end`} disabled={loading}>Inspect hash</button>
      </form>
      <button type="button" className={button} disabled={loading} onClick={() => void explicitAction(async () => {
        const ticket = sequence.current;
        const demo = await createReplayDemo();
        if (sequence.current === ticket) onLocation({ hash: demo.config_hash_full, context: demo.context_id });
      })}>Create local SMA demo</button>
      {(error || linkError) && <p role="alert" className="text-red-400 break-words">{error || linkError}</p>}
      {loading && <p role="status">Loading replay context...</p>}
      {resolution && <>
        <p className="font-mono text-xs break-all">{resolution.config_hash_full}</p>
        <fieldset className="space-y-2"><legend>Saved executions ({resolution.total})</legend>
          {resolution.contexts.map((context) => <button key={context.id} type="button" className={`${button} block max-w-full text-left break-words`}
            disabled={loading} onClick={() => onLocation({ hash: resolution.config_hash_full, context: context.id })}>
            {context.name} / context {context.id} / {context.created_at}
          </button>)}
        </fieldset>
        {resolution.total > resolution.page * resolution.page_size && <button type="button" className={button} disabled={loading}
          onClick={() => void explicitAction(async () => {
            const ticket = sequence.current;
            const next = await resolveReplay(resolution.config_hash_full, resolution.page + 1);
            if (sequence.current === ticket) setResolution(next);
          })}>Next contexts</button>}
        <details><summary>Canonical configuration</summary><pre className="text-xs whitespace-pre-wrap break-all">{JSON.stringify(resolution.canonical_config, null, 2)}</pre></details>
      </>}
      {preflight && <div className="space-y-3">
        <p>Input: <span className="font-mono text-xs break-all">{preflight.input_hash}</span></p>
        <p>Integrity: {preflight.integrity}. Data: {preflight.data_availability}. Restore: {preflight.restore_level}.</p>
        <p>Dataset version: {preflight.dataset?.version_id ?? "Not recorded"}. Artifact provenance: {preflight.artifact?.run_id ?? "Not recorded"}.</p>
        <ul className="text-sm text-amber-300 space-y-1">{preflight.limitations.map((message) => <li key={message}>{message}</li>)}</ul>
        <div className="overflow-x-auto"><table className="w-full text-xs" aria-label="Environment comparison"><thead><tr>
          <th className="text-left">Field</th><th className="text-left">Execution</th><th className="text-left">Inspection</th><th className="text-left">State</th>
        </tr></thead><tbody>{preflight.environment_comparison.map((row) => <tr key={row.field}>
          <td>{row.field}</td><td>{String(row.recorded ?? "Unknown")}</td><td>{String(row.current ?? "Unknown")}</td><td>{row.state}</td>
        </tr>)}</tbody></table></div>
        {preflight.data_availability === "reselection_required" && <label className="block">Reselect original CSV (128 KiB max)
          <input type="file" accept=".csv,text/csv" disabled={loading} onChange={(event) => {
            const file = event.target.files?.[0]; setCsvText(undefined); setConfirm(false);
            if (!file) return;
            if (file.size > 128 * 1024) { setError("CSV exceeds 128 KiB replay limit"); return; }
            void explicitAction(async () => {
              const ticket = sequence.current, context = preflight.context_id;
              const text = await file.text(); await verifyReplayCSV(context, text);
              if (sequence.current === ticket) setCsvText(text);
            });
          }} />
        </label>}
        <div className="flex flex-wrap gap-2">
          <button type="button" className={button} disabled={!canRestore || loading} onClick={() => setConfirm(true)}>Restore configuration</button>
          <button type="button" className={button} disabled={loading || !preflight.restore_request} onClick={() => void explicitAction(() => downloadReplay(preflight.context_id))}>Export replay JSON</button>
        </div>
        {confirm && <div role="dialog" aria-label="Confirm configuration restore" className="border border-amber-500 p-4 space-y-2">
          <p>Replace current Backtest Studio settings? Unsaved edits will be replaced. No analysis runs until you click Run.</p>
          <button type="button" className={button} disabled={loading} onClick={() => void explicitAction(async () => {
            if (!canRestore) return;
            const ticket = sequence.current;
            setConfirm(false);
            const fresh = await preflightReplay(preflight.context_id);
            if (sequence.current !== ticket) return;
            setPreflight(fresh);
            if (fresh.context_id !== preflight.context_id || fresh.config_hash_full !== preflight.config_hash_full ||
                fresh.input_hash !== preflight.input_hash || fresh.integrity !== "intact" || !fresh.restore_request ||
                fresh.data_availability === "reselection_required" && csvText === undefined) {
              throw new Error("Replay context changed or is incomplete. Inspect it again before restoring.");
            }
            onRestore({ preflight: fresh, request: fresh.restore_request, csvText });
          })}>Apply and open Backtest Studio</button>
          <button type="button" className={`${button} ml-2`} disabled={loading} onClick={() => setConfirm(false)}>Cancel</button>
        </div>}
      </div>}
    </section>
  );
}
