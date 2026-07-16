"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import { type CompareEntry, type RunComparison, compareRuns } from "@/lib/modelValidation";
import ErrorState from "@/components/ui/ErrorState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";

interface Props {
  aId: number;
  bId: number;
  aLabel: string;
  bLabel: string;
  onBack: () => void;
}

const GROUP_LABELS: Record<string, string> = {
  identity: "Identity",
  configuration: "Configuration",
  leakage: "Leakage & split integrity",
  aggregate_metrics_mean: "Aggregate metrics (mean across valid folds)",
};

const NEUTRAL_NOTE =
  "Differences are reported neutrally — neither run is labelled superior or recommended; split integrity is shown above performance metrics.";

export default function ModelValidationCompare({ aId, bId, aLabel, bLabel, onBack }: Props) {
  const [data, setData] = useState<RunComparison | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    compareRuns(aId, bId)
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, [aId, bId, tick]);

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
      >
        ← Back to runs
      </button>

      <div className="card p-4">
        <h2 className="text-lg font-bold text-slate-900">Compare validation runs</h2>
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
            {Object.entries(data.fingerprint_match).map(([name, match]) => (
              <span
                key={name}
                className={`rounded-full border px-2 py-0.5 font-medium ${
                  match
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-slate-200 bg-slate-50 text-slate-500"
                }`}
              >
                {name} fp: {match ? "match" : "differs"}
              </span>
            ))}
          </div>
        )}
        <p className="mt-2 text-xs text-slate-400">{NEUTRAL_NOTE}</p>
      </div>

      {error ? (
        <ErrorState
          title="Couldn’t compare runs"
          message={classifyApiError(error).message}
          onRetry={() => setTick((t) => t + 1)}
        />
      ) : !data ? (
        <SkeletonTable rows={6} cols={4} caption="Comparing…" />
      ) : (
        Object.entries(GROUP_LABELS).map(([key, label]) => {
          const entries = data.groups[key] ?? [];
          if (entries.length === 0) return null;
          return <Group key={key} label={label} entries={entries} />;
        })
      )}
    </div>
  );
}

function cell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function kindLabel(kind: CompareEntry["kind"]): string | null {
  if (kind === "same") return null;
  if (kind === "only_in_a") return "only A";
  if (kind === "only_in_b") return "only B";
  if (kind === "unavailable") return "n/a";
  return "changed";
}

function Group({ label, entries }: { label: string; entries: CompareEntry[] }) {
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">
        {label}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th scope="col" className="px-4 py-2 text-left">Field</th>
              <th scope="col" className="px-4 py-2 text-left">A</th>
              <th scope="col" className="px-4 py-2 text-left">B</th>
              <th scope="col" className="px-4 py-2 text-left">Δ</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr
                key={e.field}
                className={`border-b border-slate-50 last:border-0 ${e.kind !== "same" ? "bg-amber-50/40" : ""}`}
              >
                <td className="px-4 py-2 font-medium text-slate-700">
                  {e.field}
                  {kindLabel(e.kind) && (
                    <span className="ml-1.5 text-[10px] uppercase text-amber-600">{kindLabel(e.kind)}</span>
                  )}
                </td>
                <td className="max-w-[220px] truncate px-4 py-2 font-mono text-xs text-slate-700" title={cell(e.a)}>{cell(e.a)}</td>
                <td className="max-w-[220px] truncate px-4 py-2 font-mono text-xs text-slate-700" title={cell(e.b)}>{cell(e.b)}</td>
                <td className="px-4 py-2 text-xs text-slate-500">{e.note || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
