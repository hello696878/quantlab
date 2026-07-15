"use client";

import { useState } from "react";
import type {
  ExperimentStatus,
  ReproducibilityStatus,
} from "@/lib/experimentRegistry";
import {
  REPRO_LABELS,
  STATUS_LABELS,
  formatNumber,
} from "@/lib/experimentRegistry";

// ---------------------------------------------------------------------------
// Badges
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<ExperimentStatus, string> = {
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  running: "bg-blue-50 text-blue-700 border-blue-200",
  pending: "bg-slate-50 text-slate-600 border-slate-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  invalidated: "bg-amber-50 text-amber-700 border-amber-200",
};

const REPRO_STYLES: Record<ReproducibilityStatus, string> = {
  reproducible: "bg-emerald-50 text-emerald-700 border-emerald-200",
  partially_reproducible: "bg-amber-50 text-amber-700 border-amber-200",
  not_reproducible: "bg-red-50 text-red-700 border-red-200",
  unknown: "bg-slate-50 text-slate-500 border-slate-200",
};

export function StatusBadge({ status }: { status: ExperimentStatus }) {
  return (
    <span
      className={`inline-block max-w-full truncate rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? STATUS_STYLES.pending}`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export function ReproBadge({ status }: { status: ReproducibilityStatus }) {
  return (
    <span
      className={`inline-block max-w-full truncate rounded-full border px-2 py-0.5 text-xs font-medium ${REPRO_STYLES[status] ?? REPRO_STYLES.unknown}`}
    >
      {REPRO_LABELS[status] ?? status}
    </span>
  );
}

export function BaselineBadge({ active }: { active: boolean }) {
  if (!active) return <span className="text-slate-300">—</span>;
  return (
    <span className="inline-block rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
      ★ Baseline
    </span>
  );
}

// ---------------------------------------------------------------------------
// Copyable fingerprint
// ---------------------------------------------------------------------------

export function CopyValue({
  value,
  display,
  className = "",
}: {
  value: string | null | undefined;
  display?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-slate-400">—</span>;

  async function copy() {
    try {
      await navigator.clipboard.writeText(value as string);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // clipboard unavailable — silently ignore
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      title={`Copy: ${value}`}
      aria-label={`Copy ${value}`}
      className={`inline-flex items-center gap-1 font-mono text-xs text-slate-600 hover:text-blue-700 ${className}`}
    >
      <span className="truncate">{display ?? value}</span>
      <span className="text-[10px] text-slate-400">{copied ? "✓" : "⧉"}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Key/value table (handles nested JSON safely — never renders raw HTML)
// ---------------------------------------------------------------------------

function renderScalar(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function KeyValueTable({
  data,
  empty = "None",
}: {
  data: Record<string, unknown>;
  empty?: string;
}) {
  const keys = Object.keys(data).sort();
  if (keys.length === 0) {
    return <p className="text-sm text-slate-400">{empty}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <tbody>
          {keys.map((k) => (
            <tr key={k} className="border-b border-slate-50 last:border-0">
              <td className="whitespace-nowrap py-1.5 pr-4 align-top font-medium text-slate-600">
                {k}
              </td>
              <td className="break-words py-1.5 font-mono text-slate-800">
                {renderScalar(data[k])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Read-only JSON block (safe text rendering)
// ---------------------------------------------------------------------------

export function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-80 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

// ---------------------------------------------------------------------------
// Section container
// ---------------------------------------------------------------------------

export function DetailSection({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="card p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          {title}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}
