# QuantLab — Portfolio Launch Pack (Phase 38.0)

Copy-friendly pitches, demo routing, and launch checklists for presenting
QuantLab on GitHub, LinkedIn, portfolio pages, resumes, and interviews.
Companion docs: [`PUBLIC_PROJECT_SUMMARY.md`](PUBLIC_PROJECT_SUMMARY.md) ·
[`DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md) ·
[`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md) ·
[`LINKEDIN_POST_DRAFTS.md`](LINKEDIN_POST_DRAFTS.md) ·
[`INTERVIEW_TALKING_POINTS.md`](INTERVIEW_TALKING_POINTS.md).

> **Tone rule for every pitch below:** professional and specific, never
> hype-heavy. No fake metrics, no user/customer/revenue claims, no live-data
> or production-trading claims.

---

## 1. One-sentence pitch

> QuantLab is a local-first, full-stack educational quant research platform —
> ~40 interactive labs (portfolio risk, derivatives, crypto/DeFi, macro
> regimes, microstructure) on deterministic sample data, tied together by a
> scenario studio, research journal, and QA/reliability tooling.

## 2. 30-second pitch

> I built QuantLab, an interactive quant research platform: a FastAPI backend
> with strictly validated educational models and a Next.js frontend with
> shared charts, LaTeX formula panels, and a command palette. It covers
> options, volatility, rates, credit, futures, real estate, market
> microstructure, and a full crypto/DeFi suite — all on deterministic sample
> data, so every demo and all 2,900 backend tests run offline and
> reproducibly. On top of the labs there's a product layer: guided demo
> tours, a cross-lab scenario studio with report export, a research journal,
> and data-reliability and QA dashboards. It's educational by design — not a
> trading system — and the honest limitations are documented per module.

## 3. 2-minute pitch

> QuantLab started as a backtesting engine and grew into a platform. The core
> is a FastAPI + Pydantic v2 backend where every lab follows the same
> contract: a `GET /sample` endpoint serving hand-written deterministic
> sample data and a `POST /analyze` endpoint running documented educational
> models with strict validation — no NaN or Infinity can enter or leave the
> API. The frontend is Next.js 14 + TypeScript with a shared design system:
> theme-token charts, interactive shock sliders, locally rendered KaTeX
> formulas, a grouped sidebar, and a command palette.
>
> The research surface spans classic quant topics — Black-Scholes through
> Heston, volatility surfaces and variance swaps, yield curves and short-rate
> models, credit (Merton and hazard), FX, futures cost-of-carry, real estate
> and MBS prepayment, market microstructure with TCA and order-flow toxicity,
> and an AFML methodology lab (triple-barrier labels, purged CV, sequential
> bootstrap, fractional differentiation). A newer crypto suite covers perp
> funding and basis, DeFi lending health factors, tokenomics unlocks, and
> on-chain flows.
>
> What makes it feel like a product rather than a pile of demos is the
> workflow layer: a Demo Center with guided walkthroughs and module health, a
> Scenario Studio that maps one stress scenario into impact scores across
> every module and generates a copyable report, a Research Workspace that
> journals experiment runs with reproducibility checks, a Data Reliability
> Center documenting every module's data mode and offline fixtures, and a QA
> Command Center with a smoke-test matrix and release-readiness scoring.
>
> Two disciplines run through everything: determinism — tests never touch a
> live provider, and the one optional dependency (yfinance) fails closed to
> fixtures — and honesty: every module states its simplifications, and the
> platform never claims to be production trading, risk, or compliance
> infrastructure. It's an educational research platform and an engineering
> showcase.

## 4. Technical elevator pitch

> Full-stack TypeScript/Python monorepo: FastAPI + Pydantic v2 backend
> (strict schemas, `extra="forbid"`, finite-float guarantees, ~2,900
> deterministic tests), Next.js 14 app-router frontend (typed API clients,
> shared recharts components, local KaTeX, error boundaries, responsive
> dark-theme design system), SQLite for local persistence, Docker Compose,
> and GitHub Actions CI running backend tests plus a frontend build. Every
> feature ships with sample data, validation tests, and documentation in the
> same commit.

## 5. Quant research pitch

> The models are deliberately educational but methodologically careful:
> lookahead-safe backtests with explicit cost models, purged K-fold with
> embargo, sequential bootstrap, triple-barrier labeling, fractional
> differentiation, event studies with leakage guards, TCA attribution that
> sums to implementation shortfall by construction, and a cross-lab scenario
> layer with documented linear weight tables. Sample datasets are
> hand-written so failure modes are designed in — one alternative-data sample
> is built orthogonal to its signals specifically so the IC read fails, which
> teaches more than a cherry-picked win.

## 6. Recruiter pitch

