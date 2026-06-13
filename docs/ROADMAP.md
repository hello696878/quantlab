# QuantLab — Roadmap

This document tracks what has been built and what is planned.

The guiding principle: **build in small, usable phases**. Each phase produces something that works before moving to the next.

---

## Completed Phases

### Phase 0 — Project Setup ✅

- Clean repository structure
- FastAPI skeleton with `/health` endpoint
- pytest test infrastructure
- `requirements.txt` and local run instructions
- README with setup guide

### Phase 1 — Backend MVP ✅

Core backtesting engine:

- `data.py`: yfinance OHLCV download layer
- `strategies.py`: SMA Crossover signal generation with lookahead-bias prevention (shift by 1)
- `backtest.py`: vectorised P&L engine, transaction cost model, buy-and-hold benchmark, trade log
- `metrics.py`: Total Return, CAGR, Sharpe ratio, Sortino ratio, Calmar ratio, Max Drawdown, Volatility, Win Rate
- `schemas.py`: Pydantic request/response models
- Full test suite for all backend modules

### Phase 2 — Frontend Dashboard ✅

- Next.js 14 + React 18 + TypeScript + Tailwind CSS
- `BacktestForm` component: strategy/parameter selection
- `EquityCurveChart`: strategy vs. buy-and-hold comparison (Recharts)
- `DrawdownChart`: drawdown visualisation
- `MetricsGrid`: performance metrics display
- `TradeTable`: trade log table
- `api.ts`: typed fetch wrappers for all backend endpoints
- Next.js rewrites: `/api/*` proxy to backend

### Phase 3 — Strategy Expansion ✅

Additional strategies added to the backend and frontend:

- RSI Mean Reversion (long-only, oversold entry / exit threshold)
- Bollinger Band Mean Reversion (lower band entry, middle or upper band exit)
- Time-Series Momentum (trailing return threshold, configurable entry/exit)
- Volatility Breakout (rolling high + range multiplier, rolling mean exit)
- Pairs Trading / Statistical Arbitrage (z-score of log-price spread, dollar-neutral two-leg)

Full test coverage for each strategy (signals + API endpoint).

### Phase 4 — Research Tools ✅

Advanced analysis tools built on top of the core backtest engine:

- **SMA Parameter Sweep**: grid search over fast/slow window combinations, ranked results table
- **SMA Train/Test Out-of-Sample Validation**: IS parameter selection → OOS evaluation, degradation metrics, `oos_collapsed` flag
- **SMA Walk-Forward Optimization**: rolling window optimisation, stitched OOS equity curve, parameter stability summary
- **Strategy Comparison**: run all five single-asset strategies on the same ticker, ranked by Sharpe/CAGR/Calmar/drawdown

All research tools reuse `run_backtest` and `compute_metrics` — no separate engine.

### Phase 5 — Engineering Infrastructure ✅

- **Numeric input UX fix**: all form fields store raw string state, validate on submit, support empty fields and partial decimals (`"0."`, `"-"`, `""`) without auto-reset
- **GitHub Actions CI**: `backend-tests` (pytest) and `frontend-build` (next build) on every push/PR to `main`
- **Docker Compose**: `docker compose up --build` starts both services; `BACKEND_URL` baked at frontend build time for correct internal Docker DNS routing
- **Comprehensive README and portfolio documentation**

### Phase 6 — CSV Upload Backtesting ✅

- `POST /backtest/csv` — upload a price CSV and run any single-asset strategy
  (SMA Crossover, RSI, Bollinger Band, Momentum, Volatility Breakout)
- Flexible column detection: date (`date` / `datetime` / `timestamp`) and
  close (`close` / `adj_close` / `adjusted_close`); optional OHLCV ignored
- Reuses the existing strategy + backtest + metrics stack unchanged; Pairs
  Trading excluded (needs two assets)
- New **CSV Backtest** workspace in the dashboard with drag-and-drop upload
- Full parser + API test coverage

### Phase 6 — Custom Strategy Builder v1 ✅

- `POST /backtest/custom` — no-code, long-only, single-asset rule builder
- Operands: `close`, numeric constant, and indicators `sma` / `rsi` /
  `bb_upper` / `bb_middle` / `bb_lower` / `momentum`; operators `> >= < <=`
- Entry/exit rule lists combined with ALL (AND) or ANY (OR) logic; stateful
  long/flat machine with a one-bar forward shift (no lookahead)
- **Safe by construction**: operands resolved through a fixed dispatch table
  and evaluated with vectorised pandas — no `eval`/`exec`, no user code run
- Indicators reuse the built-in `compute_rsi` / `compute_bollinger_bands` math
- New **Strategy Builder** dashboard workspace; full evaluator + API tests

### Phase 6 — Saved Custom Strategy Templates ✅

- `custom_strategy_templates` SQLite table + `/custom-strategies` CRUD
  (POST / GET list / GET id / PUT / DELETE)
- Stores reusable **strategy definitions** (rules + AND/OR logic + name,
  description, tags) — never backtest results
- Reuses the validated `CustomRule` schema (max 10 entry / 10 exit rules,
  whitelisted indicators/operators) — **no `eval`, no arbitrary code stored**
- Strategy Builder integration: save, browse, load, update, delete templates;
  loaded rules repopulate the builder and can be re-run on any ticker/dates
- Full CRUD + validation + round-trip test coverage

### Phase 6 — Import / Export Strategy Templates ✅

- `GET /custom-strategies/{id}/export` — portable, self-describing JSON
  (`schema_version` + `type` markers; excludes id / created_at / updated_at)
- `POST /custom-strategies/import` — validates the envelope and reuses the
  whitelisted `CustomRule` schema, then persists a new template
- Rejects wrong `type`, missing `schema_version`, empty name, non-whitelisted
  indicators/operators, and >10 rules per list — **validated data, never code**
- Strategy Builder: per-template **Export** button + an **Import Template**
  file picker; imported templates appear in the saved list and can be run
- Full export/import + round-trip + security test coverage

### Phase 6 — Strategy Template Gallery ✅

- `GET /custom-strategy-gallery` (+ `/{template_id}`) — built-in, read-only
  curated strategy templates served as **static, pre-validated data** (not in
  SQLite, not backtest results)
- Five built-in templates: SMA Trend Filter, RSI Mean Reversion,
  Momentum + Trend, Bollinger Mean Reversion, Defensive Trend Strategy
