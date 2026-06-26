# QuantLab — Demo Script (8–12 minutes)

A polished walkthrough for a portfolio showcase or screen recording. It moves
from the Command Center → a real backtest with the Trust Layer → reporting →
strategy comparison → the Content Engine, and closes on the roadmap. Every
number shown is a **real backend run** — nothing is faked, and nothing planned
is presented as built.

**Before you start**
- Run the stack (`docker compose up --build`, or `uvicorn` + `npm run dev`).
- Have **at least one saved backtest and one saved report** already stored so the
  Command Center recents and global search have content. (Tip: run steps 3–6
  once beforehand.)
- Optional: set the accent theme you like in **Settings** (the **cyan** default
  or the **Risk** red read well on camera).

**Reusable parameters**

| Backtest | Portfolio |
|---|---|
| ticker **SPY** | tickers **SPY, QQQ, GLD, TLT** |
| strategy **SMA Crossover** | range **2015-01-01 → 2023-12-31** |
| range **2015-01-01 → 2023-12-31** | risk-free **0.02** |
| fast **20** / slow **100** | num portfolios **2000** |
| capital **100,000** · cost **10 bps** | |
| position mode **long_only** | |

---

## The flow

### Demo 1 · Command Center (~60s)
Load <http://localhost:3000>. Point out the four pillars on the hub: **research
workflows** (hero CTAs + quick actions), the **Trust Layer** grid, the
**Content Engine** cards (Strategy Library · Paper Replications · Quant
Disasters, with live counts), and **saved research** (recents + system status
from local SQLite). Scroll to the **Platform Direction** panel.
> "QuantLab opens on a research hub. Everything is local-first, and the
> direction panel is honest — only items marked Built exist."

### Demo 2 · Backtest Studio (~90s)
Go to **Backtest**. Set: **SMA Crossover · SPY · 2016-01-01 → present · cost
model Simple 10 bps · position sizing Full Allocation · risk management None ·
annualization trading_days_252 · benchmark Buy & Hold Same Asset**. Click
**Run**.
Walk the result top-down: **metrics grid**, the **neon equity curve vs the
labelled benchmark**, the **drawdown overlay**, the **cumulative excess return**
chart, the **Benchmark Comparison** card (alpha/beta/correlation/tracking
error/information ratio), the **Data Source** card, and the **Reproducibility**
card.
> "Real yfinance data, one-day signal shift — no lookahead. Every result
> carries its data quality and a SHA-256 config hash: same normalized config,
> same hash."

### Demo 3 · Trust Layer (~90s)
Re-run the same backtest with **Run robustness analysis** and **Run Stability
Lab** enabled (defaults: 1,000 sims · block 5 · seed 42).
Show the **Robustness Lab** card — probability of loss, percentile ranges, the
final-return histogram, and the **heuristic grade** — then the **Stability
Lab** heatmap with the selected 20/100 cell ring-highlighted.
> "Robustness resamples *returns*; stability varies *parameters*. Broad stable
> regions beat isolated spikes — and both cards say plainly they're
> diagnostics, not guarantees."

### Demo 4 · Report Export (~45s)
**Save** the backtest (toast confirms), then **Export Report** → PDF
print-preview. Scroll the structured sections: Metadata, Simulation Settings,
Data Quality, Benchmark Comparison, Robustness Lab, Stability Lab,
Reproducibility, Risk/Caveats.
> "The report carries the assumptions and the caveats — including the config
> hash — so the research is auditable. No raw JSON anywhere."

### Demo 5 · Strategy Comparison (~60s)
Open **Strategy Comparison**. Point at the **Simulation Settings** (cost,
sizing, risk, annualization, benchmark applied to all five strategies), run on
SPY, and show the ranked table plus the **"vs Benchmark"** toggle
(excess/alpha/beta/IR columns).
> "Five strategies under identical assumptions — and mean-reversion strategies
> that can't short are labelled, not silently skipped."

