"use client";

/**
 * Portfolio Showcase v1 (Phase 38.0).
 *
 * A static public-presentation page: what QuantLab demonstrates, the
 * suggested demo path (deep links into the real modules), grouped project
 * highlights, copyable pitches (mirroring docs/PORTFOLIO_LAUNCH_PACK.md),
 * and the standing safety/limitations panel.
 *
 * Deliberately frontend-only: everything here is hand-written static
 * presentation copy — no backend endpoint, no data fetch, no state beyond
 * the copy-status message. Educational only — not investment advice, not a
 * trading system, not production compliance infrastructure.
 */

import { useState } from "react";

const PITCHES: { id: string; label: string; text: string }[] = [
  {
    id: "one_sentence",
    label: "One-sentence pitch",
    text:
      "QuantLab is a local-first, full-stack educational quant research platform — " +
      "~40 interactive labs (portfolio risk, derivatives, crypto/DeFi, macro regimes, " +
      "microstructure) on deterministic sample data, tied together by a scenario studio, " +
      "research journal, and QA/reliability tooling.",
  },
  {
    id: "recruiter",
    label: "Recruiter pitch",
    text:
      "QuantLab is a solo-built, full-stack quantitative research platform: ~40 interactive " +
      "financial labs, a typed Python/TypeScript codebase, ~2,900 automated tests, CI, Docker, " +
      "and end-to-end documentation. It demonstrates API design, data visualization, testing " +
      "discipline, product thinking, and the judgment to label educational models honestly " +
      "instead of overclaiming. Everything runs locally in two commands.",
  },
  {
    id: "quant",
    label: "Quant researcher pitch",
    text:
      "QuantLab's models are deliberately educational but methodologically careful: " +
      "lookahead-safe backtests with explicit costs, purged K-fold with embargo, sequential " +
      "bootstrap, triple-barrier labeling, fractional differentiation, event studies with " +
      "leakage guards, TCA attribution that sums to shortfall by construction, and a cross-lab " +
      "scenario layer with documented weight tables. Sample datasets carry designed failure " +
      "modes — no result is presented as evidence of alpha.",
  },
  {
    id: "technical",
    label: "Technical pitch",
    text:
      "Full-stack TypeScript/Python monorepo: FastAPI + Pydantic v2 backend (strict schemas, " +
      "finite-float guarantees, ~2,900 deterministic tests), Next.js 14 app-router frontend " +
      "(typed API clients, shared recharts components, local KaTeX, error boundaries), SQLite " +
      "for local persistence, Docker Compose, and GitHub Actions CI running backend tests plus " +
      "a frontend build.",
  },
];

const DEMO_PATH: { step: string; route: string; title: string; text: string }[] = [
  { step: "1", route: "democenter", title: "Start with the Demo Center", text: "Guided walkthroughs per audience, module health, and a demo script builder." },
  { step: "2", route: "scenariostudio", title: "Build a Scenario Studio report", text: "Ten stress templates, shock sliders, the cross-module heatmap, and a copyable report." },
  { step: "3", route: "researchworkspace", title: "Organize the Research Workspace", text: "Saved research packs, an experiment journal, and Markdown/JSON exports." },
  { step: "4", route: "datareliability", title: "Inspect Data Reliability", text: "Data modes, offline fixtures, and fail-closed optional providers — documented in-app." },
  { step: "5", route: "qacommandcenter", title: "Check the QA Command Center", text: "Smoke-test matrix, release readiness, and the exact local verification commands." },
];

const HIGHLIGHTS: { title: string; route: string; text: string }[] = [
  { title: "Portfolio & Macro", route: "risklab", text: "Portfolio Risk Lab, Macro Regime & Cross-Asset Allocation, optimization/frontier/stress tools." },
  { title: "Crypto & DeFi", route: "cryptoderivatives", text: "Perp funding & basis, DeFi lending health factors, tokenomics unlocks, on-chain flows — all with shock sliders." },
  { title: "Derivatives", route: "options", text: "Black-Scholes to Heston Monte Carlo, volatility surfaces & variance swaps, futures cost-of-carry." },
  { title: "Market Microstructure", route: "microstructure", text: "Order-book analytics, execution schedules, TCA attribution, and order-flow toxicity metrics." },
  { title: "Real Assets & Credit", route: "realestate", text: "Real estate & MBS prepayment, Merton and reduced-form credit, yield curves, short rates, FX." },
  { title: "Methodology & QA", route: "finml", text: "AFML labeling/CV/bootstrap/fracdiff, lookahead-safe backtests, leakage guards, QA dashboards." },
];

