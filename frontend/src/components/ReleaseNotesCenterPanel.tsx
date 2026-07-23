"use client";

/**
 * Version Manifest & Release Notes Center v1 (Phase 40.0).
 *
 * A static release-management reference page: the current version label and
 * conventions, changelog summary cards by release area, the release-flow
 * checklist, a copyable release-notes template skeleton, the project
 * snapshot, and the standing safety panel.
 *
 * Deliberately frontend-only static copy (like the Portfolio Showcase and
 * Developer Onboarding pages): no backend endpoint, no git access from the
 * browser, no GitHub API — the live reads come from the read-only
 * scripts\print_release_summary.ps1, and the canonical documents live in
 * CHANGELOG.md, VERSION, and docs/. Version labels are project milestone
 * labels, not package publications. Educational only — not investment
 * advice, not a trading system.
 */

import { useState } from "react";

const VERSION_LABEL = "4.73.0-dev";
const EXPECTED_NEXT_TAG = "v4.73.0-transaction-cost-slippage-capacity-diagnostics-v1";
const LATEST_VERIFIED_TAG = "v4.72.0-market-regime-robustness-conditional-performance-v1";

const RELEASE_AREAS: { title: string; text: string; route?: string }[] = [
  { title: "Quant research labs", text: "Portfolio/macro, derivatives & volatility, crypto/DeFi/on-chain/alt-data, microstructure, real assets & credit, rates/FX — deterministic educational models with formulas beside the numbers.", route: "risklab" },
  { title: "Product workflow", text: "Scenario Studio, Research Workspace, Demo Center, Portfolio Showcase — scenario → report → journal → presentation.", route: "scenariostudio" },
  { title: "Reliability / QA", text: "Data Reliability Center and QA Command Center — data modes, offline fixtures, smoke matrix, release readiness.", route: "datareliability" },
  { title: "Public docs", text: "Launch pack, public summaries, screenshot/video scripts, LinkedIn drafts, interview talking points.", route: "portfolioshowcase" },
  { title: "Developer onboarding", text: "Local demo guide, environment doctor, safe helper scripts, troubleshooting, command reference.", route: "developeronboarding" },
];

