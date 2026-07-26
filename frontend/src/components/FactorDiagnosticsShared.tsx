"use client";

/**
 * Shared neutral status pills for the Factor Diagnostics Lab (Phase 59.0),
 * following the PortfolioAttributionShared / PortfolioStressShared convention
 * so the panel and the detail view never import each other.
 */

import { INTEGRITY_LABELS, RANK_LABELS } from "@/lib/factorDiagnostics";

export function IntegrityPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    verified_from_validation_split: "border-emerald-200 bg-emerald-50 text-emerald-700",
    verified_causal_lag: "border-emerald-200 bg-emerald-50 text-emerald-700",
    verified_trailing_estimation: "border-emerald-200 bg-emerald-50 text-emerald-700",
    supplied_descriptive: "border-sky-200 bg-sky-50 text-sky-700",
    contemporaneous_descriptive: "border-sky-200 bg-sky-50 text-sky-700",
    full_sample_descriptive: "border-amber-200 bg-amber-50 text-amber-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-500",
    invalid: "border-red-200 bg-red-50 text-red-700",
  };
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${
        styles[status] ?? styles.unknown
      }`}
    >
      {INTEGRITY_LABELS[status] ?? status}
    </span>
  );
}

export function RankPill({ status }: { status: string | null }) {
  const styles: Record<string, string> = {
    full_rank: "border-emerald-200 bg-emerald-50 text-emerald-700",
    rank_deficient_descriptive: "border-amber-200 bg-amber-50 text-amber-700",
  };
  const key = status ?? "";
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${
        styles[key] ?? "border-slate-200 bg-slate-50 text-slate-500"
      }`}
    >
      {RANK_LABELS[key] ?? "rank unavailable"}
    </span>
  );
}

export function ReconciliationPill({ status }: { status: string | null }) {
  const styles: Record<string, string> = {
    reconciled: "border-emerald-200 bg-emerald-50 text-emerald-700",
    mismatch: "border-amber-200 bg-amber-50 text-amber-700",
    unavailable: "border-slate-200 bg-slate-50 text-slate-500",
  };
  const key = status ?? "unavailable";
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${
        styles[key] ?? styles.unavailable
      }`}
    >
      {key}
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
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${
        styles[status] ?? styles.unavailable
      }`}
    >
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
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium ${
        styles[status] ?? styles.pending
      }`}
    >
      {status}
    </span>
  );
}