> QuantLab is a solo-built, full-stack quantitative research platform:
> ~40 interactive financial labs, a typed Python/TypeScript codebase,
> ~2,900 automated tests, CI, Docker, and end-to-end documentation. It
> demonstrates API design, data visualization, testing discipline, product
> thinking (guided demos, QA dashboards, report exports), and the judgment to
> label educational models honestly instead of overclaiming. Everything runs
> locally in two commands.

## 7. Founder / product pitch

> The platform bet is that quant education tools fail by being either toy
> calculators or opaque black boxes. QuantLab's answer is transparent
> interactive labs — every formula rendered next to every number, every
> limitation stated in the UI — plus a real product shell: guided tours for
> different audiences, one-click scenario reports, a research journal, and
> reliability/QA dashboards that treat "is this demo deterministic?" as a
> first-class product question.

## 8. Project highlights

- ~40 workspaces behind one shell (sidebar groups, dashboard, command palette).
- Consistent `sample`/`analyze` API pattern across 16 backend lab routers plus
  the backtest engines.
- ~2,900 deterministic backend tests; CI runs them plus a frontend build.
- Deterministic-by-default data policy with documented offline fixtures
  (including the KO/PEP pairs-demo fallback) and fail-closed optional
  providers.
- Product workflow layer: Demo Center, Scenario Studio, Research Workspace,
  Data Reliability Center, QA Command Center, Portfolio Showcase.
- Shared local rendering everywhere: recharts + KaTeX, no CDNs, no keys.
- An honest, versioned limitations ledger (`docs/LIMITATIONS.md`).

## 9. Suggested demo route

1. Dashboard → point at the Suggested Starting Paths strip.
2. Demo Center → pick the Founder/Investor tour, show module health.
3. Scenario Studio → Soft Landing → Severe Combo, drag one slider, copy the report.
4. Research Workspace → open a preset, show the journal + reproducibility checks.
5. Data Reliability Center → the yfinance story: optional, fail-closed, test-safe.
6. QA Command Center → smoke matrix + release readiness + command checklist.
7. One deep lab per audience (Options for classic quant; DeFi Risk for crypto).

## 10. What to show first

The **Scenario Studio severe-combo heatmap**. It is the single screen that
shows breadth (every module reacts), product polish (charts, regime pill,
report export), and honesty (the formula panel shows exactly how the scores
are computed).

## 11. What not to overclaim

- Do **not** call it a trading system, a production risk engine, or
  compliance software — it is educational.
- Do **not** imply live data anywhere; optional providers are opt-in,
  delayed/historical, and fail closed.
- Do **not** present IC/Sharpe/backtest numbers as evidence of alpha — the
  samples are hand-written teaching sets.
- Do **not** claim users, customers, revenue, or production deployment.
- Do **not** claim test/build results without running them.

## 12. Safety wording (reuse verbatim)

> QuantLab is a deterministic educational research platform. Nothing in it is
> investment, trading, allocation, legal, tax, compliance, or risk-management
> advice, and no module is production trading, risk, or compliance
> infrastructure.

## 13. Data-mode wording (reuse verbatim)

> Most labs run on hand-written static sample data; the backtest engines use
> user-configured inputs; optional external providers (yfinance, FRED,
> delayed quotes) are disabled by default, fail closed to static data, and
> are never relied on in tests. External availability is never guaranteed,
> and no data shown is live or current.

## 14. Suggested GitHub release checklist

For the **final public pass**, the Phase 42 release-candidate layer is the
authoritative flow: [`PUBLIC_RELEASE_CANDIDATE.md`](PUBLIC_RELEASE_CANDIDATE.md)
(status table with evidence) →
[`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md) →
[`DEMO_FREEZE_CHECKLIST.md`](DEMO_FREEZE_CHECKLIST.md) →
[`PUBLIC_LAUNCH_READINESS.md`](PUBLIC_LAUNCH_READINESS.md), with
[`FINAL_DEMO_SCRIPT.md`](FINAL_DEMO_SCRIPT.md) and
[`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) for the demo
itself.

Work with [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) (the manual QA pass)
and [`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md), then:

- [ ] Run the backend suite locally and record the count honestly.
- [ ] Run `npx tsc --noEmit` and `npm run build` locally.
- [ ] Confirm `artifacts/` and `backend\tests\_tmp_normalized_futures` are absent.
- [ ] Capture/refresh screenshots per the checklist (real runs only).
- [ ] Re-read README + LIMITATIONS for overclaims introduced since the last pass.
- [ ] Confirm CI is green on the release commit.
- [ ] Tag the release with a factual changelog (module list + phase numbers).
- [ ] No secrets, keys, or personal paths in the repo or screenshots.
