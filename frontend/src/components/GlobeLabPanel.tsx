"use client";

/**
 * Global Markets Globe v1.1 — "mission control" page.
 *
 * Three-zone, width-aware layout (wide / mid / narrow via a container
 * ResizeObserver): a left rail (search · region filter · market list ·
 * quick-jump), a center canvas globe (DataGlobe) with overlay controls + a
 * legend, and a right dossier panel — plus a bottom region "tape".
 *
 * All data is static illustrative sample data — no live market data, FX,
 * macro, or news is fetched (see lib/globe/markets.ts).
 */

import { useEffect, useRef, useState } from "react";
import type { View } from "@/components/AppShell";
import DataGlobe from "@/components/globe/DataGlobe";
import MarketDossier from "@/components/globe/MarketDossier";
import {
  MARKETS,
  MARKET_ARCS,
  MARKET_REGIONS,
  REGION_COLORS,
  STATIC_DATA_NOTICE,
  filterMarkets,
  meanIndexChange,
  regionRollup,
  type Market,
  type MarketRegion,
} from "@/lib/globe/markets";
import { fetchGlobeMarkets } from "@/lib/globe/remote";
import { fmtPct } from "@/lib/format";

type Mode = "wide" | "mid" | "narrow";

function useContainerMode(ref: React.RefObject<HTMLElement>): Mode {
  const [mode, setMode] = useState<Mode>("wide");
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width;
      setMode(w >= 1120 ? "wide" : w >= 720 ? "mid" : "narrow");
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return mode;
}

const QUICK_JUMP: { id: string; label: string }[] = [
  { id: "us", label: "US" },
  { id: "uk", label: "UK" },
  { id: "jp", label: "Japan" },
  { id: "hk", label: "Hong Kong" },
];

function changeColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

function MarketListItem({
  market,
  active,
  onSelect,
}: {
  market: Market;
  active: boolean;
  onSelect: () => void;
}) {
  const lead = market.indices[0];
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors"
      style={{
        background: active ? "var(--accent-softer)" : "var(--glass)",
        border: `1px solid ${active ? "var(--accent-line)" : "var(--line)"}`,
        boxShadow: active ? "inset 3px 0 0 var(--accent)" : undefined,
      }}
    >
      <span
        aria-hidden
        className="h-2 w-2 flex-shrink-0 rounded-full"
        style={{ background: REGION_COLORS[market.region], boxShadow: `0 0 6px ${REGION_COLORS[market.region]}` }}
      />
      <span aria-hidden className="text-base leading-none">
        {market.flag}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold" style={{ color: "var(--text-hi)" }}>
          {market.country}
        </span>
        <span className="mono block truncate text-[10px]" style={{ color: "var(--text-mut)" }}>
          {market.currency} · {market.exchange}
        </span>
      </span>
      {lead && (
        <span className="mono flex-shrink-0 text-xs font-semibold" style={{ color: changeColor(lead.changePct) }}>
          {fmtPct(lead.changePct, 2)}
        </span>
      )}
    </button>
  );
}

interface GlobeLabPanelProps {
  initialMarketId?: string | null;
  onNav: (view: View) => void;
}

