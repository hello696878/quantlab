"use client";

/**
 * ShockSlider — a labelled, accessible range control for the labs' deterministic
 * scenario shocks (Phase 31 UX upgrade). Pure UI: emits numbers, renders the
 * formatted current value, no network, no randomness. Dark-theme styled via the
 * project's CSS tokens.
 */

export default function ShockSlider({
  label,
  value,
  min,
  max,
  step,
  format,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  onChange: (v: number) => void;
}) {
  const neutral = Math.abs(value) < 1e-12 || Math.abs(value - 1) < 1e-12;
  return (
    <label className="block">
      <span className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>
          {label}
        </span>
        <span
          className="mono text-[11px] font-semibold"
          style={{ color: neutral ? "var(--text-faint)" : "var(--accent-text)" }}
        >
          {format(value)}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={(e) => {
          const v = Number.parseFloat(e.target.value);
          if (Number.isFinite(v)) onChange(v);
        }}
        className="mt-1 h-1.5 w-full cursor-pointer appearance-none rounded-full"
        style={{ background: "var(--glass)", accentColor: "var(--accent)" }}
      />
    </label>
  );
}
