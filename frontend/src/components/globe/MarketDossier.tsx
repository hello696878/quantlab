"use client";

/**
 * Market dossier panel for the Global Markets Globe v1.1.
 *
 * Premium "financial-intelligence" card: sticky header (flag, region dot,
 * currency, exchange, bias pill, Static-sample badge, "Last updated: Static
 * sample") + six sections — Market Pulse, Macro Vitals, FX & Rates, Market
 * Structure, Sample Headlines, QuantLab Actions.
 *
 * Every value is static illustrative sample data (see lib/globe/markets.ts).
 * No live, real-time, or country-level financial data is fetched.
 */

import type { View } from "@/components/AppShell";
import MetricCard from "@/components/MetricCard";
import {
  REGION_COLORS,
  SENTIMENT_TONE,
  marketBias,
  type Market,
  type MarketIndex,
  type Sentiment,
} from "@/lib/globe/markets";
import { fmtPct } from "@/lib/format";

const SENTIMENT_COLOR: Record<"positive" | "danger" | "default", string> = {
  positive: "var(--pos)",
  danger: "var(--neg)",
  default: "var(--text-mut)",
};

function biasColor(bias: Sentiment): string {
  return SENTIMENT_COLOR[SENTIMENT_TONE[bias]];
}

/** Tiny dependency-free sparkline (illustrative shape only — no axis/units). */
function Sparkline({ data, up }: { data: number[]; up: boolean }) {
  const w = 96;
  const h = 26;
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / span) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const color = up ? "var(--pos)" : "var(--neg)";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}

function changeStyle(v: number): React.CSSProperties {
  return { color: v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)" };
}

function IndexRow({ idx }: { idx: MarketIndex }) {
  return (
    <div
      className="flex items-center justify-between gap-3 rounded-xl px-3 py-2"
      style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
          {idx.name}
        </p>
        <p className="mono text-[11px]" style={{ color: "var(--text-mut)" }}>
          {idx.ticker} · level: {idx.level}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Sparkline data={idx.sparkline} up={idx.changePct >= 0} />
        <span className="mono w-14 text-right text-sm font-semibold" style={changeStyle(idx.changePct)}>
          {fmtPct(idx.changePct, 2)}
        </span>
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="section-title mb-2">{children}</p>;
}

function StructureRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-xs" style={{ color: "var(--text-mut)" }}>
        {label}
      </span>
      <span className="text-right text-xs font-medium" style={{ color: "var(--text-hi)" }}>
        {value}
      </span>
    </div>
  );
}

interface MarketDossierProps {
  market: Market;
  onNav: (view: View) => void;
  onClose: () => void;
}

