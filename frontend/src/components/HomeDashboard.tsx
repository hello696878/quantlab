"use client";

import { useEffect, useState } from "react";
import type { View } from "@/components/AppShell";
import {
  checkHealth,
  classifyApiError,
  listSavedBacktests,
  listSavedReports,
} from "@/lib/api";
import type { SavedBacktestSummary, SavedReportSummary } from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";
import { REGION_COLORS, regionRollup } from "@/lib/globe/markets";
import { DEMO_PRESETS, type DemoPresetId } from "@/lib/demoPresets";
import { SkeletonCard } from "@/components/ui/LoadingSkeleton";
import OfflineState from "@/components/ui/OfflineState";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import {
  EMPTY_CHECKLIST,
  ONBOARDING_EVENT,
  getChecklist,
  isOnboardingHidden,
  setOnboardingHidden,
  type ChecklistState,
  type ChecklistStep,
} from "@/lib/onboarding";
import { LIVE_MODELS, findModelBySlug } from "@/lib/modelRegistry";
import { LIVE_PAPERS, findPaperBySlug } from "@/lib/paperRegistry";
import { LIVE_DISASTERS, findDisasterBySlug } from "@/lib/disasterRegistry";

// ---------------------------------------------------------------------------
// Labels
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
  return iso.replace("T", " ").slice(0, 16);
}

function tickerLabel(tickers: unknown): string {
  return Array.isArray(tickers) && tickers.length > 0
    ? tickers.join(", ")
    : "";
}

function metricColor(v: number | null | undefined, positiveGood = true): string {
  if (v == null) return "text-slate-400";
  if (v > 0) return positiveGood ? "text-green-700" : "text-red-600";
  if (v < 0) return positiveGood ? "text-red-600" : "text-green-700";
  return "text-slate-500";
}

/** Trust Layer explainer cards — static, render fine with the backend offline. */
const TRUST_LAYER_CARDS: { title: string; description: string; view: View }[] = [
  {
    title: "Data Quality",
    description: "Shows provider, actual date range, missing values, and warnings.",
    view: "backtest",
  },
  {
    title: "Benchmark Comparison",
    description: "Compares the strategy against buy-and-hold or a custom benchmark.",
    view: "backtest",
  },
  {
    title: "Config Hash",
    description: "Creates a deterministic fingerprint of backtest assumptions.",
    view: "backtest",
  },
  {
    title: "Robustness Lab",
    description: "Resamples returns to estimate outcome uncertainty.",
    view: "backtest",
  },
  {
    title: "Stability Lab",
    description: "Checks whether nearby parameters produce similar results.",
    view: "backtest",
  },
  {
    title: "Report Export",
    description: "Exports structured research reports with assumptions and caveats.",
    view: "reports",
  },
];

/** Blueprint v3 direction chips — only "Built" items exist today. */
const ROADMAP_STATUS: { label: string; status: "Built" | "Planned" | "Future" }[] = [
  { label: "Backtest Studio", status: "Built" },
  { label: "Trust Layer", status: "Built" },
  { label: "Strategy Library", status: "Built" },
  { label: "Paper Replications", status: "Built" },
  { label: "Quant Disasters", status: "Built" },
  { label: "Global Markets Globe", status: "Built" },
  { label: "Options & Volatility Lab", status: "Built" },
  { label: "Event-Driven / Arbitrage Module", status: "Planned" },
  { label: "Portfolio Ensemble Builder", status: "Planned" },
  { label: "Microstructure & Execution Lab", status: "Built" },
  { label: "AI Explainer Copilot", status: "Future" },
  { label: "3D Visualization Engine", status: "Future" },
  { label: "Platform / Launch Layer", status: "Future" },
];

/** Quick-start checklist rows. Order = suggested first-run path. */
const CHECKLIST_ITEMS: { step: ChecklistStep; label: string }[] = [
  { step: "ran_backtest", label: "Run your first backtest" },
  { step: "saved_backtest", label: "Save a backtest" },
  { step: "exported_report", label: "Export a report" },
  { step: "viewed_risk", label: "Try the portfolio risk dashboard" },
  { step: "built_strategy", label: "Build a custom strategy" },
];

/** Featured country dossiers surfaced as Globe permalink shortcuts. */
const GLOBE_QUICK_LINKS: { id: string; label: string }[] = [
  { id: "us", label: "US" },
  { id: "tw", label: "Taiwan" },
  { id: "jp", label: "Japan" },
  { id: "de", label: "Germany" },
  { id: "in", label: "India" },
];

