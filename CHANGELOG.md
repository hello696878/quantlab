# Changelog

All notable changes to QuantLab are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Changes
after v4.7.0 are **grouped by release area** rather than per-commit — the
per-phase detail lives in [`docs/ROADMAP.md`](docs/ROADMAP.md), and local tags
follow `v4.xx.0-short-feature-name-v1`
(see [`docs/VERSION_MANIFEST.md`](docs/VERSION_MANIFEST.md)). Version labels
are project milestone labels, not package publications; no public release is
claimed by an entry here.

> **Research only.** QuantLab is an educational/research tool — it does not place
> trades, connect to a broker, or provide investment advice, and it is not
> production trading, risk, or compliance infrastructure.

---

## Unreleased

- **Purged Cross-Validation, Embargo & CPCV Model Validation Lab v1** (v4.68
  series): a local-first validation lab for time-dependent research —
  temporal-event samples with closed information intervals
  [prediction_time, evaluation_time]; standard K-fold as an explicitly-warned
  leakage reference (shuffle off by default, seed required to enable);
  chronological walk-forward (expanding/rolling) with boundary purging on by
  default; purged K-fold with interval-based purging and per-id overlap
  reasons; CPCV with deterministic C(N,k) combinations bounded at 100; a
  configurable embargo (duration-days or ≤0.2 span-fraction, start-exclusive/
  end-inclusive windows merged per disjoint test block, reported separately
  from purging); a from-scratch leakage audit that marks any split with
  remaining overlap invalid; dependency-light neutral metrics (undefined →
  null with reasons, never Infinity or zero-coercion); deterministic
  configuration/split/result fingerprints; SQLite persistence
  (validation_runs + validation_splits); idempotent Experiment Registry
  linking and Dataset Lineage version links with invalidation warnings;
  leakage-clean-only baselines scoped per (method, dataset version); neutral
  run comparison; JSON export; a seven-run deterministic demo; a new **Model
  Validation Lab** frontend view (dark ql-input controls, temporal split
  timeline SVG with membership fallback); an 11-test Playwright spec; and
  three docs (`MODEL_VALIDATION_LAB.md`, `PURGED_CV_AND_EMBARGO_POLICY.md`,
  `CPCV_RUNBOOK.md`). Methodology and audit only — no profitability claims,
  no model recommendations, not certification, not investment advice.

## Grouped release areas — v4.8 through v4.67 (post-showcase series)

### Data provenance & dataset lineage dashboard (v4.67)

- Local-first SQLite dataset registry: dataset identity with immutable
  versions, deterministic schema/manifest fingerprints (content fingerprints
  only via explicit operations), privacy-safe logical storage locators
  (absolute paths/credentials rejected), cycle-safe transformation lineage
  with bounded traversal, metadata-driven quality checks, neutral schema-drift
  comparison, invalidation that preserves lineage and links, bidirectional
  Experiment Registry links with fingerprint-match flags, JSON export, an
  idempotent three-chain demo, the Dataset Lineage frontend view (SVG lineage
  graph + tabular fallback), and a 9-test Playwright spec.

### Research experiment registry & reproducibility dashboard (v4.66)

- Local-first SQLite registry of reproducibility metadata: deterministic
  SHA-256 configuration/result fingerprints (canonical JSON, NaN/Infinity
  rejected), a conservative reproducibility assessment, per-scope baseline
  selection, neutral two-experiment comparison, JSON export, idempotent demo
  records, an opt-in best-effort integration helper (Scenario Studio / KO-PEP
  endpoints unmodified), the Experiment Registry frontend view, a Playwright
  spec, and app-wide 422 hardening for non-finite JSON tokens. The review
  pass added the dark-theme `ql-input` filter controls and the min-width
  table-density fix with E2E guards for both.

### Post-publication verification & stable release baseline (v4.65)

- Read-only verification of the real v4.64 state (tag local = remote →
  `2d4bcfe`; CI run 29188597089 ✅ and Browser E2E Preflight run 29193708980 ✅
  observed on that exact commit; GitHub Release publication remained pending),
  a factual publication record, an item-by-item post-publication verification
  report, the stable post-release baseline document, evidence-ledger/launch-
  checklist updates, and a post-publication checksum manifest.

### Public GitHub release launch closure (v4.64)