export default function MarketDossier({ market, onNav, onClose }: MarketDossierProps) {
  const accent = REGION_COLORS[market.region] ?? "var(--accent)";
  const bias = marketBias(market);
  const bColor = biasColor(bias);

  return (
    <div className="card overflow-hidden">
      {/* ── Sticky header ───────────────────────────────────────────────── */}
      <div
        className="sticky top-0 z-10 px-5 pb-3 pt-4"
        style={{ background: "rgba(10,14,24,0.92)", backdropFilter: "blur(10px)", borderBottom: "1px solid var(--line)" }}
      >
        {/* accent band */}
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 h-[3px]"
          style={{ background: `linear-gradient(90deg, ${accent}, transparent)` }}
        />
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span aria-hidden className="text-3xl leading-none">
              {market.flag}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold" style={{ color: "var(--text-hi)" }}>
                  {market.country}
                </h2>
                <span
                  aria-hidden
                  className="h-2 w-2 flex-shrink-0 rounded-full"
                  style={{ background: accent, boxShadow: `0 0 8px ${accent}` }}
                />
              </div>
              <p className="mt-0.5 text-xs" style={{ color: "var(--text-mut)" }}>
                <span style={{ color: accent }}>{market.region}</span> · {market.subregion}
              </p>
              <p className="mt-0.5 text-xs" style={{ color: "var(--text-mut)" }}>
                <span className="mono" style={{ color: "var(--text-hi)" }}>
                  {market.currency}
                </span>{" "}
                · {market.exchange}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dossier"
            className="flex-shrink-0 rounded-md px-2 py-1 text-xs font-medium transition-colors"
            style={{ border: "1px solid var(--line)", color: "var(--text-mut)" }}
          >
            ✕
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span
            className="mono rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ background: `color-mix(in oklch, ${bColor} 15%, transparent)`, border: `1px solid color-mix(in oklch, ${bColor} 35%, transparent)`, color: bColor }}
          >
            {bias}
          </span>
          <span
            className="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
          >
            Static demo data
          </span>
          <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>
            Last updated: Static sample
          </span>
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <div className="space-y-4 p-5">
        {/* Market Pulse */}
        <section>
          <SectionLabel>Market Pulse</SectionLabel>
          <div className="space-y-2">
            {market.indices.map((idx) => (
              <IndexRow key={idx.ticker} idx={idx} />
            ))}
          </div>
          <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Levels are placeholders; change % and sparklines are illustrative —
            delayed index quotes are planned.
          </p>
        </section>

        {/* Macro Vitals */}
        <section>
          <SectionLabel>Macro Vitals</SectionLabel>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <MetricCard label="GDP growth" value={`${market.macro.gdpGrowth.toFixed(1)}%`} tone="accent" />
            <MetricCard label="Inflation" value={`${market.macro.inflation.toFixed(1)}%`} tone="warn" />
            <MetricCard label="Unemployment" value={`${market.macro.unemployment.toFixed(1)}%`} />
            <MetricCard label="Policy rate" value={`${market.macro.policyRate}%`} tone="accent" />
            <MetricCard label="Debt / GDP" value={`${market.macro.debtToGdp}%`} />
          </div>
          <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Illustrative static figures — live FRED / macro wiring is planned.
          </p>
        </section>

        {/* FX & Rates */}
        <section>
          <SectionLabel>FX &amp; Rates</SectionLabel>
          <div className="rounded-xl p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
            <StructureRow label="Currency" value={market.currency} />
            {market.fx.map((f) => (
              <div key={f.pair} className="flex items-baseline justify-between gap-3 py-1">
                <span className="text-xs" style={{ color: "var(--text-mut)" }}>
                  {f.pair}
                </span>
                <span className="flex items-baseline gap-2">
                  <span className="text-xs font-medium" style={{ color: "var(--text-hi)" }}>
                    {f.value}
                  </span>
                  <span className="mono text-xs font-semibold" style={changeStyle(f.changePct)}>
                    {fmtPct(f.changePct, 2)}
                  </span>
                </span>
              </div>
            ))}
            <StructureRow label="Policy rate" value={`${market.macro.policyRate}%`} />
          </div>
          <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
            FX values are placeholders; live / delayed FX quotes are planned.
          </p>
        </section>

        {/* Market Structure */}
        <section>
          <SectionLabel>Market Structure</SectionLabel>
          <div className="rounded-xl p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
            <StructureRow label="Exchange" value={market.exchange} />
            <StructureRow label="Trading hours" value={market.tradingHours} />
            <StructureRow label="Settlement" value={market.marketStructure.settlement} />
            <StructureRow label="Market cap" value={market.marketStructure.marketCap} />
            <StructureRow label="Listed companies" value={market.marketStructure.listedCompanies} />
          </div>
          <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>
            {market.marketStructure.notes}
          </p>
        </section>

        {/* Sample Headlines */}
        <section>
          <SectionLabel>Sample Headlines</SectionLabel>
          <div className="space-y-2">
            {market.headlines.map((h) => {
              const color = SENTIMENT_COLOR[SENTIMENT_TONE[h.sentiment]];
              return (
                <div
                  key={h.title}
                  className="flex items-start justify-between gap-3 rounded-xl px-3 py-2"
                  style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
                >
                  <span className="text-xs" style={{ color: "var(--text-hi)" }}>
                    {h.title}
                  </span>
                  <span
                    className="flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                    style={{ border: `1px solid ${color}`, color }}
                  >
                    {h.sentiment}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Sample headlines — live news integration planned. Sentiment pills are
            illustrative, not a model output.
          </p>
        </section>

        {/* QuantLab Actions */}
        <section>
          <SectionLabel>QuantLab Actions</SectionLabel>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {market.links.map((l) => (
              <button
                key={l.label}
                type="button"
                onClick={() => onNav(l.view)}
                className="rounded-lg px-3 py-2 text-left text-xs font-semibold transition-colors"
                style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
              >
                {l.label} →
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Cross-links open the related QuantLab module; market-specific
            pre-filling is planned.
          </p>
        </section>
      </div>
    </div>
  );
}
