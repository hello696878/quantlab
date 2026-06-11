"use client";

import type { Reproducibility } from "@/lib/types";
import { toast } from "@/lib/toast";

interface Props {
  reproducibility: Reproducibility;
  /** Saved-backtest id, when this result has been saved (enables the local link copy). */
  savedId?: number | null;
}

/** Clipboard write with graceful fallback — never throws into React. */
export async function copyText(text: string, successTitle: string): Promise<void> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      toast.success(successTitle);
      return;
    }
    throw new Error("Clipboard API unavailable");
  } catch {
    toast.warning(
      "Clipboard unavailable",
      "Copy manually: " + (text.length > 80 ? text.slice(0, 77) + "…" : text),
    );
  }
}

/**
 * Local-first reproducibility fingerprint for a backtest result.  The hash
 * identifies normalized *input* assumptions — it is not a public URL and does
 * not guarantee identical future output if the data provider revises history.
 */
export default function ReproducibilityCard({ reproducibility, savedId }: Props) {
  const r = reproducibility;

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="section-title">Reproducibility</p>
        <span className="text-xs text-slate-500">{r.schema_version}</span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span
          className="mono rounded-lg bg-slate-100 px-2.5 py-1 text-sm font-semibold text-slate-700"
          title={r.config_hash_full}
        >
          {r.config_hash}
        </span>
        <button
          type="button"
          onClick={() => copyText(r.config_hash_full, "Config hash copied")}
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
        >
          Copy hash
        </button>
        <button
          type="button"
          onClick={() => copyText(r.canonical_config_json, "Canonical config copied")}
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
        >
          Copy config JSON
        </button>
        {typeof savedId === "number" && (
          <button
            type="button"
            onClick={() =>
              copyText(
                `Saved backtest #${savedId} · config ${r.config_hash}`,
                "Local result reference copied",
              )
            }
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            Copy local reference
          </button>
        )}
      </div>

      <p className="mt-3 text-[11px] text-slate-400">
        Same normalized config produces the same hash — a local-first fingerprint
        for reproducing and auditing backtest assumptions (it is not a public
        URL). Defaults are normalized first, so a legacy request and its explicit
        equivalent hash identically.
        {typeof savedId !== "number" &&
          " Save this backtest to keep the hash with a local saved result."}
      </p>
      <p className="mt-1 text-[11px] text-slate-400">
        Config hashes identify input assumptions; they cannot guarantee identical
        future output if the data provider revises historical data — audit
        alongside the Data Source diagnostics.
      </p>
    </div>
  );
}