### Demo 6 · Content Engine (~90s)
Open **Strategy Library** → SMA Crossover (hypothesis, parameters, failure
modes, trust checklist, related papers/disasters). Open **Paper Replications**
→ Jegadeesh–Titman (point at the **Inspired Demo** badge and the "not a full
replication" caveats). Open **Quant Disasters** → LTCM (the "what a naive
backtest might miss" section and the honest "cannot model yet" list).
> "The platform teaches how strategies work, where the ideas came from, and how
> they fail — with the same honesty rules as the engine."

### Demo 7 · Portfolio Studio (~60s, optional)
Open **Portfolio Lab**: run the **Efficient Frontier** (SPY/QQQ/GLD/TLT · rf
0.02 · 2,000 portfolios) and glance at the **Risk Dashboard** heatmap.
> "Multi-asset analytics with the same in-sample honesty caveats."

### Demo Close · Roadmap (~30s)
Return to the Command Center's **Platform Direction** panel (or open
`docs/ROADMAP.md`).
> "Options Lab v1 is now built as an educational calculator. Next up per the
> blueprint: deeper volatility tooling, event-driven and arbitrage modules, an
> ensemble builder, a microstructure/HFT teaching lab, an explainer copilot,
> and 3D visualization — all clearly marked planned or future, none claimed as
> built. Under the hood it's FastAPI + Next.js + local SQLite: research
> software, not a trading system."

---

## Optional add-ons (if you have extra time)
- **Guided demos / onboarding** — show a preset chip prefilling the form
  (never auto-runs); run the BTC-USD crypto momentum demo with **auto**
  annualization resolving to crypto 365.
- **Command palette** — Ctrl/Cmd+K, search `LTCM`, `Flash Crash`,
  `Fama French`, `robustness`, or a saved report name; everything is reachable
  from the keyboard.
- **Options Lab** — show the Black–Scholes reference case (S=100, K=100, T=1,
  r=0.05, sigma=0.20), the IV warning for an impossible price, and a short-call
  payoff with unbounded max loss. Then open **Tree Pricing**: price the same
  case on a CRR binomial tree (European call ≈ 10.45, converging to BS), switch
  to an **American put** (price ≥ the European put, early exercise detected),
  and drop steps to 5 to show the small lattice diagram. Finally open **Monte
  Carlo**: price the European call (10,000 sims · seed 42 → ≈ 10.45 with a
  standard error and 95% CI that brackets Black–Scholes), show the path-preview
  chart, then switch to an **Asian Call** and an **Up-and-Out Call** (barrier
  120) to show path-dependent payoffs with the discrete-monitoring warning.
  Last, open **Vol Surface** → *Generate Sample Surface*: the summary cards, the
  smile chart (raw IV scatter + SVI curve in distinct colours), the ATM
  term-structure chart, and the moneyness × expiry heatmap all populate from a
  synthetic chain — emphasise it is research, not live market data. Then open
  **Heston** → *Run Heston* on the defaults: the price / SE / CI / Black–Scholes
  reference / Feller-status cards plus the underlying and volatility path charts
  (multi-colour, first path highlighted); set vol of vol = 0 to show it collapse
  toward the Black–Scholes reference, and note the Euler/Feller/MC caveats.
- **Options Lab scenario flow (short):** at the top of the Options Lab pick the
  **ATM Equity Call** scenario preset (a "Scenario applied" notice appears) →
  **Black–Scholes** shows the price and Greeks → **Tree Pricing** compares
  European vs American → **Monte Carlo** shows the price with its 95% CI →
  **Vol Surface** → *Generate Sample Surface* → **Heston** shows the volatility
  paths → **Model Compare** → *Run Comparison* prices the scenario across every
  model in one table. Emphasise: presets are educational scenarios, and models
  differ because their assumptions differ — none is automatically "correct".
- **Event Lab** — *Event Study*: AAPL vs SPY, market-adjusted, a sample event
  date → show the summary cards, the sign-coloured abnormal-return bars, the CAR
  line, and the asset-vs-benchmark cumulative chart. Mention that windows are
  trading observations and post-event CAR excludes day 0 (shown separately as
  event-day AR). Note the "next trading day" warning when the date is a weekend.
  Switch to *Merger Arb* (current 90, offer
  100, downside 70, P(close) 0.8, 180 days) → spread, expected return, and
  breakeven probability. Emphasise: research diagnostic, no live filings, not
  investment advice.
