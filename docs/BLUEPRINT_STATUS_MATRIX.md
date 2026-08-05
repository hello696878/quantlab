# QuantLab — Blueprint Status Matrix (Phase 62.0)

Evidence-audited status of every Master Blueprint phase-order area and
every model category. **Nothing here is marked `built` because a roadmap
entry says so** — each row was checked against actual files, and the
evidence columns give repo-relative paths you can open.

Companion documents:
[`BLUEPRINT_RECONCILIATION_REPORT.md`](BLUEPRINT_RECONCILIATION_REPORT.md)
(gaps, stale docs, tag audit) ·
[`FORWARD_ROADMAP_PHASES_63_70.md`](FORWARD_ROADMAP_PHASES_63_70.md) ·
[`MASTER_BLUEPRINT_V3.md`](MASTER_BLUEPRINT_V3.md) (internal direction) ·
[`ROADMAP.md`](ROADMAP.md) (per-phase log).

> Positioning, unchanged: QuantLab is a **local-first, deterministic,
> educational** research platform. Not investment advice, no live
> trading, no production trading/risk/compliance certification.

## 1. Status vocabulary

| Status | Meaning |
|---|---|
| `built` | A usable implemented capability exists in code, is routed into the product where applicable, and has tests or explicit verification evidence. |
| `built_partial` | A meaningful v1 exists, but important parts of the blueprint scope remain unimplemented. |
| `planned` | Selected for a defined future phase (see the forward roadmap). |
| `research` | Needs design, dependency, feasibility, data, licensing or mathematical work first. |
| `deferred` | Intentionally postponed with no selected implementation phase. |
| `deliberate_non_goal` | Prohibited by the platform positioning (e.g. real-money order execution). |

A **workspace is not a model**: ~40 interactive workspaces exist, but a
single workspace (for example the Options Lab) contains several models,
while other workspaces contain none (Demo Center, QA Command Center).
Neither number is a percentage of the aspirational ~100-model catalog,
and this document deliberately publishes **no such percentage** because
the denominator and the counting rule for "one model" are not defined
anywhere in the repository.

## 2. Status counts

| Status | Phase-order areas (20) | Model categories (12) |
|---|---|---|
| `built` | 7 | 2 |
| `built_partial` | 9 | 8 |
| `planned` | 1 | 0 |
| `research` | 1 | 1 |
| `deferred` | 2 | 0 |
| `deliberate_non_goal` | 0 | 1 (within category 10) |

Every item below carries exactly one current status.

---

## 3. Blueprint phase-order areas (1–20)

### 1. Benchmark visualization — `built`

| Field | Value |
|---|---|
| Implemented scope | Active return, tracking error, information ratio, beta, alpha and correlation on inner-join-aligned daily returns, in three modes (`buy_and_hold_same_asset`, `custom_ticker`, `none`). Non-computable cases return null plus a warning rather than NaN/inf and never alter strategy results. UI: benchmark card, excess-return chart, equity/drawdown overlays, also on saved runs. |
| Missing scope | Risk-free rate fixed at zero (so "alpha" is a CAPM-style intercept); no multi-benchmark blends, rolling alpha/beta series, factor attribution of active return, or significance intervals. |
| Backend evidence | `backend/app/benchmark.py`, `backend/app/schemas.py` (BenchmarkConfig/BenchmarkAnalytics/ActiveMetrics), wiring in `backend/app/main.py` |
| Frontend evidence | `frontend/src/components/BenchmarkComparisonCard.tsx`, `frontend/src/lib/benchmarkCharts.ts`, `frontend/src/components/ExcessReturnChart.tsx` |
| Test evidence | `backend/tests/test_benchmark.py` (24 tests) |
| Docs evidence | `docs/BENCHMARK_AND_ACTIVE_RETURN_POLICY.md`, `docs/LIMITATIONS.md` |
| Latest relevant phase | 12.6.1 |
| Dependencies | Core backtest engine; provider seam |
| Next action | None required; optional v2 = rolling alpha/beta + risk-free input |
| Public-facing | Yes · **Release-blocking:** No |

### 2. Reproducible backtest permalink / config hash — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | Canonical-JSON SHA-256 over result-changing inputs with documented normalization (defaults collapsed, keys sorted, tickers uppercased, outputs excluded); CSV content SHA-256 folded in; hashes on single-asset and Strategy Comparison responses; UI card copies short hash, full hash and canonical config JSON. |
| Missing scope | **No replay-by-hash**: no endpoint resolving a hash to a config or result, no URL parameter rehydrating the form, and `config_hash` is not persisted on saved backtests. No environment/artifact identity, no dataset-version pinning in the hash. |
| Backend evidence | `backend/app/reproducibility.py`, `backend/app/main.py` (single-asset + comparison + CSV paths), `backend/app/batch_experiments/runner.py` |
| Frontend evidence | `frontend/src/components/ReproducibilityCard.tsx` |
| Test evidence | `backend/tests/test_reproducibility.py` (17 tests) |
| Docs evidence | `docs/EXPERIMENT_REPRODUCIBILITY_POLICY.md` |
| Latest relevant phase | 12.7 |
| Dependencies | Dataset Lineage (49.0) for dataset versions; experiment store hashes |
| Next action | **Phase 65** — replay by hash + environment manifest |
| Public-facing | Yes · **Release-blocking:** No |

