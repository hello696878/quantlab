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

- **Backtest Overfitting, PBO & Multiple Testing Diagnostics Lab v1**
  (v4.71 series): a local-first selection-bias diagnostics lab — CSCV over
  a strictly-aligned bounded candidate universe with the Probability of
  Backtest Overfitting under a fixed documented rank/logit convention
  (rank 1 = worst OOS, ω = rank/(N+1), λ = ln(ω/(1−ω)), PBO = fraction of
  valid splits with λ < 0, deterministic tie handling, all C(S,S/2)
  combinations with a hard 924 cap and no sampling); λ-distribution,
  IS↔OOS degradation and selection-frequency diagnostics in neutral
  wording; Probabilistic and Deflated Sharpe Ratios with explicit
  conventions (per-period ddof=1 Sharpe, population skew, NON-excess
  kurtosis, expected-maximum-Sharpe benchmark, explicit raw/manual/
  dependence-adjusted trial-count policies, honest one-trial and
  zero-variance handling) plus Minimum Track Record Length; Bonferroni /
  Holm / Benjamini–Hochberg corrections with the FWER-vs-FDR distinction,
  declared-only p-value provenance and stable tie ordering; bounded
  candidate-dependence diagnostics with warning-free constant detection
  and an approximate effective trial count; universe/configuration/result
  fingerprints; four new SQLite tables; scope-transactional baselines;
  comparison with explicit comparability warnings; JSON export; a 4-run
  deterministic demo; the **Overfitting Diagnostics** view (λ histogram
  with labelled zero line, Sharpe assumptions on display, multiple-testing
  table); 26 backend tests verified by a 5-agent adversarial
  reference-check pass (303 checks; 3 findings fixed); a 14-test
  Playwright spec; five docs. Every value is a research statistic under
  stated assumptions — never profitability, robustness, safety, or a
  recommendation.

## Grouped release areas — v4.69/v4.70 (research-diagnostics series)

### Feature importance, stability & drift diagnostics lab (v4.70)

- **Feature Importance, Stability & Drift Diagnostics Lab v1** (v4.70
  series): a local-first feature-diagnostics lab — held-out permutation
  importance as the primary method (deterministic in-process estimators:
  L2 logistic, closed-form ridge, bounded CART — no scikit-learn or SHAP
  added, never pickle/joblib), fitted per linked Model Validation split on
  train members only and evaluated on held-out test members
  (leakage-clean runs required; membership mismatches and leakage-failed
  links fail honestly), with declared splits recorded as declarations and
  no-split runs disclosed as not held-out; direction-normalized importance
  (positive = permuting worsened the held-out metric) with bounded
  deterministic repeats and honest negative values; model-native impurity
  and standardized-coefficient references with fixed caveats (drop-column
  omitted, documented); rank stability (Spearman/Kendall, top-k overlap,
  transparent score + thresholds); deterministic correlated-feature groups
  (no automatic removal); distribution drift with explicit
  reference/comparison sets, PSI (explicit bins, ε=1e-6) + KS + documented
  configurable thresholds; importance drift with neutral wording;
  target-leakage rejection; config/result/baseline fingerprints; six new
  SQLite tables; scope-transactional held-out-only baselines; sample-free
  JSON export; a 4-run deterministic demo; the **Feature Diagnostics**
  view (importance bars with zero line + negative-in-color, stability
  matrix, correlation groups, drift tables); 37 backend tests; a 15-test
  Playwright spec; four docs. Importance is measured sensitivity — never
  causality, profitability, or a recommendation.

### Meta-labeling, calibration & threshold lab (v4.69 series — untagged; included in the v4.70 tag history)

- **Meta-Labeling, Probability Calibration & Decision Threshold Lab v1**
  (v4.69 series): a local-first secondary-signal lab — meta-labels whether the
  primary side (−1/0/1; side 0 abstains, never a failed signal) was correct
  under a documented strict-inequality outcome rule; dependency-light Platt
  sigmoid and isotonic (PAV) calibration fitted on training data only, with
  **verified out-of-fold** calibration per linked Model Validation split
  memberships (leakage-clean runs only; membership mismatches fail honestly)
  and declared/not-out-of-fold statuses disclosed rather than trusted;
  Brier / log loss / ROC AUC / PR AUC / reliability bins / ECE / MCE with
  undefined metrics null+reason; a bounded neutral threshold grid (coverage
  prominent, optional abstention band, no "optimal" selection ever); saved
  research threshold policies with per-run baselines (rejected on failed or
  not-OOF runs); deterministic configuration/result/policy fingerprints;
  four new SQLite tables; idempotent Experiment Registry linking and Dataset
  Lineage links with invalidation warnings; a new **Meta-Labeling Lab** view
  (reliability + threshold SVG charts with accessible table fallbacks, dark
  `ql-input` controls); a 7-run demo with policies; a 10-test Playwright
  spec; 28 backend tests; and three docs (`META_LABELING_LAB.md`,
  `PROBABILITY_CALIBRATION_POLICY.md`, `META_LABELING_RUNBOOK.md`). Also
  fixed a fingerprint-row overflow in the Phase 50/51 detail views.
  Meta-label 1 means the research condition was met — never profitability.

## Grouped release areas — v4.8 through v4.68 (post-showcase series)

### Purged CV, embargo & CPCV model validation lab (v4.68)

- Local-first validation lab: temporal-event samples with closed information
  intervals, standard K-fold as an explicitly-warned leakage reference,
  boundary-purged walk-forward, purged K-fold with per-id overlap reasons,
  CPCV bounded at 100 combinations, duration/fraction embargo per disjoint
  test block, a from-scratch leakage audit (any remaining overlap or empty
  training set marks the split invalid), dependency-light neutral metrics,
  deterministic fingerprints, leakage-clean-only baselines, the Model
  Validation Lab frontend with a temporal split timeline, an 11-test
  Playwright spec, and three docs.


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

The tags between v4.8.0 and v4.68.0 (local milestone tags; full per-phase
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
