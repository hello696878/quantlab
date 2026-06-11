"use client";

import { useState } from "react";
import {
  LIVE_PAPERS,
  PLANNED_PAPERS,
  findPaperBySlug,
  type PaperEntry,
  type PaperRunPreset,
  type PaperStatus,
  type ReplicationLevel,
} from "@/lib/paperRegistry";
import { MODEL_REGISTRY } from "@/lib/modelRegistry";

interface Props {
  /** Launch a paper-inspired preset in Backtest Studio (never auto-runs). */
  onRunPreset: (preset: PaperRunPreset, paper: PaperEntry) => void;
  /** Open a related Strategy Library model page. */
  onOpenStrategy: (slug: string) => void;
  /** Initial detail slug (e.g. from the command palette); null = index. */
  initialSlug?: string | null;
}

const STATUS_STYLE: Record<PaperStatus, string> = {
  live: "bg-emerald-100 text-emerald-700",
  planned: "bg-slate-100 text-slate-500",
  future: "bg-slate-100 text-slate-400",
};
const STATUS_LABEL: Record<PaperStatus, string> = {
  live: "Live",
  planned: "Planned",
  future: "Future",
};
const LEVEL_STYLE: Record<ReplicationLevel, string> = {
  full_replication: "bg-emerald-100 text-emerald-700",
  simplified_replication: "bg-blue-50 text-blue-700",
  inspired_demo: "bg-amber-100 text-amber-700",
  planned: "bg-slate-100 text-slate-500",
};
const LEVEL_LABEL: Record<ReplicationLevel, string> = {
  full_replication: "Full Replication",
  simplified_replication: "Simplified Replication",
  inspired_demo: "Inspired Demo",
  planned: "Planned",
};

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

/**
 * Paper Replication Series v1 — honest research pages for important quant
 * papers.  v1 ships *inspired demos* (single-asset approximations), never
 * full academic replications; planned papers carry no run buttons.
 */
