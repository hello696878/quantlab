"use client";

/**
 * Shared pills for the Signal Ensemble Lab (Phase 61.0) — neutral,
 * state-first presentation; nothing here labels an ensemble good or bad.
 */

import { INTEGRITY_LABELS } from "@/lib/signalEnsemble";

export function IntegrityPill({ status }: { status: string }) {
  const label = INTEGRITY_LABELS[status] ?? status;
  const tone =
    status === "invalid"
      ? "border-red-300 bg-red-50 text-red-700"
      : status.startsWith("verified")
        ? "border-emerald-300 bg-emerald-50 text-emerald-700"
        : status === "unknown"
          ? "border-slate-300 bg-slate-50 text-slate-600"
          : "border-amber-300 bg-amber-50 text-amber-700";
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}
      title={status}
    >
      {label}
    </span>
  );
}

export function CompletenessPill({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-slate-400">—</span>;
  const tone =
    status === "complete"
      ? "border-emerald-300 bg-emerald-50 text-emerald-700"
      : status === "partial"
        ? "border-amber-300 bg-amber-50 text-amber-700"
        : "border-slate-300 bg-slate-50 text-slate-600";
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}
    >
      {status}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const tone =
    status === "completed"
      ? "border-emerald-300 bg-emerald-50 text-emerald-700"
      : status === "failed" || status === "invalidated"
        ? "border-red-300 bg-red-50 text-red-700"
        : status === "running"
          ? "border-blue-300 bg-blue-50 text-blue-700"
          : "border-slate-300 bg-slate-50 text-slate-600";
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}
    >
      {status}
    </span>
  );
}

export function ReconciliationPill({ state }: { state: string | null | undefined }) {
  if (!state) return <span className="text-slate-400">—</span>;
  const tone =
    state === "reconciled"
      ? "border-emerald-300 bg-emerald-50 text-emerald-700"
      : state === "not_applicable"
        ? "border-slate-300 bg-slate-50 text-slate-600"
        : "border-red-300 bg-red-50 text-red-700";
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}
    >
      {state.replace(/_/g, " ")}
    </span>
  );
}