- Final manual release draft, facts-only evidence ledger with observed
  CI/E2E run IDs, 22-section public launch checklist + publication runbook,
  SHA-256 checksum manifest with a read-only verifier
  (`verify_release_checksums.py`, unit-tested), README screenshot gallery
  from the frozen evidence. Publication remains a manual user action.

### Manual CI browser E2E evidence (v4.63)

- `workflow_dispatch`-only GitHub Actions workflow (`Browser E2E Preflight`)
  that builds and starts QuantLab in an isolated Ubuntu runner and runs the
  Playwright frozen-demo guard, with per-run evidence artifacts (14-day
  retention); stdlib-only localhost-only readiness helper
  (`scripts/wait_for_http.py`, unit-tested); `CI_BROWSER_E2E.md`. First
  remote run observed green (run 29185725247 on the tag target commit).

### Public release package & demo asset kit (v4.62)

- Copy-ready GitHub release draft (manual publication only), LinkedIn launch
  post drafts, portfolio case study, demo video shot list + 90-second and
  3-minute scripts, public-README checklist, release asset manifest, and
  `scripts/print_public_release_package.ps1` (print-only). Presentation
  material only — no product behavior changes, no automatic releases.

### Browser E2E regression guard (v4.61)

- Playwright harness (one devDependency; drives OS-installed Edge — zero
  browser downloads): 12 tests guarding the frozen demo route, Scenario
  Studio severe-combo result, the KO/PEP pairs fixture, and 1440/1024/768
  responsive geometry; hydration-aware stabilization; E2E runbook, setup,
  and frozen-demo-guard docs; refuse-if-down wrapper scripts.

### Public release candidate & demo freeze (v4.60)

- Six public-readiness docs (release candidate, final smoke test runbook,
  demo freeze checklist, public launch readiness, public known limitations,
  final demo script), the in-app Public Release Candidate page,
  `scripts/print_public_release_candidate.ps1` (print-only), the first full
  browser smoke test (37 views; three responsive defects fixed), futures
  fixture isolation + YM roll coverage, and the frozen freeze record with
  five SHA-256'd production screenshots.

The tags between v4.8.0 and v4.67.0 (local milestone tags; full per-phase
detail in `docs/ROADMAP.md`) grouped by area:

### CI preflight, repository hygiene & security sweep (v4.59)

- CI workflow hardening (read-only permissions, fast-fail typecheck step),
  extended `.gitignore`, `CONTRIBUTING.md`, CI / repository-hygiene /
  security-and-secrets docs, and the read-only
  `scripts/check_repo_hygiene.ps1`.

### Release management (v4.58)

- Version manifest, the grouped changelog refresh, release-notes template,
  extended release checklist, milestone history, project snapshot, `VERSION`
  file, in-app Release Notes Center page, and
  `scripts/print_release_summary.ps1` (print-only).

### Developer onboarding & local demo readiness (v4.57)

- Local demo guide, developer onboarding, troubleshooting, command reference,
  and environment-doctor docs; six safe PowerShell helper scripts (read-only
  doctor, run/test/typecheck wrappers, `.next` cache cleaner, print-only
  cheat sheet); in-app Developer Onboarding page.

### Portfolio launch & public docs (v4.56)

- Public-facing README; portfolio launch pack, public project summaries,
  screenshot checklist, demo video scripts, LinkedIn drafts, interview
  talking points, deployment-readiness notes; in-app Portfolio Showcase page.

### Platform UX polish (v4.55)

- App-router error/loading/not-found safety pages; the sidebar grouped into
  labelled sections (all entries preserved); dashboard "Suggested Starting
  Paths"; chart `ariaLabel` support; visible keyboard focus on shared sliders.

### QA & release readiness (v4.54)

- QA Command Center: 21-module QA registry, coverage rates and release
  score, rule-based release decision, smoke-test matrix, regression
  checklists, exact local verification commands — explicitly never claiming
  tests were run.

### Data reliability & offline fixtures (v4.53)

- Data Reliability Center: module data-mode registry, provider registry
  (optional yfinance/FRED/delayed-quote paths disabled by default,
  fail-closed, never relied on in tests), offline fixture registry incl. the
  KO/PEP pairs-demo fallback, documented reliability rates and score.

### Demo center & product walkthroughs (v4.52)

