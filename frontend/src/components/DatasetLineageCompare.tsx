"use client";

import { useEffect, useState } from "react";
import { classifyApiError } from "@/lib/api";
import {
  type DriftEntry,
  type VersionComparison,
  compareVersions,
} from "@/lib/datasetRegistry";
import ErrorState from "@/components/ui/ErrorState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import { DriftBadge } from "@/components/DatasetLineageShared";

interface Props {
  aId: number;
  bId: number;
  contextLabel: string;
  onBack: () => void;
}

const NEUTRAL_NOTE =
  "Differences are reported neutrally — schema drift is described, not judged; a larger dataset is not automatically better; no version is recommended.";

export default function DatasetLineageCompare({ aId, bId, contextLabel, onBack }: Props) {
  const [data, setData] = useState<VersionComparison | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    compareVersions(aId, bId)
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
        ← Back
      </button>

      <div className="card p-4">
        <h2 className="text-lg font-bold text-slate-900">Compare dataset versions</h2>
        <p className="mt-0.5 text-sm text-slate-500">
          {contextLabel} — version #{aId} (A) vs #{bId} (B)
        </p>
        {data && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <DriftBadge driftClass={data.drift_class} />
            {Object.entries(data.fingerprints).map(([name, match]) => (
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
          title="Couldn’t compare versions"
          message={classifyApiError(error).message}
          onRetry={() => setTick((t) => t + 1)}
        />
      ) : !data ? (
        <SkeletonTable rows={6} cols={4} caption="Comparing…" />
      ) : (
        <>
          <EntryTable title="Identity & context" entries={data.identity} onlyChanged={false} />
          <EntryTable title={`Schema drift (${data.drift_class.replace(/_/g, " ")})`} entries={data.schema_drift} onlyChanged={false} />
          <EntryTable title="Size metrics" entries={data.metrics} onlyChanged={false} />
          {data.provenance_changes.length > 0 && (
            <EntryTable title="Provenance changes" entries={data.provenance_changes} onlyChanged={false} />
          )}
          <div className="card p-4">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Quality checks
            </h3>
            <div className="grid gap-3 md:grid-cols-2">
              {(["a", "b"] as const).map((side) => (
                <div key={side}>
                  <h4 className="mb-1 text-xs font-semibold text-slate-500">
                    {side.toUpperCase()} · #{side === "a" ? data.a_id : data.b_id}
                  </h4>
                  {data.quality[side]?.length ? (
                    <ul className="space-y-1 text-xs text-slate-600">
                      {data.quality[side].map((line, i) => (
                        <li key={i} className="font-mono">{line}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-slate-400">No checks recorded.</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
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

function EntryTable({
  title,
  entries,
  onlyChanged,
}: {
  title: string;
  entries: DriftEntry[];
  onlyChanged: boolean;
}) {
  const rows = onlyChanged ? entries.filter((e) => e.kind !== "same") : entries;
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-sm font-semibold text-slate-700">
        {title}
      </div>
      {rows.length === 0 ? (
        <p className="px-4 py-3 text-sm text-slate-400">No differences.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th scope="col" className="px-4 py-2 text-left">Kind</th>
                <th scope="col" className="px-4 py-2 text-left">Field</th>
                <th scope="col" className="px-4 py-2 text-left">A</th>
                <th scope="col" className="px-4 py-2 text-left">B</th>
                <th scope="col" className="px-4 py-2 text-left">Note</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e, i) => (
                <tr
                  key={`${e.kind}-${e.field}-${i}`}
                  className={`border-b border-slate-50 last:border-0 ${e.kind !== "same" ? "bg-amber-50/40" : ""}`}
                >
                  <td className="whitespace-nowrap px-4 py-2 text-xs text-slate-500">{e.kind.replace(/_/g, " ")}</td>
                  <td className="px-4 py-2 font-medium text-slate-700">{e.field ?? "—"}</td>
                  <td className="max-w-[220px] truncate px-4 py-2 font-mono text-xs text-slate-700" title={cell(e.a)}>{cell(e.a)}</td>
                  <td className="max-w-[220px] truncate px-4 py-2 font-mono text-xs text-slate-700" title={cell(e.b)}>{cell(e.b)}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">{e.note || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
