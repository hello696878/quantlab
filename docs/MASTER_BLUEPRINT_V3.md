# QuantLab — Master Blueprint v3 (internal direction)

This is the **internal long-term direction** for QuantLab. It is ambitious on
purpose — and explicitly **not** a list of existing features. Anything not
labelled **built** or **built_partial** does not exist yet. Public-facing docs (README, app copy)
must stay credible: no "guaranteed alpha", no "institutional-grade data", no
"production trading system" claims.

**Positioning (fixed):** QuantLab is a **local-first quant research platform**
for education and research — transparent about data quality and backtest
limitations, **not live trading, not investment advice**.

Status labels used below follow the Phase 62 audit vocabulary:
**built** · **built_partial** · **planned** · **research** ·
**deferred** · **deliberate_non_goal**. The evidence behind every label
(actual backend, frontend, test and documentation files) lives in
[`BLUEPRINT_STATUS_MATRIX.md`](BLUEPRINT_STATUS_MATRIX.md); the gap
analysis and tag audit live in
[`BLUEPRINT_RECONCILIATION_REPORT.md`](BLUEPRINT_RECONCILIATION_REPORT.md);
the selected next phases live in
[`FORWARD_ROADMAP_PHASES_63_70.md`](FORWARD_ROADMAP_PHASES_63_70.md).
Labels below were last reconciled against the repository in **Phase 62.0
(2026-08-05)**.

---

## 1. Vision

An interactive platform where a user can explore ~**100 educational quant
models across 12 categories** — an aspiration, not an inventory: the 100
has never been enumerated, no counting rule for "one model" exists, and
**no completion percentage against it may be published** until both are
defined (see `BLUEPRINT_STATUS_MATRIX.md` §3). Today the frontend `View` union
has 57 routed identifiers, of which 6 strategy entries are executable in Backtest Studio.
The vision is to run honest backtests on real historical data,
stress the results (robustness, costs, risk rules, benchmarks), and learn the
math behind each model — with trust features that make every number
reproducible and every limitation explicit.

---

## 2. Completed foundation (built)

- Vectorized single-instrument backtest engine (lookahead-free, costs, trade log)
- **Cross-Sectional Scanner Engine v1** — a *second engine* (18.0): ranks a
  synthetic universe, forms dollar-neutral long/short baskets, and runs a
  lookahead-safe portfolio backtest (reversal + momentum signals)
- **AFML Methodology Layer v1** (19.0–19.3): leakage-aware labeling + validation
  toolkit — CUSUM event sampling, triple-barrier labeling, sample concurrency +
  uniqueness weights (19.0), **purged K-fold + embargo cross-validation** with
  leakage diagnostics (19.1), **sequential bootstrap** (uniqueness-aware sampling)
  (19.2), and **fractional differentiation** (fixed-width preprocessing with
  memory and heuristic stability diagnostics) (19.3), on synthetic data
  (a methodology toolkit, not a model)
- **Global Markets Globe v1** (20.0) — a flagship explore experience: an
  interactive **dependency-free canvas-2D orthographic globe** (no Three.js /
  WebGL) over 15
  static **sample-market dossiers** (equity indices, macro snapshot, currency /
  rates, market structure, sample headlines, QuantLab cross-links). Static
  illustrative data — **not real-time**; optional FRED macro and delayed index/FX
  quote enrichments are implemented but disabled by default and fail closed,
  while news/sentiment and GeoJSON borders remain absent
- Strategies: SMA Crossover, RSI Mean Reversion, Bollinger Band, Time-Series
  Momentum, Volatility Breakout, Pairs Trading; long/short modes
- Strategy Comparison with shared simulation settings
- Simulation engines: cost model, position sizing, risk management,
  annualization convention
- Data provider abstraction (yfinance default, CSV upload) + data-quality
  diagnostics
- Benchmark & active analytics (alpha/beta/correlation/TE/IR) + benchmark
  visualization (equity, drawdown, cumulative excess return)
- Research tools: parameter sweep, train/test, walk-forward
- Portfolio Lab: optimization, walk-forward, efficient frontier, risk
  dashboard, stress testing, factor analysis
- Custom strategy builder + template gallery; saved backtests; report export
  (Markdown/PDF, templates, gallery)
- Settings, neon theme + chart system, Command Center, palette, global search,
  resilient UX states

## 3. Platform trust features