- **Yield Curve Lab** — *Curve Builder*: Load sample curve → Build curve → show
  the spot, discount-factor, and forward-rate charts; flip compounding from
  continuous to annual to show discount factors change. *Curve Shocks*: parallel
  +100 bps, then steepener (long end rises vs short). *Bond Pricing*: face 1000,
  coupon 5%, 5y, semiannual, YTM 4.5% → price, duration, DV01 magnitude,
  convexity (result-card values are bright/readable on the dark theme).
  *Short Rate Models*: **Load Vasicek demo** → **Run simulation** → show the
  zero-coupon price / implied zero rate / mean terminal rate cards, the
  multi-colour path preview (mean path + dashed long-run mean θ), and the
  terminal-rate distribution; bump σ to ~20% to make negative-rate bars (red,
  left of 0) and the Vasicek negative-rate warning appear. **Load CIR demo** →
  **Run** → rates stay non-negative and the Feller-condition card shows; set
  σ high enough to violate Feller (2κθ < σ²) to surface that warning.
  Emphasise: forward rates are implied, not guaranteed forecasts; short-rate
  paths are model scenarios, not forecasts; synthetic curves, no live rates
  feed, no market calibration, no Hull-White, assumption-sensitive.
- **FX Lab** — *Forward / IRP*: spot 150, domestic 1%, foreign 5%, T 1,
  continuous → forward ≈ 144.12 (below spot — foreign trades at a forward
  discount). *Carry*: spot 150, dom 1%, for 5%, expected 152, 1y, notional
  1,000,000, long foreign → interest differential, carry return, expected FX
  return, total, and P&L (note "carry is not free money"). *PPP*: current 150,
  base 120, dom index 110, for index 105 → PPP-implied ≈ 125.71 and the
  deviation / valuation label. *Exposure*: USD / JPY / EUR sample rows, base USD,
  10% shock → total exposure, per-currency bars, and ± stress P&L (the base
  currency carries no FX risk). *FX Options*: call, S 1.10, K 1.10, dom 4%,
  for 2%, vol 12%, T 1 → price, d1/d2, delta, gamma, vega and the intrinsic
  payoff chart. Emphasise: domestic-per-foreign convention; all result-card
  values are readable on the dark theme; no live FX rates, no FX vol surface,
  not investment advice.
- **Credit Risk Lab** — *Merton Model*: asset value 120, debt face 100, asset
  vol 25%, rf 4%, maturity 1, recovery 40% → equity / debt / distance to default
  / default probability / credit spread cards + the equity-vs-debt capital
  breakdown; drop the asset value to 80 to watch the default probability jump.
  *Hazard / Survival*: λ 2%, recovery 40%, maturity 5 → survival (green) vs
  cumulative-default (red) curves and the simple `λ·LGD` ≈ 120 bps card. *CDS
  Spread*: λ 2%, recovery 40%, 5y, rf 4%, freq 4, notional 1,000,000 → fair
  spread ≈ 120 bps with the protection/premium legs equal at the fair spread.
  *Risky Bond*: face 1000, coupon 5%, 5y, semiannual, rf 4%, λ 2%, recovery 40%
  → risky price below the risk-free price, the credit spread, and the
  survival-weighted cash-flow table. Emphasise: stylized structural + flat-hazard
  reduced-form models, no live CDS/bond data, no full CVA, not investment advice.