export default function GlobeLabPanel({ initialMarketId, onNav }: GlobeLabPanelProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const mode = useContainerMode(wrapRef);

  const [region, setRegion] = useState<MarketRegion | "All">("All");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(initialMarketId ?? null);
  const [autoRotate, setAutoRotate] = useState(true);
  const [resetSignal, setResetSignal] = useState(0);

  // Market data: render bundled static data immediately, then upgrade to the
  // backend data layer if reachable (else fall back with a non-blocking warning).
  const [markets, setMarkets] = useState<Market[]>(MARKETS);
  const [dataStatus, setDataStatus] = useState<"loading" | "backend" | "fallback">("loading");
  const [dataNotice, setDataNotice] = useState(STATIC_DATA_NOTICE);
  const [warnings, setWarnings] = useState<string[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    let cancelled = false;
    const timeoutId = window.setTimeout(() => ctrl.abort(), 5000);
    fetchGlobeMarkets(ctrl.signal)
      .then((res) => {
        if (cancelled) return;
        setMarkets(res.markets);
        setDataNotice(res.notice);
        setWarnings(res.warnings);
        setDataStatus("backend");
      })
      .catch(() => {
        if (cancelled) return;
        setMarkets(MARKETS);
        setDataNotice(STATIC_DATA_NOTICE);
        setWarnings([]);
        setDataStatus("fallback");
      });
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
      ctrl.abort();
    };
  }, []);

  const filtering = region !== "All" || query.trim() !== "";
  const filtered = filterMarkets(region, query, markets);
  const activeIds = filtering ? new Set(filtered.map((m) => m.id)) : null;
  const selected = markets.find((m) => m.id === selectedId) ?? null;
  const rollups = regionRollup(markets);
  const fredLive = markets.some((m) => m.macroSource === "fred_live");
  const fredUnavailable = !fredLive && markets.some((m) => m.macroSource === "fred_unavailable");
  const macroChip = fredLive
    ? { text: "FRED macro live (US)", tone: "var(--pos)" }
    : fredUnavailable
      ? { text: "FRED unavailable — static macro", tone: "var(--warn)" }
      : { text: "Live macro planned", tone: "var(--text-mut)" };

  useEffect(() => {
    if (!selectedId || !filtering) return;
    if (!filterMarkets(region, query, markets).some((market) => market.id === selectedId)) {
      setSelectedId(null);
    }
  }, [filtering, query, region, selectedId, markets]);

  function resetView() {
    setRegion("All");
    setQuery("");
    setSelectedId(null);
    setResetSignal((k) => k + 1);
  }

  // ── Layout grids per container mode ─────────────────────────────────────
  const gridStyle: React.CSSProperties =
    mode === "wide"
      ? { display: "grid", gap: 16, gridTemplateColumns: "248px minmax(0,1fr) 372px", gridTemplateAreas: '"rail globe dossier"', alignItems: "start" }
      : mode === "mid"
        ? { display: "grid", gap: 16, gridTemplateColumns: "minmax(0,1fr) 360px", gridTemplateAreas: '"globe globe" "rail dossier"', alignItems: "start" }
        : { display: "grid", gap: 16, gridTemplateColumns: "minmax(0,1fr)", gridTemplateAreas: '"globe" "rail" "dossier"' };

  const globeHeight = mode === "wide" ? 560 : mode === "mid" ? 460 : 360;
  const dossierScroll: React.CSSProperties =
    mode === "narrow" ? {} : { maxHeight: "calc(100vh - 7rem)", overflowY: "auto" };

  return (
    <div ref={wrapRef} className="space-y-4">
      {/* ── Page header / honesty disclaimer ──────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>
                Global Markets Globe
              </h1>
              <span
                className="mono rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
              >
                v1.1
              </span>
            </div>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              A mission-control map of {markets.length} sample markets backed by a
              typed country-dossier data layer. Drag the globe to rotate, click a
              marker — or a row in the rail — to open a country dossier with
              indices, macro vitals, currency &amp; rates, market structure,
              sample headlines, and QuantLab cross-links.
            </p>
          </div>
          <span
            className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide"
            style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
          >
            Static data v1.1
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {dataNotice} Not real-time market data and not investment advice.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span
            className="mono rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{
              background: dataStatus === "fallback" ? "var(--warn-soft)" : "var(--accent-softer)",
              border: `1px solid ${dataStatus === "fallback" ? "var(--line)" : "var(--accent-line)"}`,
              color: dataStatus === "fallback" ? "var(--warn)" : "var(--accent-text)",
            }}
          >
            {dataStatus === "backend"
              ? "Backend static dataset"
              : dataStatus === "fallback"
                ? "Bundled static fallback"
                : "Loading data layer…"}
          </span>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{ background: `color-mix(in oklch, ${macroChip.tone} 12%, transparent)`, border: `1px solid color-mix(in oklch, ${macroChip.tone} 30%, transparent)`, color: macroChip.tone }}
          >
            {macroChip.text}
          </span>
          {["Quotes planned", "News planned"].map((t) => (
            <span
              key={t}
              className="rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* Non-blocking fallback warning when the backend data layer is unreachable. */}
      {dataStatus === "fallback" && (
        <div
          role="status"
          className="flex items-start gap-2.5 rounded-xl p-3 text-sm"
          style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
        >
          <span aria-hidden className="mt-0.5 flex-shrink-0">⚠</span>
          <p>Backend globe data unavailable; using bundled static sample data.</p>
        </div>
      )}

      {/* Non-blocking FRED adapter notices (e.g. enabled but no API key). */}
      {warnings.length > 0 && (
        <div
          role="status"
          className="rounded-xl p-3 text-xs"
          style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
        >
          {warnings.map((w) => (
            <p key={w} className="flex items-start gap-2">
              <span aria-hidden className="mt-0.5 flex-shrink-0">ⓘ</span>
              <span>{w}</span>
            </p>
          ))}
        </div>
      )}

      {/* ── Mission-control grid ──────────────────────────────────────────── */}
      <div style={gridStyle}>
        {/* Left rail */}
        <div style={{ gridArea: "rail" }} className="card flex flex-col gap-3 p-3">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search market, currency, index…"
            aria-label="Search markets"
            className="ql-input px-3 py-2 text-sm"
          />
          <div className="ql-segmented w-full" role="group" aria-label="Filter markets by region">
            {(["All", ...MARKET_REGIONS] as const).map((r) => (
              <button
                key={r}
                type="button"
                className={"ql-segmented-option flex-1" + (region === r ? " active" : "")}
                onClick={() => setRegion(r)}
              >
                {r === "Asia-Pacific" ? "APAC" : r}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between">
            <span className="section-title" aria-live="polite">
              Markets ({filtered.length})
            </span>
            {selectedId && (
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="text-[11px] font-medium"
                style={{ color: "var(--accent-text)" }}
              >
                Clear
              </button>
            )}
          </div>

          <div className="flex flex-col gap-1.5 overflow-y-auto pr-0.5" style={{ maxHeight: mode === "narrow" ? undefined : globeHeight - 150 }}>
            {filtered.map((m) => (
              <MarketListItem
                key={m.id}
                market={m}
                active={m.id === selectedId}
                onSelect={() => setSelectedId(m.id)}
              />
            ))}
            {filtered.length === 0 && (
              <div
                role="status"
                className="rounded-lg px-3 py-5 text-center text-xs"
                style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
              >
                No sample markets match this search and region.
              </div>
            )}
          </div>

          <div>
            <p className="section-title mb-1.5">Quick jump</p>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_JUMP.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => {
                    setRegion("All");
                    setQuery("");
                    setSelectedId(q.id);
                  }}
                  className="rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-colors"
                  style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Center globe */}
        <div style={{ gridArea: "globe" }} className="card relative overflow-hidden p-0">
          <div style={{ height: globeHeight }}>
            <DataGlobe
              markets={markets}
              activeIds={activeIds}
              arcs={MARKET_ARCS}
              selectedId={selectedId}
              onSelect={setSelectedId}
              autoRotate={autoRotate}
              resetSignal={resetSignal}
            />
          </div>

          {/* Top overlay controls */}
          <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-3">
            <span
              className="mono rounded-md px-2 py-1 text-[10px] uppercase tracking-wide"
              style={{ background: "rgba(8,11,20,0.6)", border: "1px solid var(--line)", color: "var(--text-mut)" }}
            >
              Static sample data
            </span>
            <div className="pointer-events-auto flex gap-1.5">
              <button
                type="button"
                onClick={() => setAutoRotate((v) => !v)}
                aria-pressed={autoRotate}
                aria-label={autoRotate ? "Pause globe rotation" : "Resume globe rotation"}
                className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
                style={{ background: "rgba(8,11,20,0.6)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
              >
                {autoRotate ? "⏸ Spin" : "▶ Spin"}
              </button>
              <button
                type="button"
                onClick={resetView}
                className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
                style={{ background: "rgba(8,11,20,0.6)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
              >
                Reset
              </button>
            </div>
          </div>

          {/* Legend */}
          <div className="pointer-events-none absolute bottom-0 left-0 flex flex-wrap items-center gap-3 p-3">
            {MARKET_REGIONS.map((r) => (
              <span key={r} className="flex items-center gap-1.5 text-[10px]" style={{ color: "var(--text-mut)" }}>
                <span className="h-2 w-2 rounded-full" style={{ background: REGION_COLORS[r], boxShadow: `0 0 6px ${REGION_COLORS[r]}` }} />
                {r === "Asia-Pacific" ? "APAC" : r}
              </span>
            ))}
            <span className="flex items-center gap-1.5 text-[10px]" style={{ color: "var(--text-mut)" }}>
              <span className="inline-block h-[2px] w-4" style={{ background: "rgba(52,214,224,0.7)" }} />
              Capital-flow arcs (illustrative)
            </span>
          </div>
        </div>

        {/* Right dossier */}
        <div style={{ gridArea: "dossier", ...dossierScroll }}>
          {selected ? (
            <MarketDossier market={selected} onNav={onNav} onClose={() => setSelectedId(null)} />
          ) : (
            <div className="card flex min-h-[300px] flex-col items-center justify-center p-8 text-center">
              <span aria-hidden className="text-4xl">🌐</span>
              <p className="mt-3 text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Select a market
              </p>
              <p className="mt-1 max-w-xs text-xs" style={{ color: "var(--text-mut)" }}>
                Click a marker on the globe or a row in the rail to open its
                financial dossier — all static illustrative sample data.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Bottom region tape ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {rollups.map((r) => (
          <button
            key={r.region}
            type="button"
            onClick={() => {
              setQuery("");
              setRegion(r.region);
            }}
            className="card flex items-center justify-between gap-3 p-3 text-left"
          >
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: REGION_COLORS[r.region], boxShadow: `0 0 6px ${REGION_COLORS[r.region]}` }} />
              <span className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
                {r.region}
              </span>
            </span>
            <span className="text-right">
              <span className="mono block text-sm font-semibold" style={{ color: changeColor(r.avgChange) }}>
                {fmtPct(r.avgChange, 2)}
              </span>
              <span className="mono block text-[10px]" style={{ color: "var(--text-mut)" }}>
                ▲{r.advancers} ▼{r.decliners}
              </span>
            </span>
          </button>
        ))}
        {selected && (
          <div className="card flex items-center justify-between gap-3 p-3 sm:col-span-2 lg:col-span-4">
            <span className="flex items-center gap-2">
              <span aria-hidden className="text-base">{selected.flag}</span>
              <span className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
                {selected.country} · {selected.indices[0]?.name}
              </span>
            </span>
            <span className="mono text-sm font-semibold" style={{ color: changeColor(meanIndexChange(selected)) }}>
              {fmtPct(meanIndexChange(selected), 2)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
