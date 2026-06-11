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

- Vectorized backtest engine (lookahead-free, costs, trade log)
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
| Robustness Lab (bootstrap Monte Carlo, deflated Sharpe, sensitivity heatmaps, PBO if feasible) | **built** (v1: block bootstrap + heuristic grade; deflated Sharpe / PBO / sensitivity heatmaps remain v2 — not implemented) |
| Quant Disasters Series (what blew up and why — LTCM, Aug 2007, vol short 2018, …) | future |
| Paper Replication Series (classic papers, honest deviations) | planned |
| AI Explainer Copilot (explains results; never recommends trades) | future |
| 3D Visualization Engine (vol surfaces, sweep landscapes) | future |
| Strategy Ensemble Builder | research |

## 4. Model catalog — 12 categories (~100 models long-term)

> **Do not claim these are implemented.** Only the "built" rows exist.

1. **Equities** — built (core 6); more planned (low-vol, quality, seasonal…)
2. **Options & Volatility** — planned (Black–Scholes v1, Greeks, IV surface,
   vol targeting / term structure; later Heston, SABR — research)
3. **Event-Driven & Arbitrage** — research (merger-arb toy, index add/remove,
   earnings drift)
4. **Futures & Commodities** — research (carry, term-structure, trend)
5. **FX** — research (carry, momentum, PPP toys)
6. **Fixed Income & Rates** — research (duration, curve steepeners, rolldown)
7. **Credit** — research (spread momentum, quality)
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
3. ~~Robustness Lab v1~~ — **built** (12.8; v2 = deflated Sharpe, PBO,
   sensitivity heatmaps)
4. Strategy Library v1 pages
5. Paper Replication Series v1
6. Options Pricing Engine v1
7. Volatility Lab v1
8. Event-Driven & Arbitrage Module
9. Rates / FX / Credit Module
10. Real Estate Module
11. Microstructure & HFT Lab (educational simulations)
12. Portfolio Studio + Ensemble Builder
13. ML & AI Lab
14. AI Explainer Copilot
15. 3D Visualization Engine
16. Dashboard & Content Engine (incl. Quant Disasters)
17. Platform & Launch

## 6. Hard constraints (apply to every phase)

- No live trading, broker integration, or real-money execution
- No paid data providers / API-key management until the platform phase
  explicitly takes it on
- No fake data, no fabricated results, no cherry-picked benchmarks
- Correctness first: lookahead-free, cost-aware, honest about overfitting
- Backward compatibility: old saved backtests, reports, and API requests keep
  working
- Educational positioning everywhere: **research, not investment advice**