- **Portfolio Risk Lab (21.0)** — open from the sidebar (or Ctrl/Cmd+K → "Open
  Portfolio Risk Lab"). The deterministic 8-asset sample loads and analyses
  automatically: key-metric cards (expected return, volatility, Sharpe, monthly
  VaR / CVaR), the efficient-frontier scatter with **Current / Min variance /
  Risk parity** markers, the risk-contribution table (note the % risk column sums
  to 100% — diversifiers like US Treasury and gold carry less risk than their
  weight), and the correlation & covariance grids. Edit a weight (e.g. push US
  Equity to 0.5) and watch every metric update live; click **Normalize weights**
  to rescale to 100%, then **Reset sample**. Switch confidence to 99% to widen
  VaR/CVaR. Show the **Risk-off shock** stress table and the estimated portfolio
  impact, then the copyable formula reference. Emphasise: static illustrative
  sample data, long-only v1, monthly historical VaR/CVaR example, a deterministic
  frontier demonstration — not a production risk engine, not investment advice.
  **Factor & scenario layer (21.1):** scroll to **Factor exposure** (per-asset
  beta heatmap across Equity Market / Size / Value / Momentum / Rates / Credit /
  USD / Commodity / Volatility), **Portfolio factor exposure** (β = Bᵀw key
  factors), and **Factor risk decomposition** (factor contributions + a Specific
  /idiosyncratic row; note factor % + specific % = 100%). In **Scenario stress**,
  click through **Equity selloff → Rates shock → USD squeeze → Commodity rally →
  Credit stress** and watch the portfolio impact, asset-impact and factor-impact
  tables, and worst/best asset update; then change a weight (e.g. raise Gold) and
  watch factor exposure and scenarios re-compute. Emphasise: factor betas are
  deterministic illustrative values (not estimated), factors are orthogonal in
  v1, scenarios are educational sample shocks — a simplified factor model, not a
  production risk model, not investment advice.
  **Optimization & Black-Litterman (21.2):** scroll to **Optimization Lab** — the
  table compares Current / Max Sharpe / Min variance / Risk parity / Equal weight
  (expected return, volatility, Sharpe, turnover, largest weight). Type a **Target
  return** of `0.06` and a **Target volatility** of `0.12` to see those rows
  appear, then a target return of `0.50` to see the friendly "not achievable"
  message (no crash). In **Current vs optimized weights**, switch the target
  between Max Sharpe / Min variance / Risk parity / Black-Litterman and watch the
  Δ column and the **absolute turnover** + largest hypothetical increase/decrease
  update. In **Black-Litterman**, point out the prior → implied → posterior return
  columns, the three sample views (Taiwan>Japan, Gold>Cash, US Treasury absolute),
  and the BL-optimized portfolio; the panel states "Sample views are illustrative
  only and are not forecasts." Change a weight and watch the optimization and
  rebalance re-compute. Emphasise: deterministic candidate-search optimizer (not a
  production solver), illustrative BL views (not forecasts), hypothetical rebalance
  deltas (not trade orders, no buy/sell) — not investment advice.
  **Monte Carlo & robustness (21.3):** scroll to **Monte Carlo simulation** — note
  the terminal-wealth mean/median/P05/P95 cards, probability of loss, drawdown-
  breach probability, simulated VaR/CVaR, and the **fan chart** (p05–p95 band +
  median). Change Horizon to `504`, Paths to `1000`, and the **Seed** to a new
  number to show the simulation re-run (same seed ⇒ identical, the panel says "It
  is not a forecast."). Then **Bootstrap robustness** (resampled sample series, with
  a short-sample note), the **Assumption sensitivity** table (±25% returns, ±vol,
  ±0.20 correlation, ±1% rate → return/vol/Sharpe/VaR/CVaR), and **Optimization
  robustness** (base vs worst-case Sharpe, range, rank stability across scenarios).
  Change a weight and watch all four re-compute. Emphasise: deterministic fixed-
  seed simulations on illustrative sample data — outcome distributions, **not
  forecasts or guaranteed probabilities**, not a production risk model, not advice.
- **Cross-Sectional Scanner** — the *second engine*. Use the defaults (reversal,
  50 assets, 2022-01-01 → 2024-12-31, lookback 5, long/short quantile 0.2, daily,
  gross 1.0, cost 5 bps, seed 42) → **Run Scanner** → metric cards (total /
  annualized return, Sharpe, max drawdown, avg turnover, avg gross ≈ 1.0, avg net
  ≈ 0), the net equity curve, drawdown, long/short exposure (net ≈ 0), turnover,
  the latest ranking table (long/short side badges, weights), and diagnostics.
  Switch to **Momentum demo** and re-run to show the workflow generalizes. Try
  long quantile 0.8 (friendly validation error) and n_assets 3 (insufficient
  universe). Emphasise: a *second engine* (the single-asset Backtest Studio is
  unchanged); signals are shifted forward one period (no lookahead); synthetic
  universe for workflow demonstration, not live market data, not investment advice.
- **AFML Methodology Lab** — the financial-ML *labeling* layer. Use the defaults
  (500 days, daily vol 1.5%, CUSUM threshold 2%, profit-take ×1.5, stop-loss ×1.0,
  vertical 10 days, seed 42) → **Run labeling demo** → summary cards (events, +1 /
  −1 / vertical counts, mean uniqueness, avg holding). *CUSUM Sampling*: the
  synthetic path with up/down event markers + the event table. *Triple-Barrier*:
  the label distribution and the label table — click a row to overlay that event's
  profit-take / stop-loss / vertical barriers on the price chart. *Sample
  Uniqueness*: the concurrency-over-time chart, the average-uniqueness histogram,
  and the sample-weight table (overlapping labels get uniqueness < 1). Raise the
  CUSUM threshold to show the event count drop; try threshold = −1 for a friendly
  validation error. *Purged CV*: with n_splits = 5 and embargo 0.01 → **Run purged
  CV** → summary cards (overlap folds before vs after, total purged / embargoed,
  avg train remaining), the fold table (overlap-after-purge = 0 everywhere), and the
  fold timeline (each label interval coloured train / test / purged / embargo —
  click a fold row to switch). Set embargo to 0 to drop the embargoed count; try
  n_splits = 100 for a friendly validation error. *Sequential Bootstrap*: sample
  size 25, random trials 200 → **Run sequential bootstrap** → summary cards
  (sequential vs random average uniqueness, improvement), the uniqueness-after-each-draw
  path against the random-mean reference line, the comparison bar, the random-baseline
  distribution, selected-interval timeline, and selected-events table; bump the CUSUM
  threshold down and the vertical barrier up to explore how overlap changes the comparison. Emphasise:
  synthetic demo data, a labeling + validation + sampling pipeline (not a trained
  model), event formation uses no future info, purged CV reduces overlap leakage but
  doesn't bless a model, sequential bootstrap reduces sample dependence (not model
  risk), and CPCV / meta-labeling are planned — not a full AFML implementation, not advice.
  *Fractional Differentiation*: d = 0.5, weight threshold 0.001, max weights 200 →
  **Run fractional differentiation** → summary cards (weight count ≈ 44, warmup,
  data loss, fracdiff vs first-diff memory correlation), the original-price chart, the
  first-diff-vs-fracdiff overlay, the weights bar chart, and the stationarity-style
  diagnostics table (compare lag-1 autocorrelation and rolling/variance stability proxies).
  Set d = 0 (fracdiff ≈ original, memory corr ≈ 1), then d = 1 (≈ first difference);
  try d = −0.5 for a friendly validation error. Emphasise: fractional differentiation
  is preprocessing (not a signal), targets a memory/persistence trade-off, and the
  diagnostics are heuristic — not a formal stationarity test.