const DEMONSTRATES = [
  "Full-stack quant research platform (FastAPI + Pydantic v2, Next.js 14 + TypeScript)",
  "Interactive modeling labs with formulas rendered beside the numbers (local KaTeX)",
  "Deterministic demo data — every lab and all ~2,900 backend tests run offline",
  "Scenario → report → journal product workflow with copyable Markdown/JSON exports",
  "Data reliability and QA readiness treated as first-class product surfaces",
];

export default function PortfolioShowcasePanel({ onNav }: { onNav?: (route: string) => void }) {
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  async function copyText(text: string, what: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus(`${what} copied ✓`);
    } catch {
      setCopyStatus("Copy failed — select the text instead");
    }
    window.setTimeout(() => setCopyStatus(null), 2500);
  }

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>
              QuantLab Portfolio Showcase
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              The public-presentation view of QuantLab: what the platform demonstrates, the
              suggested demo route, grouped highlights, and copyable pitches for portfolio
              pages, resumes, and interviews. Companion docs live in{" "}
              <span className="mono text-[12px]">docs/PORTFOLIO_LAUNCH_PACK.md</span>.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static presentation copy
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Deterministic educational sample data throughout the platform — not investment,
          trading, allocation, legal, tax, compliance, or risk-management advice; not a live
          trading system; not production risk or compliance infrastructure.
        </p>
      </div>

      {/* ── What QuantLab demonstrates ───────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">What QuantLab demonstrates</p>
        <ul className="grid grid-cols-1 gap-x-6 gap-y-1.5 lg:grid-cols-2">
          {DEMONSTRATES.map((d) => (
            <li key={d} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-mut)" }}>
              <span aria-hidden className="mt-0.5 flex-shrink-0" style={{ color: "var(--accent-text)" }}>▸</span>
              {d}
            </li>
          ))}
        </ul>
      </div>

      {/* ── Demo path ────────────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Suggested demo path</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-5">
          {DEMO_PATH.map((p) => (
            <button
              key={p.route}
              type="button"
              onClick={() => onNav?.(p.route)}
              className="rounded-xl p-3 text-left transition-colors"
              style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
            >
              <span className="flex items-center gap-2">
                <span
                  className="mono flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
                  style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
                  aria-hidden
                >
                  {p.step}
                </span>
                <span className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{p.title}</span>
              </span>
              <span className="mt-1 block text-[11px]" style={{ color: "var(--text-mut)" }}>{p.text}</span>
              <span className="mt-1 block text-xs font-medium text-blue-600">Open →</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Project highlights ───────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Project highlights</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {HIGHLIGHTS.map((h) => (
            <button
              key={h.title}
              type="button"
              onClick={() => onNav?.(h.route)}
              className="rounded-xl p-3 text-left transition-colors"
              style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
            >
              <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{h.title}</p>
              <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>{h.text}</p>
              <span className="mt-1 block text-xs font-medium text-blue-600">Explore →</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Copyable pitches ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Copyable pitches</p>
          {copyStatus && <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>{copyStatus}</span>}
        </div>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {PITCHES.map((p) => (
            <div key={p.id} className="rounded-xl p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{p.label}</p>
                <button
                  type="button"
                  onClick={() => copyText(p.text, p.label)}
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
                  style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
                >
                  📋 Copy
                </button>
              </div>
              <p className="mt-1.5 text-[12px] leading-relaxed" style={{ color: "var(--text-hi)" }}>{p.text}</p>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Longer versions (30-second, 2-minute, founder/product) live in
          docs/PORTFOLIO_LAUNCH_PACK.md; LinkedIn drafts and interview talking points are in
          docs/ as well.
        </p>
      </div>

      {/* ── Safety / limitations ─────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Safety &amp; limitations</p>
        <ul className="list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Deterministic static sample data in most labs; user-configured inputs in the backtest engines; optional external providers are disabled by default, fail closed, and are never relied on in tests.</li>
          <li>Educational only — not investment, trading, allocation, legal, tax, compliance, or risk-management advice.</li>
          <li>Not a live trading system; no broker, exchange, or wallet integration; no order submission.</li>
          <li>Not production risk, compliance, or data-governance infrastructure — the honest per-module ledger is docs/LIMITATIONS.md.</li>
          <li>No telemetry, no login, no cloud sync; verification (backend suite, typecheck, production build) is run locally by the user.</li>
        </ul>
      </div>
    </div>
  );
}