| Feature | Status |
|---|---|
| Data Quality Layer (provider metadata, gap/duplicate/missing diagnostics) | **built** (v1) |
| Honest caveats in every report (costs, overfitting, short selling, data) | **built** |
| Reproducible Backtest Permalinks / config hash | **built_partial** (canonical config hash + CSV content fingerprint; frontend saves preserve it in optional params JSON, but indexed replay + dataset-version identity are absent) |
| Robustness Lab (bootstrap Monte Carlo, deflated Sharpe, sensitivity heatmaps, PBO if feasible) | **built_partial** (this lab has block bootstrap + heuristic grade and SMA sensitivity; deflated Sharpe/PBO are absent here but implemented separately in Phase 53) |
| Quant Disasters Series (what blew up and why — LTCM, Aug 2007, vol short 2018, …) | **built** (v1: 6 case studies — LTCM, 1987, Flash Crash, Volmageddon, Archegos, FTX — educational summaries with honest "cannot model yet" lists; scenario stress simulations remain future) |
| Paper Replication Series (classic papers, honest deviations) | **built_partial** (8 paper pages + 3 `inspired_demo` presets; no entry is a simplified or full replication) |
| AI Explainer Copilot (explains results; never recommends trades) | **research** (Phase 69 adds a deterministic evidence-grounded renderer with no model/provider; an actual AI/copilot mode remains unscheduled research) |
| 3D Visualization Engine (vol surfaces, sweep landscapes) | **research** (no GPU/3D path exists; the globe is a hand-written canvas-2D projection, and surfaces elsewhere are 2-D grids — adding a 3D library is an open dependency decision) |
| Strategy Ensemble Builder | **planned for Phase 64.** Phase 61 built a *Signal* Ensemble Lab (combining signal VALUES). Strategy-level work — return-stream alignment, capital/risk allocation across strategies, strategy turnover, drawdown/tail overlap, walk-forward ensemble policies, frozen held-out combination, ensemble constraints, strategy contribution attribution — does **not** exist yet |

## 4. Model catalog — 12 categories (~100 models long-term)

> **Do not claim all named models are implemented.** Only `built` and
> `built_partial` scope described below exists.

1. **Equities** — **built_partial** (6 executable entries: five single-asset
   strategies plus two-asset pairs); more planned (low-vol, quality, seasonal…)
2. **Options & Volatility** — **built (v1)**: Black–Scholes pricing + Greeks +
   bisection IV solver + multi-leg payoff builder (14.0); CRR **binomial tree**
   + **American exercise** + early-exercise diagnostic + BS convergence (14.1);
   **Monte Carlo** GBM engine — European / Asian / barrier, standard error + CI,
   path preview (14.2); **IV surface** + smile / term structure / skew + **SVI**
   research fit (14.3); **Heston** stochastic-vol Monte Carlo (14.4). Planned:
   Heston calibration to an IV surface, trinomial tree, arbitrage-free surface,
   vol targeting / term structure; later SABR, local / rough vol — research
3. **Event-Driven & Arbitrage** — **built (v1)**: event study (abnormal returns,
   CAR/CAAR) + simplified merger-arb calculator (15.0). Planned: full merger-arb,
   convertible-arb, index add/remove engines
4. **Futures & Commodities** — **built_partial** (no longer "research").
   Two tracks exist: the educational Futures & Commodities Lab
   (cost-of-carry, convenience yield, basis, curve shape, roll yield,
   calendar spread, margin/leverage, stress scenarios) **and** a local
   futures research pipeline — YAML instrument registry (ES/NQ/RTY/YM),
   validated raw bars with content hashes, local-CSV ingest into a
   `RawFuturesStore`, ratio-adjusted continuous-contract building with
   documented roll rules, a t+1 futures backtest adapter, and a
   features → labels → model → experiment pipeline. Missing: session/
   holiday calendars, any vendor/network source, intraday bars,
   multi-root portfolio backtests, and any frontend surface for the
   research pipeline (Phase 67 specifies the real-data contract)
5. **FX** — **built_partial (v1)**: FX Lab — interest rate parity forward, FX carry, PPP
   deviation, currency exposure + stress, Garman-Kohlhagen FX options (16.2).
   Planned: FX vol surface, momentum/carry strategy backtests, live rates
6. **Fixed Income & Rates** — **built_partial (v1)**: Yield Curve Lab — zero rates,
   discount factors, forwards, curve shocks, bond duration/convexity/DV01 (16.0);
   Short Rate Models Lab — Vasicek / CIR simulation + analytic zero-coupon pricing
   (16.1). Planned: Hull-White, swap-curve bootstrapping, rolldown
