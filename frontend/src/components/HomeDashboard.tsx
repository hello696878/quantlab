"use client";

import { useEffect, useState } from "react";
import type { View } from "@/components/AppShell";
import { checkHealth, listSavedBacktests, listSavedReports } from "@/lib/api";
import type { SavedBacktestSummary, SavedReportSummary } from "@/lib/types";
import { fmtPct, fmtRatio } from "@/lib/format";
import { DEMO_PRESETS, type DemoPresetId } from "@/lib/demoPresets";
import {
  EMPTY_CHECKLIST,
  ONBOARDING_EVENT,
  getChecklist,
  isOnboardingHidden,
  setOnboardingHidden,
  type ChecklistState,
  type ChecklistStep,
} from "@/lib/onboarding";

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

function metricColor(v: number | null | undefined, positiveGood = true): string {
  if (v == null) return "text-slate-400";
  if (v > 0) return positiveGood ? "text-green-700" : "text-red-600";
  if (v < 0) return positiveGood ? "text-red-600" : "text-green-700";
  return "text-slate-500";
}

/** Quick-start checklist rows. Order = suggested first-run path. */
const CHECKLIST_ITEMS: { step: ChecklistStep; label: string }[] = [
  { step: "ran_backtest", label: "Run your first backtest" },
  { step: "saved_backtest", label: "Save a backtest" },
  { step: "exported_report", label: "Export a report" },
  { step: "viewed_risk", label: "Try the portfolio risk dashboard" },
  { step: "built_strategy", label: "Build a custom strategy" },
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
}

export default function HomeDashboard({
  onNav,
  onOpenBacktest,
  onOpenReport,
  onDemo,
}: HomeDashboardProps) {
  const [backtests, setBacktests] = useState<SavedBacktestSummary[]>([]);
  const [reports, setReports] = useState<SavedReportSummary[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [btOk, setBtOk] = useState(true);
  const [rpOk, setRpOk] = useState(true);

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
    checkHealth().then((ok) => {
      if (!cancelled) setOnline(ok);
    });
    Promise.allSettled([listSavedBacktests(), listSavedReports()]).then(
      ([b, r]) => {
        if (cancelled) return;
        if (b.status === "fulfilled") setBacktests(b.value);
        else setBtOk(false);
        if (r.status === "fulfilled") setReports(r.value);
        else setRpOk(false);
        setLoaded(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  // ISO timestamps sort lexicographically == chronologically; newest first.
  const recentBacktests = [...backtests]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 5);
  const recentReports = [...reports]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 5);

  const doneCount = CHECKLIST_ITEMS.filter((i) => checklist[i.step]).length;

  const quickActions: QuickAction[] = [
    {
      label: "Run Single-Asset Backtest",
      description: "SMA, RSI, Bollinger, Momentum, Breakout, or Pairs",
      icon: "M4 4v16h16M8 16l3-4 3 2 4-6",
      onClick: () => onNav("backtest"),
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
              QuantLab Command Center
            </h1>
            <p className="mt-1.5 max-w-2xl text-sm text-slate-400">
              Research, backtest, optimize, and report trading strategies from
              one local dashboard.
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
      </div>

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
                className="flex-shrink-0 rounded-md px-2 py-1 text-xs font-medium text-slate-400 transition-colors hover:text-slate-200"
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
            value={!loaded ? "…" : btOk ? String(backtests.length) : "—"}
          />
          <StatusTile
            label="Saved Reports"
            value={!loaded ? "…" : rpOk ? String(reports.length) : "—"}
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
            <div className="card p-6 text-center text-sm text-slate-500">Loading…</div>
          ) : !btOk ? (
            <div className="card p-6 text-center text-sm text-slate-400">
              Couldn&apos;t reach the backend to load saved backtests.
            </div>
          ) : recentBacktests.length === 0 ? (
            <div className="card p-6 text-center text-sm text-slate-400">
              No saved backtests yet. Run a backtest and save it to see it here.
            </div>
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
            <div className="card p-6 text-center text-sm text-slate-500">Loading…</div>
          ) : !rpOk ? (
            <div className="card p-6 text-center text-sm text-slate-400">
              Couldn&apos;t reach the backend to load saved reports.
            </div>
          ) : recentReports.length === 0 ? (
            <div className="card p-6 text-center text-sm text-slate-400">
              No saved reports yet. Run any analysis and click Save Report to see
              it here.
            </div>
          ) : (
            <div className="card overflow-hidden">
              {recentReports.map((r, i) => (
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
                      {r.tickers.length > 0 ? ` · ${r.tickers.join(", ")}` : ""}
                    </p>
                  </div>
                  <span className="flex-shrink-0 text-xs text-slate-500">
                    {fmtDate(r.created_at)}
                  </span>
                </button>
              ))}
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
    </div>
  );
}
