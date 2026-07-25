"use client";

/**
 * Shared neutral status pills for the Portfolio Stress Lab (Phase 57.0),
 * following the ExperimentRegistryShared / DatasetLineageShared convention
 * so the panel and the detail view never import each other.
 */

import { INTEGRITY_LABELS } from "@/lib/portfolioStress";

export function IntegrityPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    verified_historical_window: "border-emerald-200 bg-emerald-50 text-emerald-700",
    verified_deterministic_rule: "border-emerald-200 bg-emerald-50 text-emerald-700",
    supplied_descriptive: "border-sky-200 bg-sky-50 text-sky-700",
    full_sample_descriptive: "border-amber-200 bg-amber-50 text-amber-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-500",
    invalid: "border-red-200 bg-red-50 text-red-700",
  };
  return (
    <span className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles[status] ?? styles.unknown}`}>
      {INTEGRITY_LABELS[status] ?? status}
    </span>
  );
}

export function CompletenessPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    complete: "border-emerald-200 bg-emerald-50 text-emerald-700",
    partial: "border-amber-200 bg-amber-50 text-amber-700",
    unavailable: "border-slate-200 bg-slate-50 text-slate-500",
  };
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles[status] ?? styles.unavailable}`}>
      {status}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
    running: "border-sky-200 bg-sky-50 text-sky-700",
    pending: "border-slate-200 bg-slate-50 text-slate-500",
    failed: "border-red-200 bg-red-50 text-red-700",
    invalidated: "border-slate-300 bg-slate-100 text-slate-500",
  };
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles[status] ?? styles.pending}`}>
      {status}
    </span>
  );
}