- Each carries `difficulty` + `category` metadata and is constructed through
  the same `CustomRule` schema as the live builder — **no `eval`, no
  executable formula strings; unknown indicators/operators are impossible**
- Strategy Builder **Gallery** panel: cards with rule summaries, Load (into
  builder) and Save to My Templates
- Tests assert every template validates, has entry+exit rules, generates
  signals on deterministic data, and matches the saved-template shape

### Phase 7 — Multi-Asset Portfolio Backtesting v1 ✅

- `POST /portfolio/backtest` — equal-weight, long-only, fully-invested
  portfolio (1–20 assets); target weight 1/N
- Rebalance cadence: none (drift / buy & hold) or monthly / quarterly / yearly
  on the first trading day of each new period
- **Turnover-based** rebalancing cost: `cost = equity × Σ|target−drift| ×
  bps/10000`; no initial-purchase cost (equity starts at initial_capital)
- Assets aligned on common trading days; SPY buy-and-hold benchmark when
  available (else first-ticker fallback, documented)
- Response: metrics + benchmark metrics, equity curve, drawdown, per-day
  weights, and a rebalance-events log
- New **Portfolio Backtest** workspace; `portfolio.py` logic module reusing
  `compute_metrics`; full unit + API test coverage
- **Not** portfolio optimization — no optimisation, shorting, or leverage yet

### Phase 7 — Portfolio Optimization v1 ✅

- `POST /portfolio/optimize` — long-only (`wᵢ ≥ 0`, `Σw = 1`) weight
  optimization over historical returns
- Objectives: equal_weight, **min_volatility** (minimise `wᵀΣw`), **max_sharpe**
  (maximise `(wᵀμ − r_f)/√(wᵀΣw)`); solved with **SciPy SLSQP** (added `scipy`
  to requirements)
- Annualised expected returns + covariance (252-day); optimized weights are
  backtested buy-and-hold and compared to equal weight (metrics, equity,
  drawdown)
- Portfolio workspace gains an **Optimization** tab alongside the equal-weight
  backtest; both share the dark UI
- **In-sample only** — optimized and backtested on the same window; explicit
  overfitting warning in the API response and UI. Not investment advice.
- Full optimizer unit tests (constraints, min-vol/max-sharpe behaviour) + API
  tests

### Phase 7 — Walk-Forward Portfolio Optimization ✅

- `POST /portfolio/walk-forward-optimize` — rolling, **out-of-sample** weight
  optimization (train window → optimize → apply fixed weights to the next test
  window → step → repeat → stitch the OOS test windows)
- **No data leakage**: each window's weights come only from its training slice
  and are applied to strictly later dates (verified by tests, incl. a
  future-data-mutation invariance test)
- Turnover-based transaction cost at each window boundary (entry-from-cash for
  the first window), deducted at the start of the test window; equal-weight
  benchmark rebalanced on the same boundaries
- Response: per-window detail (dates, weights, train stats, OOS `test_metrics`,
  turnover, cost), stitched OOS equity vs benchmark, drawdown, aggregate
  metrics, and a weight-stability summary
- Portfolio workspace gains a **Walk-Forward Optimization** tab (third tab)
- Reduces — but does not eliminate — overfitting; still historical-assumption
  dependent. Not investment advice.
- Full unit (`portfolio.py` walk-forward) + API test coverage

### Phase 7 — Efficient Frontier Visualization ✅

- `POST /portfolio/efficient-frontier` — risk–return space of a long-only
  universe from annualised expected returns + covariance (252-day)
- Samples N random long-only portfolios (Dirichlet, deterministic seed),
  locates equal-weight / min-volatility / max-Sharpe portfolios, and traces a
  long-only efficient-frontier curve (min vol per target return, SLSQP)
- Response: per-asset expected returns + covariance matrix, random portfolios
  (return/vol/Sharpe/weights), the three special portfolios, and frontier curve
- Portfolio workspace gains an **Efficient Frontier** tab — Recharts scatter
  plot (x = volatility, y = return, Sharpe/weights in tooltip) with the special
  portfolios highlighted, plus weight cards
- **Historical, in-sample** — descriptive only, not a forecast or advice
- Full unit + API test coverage

### Phase 7 — Portfolio Risk Dashboard ✅

- `POST /portfolio/risk-dashboard` — asset/portfolio risk diagnostics from
  historical daily returns (252-day annualisation)
- Per-asset annual return + volatility; correlation matrix (`returns.corr()`)
  and annualised covariance matrix
- Equal-weight portfolio return/volatility + **diversification ratio**
  (weighted-avg vol ÷ portfolio vol)
- Correlation diagnostics: average / most / least correlated pairs
- **Risk contribution** decomposition for the equal-weight portfolio
  (marginal `Σw/σ_p`, component `wᵢ·marginalᵢ`, percent — sums to ~1)
- Portfolio workspace gains a **Risk Dashboard** tab: asset table, correlation
  heatmap (cyan→amber→red), diagnostic + diversification cards, risk-contribution
  bars, collapsible covariance table
- Historical estimates may not persist; not investment advice
- Full unit + API test coverage

### Phase 7 — Portfolio Stress Testing / Scenario Analysis ✅

- `POST /portfolio/stress-test` — static long-only portfolio (equal or custom
  weights) evaluated across historical stress windows vs a benchmark
- Per scenario: total return, max drawdown, annualised volatility, worst/best
  day, excess return vs benchmark, scenario correlation matrix, and rebased
  portfolio + benchmark equity curves
- Built-in presets (COVID, 2022 rate hikes, 2018 Q4, 2011 Euro crisis, 2008
  GFC) plus custom user-defined scenarios; full-period summary included
- Validates weights (present for all tickers, ≥0, sum 1), scenario dates, and
  rejects scenarios that don't overlap the data
- Portfolio workspace gains a **Stress Test** tab: comparison table, selectable
  scenario equity curve, correlation heatmap, full-period metrics
- Static weights, no rebalancing/leverage; results are historical, not a
  forecast or investment advice
- Full unit + API test coverage

### Phase 7 — Factor Exposure / Regression Analysis ✅

- `POST /portfolio/factor-analysis` — OLS regression of portfolio daily returns
  on ETF factor-proxy returns (`r_p = alpha + Σ beta_k·factor_k + residual`)
- Pure NumPy least squares (intercept included) — no statsmodels, no external
  Fama-French data
- Returns alpha (daily + annualised), per-factor betas, R², annualised residual
  volatility, factor correlation matrix, actual-vs-fitted return series +
  equity curves, and diagnostics (strongest ± exposures, multicollinearity
  warning via rank check)
