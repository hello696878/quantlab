"use client";

/**
 * Market dossier panel for the Global Markets Globe v1.1.
 *
 * Premium "financial-intelligence" card: sticky header (flag, region dot,
 * currency, exchange, bias pill, Static-sample badge, "Last updated: Static
 * sample") + six sections — Market Pulse, Macro Vitals, FX & Rates, Market
 * Structure, Sample Headlines, QuantLab Actions.
 *
 * The bundled fallback is static illustrative data. The backend may optionally
 * source selected US macro fields from FRED; field-level provenance is shown
 * explicitly. Index, FX, structure, and headline values remain sample data.
 */

import { useEffect, useState } from "react";
import type { View } from "@/components/AppShell";
import MetricCard from "@/components/MetricCard";
import { buildGlobeShareUrl } from "@/lib/globe/permalink";
import {
  REGION_COLORS,
  SENTIMENT_TONE,
  marketBias,
  type MacroField,
  type MacroSourceState,
  type Market,
  type MarketIndex,
  type NewsSourceState,
  type QuoteSourceState,
  type Sentiment,
} from "@/lib/globe/markets";
import { fmtPct } from "@/lib/format";

const SENTIMENT_COLOR: Record<"positive" | "danger" | "default", string> = {
  positive: "var(--pos)",
  danger: "var(--neg)",
  default: "var(--text-mut)",
};
const MACRO_FIELD_LABELS: Record<MacroField, string> = {
  gdp_growth: "GDP growth",
  inflation: "Inflation",
  unemployment: "Unemployment",
  policy_rate: "Policy rate",
  debt_to_gdp: "Debt / GDP",
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

/** Honest macro provenance chip (static sample by default; FRED if enriched). */
function MacroSourceChip({
  source,
  asOf,
  fieldCount,
}: {
  source: MacroSourceState | undefined;
  asOf: string | null | undefined;
  fieldCount: number;
}) {
  const s = source ?? "static_sample";
  const label =
    s === "fred_live"
      ? `Macro: Partial FRED · ${fieldCount} field${fieldCount === 1 ? "" : "s"}${asOf ? ` · oldest ${asOf}` : ""}`
      : s === "fred_unavailable"
        ? "Macro: FRED unavailable, static fallback"
        : "Macro: Static sample";
  const color =
    s === "fred_live" ? "var(--pos)" : s === "fred_unavailable" ? "var(--warn)" : "var(--text-mut)";
  return (
    <span
      className="mono rounded-full px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide"
      style={{ background: `color-mix(in oklch, ${color} 14%, transparent)`, border: `1px solid color-mix(in oklch, ${color} 32%, transparent)`, color }}
    >
      {label}
    </span>
  );
}

function macroNote(market: Market): string {
  if (market.macroSource === "fred_live") {
    const details = (market.macroFredFields ?? [])
      .map((field) => {
        const observationDate = market.macroFredAsOf?.[field];
        return `${MACRO_FIELD_LABELS[field]}${observationDate ? ` (${observationDate})` : ""}`;
      })
      .join(", ");
    return `FRED-sourced fields: ${details || "Not available"}. All remaining macro values are static sample data; index/FX provenance is labelled separately, and structure/headlines remain sample data.`;
  }
  if (market.macroSource === "fred_unavailable") {
    return "FRED macro was requested but unavailable; showing static sample figures.";
  }
  return "Illustrative static figures; optional US FRED macro enrichment is off by default.";
}

/** Honest delayed-quote provenance chip for the index / FX sections. */
function QuoteSourceChip({
  label,
  source,
  asOf,
}: {
  label: string;
  source: QuoteSourceState | undefined;
  asOf: string | null | undefined;
}) {
  const s = source ?? "static_sample";
  const text =
    s === "delayed_quote"
      ? `${label}: delayed${asOf ? ` · as of ${asOf}` : ""}`
      : s === "quote_unavailable"
        ? `${label} unavailable — static fallback`
        : `${label}: static sample`;
  const color =
    s === "delayed_quote" ? "var(--pos)" : s === "quote_unavailable" ? "var(--warn)" : "var(--text-mut)";
  return (
    <span
      className="mono rounded-full px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide"
      style={{ background: `color-mix(in oklch, ${color} 14%, transparent)`, border: `1px solid color-mix(in oklch, ${color} 32%, transparent)`, color }}
    >
      {text}
    </span>
  );
}

/** Honest news provenance chip (static sample by default; never live in v1). */
function NewsSourceChip({ source }: { source: NewsSourceState | undefined }) {
  const s = source ?? "static_sample";
  const text =
    s === "news_unavailable" ? "News unavailable — static fallback" : "News: static sample";
  const color = s === "news_unavailable" ? "var(--warn)" : "var(--text-mut)";
  return (
    <span
      className="mono rounded-full px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide"
      style={{ background: `color-mix(in oklch, ${color} 14%, transparent)`, border: `1px solid color-mix(in oklch, ${color} 32%, transparent)`, color }}
    >
      {text}
    </span>
  );
}

function macroMetricLabel(
  label: string,
  field: MacroField,
  fredFields: Set<MacroField>,
): string {
  return fredFields.has(field) ? `${label} · FRED` : label;
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

/**
 * Build a short plain-text summary of the dossier for the "Copy summary" button.
 * Honest by construction: states static-by-default, the per-section source
 * status, that news is sample-only, and the not-investment-advice disclaimer.
 */
function buildDossierSummary(market: Market): string {
  const macro =
    market.macroSource === "fred_live"
      ? "Partial FRED-enriched (US); other fields static sample"
      : market.macroSource === "fred_unavailable"
        ? "FRED unavailable; static sample"
        : "Static sample";
  const hasDelayed =
    market.indicesSource === "delayed_quote" || market.fxSource === "delayed_quote";
  const quoteUnavail =
    market.indicesSource === "quote_unavailable" ||
    market.fxSource === "quote_unavailable";
  const quotes = hasDelayed
    ? "Delayed quotes on supported rows (not real-time); others static sample"
    : quoteUnavail
      ? "Quotes unavailable; static sample"
      : "Static sample";
  const news =
    market.newsSource === "news_unavailable"
      ? "Unavailable; static sample headlines"
      : "Sample headlines only; live news integration planned";
  return [
    `QuantLab Globe Dossier — ${market.country}`,
    `Region: ${market.region}`,
    `Primary index: ${market.indices[0]?.name ?? "n/a"}`,
    `Macro: ${macro}`,
    `Index/FX: ${quotes}`,
    `News: ${news}`,
    "Data status: Static sample by default; optional adapters may enrich supported fields.",
    "Educational use only. Not investment advice.",
  ].join("\n");
}

export default function MarketDossier({ market, onNav, onClose }: MarketDossierProps) {
  // Share-link copy feedback. Reset whenever the dossier switches markets.
  const [copyMsg, setCopyMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => setCopyMsg(null), [market.id]);

  async function handleShare() {
    const url = buildGlobeShareUrl({ market: market.id });
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        setCopyMsg({ ok: true, text: "Copied Globe dossier link." });
        return;
      }
    } catch {
      // fall through to the manual-copy message
    }
    setCopyMsg({
      ok: false,
      text: `Could not copy automatically. Copy the URL from your browser: ${url}`,
    });
  }

  async function handleCopySummary() {
    const summary = buildDossierSummary(market);
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(summary);
        setCopyMsg({ ok: true, text: "Copied dossier summary." });
        return;
      }
    } catch {
      // fall through to the manual-copy message
    }
    setCopyMsg({
      ok: false,
      text: "Could not copy automatically. Copy the text manually.",
    });
  }

  const accent = REGION_COLORS[market.region] ?? "var(--accent)";
  const bias = marketBias(market);
  const bColor = biasColor(bias);
  const fredFields = new Set<MacroField>(market.macroFredFields ?? []);
  const hasFredMacro =
    market.macroSource === "fred_live" && fredFields.size > 0;
  const hasDelayedQuotes =
    market.indicesSource === "delayed_quote" || market.fxSource === "delayed_quote";
  const quoteUnavailable =
    market.indicesSource === "quote_unavailable" || market.fxSource === "quote_unavailable";
  const dataLabel =
    hasFredMacro && hasDelayedQuotes
      ? "Static core + FRED + delayed quotes"
      : hasFredMacro
        ? "Static core + partial FRED"
        : hasDelayedQuotes
          ? "Static core + delayed quotes"
          : market.macroSource === "fred_unavailable" || quoteUnavailable
            ? "Static fallback data"
            : "Static demo data";

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
          <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-1.5">
            <button
              type="button"
              onClick={handleShare}
              aria-label={`Copy a shareable link to the ${market.country} market dossier`}
              className="rounded-md px-2 py-1 text-xs font-semibold transition-colors"
              style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
            >
              🔗 Share
            </button>
            <button
              type="button"
              onClick={handleCopySummary}
              aria-label={`Copy a plain-text summary of the ${market.country} dossier`}
              className="rounded-md px-2 py-1 text-xs font-semibold transition-colors"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
            >
              📋 Copy summary
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close dossier"
              className="rounded-md px-2 py-1 text-xs font-medium transition-colors"
              style={{ border: "1px solid var(--line)", color: "var(--text-mut)" }}
            >
              ✕
            </button>
          </div>
        </div>

        {copyMsg && (
          <p
            role="status"
            aria-live="polite"
            className="mt-2 break-words rounded-lg px-2.5 py-1.5 text-[11px]"
            style={{
              background: copyMsg.ok ? "var(--accent-softer)" : "var(--warn-soft)",
              border: `1px solid ${copyMsg.ok ? "var(--accent-line)" : "var(--line)"}`,
              color: copyMsg.ok ? "var(--accent-text)" : "var(--warn)",
            }}
          >
            {copyMsg.text}
          </p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span
            className="mono rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ background: `color-mix(in oklch, ${bColor} 15%, transparent)`, border: `1px solid color-mix(in oklch, ${bColor} 35%, transparent)`, color: bColor }}
          >
            Sample bias: {bias}
          </span>
          <span
            className="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
          >
            {dataLabel}
          </span>
          <span className="text-[10px]" style={{ color: "var(--text-faint)" }}>
            {hasFredMacro
              ? `Oldest FRED observation: ${market.macroAsOf ?? "date unavailable"}`
              : hasDelayedQuotes
                ? "Delayed quote dates are shown by section"
                : "Last updated: Static sample"}
          </span>
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <div className="space-y-4 p-5">
        {/* Market Pulse */}
        <section>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="section-title">Market Pulse</p>
            <QuoteSourceChip label="Index quotes" source={market.indicesSource} asOf={market.indicesAsOf} />
          </div>
          <div className="space-y-2">
            {market.indices.map((idx) => (
              <IndexRow key={idx.ticker} idx={idx} />
            ))}
          </div>
          <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
            {market.indicesSource === "delayed_quote"
              ? "Primary index level is a delayed quote (not real-time); sparklines remain illustrative."
              : market.indicesSource === "quote_unavailable"
                ? "Delayed index quote was requested but unavailable; showing static sample data."
                : "Levels shown as “Sample”; change % and sparklines are illustrative. Optional delayed index quotes are off by default."}
          </p>
        </section>

        {/* Macro Vitals */}
        <section>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="section-title">Macro Vitals</p>
            <MacroSourceChip
              source={market.macroSource}
              asOf={market.macroAsOf}
              fieldCount={fredFields.size}
            />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <MetricCard label={macroMetricLabel("GDP growth", "gdp_growth", fredFields)} value={`${market.macro.gdpGrowth.toFixed(1)}%`} tone="accent" />
            <MetricCard label={macroMetricLabel("Inflation", "inflation", fredFields)} value={`${market.macro.inflation.toFixed(1)}%`} tone="warn" />
            <MetricCard label={macroMetricLabel("Unemployment", "unemployment", fredFields)} value={`${market.macro.unemployment.toFixed(1)}%`} />
            <MetricCard label={macroMetricLabel("Policy rate", "policy_rate", fredFields)} value={`${market.macro.policyRate}%`} tone="accent" />
            <MetricCard label={macroMetricLabel("Debt / GDP", "debt_to_gdp", fredFields)} value={`${market.macro.debtToGdp}%`} />
          </div>
          <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
            {macroNote(market)}
          </p>
        </section>

        {/* FX & Rates */}
        <section>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="section-title">FX &amp; Rates</p>
            <QuoteSourceChip label="FX" source={market.fxSource} asOf={market.fxAsOf} />
          </div>
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
            {market.fxSource === "delayed_quote"
              ? "Primary FX rate is a delayed quote (not real-time)."
              : market.fxSource === "quote_unavailable"
                ? "Delayed FX quote was requested but unavailable; showing static sample data."
                : "FX values shown as “Sample”. Optional delayed FX quotes are off by default."}
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
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="section-title">Sample Headlines</p>
            <NewsSourceChip source={market.newsSource} />
          </div>
          {market.newsSource === "news_unavailable" && (
            <p
              role="status"
              className="mb-2 rounded-lg px-3 py-2 text-[11px]"
              style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
            >
              A news provider was requested but is not configured; showing static
              sample headlines.
            </p>
          )}
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
