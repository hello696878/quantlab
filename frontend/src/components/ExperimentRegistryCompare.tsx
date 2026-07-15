"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type ComparisonEntry,
  type ComparisonResponse,
  compareExperiments,
  formatNumber,
} from "@/lib/experimentRegistry";
import ErrorState from "@/components/ui/ErrorState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";

interface Props {
  aId: number;
  bId: number;
  aLabel: string;
  bLabel: string;
  onBack: () => void;
}

const GROUP_ORDER: { key: string; label: string }[] = [
  { key: "identity", label: "Identity" },
  { key: "fingerprints", label: "Fingerprints" },
  { key: "dataset", label: "Dataset" },
  { key: "seed", label: "Random seed" },
  { key: "parameters", label: "Parameters" },
  { key: "metrics", label: "Metrics" },
  { key: "provenance", label: "Provenance" },
  { key: "status_timing", label: "Status & timing" },
];

const NEUTRAL_NOTE =
  "Differences are reported neutrally — a larger or smaller value is not labelled better or worse, and no experiment is recommended.";

export default function ExperimentRegistryCompare({ aId, bId, aLabel, bLabel, onBack }: Props) {
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    compareExperiments(aId, bId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [aId, bId, tick]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          ← Back to registry
        </button>
      </div>

      <div className="card p-4">
        <h2 className="text-lg font-bold text-slate-900">Compare experiments</h2>
        <div className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-blue-600">A · #{aId}</span>
            <div className="truncate font-medium text-slate-800">{aLabel}</div>
          </div>
          <div className="rounded-lg border border-purple-100 bg-purple-50/50 p-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-purple-600">B · #{bId}</span>
            <div className="truncate font-medium text-slate-800">{bLabel}</div>
          </div>
        </div>
        {data && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <FingerprintPill label="Configuration" match={data.fingerprint_match.configuration} />
            <FingerprintPill label="Result" match={data.fingerprint_match.result} />
          </div>
        )}
        <p className="mt-2 text-xs text-slate-400">{NEUTRAL_NOTE}</p>
      </div>

      {error ? (
        <ErrorState
          title="Couldn’t compare experiments"
          message={classifyApiError(error).message}
          onRetry={() => setTick((t) => t + 1)}
        />
      ) : !data ? (
        <SkeletonTable rows={6} cols={4} caption="Comparing…" />
      ) : (
        GROUP_ORDER.map(({ key, label }) => {
          const entries = data.groups[key] ?? [];
          if (entries.length === 0) return null;
          return <CompareGroup key={key} label={label} entries={entries} />;
        })
      )}
    </div>
  );
}

function FingerprintPill({ label, match }: { label: string; match: boolean }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-medium ${
        match
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-slate-200 bg-slate-50 text-slate-500"
      }`}
    >
      {label} fingerprint: {match ? "match" : "differs"}
    </span>
  );
}

function CompareGroup({ label, entries }: { label: string; entries: ComparisonEntry[] }) {
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">
        {label}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-4 py-2 text-left">Field</th>
              <th scope="col" className="px-4 py-2 text-left">A</th>
              <th scope="col" className="px-4 py-2 text-left">B</th>
              <th scope="col" className="px-4 py-2 text-right">Δ</th>
              <th scope="col" className="px-4 py-2 text-right">Δ %</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr
                key={e.key}
                className={`border-b border-slate-50 last:border-0 ${
                  e.state !== "same" ? "bg-amber-50/40" : ""
                }`}
              >
                <td className="px-4 py-2 font-medium text-slate-700">
                  {e.key}
                  {e.state !== "same" && (
                    <span className="ml-1.5 text-[10px] uppercase text-amber-600">{stateLabel(e.state)}</span>
                  )}
                </td>
                <td className="px-4 py-2 font-mono text-xs text-slate-700">{cell(e.a)}</td>
                <td className="px-4 py-2 font-mono text-xs text-slate-700">{cell(e.b)}</td>
                <td className="px-4 py-2 text-right font-mono text-xs text-slate-600">
                  {e.abs_diff === null || e.abs_diff === undefined ? "—" : formatNumber(e.abs_diff)}
                </td>
                <td className="px-4 py-2 text-right font-mono text-xs text-slate-600">
                  {e.pct_diff === null || e.pct_diff === undefined ? "—" : `${formatNumber(e.pct_diff)}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function stateLabel(state: ComparisonEntry["state"]): string {
  if (state === "only_in_a") return "only A";
  if (state === "only_in_b") return "only B";
  return "changed";
}

function cell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