### 3. Robustness / Stability — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | Seeded block-bootstrap Monte Carlo over realized daily returns with distributions of final return, max drawdown and Sharpe (never mutates the core backtest); SMA fast×slow parameter-sensitivity grid re-run through the identical pipeline with a metric-tabbed heatmap. Separately, Phase 53's Overfitting lab implements PBO/CSCV, deflated Sharpe and multiple-testing corrections. |
| Missing scope | Inside *this* lab: deflated Sharpe is null in v1, PBO is not implemented, the sweep supports only SMA, and the A–F grade is heuristic. No stationary/circular bootstrap选择, no cross-lab bridge that feeds Robustness output into the Overfitting lab. |
| Backend evidence | `backend/app/robustness.py`, `backend/app/sensitivity.py`; separately `backend/app/overfitting_diagnostics/` |
| Frontend evidence | `frontend/src/components/RobustnessLabCard.tsx`, `frontend/src/components/StabilityLabCard.tsx`, `frontend/src/components/OverfittingDiagnosticsPanel.tsx` |
| Test evidence | `backend/tests/test_robustness.py` (18), `backend/tests/test_sensitivity.py` (20), `backend/tests/test_overfitting_diagnostics.py` |
| Docs evidence | `docs/LIMITATIONS.md` ("a bootstrap, not a proof"; "cannot bless them") |
| Latest relevant phase | 12.8 / 12.9; Phase 53 for PBO |
| Dependencies | Core engine; Phase 53 utilities |
| Next action | Optional: route Robustness/Stability outputs into the Phase 53 lab |
| Public-facing | Yes · **Release-blocking:** No |

### 4. Strategy Library — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | Typed registry of 14 model entries (7 `live` with a `strategyId` linking into Backtest Studio) with hypothesis, signal logic, parameters, strengths, failure modes and cost notes; index + detail panel with deep links and cross-links into papers/disasters. |
| Missing scope | 7 of 14 entries are documentation stubs; blueprint scale implies many more implemented models. **No automated test at all** for the registry or panel (no slug-uniqueness or registry-vs-route drift guard). |
| Backend evidence | `backend/app/strategies.py`, `backend/app/backtest.py`, `backend/app/strategy_gallery.py` |
| Frontend evidence | `frontend/src/lib/modelRegistry.ts` (568 lines, 14 entries), `frontend/src/components/StrategyLibraryPanel.tsx` |
| Test evidence | Indirect only: `backend/tests/test_backtest.py` (21), `backend/tests/test_bb_strategy.py` (27). No registry test. |
| Docs evidence | `docs/ROADMAP.md` (Phase 13.0), `docs/PROJECT_OVERVIEW.md` |
| Latest relevant phase | 13.0 |
| Dependencies | Core engine |
| Next action | **Phase 66** — registry drift guards + component tests |
| Public-facing | Yes · **Release-blocking:** No |

### 5. Paper Replication Series — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | 9 classic-paper entries with research question, original method, "what QuantLab can do today", data requirements, limitations and an explicit `replicationLevel`; 4 live, 3 carrying a run-preset that preselects a strategy/ticker (never auto-running). |
| Missing scope | No entry reaches `simplified_replication` or `full_replication` — nothing reproduces a paper's universe, rebalancing or reported results (needs cross-sectional data + formation/holding portfolio construction + factor benchmarks). 5 of 9 entries are planned text. No tests. |
| Backend evidence | Routes into `backend/app/backtest.py` / `strategies.py` presets |
| Frontend evidence | `frontend/src/lib/paperRegistry.ts` (367 lines), `frontend/src/components/PaperReplicationsPanel.tsx` |
| Test evidence | None dedicated (no e2e spec, no unit test); indirect backend strategy tests only |
| Docs evidence | `docs/ROADMAP.md` (Phase 13.1), `README.md` |
| Latest relevant phase | 13.1 |
| Dependencies | Cross-sectional universe data (Phase 67/68 territory) |
| Next action | Keep labelled "inspired demo"; revisit after real-data adapters |
| Public-facing | Yes · **Release-blocking:** No |

### 6. Options Pricing Engine — `built`

| Field | Value |
|---|---|
| Implemented scope | European Black–Scholes with greeks + bisection IV solver + multi-leg payoff; CRR binomial lattice with American exercise, early-exercise diagnostics and BS convergence; GBM Monte Carlo (European/Asian/barrier) with seed, standard error and CI; Heston stochastic-vol Monte Carlo; IV surface with SVI research fit. All routed into a tabbed Options Lab. |
| Missing scope | No option-chain ingestion or vendor connectivity, no discrete dividends/corporate actions, no transaction costs or bid-ask modelling; the SVI fit is not constrained arbitrage-free; no surface calibration service; American pricing is lattice-only. |
| Backend evidence | `backend/app/options.py`, `backend/app/options_tree.py`, `backend/app/options_monte_carlo.py`, `backend/app/options_heston.py`, `backend/app/options_surface.py` |
| Frontend evidence | `frontend/src/components/OptionsLabPanel.tsx` (2451 lines, 8 tabs) |
| Test evidence | `backend/tests/test_options.py` (29), `backend/tests/test_options_tree.py` (32), plus MC/Heston/surface suites |
| Docs evidence | `README.md`, `docs/LIMITATIONS.md` |
| Latest relevant phase | 14.0–14.4 |
| Dependencies | None |
| Next action | None required for v1 |
| Public-facing | Yes · **Release-blocking:** No |

