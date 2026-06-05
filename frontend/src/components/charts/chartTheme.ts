/**
 * Shared chart theme constants for the neon quant-terminal charts.
 *
 * Accent-dependent colors are resolved at runtime from CSS variables via
 * `useAccentColors` (so they follow the theme); the values here are the
 * theme-independent pieces — grid, axes, the muted benchmark, and the fixed
 * semantic danger ramp used by drawdown charts.
 */

/** Subtle gridlines that don't fight the data. */
export const CHART_GRID = "rgba(255,255,255,0.06)";
/** Axis tick label color (muted slate). */
export const CHART_AXIS = "#79839a";
/** Faint axis baseline. */
export const CHART_AXIS_LINE = "rgba(255,255,255,0.10)";
/** Initial-capital / zero reference line. */
export const CHART_REF_LINE = "rgba(255,255,255,0.18)";

/**
 * Benchmark series — intentionally muted blue-slate and subordinate, never the
 * accent, so the strategy line stays the visual hero.
 */
export const BENCHMARK_MUTED = "#7c8aa5";

/** Semantic danger colors (drawdown / losses — never themed by the accent). */
export const DANGER = "#ef4444";
export const DANGER_SOFT = "#f97316";

/** Opacity of the wide "glow" underlay line behind a primary series. */
export const GLOW_OPACITY = 0.18;
/** Stroke width of the glow underlay relative to the main line. */
export const GLOW_WIDTH = 6;
/** Main primary line stroke width. */
export const MAIN_WIDTH = 2.5;
