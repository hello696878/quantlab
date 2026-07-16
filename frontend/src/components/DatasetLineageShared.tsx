"use client";

import type { DriftClass, ProvenanceStatus, QualityStatus } from "@/lib/datasetRegistry";
import { DRIFT_LABELS } from "@/lib/datasetRegistry";

const QUALITY_STYLES: Record<QualityStatus, string> = {
  passed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  skipped: "bg-slate-50 text-slate-500 border-slate-200",
  unknown: "bg-slate-50 text-slate-500 border-slate-200",
};

const PROVENANCE_STYLES: Record<ProvenanceStatus, string> = {
  complete: "bg-emerald-50 text-emerald-700 border-emerald-200",
  partial: "bg-amber-50 text-amber-700 border-amber-200",
  unknown: "bg-slate-50 text-slate-500 border-slate-200",
  invalidated: "bg-red-50 text-red-700 border-red-200",
};

const DRIFT_STYLES: Record<DriftClass, string> = {
  none: "bg-emerald-50 text-emerald-700 border-emerald-200",
  compatible: "bg-emerald-50 text-emerald-700 border-emerald-200",
  potentially_breaking: "bg-amber-50 text-amber-700 border-amber-200",
  breaking: "bg-red-50 text-red-700 border-red-200",
  unknown: "bg-slate-50 text-slate-500 border-slate-200",
};

export function QualityBadge({ status }: { status: QualityStatus | null }) {
  const s = status ?? "unknown";
  return (
    <span
      className={`inline-block max-w-full truncate rounded-full border px-2 py-0.5 text-xs font-medium ${QUALITY_STYLES[s] ?? QUALITY_STYLES.unknown}`}
    >
      {s}
    </span>
  );
}

export function ProvenanceBadge({ status }: { status: ProvenanceStatus }) {
  return (
    <span
      className={`inline-block max-w-full truncate rounded-full border px-2 py-0.5 text-xs font-medium ${PROVENANCE_STYLES[status] ?? PROVENANCE_STYLES.unknown}`}
    >
      provenance: {status}
    </span>
  );
}

export function DriftBadge({ driftClass }: { driftClass: DriftClass }) {
  return (
    <span
      className={`inline-block max-w-full truncate rounded-full border px-2 py-0.5 text-xs font-medium ${DRIFT_STYLES[driftClass] ?? DRIFT_STYLES.unknown}`}
    >
      {DRIFT_LABELS[driftClass] ?? driftClass}
    </span>
  );
}
