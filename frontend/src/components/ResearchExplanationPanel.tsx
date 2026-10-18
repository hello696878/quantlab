"use client";

import { useEffect, useRef, useState } from "react";
import { explainSavedBacktest, downloadExplanation, type ResearchExplanation } from "@/lib/researchExplainer";

export default function ResearchExplanationPanel({ id, corpusId }: { id: number; corpusId?: string }) {
  const [bundle, setBundle] = useState<ResearchExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const ticket = useRef(0), pending = useRef(false);
  useEffect(() => {
    ticket.current++; pending.current = false;
    setBundle(null); setError(null); setBusy(false); setSelected(null);
    return () => { ticket.current++; };
  }, [id, corpusId]);
  async function request(check = false) {
    if (pending.current) return;
    const current = ++ticket.current;
    pending.current = true; setBusy(true); setError(null);
    try {
      const result = await explainSavedBacktest(id, check ? bundle?.fingerprint : undefined, corpusId);
      if (current === ticket.current) { setBundle(result); setSelected(null); }
    } catch (err) {
      if (current === ticket.current) {
        setError(err instanceof Error ? err.message : "Stored explanation unavailable");
        if (check) setBundle(null);
      }
    } finally {
      if (current === ticket.current) { pending.current = false; setBusy(false); }
    }
  }
  // Identity guard also covers a render before the selection-reset effect runs.
  const shown = bundle?.identity.saved_backtest_id === id ? bundle : null;
  const fact = shown?.facts.find((value) => value.id === selected);
  return <section aria-label="Stored research explanation" className="space-y-3 min-w-0 border-t border-[var(--line)] pt-4">
    <div className="flex flex-wrap gap-2 items-center">
      <button type="button" className="btn-secondary" disabled={busy} onClick={() => void request()}>{busy ? "Reading stored result..." : "Explain stored result"}</button>
      {shown && <>
        <button type="button" className="btn-secondary" disabled={busy} onClick={() => void request(true)}>Check pinned source</button>
        <button type="button" className="btn-secondary" onClick={() => { try { downloadExplanation(shown); } catch { setError("Explanation export failed"); } }}>Download explanation JSON</button>
      </>}
    </div>
    {error && <p role="alert" className="text-red-400 break-words">{error}</p>}
    {shown && <div className="space-y-3 text-sm text-[var(--text)]">
      <h3 className="font-semibold">Stored SMA explanation</h3>
      <dl className="text-xs break-all"><dt>Source / schema</dt><dd>{shown.identity.source_kind} / {shown.identity.source_schema} / record {shown.identity.saved_backtest_id}</dd>
        <dt>Trust</dt><dd>{shown.identity.trust}</dd><dt>Pinned material</dt><dd>{shown.identity.material_hash}</dd></dl>
      <ul className="space-y-2">{shown.statements.map((statement) => <li key={statement.template_id} className="break-words">
        {statement.text}{statement.facts.map((key) => <button key={key} type="button" className="ml-2 underline text-[var(--accent)]" onClick={() => setSelected(key)} aria-label={`Inspect source ${key}`}>Source</button>)}
        {statement.policy_id && <span className="ml-2 text-xs text-[var(--text-dim)]">{statement.policy_id} / {statement.template_id}</span>}
      </li>)}</ul>
      {fact && <div role="region" aria-label="Evidence reference" className="border border-[var(--line)] p-3 break-words">
        <h4 className="font-semibold">{fact.id}</h4><dl className="text-xs space-y-1">
          <dt>Original field path</dt><dd className="font-mono break-all">{fact.source}{fact.path}</dd>
          <dt>State</dt><dd>{fact.state}</dd><dt>Raw value</dt><dd>{fact.state === "missing" ? "Absent" : JSON.stringify(fact.value)}</dd>
          <dt>Displayed value / unit / formatting rule</dt><dd>{fact.display ?? "Unavailable"} / {fact.unit} / {fact.rule}</dd>
          <dt>Pinned source identity</dt><dd className="break-all">{fact.source === "saved" ? shown.identity.material_hash : shown.identity.context?.snapshot_hash}</dd>
        </dl>
      </div>}
    </div>}
  </section>;
}