7. **Credit** — **built_partial (v1)**: Credit Risk Lab — Merton structural model +
   distance to default, reduced-form hazard / survival, simplified CDS par spread,
   risky bond pricing (17.0). Planned: full CVA, credit-portfolio model, rating
   transitions, credit spread strategies
8. **Crypto** — **built_partial**: yfinance-compatible crypto backtests plus
   deterministic crypto-derivatives, DeFi risk, tokenomics, on-chain,
   alternative-data and macro-regime labs; no exchange, RPC, explorer,
   subgraph, oracle or historical funding-data path
9. **Real Estate** — **built_partial** (no longer "research"): income-property
   analytics (EGI/NOI, cap-rate valuation, amortization, LTV/DSCR, levered
   cash flow with a bisection IRR, equity multiple, six stress scenarios,
   REIT NAV discount/premium) plus MBS prepayment analytics (CPR/SMM/PSA,
   projected cash flows, WAL, duration/convexity approximations). Missing:
   OAS, a term-structure model, prepayment behaviour under shocks, CMO
   waterfalls
10. **Market Microstructure & educational HFT** — **built_partial** (no longer
    "future"): order-book summary and depth imbalance, microprice, trade-tape
    VWAP/TWAP/signed imbalance, implementation shortfall and slippage,
    execution-schedule comparison, liquidity stress scenarios, TCA attribution
    and order-flow toxicity — analytic formulas over a static tape. Missing:
    matching engine, queue-position and latency models, agent-based
    simulation. **deliberate_non_goal:** real HFT execution, live tick feeds
    for trading, order submission
11. **Portfolio & Risk** — **built** (multi-asset backtest/optimization/
    frontier/risk dashboard/stress/factor analysis, risk parity and
    Black-Litterman helpers, plus the Phase 56-58 construction, stress and
    attribution labs). The **strategy** ensemble builder remains absent —
    see the trust-features table and Phase 64
12. **Machine Learning & AI** — **built_partial** (no longer "future"): a
    validation/diagnostics chain exists (purged CV + embargo + CPCV,
    meta-labeling calibration and thresholds, feature importance/stability/
    drift, PBO/deflated Sharpe/multiple testing, regime, cost, signal decay
    and ensemble diagnostics) **and** a local futures ML loop exists (16
    trailing features, five label families, linear/logistic/dummy models,
    split/train/evaluate, experiment persistence). They are **not one
    lifecycle**: the ML loop is CLI-only with no API or UI and stores runs
    on the filesystem while the labs use the SQLite registry. No tree
    ensembles, boosting or neural models exist. Phase 65 unifies this

## 5. Phase order (near-term first)

1. ~~Benchmark visualization~~ — **built** (12.6.1)
2. ~~Reproducible Backtest Permalinks / Config Hash~~ — **built_partial** (12.7)
3. ~~Robustness Lab v1~~ — **built_partial** (12.8 + 12.9 Stability Lab heatmap; v2 =
   deflated Sharpe, PBO, multi-strategy sweeps)
4. ~~Strategy Library v1 pages~~ — **built_partial** (13.0: six live strategy pages +
   honest planned catalog; registry in `frontend/src/lib/modelRegistry.ts`)
5. ~~Paper Replication Series v1~~ — **built_partial** (13.1)
6. ~~Options Pricing Engine v1~~ — **built** (14.0 Black–Scholes; 14.1 CRR
   binomial tree + American exercise; 14.2 Monte Carlo GBM + Asian/barrier;
   14.3 IV surface + SVI research fit; 14.4 Heston stochastic volatility)
7. ~~Volatility Lab v1~~ — **built_partial** (21.x: IV inversion over a
   supplied chain, smile, put-spread skew, ATM term structure, surface
   summary grid, realized-vs-implied, simplified variance-swap fair strike,
   vega exposure, scenarios; no fitted/arbitrage-free surface, no SABR
   calibration, no chain source, and no dedicated lab doc yet)
8. ~~Event-Driven & Arbitrage Module~~ — **built_partial (v1)** (15.0: event study + merger-arb calculator)
9. Rates / FX / Credit Module — **built_partial** (16.0: Yield Curve Lab v1;
   16.1: Short Rate Models v1 — Vasicek / CIR; 16.2: FX Lab v1 — IRP / carry /
   PPP / exposure / Garman-Kohlhagen; 17.0: Credit Risk Lab v1 — Merton / hazard /
   CDS / risky bond)
