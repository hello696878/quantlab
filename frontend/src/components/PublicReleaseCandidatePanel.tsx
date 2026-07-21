"use client";

/**
 * Public Release Candidate v1 (Phase 42.0).
 *
 * The final public-readiness page: RC status cards, the frozen demo route,
 * the manual smoke checklist, public-facing limitations, copyable closing
 * pitches, and pointers to the six Phase 42 docs.
 *
 * Deliberately frontend-only static copy (like the Portfolio Showcase and
 * Release Notes Center pages): no backend endpoint, no git access, no
 * GitHub API. Nothing on this page claims a check passed — every
 * verification step is run manually by the user and recorded in
 * docs/PUBLIC_RELEASE_CANDIDATE.md. Educational only — not investment
 * advice, not a trading system, not production compliance infrastructure.
 */

import { useState } from "react";

const VERSION_LABEL = "4.71.0-dev";
const LATEST_VERIFIED_TAG = "v4.70.0-feature-importance-stability-drift-lab-v1";
const EXPECTED_NEXT_TAG = "v4.71.0-backtest-overfitting-multiple-testing-diagnostics-v1";

const RC_STATUS_CARDS: { title: string; status: string; tone: "ok" | "warn"; text: string }[] = [
  {
    title: "Docs ready",
    status: "Written this phase",
    tone: "ok",
    text: "Release candidate, smoke runbook, demo freeze, launch readiness, public limitations, and final demo script exist under docs/ and cross-link.",
  },
  {
    title: "Smoke test required",
    status: "Manual — not yet run",
    tone: "warn",
    text: "The page-by-page pass in FINAL_SMOKE_TEST_RUNBOOK.md is a human step. This page never claims it happened.",
  },
  {
    title: "User build required",
    status: "User-run — not yet run",
    tone: "warn",
    text: "npm run build is always executed locally by the user; no tooling in this repo runs it.",
  },
  {
    title: "Safety wording reviewed",
    status: "Searched at phase time — re-check before sharing",
    tone: "ok",
    text: "The overclaim/advice/secret search was run when this phase landed; the release checklist repeats it as a pre-publish step.",
  },
  {
    title: "Secrets check required",
    status: "Manual — before going public",
    tone: "warn",
    text: "Run the publishing-time secret search in SECURITY_AND_SECRETS.md against the tree and recent history.",
  },
];

const DEMO_ROUTES: { route: string; title: string; text: string }[] = [
  { route: "portfolioshowcase", title: "1 · Portfolio Showcase", text: "What the platform demonstrates — and what it deliberately does not do." },
  { route: "democenter", title: "2 · Demo Center", text: "Guided walkthroughs plus the honest module health dashboard." },
  { route: "scenariostudio", title: "3 · Scenario Studio", text: "Cross-lab scenario impacts with every formula on the page." },
  { route: "researchworkspace", title: "4 · Research Workspace", text: "Presets, experiment journal, reproducibility — research with memory." },
  { route: "datareliability", title: "5 · Data Reliability Center", text: "Data modes and fail-closed provider story as a product surface." },
  { route: "qacommandcenter", title: "6 · QA Command Center", text: "Smoke matrix and readiness score — shows commands, never claims runs." },
  { route: "releasenotes", title: "7 · Release Notes Center", text: "Version manifest, changelog areas, and the honest release flow." },
];

const SMOKE_CHECKS: string[] = [
  "Route loads — no blank screen, spinner, or red overlay",
  "No NaN / Infinity anywhere visible",
  "No broken chart or raw LaTeX / formula error",
  "No unreadable dark-on-dark text",
  "No horizontal page overflow at desktop width",
  "Copy buttons show a success state and fill the clipboard",
  "Export / report buttons produce well-formed Markdown or JSON",
  "No live-trading or investment-advice wording in any output",
  "Responsive pass at ~1280 / ~768 / ~375 px on the demo route",
];