- Default **Core ETF Factors** preset (market/tech/small-cap/bonds/gold) plus
  editable custom factors; equal or custom long-only portfolio weights
- Portfolio workspace gains a **Factor Analysis** tab: summary cards, beta
  table, factor correlation heatmap, actual-vs-fitted equity chart
- Historical / proxy-dependent; collinear factors flagged. Not investment advice
- Full unit (known-beta recovery, collinearity) + API test coverage

### Phase 8 — Research Report Export v1 ✅

- Client-side **Markdown** research-report generation — no backend, no stored
  files, no PDF rendering (`frontend/src/lib/reportExport.ts`)
- Reusable **Export Report** button (`ExportReportButton.tsx`) wired into the
  single backtest, saved-backtest detail, and the portfolio Equal-Weight
  Backtest, Static Optimization, Risk Dashboard, Stress Test, and Factor
  Analysis views
- Reports include metadata, executive summary, parameters/weights, a
  performance-metrics table, equity-curve summary (start/end/peak, final +
  worst drawdown), trades/events summary, and a risk/caveats disclaimer
- Extensible builder design (one builder per analysis type); embedded chart
  images are deferred to future work
- Frontend-only (`tsc --noEmit` clean); no backend changes

### Phase 8.2 — PDF Research Report Export v1 ✅

- Browser-based **PDF export** — no server-side PDF rendering, no new
  dependency. The existing Markdown report is the single source of truth
- `frontend/src/lib/printReport.ts` converts the report Markdown to clean,
  HTML-escaped, print-friendly HTML (headings, tables, lists, blockquotes)
- `PrintableReportModal.tsx` portals a white-background preview to `<body>`;
  **Print / Save as PDF** calls `window.print()`
- `ExportReportButton.tsx` now renders both **Export Report** (Markdown) and
  **Export PDF** — so every existing export location gains PDF automatically
- `@media print` rules in `globals.css` hide the dark app chrome / nav / buttons,
  force a light page, and add `@page` margins + table/heading page-break control
- Text/table only (no chart images); frontend-only (`tsc --noEmit` clean)

### Phase 8.3 — Saved Reports / Report Gallery ✅

- Local **SQLite** persistence for generated reports (Markdown text + metadata
  only — **no PDF binaries stored**), consistent with Saved Backtests
- New `saved_reports` table (`db.py`) + parameterised CRUD module
  (`saved_reports.py`); all tests use a temporary DB
- Endpoints: `POST/GET/GET{id}/PUT{id}/DELETE{id} /saved-reports` with
  validation (non-empty title / report_type / markdown_content, enum
  source_type, date ordering, 404 on missing, 422 on invalid)
- Report generators now attach structured save-metadata to each `Report`;
  `ExportReportButton.tsx` adds a **Save Report** button beside the export
  buttons (every export location), opening `SaveReportModal.tsx`
- New **Saved Reports** workspace: `SavedReportsList.tsx` +
  `SavedReportDetail.tsx` (renders Markdown via the existing HTML-escaping
  renderer — no `dangerouslySetInnerHTML` of unsanitised text, no script
  execution), with Download Markdown / Print-to-PDF / Delete
- Backend `pytest -q` green (793 passed, incl. the 32-test saved-reports
  suite); frontend `tsc --noEmit` clean; no quant logic changed

### Phase 8.4 — Branded Report Templates ✅

- `ReportTemplate` enum (`standard` / `executive_summary` / `quant_tear_sheet`
  / `risk_report`) selectable wherever reports are exported; the choice applies
  to Markdown download, PDF/print, and Save Report
- `reportExport.ts` refactored around a structured `ReportDoc` model +
  `renderReport(doc, template)`; each builder populates one doc and the four
  templates pick/trim sections from it (Standard output preserved)
- Risk Report shows only the risk sections the result type actually provides
  (volatility, max/worst drawdown, stress, factor exposures, correlation, risk
  contribution) — **missing data is never fabricated**
- `ExportReportButton.tsx` gains a template `<select>`; analyses that cannot
  fill a template don't offer it (Risk Dashboard / Factor Analysis omit the
  Tear Sheet). Saved reports record the template in `metadata.report_template`
- Frontend-only (`tsc --noEmit` clean); no backend analytics or quant logic
  changed (backend `pytest -q` still green, 797 passed)

### Phase 9.1 — App Settings / Preferences ✅

- Local, single-user preferences in **`localStorage`** (no account, no cloud
  sync): `lib/settings.ts` (typed `AppSettings`, defaults, validating
  load/save/reset, `resolveDateRange`, `applyAccent`) + `SettingsPanel.tsx`
- Settings: default initial capital, transaction cost bps, benchmark ticker,
  risk-free rate, default date range, annualization convention, theme accent
  (cyan/blue/emerald/violet/amber), default report template
- Prefills **newly mounted** forms only (mount-effect, SSR-safe) so it never
  overrides in-progress edits: single Backtest, Portfolio Backtest / Optimize /
  Stress Test, and the report template selector
- Theme accent applies live via existing `[data-accent]` CSS (violet/amber
  added) + a pre-paint script in `layout.tsx` to avoid a flash on reload
- Annualization convention is now applied to new single-asset Backtest and
  Strategy Comparison runs (`trading_days_252`, `crypto_365`, or `auto`);
  portfolio analytics remain on the existing 252 trading-day convention
- Affects annualized metrics only (CAGR, Calmar, volatility, Sharpe, Sortino);
  trades, equity curves, total return, and drawdown are unchanged

### Phase 9.2 — Neon Quant Terminal Theme System ✅

- Global CSS-variable theme: one `data-accent` token re-skins the **whole**
  product (was sidebar-only). New tokens in `globals.css`: `--accent-soft/
  -softer/-muted/-line/-border/-text/-ink`, `--on-accent`, `--accent-glow/
  -2-rgb/-hue`, `--panel-glow`, `--focus-ring`, `--neon-line`, `--grid-line`,
  `--chart-primary/-secondary`
- **Accent reach via utility remap:** the app's `blue-*` Tailwind classes
  (buttons, focus rings, inputs, strategy tabs, links, badges, selected rows,
  quick-picks) are routed through accent tokens in one CSS block — themes all
  ~26 components with no per-file edits
- Neon detailing: sidebar active glow + left bar, top-bar accent rule + neon
  divider, card accent-tinted border + restrained hover glow, primary-button
  glow, on-screen report header strip
