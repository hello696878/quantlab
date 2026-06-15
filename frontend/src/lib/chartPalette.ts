/**
 * Centralized, deterministic chart palette for the Options Lab.
 *
 * Goals (from repeated feedback that charts looked too uniform / all-cyan):
 * - deterministic and stable across renders (index → fixed colour),
 * - dark-theme friendly with enough contrast,
 * - professional multi-colour (no uncontrolled rainbow).
 *
 * Use `seriesColor(i)` for per-series / per-path colours and the named
 * constants for specific roles (smile points, SVI fit, term structure, …).
 */

export const OPTIONS_CHART_PALETTE = [
  "#22d3ee", // cyan
  "#60a5fa", // blue
  "#a78bfa", // violet
  "#c084fc", // purple
  "#fbbf24", // amber
  "#34d399", // emerald
  "#f472b6", // pink
  "#2dd4bf", // teal
  "#fb923c", // orange
  "#e879f9", // fuchsia
] as const;

/** Deterministic colour for series/path index `i` (wraps around the palette). */
export function seriesColor(i: number): string {
  const n = OPTIONS_CHART_PALETTE.length;
  return OPTIONS_CHART_PALETTE[((i % n) + n) % n];
}

// Role-specific colours (distinct so raw vs fit, etc. never collide).
export const SMILE_RAW_COLOR = "#22d3ee"; // raw implied-vol points
export const SMILE_FIT_COLOR = "#fbbf24"; // SVI fitted curve
export const TERM_STRUCTURE_COLOR = "#a78bfa"; // ATM term-structure line

// Sequential heat scale for the vol surface (low → high), dark-theme friendly.
export const HEAT_STOPS = ["#3b82f6", "#22d3ee", "#34d399", "#fbbf24", "#f87171"] as const;

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

/** Map a value in [min, max] to a colour on the sequential heat scale. */
export function heatColor(value: number | null | undefined, min: number, max: number): string {
  if (value == null || !Number.isFinite(value)) return "rgba(148,163,184,0.12)";
  const t = max > min ? Math.min(1, Math.max(0, (value - min) / (max - min))) : 0.5;
  const x = Math.min(0.9999, t) * (HEAT_STOPS.length - 1);
  const i = Math.floor(x);
  const f = x - i;
  const [r0, g0, b0] = hexToRgb(HEAT_STOPS[i]);
  const [r1, g1, b1] = hexToRgb(HEAT_STOPS[i + 1]);
  const mix = (a: number, b: number) => Math.round(a + (b - a) * f);
  return `rgb(${mix(r0, r1)}, ${mix(g0, g1)}, ${mix(b0, b1)})`;
}
