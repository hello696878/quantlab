# QuantLab — Master Blueprint v3 (internal direction)

This is the **internal long-term direction** for QuantLab. It is ambitious on
purpose — and explicitly **not** a list of existing features. Anything not
labelled **built** does not exist yet. Public-facing docs (README, app copy)
must stay credible: no "guaranteed alpha", no "institutional-grade data", no
"production trading system" claims.

**Positioning (fixed):** QuantLab is a **local-first quant research platform**
for education and research — transparent about data quality and backtest
limitations, **not live trading, not investment advice**.

Status labels used below: **built** · **planned** · **research** · **future**.

---

## 1. Vision

An interactive platform where a user can explore ~**100 educational quant
models across 12 categories**, run honest backtests on real historical data,
stress the results (robustness, costs, risk rules, benchmarks), and learn the
math behind each model — with trust features that make every number
reproducible and every limitation explicit.

---

## 2. Completed foundation (built)

- Vectorized single-instrument backtest engine (lookahead-free, costs, trade log)
- **Cross-Sectional Scanner Engine v1** — a *second engine* (18.0): ranks a
  synthetic universe, forms dollar-neutral long/short baskets, and runs a
  lookahead-safe portfolio backtest (reversal + momentum signals)
- **AFML Methodology Layer v1** (19.0–19.2): leakage-aware labeling + validation
  toolkit — CUSUM event sampling, triple-barrier labeling, sample concurrency +
  uniqueness weights (19.0), **purged K-fold + embargo cross-validation** with
  leakage diagnostics (19.1), and **sequential bootstrap** (uniqueness-aware
  sampling) (19.2), on synthetic data (a methodology toolkit, not a model)
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
| Reproducible Backtest Permalinks / config hash | **built** (v1: canonical config hash + CSV content fingerprint; replay-by-hash routing + dataset version hashes future) |
| Robustness Lab (bootstrap Monte Carlo, deflated Sharpe, sensitivity heatmaps, PBO if feasible) | **built** (v1: block bootstrap + heuristic grade; 12.9 added the SMA parameter-sensitivity heatmap / Stability Lab. Deflated Sharpe / PBO / multi-strategy sweeps remain v2 — not implemented) |
| Quant Disasters Series (what blew up and why — LTCM, Aug 2007, vol short 2018, …) | **built** (v1: 6 case studies — LTCM, 1987, Flash Crash, Volmageddon, Archegos, FTX — educational summaries with honest "cannot model yet" lists; scenario stress simulations remain future) |
| Paper Replication Series (classic papers, honest deviations) | **built** (v1: 8 paper pages + 3 inspired demos clearly labelled as simplified; full replications future — need universe data) |
| AI Explainer Copilot (explains results; never recommends trades) | future |
| 3D Visualization Engine (vol surfaces, sweep landscapes) | future |
| Strategy Ensemble Builder | research |

## 4. Model catalog — 12 categories (~100 models long-term)

> **Do not claim these are implemented.** Only the "built" rows exist.

1. **Equities** — built (core 6); more planned (low-vol, quality, seasonal…)
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
4. **Futures & Commodities** — research (carry, term-structure, trend)
5. **FX** — **built (v1)**: FX Lab — interest rate parity forward, FX carry, PPP
   deviation, currency exposure + stress, Garman-Kohlhagen FX options (16.2).
   Planned: FX vol surface, momentum/carry strategy backtests, live rates
6. **Fixed Income & Rates** — **built (v1)**: Yield Curve Lab — zero rates,
   discount factors, forwards, curve shocks, bond duration/convexity/DV01 (16.0);
   Short Rate Models Lab — Vasicek / CIR simulation + analytic zero-coupon pricing
   (16.1). Planned: Hull-White, swap-curve bootstrapping, rolldown
7. **Credit** — **built (v1)**: Credit Risk Lab — Merton structural model +
   distance to default, reduced-form hazard / survival, simplified CDS par spread,
   risky bond pricing (17.0). Planned: full CVA, credit-portfolio model, rating
   transitions, credit spread strategies
8. **Crypto** — built (partial: tickers + 365-day convention); funding-rate /
   basis models research; exchange-native data future
9. **Real Estate** — research (REIT factor / rate sensitivity)
10. **Market Microstructure & HFT** — future; **14 educational HFT models as
    simulations on synthetic data only** (order-book imbalance, queue position,
    market-making toys). No real HFT execution, no live tick feeds.
11. **Portfolio & Risk** — built (core); ensemble builder + risk parity v2
    planned
12. **Machine Learning & AI** — future (feature pipelines, walk-forward ML
    guards, overfitting alarms first)

## 5. Phase order (near-term first)

1. ~~Benchmark visualization~~ — **built** (12.6.1)
2. ~~Reproducible Backtest Permalinks / Config Hash~~ — **built** (12.7)
3. ~~Robustness Lab v1~~ — **built** (12.8 + 12.9 Stability Lab heatmap; v2 =
   deflated Sharpe, PBO, multi-strategy sweeps)
4. ~~Strategy Library v1 pages~~ — **built** (13.0: six live strategy pages +
   honest planned catalog; registry in `frontend/src/lib/modelRegistry.ts`)
5. ~~Paper Replication Series v1~~ — **built** (13.1)
6. ~~Options Pricing Engine v1~~ — **built** (14.0 Black–Scholes; 14.1 CRR
   binomial tree + American exercise; 14.2 Monte Carlo GBM + Asian/barrier;
   14.3 IV surface + SVI research fit; 14.4 Heston stochastic volatility)
7. Volatility Lab v1
8. ~~Event-Driven & Arbitrage Module~~ — **built (v1)** (15.0: event study + merger-arb calculator)
9. Rates / FX / Credit Module — **started** (16.0: Yield Curve Lab v1;
   16.1: Short Rate Models v1 — Vasicek / CIR; 16.2: FX Lab v1 — IRP / carry /
   PPP / exposure / Garman-Kohlhagen; 17.0: Credit Risk Lab v1 — Merton / hazard /
   CDS / risky bond)
10. Real Estate Module
11. Microstructure & HFT Lab (educational simulations)
12. ~~Cross-Sectional Scanner Engine~~ — **built (v1)** (18.0: second engine —
    synthetic universe, dollar-neutral long/short, lookahead-safe portfolio
    backtest; reversal + momentum)
13. ~~AFML Methodology Layer~~ — **built (v1)** (19.0: CUSUM event sampling,
    triple-barrier labeling, sample concurrency + uniqueness weights; 19.1: purged
    K-fold + embargo CV with leakage diagnostics; 19.2: sequential bootstrap;
    meta-labeling, fractional differentiation, CPCV planned)
14. Portfolio Studio + Ensemble Builder
15. ML & AI Lab
16. AI Explainer Copilot
17. 3D Visualization Engine
18. Dashboard & Content Engine — Quant Disasters **built** (13.2); dashboard
    content hub **built** (13.3: hero workflows, Trust Layer grid, Content
    Engine cards, featured items, direction panel); broader content engine
    future
19. Platform & Launch

## 6. Hard constraints (apply to every phase)

- No live trading, broker integration, or real-money execution
- No paid data providers / API-key management until the platform phase
  explicitly takes it on
- No fake data, no fabricated results, no cherry-picked benchmarks
- Correctness first: lookahead-free, cost-aware, honest about overfitting
- Backward compatibility: old saved backtests, reports, and API requests keep
  working
- Educational positioning everywhere: **research, not investment advice**
