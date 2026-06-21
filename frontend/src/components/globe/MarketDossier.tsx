"use client";

/**
 * Market dossier side panel for the Global Markets Globe.
 *
 * Every value shown here is static illustrative sample data (see
 * lib/globe/markets.ts). The panel makes that explicit with a badge and
 * per-section notes — no live, real-time, or country-level financial data is
 * fetched.
 */

import type { View } from "@/components/AppShell";
import MetricCard from "@/components/MetricCard";
import {
  SENTIMENT_TONE,
  type Market,
  type MarketIndex,
} from "@/lib/globe/markets";
import { fmtPct } from "@/lib/format";

const REGION_COLOR: Record<string, string> = {
  Americas: "var(--cyan)",
  Europe: "var(--violet)",
  "Asia-Pacific": "var(--emerald)",
};

const SENTIMENT_COLOR: Record<"positive" | "danger" | "default", string> = {
  positive: "var(--pos)",
  danger: "var(--neg)",
  default: "var(--text-mut)",
};

/** Tiny dependency-free sparkline (illustrative shape only — no axis/units). */
function Sparkline({ data }: { data: number[] }) {
  const w = 92;
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
  const up = data[data.length - 1] >= data[0];
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
      className="flex items-center justify-between gap-3 rounded-lg px-3 py-2"
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
        <Sparkline data={idx.sparkline} />
        <span className="mono text-sm font-semibold" style={changeStyle(idx.changePct)}>
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
  const accent = REGION_COLOR[market.region] ?? "var(--accent)";
  return (
    <div className="card p-5">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span aria-hidden className="text-3xl leading-none">
            {market.flag}
          </span>
          <div>
            <h2 className="text-lg font-bold" style={{ color: "var(--text-hi)" }}>
              {market.country}
            </h2>
            <p className="text-xs" style={{ color: "var(--text-mut)" }}>
              <span style={{ color: accent }}>{market.region}</span> · {market.subregion}
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
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

      <div className="mt-3">
        <span
          className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
          style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
        >
          Static demo data
        </span>
      </div>

      <div className="my-4 neon-divider" />

      {/* ── Equity indices ──────────────────────────────────────────────── */}
      <section>
        <SectionLabel>Equity indices</SectionLabel>
        <div className="space-y-2">
          {market.indices.map((idx) => (
            <IndexRow key={idx.ticker} idx={idx} />
          ))}
        </div>
        <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Levels are placeholders; daily change % and sparklines are illustrative
          shapes — delayed index quotes are planned.
        </p>
      </section>

      {/* ── Macro snapshot ──────────────────────────────────────────────── */}
      <section className="mt-4">
        <SectionLabel>Macro snapshot</SectionLabel>
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

      {/* ── Currency and rates ──────────────────────────────────────────── */}
      <section className="mt-4">
        <SectionLabel>Currency &amp; rates</SectionLabel>
        <div className="rounded-lg p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
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

      {/* ── Market structure ────────────────────────────────────────────── */}
      <section className="mt-4">
        <SectionLabel>Market structure</SectionLabel>
        <div className="rounded-lg p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
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

      {/* ── News placeholder ────────────────────────────────────────────── */}
      <section className="mt-4">
        <SectionLabel>Market news</SectionLabel>
        <div className="space-y-2">
          {market.headlines.map((h) => {
            const color = SENTIMENT_COLOR[SENTIMENT_TONE[h.sentiment]];
            return (
              <div
                key={h.title}
                className="flex items-start justify-between gap-3 rounded-lg px-3 py-2"
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
          Sample headlines — live news integration planned. Sentiment tags are
          illustrative, not a model output.
        </p>
      </section>

      {/* ── Cross-links ─────────────────────────────────────────────────── */}
      <section className="mt-4">
        <SectionLabel>Open in QuantLab</SectionLabel>
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
  );
}