- Demo Center: eight guided demo paths with deep links, module health
  dashboard, capability matrix, audience/time-budget-aware demo script
  builder with Markdown/JSON export.

### Research workspace & experiment journal (v4.51)

- Research Workspace: saved research packs, staged-run experiment journal,
  severity/coverage/reproducibility scores, workflow timeline, methodology
  checklist, Markdown/JSON exports, optional browser-local drafts.

### Scenario studio & cross-lab reports (v4.50)

- Unified Scenario Studio: ten deterministic scenario templates, global
  shock sliders, documented cross-lab impact-score weight tables, module
  impact charts and heatmap, regime classification, copyable Markdown report.

### Crypto / DeFi / on-chain / alternative data / macro labs (≈v4.42–v4.49)

- Crypto Derivatives (perp funding/basis, educational liquidation
  estimates), DeFi Risk (kinked rate model, finite-by-construction health
  factors), Tokenomics (unlocks, treasury runway), On-Chain Analytics
  (flows, cohorts, whale reads), Alternative Data (sentiment pipeline,
  signal decay, leakage guards), Macro Regime & Cross-Asset Allocation —
  later upgraded with interactive shock sliders, horizon selectors, local
  charts, and collapsible formula panels.

### Derivatives / volatility / futures / real assets / microstructure labs (≈v4.8–v4.41)

- Options Lab (Black-Scholes, Greeks, IV solver, payoff builder, CRR trees,
  Monte Carlo incl. Asian/barrier, vol surface + SVI research fit, Heston);
  Volatility Surface & Variance Swap Lab (explicitly not the VIX
  methodology); Futures & Commodities Lab (cost-of-carry, curve shapes,
  roll yield); Real Estate + MBS Prepayment (CPR/SMM/PSA, WAL, duration);
  Credit Risk (Merton, hazard, simplified CDS); Yield Curve & Short Rate
  (Vasicek/CIR); FX (parity, carry, Garman-Kohlhagen); Event Lab (event
  studies); Market Microstructure & Execution (order-book analytics, TCA
  attribution summing to shortfall by construction, order-flow toxicity
  approximations); Global Markets Globe data layer with opt-in fail-closed
  adapters; Cross-Sectional Scanner; local LaTeX formula rendering
  everywhere.

### Methodology & testing (throughout)

- AFML Methodology Lab (CUSUM events, triple-barrier labels, purged K-fold +
  embargo, sequential bootstrap, fractional differentiation — synthetic
  data, no fitted models, no performance claims); platform-wide testing
  discipline: ~2,900 deterministic backend tests with no live-provider
  dependency, strict Pydantic v2 schemas with finiteness guarantees, wording
  contracts as tests, GitHub Actions CI (backend tests + frontend build).

---

## v4.7.0 — Showcase Candidate — 2026-06-13

This candidate packages QuantLab as a portfolio-ready local research showcase:
the core backtesting/research stack is stable, the Trust Layer is visible in
results and reports, and the Content Engine explains strategies, papers, and
failure modes without pretending planned work is already built.

### Added

**Trust Layer v1**
- Data-quality diagnostics, benchmark analytics/visualization, reproducible
  SHA-256 config hashes, Robustness Lab bootstrap diagnostics, and Stability
  Lab SMA parameter-sensitivity heatmaps.
- Report/export integration for trust diagnostics and caveats, so saved and
  downloaded research remains auditable.

**Content Engine v1**
- Strategy Library pages for live strategies plus honest planned/research
  catalog entries with no run buttons until the backend exists.
- Paper Replications pages with clearly labelled inspired demos, not full
  academic replications.
- Quant Disasters case studies that connect backtest limitations to real risk
  mechanisms and explicit "cannot model yet" lists.
- Command Center content hub, global-search access, and release screenshot/demo
  plans for the showcase flow.

### Changed

- README, release checklist, demo script, screenshot plan, limitations, and
  known-issues docs refreshed for v4.7 showcase readiness.
- Command Palette search now opens all existing educational registry pages
  (including planned Strategy Library / Paper Replication entries) while keeping
  runnable commands limited to implemented strategies and safe demo presets.
- Test-count references updated to the current 1,060+ backend tests across 53
  files.

### Limitations