- **Global Markets Globe (v1.1)** — the flagship "mission-control" explore
  experience. Open **Global Markets Globe** from the sidebar (or the hero
  "Explore Global Markets" button). Note the three zones: left rail
  (search · region filter · market list · quick-jump), center **canvas globe**
  (dot-matrix continents, atmosphere halo, starfield, pulsing region-colored
  markers, illustrative great-circle arcs), and right dossier. Drag the globe to
  rotate, toggle **⏸ Spin**, hover a marker for its tooltip, then click
  **United States** → the dossier opens and the globe re-centres on it: sticky
  header with a **bias pill** + **"Static demo data"** badge + "Last updated:
  Static sample", then **Market Pulse** (indices + sparklines), **Macro Vitals**,
  **FX & Rates**, **Market Structure**, **Sample Headlines** with
  **Bullish / Bearish / Neutral** pills, and **QuantLab Actions**. Use the
  quick-jump chips (US / UK / Japan / Hong Kong), filter to **APAC** and search
  `Taiwan`, then **Reset**. Point at the bottom **region tape** and the dashboard
  **Global Markets** strip. Use Ctrl/Cmd+K → "Open Taiwan Market Dossier" for the
  deep-link. Emphasise: a hand-built canvas globe (no WebGL/Three.js — the market
  list is the keyboard-accessible fallback, with a graceful message if 2D canvas
  is unavailable), **indices, FX, market structure, and headlines are static
  illustrative sample data**; the arcs and bias pill are decorative. Optional
  US FRED macro observations can be enabled locally, while delayed index/FX
  quotes, news/sentiment, and GeoJSON borders remain planned — not investment
  advice. **Data Layer (20.2):** open the network tab to see the page call
  `GET /api/globe/markets` (typed backend dossier API); the header chip reads
  "Backend static dataset" by default. Stop the backend and reload to show the
  graceful fallback — the chip flips to "Bundled static fallback" with a
  non-blocking "Backend globe data unavailable…" warning and the globe stays
  fully usable. **FRED macro (20.3):** by default the dossier macro chip reads
  "Macro: Static sample". To show the fail-closed path, set
  `GLOBE_FRED_ENABLED=true` with no key: a non-blocking warning appears and the
  US macro chip reads "FRED unavailable, static fallback"; unsupported markets
  remain static. With a personal `FRED_API_KEY` loaded locally (never
  committed), the US dossier reads "Macro: Partial FRED", marks only the
  FRED-sourced metric cards, and shows per-field observation dates. Inflation,
  debt/GDP, every unsupported country, indices, FX, and news remain static.
  **Delayed quotes (20.4):** by default the dossier shows "Index quotes: static
  sample" and "FX: static sample". Set `GLOBE_QUOTES_ENABLED=true` with
  `GLOBE_QUOTES_PROVIDER=mock` (no real provider) → supported markets show
  "… unavailable — static fallback" + a non-blocking warning (never crashes).
  With the default `yfinance` provider + network, supported markets (e.g. US
  index, Japan index+FX) show a **delayed** level/rate and "Index quotes:
  delayed · as of …" — delayed, never real-time; unsupported markets and
  secondary rows stay static. **News sentiment (20.5):** the dossier **Sample
  Headlines** section shows a "News: static sample" chip, the copy "Sample
  headlines — live news integration planned.", and Bullish/Bearish/Neutral
  pills. Set `GLOBE_NEWS_ENABLED=true` with `GLOBE_NEWS_PROVIDER=live` (no real
  provider) → the chip flips to "News unavailable — static fallback" with a
  non-blocking warning; headlines stay static (never crashes). It's a scaffold
  only — **no live news, no scraping, no API, no AI summarizer**.
  **Dossier permalinks (20.6):** open **`/globe?market=tw`** (or
  `/?view=globe&market=tw`) — Taiwan's dossier opens automatically with the
  marker highlighted; try `/globe?market=jp` and `/globe?market=bad-id` (the
  latter falls back to the US default with a "Market not found; showing default
  market." notice, no crash). Click markers for US/Germany/India and watch the
  URL update (`?market=us/de/in`); use browser **Back/Forward** to walk the
  visited dossiers. Click the dossier **🔗 Share** button → "Copied Globe dossier
  link." (the copied URL includes `?market=<id>`). Stop the backend and reopen
  `/globe?market=tw` — Taiwan still selects from bundled fallback data. In
  Ctrl/Cmd+K search "US/Taiwan/Japan/Germany/India Market Dossier"; the Dashboard
  globe card links straight to those dossiers. Navigation/UX only — no new data.
  **Guided tours & presentation mode (20.7):** open **`/globe?tour=global`** — the
  Guided Tour card opens, the first market (US) is selected, and its dossier
  opens. Click **Next/Previous** to walk the curated steps (the URL updates,
  e.g. `?market=tw&tour=global`); **Exit tour** drops `?tour` but keeps the
  market. Try `/globe?market=tw&tour=asia` (Taiwan's step in the Asia tour) and
  `/globe?tour=bad-tour` (friendly "Tour not found; showing Globe normally."
  notice, no crash). Toggle **⤢ Present** (or open `/globe?market=tw&presentation=1`)
  for a screenshot-friendly layout — rail/tape hidden, globe + dossier + tour card
  emphasised, source badges and static-data notice still visible. Click the
  dossier **📋 Copy summary** → "Copied dossier summary." (text includes the
  market name and the static-data / not-investment-advice disclaimer). Stop the
  backend and reopen `/globe?tour=asia` — the tour still works on bundled
  fallback. Palette: *Start Global/Asia/Macro Regime/Risk Lens Tour*, *Open Globe
  Presentation Mode*. Educational tours only — no live data, no signals, not advice.
- **Real Estate Lab (22.0)** — open from the sidebar (or Ctrl/Cmd+K → "Open Real
  Estate Lab"). The deterministic Urban Apartment sample loads and analyses
  automatically: key-metric cards (NOI, in-place cap rate, value @ exit cap, LTV,
  DSCR, cash-on-cash, IRR, equity multiple), the year-1 income statement, the debt
  & amortization table (first 12 months), the scenario-stress table (base / rent
  upside / vacancy shock / cap-rate expansion / interest-rate shock / downside
  combo), and the REIT NAV panel (NAV/share 25 vs price 22 → ~12% discount, P/FFO,
  dividend yield). Edit assumptions (e.g. raise vacancy or the interest rate, lower
  the exit cap) and watch every metric and scenario re-compute; **Reset sample**
  restores defaults. Emphasise: static illustrative sample data, a simplified
  deterministic model — not live property/REIT prices, not a production appraisal
  or underwriting tool, not investment / tax / legal / lending advice.
  **Mortgage & MBS Prepayment (22.1):** scroll to the appended section — the
  Agency MBS Sample Pool loads and analyses automatically. Show the key-metric
  cards (price/100, WAL, duration, convexity, total interest, final balance), the
  month-1 CPR→SMM line, the MBS cash-flow table (scheduled vs prepayment
  principal), the PSA/CPR path (ramp to 6% by pool age 30 at 100 PSA), and the
  scenario-stress table. Raise the **PSA speed** to 200 (faster prepay → shorter
  WAL), drop it to 50 (slower → longer WAL), and move the **discount rate** up/down
  (price falls/rises). Point out the scenario rows: Fast prepayment shortens WAL,
  Slow/Extension extends it, Rate up lowers price, Refinance wave shortens WAL.
  Emphasise: simplified CPR/SMM/PSA and educational WAL/duration/convexity
  approximations — no live mortgage rates or MBS prices, not a production
  valuation, not investment or lending advice.
- **Futures & Commodities Lab (23.0)** — open from the sidebar (or Ctrl/Cmd+K →
  "Open Futures and Commodities Lab"). The Crude Oil sample loads and analyses
  automatically. Show the key-metric cards (model 12M future, curve shape, near
  basis, implied convenience yield, roll yield, calendar spread, initial margin,
  return on margin) and the futures-curve table (observed vs cost-of-carry model,
  basis, implied convenience yield, roll yield). Switch commodities: **Crude** and
  **Gold** are contango, **Natural Gas** is backwardation (near above far),
  **Wheat** is mixed — point out the curve-shape panel and roll-yield
  interpretation. Edit assumptions (raise the convenience yield → curve drifts
  toward backwardation; raise storage → more contango; change spot/margin rates)
  and watch every metric and scenario re-compute. Walk the scenario-stress table
  (base, spot rally/selloff, contango steepening, backwardation/storage/convenience
  shocks, margin stress). Emphasise: static illustrative sample data, simplified
  cost-of-carry and curve analytics — no live futures/commodity prices, not a
  production risk engine, no exchange/broker integration, not investment or
  trading advice.
- **Volatility Surface & Variance Swap Lab (24.0)** — open from the sidebar (or
  Ctrl/Cmd+K → "Open Volatility Lab"). The SPX-like sample chain loads and
  analyses automatically (implied vols are recovered from Black-Scholes-generated
  mids). Show the key-metric cards (ATM 30d/90d/1Y IV, realized vol, implied−realized
  spread, variance-swap vol strike, total vega, term slope), the **smile** table
  (switch the maturity selector — note downside puts trade richer than upside
  calls, the equity skew), the **term-structure/skew** table, the 2-D **surface
  grid** (maturity × strike), the **variance-swap** panel with the option strip,
  and the **vega-exposure** panel (by maturity & moneyness). Edit the underlying
  spot/rate/dividend and watch everything re-compute. Walk the scenario-stress
  table (parallel vol up/down, skew steepening/flattening, short-/long-dated
  repricing, spot-selloff-with-vol-up). Emphasise: static illustrative sample data,
  a simplified educational variance-swap approximation — **not** a live option
  chain, **not** official VIX methodology, not a production risk engine, not
  investment or trading advice.
- **Market Microstructure & Execution Lab (25.0; TCA in 25.1)** — open from the
  sidebar (or Ctrl/Cmd+K → "Open Market Microstructure Lab" / "Execution Cost
  Attribution"). Pick an instrument tab (BTCUSDT, SPY, CL, TSM); the sample order
  book, trade tape, parent order, and fills load and analyse automatically. Show the
  key-metric cards (mid, spread_bps, microprice Δ, top imbalance, VWAP, implementation
  shortfall, participation, market impact), the **order-book depth ladder**, the
  **imbalance & microprice** panel (note the bid-heavy book pushes microprice above
  mid), the **trade-tape** panel (VWAP vs TWAP, signed trade imbalance), and the
  **execution summary** (avg fill vs arrival → positive shortfall is a cost). Walk the
  **execution-schedule comparison** (Immediate front-loads impact vs TWAP/VWAP/POV),
  the **liquidity-stress** table (spread doubles, depth halves, volatility spike,
  volume drought, combo shock, bid-/ask-side pressure), and the new **TCA / Execution
  Cost Attribution** card (arrival/VWAP/TWAP benchmark shortfalls + a spread / impact /
  timing / fees / residual table that sums to the realised shortfall). Then scroll to
  the new **Order Flow Toxicity & Liquidity** section (Phase 25.2): key cards (order-flow
  imbalance, queue imbalance, **VPIN**, effective / realized spread, **adverse selection**,
  **Kyle λ**, **Amihud**), a **liquidity-regime** pill, a **spread-quality** table, and the
  **toxic-flow scenarios** table — point out that buy/sell pressure waves move OFI, spread
  widening raises effective spread, toxic informed flow raises adverse selection, and
  volume drought raises Amihud illiquidity. Note the **Formulas & notes** now render as
  crisp **LaTeX** (KaTeX, local — no CDN) with a **📋 Copy LaTeX** button. Edit the parent
  quantity / ADV / volatility / impact and watch everything re-compute. Emphasise: static
  illustrative sample data, simplified educational impact/schedule/TCA/toxicity models —
  the **VPIN-style metric is a simplified approximation, not exchange VPIN**, **not**
  real-time toxicity detection, **not** a live order book or trade feed, no broker/exchange
  integration, **not** a production execution / TCA system, no schedule is recommended, not
  investment / trading / order-routing advice.
- **LaTeX formula polish (25.1)** — across the labs (Portfolio Risk, Options,
  Volatility, Futures, Real Estate, MBS, Credit, FX, Yield Curve / Short Rate, Event,
  Microstructure), open each "Formulas & notes" / "Key formulas" section to show
  equations rendered as **local KaTeX** (no math CDN) with a **Copy LaTeX** button that
  yields clean LaTeX source. A malformed formula degrades to a code block rather than
  crashing the page.
- **Custom Strategy Builder** — load the *Momentum + Trend* gallery template and run it (no-code rules, no `eval`).
- **Stress Test** — run COVID Crash + 2022 Rate-Hike on the basket.
- **Offline UX** — stop the backend and open Saved Reports to show the friendly **Backend offline** panel with **Retry** (graceful, not a crash).
- **Theme** — switch the accent in Settings to show the whole app re-skin instantly.

## Tips
- Keep the window at ~1440×900 for clean charts.
- Pre-run steps 3–6 so recents/search have content on camera.
- If a run shows few/zero trades, that's expected for long-only in a downtrend —
  mention it rather than hiding it; it's an honest behavior, not a bug.
