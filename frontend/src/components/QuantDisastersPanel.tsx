"use client";

import { useState } from "react";
import {
  LIVE_DISASTERS,
  findDisasterBySlug,
  type DisasterEntry,
} from "@/lib/disasterRegistry";
import { MODEL_REGISTRY } from "@/lib/modelRegistry";
import { findPaperBySlug } from "@/lib/paperRegistry";

interface Props {
  /** Open a related Strategy Library model page. */
  onOpenStrategy: (slug: string) => void;
  /** Open a related Paper Replications page. */
  onOpenPaper: (slug: string) => void;
  /** Initial detail slug (e.g. from the command palette); null = index. */
  initialSlug?: string | null;
}

function Badge({ children, cls }: { children: React.ReactNode; cls: string }) {
  return (
    <span
      className={
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide " +
        cls
      }
    >
      {children}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <p className="section-title mb-3">{title}</p>
      {children}
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
      {items.map((s, i) => (
        <li key={i}>{s}</li>
      ))}
    </ul>
  );
}

const CAVEAT =
  "These case studies are simplified educational summaries, not full forensic " +
  "investigations. They illustrate failure mechanisms relevant to systematic " +
  "research and are not investment advice.";

/**
 * Quant Disasters Series v1 — risk-education case studies connecting famous
 * failures to QuantLab's diagnostics and, just as importantly, to what
 * QuantLab honestly cannot model yet.  Educational pages only — no runnable
 * scenario simulations in v1.
 */
export default function QuantDisastersPanel({
  onOpenStrategy,
  onOpenPaper,
  initialSlug = null,
}: Props) {
  const [slug, setSlug] = useState<string | null>(initialSlug);

  if (slug) {
    const entry = findDisasterBySlug(slug);
    if (!entry) {
      return (
        <div className="card p-6">
          <p className="text-sm text-slate-500">No case study found for “{slug}”.</p>
          <button
            type="button"
            onClick={() => setSlug(null)}
            className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            ← Back to Quant Disasters
          </button>
        </div>
      );
    }
    return (
      <DisasterDetail
        entry={entry}
        onBack={() => setSlug(null)}
        onOpenStrategy={onOpenStrategy}
        onOpenPaper={onOpenPaper}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {LIVE_DISASTERS.map((d) => (
          <DisasterCard key={d.id} entry={d} onOpen={() => setSlug(d.slug)} />
        ))}
      </div>
      <p className="text-[11px] text-slate-400">{CAVEAT}</p>
    </div>
  );
}

function DisasterCard({ entry, onOpen }: { entry: DisasterEntry; onOpen: () => void }) {
  return (
    <div className="card flex flex-col gap-2 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-bold text-slate-900">
            {entry.title}{" "}
            <span className="font-normal text-slate-400">({entry.year})</span>
          </p>
          <p className="text-xs text-slate-400">{entry.category}</p>
        </div>
        <Badge cls="bg-red-100 text-red-600">{entry.severity}</Badge>
      </div>
      <p className="text-sm text-slate-600">{entry.shortDescription}</p>
      <div className="flex flex-wrap gap-1.5">
        {entry.failureModes.slice(0, 4).map((m) => (
          <Badge key={m} cls="bg-amber-100 text-amber-700">
            {m}
          </Badge>
        ))}
        {entry.relatedConcepts.slice(0, 2).map((c) => (
          <Badge key={c} cls="bg-blue-50 text-blue-700">
            {c}
          </Badge>
        ))}
      </div>
      <div className="mt-1">
        <button
          type="button"
          onClick={onOpen}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-blue-400 hover:text-blue-600"
        >
          Open case study
        </button>
      </div>
    </div>
  );
}

function DisasterDetail({
  entry,
  onBack,
  onOpenStrategy,
  onOpenPaper,
}: {
  entry: DisasterEntry;
  onBack: () => void;
  onOpenStrategy: (slug: string) => void;
  onOpenPaper: (slug: string) => void;
}) {
  const relatedModels = MODEL_REGISTRY.filter((m) =>
    entry.relatedStrategyIds.includes(m.id),
  );
  const relatedPapers = entry.relatedPaperSlugs
    .map((s) => findPaperBySlug(s))
    .filter((p): p is NonNullable<typeof p> => Boolean(p));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          ← Quant Disasters
        </button>
        <Badge cls="bg-red-100 text-red-600">{entry.severity}</Badge>
      </div>

      <div className="card p-5">
        <p className="text-lg font-bold text-slate-900">
          {entry.title} <span className="font-normal text-slate-400">({entry.year})</span>
        </p>
        <p className="text-xs text-slate-400">{entry.category}</p>
        <p className="mt-3 text-sm text-slate-600">{entry.overview}</p>
      </div>

      <Section title="Why It Matters for Quant Research">
        <p className="text-sm text-slate-600">{entry.whyItMatters}</p>
      </Section>

      <Section title="Failure Modes">
        <div className="flex flex-wrap gap-1.5">
          {entry.failureModes.map((m) => (
            <Badge key={m} cls="bg-amber-100 text-amber-700">
              {m}
            </Badge>
          ))}
        </div>
      </Section>

      <Section title="Simplified Mechanism">
        <p className="text-sm text-slate-600">{entry.simplifiedMechanism}</p>
        <p className="mt-2 text-[11px] text-slate-400">
          A simplified interpretation — the full episode involved more moving
          parts than any short summary can capture.
        </p>
      </Section>

      <Section title="What a Naive Backtest Might Miss">
        <Bullets items={entry.naiveBacktestMisses} />
      </Section>

      <Section title="QuantLab Trust Layer Checklist">
        <ul className="space-y-2">
          {entry.trustChecklist.map((item) => (
            <li key={item.tool} className="flex items-start gap-2 text-sm">
              <Badge
                cls={
                  item.available
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-slate-100 text-slate-500"
                }
              >
                {item.available ? "Available" : "Not yet"}
              </Badge>
              <span className="text-slate-600">
                <span className="font-medium text-slate-700">{item.tool}:</span>{" "}
                {item.note}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-slate-400">
          Current QuantLab tools can help examine parts of this failure mode,
          but cannot fully model it.
        </p>
      </Section>

      <Section title="What QuantLab Cannot Model Yet">
        <Bullets items={entry.cannotModelYet} />
      </Section>

      <Section title="Lessons">
        <Bullets items={entry.lessons} />
      </Section>

      {(relatedModels.length > 0 || relatedPapers.length > 0) && (
        <Section title="Related Pages">
          <div className="flex flex-wrap gap-2">
            {relatedModels.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => onOpenStrategy(m.slug)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-blue-400 hover:text-blue-600"
              >
                Strategy: {m.name} →
              </button>
            ))}
            {relatedPapers.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onOpenPaper(p.slug)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-blue-400 hover:text-blue-600"
              >
                Paper: {p.authors} ({p.year}) →
              </button>
            ))}
          </div>
        </Section>
      )}

      <p className="text-[11px] text-slate-400">{CAVEAT}</p>
    </div>
  );
}