### 7. Volatility Lab — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | IV inversion over a supplied quote chain (reusing the Options BS/bisection code), smile, put-spread skew, ATM term structure, maturity×strike surface summary, realized-vs-implied spread, simplified variance-swap fair strike, position vega exposure and volatility scenarios; IV failures return null with a note. |
| Missing scope | The surface is a table/grid, not a fitted/interpolated surface object; no SVI/SABR calibration inside the package, no arbitrage-free constraints, no term-structure interpolation, no chain source, no VIX-style replication. **No lab documentation file and no e2e spec.** |
| Backend evidence | `backend/app/volatility/service.py`, `models.py`, `sample.py`, `backend/app/volatility_routes.py` |
| Frontend evidence | `frontend/src/components/VolatilityLabPanel.tsx` (470 lines) |
| Test evidence | `backend/tests/test_volatility.py` (21) |
| Docs evidence | Module docstrings only — no `docs/` file for this lab |
| Latest relevant phase | 21.x |
| Dependencies | Options engine |
| Next action | Add a lab doc; consider calibration in a later phase |
| Public-facing | Yes · **Release-blocking:** No |

### 8. Event-Driven & Arbitrage — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | Abnormal-return event studies with three baselines (market-adjusted, mean-adjusted, OLS market model), estimation-window validation, per-day AR, CAR and multi-event CAAR; a simplified merger-arb expected-value calculator (spread, breakeven probability, annualized figures); four endpoints and a lab panel. |
| Missing scope | No corporate-action/filing feed — event dates are typed by hand and are not point-in-time verified; no cross-sectional significance tests (BMP/Patell/Corrado), no confounding-event control; no convertible-arb or index add/remove engines. No e2e spec, no dedicated lab doc. |
| Backend evidence | `backend/app/event_study.py` (466 lines), routes in `backend/app/main.py` |
| Frontend evidence | `frontend/src/components/EventLabPanel.tsx` (742 lines) |
| Test evidence | `backend/tests/test_event_study.py` (34) |
| Docs evidence | `docs/LIMITATIONS.md`, `docs/PROJECT_OVERVIEW.md` |
| Latest relevant phase | 15.0 |
| Dependencies | Point-in-time event data (not present) |
| Next action | Keep as calculator; a real event database is out of current scope |
| Public-facing | Yes · **Release-blocking:** No |

### 9. Rates / FX / Credit — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | Yield curve (zero rates, discount factors, forwards, two interpolations, three compounding conventions, parallel/steepener/flattener/butterfly shocks, bond price + Macaulay/modified duration, convexity, DV01); Vasicek and CIR risk-neutral Monte Carlo with full-truncation Euler plus analytic affine ZCB prices and the Feller condition; FX (CIP forward, carry, PPP deviation, exposure + stress, Garman–Kohlhagen); Credit (Merton distance-to-default, reduced-form hazard/survival, simplified CDS par spread, risky bond). |
| Missing scope | No market data or calibration: no live rates/FX/CDS feed, no bootstrapping from deposits/futures/swaps, no Nelson-Siegel/Svensson fitting, no Hull-White or multi-factor models, no CVA/DVA, no rating transitions, no credit portfolio model. |
| Backend evidence | `backend/app/yield_curve.py` (474), `backend/app/short_rates.py` (564), `backend/app/fx.py` (474), `backend/app/credit.py` |
| Frontend evidence | `frontend/src/components/YieldCurveLabPanel.tsx` (1004), `FxLabPanel.tsx` (765), `CreditRiskLabPanel.tsx` |
| Test evidence | `backend/tests/test_yield_curve.py` (40), `test_short_rates.py` (34), `test_fx.py`, `test_credit.py` |
| Docs evidence | `docs/LIMITATIONS.md`, `docs/PROJECT_OVERVIEW.md` |
| Latest relevant phase | 16.0–16.2, 17.0 |
| Dependencies | Real curve data for calibration (absent) |
| Next action | None near-term; calibration needs a data contract first |
| Public-facing | Yes · **Release-blocking:** No |

### 10. Real Estate — `built_partial` *(blueprint says "research" — stale)*

