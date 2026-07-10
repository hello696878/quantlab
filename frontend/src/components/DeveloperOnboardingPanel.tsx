"use client";

/**
 * Local Demo & Developer Onboarding v1 (Phase 39.0).
 *
 * A static developer-experience page: the environment checklist (mirroring
 * scripts/check_environment.ps1), copyable run/verify commands, common
 * troubleshooting cards, the suggested demo route with deep links, and the
 * standing safety panel.
 *
 * Deliberately frontend-only: hand-written static copy — no backend
 * endpoint, no environment probing from the browser (the real doctor is the
 * read-only PowerShell script), no network. Commands shown here are run by
 * the user; this page never runs anything. Educational only — not
 * investment advice, not a trading system.
 */

import { useState } from "react";

const ENV_CHECKLIST: { label: string; note: string }[] = [
  { label: "Python 3.11", note: "System Python on PATH (informational — the venv matters more)." },
  { label: "Backend venv", note: "backend\\venv\\Scripts\\python.exe — this repo's real venv location." },
  { label: "Backend dependencies", note: "fastapi / pydantic / pytest import inside the venv." },
  { label: "Node 18+ & npm", note: "Required for the frontend dev server, typecheck, and build." },
  { label: "Frontend dependencies", note: "frontend\\node_modules present (npm install)." },
  { label: "Backend tests", note: "Run yourself — ~2,900 deterministic tests; artifacts\\ absent after." },
  { label: "Frontend typecheck", note: "npx tsc --noEmit — strict TypeScript, run yourself." },
  { label: "Production build", note: "npm run build — always user-run; never run by scripts or this page." },
];

const COMMANDS: { label: string; cmd: string }[] = [
  { label: "Backend dev server", cmd: "cd C:\\quantlab\\backend; venv\\Scripts\\uvicorn app.main:app --reload --port 8000" },
  { label: "Backend tests", cmd: "cd C:\\quantlab; backend\\venv\\Scripts\\python.exe -m pytest backend\\tests -q" },
  { label: "Frontend typecheck", cmd: "cd C:\\quantlab\\frontend; npx tsc --noEmit" },
  { label: "Frontend dev server (user-run)", cmd: "cd C:\\quantlab\\frontend; npm run dev" },
  { label: "Production build (user-run)", cmd: "cd C:\\quantlab\\frontend; npm run build" },
  { label: "Commit & tag", cmd: "git add -A; git commit -m \"Add <thing> v1\"; git tag v<x.y.z>; git push; git push origin v<x.y.z>" },
];

const TROUBLESHOOTING: { title: string; text: string }[] = [
  { title: "uvicorn missing", text: "Run it from the venv: backend\\venv\\Scripts\\uvicorn … — if absent, pip install -r backend\\requirements.txt into the venv (yourself)." },
  { title: "venv missing", text: "python -m venv backend\\venv, then install requirements. This repo's venv is backend\\venv, not .venv." },
  { title: "node_modules missing", text: "cd frontend; npm install — then npm run dev (user-run)." },
  { title: "Port 8000/3000 busy", text: "Get-NetTCPConnection -LocalPort 8000 -State Listen to find the process, or start on another port." },
  { title: "External provider unavailable", text: "Expected: arbitrary-ticker backtests show a friendly error; the KO/PEP pairs demo always works offline; globe adapters fail closed. Stay on deterministic paths for demos." },
];

const DEMO_ROUTE: { step: string; route: string; title: string }[] = [
  { step: "1", route: "portfolioshowcase", title: "Portfolio Showcase" },
  { step: "2", route: "democenter", title: "Demo Center" },
  { step: "3", route: "scenariostudio", title: "Scenario Studio" },
  { step: "4", route: "researchworkspace", title: "Research Workspace" },
  { step: "5", route: "datareliability", title: "Data Reliability Center" },
  { step: "6", route: "qacommandcenter", title: "QA Command Center" },
];

export default function DeveloperOnboardingPanel({ onNav }: { onNav?: (route: string) => void }) {
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
              Local Demo &amp; Developer Onboarding
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Everything needed to run, verify, and demo QuantLab locally — the environment
              checklist, copyable commands, common fixes, and the suggested demo route. The
              full guides live in <span className="mono text-[12px]">docs/</span>{" "}
              (LOCAL_DEMO_GUIDE, DEVELOPER_ONBOARDING, TROUBLESHOOTING, COMMAND_REFERENCE,
              ENVIRONMENT_DOCTOR), and the read-only doctor is{" "}
              <span className="mono text-[12px]">scripts\check_environment.ps1</span>.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static reference copy
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          This page lists commands — it never runs them, probes your environment, or claims
          anything passed. Verification is your local step.
        </p>
      </div>

      {/* ── Environment checklist ────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Environment checklist</p>
          <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>
            Live read: run <span className="mono">.\scripts\check_environment.ps1</span> (read-only)
          </span>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {ENV_CHECKLIST.map((item) => (
            <div key={item.label} className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>☐ {item.label}</p>
              <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{item.note}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Command cards ────────────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Commands — run locally by you</p>
          {copyStatus && <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>{copyStatus}</span>}
        </div>
        <div className="space-y-2">
          {COMMANDS.map((c) => (
            <div key={c.label} className="flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <div className="min-w-0">
                <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{c.label}</p>
                <p className="mono break-all text-[11.5px]" style={{ color: "var(--text-hi)" }}>{c.cmd}</p>
              </div>
              <button
                type="button"
                onClick={() => copyText(c.cmd, c.label)}
                className="rounded-md px-2 py-1 text-[11px] font-semibold"
                style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
              >
                📋 Copy
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ── Troubleshooting cards ────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Common fixes</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {TROUBLESHOOTING.map((t) => (
            <div key={t.title} className="rounded-lg px-3 py-2" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{t.title}</p>
              <p className="mt-0.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{t.text}</p>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          The full list (14 issues, incl. the PowerShell execution-policy note) is in
          docs/TROUBLESHOOTING.md.
        </p>
      </div>

      {/* ── Demo route ───────────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Suggested demo route</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
          {DEMO_ROUTE.map((d) => (
            <button
              key={d.route}
              type="button"
              onClick={() => onNav?.(d.route)}
              className="rounded-xl p-3 text-left"
              style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
            >
              <span className="mono text-[11px] font-bold" style={{ color: "var(--accent-text)" }} aria-hidden>{d.step}.</span>
              <span className="mt-0.5 block text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{d.title}</span>
              <span className="mt-1 block text-xs font-medium text-blue-600">Open →</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Safety / limitations ─────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Safety &amp; limitations</p>
        <ul className="list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Local demo only — deterministic educational sample data throughout; optional external providers are disabled by default and fail closed.</li>
          <li>The helper scripts are local conveniences: no installs, no dev/build runs, no downloads, no execution-policy changes, no secrets — inspect them before running.</li>
          <li>Not investment, trading, allocation, legal, tax, compliance, or risk-management advice; no live trading; not production compliance or risk infrastructure.</li>
          <li>Nothing on this page proves tests or builds passed — run the verification commands yourself.</li>
        </ul>
      </div>
    </div>
  );
}