const CHANGELOG_CARDS: { tag: string; title: string; text: string }[] = [
  { tag: "v4.73 (next)", title: "Cost & capacity diagnostics lab", text: "Unit-safe commission/spread/slippage/square-root-impact estimates on supplied observations with a no-look-ahead liquidity-input policy, exact gross-to-net reconciliation (missing inputs stay unavailable — never zero), break-even, sensitivity, and capacity scaling with participation warnings. Estimates under configured assumptions — never fill predictions or size advice." },
  { tag: "v4.72", title: "Regime diagnostics lab", text: "Conditional performance across no-look-ahead market regimes (trailing windows, lagged labels, integrity-stated threshold fitting), rank stability, concentration, and transition differences. Descriptive states — never predictions or switching advice." },
  { tag: "v4.71", title: "Overfitting diagnostics lab", text: "CSCV/PBO selection-bias estimates with a fixed rank convention, deflated Sharpe (PSR/DSR) under explicit trial-count assumptions, MinTRL, and Bonferroni/Holm/BH corrections. Research statistics — never robustness or a strategy pick." },
  { tag: "v4.70", title: "Feature diagnostics lab", text: "Held-out permutation importance via validation-split memberships, caveated native/coefficient references, rank stability, correlated-feature groups, and PSI/KS distribution + importance drift. Sensitivity, never causality." },
  { tag: "v4.69 (untagged)", title: "Meta-labeling lab", text: "Outcome-rule meta-labels, Platt/isotonic calibration with out-of-fold integrity via validation splits, reliability curves (Brier/ECE), and neutral threshold trade-offs with user-saved policies. Never a recommendation." },
  { tag: "v4.68", title: "Model validation lab", text: "Purged K-fold, embargo, and CPCV over information intervals with a from-scratch leakage audit, temporal split timeline, neutral metrics, and registry links. Methodology only — no profitability claims." },
  { tag: "v4.67", title: "Dataset lineage", text: "Local-first dataset registry: immutable versions with schema/manifest fingerprints, privacy-safe locators, cycle-safe transformation lineage, quality checks, neutral schema drift, and experiment links. Integrity aids only." },
  { tag: "v4.66", title: "Experiment registry", text: "Local-first SQLite registry of reproducibility metadata: deterministic fingerprints, a conservative reproducibility check, baseline scope, neutral comparison, JSON export, and demo records. Integrity aids only." },
  { tag: "v4.65", title: "Post-publication baseline", text: "Read-only verification of the v4.64 state with observed run IDs, publication record, stable post-release baseline and change policy." },
  { tag: "v4.64", title: "Public release launch", text: "Final manual release draft, facts-only evidence ledger with observed run IDs, public launch checklist, SHA-256 checksum manifest + verifier." },
  { tag: "v4.63", title: "Manual CI browser E2E", text: "workflow_dispatch-only GitHub Actions workflow running the Playwright guard in an isolated runner with per-run evidence artifacts." },
  { tag: "v4.62", title: "Public release package", text: "GitHub release draft (manual publish), LinkedIn drafts, portfolio case study, demo video shot list + scripts, release asset manifest." },
  { tag: "v4.61", title: "Browser E2E guard", text: "Playwright harness (12 tests, zero browser downloads) pinning the frozen demo route, scenario result, KO/PEP fixture, responsive geometry." },
  { tag: "v4.60", title: "Public release candidate", text: "Demo freeze with SHA-256'd evidence screenshots, final smoke runbook, launch readiness, public limitations, Public Release Candidate page." },
  { tag: "v4.59", title: "CI preflight & repo hygiene", text: "CI hardening (read-only permissions, fast-fail typecheck), CONTRIBUTING, hygiene and security/secrets docs, read-only hygiene script." },
  { tag: "v4.58", title: "Release management", text: "Version manifest, grouped changelog, release-notes template, extended checklist, milestone history, project snapshot, this page." },
  { tag: "v4.57", title: "Developer onboarding", text: "Local demo guide, environment doctor, six safe helper scripts, onboarding page." },
  { tag: "v4.56", title: "Portfolio launch pack", text: "Public README, pitches, screenshot/video/interview docs, Portfolio Showcase page." },
  { tag: "v4.55", title: "Platform UX polish", text: "Route error boundaries, grouped sidebar, starting paths, accessibility passes." },
  { tag: "v4.54", title: "QA Command Center", text: "QA registry, release score & decision, smoke matrix, verification command checklist." },
  { tag: "v4.53", title: "Data Reliability Center", text: "Data-mode/provider/fixture registries; fail-closed provider story as a product surface." },
  { tag: "v4.52", title: "Demo Center", text: "Guided demo paths, module health dashboard, audience-aware demo script builder." },
  { tag: "v4.50–51", title: "Scenario Studio & Research Workspace", text: "Cross-lab impact scoring + report builder; experiment journal with reproducibility checks." },
  { tag: "v4.42–49", title: "Crypto & macro suite", text: "Crypto derivatives, DeFi, tokenomics, on-chain, alternative data, macro regimes — plus interactive charts." },
  { tag: "v4.8–41", title: "Asset-class labs", text: "Options → Heston, vol surfaces, futures, real estate/MBS, credit, rates, FX, events, microstructure, globe data layer." },
];

const CHECKLIST_STEPS: string[] = [
  "git status / pull --rebase — clean tree on main",
  "Backend suite (run, don't assume) — record the real count; artifacts\\ absent after",
  "npx tsc --noEmit — exit 0",
  "npm run build — user-run, always",
  "Manual route smoke pass (QA Command Center matrix)",
  "Docs & wording: CHANGELOG Unreleased → version heading; VERSION bump; no overclaims; no secrets",
  "Tag after the Review commit: v4.xx.0-short-feature-name-v1",
  "Optional manual steps: GitHub release draft, LinkedIn/portfolio update",
];

const TEMPLATE_SKELETON = `# QuantLab <version tag> — <Release Title>

**Tag:** v4.xx.0-<short-feature-name>-v1

## Summary
## Highlights
## Added / Changed / Fixed
## Documentation
## Tests / checks actually run        <- real results only
## Checks expected but not run in this pass
## Frontend build status              <- user-run; state honestly
## Known limitations
## Data mode / safety notes
## Manual demo checklist
## Rollback notes
## Next release candidates`;