// ---------------------------------------------------------------------------
// Small building blocks
// ---------------------------------------------------------------------------

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="rounded-full px-2.5 py-0.5 text-[11px] font-medium"
      style={{
        background: "var(--accent-softer)",
        border: "1px solid var(--accent-line)",
        color: "var(--accent-text)",
      }}
    >
      {children}
    </span>
  );
}

interface QuickAction {
  label: string;
  description: string;
  icon: string; // svg path
  onClick: () => void;
}

function QuickActionCard({ action }: { action: QuickAction }) {
  return (
    <button
      type="button"
      onClick={action.onClick}
      className="card group flex items-start gap-3 p-4 text-left"
    >
      <span
        className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg"
        style={{
          background: "var(--accent-soft)",
          border: "1px solid var(--accent-line)",
          color: "var(--accent)",
        }}
      >
        <svg
          width={18}
          height={18}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d={action.icon} />
        </svg>
      </span>
      <span className="min-w-0">
        <span
          className="block text-sm font-semibold transition-colors"
          style={{ color: "var(--text-hi)" }}
        >
          {action.label}
        </span>
        <span className="mt-0.5 block text-xs text-slate-400">
          {action.description}
        </span>
      </span>
    </button>
  );
}

function StatusTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "off" | "neutral";
}) {
  const valueStyle =
    tone === "ok"
      ? { color: "var(--pos)" }
      : tone === "off"
        ? { color: "var(--neg)" }
        : { color: "var(--text-hi)" };
  return (
    <div className="card p-4">
      <p className="uplabel">{label}</p>
      <p className="mono mt-1 text-lg font-bold" style={valueStyle}>
        {value}
      </p>
    </div>
  );
}

function FeatureCard({
  title,
  items,
  onClick,
}: {
  title: string;
  items: string[];
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="card flex flex-col gap-2 p-4 text-left"
    >
      <span className="flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full"
          style={{
            background: "var(--accent)",
            boxShadow: "0 0 8px rgba(var(--accent-rgb), 0.8)",
          }}
        />
        <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
          {title}
        </span>
      </span>
      <span className="flex flex-wrap gap-1.5">
        {items.map((it) => (
          <span
            key={it}
            className="rounded-md px-1.5 py-0.5 text-[10.5px] text-slate-400"
            style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
          >
            {it}
          </span>
        ))}
      </span>
    </button>
  );
}

/** Filled accent button used for the onboarding primary actions. */
function PrimaryButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors"
      style={{
        background: "var(--accent-soft)",
        border: "1px solid var(--accent-line)",
        color: "var(--accent-text)",
      }}
    >
      {label}
    </button>
  );
}

/** A guided-demo shortcut chip. Prefills a workspace; never auto-runs. */
function DemoChip({
  label,
  detail,
  onClick,
}: {
  label: string;
  detail: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={`${label} — ${detail}`}
      className="group flex flex-col items-start rounded-lg px-3 py-2 text-left transition-colors"
      style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
    >
      <span className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
        {label}
      </span>
      <span className="mt-0.5 text-[11px] text-slate-400">{detail}</span>
    </button>
  );
}

