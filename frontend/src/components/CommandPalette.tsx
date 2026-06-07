"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  listCustomStrategyTemplates,
  listSavedBacktests,
  listSavedReports,
  listStrategyGallery,
} from "@/lib/api";
import type {
  CustomStrategyTemplateSummary,
  GalleryTemplate,
  SavedBacktestSummary,
  SavedReportSummary,
} from "@/lib/types";
import {
  buildHaystack,
  searchItems,
  type SearchableItem,
} from "@/lib/search";

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface Command {
  id: string;
  /** Group header the command is listed under (e.g. "Navigation"). */
  group: string;
  title: string;
  /** Extra words matched by the search box but not displayed. */
  keywords?: string;
  /** Optional right-aligned hint (e.g. a shortcut or context label). */
  hint?: string;
  /** Action to run.  Must be safe: navigate / prefill only, never auto-run. */
  run: () => void;
}

export interface CommandPaletteProps {
  /** Static commands (navigation, demos, tools) built by the page. */
  commands: Command[];
  /** Open a saved backtest's detail view. */
  onOpenBacktest: (id: number) => void;
  /** Open a saved report's detail view. */
  onOpenReport: (id: number) => void;
  /** Load a saved (My Templates) custom strategy into the builder. */
  onOpenSavedTemplate: (id: number) => void;
  /** Load a built-in gallery template into the builder. */
  onOpenGalleryTemplate: (id: string) => void;
}

/** Window event other components can dispatch to open the palette. */
export const COMMAND_PALETTE_EVENT = "quantlab:command-palette";

/** Open the command palette from anywhere (e.g. a TopBar button). */
export function openCommandPalette(): void {
  try {
    window.dispatchEvent(new Event(COMMAND_PALETTE_EVENT));
  } catch {
    /* non-browser — ignore */
  }
}

/** True on macOS/iOS, used only to render ⌘ vs Ctrl in hints. */
export function useIsMac(): boolean {
  const [isMac, setIsMac] = useState(false);
  useEffect(() => {
    const s = `${navigator.platform} ${navigator.userAgent}`;
    setIsMac(/mac|iphone|ipad|ipod/i.test(s));
  }, []);
  return isMac;
}

// ---------------------------------------------------------------------------
// Presentation helpers (display only — never affect quant results)
// ---------------------------------------------------------------------------

const STRATEGY_LABELS: Record<string, string> = {
  sma_crossover: "SMA Crossover",
  rsi_mean_reversion: "RSI Mean Reversion",
  bollinger_band: "Bollinger Band",
  momentum: "Momentum",
  volatility_breakout: "Volatility Breakout",
  pairs: "Pairs Trading",
  custom: "Custom Strategy",
};

const SOURCE_LABELS: Record<string, string> = {
  backtest: "Backtest",
  csv_backtest: "CSV Backtest",
  custom_strategy: "Custom Strategy",
  portfolio_backtest: "Portfolio Backtest",
  portfolio_optimization: "Optimization",
  risk_dashboard: "Risk Dashboard",
  stress_test: "Stress Test",
  factor_analysis: "Factor Analysis",
  manual: "Manual",
};

function fmtDate(iso: string): string {
  return typeof iso === "string" ? iso.slice(0, 10) : "";
}

/** Join non-empty bits with a separator (skips null/empty safely). */
function joinBits(bits: Array<string | null | undefined>, sep = " · "): string {
  return bits.filter((b): b is string => Boolean(b && b.trim())).join(sep);
}

function backtestMetrics(b: SavedBacktestSummary): string {
  const parts: string[] = [];
  if (typeof b.sharpe_ratio === "number" && Number.isFinite(b.sharpe_ratio)) {
    parts.push(`Sharpe ${b.sharpe_ratio.toFixed(2)}`);
  }
  if (typeof b.cagr === "number" && Number.isFinite(b.cagr)) {
    parts.push(`CAGR ${(b.cagr * 100).toFixed(1)}%`);
  }
  return parts.join(" · ");
}

// ---------------------------------------------------------------------------
// Resource → searchable item builders
// ---------------------------------------------------------------------------

interface ResourceData {
  backtests: SavedBacktestSummary[];
  reports: SavedReportSummary[];
  templates: CustomStrategyTemplateSummary[];
  gallery: GalleryTemplate[];
}