| Field | Value |
|---|---|
| Implemented scope | Income-property analytics: EGI/NOI, in-place and exit cap-rate valuation, mortgage amortization, LTV, DSCR, levered cash flow with a bisection IRR (null when cash flows don't bracket), equity multiple, six stress scenarios, REIT NAV discount/premium. MBS: CPR↔SMM↔PSA conversions, prepayment-projected cash flows, WAL, duration/convexity approximations. |
| Missing scope | No OAS, no lattice/Monte Carlo term-structure model; duration/convexity hold cash flows fixed rather than re-running prepayments under shocks; no burnout/turnover/refi-incentive behaviour, no servicing/loss modelling, no CMO waterfalls. |
| Backend evidence | `backend/app/real_estate/service.py`, `backend/app/real_estate/mbs.py`, `models.py` |
| Frontend evidence | `frontend/src/components/RealEstateLabPanel.tsx`, `frontend/src/components/real_estate/MbsSection.tsx` |
| Test evidence | `backend/tests/test_real_estate.py` (28), `backend/tests/test_mbs.py` (22) |
| Docs evidence | `docs/PROJECT_OVERVIEW.md`, `docs/LIMITATIONS.md` |
| Latest relevant phase | 22.0 / 23.0 |
| Dependencies | None |
| Next action | Update the blueprint label (done in this phase) |
| Public-facing | Yes · **Release-blocking:** No |

### 11. Microstructure & educational HFT — `built_partial` *(blueprint says "future" — stale)*

| Field | Value |
|---|---|
| Implemented scope | Order-book summary (best bid/ask, mid, spread bps, top-of-book and 5-level depth imbalance, microprice), trade-tape VWAP/TWAP/signed imbalance, execution analytics (implementation shortfall, slippage, participation, square-root impact), a four-schedule comparison, eight liquidity stress scenarios, and TCA attribution. |
| Missing scope | No order-by-order matching engine, no event-driven/agent-based simulator, no queue-position or latency model, no live feed, and no order submission (the last is a permanent non-goal). The "HFT" surface is analytic formulas over a static tape. |
| Backend evidence | `backend/app/microstructure/service.py`, `models.py` |
| Frontend evidence | `frontend/src/components/MicrostructureLabPanel.tsx`, `frontend/src/lib/microstructure.ts` |
| Test evidence | `backend/tests/test_microstructure.py` (43) |
| Docs evidence | `docs/PROJECT_OVERVIEW.md`, `docs/LIMITATIONS.md` |
| Latest relevant phase | 24.x |
| Dependencies | None (simulation depth would need a new engine) |
| Next action | Update the blueprint label (done in this phase) |
| Public-facing | Yes · **Release-blocking:** No |

### 12. Cross-Sectional Scanner — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | Universe-level engine over a deterministic synthetic panel: cross-sectional momentum/reversal scoring, ranking at daily/weekly/monthly rebalances, equal-weight long/short baskets sized to ±gross/2, weights shifted one period before P&L, turnover-based costs, explicit input validation, capped previews. |
| Missing scope | Only dollar-neutral weighting exists (`neutralize.py` has one function); no sector-neutral, beta-neutral or vol-targeted weighting, no cross-sectional residualisation, no real universe, no validation of the scanner's own selection (no purged CV / PBO link). No e2e spec. |
| Backend evidence | `backend/app/scanner/cross_sectional.py` (373), `backend/app/scanner/neutralize.py` (52), `backend/app/scanner/sample_data.py` |
| Frontend evidence | `frontend/src/components/ScannerLabPanel.tsx` (373) |
| Test evidence | `backend/tests/test_scanner.py` (36) |
| Docs evidence | `docs/LIMITATIONS.md` (dollar-neutral only, synthetic universe) |
| Latest relevant phase | 18.0 |
| Dependencies | Phase 59 factor infrastructure for neutralisation; Phase 52/53 for validation |
| Next action | **Phase 68** — neutralisation + scanner validation |
| Public-facing | Yes · **Release-blocking:** No |

### 13. AFML Methodology — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | CUSUM event sampling (fixed and vol-scaled), triple-barrier labeling, sample concurrency + average-uniqueness weights, purged K-fold with embargo and leakage reporting, sequential bootstrap, fractional differentiation with stability diagnostics — pure functions plus demo orchestrators over a seeded synthetic path, in a 7-tab lab. |
| Missing scope | No feature engineering, model fitting or OOS evaluation inside `finml`; CPCV, information-driven bars and meta-labeling are not in this module (CPCV and meta-labeling exist separately in Phases 50/51 — the toolkit and the labs are not unified). No structural-break tests. |
| Backend evidence | `backend/app/finml/` (cusum.py, labeling.py, uniqueness.py, cv.py, bootstrap.py, fracdiff.py, sample_data.py) |
| Frontend evidence | `frontend/src/components/AfmlLabPanel.tsx` (1221) |
| Test evidence | `backend/tests/test_finml.py` (34), `test_finml_cv.py` (29), `test_finml_bootstrap.py` (31) |
| Docs evidence | `docs/LIMITATIONS.md` |
| Latest relevant phase | 19.0–19.3 |
| Dependencies | Phase 50 Model Validation (CPCV), Phase 51 Meta-Labeling |
| Next action | **Phase 64** unifies the ML lifecycle across these islands |
| Public-facing | Yes · **Release-blocking:** No |

### 14. Global Markets Globe — `built`

| Field | Value |
|---|---|
| Implemented scope | 15 static market dossiers over three endpoints, rendered by a hand-written canvas-2D orthographic globe (projection, back-face culling, dot-matrix land mask, graticule, starfield, pulsing markers, great-circle arcs, drag/auto-rotate, tooltips, graceful fallback). Three optional enrichment layers behind env flags (FRED macro, delayed index/FX quotes), disabled by default and failing closed to static data. |
| Missing scope | No live news provider (scaffold reports `news_unavailable`); FRED coverage is US-only; no streaming quotes, no per-market history, no GeoJSON geometry. **No browser E2E spec for the globe UI.** |
| Backend evidence | `backend/app/globe/` (sample_markets, service, models, adapters, news, quotes), `backend/app/globe_routes.py` |
| Frontend evidence | `frontend/src/components/globe/DataGlobe.tsx` (614), `frontend/src/components/GlobeLabPanel.tsx` (879) |
| Test evidence | `backend/tests/test_globe.py` (76 — the largest audited suite) |
| Docs evidence | `docs/GLOBE_DATA.md` |
| Latest relevant phase | 20.0 + data-layer phases |
| Dependencies | Optional providers only |
| Next action | Optional: add a globe e2e spec in Phase 66 |
| Public-facing | Yes · **Release-blocking:** No |

### 15. Portfolio Studio and Strategy Ensemble Builder — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | **Portfolio Studio side is built:** multi-asset alignment, equal-weight/periodic-rebalance backtest, mean-variance optimization (equal-weight/min-vol/max-Sharpe), walk-forward re-optimization, random portfolios + efficient frontier, correlation/vol risk dashboard, scenario stress, factor analysis; plus the Phase 56–58 Portfolio Diagnostics / Stress / Attribution labs (construction, risk budgeting, constraints, scenario shocks, drawdown attribution, Brinson effects, active risk). |
| Missing scope | **The Strategy Ensemble Builder does not exist.** Phase 61's Signal Ensemble combines signal VALUES, not strategy RETURN STREAMS: no strategy return-stream alignment, no capital/risk allocation across strategies, no strategy-level turnover/rebalancing, no drawdown/tail overlap, no walk-forward ensemble policy, no frozen held-out combination, no portfolio constraints on an ensemble, no strategy contribution attribution. |
| Backend evidence | `backend/app/portfolio.py` (1219), `backend/app/portfolio_risk/`, `backend/app/portfolio_diagnostics/`, `portfolio_stress/`, `portfolio_attribution/`; contrast `backend/app/signal_ensemble/` |
| Frontend evidence | `frontend/src/components/PortfolioRiskLabPanel.tsx` (1235), `PortfolioBacktestPanel.tsx`, `PortfolioDiagnosticsPanel.tsx`, `PortfolioStressPanel.tsx`, `PortfolioAttributionPanel.tsx`, `SignalEnsemblePanel.tsx` |
| Test evidence | `backend/tests/test_portfolio_risk.py` (61), `test_portfolio.py` (16), `test_portfolio_diagnostics.py`, `test_portfolio_stress.py`, `test_portfolio_attribution.py`, `test_signal_ensemble.py` (71) |
| Docs evidence | `docs/PORTFOLIO_CONSTRUCTION_POLICY.md`, `docs/SIGNAL_ENSEMBLE_DIAGNOSTICS_LAB.md` |
| Latest relevant phase | 56.0–58.0 (portfolio), 61.0 (signal ensemble) |
| Dependencies | Phases 55–61 infrastructure |
| Next action | **Phase 63** — strategy return-stream ensemble diagnostics (selected next phase) |
| Public-facing | Yes · **Release-blocking:** No |

### 16. ML and AI Lab — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | Two disconnected halves both exist. (a) The **local futures ML loop**: 16 trailing-window features with warmup marking and no fill, five label families aligned so a label equals what acting at t+1 earns, three deterministic numeric models (linear/logistic/dummy), train/eval split, metrics and experiment persistence. (b) The **validation/diagnostics chain** (Phases 50–61): purged CV/embargo/CPCV, meta-labeling calibration and thresholds, feature importance/stability/drift, PBO/deflated Sharpe/multiple testing, regime conditioning, cost/capacity, signal decay and ensemble diagnostics. |
| Missing scope | The two halves are **not one lifecycle**: the ML loop is CLI-only with no API route or UI, its runs live in a filesystem `ExperimentStore` while the labs use the SQLite registry, and predictions do not flow automatically into validation/meta-labeling/cost evaluation. Models are linear/logistic only; no calibration inside the loop; no artifact registry with model identity. |
| Backend evidence | `backend/app/features/`, `labels/`, `ml_signal/`, `signals/`, `local_pipeline/`, `experiments/store.py`; and `model_validation/`, `meta_labeling/`, `feature_diagnostics/`, `overfitting_diagnostics/` |
| Frontend evidence | Labs only (`ModelValidationPanel.tsx`, `MetaLabelingPanel.tsx`, `FeatureDiagnosticsPanel.tsx`, …); **no UI for the futures ML loop** |
| Test evidence | `backend/tests/test_ml_signal.py` (80), `test_futures_features.py` (49), `test_local_futures_ml_pipeline.py` (25), plus every Phase 50–61 suite |
| Docs evidence | `docs/AI_QUANT_ARCHITECTURE.md`, `docs/EXPERIMENT_REPRODUCIBILITY_POLICY.md`, `docs/MODEL_VALIDATION_LAB.md` |
| Latest relevant phase | 50.0–61.0 + the local futures track |
| Dependencies | Experiment Registry, Dataset Lineage |
| Next action | **Phase 64** — unified ML lifecycle + model artifact registry |
| Public-facing | Partly (labs yes; ML loop no) · **Release-blocking:** No |

### 17. AI Explainer Copilot — `planned`

| Field | Value |
|---|---|
| Implemented scope | Nothing. No LLM integration, no explanation service, no copilot surface exists in the repository. |
| Missing scope | Everything: an evidence-grounded explanation service constrained to stored run values, provenance for every claim, refusal behaviour, and a strict no-recommendation boundary. |
| Backend evidence | None |
| Frontend evidence | None (in-app formula/education content is static: `frontend/src/components/math/`) |
| Test evidence | None |
| Docs evidence | `docs/MASTER_BLUEPRINT_V3.md` (listed as future) |
| Latest relevant phase | — |
| Dependencies | Phase 65 replay identity (so explanations cite reproducible runs) |
| Next action | **Phase 69** — evidence-grounded explainer (no trade advice, ever) |
| Public-facing | Would be · **Release-blocking:** No |

### 18. 3D Visualization Engine — `research`

| Field | Value |
|---|---|
| Implemented scope | No general 3D engine. The only spatially-projected visual is the canvas-2D orthographic globe (deliberately dependency-free: no WebGL, no Three.js). Surfaces elsewhere (IV surface, sweep heatmaps) are 2-D grids/heatmaps. |
| Missing scope | A GPU rendering path with scene graph, camera, lighting and reusable 3D primitives (vol-surface meshes, sweep landscapes), plus the dependency decision itself (adding Three.js conflicts with the current no-heavy-dependency stance). |
| Backend evidence | n/a |
| Frontend evidence | `frontend/src/components/globe/DataGlobe.tsx` (canvas 2D), `OptionsLabPanel.tsx` SurfaceHeatmap |
| Test evidence | n/a |
| Docs evidence | `docs/MASTER_BLUEPRINT_V3.md` |
| Latest relevant phase | — |
| Dependencies | A dependency-policy decision |
| Next action | Remain `research`; not scheduled in Phases 63–70 |
| Public-facing | Would be · **Release-blocking:** No |

### 19. Dashboard and Content Engine — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | Quant Disasters: 7 case studies with severity/category, failure modes, simplified mechanism, "what a naive backtest would miss", a trust checklist with available true/false flags, "cannot model yet" lists and lessons, cross-linked to models and papers. Dashboard: hero workflows, trust-layer grid, content cards, featured items, health/offline tiles. |
| Missing scope | No disaster case is runnable as a scenario (the registry has no run-preset); a blueprint version would need replayable stress scenarios with historical windows wired into the stress/scenario engines. Content is static frontend data with no backend. Broader content engine (authoring, versioning) absent. |
| Backend evidence | None for disasters (frontend-static); health endpoint consumed by the dashboard |
| Frontend evidence | `frontend/src/lib/disasterRegistry.ts` (399), `frontend/src/components/QuantDisastersPanel.tsx` (302), `HomeDashboard.tsx` |
| Test evidence | `frontend/e2e/responsive.spec.ts` (dashboard geometry), `frontend/e2e/frozen-demo.spec.ts` (header) |
| Docs evidence | `docs/ROADMAP.md` (13.2/13.3), `docs/LIMITATIONS.md` |
| Latest relevant phase | 13.2 / 13.3 |
| Dependencies | Scenario Studio / Stress engines for replayable cases |
| Next action | Optional: link disaster cases to Scenario Studio presets |
| Public-facing | Yes · **Release-blocking:** No |

### 20. Platform and Launch — `built_partial`

| Field | Value |
|---|---|
| Implemented scope | QA Command Center, Demo Center and Data Reliability packages with deterministic registries and analyze endpoints; Release Notes Center, Public Release Candidate, Portfolio Showcase and Developer Onboarding panels; release docs (checklist, notes template, manifest, milestone history); checksum verifier and print-summary scripts; CI (backend tests + frontend build) and a manual `workflow_dispatch` Browser E2E Preflight; a frozen demo baseline with五 screenshots and regression fixtures. |
| Missing scope | Hosted deployment: no authentication, no multi-user isolation (single-user SQLite by design), no backups/migration ops, no monitoring, no secret management beyond env-var docs, no hosting target/HTTPS/reverse proxy, no provider governance for a public instance. |
| Backend evidence | `backend/app/qa_command_center/`, `demo_center/`, `data_reliability/` + their routers |
| Frontend evidence | `ReleaseNotesCenterPanel.tsx`, `PublicReleaseCandidatePanel.tsx`, `PortfolioShowcasePanel.tsx`, `DeveloperOnboardingPanel.tsx`, `QaCommandCenterPanel.tsx` |
| Test evidence | `backend/tests/test_qa_command_center.py` (24), `test_demo_center.py` (23), `test_data_reliability.py`; `frontend/e2e/` (19 spec files) |
| Docs evidence | `docs/DEPLOYMENT_READINESS.md`, `docs/RELEASE_CHECKLIST.md`, `docs/POST_RELEASE_BASELINE_v4.64.md`, `docs/CI_BROWSER_E2E.md` |
| Latest relevant phase | 52.0–58.0 + release phases |
| Dependencies | A hosting decision; auth remains deferred |
| Next action | **Phase 70** — read-only hosted demo + deployment hardening **plan** |
| Public-facing | Yes · **Release-blocking:** Yes for any hosted launch |

---

## 4. Model categories (1–12)

Data-mode key: **DS** deterministic sample · **US** user-supplied ·
**CSV** local CSV · **OPT** optional provider (fail-closed, off by
default).

### 1. Equities — `built_partial`
- **Implemented:** six single-asset strategies (SMA crossover, RSI mean reversion, Bollinger, time-series momentum, volatility breakout, pairs) on a lookahead-safe, cost-aware vectorised engine with long/short modes; Strategy Comparison; sweep/train-test/walk-forward; cross-sectional momentum/reversal scanner.
- **Partial:** the Strategy Library lists 7 further catalog entries as documentation only.
- **Planned:** low-vol, quality, seasonality models (no phase selected → `deferred` in practice).
- **Research:** none blocking. **Excluded:** live order routing (`deliberate_non_goal`).
- **Data mode:** US + CSV + DS. **Validation maturity:** high for the engine (`test_backtest.py` 21, `test_strategies.py` 10, `test_pairs_strategy.py` 30, plus Phases 50–61 diagnostics); no registry test.
- **Remaining dependency:** a real cross-sectional universe for library breadth.

### 2. Options & Volatility — `built`
- **Implemented:** BS + greeks + IV solver + payoffs; CRR tree with American exercise; MC (European/Asian/barrier) with CI; Heston MC; IV surface + SVI research fit; volatility lab (smile/skew/term structure/surface summary, realized-vs-implied, variance-swap approximation, vega exposure, scenarios).
- **Partial:** no arbitrage-free surface, no SABR/local/rough vol, no calibration service.
- **Research:** SABR, local/rough vol. **Excluded:** live chain feeds are absent (not prohibited, just unimplemented).
- **Data mode:** US + DS. **Validation maturity:** high (`test_options.py` 29, `test_options_tree.py` 32, `test_volatility.py` 21, plus MC/Heston/surface suites).
- **Remaining dependency:** an option-chain data contract.

### 3. Event-Driven & Arbitrage — `built_partial`
- **Implemented:** event study (AR/CAR/CAAR, three baselines), simplified merger-arb calculator.
- **Missing:** full merger-arb, convertible arb, index add/remove engines; significance testing; a point-in-time event database.
- **Data mode:** US + DS. **Validation maturity:** medium (`test_event_study.py` 34; no e2e).
- **Remaining dependency:** corporate-action/filing data with point-in-time dates.

### 4. Futures & Commodities — `built_partial` *(blueprint says "research" — stale)*
- **Implemented (educational lab):** cost-of-carry, convenience yield, basis, curve-shape classification, roll yield, calendar spread, margin/leverage, P&L, eight stress scenarios.
- **Implemented (local research pipeline — under-documented until this phase):** YAML instrument registry (ES/NQ/RTY/YM) with CME month codes and expiry math; raw-bar validation with a deterministic content hash; a local-CSV ingest → `RawFuturesStore` → continuous-contract build (ratio-adjusted, documented roll rules with a days-before-expiry fallback); a futures backtest adapter with t+1 execution, roll-seam-safe returns and tick/commission costs; a pipeline chaining features → labels → split → train → evaluate → experiment persistence.
- **Missing:** no session/holiday calendar, no vendor/network source, no intraday bars, no multi-root portfolio backtest, no frontend surface for the research pipeline.
- **Data mode:** CSV + DS (no network path exists). **Validation maturity:** high (`test_instruments_registry.py` 24, `test_store.py` 16, `test_futures_signal_backtest.py` 41, `test_local_futures_ml_pipeline.py` 25, plus continuous-build suites).
- **Remaining dependency:** a point-in-time data contract + calendars → **Phase 67**.

### 5. FX — `built_partial`
- **Implemented:** CIP forward and forward points, cross rates, carry, relative PPP deviation, currency exposure with stress, Garman–Kohlhagen options.
- **Missing:** FX vol surface, carry/momentum strategy backtests, live rates.
- **Data mode:** US + DS. **Validation maturity:** medium-high (`test_fx.py`).
- **Remaining dependency:** FX market data.

### 6. Fixed Income & Rates — `built_partial`
- **Implemented:** zero/discount/forward curve machinery with two interpolations and three compounding conventions, curve shocks, bond pricing with duration/convexity/DV01; Vasicek and CIR simulation plus analytic ZCB prices.
- **Missing:** Hull-White and multi-factor models, swap/OIS bootstrapping, Nelson-Siegel/Svensson fitting, rolldown, calibration.
- **Data mode:** US + DS. **Validation maturity:** high (`test_yield_curve.py` 40, `test_short_rates.py` 34).
- **Remaining dependency:** real curve data.

### 7. Credit — `built_partial`
- **Implemented:** Merton structural model + distance to default, reduced-form hazard/survival, simplified CDS par spread, risky bond pricing.
- **Missing:** CVA/DVA, credit portfolio models, rating transitions, credit spread strategies.
- **Data mode:** US + DS. **Validation maturity:** medium-high (`test_credit.py`).
- **Remaining dependency:** credit market data.

### 8. Crypto — `built_partial`
- **Implemented:** the original crypto-capable backtest heritage (any yfinance ticker incl. crypto pairs, 365-day convention) plus six deterministic labs — crypto derivatives (basis, funding, cash-and-carry, liquidation approximation), DeFi risk (peg, lending health factor), tokenomics (unlocks, treasury), on-chain analytics (flows, whales), alternative data, macro regime.
- **Missing:** every live path — no exchange API, no RPC/explorer, no subgraph/oracle connector, no historical funding/TVL/unlock store.
- **Data mode:** DS + US (analyze bodies); US via yfinance for price backtests. **Validation maturity:** medium-high (`test_crypto_derivatives.py` 29, `test_defi_risk.py` 30, plus four sibling suites).
- **Remaining dependency:** exchange/on-chain data contracts (not scheduled).

### 9. Real Estate — `built_partial` *(blueprint says "research" — stale)*
- See phase-order area 10 above for evidence. **Data mode:** DS + US. **Validation maturity:** medium-high (28 + 22 tests).
- **Remaining dependency:** a term-structure model for OAS-style work.

### 10. Market Microstructure & educational HFT — `built_partial`, with `deliberate_non_goal` components
- **Implemented:** order-book/tape analytics, execution schedules, TCA attribution, order-flow toxicity, liquidity stress (see area 11).
- **Missing:** matching engine, queue/latency models, agent-based simulation.
- **Deliberate non-goal:** real HFT execution, live tick feeds for trading, order submission — prohibited by positioning, not merely unimplemented.
- **Data mode:** DS + US. **Validation maturity:** medium-high (`test_microstructure.py` 43).

### 11. Portfolio & Risk — `built`
- **Implemented:** multi-asset backtest/optimization/frontier/risk dashboard/stress/factor analysis, risk parity and Black–Litterman helpers, capped-simplex projection, rebalancing; plus Phases 56–58 diagnostics labs (construction & risk budgeting, scenario stress & drawdown attribution, performance attribution & active risk).
- **Partial within the category:** the *strategy* ensemble builder (area 15) is absent; factor betas/scenarios in the Risk Lab are hand-specified constants rather than estimated.
- **Data mode:** DS + US. **Validation maturity:** high (`test_portfolio_risk.py` 61, `test_portfolio.py` 16, plus three lab suites and three e2e specs).
- **Remaining dependency:** none for v1; **Phase 63** extends it to strategy streams.

### 12. Machine Learning & AI — `built_partial`
- See phase-order area 16. Two working halves (local futures ML loop; validation/diagnostics chain) that are not one lifecycle.
- **Research-only:** tree ensembles/boosting/neural models (deliberately absent — no heavy ML dependency has been added); AI Explainer (`planned`, Phase 69).
- **Data mode:** CSV + DS. **Validation maturity:** high in parts (`test_ml_signal.py` 80; every Phase 50–61 suite) but no end-to-end lifecycle test.
- **Remaining dependency:** artifact registry + lifecycle wiring → **Phase 64**.

---

## 5. Architecture and data-mode map

### Product workflow layer (all `built`, deterministic sample + user-supplied)

| Workspace | Backend package | Data mode |
|---|---|---|
| Scenario Studio | `backend/app/scenario_studio/` | DS |
| Research Workspace | `backend/app/research_workspace/` | DS + US |
| Experiment Registry | `backend/app/experiment_registry/` | DS + US |
| Dataset Lineage | `backend/app/dataset_registry/` | DS + US (declared metadata) |
| Model Validation | `backend/app/model_validation/` | DS + US |
| Meta-Labeling | `backend/app/meta_labeling/` | DS + US |
| Feature Diagnostics | `backend/app/feature_diagnostics/` | DS + US |
| Overfitting Diagnostics | `backend/app/overfitting_diagnostics/` | DS + US |
| Regime Diagnostics | `backend/app/regime_diagnostics/` | DS + US |
| Cost & Capacity | `backend/app/cost_diagnostics/` | DS + US |
| Portfolio Diagnostics | `backend/app/portfolio_diagnostics/` | DS + US |
| Portfolio Stress | `backend/app/portfolio_stress/` | DS + US |
| Portfolio Attribution | `backend/app/portfolio_attribution/` | DS + US |
| Factor Diagnostics | `backend/app/factor_diagnostics/` | DS + US |
| Signal Decay | `backend/app/signal_decay/` | DS + US |
| Signal Ensemble | `backend/app/signal_ensemble/` | DS + US |
| Data Reliability | `backend/app/data_reliability/` | DS |
| QA Command Center | `backend/app/qa_command_center/` | DS |

### Research engines

| Engine | Status | Data mode | Note |
|---|---|---|---|
| Single-asset backtesting | `built` | US + CSV + DS | lookahead-safe, cost-aware |
| Pairs | `built` | US + DS | KO/PEP frozen fixture |
| Portfolio backtesting | `built` | US + DS | optimization/frontier/stress |
| Cross-sectional scanner | `built_partial` | DS | synthetic universe only |
| AFML methodology | `built_partial` | DS + US | toolkit, not a model |
| Local futures research pipeline | `built_partial` | **CSV + DS** | ingest → continuous → features → labels → model → experiment; CLI-only |
| Options / volatility | `built` / `built_partial` | US + DS | no chain feed |
| Rates / FX / Credit | `built_partial` | US + DS | no calibration data |
| Crypto / DeFi / on-chain | `built_partial` | DS + US | no live chain/exchange path |
| Real estate / MBS | `built_partial` | DS + US | no OAS |
| Microstructure / TCA | `built_partial` | DS + US | analytics over a static tape |

**No layer in this repository is production-ready, and no deterministic
sample work is described as such.** The only network-capable paths are
the default yfinance price provider and two opt-in, fail-closed globe
adapters that are disabled by default.
