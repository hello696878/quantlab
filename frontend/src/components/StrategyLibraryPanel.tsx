"use client";

import { useState } from "react";
import {
  LIVE_MODELS,
  PLANNED_MODELS,
  findModelBySlug,
  type ModelEntry,
  type ModelStatus,
} from "@/lib/modelRegistry";
import type { StrategyType } from "@/lib/types";

interface Props {
  /** Navigate to Backtest Studio with the strategy preselected + defaults. */
  onRunStrategy: (strategy: StrategyType) => void;
  /** Navigate to Strategy Comparison. */
  onOpenComparison: () => void;
  /** Initial detail slug (e.g. from the command palette); null = index. */
  initialSlug?: string | null;
}

const STATUS_STYLE: Record<ModelStatus, string> = {
  live: "bg-emerald-100 text-emerald-700",
  planned: "bg-slate-100 text-slate-500",
  research: "bg-violet-100 text-violet-700",
  future: "bg-slate-100 text-slate-400",
};

const STATUS_LABEL: Record<ModelStatus, string> = {
  live: "Live",
  planned: "Planned",
  research: "Research",
  future: "Future",
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

function FeatureChips({ model }: { model: ModelEntry }) {
  const f = model.supportedFeatures;
  if (!f) return null;
  const chips: string[] = [];
  if (f.backtest) chips.push("Backtest");
  if (f.benchmark) chips.push("Benchmark");
  if (f.robustness) chips.push("Robustness");
  if (f.sensitivity) chips.push("Sensitivity");
  if (f.longShort) chips.push("Long/Short");
  return (
    <div className="flex flex-wrap gap-1">
      {chips.map((c) => (
        <span
          key={c}
          className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500"
        >
          {c}
        </span>
      ))}
    </div>
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

/**
 * Strategy Library v1 — educational pages for the live strategies plus an
 * honest catalog of planned/research models (Blueprint v3).  Research
 * material, not investment advice; planned models never get run buttons.
 */
export default function StrategyLibraryPanel({
  onRunStrategy,
  onOpenComparison,
  initialSlug = null,
}: Props) {
  const [slug, setSlug] = useState<string | null>(initialSlug);

  if (slug) {
    const model = findModelBySlug(slug);
    if (!model) {
      return (
        <div className="card p-6">
          <p className="text-sm text-slate-500">
            No strategy page found for “{slug}”.
          </p>
          <button
            type="button"
            onClick={() => setSlug(null)}
            className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            ← Back to Strategy Library
          </button>
        </div>
      );
    }
    return (
      <ModelDetail
        model={model}
        onBack={() => setSlug(null)}
        onRunStrategy={onRunStrategy}
        onOpenComparison={onOpenComparison}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Live strategies */}
      <div>
        <p className="section-title mb-3">Live strategies</p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {LIVE_MODELS.map((m) => (
            <div key={m.id} className="card flex flex-col gap-2 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-bold text-slate-900">{m.name}</p>
                <div className="flex gap-1.5">
                  <Badge cls={STATUS_STYLE[m.status]}>{STATUS_LABEL[m.status]}</Badge>
                  <Badge cls="bg-blue-50 text-blue-700">
                    {m.difficulty === "core" ? "Core" : m.difficulty === "advanced" ? "Advanced" : "Frontier"}
                  </Badge>
                </div>
              </div>
              <p className="text-xs text-slate-400">{m.category}</p>
              <p className="text-sm text-slate-600">{m.description}</p>
              <FeatureChips model={m} />
              <div className="mt-1 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setSlug(m.slug)}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-blue-400 hover:text-blue-600"
                >
                  Open model page
                </button>
                {m.strategyId && (
                  <button
                    type="button"
                    onClick={() => onRunStrategy(m.strategyId!)}
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-700"
                  >
                    Run in Backtest Studio
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Planned / research / future */}
      <div>
        <p className="section-title mb-1">Catalog — planned & research</p>
        <p className="mb-3 text-xs text-slate-400">
          From the Master Blueprint v3 model catalog. These are{" "}
          <span className="font-medium text-slate-500">not implemented</span> —
          listed for direction, with no run buttons until they ship.
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {PLANNED_MODELS.map((m) => (
            <div key={m.id} className="card flex flex-col gap-2 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-700">{m.name}</p>
                <Badge cls={STATUS_STYLE[m.status]}>{STATUS_LABEL[m.status]}</Badge>
              </div>
              <p className="text-[11px] text-slate-400">{m.category}</p>
              <p className="text-xs text-slate-500">{m.description}</p>
            </div>
          ))}
        </div>
      </div>

      <p className="text-[11px] text-slate-400">
        Strategy pages are educational research material — hypotheses,
        assumptions, and failure modes. Nothing here is a trading
        recommendation or investment advice.
      </p>
    </div>
  );
}

function ModelDetail({
  model,
  onBack,
  onRunStrategy,
  onOpenComparison,
}: {
  model: ModelEntry;
  onBack: () => void;
  onRunStrategy: (strategy: StrategyType) => void;
  onOpenComparison: () => void;
}) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          ← Strategy Library
        </button>
        <div className="flex gap-1.5">
          <Badge cls={STATUS_STYLE[model.status]}>{STATUS_LABEL[model.status]}</Badge>
          <Badge cls="bg-blue-50 text-blue-700">
            {model.difficulty === "core" ? "Core" : model.difficulty === "advanced" ? "Advanced" : "Frontier"}
          </Badge>
          {model.supportedFeatures?.benchmark && (
            <Badge cls="bg-emerald-100 text-emerald-700">Trust Layer supported</Badge>
          )}
        </div>
      </div>

      <div className="card p-5">
        <p className="text-lg font-bold text-slate-900">{model.name}</p>
        <p className="text-xs text-slate-400">{model.category}</p>
        {model.overview && <p className="mt-3 text-sm text-slate-600">{model.overview}</p>}
      </div>

      {model.hypothesis && (
        <Section title="Hypothesis">
          <p className="text-sm text-slate-600">{model.hypothesis}</p>
        </Section>
      )}

      {model.signalLogic && model.signalLogic.length > 0 && (
        <Section title="Signal Logic">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
            {model.signalLogic.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </Section>
      )}

      {model.params && model.params.length > 0 && (
        <Section title="Parameters">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b-2 border-slate-200 text-left">
                  <th className="px-2 py-1.5 font-semibold text-slate-600">Parameter</th>
                  <th className="px-2 py-1.5 font-semibold text-slate-600">Default</th>
                  <th className="px-2 py-1.5 font-semibold text-slate-600">Meaning</th>
                  <th className="px-2 py-1.5 font-semibold text-slate-600">Reasonable range</th>
                  <th className="px-2 py-1.5 font-semibold text-slate-600">Extreme values</th>
                </tr>
              </thead>
              <tbody>
                {model.params.map((p) => (
                  <tr key={p.name} className="border-b border-slate-100 align-top">
                    <td className="px-2 py-1.5 font-mono text-xs text-slate-700">{p.name}</td>
                    <td className="px-2 py-1.5 font-mono text-xs text-slate-700">{p.defaultValue}</td>
                    <td className="px-2 py-1.5 text-xs text-slate-600">{p.meaning}</td>
                    <td className="px-2 py-1.5 text-xs text-slate-600">{p.range}</td>
                    <td className="px-2 py-1.5 text-xs text-slate-500">{p.extremes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            Defaults are demo-friendly starting points, not recommendations —
            run the Stability Lab before trusting any specific value.
          </p>
        </Section>
      )}

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {model.strengths && model.strengths.length > 0 && (
          <Section title="Strengths">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
              {model.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </Section>
        )}
        {model.failureModes && model.failureModes.length > 0 && (
          <Section title="Failure Modes">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
              {model.failureModes.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </Section>
        )}
      </div>

      {(model.costNotes || model.interactionNotes) && (
        <Section title="Costs, Sizing & Risk Interactions">
          {model.costNotes && <p className="text-sm text-slate-600">{model.costNotes}</p>}
          {model.interactionNotes && (
            <p className="mt-2 text-sm text-slate-600">{model.interactionNotes}</p>
          )}
        </Section>
      )}

      <Section title="Trust Layer Checklist">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600">
          <li>Run the baseline backtest with realistic transaction costs.</li>
          <li>Compare against the benchmark (buy &amp; hold or a custom ticker).</li>
          <li>Check the Data Source card for gaps, warnings, and actual range.</li>
          <li>Run the Robustness Lab (bootstrap the return path).</li>
          <li>
            Run the Stability Lab
            {model.supportedFeatures?.sensitivity
              ? " (parameter heatmap is supported for this strategy)."
              : " where supported (v1 sweeps SMA Crossover; this strategy is planned)."}
          </li>
          <li>Export the report — the config hash fingerprints the assumptions.</li>
        </ol>
        <p className="mt-2 text-[11px] text-slate-400">
          A strategy that survives this checklist is still a historical
          diagnostic, not a guarantee.
        </p>
      </Section>

      {model.status === "live" && model.strategyId ? (
        <div className="card p-5">
          <p className="section-title mb-3">Run This Strategy</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onRunStrategy(model.strategyId!)}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
            >
              Open in Backtest Studio
            </button>
            <button
              type="button"
              onClick={onOpenComparison}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-blue-400 hover:text-blue-600"
            >
              Compare with other strategies
            </button>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            Opens the Backtest form with this strategy and its default
            parameters preselected ({model.defaultTicker ?? "default ticker"}).
            Global preferences (cost model defaults, annualization, theme) are
            untouched.
          </p>
        </div>
      ) : (
        <div className="card p-5">
          <p className="section-title mb-2">Status</p>
          <p className="text-sm text-slate-500">
            This model is {STATUS_LABEL[model.status].toLowerCase()} — it is not
            implemented yet and cannot be backtested in QuantLab today.
          </p>
        </div>
      )}
    </div>
  );
}