export default function PaperReplicationsPanel({
  onRunPreset,
  onOpenStrategy,
  initialSlug = null,
}: Props) {
  const [slug, setSlug] = useState<string | null>(initialSlug);

  if (slug) {
    const paper = findPaperBySlug(slug);
    if (!paper) {
      return (
        <div className="card p-6">
          <p className="text-sm text-slate-500">No paper page found for “{slug}”.</p>
          <button
            type="button"
            onClick={() => setSlug(null)}
            className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            ← Back to Paper Replications
          </button>
        </div>
      );
    }
    return (
      <PaperDetail
        paper={paper}
        onBack={() => setSlug(null)}
        onRunPreset={onRunPreset}
        onOpenStrategy={onOpenStrategy}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="section-title mb-1">Live — runnable inspired demos</p>
        <p className="mb-3 text-xs text-slate-400">
          These pages explain the research idea and provide a simplified
          QuantLab demo. Full replication requires broader data than the
          current local-first version — none of these are full academic
          replications.
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {LIVE_PAPERS.map((p) => (
            <PaperCard
              key={p.id}
              paper={p}
              onOpen={() => setSlug(p.slug)}
              onRunPreset={onRunPreset}
            />
          ))}
        </div>
      </div>

      <div>
        <p className="section-title mb-1">Planned full replications & future modules</p>
        <p className="mb-3 text-xs text-slate-400">
          Listed for direction per Master Blueprint v3 —{" "}
          <span className="font-medium text-slate-500">not implemented</span>,
          no run buttons until they ship.
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {PLANNED_PAPERS.map((p) => (
            <PaperCard key={p.id} paper={p} onOpen={() => setSlug(p.slug)} />
          ))}
        </div>
      </div>

      <p className="text-[11px] text-slate-400">
        Paper pages are educational research material. They do not reproduce
        original performance figures, do not prove any strategy works, and are
        not investment advice. Use the Trust Layer before interpreting any
        demo result.
      </p>
    </div>
  );
}

function PaperCard({
  paper,
  onOpen,
  onRunPreset,
}: {
  paper: PaperEntry;
  onOpen: () => void;
  onRunPreset?: (preset: PaperRunPreset, paper: PaperEntry) => void;
}) {
  return (
    <div className="card flex flex-col gap-2 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-bold text-slate-900">{paper.title}</p>
          <p className="text-xs text-slate-400">
            {paper.authors} ({paper.year}) · {paper.category}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          <Badge cls={STATUS_STYLE[paper.status]}>{STATUS_LABEL[paper.status]}</Badge>
          <Badge cls={LEVEL_STYLE[paper.replicationLevel]}>
            {LEVEL_LABEL[paper.replicationLevel]}
          </Badge>
        </div>
      </div>
      <p className="text-sm text-slate-600">{paper.summary}</p>
      <div className="mt-1 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onOpen}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-blue-400 hover:text-blue-600"
        >
          Open replication page
        </button>
        {paper.runPreset && onRunPreset && (
          <button
            type="button"
            onClick={() => onRunPreset(paper.runPreset!, paper)}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-700"
          >
            Run inspired demo
          </button>
        )}
      </div>
    </div>
  );
}

function PaperDetail({
  paper,
  onBack,
  onRunPreset,
  onOpenStrategy,
}: {
  paper: PaperEntry;
  onBack: () => void;
  onRunPreset: (preset: PaperRunPreset, paper: PaperEntry) => void;
  onOpenStrategy: (slug: string) => void;
}) {
  const relatedModels = MODEL_REGISTRY.filter((m) =>
    paper.relatedStrategyIds.includes(m.id),
  );
  const statusLine =
    paper.replicationLevel === "inspired_demo"
      ? "Inspired demo available — a single-asset approximation of the research idea, not the paper's design."
      : paper.replicationLevel === "simplified_replication"
        ? "Simplified replication available — follows the paper's design with reduced scope."
        : paper.replicationLevel === "full_replication"
          ? "Full replication available."
          : "Planned — not implemented yet.";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          ← Paper Replications
        </button>
        <div className="flex gap-1.5">
          <Badge cls={STATUS_STYLE[paper.status]}>{STATUS_LABEL[paper.status]}</Badge>
          <Badge cls={LEVEL_STYLE[paper.replicationLevel]}>
            {LEVEL_LABEL[paper.replicationLevel]}
          </Badge>
        </div>
      </div>

      <div className="card p-5">
        <p className="text-lg font-bold text-slate-900">{paper.title}</p>
        <p className="text-xs text-slate-400">
          {paper.authors} ({paper.year}) · {paper.category}
        </p>
        <p className="mt-3 text-sm text-slate-600">{paper.summary}</p>
      </div>

      <Section title="Original Research Question">
        <p className="text-sm text-slate-600">{paper.researchQuestion}</p>
      </Section>

      <Section title="Core Idea">
        <p className="text-sm text-slate-600">{paper.coreIdea}</p>
      </Section>

      <Section title="Original Method (summary)">
        <Bullets items={paper.originalMethod} />
        <p className="mt-2 text-[11px] text-slate-400">
          Summary of the published methodology — original performance figures
          are not reproduced here; see the reference below.
        </p>
      </Section>

      <Section title="QuantLab Implementation Status">
        <p className="text-sm font-medium text-slate-700">{statusLine}</p>
        <div className="mt-2">
          <Bullets items={paper.quantlabToday} />
        </div>
      </Section>

      <Section title="Data Requirements for Full Replication">
        <Bullets items={paper.dataRequirements} />
      </Section>

      <Section title="Limitations">
        <Bullets items={paper.limitations} />
      </Section>

      <Section title="Trust Layer Workflow">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600">
          <li>Run the demo backtest with realistic transaction costs.</li>
          <li>Compare against the benchmark.</li>
          <li>Check the Data Source card for gaps and warnings.</li>
          <li>Run the Robustness Lab.</li>
          <li>Run the Stability Lab where supported.</li>
          <li>Export the report — the config hash fingerprints the assumptions.</li>
        </ol>
      </Section>

      {relatedModels.length > 0 && (
        <Section title="Related Strategy Pages">
          <div className="flex flex-wrap gap-2">
            {relatedModels.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => onOpenStrategy(m.slug)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-blue-400 hover:text-blue-600"
              >
                {m.name} →
              </button>
            ))}
          </div>
        </Section>
      )}

      {paper.runPreset ? (
        <div className="card p-5">
          <p className="section-title mb-3">Run Demo</p>
          <button
            type="button"
            onClick={() => onRunPreset(paper.runPreset!, paper)}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
          >
            {paper.runPreset.label}
          </button>
          <p className="mt-2 text-[11px] text-slate-400">
            Opens Backtest Studio with the strategy preselected
            {paper.runPreset.ticker ? ` (${paper.runPreset.ticker})` : ""} and
            default parameters — it never auto-runs. This is a simplified
            educational demo, not a full replication of the paper.
          </p>
        </div>
      ) : (
        <div className="card p-5">
          <p className="section-title mb-2">Status</p>
          <p className="text-sm text-slate-500">
            No runnable demo yet — this replication is{" "}
            {STATUS_LABEL[paper.status].toLowerCase()} and will activate with its
            future module.
          </p>
        </div>
      )}

      <p className="text-[11px] text-slate-400">Reference: {paper.reference}</p>
    </div>
  );
}