const LIMITATIONS: string[] = [
  "Educational deterministic sample data — nothing calibrated to markets",
  "Not investment advice; wording rules are enforced by backend tests",
  "Not a live trading system — no orders, no execution, no connectivity",
  "No broker, exchange, or wallet integrations",
  "Not a production compliance or risk system; not audited",
  "Optional providers are off by default, fail closed, never in tests",
  "Local-first and single-user; frontend build and smoke pass are user-run",
  "CI is a preflight signal (tests + typecheck + build), not a certification",
];

const FINAL_PITCH = `QuantLab — Public Release Candidate

A deterministic, local-first educational quant research platform: ~40
interactive labs (portfolio risk, macro regimes, derivatives, crypto/DeFi,
microstructure, credit, real assets) behind one shell, with a tested product
workflow layer — scenario studio, research workspace, data reliability, QA
readiness — and docs that say exactly what it is and is not.

Not a trading system, not investment advice, nothing calibrated to markets —
deliberately. The engineering story is keeping forty labs deterministic,
tested (thousands of backend tests, wording contracts included), and honestly
labeled. Limitations doc ships with the repo: docs/KNOWN_LIMITATIONS_PUBLIC.md`;

const DOC_LINKS: { path: string; title: string; text: string }[] = [
  { path: "docs/PUBLIC_RELEASE_CANDIDATE.md", title: "Public Release Candidate", text: "Required checks + the status table to fill in with evidence." },
  { path: "docs/FINAL_SMOKE_TEST_RUNBOOK.md", title: "Final Smoke Test Runbook", text: "The hands-on page-by-page verification pass (~45–60 min)." },
  { path: "docs/DEMO_FREEZE_CHECKLIST.md", title: "Demo Freeze Checklist", text: "Pin date/commit/tag; do-not-change list; allowed last-minute fixes." },
  { path: "docs/PUBLIC_LAUNCH_READINESS.md", title: "Public Launch Readiness", text: "Ten readiness areas and the Ready / Needs fix / Defer decision table." },
  { path: "docs/KNOWN_LIMITATIONS_PUBLIC.md", title: "Known Limitations (Public)", text: "The public-facing honest boundaries — link it wherever you share." },
  { path: "docs/FINAL_DEMO_SCRIPT.md", title: "Final Demo Script", text: "90-second / 3-minute / 7-minute scripts over the frozen route." },
];

