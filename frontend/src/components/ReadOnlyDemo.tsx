"use client";
import { useState } from "react";
import AppShell, { type View } from "@/components/AppShell";
import SavedBacktestsList from "@/components/SavedBacktestsList";
import SavedBacktestDetail from "@/components/SavedBacktestDetail";
import type { ServingCapabilities } from "@/lib/servingCapabilities";

export default function ReadOnlyDemo({ capabilities }: { capabilities: ServingCapabilities }) {
  const [view, setView] = useState<View>("home");
  const [selected, setSelected] = useState<number | null>(null);
  const corpusId = capabilities.corpus_id;
  if (corpusId === null) return <p role="alert">Demo corpus identity unavailable</p>;
  function navigate(next: View) {
    if (next !== "home" && next !== "saved") return;
    setView(next); setSelected(null);
  }
  return <AppShell active={view} onNav={navigate} title="QuantLab Synthetic Demo" subtitle="Prepared SMA research showcase" readOnly>
    <section aria-label="Read-only synthetic demo" data-corpus-id={capabilities.corpus_id} className="mb-6 space-y-2 border-l-2 border-[var(--accent)] pl-4 text-sm text-[var(--text)]">
      <h2 className="font-semibold text-[var(--text-hi)]">Read-only synthetic demo</h2>
      <p>Illustrative prices and dates, prepared offline with the existing engine. Not real market history, advice, or execution attestation.</p>
      <p>Run, Save, Delete, Import, registration, provider access and other workspaces are unavailable. Only approved stored SMA browsing and explanation are supported.</p>
      <p className="break-all font-mono text-xs">Corpus {capabilities.corpus_id}</p>
    </section>
    {selected === null
      ? <SavedBacktestsList key={corpusId} readOnly corpusId={corpusId} refreshKey={0} onSelect={setSelected} />
      : <SavedBacktestDetail key={`${corpusId}:${selected}`} readOnly corpusId={corpusId} id={selected} onBack={() => setSelected(null)} />}
  </AppShell>;
}
