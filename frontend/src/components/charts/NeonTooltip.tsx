"use client";

import { fmtMonthYear } from "@/lib/format";

interface TooltipEntry {
  name?: string;
  value?: number | string | null;
  color?: string;
}

interface NeonTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  /** Recharts passes the x-axis datum here — string date, number, or anything. */
  label?: unknown;
  /** Format a numeric series value (e.g. dollars or percent). */
  formatValue: (v: number) => string;
  /**
   * Format the header label. Defaults to defensive month/year date formatting;
   * pass a custom formatter when the x-axis is not date-based (e.g. histogram
   * buckets) so the header stays semantically correct.
   */
  formatLabel?: (label: unknown) => string;
  /** Border color — defaults to the accent; pass a semantic color for e.g. drawdown. */
  borderColor?: string;
  /** Box-shadow glow — defaults to the accent glow token. */
  glow?: string;
}

/**
 * Dark-glass chart tooltip with an accent (or semantic) neon border + glow.
 *
 * Series whose name starts with "_" (the glow/area helper series used by the
 * neon line technique) are filtered out so each datum appears once.
 */
export default function NeonTooltip({
  active,
  payload,
  label,
  formatValue,
  formatLabel = fmtMonthYear,
  borderColor = "var(--accent-border)",
  glow = "var(--accent-glow)",
}: NeonTooltipProps) {
  if (!active || !payload?.length) return null;

  const rows = payload.filter(
    (p): p is TooltipEntry & { name: string; value: number } =>
      typeof p.name === "string" &&
      !p.name.startsWith("_") &&
      typeof p.value === "number" &&
      Number.isFinite(p.value),
  );
  if (!rows.length) return null;

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: "rgba(10,14,24,0.94)",
        border: `1px solid ${borderColor}`,
        boxShadow: `${glow}, var(--sh-md)`,
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
      }}
    >
      <p className="mb-1 font-semibold" style={{ color: "var(--text-hi)" }}>
        {label != null ? formatLabel(label) : ""}
      </p>
      {rows.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-5">
          <span
            className="flex items-center gap-1.5"
            style={{ color: "var(--text-mut)" }}
          >
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: 9,
                background: p.color,
              }}
            />
            {p.name}
          </span>
          <span className="mono font-semibold" style={{ color: "var(--text-hi)" }}>
            {formatValue(p.value)}
          </span>
        </div>
      ))}
    </div>
  );
}