function buildResourceItems(
  data: ResourceData,
  actions: Pick<
    CommandPaletteProps,
    "onOpenBacktest" | "onOpenReport" | "onOpenSavedTemplate" | "onOpenGalleryTemplate"
  >,
): SearchableItem[] {
  const items: SearchableItem[] = [];

  for (const b of data.backtests) {
    const strat = STRATEGY_LABELS[b.strategy] ?? b.strategy;
    items.push({
      id: `bt-${b.id}`,
      group: "Saved Backtests",
      title: b.name,
      subtitle: joinBits([b.ticker, strat, backtestMetrics(b), fmtDate(b.created_at)]),
      haystack: buildHaystack(b.name, b.ticker, b.strategy, strat, "saved backtest", b.created_at),
      run: () => actions.onOpenBacktest(b.id),
    });
  }

  for (const r of data.reports) {
    const src = SOURCE_LABELS[r.source_type] ?? r.source_type;
    const tickers = Array.isArray(r.tickers) ? r.tickers.join(", ") : "";
    items.push({
      id: `rp-${r.id}`,
      group: "Saved Reports",
      title: r.title,
      subtitle: joinBits([src, tickers, fmtDate(r.created_at)]),
      haystack: buildHaystack(
        r.title,
        tickers,
        r.strategy,
        r.source_type,
        src,
        "saved report",
        r.created_at,
      ),
      run: () => actions.onOpenReport(r.id),
    });
  }

  for (const t of data.templates) {
    const tags = Array.isArray(t.tags) ? t.tags.join(", ") : "";
    items.push({
      id: `tpl-${t.id}`,
      group: "Strategy Templates",
      title: t.name,
      subtitle: joinBits(["Saved template", t.description, tags]),
      hint: "saved",
      haystack: buildHaystack(t.name, t.description, tags, "custom strategy template saved my templates"),
      run: () => actions.onOpenSavedTemplate(t.id),
    });
  }

  for (const g of data.gallery) {
    const tags = Array.isArray(g.tags) ? g.tags.join(", ") : "";
    items.push({
      id: `gal-${g.id}`,
      group: "Strategy Templates",
      title: g.name,
      subtitle: joinBits(["Built-in gallery", g.category, g.description]),
      hint: "gallery",
      haystack: buildHaystack(
        g.name,
        g.description,
        tags,
        g.category,
        g.difficulty,
        "strategy template gallery built-in",
      ),
      run: () => actions.onOpenGalleryTemplate(g.id),
    });
  }

  return items;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CommandPalette({
  commands,
  onOpenBacktest,
  onOpenReport,
  onOpenSavedTemplate,
  onOpenGalleryTemplate,
}: CommandPaletteProps) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const isMac = useIsMac();

  // Saved-resource cache (fetched once, the first time the palette opens).
  const [data, setData] = useState<ResourceData | null>(null);
  const [resLoading, setResLoading] = useState(false);
  const [resOffline, setResOffline] = useState(false);
  // Mirror of `data` so the fetch effect can read it without depending on it
  // (depending on `data` + calling setData would loop).
  const dataRef = useRef<ResourceData | null>(null);
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  useEffect(() => setMounted(true), []);

  // Global open shortcut (Ctrl/Cmd+K) + programmatic open event.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); // some browsers focus the address bar on Ctrl+K
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    function onOpen() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener(COMMAND_PALETTE_EVENT, onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(COMMAND_PALETTE_EVENT, onOpen);
    };
  }, []);

  // On open: clear the query, reset selection, focus the input.
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open]);

  // Fetch saved resources each time the palette opens so newly-saved items
  // appear, while keeping any cached data visible during the (silent) refresh.
  // Each list is settled independently, so one failing endpoint never breaks
  // the others or crashes the palette.  A *total* failure (backend offline)
  // omits saved resources entirely — we never show stale rows — and surfaces
  // the "unavailable" note; commands and demos keep working.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setResLoading(dataRef.current === null); // full "loading" only when nothing cached
    Promise.allSettled([
      listSavedBacktests(),
      listSavedReports(),
      listCustomStrategyTemplates(),
      listStrategyGallery(),
    ]).then((settled) => {
      if (cancelled) return;
      const [bt, rp, tpl, gal] = settled;
      const allFailed = settled.every((s) => s.status === "rejected");
      // Total failure → drop any cached resources so nothing stale is shown.
      setData(
        allFailed
          ? null
          : {
              backtests: bt.status === "fulfilled" ? bt.value : [],
              reports: rp.status === "fulfilled" ? rp.value : [],
              templates: tpl.status === "fulfilled" ? tpl.value : [],
              gallery: gal.status === "fulfilled" ? gal.value : [],
            },
      );
      setResOffline(allFailed);
      setResLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const commandItems: SearchableItem[] = useMemo(
    () =>
      commands.map((c) => ({
        id: c.id,
        group: c.group,
        title: c.title,
        hint: c.hint,
        haystack: buildHaystack(c.title, c.group, c.keywords),
        run: c.run,
      })),
    [commands],
  );

  const resourceItems: SearchableItem[] = useMemo(
    () =>
      data
        ? buildResourceItems(data, {
            onOpenBacktest,
            onOpenReport,
            onOpenSavedTemplate,
            onOpenGalleryTemplate,
          })
        : [],
    [data, onOpenBacktest, onOpenReport, onOpenSavedTemplate, onOpenGalleryTemplate],
  );

  // Commands first (already grouped), then saved-resource groups — contiguous
  // so category headers render cleanly.
  const allItems = useMemo(
    () => [...commandItems, ...resourceItems],
    [commandItems, resourceItems],
  );

  const filtered = useMemo(
    () => searchItems(allItems, query),
    [allItems, query],
  );

  // Keep the selection inside the (possibly shrunken) filtered list.
  useEffect(() => {
    setActive((i) =>
      filtered.length === 0 ? 0 : Math.min(i, filtered.length - 1),
    );
  }, [filtered.length]);

  // Scroll the active row into view as the selection moves.
  useEffect(() => {
    if (!open) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-idx="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function runAt(i: number) {
    const item = filtered[i];
    if (!item) return;
    setOpen(false); // close first so the workspace change is visible immediately
    item.run();
  }

  function onInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "Escape":
        e.preventDefault();
        setOpen(false);
        break;
      case "ArrowDown":
        e.preventDefault();
        setActive((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((i) => Math.max(i - 1, 0));
        break;
      case "Enter":
        e.preventDefault();
        runAt(active);
        break;
    }
  }

  if (!mounted || !open) return null;

  const node = (
    <div
      className="fixed inset-0 z-[130] flex items-start justify-center overflow-y-auto p-4 sm:p-6"
      style={{ background: "rgba(2,4,10,0.66)", backdropFilter: "blur(3px)" }}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={() => setOpen(false)}
    >
      <div
        className="card mt-[8vh] w-full max-w-xl overflow-hidden p-0"
        style={{ boxShadow: "var(--sh-md), var(--panel-glow)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div
          className="flex items-center gap-2.5 px-4 py-3"
          style={{ borderBottom: "1px solid var(--line)" }}
        >
          <svg
            width={16}
            height={16}
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--accent)"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onInputKeyDown}
            placeholder="Search commands, backtests, reports, templates…"
            spellCheck={false}
            autoComplete="off"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--text-hi)" }}
          />
          <kbd
            className="mono rounded px-1.5 py-0.5 text-[10px]"
            style={{
              background: "var(--glass)",
              border: "1px solid var(--line)",
              color: "var(--text-mut)",
            }}
          >
            esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[52vh] overflow-y-auto px-1.5 py-1.5" ref={listRef}>
          {filtered.length === 0 ? (
            <div className="px-4 py-10 text-center">
              <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                No results found{query ? ` for “${query}”` : ""}
              </p>
              <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
                Try searching for a strategy, report, ticker, or tool.
              </p>
            </div>
          ) : (
            filtered.map((item, i) => {
              const showHeader =
                i === 0 || filtered[i - 1].group !== item.group;
              const selected = i === active;
              return (
                <div key={item.id}>
                  {showHeader && (
                    <div
                      className="uplabel px-2.5 pb-1 pt-2"
                      style={{ color: "var(--text-mut)" }}
                    >
                      {item.group}
                    </div>
                  )}
                  <button
                    type="button"
                    data-idx={i}
                    onMouseMove={() => setActive(i)}
                    onClick={() => runAt(i)}
                    className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left"
                    style={
                      selected
                        ? {
                            background: "var(--accent-soft)",
                            border: "1px solid var(--accent-line)",
                          }
                        : { border: "1px solid transparent" }
                    }
                  >
                    <span className="min-w-0 flex-1">
                      <span
                        className="block truncate text-sm"
                        style={{ color: "var(--text-hi)" }}
                      >
                        {item.title}
                      </span>
                      {item.subtitle && (
                        <span className="block truncate text-[11.5px] text-slate-400">
                          {item.subtitle}
                        </span>
                      )}
                    </span>
                    {item.hint && (
                      <span className="mono flex-shrink-0 text-[11px] text-slate-500">
                        {item.hint}
                      </span>
                    )}
                  </button>
                </div>
              );
            })
          )}

          {/* Saved-resource status note (non-selectable). */}
          {resLoading && (
            <div className="px-3 py-2 text-[11.5px] text-slate-500">
              Loading saved resources…
            </div>
          )}
          {!resLoading && resOffline && (
            <div className="px-1">
              <div className="uplabel px-2.5 pb-1 pt-2" style={{ color: "var(--text-mut)" }}>
                Saved resources
              </div>
              <div
                className="rounded-lg px-2.5 py-2 text-[11.5px]"
                style={{
                  border: "1px solid rgba(245,158,11,0.3)",
                  background: "rgba(245,158,11,0.06)",
                  color: "#fbbf24",
                }}
              >
                Saved resources unavailable while backend is offline. Navigation
                and demo commands still work.
              </div>
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div
          className="flex items-center gap-3 px-4 py-2 text-[11px]"
          style={{ borderTop: "1px solid var(--line)", color: "var(--text-mut)" }}
        >
          <span className="mono">↑↓</span> navigate
          <span className="mono">↵</span> run
          <span className="mono">esc</span> close
          <span className="ml-auto">{isMac ? "⌘K" : "Ctrl K"}</span>
        </div>
      </div>
    </div>
  );

  return createPortal(node, document.body);
}