- Charts: `lib/useAccentColors.ts` resolves `--accent-rgb`/`--accent-2-rgb` to
  concrete `rgb()` and re-reads on a `MutationObserver`; `EquityCurveChart`
  primary line = accent, benchmark = accent-2 (restyles live, no remount)
- Accents: cyan / blue / emerald / violet / amber + optional **risk** (red,
  deepens `--neg` so losses stay legible). Semantic colors (pos/neg/warn + API
  status) intentionally **left fixed** across every accent
- Settings switch applies live + persists in `localStorage` (reload-safe);
  reset restores default. Frontend-only; no backend / API / quant changes;
  `tsc --noEmit` clean; dev server compiles and serves 200

### Phase 9.3 — Neon Chart & Data Visualization System ✅

- Shared neon chart toolkit: `components/charts/chartTheme.ts` (grid/axis/muted
  benchmark/semantic-danger constants + glow widths) and
  `components/charts/NeonTooltip.tsx` (dark-glass tooltip, accent or semantic
  border + glow, hides helper series)
- **`EquityCurveChart`** rebuilt as a Recharts `ComposedChart`: accent→transparent
  gradient `Area` fill (gridlines still visible) + a wide low-opacity accent
  glow underlay behind a crisp accent line (duplicate-line technique, no costly
  SVG filters) + muted slate **dashed** benchmark + neon tooltip. Used by ~12
  views, so single/CSV/builder/portfolio/optimize/walk-forward/stress/factor/
  saved/train-test equity charts all upgrade at once
- **`DrawdownChart`** keeps semantic **red** (area + subtle red glow line + a
  danger-toned neon tooltip) — drawdown is never recolored to the accent
- Efficient-frontier line/dots/glow follow the accent (reference markers stay
  distinct); parameter-sweep best cell gets an accent outline + inner glow;
  risk correlation matrix renders as rounded neon tiles (red glow on
  concentrated pairs, cyan on diversifying) — all still readable
- Charts restyle **live** on accent change via `useAccentColors` (verified:
  switching accent updates strategy strokes to the new `rgb()` with no remount;
  benchmark/drawdown stay fixed). Fixed a Recharts legend crash by supplying an
  explicit legend `payload` (with inner `strokeDasharray`) so helper series are
  excluded cleanly
- Frontend-only; no backend / API / quant changes; `tsc --noEmit` clean;
  verified in a running dev server with real yfinance data

### Phase 9.4 — Calibrate Strategy Default Parameters ✅

- Demo-friendly first-run defaults (usability, not performance; no quant-logic
  change). Old → new: SMA `50/200 → 20/100`; RSI oversold/exit `30/50 → 35/55`;
  Bollinger `2.0σ → 1.8σ`; momentum window `126 → 63`; volatility-breakout
  multiplier `1.0 → 0.3`; pairs entry-z `2.0 → 1.5` (KO/PEP kept). Values were
  sanity-checked as demo-friendly starting points, not return-optimized settings
- Synced everywhere: `page.tsx` `DEFAULT_*_PARAMS`, `CsvBacktestPanel` `DEFAULTS`,
  and the backend `schemas.py` `Field(default=…)` (docs/examples stay consistent;
  explicit user inputs unaffected). Strategy Builder starter (SMA 20/50) was
  already demo-friendly — left as-is; gallery templates keep their classic params
- One-click **presets** added to `BacktestForm` for SMA / RSI / Bollinger /
  momentum (incl. the classic long-term variants), plus a "defaults are
  demo-friendly, not optimized — validate with the research tools" notice.
  Numeric input editing behaviour unchanged; parameters stay user-editable
- New `backend/tests/test_default_params.py` (14 tests): synthetic deterministic
  prices (no live yfinance) confirm every default returns a valid backtest,
  SMA/RSI defaults generate trades, and the calibrated values are locked in.
  Updated the one CSV test that asserted the old SMA defaults
- Backend `pytest -q` green (**811 passed**); frontend `tsc --noEmit` clean

### Phase 9.4.1 — Strategy Defaults & Signal Diagnostics v2 ✅

- **Root-caused the persistent zero-trade Volatility Breakout** (esp. in Strategy
  Comparison): the comparison endpoint hard-coded the *old* params (incl. VB
  `breakout_multiplier=1.0`, which could be too strict for demos) instead of
  the calibrated defaults.
  Aligned all five comparison strategies with the demo-friendly defaults
  (SMA 20/100, RSI 35/55, BB 1.8σ, momentum 63, VB 0.3) and lowered the
  comparison `min_bars` 202 → 102. No strategy math changed (VB entry/exit rule
  audited and left intact — only the multiplier was too strict)
- Sanity-checked on representative demo assets; zero trades remain possible
  when market conditions do not trigger a strategy's entry rule
- **VB presets** added to `BacktestForm` (Responsive 0.2× / Balanced 0.3× /
  Conservative 0.5×), completing the preset set for all preset-able strategies
- **No-signal diagnostics** (`SignalDiagnostics.tsx`): a non-error info card on
  the Backtest results — "0 trades, stayed in cash…" (amber) or "very few
  trades…" (muted), with a long-only-downtrend note for trend strategies.
  Strategy Comparison tags 0-trade rows with a muted "No signal · stayed flat"
  (row still shown), plus a long-only explainer under the table
- **Long-only behaviour explained** in the UI (Backtest + Comparison) and docs:
  staying flat in downtrends is expected, not a bug; Pairs Trading for
  non-directional exposure; no short selling yet
- Backend changed (comparison params + min_bars + 2 test assertions /
  docstrings); no API contract change. `pytest -q` green (**811 passed**);
  frontend `tsc --noEmit` clean

### Phase 9.5 — Long / Short Strategy Modes ✅

- New `position_mode` (`long_only` default / `short_only` / `long_short`) for
  **SMA Crossover, Momentum, Volatility Breakout**. No leverage (|position| ≤ 1),
  no margin/options; a short earns `−1 × asset_return`
- Engine: `run_backtest` already computed `position·return` and `|Δposition|`
  cost, so only the position-range guard was relaxed (now [−1, 1]) and the trade
  log extended → **BUY / SELL / SHORT / COVER / FLIP_TO_LONG / FLIP_TO_SHORT**.
  Long-only (position ∈ {0,1}) math + trade log are byte-for-byte unchanged
- Signals: each function gained a mode-aware, symmetric state machine
  (`long_only` reduces *exactly* to the original). Volatility Breakout adds a
  symmetric downside-breakdown short (prior rolling low − mult×range)
