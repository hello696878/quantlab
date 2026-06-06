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
- Annualization convention is **stored for future use only** — backend still
  uses 252 trading days; the panel shows a clear (crypto = experimental) note
- Frontend-only (`tsc --noEmit` clean); no backend or quant-logic changes

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

## Future Phases

The items below are planned but not yet started. Order and scope may change.

### Phase 6 — Saved Backtests and Database

- Persist backtest results to a lightweight database (SQLite or PostgreSQL)
- Save, name, and reload previous backtest runs
- Compare saved runs side by side

### Phase 7 — User Accounts

- Authentication (email/password or OAuth)
- Per-user saved strategies and backtests
- User dashboard

### Phase 8 — CSV Upload (extensions)

- Single-asset CSV upload backtesting shipped — see "Phase 6 — CSV Upload
  Backtesting" above.
- Remaining: run the research tools (sweep, train/test, walk-forward,
  comparison) on uploaded data, and two-asset CSV upload for Pairs Trading.

### Phase 9 — Multi-Asset Portfolio Backtesting

- Portfolio of assets with configurable weights
- Rebalancing schedule (monthly, quarterly, annual)
- Portfolio-level metrics (portfolio Sharpe, diversification ratio)
- Mean-variance optimisation (Markowitz efficient frontier)
- Risk parity

### Phase 10 — Better Visualisation

- Monthly return heatmap (calendar chart)
- Rolling Sharpe / rolling beta charts
- Trade distribution histogram
- Underwater plot (time spent in drawdown)
- Interactive parameter sensitivity charts

### Phase 11 — Live Data Integration

- Real-time or end-of-day price feed
- Paper trading mode (no real orders, just simulated fills)
- Alert when a live signal triggers

### Phase 12 — Deployment

- Hosted public demo (Railway, Render, Fly.io, or AWS)
- Environment-specific configuration
- Rate limiting and basic abuse protection
- Custom domain

### Phase 13 — Advanced Models

Items from the long-term vision, ordered by complexity:

- Kalman filter pairs trading (dynamic hedge ratio)
- Rolling-beta pairs trading v2 (vs. fixed lookback z-score)
- Hidden Markov Model regime detection
- Factor model exposure analysis (Fama-French)
- Black-Scholes options pricing module
- Heston model and volatility surface

### Phase 14 — Data Quality Improvements

- Crypto calendar support (365-day annualisation, 24/7 trading)
- Survivorship-bias awareness flag
- Dividend-adjusted vs. unadjusted price toggle
- Data quality warnings (gaps, splits, anomalies)

---

## Non-Goals (deliberate omissions)

These items will not be built in the foreseeable future:

- Real-money order execution / brokerage API integration
- Intraday data or tick-level backtesting
- High-frequency or market-making strategies
- Tax modelling
- Options order management
- Proprietary data subscriptions