10. ~~Real Estate Module~~ — **built_partial** (22.0/23.0: income-property
    analytics + MBS prepayment; no OAS or term-structure model)
11. ~~Microstructure & HFT Lab (educational simulations)~~ —
    **built_partial** (24.x: order book, execution schedules, TCA
    attribution, order-flow toxicity, liquidity stress; no matching engine,
    queue/latency model or agent simulation; live execution is a permanent
    non-goal)
12. ~~Cross-Sectional Scanner Engine~~ — **built_partial (v1)** (18.0: second engine —
    synthetic universe, dollar-neutral long/short, lookahead-safe portfolio
    backtest; reversal + momentum)
13. ~~AFML Methodology Layer~~ — **built_partial (v1)** (19.0: CUSUM event sampling,
    triple-barrier labeling, sample concurrency + uniqueness weights; 19.1: purged
    K-fold + embargo CV with leakage diagnostics; 19.2: sequential bootstrap;
    19.3: fractional differentiation; meta-labeling and CPCV now exist in
    separate Phase 50/51 packages but are not unified with `finml`)
14. ~~Global Markets Globe~~ — **built (v1)** (20.0: interactive dependency-free
    canvas-2D orthographic globe + 15 static sample-market dossiers — indices, macro, currency /
    rates, market structure, sample headlines, QuantLab cross-links; optional
    FRED macro and delayed index/FX quote adapters are built but disabled by
    default; news/sentiment and GeoJSON borders remain absent; static illustrative data, not real-time)
15. Portfolio Studio + Ensemble Builder — **built_partial**: the Portfolio
    Studio side is built (multi-asset optimization/frontier/risk/stress/
    factor tools plus the Phase 56-58 diagnostics labs); the **Strategy
    Ensemble Builder is not** — Phase 61's Signal Ensemble combines signal
    values, not strategy return streams. Planned for **Phase 64**
16. ML & AI Lab — **built_partial** (see category 12: two working halves,
    not one lifecycle; Phase 65 unifies them)
17. AI Explainer Copilot — **research** (Phase 69 adds a deterministic
    evidence-grounded renderer only; an actual model-backed copilot is unscheduled)
18. 3D Visualization Engine — **research** (no 3D rendering path exists;
    open dependency decision)
19. Dashboard & Content Engine — **built_partial**: Quant Disasters built (13.2); dashboard
    content hub **built** (13.3: hero workflows, Trust Layer grid, Content
    Engine cards, featured items, direction panel); broader content engine
    future. Note: no disaster case is replayable as a scenario yet (the
    registry carries no run preset)
20. Platform & Launch — **built_partial**: QA Command Center, Demo Center,
    Data Reliability, Release Notes Center, Public Release Candidate,
    Portfolio Showcase and Developer Onboarding all exist, with release
    docs, checksum verification, CI and a manual Browser E2E workflow.
    **Hosted deployment, authentication and multi-user isolation remain
    deferred** — no auth, no per-user data isolation, no backups or
    monitoring story (Phase 70 plans a read-only demo without adding
    accounts)

## 5b. Areas whose labels changed in the Phase 62 audit

For traceability, the labels corrected on 2026-08-05 were: Futures &
Commodities (research → built_partial), Real Estate (research →
built_partial), Microstructure & HFT (future → built_partial), ML & AI
(future → built_partial), Volatility Lab (unlabelled → built_partial),
Strategy Ensemble Builder (research → planned for Phase 64, explicitly
distinguished from the built Signal Ensemble Lab), AI Explainer (future → research), 3D Visualization (future →
research), Platform & Launch (unlabelled → built_partial with deferred
hosting/auth). Evidence for each:
[`BLUEPRINT_STATUS_MATRIX.md`](BLUEPRINT_STATUS_MATRIX.md).

## 6. Hard constraints (apply to every phase)

- No live trading, broker integration, or real-money execution
- No new paid data providers or credential-management system; existing
  optional provider credentials remain environment-only and fail closed
- No fabricated results or cherry-picked benchmarks; deterministic samples
  must stay explicitly labelled illustrative
- Correctness first: lookahead-free, cost-aware, honest about overfitting
- Backward compatibility: old saved backtests, reports, and API requests keep
  working
- Educational positioning everywhere: **research, not investment advice**
