"use client";

import { useMemo, useState } from "react";
import type { RunSample, SplitRecord } from "@/lib/modelValidation";

/**
 * Split timeline (Phase 50.0): every sample's information interval
 * [prediction_time, evaluation_time] drawn as a horizontal bar on a **true
 * temporal x-axis** (not index-based), colored + patterned by assignment for
 * the selected split.  Shape/pattern accompanies color (invalid overlap uses a
 * dashed outline, purged uses hatching) so nothing is color-only, and the
 * table fallback lists the exact memberships.  Rendering is bounded to
 * MAX_ROWS samples with an explicit truncation note.
 */

const MAX_ROWS = 400;
const ROW_H = 8;
const ROW_GAP = 3;
const PAD_X = 8;
const WIDTH = 900;

const CATEGORY_COLORS: Record<string, string> = {
  train: "#34d399",
  test: "#60a5fa",
  purged: "#f59e0b",
  embargoed: "#c084fc",
  unused: "#475569",
  overlap: "#f87171",
};

const CATEGORY_LABELS: Record<string, string> = {
  train: "Retained training",
  test: "Test",
  purged: "Purged",
  embargoed: "Embargoed",
  unused: "Unused",
  overlap: "Invalid overlap",
};

interface Props {
  samples: RunSample[];
  split: SplitRecord;
}

export default function ModelValidationTimeline({ samples, split }: Props) {
  const [showTable, setShowTable] = useState(false);

  const { rows, t0, t1, truncated, categories } = useMemo(() => {
    const train = new Set(split.train_ids);
    const test = new Set(split.test_ids);
    const purged = new Set(split.purged_ids);
    const embargoed = new Set(split.embargoed_ids);
    const overlapTrain = new Set(
      ((split.diagnostics.remaining_overlap_examples as { train: string }[]) ?? []).map(
        (o) => o.train,
      ),
    );
    const cats = new Map<string, string>();
    const shown = samples.slice(0, MAX_ROWS);
    for (const s of shown) {
      let cat = "unused";
      if (overlapTrain.has(s.sample_id)) cat = "overlap";
      else if (test.has(s.sample_id)) cat = "test";
      else if (purged.has(s.sample_id)) cat = "purged";
      else if (embargoed.has(s.sample_id)) cat = "embargoed";
      else if (train.has(s.sample_id)) cat = "train";
      cats.set(s.sample_id, cat);
    }
    const times = shown.flatMap((s) => [
      new Date(s.prediction_time).getTime(),
      new Date(s.evaluation_time).getTime(),
    ]);
    return {
      rows: shown,
      t0: Math.min(...times),
      t1: Math.max(...times),
      truncated: samples.length > MAX_ROWS,
      categories: cats,
    };
  }, [samples, split]);

  const span = Math.max(t1 - t0, 1);
  const x = (iso: string) =>
    PAD_X + ((new Date(iso).getTime() - t0) / span) * (WIDTH - PAD_X * 2);
  const height = rows.length * (ROW_H + ROW_GAP) + 24;

  const present = new Set(Array.from(categories.values()));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3 text-xs" aria-hidden={false}>
          {Object.entries(CATEGORY_LABELS)
            .filter(([key]) => present.has(key))
            .map(([key, label]) => (
              <span key={key} className="inline-flex items-center gap-1.5 text-slate-600">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{
                    background: CATEGORY_COLORS[key],
                    outline: key === "overlap" ? "2px dashed #f87171" : undefined,
                  }}
                />
                {label}
              </span>
            ))}
        </div>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          {showTable ? "Hide membership table" : "Membership table"}
        </button>
      </div>

      <p className="text-xs text-slate-400">
        Bars span each sample&apos;s information interval [prediction → evaluation] on a true
        temporal axis{truncated ? ` — showing the first ${MAX_ROWS} of ${samples.length} samples` : ""}.
      </p>

      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <svg
          width={WIDTH}
          height={height}
          role="img"
          aria-label={`Split timeline for ${split.split_label}: ${split.train_ids.length} retained training, ${split.test_ids.length} test, ${split.purged_ids.length} purged, ${split.embargoed_ids.length} embargoed samples. A membership table alternative is available.`}
        >
          <defs>
            <pattern id="mv-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="4" height="4" fill={CATEGORY_COLORS.purged} opacity="0.55" />
              <line x1="0" y1="0" x2="0" y2="4" stroke="#7c2d12" strokeWidth="1.4" />
            </pattern>
          </defs>
          {rows.map((s, i) => {
            const cat = categories.get(s.sample_id) ?? "unused";
            const y = 12 + i * (ROW_H + ROW_GAP);
            const x1 = x(s.prediction_time);
            const x2 = Math.max(x(s.evaluation_time), x1 + 2);
            return (
              <g key={s.sample_id}>
                <rect
                  x={x1}
                  y={y}
                  width={x2 - x1}
                  height={ROW_H}
                  rx={2}
                  fill={cat === "purged" ? "url(#mv-hatch)" : CATEGORY_COLORS[cat]}
                  opacity={cat === "unused" ? 0.35 : 0.9}
                  stroke={cat === "overlap" ? "#b91c1c" : "none"}
                  strokeWidth={cat === "overlap" ? 1.5 : 0}
                  strokeDasharray={cat === "overlap" ? "4 2" : undefined}
                >
                  <title>
                    {`${s.sample_id} · ${CATEGORY_LABELS[cat]} · ${s.prediction_time.slice(0, 10)} → ${s.evaluation_time.slice(0, 10)}`}
                  </title>
                </rect>
              </g>
            );
          })}
        </svg>
      </div>

      {showTable && (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {(["test", "purged", "embargoed", "train"] as const).map((key) => {
            const ids =
              key === "test"
                ? split.test_ids
                : key === "purged"
                  ? split.purged_ids
                  : key === "embargoed"
                    ? split.embargoed_ids
                    : split.train_ids;
            return (
              <div key={key} className="rounded-lg border border-slate-100 p-3">
                <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {CATEGORY_LABELS[key]} ({ids.length})
                </h4>
                <p className="break-words font-mono text-[11px] leading-relaxed text-slate-600">
                  {ids.length ? ids.join(", ") : "—"}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