export default function PublicReleaseCandidatePanel({ onNav }: { onNav?: (route: string) => void }) {
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
              Public Release Candidate
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              The final manual verification layer before QuantLab is shared publicly — the
              frozen demo route, the smoke checklist, the public limitations, and the closing
              pitch. Canonical checklists live in{" "}
              <span className="mono text-[12px]">docs/PUBLIC_RELEASE_CANDIDATE.md</span> and
              its five companion docs; the read-only summary script is{" "}
              <span className="mono text-[12px]">scripts\print_public_release_candidate.ps1</span>.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static reference copy
          </span>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <div className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
            <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Version label (VERSION file)</p>
            <p className="mono mt-0.5 text-lg font-bold" style={{ color: "var(--accent-text)" }}>{VERSION_LABEL}</p>
          </div>
          <div className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
            <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Latest verified tag (when written)</p>
            <p className="mono mt-0.5 break-all text-[12px] font-semibold" style={{ color: "var(--text-hi)" }}>{LATEST_VERIFIED_TAG}</p>
          </div>
          <div className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
            <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Expected next tag (created by the user after review)</p>
            <p className="mono mt-0.5 break-all text-[12px] font-semibold" style={{ color: "var(--text-hi)" }}>{EXPECTED_NEXT_TAG}</p>
          </div>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Public portfolio readiness only — not a production, compliance, or trading
          certification. Nothing on this page claims a test, build, or smoke pass happened;
          every check is user-run and recorded with evidence in the docs.
        </p>
      </div>

      {/* ── RC status cards ──────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Release candidate status</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-5">
          {RC_STATUS_CARDS.map((c) => (
            <div key={c.title} className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-[13px] font-semibold" style={{ color: "var(--text-hi)" }}>{c.title}</p>
              </div>
              <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide" style={{ color: c.tone === "ok" ? "var(--accent-text)" : "var(--warn)" }}>
                {c.status}
              </p>
              <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>{c.text}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Final demo route ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Final demo route (frozen order)</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {DEMO_ROUTES.map((r) => (
            <button
              key={r.route}
              type="button"
              onClick={() => onNav?.(r.route)}
              className="rounded-lg px-3 py-2 text-left transition-colors hover:border-[var(--accent)]"
              style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
            >
              <p className="text-[13px] font-semibold" style={{ color: "var(--text-hi)" }}>{r.title}</p>
              <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{r.text}</p>
              <p className="mt-1 text-[11px] font-medium" style={{ color: "var(--accent-text)" }}>Open →</p>
            </button>
          ))}
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          The 90-second demo uses stops 1–3, the 3-minute demo 1–5, the 7-minute demo all
          seven — timings and talking points in docs/FINAL_DEMO_SCRIPT.md.
        </p>
      </div>

      {/* ── Manual smoke checklist ───────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Manual smoke checklist (per page — user-run)</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {SMOKE_CHECKS.map((s) => (
            <div key={s} className="rounded-lg px-3 py-2 text-[12px]" style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}>
              {s}
            </div>
          ))}
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          The full pass (workflow pages + 15 core labs + responsive widths) is
          docs/FINAL_SMOKE_TEST_RUNBOOK.md. It is deliberately a human pass — there is no
          browser automation in this repo.
        </p>
      </div>

      {/* ── Known limitations ────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Known limitations (public-facing headlines)</p>
        <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {LIMITATIONS.map((l) => (
            <li key={l} className="flex items-start gap-2 text-[12px]" style={{ color: "var(--text-mut)" }}>
              <span aria-hidden="true" style={{ color: "var(--warn)" }}>•</span>
              <span>{l}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Full public version: docs/KNOWN_LIMITATIONS_PUBLIC.md · full internal ledger:
          docs/LIMITATIONS.md. These are deliberate boundaries, stated plainly.
        </p>
      </div>

      {/* ── Copyable final pitch ─────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title mb-0">Final demo pitch (copyable)</p>
          <div className="flex items-center gap-2">
            {copyStatus && (
              <span className="text-[11px]" style={{ color: "var(--accent-text)" }} role="status">
                {copyStatus}
              </span>
            )}
            <button
              type="button"
              onClick={() => copyText(FINAL_PITCH, "Final pitch")}
              className="rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-colors hover:border-[var(--accent)]"
              style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}
            >
              Copy pitch
            </button>
          </div>
        </div>
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg p-3 text-[12px] leading-relaxed" style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}>
          {FINAL_PITCH}
        </pre>
      </div>

      {/* ── Doc links ────────────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">The six Phase 42 documents</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {DOC_LINKS.map((d) => (
            <div key={d.path} className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <p className="text-[13px] font-semibold" style={{ color: "var(--text-hi)" }}>{d.title}</p>
              <p className="mono mt-0.5 break-all text-[11px]" style={{ color: "var(--accent-text)" }}>{d.path}</p>
              <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>{d.text}</p>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Open these in your editor — this page intentionally has no file access. Related:
          docs/RELEASE_CHECKLIST.md · docs/SECURITY_AND_SECRETS.md · docs/CI.md.
        </p>
      </div>

      {/* ── Safety panel ─────────────────────────────────────────────────── */}
      <div className="card p-4" style={{ borderColor: "var(--warn)" }}>
        <p className="section-title mb-1">Standing safety notes</p>
        <p className="text-[12px]" style={{ color: "var(--text-mut)" }}>
          Deterministic educational sample data; no live trading; no telemetry; no login; no
          cloud sync. Not investment, trading, allocation, legal, tax, compliance, or
          risk-management advice — and not production trading, risk, or compliance
          infrastructure. A release candidate here means "ready for the user's final manual
          verification before public portfolio sharing," nothing more.
        </p>
      </div>
    </div>
  );
}
