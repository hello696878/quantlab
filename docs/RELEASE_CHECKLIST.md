# QuantLab — Release Candidate QA Checklist

A manual pre-release checklist for cutting a **v4.0 release candidate**. Work top
to bottom; everything is local and reproducible. Companion docs:
[`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) · [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) ·
[`SCREENSHOT_PLAN.md`](SCREENSHOT_PLAN.md).

> **Honesty rule:** every result shown during QA must come from a **real backend
> run** on real data. No fabricated metrics, no placeholder rows.

Suggested baseline used throughout: **SPY · 2015-01-01 → 2023-12-31 · capital
100,000 · cost 10 bps · long_only**, and the portfolio basket **SPY, QQQ, GLD,
TLT** over the same range.

---

## 1. Environment

- [ ] **Backend starts** — `cd backend && python -m uvicorn app.main:app --reload --port 8000` serves <http://localhost:8000> and <http://localhost:8000/docs>.
- [ ] **Frontend starts** — `cd frontend && npm run dev` serves <http://localhost:3000> and opens on the Command Center.
- [ ] **Docker Compose starts** — `docker compose up --build` brings up both services; frontend on `:3000`, backend on `:8000`, proxied `/api/*` works.
- [ ] **GitHub Actions CI passes** — latest push/PR shows `backend-tests` and `frontend-build` green (`.github/workflows/ci.yml`).
- [ ] **SQLite persistence works** — saving a backtest/report creates/updates `backend/data/quantlab.db`; restarting the backend retains saved records.

---

## 2. Backend

```powershell
cd backend
python -m pytest -q
```

- [ ] **All tests pass** — 1,060+ tests across 53 files, all on synthetic data (no network calls at test time).
- [ ] **No real database polluted by tests** — persistence tests redirect to a temporary SQLite file via the `fresh_db` / `monkeypatch` fixture; the guard test `test_tests_use_temp_database_not_real_database` asserts the active DB path is **never** the real `backend/data/quantlab.db`. After a test run, confirm your real DB's row counts are unchanged.
- [ ] **Health endpoint works** — `curl http://localhost:8000/health` returns a healthy JSON payload; `GET /api/health` works through the frontend proxy.
- [ ] **Swagger loads** — <http://localhost:8000/docs> lists endpoints grouped by tag (`backtest`, `research`, `portfolio`, persistence, `ops`).

---

## 3. Frontend

```powershell
cd frontend
npx tsc --noEmit   # fast type check (must be clean)
npm run build      # full production build
```

- [ ] **Type check clean** — `tsc --noEmit` exits 0 with no errors.
- [ ] **Production build passes** — `npm run build` completes without errors.
- [ ] **No broken imports / no console errors** — load each workspace once in the browser and confirm no red console errors and no hydration warnings.

---

## 4. Core Feature QA

For each item: **what to test → expected result → suggested parameters**.

### Command Center (Home)
- **Test:** open the app cold; check quick actions, recent saved backtests/reports, system status, feature map.
- **Expected:** lands on Home by default; API status shows **ONLINE**; recents populate after items exist, otherwise honest empty states; every quick action navigates.
- **Params:** none.

### Guided demo
- **Test:** click a guided-demo button/preset (e.g. *Demo Backtest*).
- **Expected:** navigates + prefills the form and shows *"Demo parameters loaded. Click Run to execute."* — **nothing auto-runs**; pressing Run produces a real result.
- **Params:** Demo Backtest (SPY · SMA 20/100), Demo Crypto Momentum (BTC-USD · Momentum), Demo Portfolio Risk / Efficient Frontier (SPY/QQQ/GLD/TLT).

### Command palette
- **Test:** press **Ctrl/Cmd + K**; arrow-navigate; Enter; Esc.
- **Expected:** opens; ↑/↓ moves selection; Enter runs the command; Esc/click-outside closes; the TopBar **Search** chip also opens it.
- **Params:** n/a.

### Global search
- **Test:** in the palette, search `momentum`, `risk`, `BTC`.
- **Expected:** results mix commands + real saved resources (backtests, reports, templates, gallery), grouped; selecting a saved item opens its detail/builder. Empty query → all; no match → "No results found".
- **Params:** must have a few saved items to see resource rows.

### Backtest (single-asset)
- **Test:** run the baseline; check metrics, neon equity curve, drawdown, trade log; try a short mode on SMA.
- **Expected:** metrics + benchmark; neon glow line vs dashed benchmark; trade events; short modes show the short-selling warning + direction diagnostics. Long-only output unchanged.
- **Params:** SPY · SMA Crossover 20/100 · 2015-01-01 → 2023-12-31 · 100,000 · 10 bps · long_only.

### CSV upload
- **Test:** upload a daily CSV (date + close columns) and run a strategy; also upload a malformed file.
- **Expected:** valid file runs through the same engine and shows results + a **CSV backtest complete** toast; malformed/invalid → a friendly warning/error toast, no crash. Pairs is unavailable for CSV.
- **Params:** any `date,close` CSV; SMA Crossover.

### Custom Strategy Builder
- **Test:** load a gallery template (*Momentum + Trend*), run it; save a template; export then import the JSON.
- **Expected:** rules populate; runs a real backtest; save/update/delete/import/export each show a toast; import rejects malformed JSON with HTTP 422 (friendly message). No `eval`.
- **Params:** any ticker; template *Momentum + Trend* or *SMA Trend Filter*.

### Saved Backtests
- **Test:** save a result, reopen it from Saved Backtests, delete one.
- **Expected:** list shows skeleton → rows; detail loads metrics/curve/trades; delete shows a toast and removes the row. Empty state offers **Run Backtest**.
- **Params:** baseline backtest.

### Saved Reports
- **Test:** save a report, open it, download Markdown, print, delete.
- **Expected:** Markdown renders (HTML-escaped, inert), Download/Print/Delete each toast; PDF is via browser print. Empty state offers **Run a Backtest**.
- **Params:** report from the baseline backtest.

### Portfolio Backtest (equal-weight)
- **Test:** run equal-weight with a rebalance frequency.
- **Expected:** metrics, equity vs SPY benchmark, drawdown, per-day weights, rebalance log; turnover cost deducted on rebalance days.
- **Params:** SPY, QQQ, GLD, TLT · 2015-01-01 → 2023-12-31 · monthly rebalance.

### Portfolio Optimization (static)
- **Test:** run Min Volatility and Max Sharpe.
- **Expected:** long-only weights (≥0, sum 1), optimized vs equal-weight comparison, **in-sample caveat** banner visible.
- **Params:** same basket; objective min_volatility / max_sharpe.

### Walk-Forward Optimization
- **Test:** run with train/test/step windows.
- **Expected:** per-window detail, stitched **out-of-sample** equity vs equal-weight, weight-stability summary; no data leakage.
- **Params:** same basket; train 504 / test 126 / step 63.

### Efficient Frontier
- **Test:** run the frontier.
- **Expected:** scatter (x=vol, y=return), min-vol / max-Sharpe / equal-weight highlighted, weight cards; in-sample caveat.
- **Params:** SPY, QQQ, GLD, TLT · rf 0.02 · 2,000 portfolios.

### Risk Dashboard
- **Test:** open the risk dashboard.
- **Expected:** per-asset return/vol, correlation heatmap, diversification ratio, correlation diagnostics, risk-contribution table (≈100%).
- **Params:** SPY, QQQ, GLD, TLT.

### Stress Test
- **Test:** add scenarios and run.
- **Expected:** scenario-comparison table, selectable scenario equity vs benchmark, per-scenario correlation heatmap, full-period summary.
- **Params:** basket + COVID Crash + 2022 Rate-Hike scenarios.

### Factor Analysis
- **Test:** run with the Core ETF Factors preset.
- **Expected:** R²/alpha/residual-vol/largest-exposure cards, beta table, factor correlation heatmap, actual-vs-fitted curve; multicollinearity warning when proxies overlap.
- **Params:** basket vs market SPY / tech_growth QQQ / small_cap IWM / bonds TLT / gold GLD.

### Trust Layer (single backtest)
- **Test:** run the baseline with benchmark Buy & Hold, robustness ON (1,000 sims · block 5 · seed 42), and Stability Lab ON; re-run with a different seed.
- **Expected:** Benchmark Comparison card (alpha/beta/correlation/TE/IR) + equity/drawdown/excess overlays; Data Source card with provider + actual range; Reproducibility card (same config → same hash; copy buttons toast); Robustness card (P(loss), histogram, heuristic grade; same seed → same summary); Stability heatmap (20/100 ring-highlighted, invalid cells blank, score labelled heuristic). **No runtime errors on seed re-runs.**
- **Params:** baseline SPY SMA.

### Content Engine
- **Test:** open Strategy Library → SMA detail; Paper Replications → Jegadeesh–Titman; Quant Disasters → LTCM; click each "Run in Backtest Studio"/"Run inspired demo" CTA.
- **Expected:** detail sections render; status/replication badges honest (planned items have **no run buttons**); CTAs preload Backtest Studio (never auto-run); related papers/disasters cross-links navigate correctly.
- **Params:** n/a (static pages).

### Report Export
- **Test:** from a result, switch templates and export Markdown + PDF; Save Report.
- **Expected:** four templates (Standard / Executive Summary / Quant Tear Sheet / Risk Report); Markdown downloads; PDF opens a print preview; Save stores Markdown only. Toasts confirm each. Templates that can't be filled aren't offered. **No raw JSON anywhere in the PDF; the Parameters table shows strategy parameters only; no letter-by-letter wrapped labels; no white broken inputs anywhere in the demo flow.**
- **Params:** baseline backtest with benchmark + robustness + stability enabled (worst-case report length).

### Settings
- **Test:** change accent theme, defaults, and report template; reload.
- **Expected:** theme re-skins instantly and persists (no flash on reload); defaults prefill newly-mounted forms; stored in `localStorage` only.
- **Params:** try the **Risk** red accent.

### Offline UX
- **Test:** stop the backend, then browse Saved Reports/Backtests, open the palette, and try to save.
- **Expected:** commands/demos still work; saved resources show the consistent **Backend offline** panel with **Retry** (not a raw HTTP 500); a single de-duplicated offline toast; restarting + **Retry** loads data. No crash, no implied data loss.
- **Params:** n/a.

---

## 5. Release sign-off

- [ ] README, `ROADMAP.md`, `LIMITATIONS.md`, and `KNOWN_ISSUES.md` reflect the current build (Trust Layer + Content Engine included; nothing planned claimed as built).
- [ ] Educational disclaimer present in README and app copy (research-only, not investment advice, no live trading claims).
- [ ] Screenshots captured per [`SCREENSHOT_PLAN.md`](SCREENSHOT_PLAN.md) (or the README's "pending capture pass" note retained).
- [ ] Demo rehearsed against [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) end-to-end with no runtime errors.
- [ ] `backend/data/*.db` is git-ignored; no local DB or secrets committed.
- [ ] `git status` clean; release notes / changelog updated; tag the release (e.g. `v4.1-rc1`) once all boxes are checked.