export default function ReleaseNotesCenterPanel({ onNav }: { onNav?: (route: string) => void }) {
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
              Version Manifest &amp; Release Notes Center
            </h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              The project's versioning story in one place: current version label, tag/commit
              conventions, changelog by release area, the release flow, and a copyable
              release-notes skeleton. Canonical documents:{" "}
              <span className="mono text-[12px]">CHANGELOG.md</span>,{" "}
              <span className="mono text-[12px]">VERSION</span>, and{" "}
              <span className="mono text-[12px]">docs/VERSION_MANIFEST.md</span>; the read-only
              live summary is <span className="mono text-[12px]">scripts\print_release_summary.ps1</span>.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static reference copy
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Version labels are project milestone labels, not package publications. Nothing here
          claims a public release, production certification, or that tests/builds passed —
          verification results are recorded per release, honestly.
        </p>
      </div>

      {/* ── Current version card ─────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Current version</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
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
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Conventions (verified against the local git history): commits land as
          “Add &lt;feature&gt; v1” then “Review &lt;feature&gt; v1”; tags follow
          v4.xx.0-short-feature-name-v1 and are created manually after review. A review tag is
          not a production, compliance, or live-trading certification.
        </p>
      </div>

      {/* ── Release areas ────────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Release areas</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-5">
          {RELEASE_AREAS.map((a) => (
            <button
              key={a.title}
              type="button"
              onClick={() => a.route && onNav?.(a.route)}
              className="rounded-xl p-3 text-left"
              style={{ background: "var(--glass)", border: "1px solid var(--line)" }}
            >
              <p className="text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{a.title}</p>
              <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>{a.text}</p>
              {a.route && <span className="mt-1 block text-xs font-medium text-blue-600">Open →</span>}
            </button>
          ))}
        </div>
      </div>

      {/* ── Changelog summary cards ──────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Changelog by release area (summary)</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-5">
          {CHANGELOG_CARDS.map((c) => (
            <div key={c.tag} className="rounded-xl p-3" style={{ background: "var(--glass)", border: "1px solid var(--line)" }}>
              <p className="mono text-[10px] font-bold uppercase tracking-wide" style={{ color: "var(--accent-text)" }}>{c.tag}</p>
              <p className="mt-0.5 text-sm font-semibold" style={{ color: "var(--text-hi)" }}>{c.title}</p>
              <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>{c.text}</p>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Full grouped changelog: CHANGELOG.md · per-phase detail: docs/ROADMAP.md · narrative:
          docs/MILESTONE_HISTORY.md.
        </p>
      </div>

      {/* ── Release checklist ────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Release flow (docs/RELEASE_CHECKLIST.md, Part 1)</p>
        <ol className="space-y-1.5">
          {CHECKLIST_STEPS.map((step, i) => (
            <li key={step} className="flex items-start gap-2.5 text-sm" style={{ color: "var(--text-mut)" }}>
              <span className="mono mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
                style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }} aria-hidden>
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      </div>

      {/* ── Release notes template ───────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Release notes skeleton</p>
          <div className="flex items-center gap-2">
            {copyStatus && <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>{copyStatus}</span>}
            <button
              type="button"
              onClick={() => copyText(TEMPLATE_SKELETON, "Template")}
              className="rounded-md px-2.5 py-1 text-xs font-semibold"
              style={{ background: "var(--accent-softer)", border: "1px solid var(--accent-line)", color: "var(--accent-text)" }}
            >
              📋 Copy skeleton
            </button>
          </div>
        </div>
        <pre className="mono overflow-x-auto whitespace-pre rounded-lg p-3 text-[11.5px] leading-relaxed"
          style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-mut)" }}>
          {TEMPLATE_SKELETON}
        </pre>
        <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
          The full template (docs/RELEASE_NOTES_TEMPLATE.md) insists on the three verification
          distinctions: tests <em>actually run</em> vs <em>expected</em>, and the frontend build
          as a user-run step — no false pass claims, ever.
        </p>
      </div>

      {/* ── Project snapshot summary ─────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Project snapshot (docs/PROJECT_SNAPSHOT.md)</p>
        <ul className="list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>~40 workspaces across 11 sidebar groups; FastAPI + Pydantic v2 backend with a consistent sample/analyze pattern; Next.js 14 + TypeScript frontend with shared chart/formula/state primitives.</li>
          <li>Deterministic static samples in most labs; the only external providers are disabled by default, fail closed, and never relied on in tests.</li>
          <li>~2,900 deterministic backend tests (count recorded per phase in the ROADMAP); strict TypeScript; CI runs backend tests + a frontend build; no frontend test framework yet.</li>
          <li>Public-portfolio ready except newer-lab screenshots; hosted deployment deliberately not claimed (docs/DEPLOYMENT_READINESS.md).</li>
        </ul>
      </div>

      {/* ── Safety / limitations ─────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Safety &amp; limitations</p>
        <ul className="list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Deterministic educational sample data throughout — no live data, no live trading, no broker/exchange/wallet integration.</li>
          <li>Version labels and review tags are milestone markers — not production, compliance, or risk certifications.</li>
          <li>Not investment, trading, allocation, legal, tax, compliance, or risk-management advice.</li>
          <li>This page is hand-written static copy and can drift until re-reviewed — the canonical sources are VERSION, CHANGELOG.md, and docs/.</li>
        </ul>
      </div>
    </div>
  );
}