function ChecklistRow({ done, label }: { done: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2.5 py-1.5 text-sm">
      <span
        aria-hidden
        className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
        style={
          done
            ? { background: "var(--pos)", color: "#04140d" }
            : {
                background: "transparent",
                border: "1.5px solid var(--line-strong)",
                color: "transparent",
              }
        }
      >
        ✓
      </span>
      <span
        className={done ? "line-through" : ""}
        style={{ color: done ? "var(--text-lo, #8b93a7)" : "var(--text-hi)" }}
      >
        {label}
      </span>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface HomeDashboardProps {
  onNav: (view: View) => void;
  onOpenBacktest: (id: number) => void;
  onOpenReport: (id: number) => void;
  /** Load a guided-demo preset: navigates + prefills, never auto-runs. */
  onDemo: (id: DemoPresetId) => void;
  /** Deep-open content pages by slug (featured cards reference registries). */
  onOpenLibraryPage?: (slug: string | null) => void;
  onOpenPaperPage?: (slug: string | null) => void;
  onOpenDisasterPage?: (slug: string | null) => void;
  /** Open the Globe, optionally deep-selecting a country dossier (permalink). */
  onOpenGlobe?: (marketId: string | null) => void;
  /** Start a guided Globe tour by id (Phase 20.7). */
  onStartTour?: (tourId: string) => void;
}

export default function HomeDashboard({
  onNav,
  onOpenBacktest,
  onOpenReport,
  onDemo,
  onOpenLibraryPage,
  onOpenPaperPage,
  onOpenDisasterPage,
  onOpenGlobe,
  onStartTour,
}: HomeDashboardProps) {
  /** Open a country dossier permalink (falls back to the globe index). */
  const openMarket = (id: string) =>
    onOpenGlobe ? onOpenGlobe(id) : onNav("globe");
  /** Start a guided Globe tour (falls back to the globe index). */
  const startTour = (id: string) =>
    onStartTour ? onStartTour(id) : onNav("globe");
  const [backtests, setBacktests] = useState<SavedBacktestSummary[]>([]);
  const [reports, setReports] = useState<SavedReportSummary[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [backtestsError, setBacktestsError] = useState<unknown>(null);
  const [reportsError, setReportsError] = useState<unknown>(null);
  const [retryTick, setRetryTick] = useState(0);

  // Onboarding state lives in localStorage (client-only).  Start from
  // deterministic values so SSR and first client render match, then hydrate
  // from localStorage in an effect.  `hidden === null` means "not yet known"
  // (render nothing) so the welcome card never flashes before we know.
  const [hidden, setHidden] = useState<boolean | null>(null);
  const [checklist, setChecklist] = useState<ChecklistState>(EMPTY_CHECKLIST);

  useEffect(() => {
    const sync = () => {
      setHidden(isOnboardingHidden());
      setChecklist(getChecklist());
    };
    sync();
    window.addEventListener(ONBOARDING_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(ONBOARDING_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setBacktestsError(null);
    setReportsError(null);
    checkHealth().then((ok) => {
      if (!cancelled) setOnline(ok);
    });
    Promise.allSettled([listSavedBacktests(), listSavedReports()]).then(
      ([b, r]) => {
        if (cancelled) return;
        if (b.status === "fulfilled") {
          setBacktests(b.value);
          setBacktestsError(null);
        } else {
          setBacktestsError(b.reason);
        }
        if (r.status === "fulfilled") {
          setReports(r.value);
          setReportsError(null);
        } else {
          setReportsError(r.reason);
        }
        setLoaded(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [retryTick]);

  // ISO timestamps sort lexicographically == chronologically; newest first.
  const recentBacktests = [...backtests]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 5);
  const recentReports = [...reports]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 5);
  const backtestsErrorInfo = backtestsError
    ? classifyApiError(backtestsError)
    : null;
  const reportsErrorInfo = reportsError ? classifyApiError(reportsError) : null;

  const doneCount = CHECKLIST_ITEMS.filter((i) => checklist[i.step]).length;

  // Featured content — names/descriptions come from the registries (single
  // source of truth, no metadata drift); only existing destinations are linked.
  const featuredSma = findModelBySlug("sma-crossover");
  const featuredPaper = findPaperBySlug("jegadeesh-titman-1993-momentum");
  const featuredDisaster = findDisasterBySlug("ltcm-1998");
  const featuredItems: {
    title: string;
    type: "Strategy" | "Paper" | "Disaster" | "Workflow";
    description: string;
    cta: string;
    onClick: () => void;
  }[] = [
    ...(featuredSma && onOpenLibraryPage
      ? [{
          title: featuredSma.name,
          type: "Strategy" as const,
          description: featuredSma.description,
          cta: "Open strategy page",
          onClick: () => onOpenLibraryPage(featuredSma.slug),
        }]
      : []),
    ...(featuredPaper && onOpenPaperPage
      ? [{
          title: `${featuredPaper.authors} (${featuredPaper.year})`,
          type: "Paper" as const,
          description: featuredPaper.summary,
          cta: "Open replication page",
          onClick: () => onOpenPaperPage(featuredPaper.slug),
        }]
      : []),
    ...(featuredDisaster && onOpenDisasterPage
      ? [{
          title: `${featuredDisaster.title} (${featuredDisaster.year})`,
          type: "Disaster" as const,
          description: featuredDisaster.shortDescription,
          cta: "Open case study",
          onClick: () => onOpenDisasterPage(featuredDisaster.slug),
        }]
      : []),
    {
      title: "Robustness Lab workflow",
      type: "Workflow",
      description:
        "Bootstrap-resample a backtest's returns to see how fragile the result is.",
      cta: "Run a backtest with robustness",
      onClick: () => onNav("backtest"),
    },
    {
      title: "Stability Lab workflow",
      type: "Workflow",
      description:
        "Sweep nearby SMA parameters to check for stable regions vs isolated spikes.",
      cta: "Run a backtest with stability",
      onClick: () => onNav("backtest"),
    },
  ];

  const quickActions: QuickAction[] = [
    {
      label: "Run Single-Asset Backtest",
      description: "SMA, RSI, Bollinger, Momentum, Breakout, or Pairs",
      icon: "M4 4v16h16M8 16l3-4 3 2 4-6",
      onClick: () => onNav("backtest"),
    },
    {
      label: "Compare Strategies",
      description: "All five strategies under shared simulation settings",
      icon: "M4 20V10m5 10V4m5 16v-7m5 7V8",
      onClick: () => onNav("comparison"),
    },
    {
      label: "Upload CSV Data",
      description: "Backtest your own price history",
      icon: "M12 16V4m0 0L7 9m5-5 5 5M5 20h14",
      onClick: () => onNav("csv"),
    },
    {
      label: "Build Custom Strategy",
      description: "Compose indicator rules — no code",
      icon: "M4 7h7v7H4V7Zm9 3h7v7h-7v-7ZM7 4h10M16 14v6",
      onClick: () => onNav("builder"),
    },
    {
      label: "Open Portfolio Lab",
      description: "Backtest, optimize, risk & factor analysis",
      icon: "M3 3v18h18M7 14l3-3 3 2 5-6",
      onClick: () => onNav("portfolio"),
    },
    {
      label: "View Saved Backtests",
      description: "Reopen locally persisted results",
      icon: "M5 3h11l3 3v15H5V3Zm3 0v6h7V3M8 14h8M8 17h8",
      onClick: () => onNav("saved"),
    },
    {
      label: "View Saved Reports",
      description: "Open the local report gallery",
      icon: "M7 3h7l4 4v14H7V3Zm7 0v4h4M10 12h5M10 16h5M10 8h2",
      onClick: () => onNav("reports"),
    },
    {
      label: "Open Settings",
      description: "Theme, default inputs, and report preferences",
      icon: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm8.4 3a8.4 8.4 0 0 0-.12-1.4l2-1.55-2-3.46-2.36.95a8.4 8.4 0 0 0-2.42-1.4L14.8 1.6h-4l-.3 2.94a8.4 8.4 0 0 0-2.42 1.4l-2.36-.95-2 3.46 2 1.55A8.4 8.4 0 0 0 3.6 12c0 .47.04.94.12 1.4l-2 1.55 2 3.46 2.36-.95a8.4 8.4 0 0 0 2.42 1.4l.3 2.94h4l.3-2.94a8.4 8.4 0 0 0 2.42-1.4l2.36.95 2-3.46-2-1.55c.08-.46.12-.93.12-1.4Z",
      onClick: () => onNav("settings"),
    },
    {
      label: "Export Research Report",
      description: "Run an analysis, then export Markdown / PDF",
      icon: "M12 16V4m0 0l-4 4m4-4 4 4M6 20h12",
      onClick: () => onNav("backtest"),
    },
  ];

  return (
    <div className="space-y-7">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-6 sm:p-7">
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            style={{
              width: 4,
              alignSelf: "stretch",
              minHeight: 44,
              borderRadius: 3,
              background: "var(--accent)",
              boxShadow: "0 0 14px -1px rgba(var(--accent-rgb), 0.7)",
              flexShrink: 0,
            }}
          />
          <div>
            <h1
              className="text-2xl font-extrabold tracking-[-0.01em] sm:text-3xl"
              style={{ color: "var(--text-hi)" }}
            >
              QuantLab Research Terminal
            </h1>
            <p className="mt-1.5 max-w-2xl text-sm text-slate-400">
              Local-first quant research platform for backtesting,
              benchmarking, robustness, and strategy education — research only,
              not investment advice.
            </p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge>Local-first</Badge>
          <Badge>FastAPI backend</Badge>
          <Badge>Next.js frontend</Badge>
          <Badge>SQLite persistence</Badge>
          <Badge>Research-only</Badge>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <PrimaryButton
            label="Explore Global Markets"
            onClick={() => onNav("globe")}
          />
          <PrimaryButton label="Run Backtest" onClick={() => onNav("backtest")} />
          <PrimaryButton
            label="Open Strategy Library"
            onClick={() => onNav("library")}
          />
          <PrimaryButton
            label="Open Paper Replications"
            onClick={() => onNav("replications")}
          />
          <PrimaryButton
            label="Open Quant Disasters"
            onClick={() => onNav("disasters")}
          />
        </div>
      </div>

      {/* ── Global Markets strip ─────────────────────────────────────────── */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <p className="section-title">Global Markets</p>
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
          >
            Static sample
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {regionRollup().map((r) => (
            <button
              key={r.region}
              type="button"
              onClick={() => onNav("globe")}
              className="card flex items-center justify-between gap-3 p-3 text-left"
            >
              <span className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: REGION_COLORS[r.region], boxShadow: `0 0 6px ${REGION_COLORS[r.region]}` }}
                />
                <span className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>
                  {r.region}
                </span>
              </span>
              <span
                className="mono text-sm font-semibold"
                style={{ color: r.avgChange > 0 ? "var(--pos)" : r.avgChange < 0 ? "var(--neg)" : "var(--text-mut)" }}
              >
                {fmtPct(r.avgChange, 2)}
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* ── Onboarding / Guided demo ─────────────────────────────────────── */}
      {hidden === true && (
        <button
          type="button"
          onClick={() => setOnboardingHidden(false)}
          className="text-xs font-medium text-blue-600 hover:underline"
        >
          ↘ Show welcome guide
        </button>
      )}

      {hidden === false && (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Welcome + guided demos */}
          <div className="card panel-glow p-5 sm:p-6 lg:col-span-2">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold" style={{ color: "var(--text-hi)" }}>
                  Welcome to QuantLab
                </h2>
                <p className="mt-0.5 text-sm text-slate-400">
                  Start with a guided workflow or jump directly into a research
                  tool.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOnboardingHidden(true)}
                className="flex-shrink-0 rounded-md px-2 py-1 text-xs font-medium text-slate-400 transition-colors hover:text-slate-900"
                style={{ border: "1px solid var(--line)" }}
              >
                Hide onboarding
              </button>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <PrimaryButton
                label="Run Demo Backtest"
                onClick={() => onDemo("sma_backtest")}
              />
              <PrimaryButton
                label="Try Portfolio Lab"
                onClick={() => onDemo("portfolio_risk")}
              />
              <PrimaryButton
                label="Build a Custom Strategy"
                onClick={() => onDemo("strategy_builder")}
              />
              <PrimaryButton
                label="Open Saved Reports"
                onClick={() => onNav("reports")}
              />
            </div>

            <div className="my-4 neon-divider" />

            <p className="uplabel mb-2">
              Guided demos · parameters are prefilled, nothing runs until you
              click Run
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {DEMO_PRESETS.map((p) => (
                <DemoChip
                  key={p.id}
                  label={p.label}
                  detail={p.detail}
                  onClick={() => onDemo(p.id)}
                />
              ))}
            </div>
          </div>

          {/* Quick-start checklist */}
          <div className="card p-5 sm:p-6">
            <div className="flex items-baseline justify-between">
              <h2 className="text-sm font-bold" style={{ color: "var(--text-hi)" }}>
                Quick-start checklist
              </h2>
              <span className="mono text-xs text-slate-400">
                {doneCount}/{CHECKLIST_ITEMS.length}
              </span>
            </div>
            <ul className="mt-2">
              {CHECKLIST_ITEMS.map((i) => (
                <ChecklistRow
                  key={i.step}
                  done={checklist[i.step]}
                  label={i.label}
                />
              ))}
            </ul>
            <p className="mt-3 text-[11px] text-slate-500">
              Progress is tracked locally as you use each tool — no account
              needed.
            </p>
          </div>
        </section>
      )}

      {/* ── Quick Actions ────────────────────────────────────────────────── */}
      <section>
        <p className="section-title mb-3">Quick Actions</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {quickActions.map((a) => (
            <QuickActionCard key={a.label} action={a} />
          ))}
        </div>
      </section>

      {/* ── System Status ────────────────────────────────────────────────── */}
      <section>
        <p className="section-title mb-3">System Status</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatusTile
            label="API"
            value={online === null ? "…" : online ? "ONLINE" : "OFFLINE"}
            tone={online === null ? "neutral" : online ? "ok" : "off"}
          />
          <StatusTile label="Mode" value="LOCAL" tone="neutral" />
          <StatusTile
            label="Saved Backtests"
            value={!loaded ? "…" : backtestsErrorInfo ? "—" : String(backtests.length)}
          />
          <StatusTile
            label="Saved Reports"
            value={!loaded ? "…" : reportsErrorInfo ? "—" : String(reports.length)}
          />
        </div>
      </section>

      {/* ── Recent items ─────────────────────────────────────────────────── */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent Saved Backtests */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <p className="section-title">Recent Saved Backtests</p>
            {recentBacktests.length > 0 && (
              <button
                type="button"
                onClick={() => onNav("saved")}
                className="text-xs font-medium text-blue-600 hover:underline"
              >
                View all →
              </button>
            )}
          </div>
          {!loaded ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : backtestsErrorInfo ? (
            backtestsErrorInfo.backendUnavailable ? (
              <OfflineState
                compact
                message="Recent saved backtests require the FastAPI backend (local SQLite)."
                onRetry={() => setRetryTick((k) => k + 1)}
              />
            ) : (
              <ErrorState
                title="Couldn’t load recent backtests"
                message={backtestsErrorInfo.message}
                onRetry={() => setRetryTick((k) => k + 1)}
              />
            )
          ) : recentBacktests.length === 0 ? (
            <EmptyState
              compact
              title="No saved backtests yet"
              description="Run a backtest and save it to build your research history."
              actions={[{ label: "Run Backtest", onClick: () => onNav("backtest") }]}
            />
          ) : (
            <div className="card overflow-hidden">
              {recentBacktests.map((b, i) => (
                <button
                  key={b.id}
                  type="button"
                  onClick={() => onOpenBacktest(b.id)}
                  style={{ borderTop: i ? "1px solid var(--line)" : undefined }}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--glass)]"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium" style={{ color: "var(--text-hi)" }}>
                      {b.name}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-400">
                      <span className="mono">{b.ticker}</span> ·{" "}
                      {STRATEGY_LABELS[b.strategy] ?? b.strategy} · {fmtDate(b.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-shrink-0 gap-3 text-right text-xs mono">
                    <span>
                      <span className="block text-[10px] uppercase text-slate-500">CAGR</span>
                      <span className={metricColor(b.cagr)}>
                        {b.cagr == null ? "—" : fmtPct(b.cagr, 1)}
                      </span>
                    </span>
                    <span>
                      <span className="block text-[10px] uppercase text-slate-500">Sharpe</span>
                      <span className={metricColor(b.sharpe_ratio)}>
                        {b.sharpe_ratio == null ? "—" : fmtRatio(b.sharpe_ratio, 2)}
                      </span>
                    </span>
                    <span>
                      <span className="block text-[10px] uppercase text-slate-500">Max DD</span>
                      <span className={metricColor(b.max_drawdown, false)}>
                        {b.max_drawdown == null ? "—" : fmtPct(b.max_drawdown, 1)}
                      </span>
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Recent Saved Reports */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <p className="section-title">Recent Saved Reports</p>
            {recentReports.length > 0 && (
              <button
                type="button"
                onClick={() => onNav("reports")}
                className="text-xs font-medium text-blue-600 hover:underline"
              >
                View all →
              </button>
            )}
          </div>
          {!loaded ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : reportsErrorInfo ? (
            reportsErrorInfo.backendUnavailable ? (
              <OfflineState
                compact
                message="Recent saved reports require the FastAPI backend (local SQLite)."
                onRetry={() => setRetryTick((k) => k + 1)}
              />
            ) : (
              <ErrorState
                title="Couldn’t load recent reports"
                message={reportsErrorInfo.message}
                onRetry={() => setRetryTick((k) => k + 1)}
              />
            )
          ) : recentReports.length === 0 ? (
            <EmptyState
              compact
              title="No saved reports yet"
              description="Export or save a research report to see it here."
              actions={[{ label: "Run a Backtest", onClick: () => onNav("backtest") }]}
            />
          ) : (
            <div className="card overflow-hidden">
              {recentReports.map((r, i) => {
                const tickers = tickerLabel(r.tickers);
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => onOpenReport(r.id)}
                    style={{ borderTop: i ? "1px solid var(--line)" : undefined }}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--glass)]"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium" style={{ color: "var(--text-hi)" }}>
                        {r.title}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-slate-400">
                        {SOURCE_LABELS[r.source_type] ?? r.source_type}
                        {r.strategy ? ` · ${STRATEGY_LABELS[r.strategy] ?? r.strategy}` : ""}
                        {tickers ? ` · ${tickers}` : ""}
                      </p>
                    </div>
                    <span className="flex-shrink-0 text-xs text-slate-500">
                      {fmtDate(r.created_at)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* ── Feature Map ──────────────────────────────────────────────────── */}
      <section>
        <p className="section-title mb-3">Feature Map</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <FeatureCard
            title="Strategy Lab"
            items={["SMA", "RSI", "Bollinger", "Momentum", "Vol Breakout", "Pairs"]}
            onClick={() => onNav("backtest")}
          />
          <FeatureCard
            title="Research Tools"
            items={["Parameter Sweep", "Train/Test", "Walk-Forward", "Comparison"]}
            onClick={() => onNav("sweep")}
          />
          <FeatureCard
            title="Portfolio Lab"
            items={[
              "Backtesting",
              "Optimization",
              "Efficient Frontier",
              "Risk Dashboard",
              "Stress Test",
              "Factor Analysis",
            ]}
            onClick={() => onNav("portfolio")}
          />
          <FeatureCard
            title="Reporting"
            items={["Markdown Export", "PDF Print", "Saved Reports", "Templates"]}
            onClick={() => onNav("reports")}
          />
        </div>
      </section>

      {/* ── Trust Layer ──────────────────────────────────────────────────── */}
      <section>
        <p className="section-title mb-1">Trust Layer</p>
        <p className="mb-3 text-xs text-slate-400">
          Every backtest result carries diagnostics for auditing assumptions —
          research tools, not guarantees.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TRUST_LAYER_CARDS.map((c) => (
            <button
              key={c.title}
              type="button"
              onClick={() => onNav(c.view)}
              className="card flex flex-col gap-1 p-4 text-left"
            >
              <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                {c.title}
              </span>
              <span className="text-xs text-slate-400">{c.description}</span>
            </button>
          ))}
        </div>
      </section>

      {/* ── Content Engine ───────────────────────────────────────────────── */}
      <section>
        <p className="section-title mb-1">Content Engine</p>
        <p className="mb-3 text-xs text-slate-400">
          Learn how strategies work, where the ideas came from, and how they
          fail.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="card flex flex-col gap-1 p-4">
            <span className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Global Markets Globe
              </span>
              <span
                className="flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
              >
                Static API + optional adapters
              </span>
            </span>
            <span className="text-xs text-slate-400">
              Explore a 3D map backed by a typed country-dossier data layer.
              Static data remains the default; optional macro and delayed quote
              adapters can enrich supported fields. News sentiment is represented
              by sample headlines, with live news integration planned. Country
              dossiers are shareable permalinks (e.g. ?view=globe&amp;market=us).
            </span>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              {GLOBE_QUICK_LINKS.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => openMarket(q.id)}
                  aria-label={`Open the ${q.label} market dossier`}
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors"
                  style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
                >
                  {q.label}
                </button>
              ))}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={() => startTour("global")}
                aria-label="Start the guided global markets tour"
                className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors"
                style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
              >
                ▶ Guided Global Tour
              </button>
              <button
                type="button"
                onClick={() => startTour("asia")}
                aria-label="Start the Asia markets tour"
                className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors"
                style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
              >
                ▶ Asia Tour
              </button>
            </div>
            <button
              type="button"
              onClick={() => onNav("globe")}
              className="mt-1 self-start text-xs font-medium text-blue-600"
            >
              Open Globe →
            </button>
          </div>
          <button
            type="button"
            onClick={() => onNav("library")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              Strategy Library
            </span>
            <span className="text-xs text-slate-400">
              {LIVE_MODELS.length} implemented strategy models with hypothesis, signal
              logic, failure modes, and trust checklist.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Browse Strategies →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("replications")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              Paper Replications
            </span>
            <span className="text-xs text-slate-400">
              Classic quant papers with {LIVE_PAPERS.length} simplified inspired
              demos — honest about what full replication needs.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Study Papers →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("disasters")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              Quant Disasters
            </span>
            <span className="text-xs text-slate-400">
              {LIVE_DISASTERS.length} risk-education case studies on how quant
              strategies and risk systems fail.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Study Disasters →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("options")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              Options Lab
            </span>
            <span className="text-xs text-slate-400">
              Black–Scholes, Greeks, implied volatility, payoff diagrams,
              binomial-tree / American-exercise pricing, Monte Carlo (Asian &amp;
              barrier), an implied-volatility surface with SVI fit, and Heston
              stochastic volatility — an educational calculator.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Options Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("events")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              Event Lab
            </span>
            <span className="text-xs text-slate-400">
              Study abnormal returns around events (CAR / CAAR) and explore
              simplified merger-arbitrage economics — research diagnostic, no
              live filings.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Event Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("rates")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              Yield Curve Lab
            </span>
            <span className="text-xs text-slate-400">
              Explore yield curves, discount factors, forward rates, curve shocks,
              bond duration / convexity, and short-rate models like Vasicek and
              CIR — synthetic curves, no live rates feed.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Yield Curve Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("fx")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              FX Lab
            </span>
            <span className="text-xs text-slate-400">
              Explore spot/forward relationships, interest rate parity, FX carry, PPP
              deviation, currency exposure, and FX option pricing — no live FX rates.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open FX Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("credit")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              Credit Risk Lab
            </span>
            <span className="text-xs text-slate-400">
              Explore Merton structural credit, hazard rates, CDS spread approximation,
              survival curves, and risky bond pricing — no live CDS data.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Credit Risk Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("risklab")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Portfolio Risk Lab
              </span>
              <span
                className="flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
              >
                Portfolio analytics + robustness
              </span>
            </span>
            <span className="text-xs text-slate-400">
              Analyze sample portfolio risk, factor exposure, stress scenarios,
              optimization, Black-Litterman views, Monte Carlo paths, and robustness
              diagnostics using deterministic illustrative data — not investment advice.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Portfolio Risk Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("realestate")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Real Estate Lab
              </span>
              <span
                className="flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
              >
                Real estate + MBS analytics
              </span>
            </span>
            <span className="text-xs text-slate-400">
              Analyze deterministic sample property NOI, mortgage debt, DSCR, REIT NAV,
              and mortgage/MBS prepayment cash flows with CPR, PSA, WAL, duration, and
              convexity — not investment advice.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Real Estate Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("futures")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Futures &amp; Commodities Lab
              </span>
              <span
                className="flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
              >
                Futures analytics
              </span>
            </span>
            <span className="text-xs text-slate-400">
              Analyze deterministic sample futures curves, cost-of-carry pricing, convenience
              yield, contango/backwardation, roll yield, calendar spreads, margin, and
              commodity scenario stress — not investment advice.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Futures &amp; Commodities Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("volatility")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Volatility Surface Lab
              </span>
              <span
                className="flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
              >
                Volatility analytics
              </span>
            </span>
            <span className="text-xs text-slate-400">
              Analyze deterministic sample option chains, implied volatility smiles, skew, term
              structure, realized volatility, variance swap fair strikes, vega exposure, and
              volatility scenario stress — not investment advice.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Volatility Surface Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("microstructure")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                Market Microstructure Lab
              </span>
              <span
                className="flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}
              >
                Execution + liquidity analytics
              </span>
            </span>
            <span className="text-xs text-slate-400">
              Analyze deterministic sample order books, VWAP/TWAP, implementation shortfall, TCA
              attribution, order-flow toxicity, VPIN-style liquidity metrics, adverse selection,
              execution schedules, and liquidity stress — not investment or order-routing advice.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Market Microstructure Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("scanner")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              Cross-Sectional Scanner
            </span>
            <span className="text-xs text-slate-400">
              Rank a synthetic universe, form long/short baskets, and backtest portfolio-level
              cross-sectional strategies — synthetic universe, no live market data.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open Scanner Lab →
            </span>
          </button>
          <button
            type="button"
            onClick={() => onNav("finml")}
            className="card flex flex-col gap-1 p-4 text-left"
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
              AFML Methodology Lab
            </span>
            <span className="text-xs text-slate-400">
              Build leakage-aware financial-ML labels and validation with CUSUM sampling, triple
              barriers, uniqueness weights, purged K-fold + embargo, sequential bootstrap, and
              fractional differentiation — synthetic data, not a model.
            </span>
            <span className="mt-1 text-xs font-medium text-blue-600">
              Open AFML Lab →
            </span>
          </button>
        </div>
      </section>

      {/* ── Featured ─────────────────────────────────────────────────────── */}
      <section>
        <p className="section-title mb-3">Featured</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {featuredItems.map((f) => (
            <button
              key={f.title}
              type="button"
              onClick={f.onClick}
              className="card flex flex-col gap-1.5 p-4 text-left"
            >
              <span className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>
                  {f.title}
                </span>
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                  style={{
                    background: "var(--accent-softer)",
                    border: "1px solid var(--accent-line)",
                    color: "var(--accent-text)",
                  }}
                >
                  {f.type}
                </span>
              </span>
              <span className="text-xs text-slate-400">{f.description}</span>
              <span className="mt-0.5 text-xs font-medium text-blue-600">{f.cta} →</span>
            </button>
          ))}
        </div>
      </section>

      {/* ── Platform Direction (Blueprint v3) ────────────────────────────── */}
      <section>
        <p className="section-title mb-1">Platform Direction</p>
        <p className="mb-3 text-xs text-slate-400">
          Development follows Master Blueprint v3 — only items marked Built
          exist today; nothing here is a feature promise.
        </p>
        <div className="card p-4">
          <div className="flex flex-wrap gap-1.5">
            {ROADMAP_STATUS.map((r) => (
              <span
                key={r.label}
                className={
                  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium " +
                  (r.status === "Built"
                    ? "bg-emerald-100 text-emerald-700"
                    : r.status === "Planned"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-slate-100 text-slate-500")
                }
              >
                <span className="font-semibold uppercase text-[9px] tracking-wide opacity-70">
                  {r.status}
                </span>
                {r.label}
              </span>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