- Still **research only**: no live trading, broker connection, account system,
  cloud sync, billing, or AI copilot.
- yfinance/CSV daily data only; no survivorship-bias-free institutional data,
  intraday/tick data, or live feeds.
- Cost modelling is static bps/commission/slippage/spread; there is no
  size-dependent market-impact, partial-fill, order-book, borrow, margin, or tax
  simulator.
- Browser print-to-PDF remains the PDF export path; embedded chart images in
  reports are future work.

---

## v4.0.0 — Local-First Quant Research Terminal — 2026-06-08

The first public, portfolio-ready release: a full local-first quantitative
research platform (FastAPI backend · Next.js frontend · local SQLite), with a
neon "quant terminal" UI, single-asset and portfolio analytics, a no-code
strategy builder, branded reporting, and a polished command-center experience.

### Added

**Product experience**
- **Command Center** — local-first home dashboard (quick actions, recent saved work, system status, feature map).
- **Guided Demo Mode** — onboarding card + prefilled demo presets that never auto-run, plus a local quick-start checklist.
- **Command Palette / Global Search** — `Ctrl/Cmd + K` to navigate and search commands plus real saved backtests, reports, and templates.
- **Neon theme & neon chart system** — CSS-variable accent theme (six accents incl. a Risk mode) and accent-aware glowing equity/drawdown/heatmap charts.
- **Toast notifications**, an app-level **error boundary**, and consistent **loading / empty / offline** state primitives.
- **App Settings** — local (browser) defaults for capital, cost, benchmark, date range, accent theme, and report template.

**Strategy research**
- **Single-asset backtesting** with a vectorised, lookahead-bias-free engine (one-day signal shift).
- Strategies: **SMA Crossover, RSI Mean Reversion, Bollinger Band, Time-Series Momentum, Volatility Breakout, Pairs Trading**.
- **Long / short / long-short** direction modes (SMA, Momentum, Volatility Breakout) with diagnostics and a short-selling warning.
- **Strategy Comparison** and **Research tools** — Parameter Sweep, Train/Test validation, Walk-Forward validation.
- **CSV Upload Backtesting** — run strategies on your own daily price CSV.

**Custom strategy lab**
- **Custom Strategy Builder** — no-code entry/exit rule builder over whitelisted indicators (no `eval`).
- **Saved strategy templates** with JSON **import / export**, and a built-in **Strategy Template Gallery**.

**Portfolio lab**
- **Portfolio Backtesting** (equal-weight, turnover-based rebalancing costs).
- **Portfolio Optimization** (min-volatility / max-Sharpe, long-only) and **Walk-Forward Portfolio Optimization** (out-of-sample).
- **Efficient Frontier**, **Risk Dashboard**, **Stress Testing**, and **Factor Analysis**.

**Reporting & persistence**
- **Markdown** and **PDF / print** report export with four **branded report templates**.
- **Saved Reports Gallery** and **Saved Backtests**, persisted in local SQLite.

**Platform**
- **Docker / Docker Compose** one-command stack and **GitHub Actions CI** (backend tests + frontend build).

### Changed
- **README and docs refreshed** — local-first positioning, categorized feature overview, screenshot gallery, and release/QA docs.
- **UI upgraded** to the neon quant-terminal style across every workspace.
- **Default parameters calibrated** for demo usability (clearly not tuned for returns, and not recommendations).
- **Offline UX improved** — friendly "Backend offline" panels with Retry instead of raw HTTP errors, de-duplicated offline notifications.

### Limitations
- **Research only — not investment advice**; **no live trading** and **no broker integration**.
- **yfinance data limitations** (no SLA, possible gaps/anomalies; not survivorship-bias-free; daily only).
- **Local SQLite only** — single-user, no authentication, no cloud sync.
- **Short selling is simplified** — no borrow fees, margin, liquidation, or funding modelled (`|position| ≤ 1`).
- **Portfolio optimization is historical / in-sample** and can overfit; it does not forecast future performance.
- **PDF export** is browser print-to-PDF (text + tables; embedded chart images are future work).

See [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) and [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for the full, categorized list.

---

_Earlier development progressed through phases 0–11 (backend MVP → strategies →
research tools → portfolio lab → reporting → settings/theme → long/short →
Command Center / palette / search → toasts, error boundary, state polish →
release prep). See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full history._
