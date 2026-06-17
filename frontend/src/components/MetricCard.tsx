/**
 * Shared metric/result card for the Rates and FX labs.
 *
 * Colours are driven by **explicit CSS design tokens** (inline style), NOT by
 * Tailwind numeric colour classes. This is deliberate: QuantLab's dark theme
 * remaps the Tailwind `slate` ramp to an *inverted* scale (low shades are dark
 * surfaces, high shades are bright text), so a class like `text-slate-100`
 * resolves to a near-invisible dark navy on dark cards. Using `var(--text-hi)`
 * etc. keeps values readable regardless of that remap.
 *
 * Tones:
 *   default  → bright primary text (var(--text-hi))
 *   accent   → themed bright accent (var(--accent-text))
 *   positive → emerald (gains / success)
 *   warn     → amber (warnings)
 *   danger   → red (errors / negative warnings)
 */

export type MetricTone = "default" | "accent" | "positive" | "warn" | "danger";

const TONE_COLOR: Record<MetricTone, string> = {
  default: "var(--text-hi)",
  accent: "var(--accent-text)",
  positive: "var(--emerald)",
  warn: "var(--warn)",
  danger: "var(--risk)",
};

export default function MetricCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: MetricTone;
}) {
  return (
    <div className="glass px-3 py-2 text-center">
      <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
        {label}
      </p>
      <p className="mono mt-0.5 text-sm font-semibold" style={{ color: TONE_COLOR[tone] }}>
        {value}
      </p>
    </div>
  );
}