- Schema: `PositionMode` + `position_mode` on the three requests (and echoed on
  `BacktestResponse`); invalid mode → 422. Frontend: types, a **Direction**
  segmented control in `BacktestForm` (long-only strategies don't show it),
  trade-table colours/labels for short/flip actions, and a mode tag in the
  results summary
- New `backend/tests/test_position_modes.py` (22 tests): engine short returns +
  flip turnover + actions, signal mode-mapping + long-only identity, API echo /
  valid actions / 422. `pytest -q` green (**833 passed**); `tsc --noEmit` clean
- Verified live on real SPY 2015–2023: long-only returns unchanged; short/
  long-short produce the expected SHORT/COVER/FLIP actions and inverse P&L
- RSI / Bollinger left long-only for now (clean symmetric short = future work)

### Phase 9.5.1 — Long/Short Mode UX & Diagnostics ✅

- Confirmed `long_only` stays the default everywhere (forms, schema, Strategy
  Comparison); requests omitting `position_mode` and old saved backtests (params
  without the field) load as long-only
- UX wording near the Direction control: per-mode helper text (long-only stays
  in cash; short-only is experimental/no borrow costs; long/short is an
  **advanced research mode** that may underperform trending assets) plus a
  "short-selling costs, borrow fees, margin calls, liquidation not modelled" note
- **Direction Diagnostics**: optional `BacktestDiagnostics` on `BacktestResponse`
  computed in the engine (`compute_position_diagnostics`) — long/short trade
  counts, % time long/short/cash, pre-cost gross long & short return (exact
  multiplicative decomposition), short contribution, turnover. New
  `ShortModeDiagnostics.tsx` card renders for short-enabled runs and says whether
  shorts helped or hurt
- Strategy Comparison labelled "uses long-only mode by default" + "long/short is
  not guaranteed to improve performance — useful for studying bearish signals"
- Reports: short-selling caveat added when `position_mode` is short/long-short,
  `position_mode` shown in metadata table + saved-report metadata
- Saved backtests preserve `position_mode` (in `params`); `SignalDiagnostics`
  made mode-aware (no misleading "long-only" note on short runs)
- Backend additive only (optional field; no breaking change). New diagnostics
  tests; `pytest -q` green (**836 passed**); `tsc --noEmit` clean

### Phase 9.5.2 — Complete Long/Short UX Integration ✅

- Reusable, prominent **`ShortSellingWarning`** (amber, non-blocking) shown in
  three places for short/long-short runs: near the Backtest mode selector, on
  the results, and in Strategy Comparison (reports already carry the caveat)
- **Strategy Comparison now supports `position_mode`** (backend + UI): a
  Direction selector (default long-only) applies the mode to SMA / Momentum /
  Volatility Breakout; RSI & Bollinger stay long-only and are **tagged
  "long-only"** in the table. Response echoes the comparison mode and a
  per-strategy applied `position_mode` (additive, non-breaking). Header shows
  the active mode; invalid mode → 422
- Backtest form: unsupported strategies (RSI / Bollinger) now show a small
  "Long-only strategy" label instead of just hiding the selector
- Diagnostics card (`ShortModeDiagnostics`) unchanged from 9.5.1 (long/short
  trade counts, time long/short/cash, gross long/short contribution, turnover);
  rendered alongside the warning on short runs
- Saved backtests preserve `position_mode`; old records without it load as
  long-only; export/report still works (verified)
- Backend additive only. New comparison-mode tests (default long-only, mode
  applied to supported only, 422). `pytest -q` green (**840 passed**);
  `tsc --noEmit` clean; verified live on SPY (short comparison: SMA/Mom/VB go
  short, RSI/BB stay long-only)

---

### Phase 10.1 — Dashboard Home / Command Center ✅

- New **Home / Command Center** workspace (`HomeDashboard.tsx`) added as the
  **default view** on load, with a **Home** sidebar item. Existing views are
  untouched.
- **Hero** (title + subtitle + Local-first / FastAPI / Next.js / SQLite /
  Research-only badges), **Quick Actions** grid (Run Backtest, Upload CSV, Build
  Custom Strategy, Portfolio Lab, Saved Backtests, Saved Reports, Export Report)
  wired to the same `handleNav` the sidebar uses.
- **Recent Saved Backtests** and **Recent Saved Reports** fetched live from
  `GET /saved-backtests` and `GET /saved-reports` (latest 5, newest first),
  clickable to open the full record; honest **empty states** when none exist —
  no fake rows.
- **System Status** (real `GET /health`, local mode, live saved counts) and a
  **Feature Map** (Strategy Lab / Research Tools / Portfolio Lab / Reporting).
- **No backend changes** — reuses existing endpoints; counts computed
  frontend-side. Neon terminal theme, responsive laptop layout. `tsc --noEmit`
  clean.

---

### Phase 10.2 — Onboarding / Guided Demo Mode ✅

- **Welcome to QuantLab** onboarding card on the Command Center: primary
  actions (Run Demo Backtest, Try Portfolio Lab, Build a Custom Strategy, Open
  Saved Reports) plus a row of **guided demo presets**.
- **Demo presets** (`lib/demoPresets.ts`): Demo Backtest (SPY · SMA 20/100),
  Demo Crypto Momentum (BTC-USD · Momentum), Demo Portfolio Risk and Demo
  Efficient Frontier (SPY/QQQ/GLD/TLT — match the panels' existing defaults,
  rf 0.02 / 2,000 portfolios), Demo Strategy Builder (gallery templates).
- **Prefill, never auto-run**: clicking a demo navigates + prefills the form and
  shows a *"Demo parameters loaded. Click Run to execute."* banner. Results come
  only from the real backend API after the user clicks Run — **no fabricated
  data**. `PortfolioWorkspace` gained an optional `initialTab` so demos land on
  the right sub-tool.
- **Dismissible onboarding** persisted in `localStorage` ("Hide onboarding" /
  "Show welcome guide") and a **quick-start checklist** (run / save backtest,
  export report, view portfolio risk, build strategy) tracked with local flags
  set from real user actions (`lib/onboarding.ts`; checklist refreshes via a
  same-tab event).
- **No backend changes, no new endpoints, no auth/cloud/billing.** Existing
  long_only defaults and every workspace untouched. `tsc --noEmit` clean.

---

### Phase 10.3 — Command Palette / Keyboard Shortcuts ✅

- **`CommandPalette.tsx`**: a portalled, dark-glass modal opened with
  **Ctrl/Cmd + K** (toggle) or the new TopBar **Search** chip. Search input,
  grouped + filtered list, **↑/↓** to move, **Enter** to run, **Esc** / click
  outside to close. Footer + TopBar show the platform-correct ⌘K / Ctrl K hint.
- **Commands** (built in `page.tsx`, all reusing existing handlers — no second
  router): Navigation (13 views incl. research tools), Guided demos (from
  `DEMO_PRESETS` — no duplication), Portfolio tools (7 sub-tabs via the
  `initialTab` mechanism), and a conditional *Export current backtest report*
  shown only when a result exists (no broken commands listed).
- **State-safe**: commands only navigate / prefill (demos still never auto-run);
  Ctrl+K is global but only opens an overlay, so no form values are lost and no
  saved data is mutated. `e.preventDefault()` stops the browser's native Ctrl+K.
- **No backend, API, auth, or fake data changes.** `tsc --noEmit` clean.

---

### Phase 10.4 — Global Search in the Command Palette ✅

- The Ctrl/Cmd+K palette now searches **commands + real local resources** in one
  list: Navigation, Guided demos, Portfolio/Research tools, **Saved Backtests**,
  **Saved Reports**, and **Strategy Templates** (saved *My Templates* + built-in
  gallery).
- **`lib/search.ts`**: tiny dependency-free search — `tokenize`, `buildHaystack`
  (null-safe), `searchItems` (AND-substring match, preserves grouped order). No
  external library.
- **Data**: fetched lazily on first open via `Promise.allSettled` over
  `/saved-backtests`, `/saved-reports`, `/custom-strategies`,
  `/custom-strategy-gallery` and cached; results carry display fields (ticker ·
  strategy · Sharpe/CAGR, source_type · tickers, template tags). **No fake
  data.**
- **Resilient**: partial/total fetch failure never crashes — commands still
  work, a *"Saved resources unavailable while backend is offline"* note shows,
  and an all-failed first open is retried on the next open. Missing optional
  fields render safely (null-safe haystack/subtitle builders).
- **Actions**: backtest → Saved Backtests detail; report → Saved Reports detail;
  saved/gallery template → Custom Strategy Builder with the template loaded
  (new `initialSavedTemplateId` prop mirrors the existing gallery loader).
  Selecting an item only navigates/loads — no form is mutated otherwise.
- **No backend / API / auth / fake-data changes.** `tsc --noEmit` clean.

---

### Phase 10.4.1 — Offline UX for Global Search & Saved Resources ✅

- **Error classifier** (`classifyApiError` in `lib/api.ts`): normalises any
  thrown API error into `offline / server / not_found / validation / unknown`
  with a `backendUnavailable` flag (status 0 *or* ≥500 — the dev proxy surfaces
  an unreachable backend as a 500). Original messages are preserved, not
  swallowed. Plus `isBackendUnavailable`.
- **`BackendOfflinePanel.tsx`**: reusable amber neon info card — "Backend
  offline", reassurance that local SQLite data is safe, the exact `uvicorn`
  start command, and **Retry** / **Go to Command Center** actions.
- **Saved Backtests & Saved Reports** (list + detail) now branch on the
  classifier: a backend-unavailable failure shows the friendly panel (with a
  working in-place Retry) instead of a raw "HTTP 500"; genuine 4xx errors keep
  the concise red message. `onGoHome` wired from `page.tsx`.
- **Command Palette**: on a *total* resource-fetch failure it now **drops the
  cache** (never shows stale saved rows) and shows a grouped *"Saved resources
  unavailable while backend is offline"* card; commands/demos keep working.
  Each list is still settled independently (one failure can't break the rest).
- **No backend, schema, or fake-data changes.** Global search retained.
  `tsc --noEmit` clean.

---

### Phase 10.5 — Global Toasts & Error Boundary ✅

- **Toast system**: module-level store (`lib/toast.ts`) so any code can fire a
  toast without context/prop-drilling; a `useSyncExternalStore` adapter
  (`hooks/useToasts.ts`), a portalled `ToastViewport` (bottom-right, semantic
  colors, auto-dismiss + hover-pause, manual close, optional action), and a thin
  `ToastProvider`. `toast.success/error/warning/info` + a de-duplicated
  `notifyBackendOffline` (collapses repeated offline errors into one toast,
  suppressed briefly after dismissal).
- **App-level error boundary** (`AppErrorBoundary`, class component): catches
  unexpected render errors and shows a friendly *"Something went wrong"* panel
  (Reload app / Go to Command Center + collapsible technical details) instead of
  a crash. Wrapped around the app in `layout.tsx` with `ToastProvider`
  (SSR-safe: viewport mounts client-side, store has a server snapshot → no
  hydration mismatch).
- **Actions now toasting**: save/delete backtest & report, markdown export /
  print preview, custom-strategy template save/update/delete/import/export,
  CSV backtest complete / invalid CSV, demo parameters loaded, and a consistent
  backend-offline notification (with Retry) across save/delete/load/run paths.
  Inline error panels and the offline panel are retained as context.
- **No backend, API, schema, or fake-data changes.** `tsc --noEmit` clean.

---

### Phase 10.6 — Loading Skeletons & Empty/Offline/Error State Polish ✅

- **Shared `components/ui/` primitives**: `LoadingSkeleton` (`Skeleton`,
  `SkeletonText`, `SkeletonCard`, `SkeletonTable` — shimmer via a new
  `.skeleton` keyframe, reduced-motion aware), `EmptyState` (title + description
  + action buttons), `OfflineState` (canonical amber backend-offline panel —
  `BackendOfflinePanel` is now a thin re-export), and `ErrorState` (title +
  message + Retry + collapsed technical `<details>`).
- **Applied consistently**: Saved Backtests & Saved Reports (list = skeleton
  table / detail = skeleton blocks), Command Center recents (compact skeleton
  cards + compact offline/empty with actions), custom-strategy **My Templates**
  and the **strategy gallery** (skeleton cards + offline/error), and the Command
  Palette "No results" empty state. Each list/detail gained an in-place **Retry**.
- **Empty states with next actions**: e.g. *No saved backtests yet → Run
  Backtest*, *No saved reports yet → Run a Backtest*, *No saved strategy
  templates yet*. No fake/placeholder rows anywhere.
- **A11y/UX**: skeletons match content size to limit layout shift; retry buttons
  are real `<button>`s (keyboard accessible); offline copy reassures data is
  safe in local SQLite.
- **Frontend-only. No backend, API, schema, or fake-data changes.**
  `tsc --noEmit` clean.

---

### Phase 10.7 — Final Portfolio Polish & README Refresh ✅

- Documentation-only pass to make the repo accurately represent the current
  platform. **No code, quant logic, API, or feature changes.**
- **README** rewritten/refreshed: new local-first one-liner + hero, a
  categorized **Features at a glance** table (Strategy Research / Custom Strategy
  Lab / Portfolio Lab / Reporting / Product Experience), updated tech stack and
  architecture (now lists `portfolio.py`, `custom_strategy.py`, `saved_reports.py`,
  `custom_strategy_templates.py`, `strategy_gallery.py`), frontend build added to
  Testing, corrected test count (840+), a consolidated **Limitations &
  Disclaimers** section, and an honest near-term **Roadmap**.
- Fixed stale claims: "short selling is not enabled yet" (long/short modes
  exist) and "backtest results are not saved" in `LIMITATIONS.md` (SQLite
  persistence shipped).
- **`docs/`** refreshed: `PROJECT_OVERVIEW.md` (architecture + post-MVP module
  map), `LIMITATIONS.md` (long/short cost model, in-sample portfolio caveats,
  local SQLite / no-auth), and `docs/screenshots/README.md` (current files +
  recommended new captures with suggested parameters).

---

### Phase 11.1 — Release Candidate QA Checklist ✅

- Documentation-only pass to prepare the initial release-candidate package. **No code,
  quant logic, API, or feature changes.**
- New release/QA docs: **`RELEASE_CHECKLIST.md`** (environment / backend /
  frontend / per-feature QA with expected results + demo parameters),
  **`DEMO_SCRIPT.md`** (showcase flow with exact parameters),
  **`KNOWN_ISSUES.md`** (honest, release-facing limitations), and
  **`SCREENSHOT_PLAN.md`** (12 recommended captures with page/params/visible/
  filename).
- README gained a **Documentation** index linking all docs and a **Next stages**
  roadmap (v4.0 RC → quant research depth → commercialization foundation).
- Verified facts used in the QA docs against the code: health endpoint is
  `GET /health`; tests redirect persistence to a temp SQLite DB via a
  `fresh_db`/monkeypatch fixture, guarded by
  `test_tests_use_temp_database_not_real_database`.

---

### Phase 12 — Simulation Realism & Analytics Engines ✅

Post-v4.0 engine series — all optional, backward-compatible, and applied to
single-asset Backtest + Strategy Comparison:

- **12.1 Cost Model** — simple bps / commission + slippage (+ spread) /
  conservative preset; `effective_cost_bps`, total cost, cost-drag reporting
- **12.2 Position Sizing** — full allocation / fixed fraction / volatility
  target / exposure cap; no leverage (`|exposure| ≤ 1`); `average_exposure`
- **12.3 Risk Management** — stop loss / take profit / trailing stop / max
  holding days / combined; close-to-cash only; trade `reason` tags + diagnostics
- **12.3.1 Strategy Comparison simulation settings** — the shared controls
  applied globally to all five strategies, with unsupported-mode labelling
- **12.4 Annualization Convention** — 252 / 365 / auto (ticker-aware), affects
  metric scaling only
- **12.5 Data Provider Abstraction + Data Quality Diagnostics** — yfinance /
  CSV provider metadata, row/gap/duplicate/missing diagnostics, Data Source card
- **12.6 Benchmark & Active Analytics** — buy-and-hold same asset / custom
  ticker / none; alpha, beta, correlation, tracking error, information ratio
- **12.6.1 Benchmark Visualization** — labelled strategy-vs-benchmark equity +
  drawdown overlays and a cumulative excess return chart; saved-backtest reopen
- **12.7 Reproducible Config Hash** — SHA-256 over canonical normalized inputs
  (defaults + legacy forms normalized first); Reproducibility card with copy
  hash / copy canonical config; persisted in saved backtests + reports; CSV
  content fingerprint; local-first (no public URLs; replay-by-hash future)
- **12.8 Robustness Lab v1** — opt-in block-bootstrap Monte Carlo on daily
  strategy returns (deterministic per seed): P(loss), final-return / drawdown /
  Sharpe percentiles, P(beat benchmark), final-return histogram, heuristic A–F
  grade; saved + report integration; deflated Sharpe deliberately null
  (needs trial counts — v2 with PBO + sensitivity heatmaps)
- **12.9 Stability Lab v1** — opt-in SMA fast×slow parameter-sensitivity
  heatmap (full pipeline per cell, 42 default runs, 200 hard cap, summary
  metrics only); selected/best points, heuristic stability score + fragility
  flag; saved + report integration; other strategies clearly unsupported

### Phase 13.0 — Strategy Library v1 ✅

- New **Strategy Library** workspace (sidebar + command palette): index cards
  for the six live strategies + an honest planned/research catalog (no run
  buttons for unimplemented models)
- Per-strategy research pages: overview, hypothesis, signal logic, parameter
  table (defaults / ranges / extreme-value risks), strengths, failure modes,
  cost & risk-interaction notes, Trust Layer validation checklist
- "Run in Backtest Studio" preloads the strategy + demo defaults (never
  auto-runs); model registry (`frontend/src/lib/modelRegistry.ts`) is the
  single metadata source

### Phase 13.1 — Paper Replication Series v1 ✅

- New **Paper Replications** workspace: 8 classic papers (momentum, pairs,
  TSMOM, Fama–French, BAB, Avellaneda–Stoikov, Black–Scholes,
  Black–Litterman) with research question, core idea, original-method summary,
  honest implementation status, data requirements, and limitations
- Three **inspired demos** (Jegadeesh–Titman, Gatev pairs, MOP TSMOM) preload
  Backtest Studio with clear "simplified educational demo — not a full
  replication" labelling; planned papers have no run buttons
- Registry (`frontend/src/lib/paperRegistry.ts`) cross-links Strategy Library
  pages (Related Papers) and powers command-palette commands

### Phase 13.2 — Quant Disasters Series v1 ✅

- New **Quant Disasters** workspace: six risk-education case studies (LTCM,
  1987 portfolio insurance, 2010 Flash Crash, Volmageddon, Archegos,
  FTX/Alameda) with simplified mechanism, "what a naive backtest might miss",
  an honest Trust-Layer checklist (available vs not-yet tools), explicit
  "what QuantLab cannot model yet" lists, and lessons
- Registry (`frontend/src/lib/disasterRegistry.ts`) cross-links Strategy
  Library (Related Disasters) and Paper Replications pages; command-palette
  commands per case
- Educational pages only — neutral phrasing for legally sensitive cases, no
  runnable scenario simulations (scenario stress tests remain future work)

### Phase 13.3 — Dashboard Content Hub ✅

- Command Center upgraded into a unified research hub: hero CTAs (Run
  Backtest / Strategy Library / Paper Replications / Quant Disasters),
  **Trust Layer** explainer grid (Data Quality, Benchmark, Config Hash,
  Robustness, Stability, Report Export), **Content Engine** cards with live
  registry counts, registry-driven **Featured** items (no metadata drift),
  and a **Platform Direction** status panel (Built / Planned / Future —
  honest Blueprint v3 chips)
- Strategy Comparison added to Quick Actions; Trust-Layer workflow commands in
  the palette; all static sections render with the backend offline

### Phase 13.4 — Showcase Demo Script & Screenshot Refresh ✅

- README: Trust Layer + Content Engine feature rows; honest "screenshots
  pending capture pass" note for the post-v4.0 features
- `DEMO_SCRIPT.md` rewritten as a 7-demo showcase flow (Command Center →
  Backtest Studio → Trust Layer → Report → Comparison → Content Engine →
  Portfolio → roadmap close)
- `SCREENSHOT_PLAN.md` refreshed: 16-shot checklist with per-shot setup,
  must-show/avoid lists, and captured/recapture/pending status
- `RELEASE_CHECKLIST.md`: current test counts, Trust-Layer + Content-Engine QA
  blocks, report no-raw-JSON checks, sign-off items (disclaimer, clean git,
  tag); `KNOWN_ISSUES.md` gained Trust Layer + Content Engine sections
- App copy audited for overclaims — none found (all "full replication"
  mentions are honest status framing)

---

## Future Phases — aligned with Master Blueprint v3

Development now follows **[Master Blueprint v3](MASTER_BLUEPRINT_V3.md)**: a
long-term catalog of ~100 educational quant models across 12 categories plus
platform trust features. The blueprint is a direction, not a promise — phases
ship in small, usable increments, and **none of the not-yet-built items below
are claimed as existing features**.

Status labels: **built** · **planned** (next phases) · **research** (needs
design/feasibility work) · **future** (long-term).

### Completed foundation (built)

Backtest engine · five single-asset strategies + pairs · Strategy Comparison
with shared simulation settings · cost model · position sizing · risk
management · annualization convention · data provider abstraction + data
quality diagnostics · benchmark & active analytics + visualization · research
tools (sweep / train-test / walk-forward) · Portfolio Lab (optimization,
frontier, risk, stress, factors) · CSV upload · custom strategy builder +
template gallery · saved backtests · report export (MD/PDF/templates/gallery)
· settings · neon theme + chart system · Command Center / palette / global
search · toasts, error boundary, loading/offline states.

### Near-term next phases (planned)

1. ~~Benchmark visualization~~ — **built** (12.6.1)
2. ~~Reproducible Backtest Permalinks / Config Hash~~ — **built** (12.7: config
   hash + CSV fingerprint; replay-by-hash routing remains future work)
3. ~~Robustness Lab v1~~ — **built** (12.8: block-bootstrap Monte Carlo +
   heuristic grade). ~~Parameter-sensitivity heatmaps~~ — **built** (12.9:
   Stability Lab v1, SMA only). **Robustness/Stability v2** stays planned:
   deflated Sharpe (needs trial tracking), PBO, sweeps for RSI / Bollinger /
   Momentum, comparison-mode robustness
4. ~~Strategy Library v1 pages~~ — **built** (13.0: research pages for the six
   live strategies + honest planned-model catalog)
5. ~~Paper Replication Series v1~~ — **built** (13.1: 8 paper pages, 3 honest
   inspired demos; full replications remain future work pending universe data)
6. **Options Pricing Engine v1** — Black–Scholes, Greeks, simple IV surface
   (educational; no options data feed)
7. **Volatility Lab v1** — realized vol estimators, vol targeting deep-dive,
   term-structure visuals
8. **Event-Driven & Arbitrage Module** (research)
9. **Rates / FX / Credit Module** (research)
10. **Real Estate Module** (research)
11. **Microstructure & HFT Lab** — *educational simulations* (order-book toys,
    queue models) on synthetic data; **not** real HFT execution (research)
12. **Portfolio Studio + Strategy Ensemble Builder** (research)
13. **ML & AI Lab** — feature pipelines, walk-forward ML guards (research)
14. **AI Explainer Copilot** — explains a result, never recommends trades
    (future)
15. **3D Visualization Engine** — surfaces (vol, parameter sweeps) (future)
16. **Dashboard & Content Engine** — ~~Quant Disasters series~~ **built**
    (13.2, six case studies); broader educational content engine (future)
17. **Platform & Launch** — hosted demo, hardening, optional accounts (future)

### Long-term model catalog (12 categories)

Target of ~100 educational models over time — **currently a small fraction is
built**; everything else is planned/research/future:

| # | Category | Status today |
|---|----------|--------------|
| 1 | Equities | **built (core)** — SMA, RSI, Bollinger, Momentum, Vol Breakout, Pairs |
| 2 | Options & Volatility | planned (Options Engine v1, Vol Lab v1) |
| 3 | Event-Driven & Arbitrage | research |
| 4 | Futures & Commodities | research |
| 5 | FX | research |
| 6 | Fixed Income & Rates | research |
| 7 | Credit | research |
| 8 | Crypto | **built (partial)** — crypto tickers, 365-day annualization; exchange-native data future |
| 9 | Real Estate | research |
| 10 | Market Microstructure & HFT | future (educational simulations only) |
| 11 | Portfolio & Risk | **built (core)** — optimization, frontier, risk dashboard, stress, factors; ensemble builder planned |
| 12 | Machine Learning & AI | future |

---

## Non-Goals (deliberate omissions)

These items will not be built in the foreseeable future:

- Real-money order execution / brokerage API integration / live trading
- Real high-frequency trading execution or live tick-data feeds (the future
  Microstructure & HFT Lab is *educational simulation on synthetic data* only)
- Tax modelling
- Options order management
- Proprietary / paid data subscriptions and API-key management
- Anything that positions QuantLab as a production trading system or
  investment advice — it is a local-first, educational research platform
