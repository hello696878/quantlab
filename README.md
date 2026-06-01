# QuantLab

An interactive quantitative research and backtesting platform built for learning, exploration, and portfolio demonstration.

QuantLab lets you select a strategy, choose an asset and date range, tune parameters, and instantly see equity curves, drawdown charts, performance metrics, and trade logs — all computed on real historical price data with no lookahead bias.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI · Python 3.11 · Pydantic v2 |
| Data | yfinance (OHLCV daily) |
| Backtest engine | NumPy · pandas (vectorised) |
| Frontend | Next.js 14 · React 18 · TypeScript |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Local persistence | SQLite for saved backtests |
| Testing | pytest (325+ tests, synthetic data) |
| CI | GitHub Actions |
| Containerisation | Docker · Docker Compose |

---

## Features

### Strategies

| Strategy | Type | Parameters |
|---|---|---|
| SMA Crossover | Trend-following | Fast window, slow window |
| RSI Mean Reversion | Mean-reversion | RSI window, oversold threshold, exit threshold |
| Bollinger Band Mean Reversion | Mean-reversion | Window, std multiplier, exit band |
| Time-Series Momentum | Trend-following | Momentum window, entry/exit thresholds |
| Volatility Breakout | Trend-following | Lookback window, breakout multiplier, exit window |
| Pairs Trading | Statistical arbitrage | Asset Y, asset X, lookback window, entry/exit z-score |

All strategies apply a **one-day signal shift** — the position derived from day T's close prices is applied on day T+1. This prevents lookahead bias by construction.

### Research Tools

| Tool | Purpose |
|---|---|
| SMA Parameter Sweep | Grid search over fast/slow window combinations; ranks by Sharpe, CAGR, or Calmar |
| SMA Train/Test Validation | Splits data at a user-defined date; selects parameters in-sample, evaluates out-of-sample; reports degradation and an `oos_collapsed` flag |
| SMA Walk-Forward Optimization | Rolls a training window forward, re-selects parameters each fold, stitches OOS windows into a continuous equity curve |
| Strategy Comparison | Runs all five single-asset strategies on the same ticker/period with default parameters and ranks them |

### Performance Metrics

Total return · CAGR · Sharpe ratio · Sortino ratio · Calmar ratio · Max drawdown · Annualised volatility · Win rate · Trade count

Benchmark: buy-and-hold with no transaction costs.

### CSV Upload Backtesting

The **CSV Backtest** workspace lets you upload your own historical price CSV and run any single-asset strategy on it (Pairs Trading excluded). Column detection is flexible: a date column (`date` / `datetime` / `timestamp`) and a close column (`close` / `adj_close` / `adjusted_close`) are required; optional OHLCV columns are ignored. The uploaded series flows through the same lookahead-bias-free strategy, backtest, and metrics stack as the yfinance endpoints (`POST /backtest/csv`).

### Custom Strategy Builder

The **Strategy Builder** workspace is a no-code rule builder for long-only, single-asset strategies (`POST /backtest/custom`). Compose entry and exit rules that compare two operands — `close`, a numeric constant, or an indicator (`sma`, `rsi`, `bb_upper`/`bb_middle`/`bb_lower`, `momentum`) — with `>`, `>=`, `<`, or `<=`. Rules are combined with ALL (AND) or ANY (OR) logic; the position is shifted one bar forward to avoid lookahead bias. Rules are evaluated entirely with vectorised pandas math — **no `eval`, no user code is ever executed**. Indicators reuse the exact formulas of the built-in strategies. No short selling, leverage, or pairs.

### Saved Strategy Templates

The Strategy Builder can **save reusable strategy definitions** (`/custom-strategies` CRUD endpoints). A template stores the rule definition only — entry/exit rules, combine logic, name, description, and tags — and can be loaded back into the builder and re-run on any ticker, date range, or (future) CSV upload. Templates are validated against the same whitelisted rule schema as the live builder, so **no arbitrary code is ever stored or executed** (no `eval`). Create, list, load, update, and delete templates directly from the Strategy Builder workspace.

**Saved Backtests vs. Saved Strategy Templates** — these are distinct:

| | Saved Backtests | Saved Strategy Templates |
|---|---|---|
| Stores | A completed **result** (metrics, equity curve, trades) frozen at run time | A reusable **strategy definition** (rules + logic + metadata) |
| Tied to a ticker/date range | Yes — captures one specific run | No — re-runnable on any ticker/dates |
| Table | `saved_backtests` | `custom_strategy_templates` |
| Purpose | Review/compare past results | Reuse and iterate on a strategy idea |

#### Import / Export

Templates are portable. **Export** any saved template to a self-describing JSON file (`GET /custom-strategies/{id}/export`, or the per-row **Export** button), and **import** one from a file (`POST /custom-strategies/import`, or the **Import Template** button). Exported files deliberately omit `id`, `created_at`, and `updated_at` so they are safe to share. On import the backend re-validates the document against the **same whitelisted rule schema** as the live builder — wrong `type`, missing `schema_version`, empty name, non-whitelisted indicator/operator, or more than 10 rules per list are rejected with HTTP 422. **Imported templates are validated data, never executed code** (no `eval`).

Example exported JSON:

```json
{
  "schema_version": "1.0",
  "type": "quantlab_custom_strategy_template",
  "name": "SMA + RSI Trend Filter",
  "description": "Long when SMA trend is positive and RSI is not overbought.",
  "entry_logic": "AND",
  "exit_logic": "OR",
  "entry_rules": [
    {
      "left": { "type": "indicator", "name": "sma", "params": { "window": 50 } },
      "operator": ">",
      "right": { "type": "indicator", "name": "sma", "params": { "window": 200 } }
    },
    {
      "left": { "type": "indicator", "name": "rsi", "params": { "window": 14 } },
      "operator": "<",
      "right": { "type": "constant", "value": 70 }
    }
  ],
  "exit_rules": [
    {
      "left": { "type": "indicator", "name": "sma", "params": { "window": 50 } },
      "operator": "<=",
      "right": { "type": "indicator", "name": "sma", "params": { "window": 200 } }
    }
  ],
  "tags": ["trend", "rsi"]
}
```

### Multi-Asset Portfolio Backtesting

The **Portfolio Backtest** workspace runs a simple equal-weight, long-only, fully-invested portfolio across up to 20 assets (`POST /portfolio/backtest`). Every asset targets a 1/N weight. Choose a **rebalance frequency**:

- **none** — buy equal-weight once and let the weights drift (buy & hold)
- **monthly / quarterly / yearly** — reset to equal weight on the first trading day of each new period

Rebalancing isn't free: the cost is **turnover-based** — `turnover = Σ|target_weightᵢ − driftedᵢ|` and `cost = equity × turnover × bps/10000`, deducted on the rebalance day. All assets are aligned to their common trading days (dates where any asset is missing are dropped); the benchmark is SPY buy-and-hold when available (in the basket or fetched separately), otherwise the first ticker as a documented fallback. The response includes metrics, the equity curve vs. benchmark, drawdown, per-day weights, and a rebalance-events log.

> The equal-weight backtest is a transparent baseline. For weight optimization, see below.

### Portfolio Optimization

The Portfolio workspace also includes an **Optimization** tab (`POST /portfolio/optimize`) that solves for **long-only** weights (each `wᵢ ≥ 0`, `Σw = 1` — no shorting, no leverage) under one of three objectives:

- **Equal Weight** — `wᵢ = 1/N` (baseline).
- **Minimum Volatility** — minimise `√(wᵀ Σ w)` (portfolio variance).
- **Maximum Sharpe** — maximise `(wᵀμ − r_f) / √(wᵀ Σ w)`.

Expected returns and the covariance matrix are estimated from daily returns and annualised with 252 trading days; the constrained problem is solved with SciPy's SLSQP. The optimized weights are backtested buy-and-hold over the period and compared against the equal-weight portfolio (metrics, equity curve, drawdown). Portfolio Optimization v1 is a static allocation model: `transaction_cost_bps` is accepted for API/UI consistency but no one-time allocation cost or ongoing turnover cost is deducted.

> ⚠️ **In-sample caveat.** Static optimization optimizes weights on the **same** historical window it then backtests. This is in-sample optimization: it will look good by construction, can badly overfit, and **does not predict future performance**. For an out-of-sample variant, use Walk-Forward Optimization below. **Not investment advice.**

### Walk-Forward Portfolio Optimization

The Portfolio workspace's **Walk-Forward Optimization** tab (`POST /portfolio/walk-forward-optimize`) addresses the in-sample problem with rolling, **out-of-sample** optimization:

1. Estimate expected returns and covariance on a **training window** (`train_window_days`).
2. Optimize long-only weights on that window (equal_weight / min_volatility / max_sharpe).
3. Apply those **fixed** weights to the following **test window** (`test_window_days`) — unseen data.
4. Advance by `step_days` and repeat; stitch all test windows into one out-of-sample equity curve.

**No data leakage:** weights for each window are estimated only from that window's training slice and applied to strictly later dates — the optimizer never sees test data.

**Transaction cost (turnover-based):** at each test-window boundary the portfolio moves from the previous weights to the new ones — `turnover = Σ|new_wᵢ − prev_wᵢ|` (the first window's turnover is `Σ|wᵢ − 0| = 1`, i.e. entry from cash). `cost = turnover × bps/10000` is deducted from equity at the start of that test window. The equal-weight benchmark is treated identically (its target never changes, so it pays only the initial entry).

If `step_days < test_window_days`, test windows overlap; the stitched OOS curve uses each window's non-overlapping step slice (and the final window's remaining test tail) so re-optimization happens at the requested step cadence without duplicate dates. If `step_days > test_window_days`, gaps between test windows are intentionally left out of the stitched OOS curve.

The response includes per-window detail (train/test dates, weights, train Sharpe, out-of-sample `test_metrics`, turnover, cost), the stitched OOS equity vs. an equal-weight benchmark, drawdown, aggregate OOS metrics, and a **weight-stability** summary (average/max turnover, per-asset average/min/max weight).

> ⚠️ Walk-forward results are out-of-sample and far more honest than in-sample optimization, but they still rely on historical return/covariance assumptions and **do not predict future performance**. Not investment advice.

### Efficient Frontier

The Portfolio workspace's **Efficient Frontier** tab (`POST /portfolio/efficient-frontier`) visualises the risk–return space of a multi-asset, **long-only** universe. From annualised expected returns and covariance (252-day) it:

- samples many random long-only portfolios (`w_i ≥ 0`, `Σw = 1`; `num_portfolios`, deterministic seed) and computes each one's expected return, volatility, and Sharpe;
- locates the **equal-weight**, **minimum-volatility**, and **maximum-Sharpe** portfolios; and
- traces the **efficient-frontier curve** (minimise volatility for each target return).

The dashboard renders a Recharts scatter plot — x = volatility, y = expected return, hover for Sharpe and weights — with the three special portfolios highlighted, plus weight cards for each. **Expected return** = `wᵀμ`, **volatility** = `√(wᵀΣw)`, **Sharpe** = `(wᵀμ − r_f)/volatility`.

> ⚠️ This is **historical, in-sample** analysis: expected returns and covariance are estimated from the selected window and may not persist. It is descriptive, **not a forecast or investment advice**.

#### Strategy Template Gallery

The Strategy Builder includes a built-in **gallery** of curated, ready-to-use strategy templates (`GET /custom-strategy-gallery`). Open the **Gallery** from the Strategy Builder, browse the cards (each shows name, description, tags, difficulty, category, and a readable rule summary), then **Load** one into the builder to run it on any ticker/date range, or **Save to My Templates** to keep a local copy. Built-in templates are **static, pre-validated rule objects — not executable code** (no `eval`); they pass through the exact same whitelisted `CustomRule` validation as user-built strategies.

Built-in templates:

| Template | Category | Entry → Exit |
|---|---|---|
| SMA Trend Filter | trend | SMA(50) > SMA(200) → SMA(50) < SMA(200) |
| RSI Mean Reversion | mean reversion | RSI(14) < 30 → RSI(14) > 50 |
| Momentum + Trend | momentum | Momentum(126) > 0 **AND** SMA(50) > SMA(200) → Momentum(126) ≤ 0 **OR** SMA(50) < SMA(200) |
| Bollinger Mean Reversion | mean reversion | Close < BB Lower(20, 2.0) → Close > BB Middle(20) |
| Defensive Trend Strategy | trend | Close > SMA(200) → Close < SMA(200) |

### Saved Backtests

Completed backtest results can be saved to a local SQLite database and reopened from the Saved Backtests view. Saved records preserve the run name, notes, strategy parameters, metrics, equity curve, and trade log.

The local database lives at `backend/data/quantlab.db` (both `saved_backtests` and `custom_strategy_templates` tables). The backend creates `backend/data/` automatically when needed, and `backend/data/*.db` is ignored by git so local research artifacts are not committed.

### Engineering

- Vectorised backtest engine (no Python loops over price series)
- Transaction cost model: flat bps charged on each position change
- Pydantic v2 request/response schemas with full validation
- 325+ pytest tests using synthetic data (no network calls)
- GitHub Actions CI: backend tests + frontend build on every push/PR
- Docker Compose: one command to start the full stack

---

## Screenshots

### Main Backtest Dashboard

![Main Backtest Dashboard](docs/screenshots/main-backtest-dashboard.png)

### Strategy Comparison

![Strategy Comparison](docs/screenshots/strategy-comparison.png)

### SMA Parameter Sweep

![SMA Parameter Sweep](docs/screenshots/sma-parameter-sweep.png)

### Train/Test Validation

![Train/Test Validation](docs/screenshots/train-test-validation.png)

### Walk-Forward Optimization

![Walk-Forward Optimization](docs/screenshots/walk-forward-optimization.png)

### FastAPI Docs

![FastAPI Docs](docs/screenshots/fastapi-docs.png)

---

## Architecture

```
Browser
  │
  │  http://localhost:3000
  ▼
Next.js Frontend  (React 18, Tailwind, Recharts)
  │  BacktestForm → SmaSweepPanel → StrategyComparisonPanel → …
  │
  │  /api/*  (proxied at build time via next.config.js rewrites)
  ▼
FastAPI Backend  (Python 3.11, Pydantic v2)
  │  /backtest/*  /research/*  /saved-backtests  /health
  │
  ├── data.py        yfinance OHLCV download + alignment
  ├── strategies.py  Signal generation (all shift-by-1)
  ├── backtest.py    Vectorised engine, trade log, benchmark
  ├── metrics.py     Sharpe, CAGR, drawdown, Sortino, Calmar, …
  ├── db.py          SQLite connection + schema initialisation
  ├── saved_backtests.py  Saved-backtest CRUD helpers
  └── schemas.py     Pydantic request / response models
```

In Docker, the browser never calls the backend directly:

```
Browser  →  localhost:3000/api/*
                │
          Next.js server (frontend container)
                │  rewrites /api/* → http://backend:8000/*
                ▼
          FastAPI server (backend container, internal DNS)
```

---

## Quick Start — Docker (recommended)

Requires Docker Desktop (or Docker Engine + Compose V2).

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend dashboard | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |

The first build pulls base images and installs all dependencies. Subsequent starts reuse cached layers.

**Stop:**

```bash
# Ctrl+C, then:
docker compose down
```

---

## Quick Start — Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+

### Backend

```powershell
# create and activate a virtual environment (Windows PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# install dependencies
pip install -r backend\requirements.txt

# start the API server
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Backend: http://localhost:8000  
Swagger docs: http://localhost:8000/docs

Saved backtests are persisted locally in `backend/data/quantlab.db`. Delete that file to reset local saved runs.

### Frontend

Open a second terminal:

```powershell
cd frontend
npm install        # first time only
npm run dev
```

Frontend: http://localhost:3000

---

## Testing

```powershell
cd backend
python -m pytest -q
```

All 325+ tests use synthetic price data — no network calls, no yfinance dependency at test time.

---

## CI

GitHub Actions runs on every push and pull request to `main`:

| Job | What it does |
|---|---|
| `backend-tests` | Installs Python 3.11 deps, runs `pytest -q` |
| `frontend-build` | Installs Node 20 deps via `npm ci`, runs `next build` |

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Project Layout

```
quantlab/
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI routes (backtest + research endpoints)
│   │   ├── strategies.py    Signal generation — all shift by 1 day
│   │   ├── backtest.py      Vectorised backtest engine + trade log
│   │   ├── metrics.py       Sharpe, CAGR, drawdown, Sortino, Calmar, …
│   │   ├── schemas.py       Pydantic v2 request / response models
│   │   ├── data.py          yfinance OHLCV download layer
│   │   └── utils.py         Shared helpers (date validation, etc.)
│   ├── tests/               pytest suite (325+ tests, synthetic data)
│   ├── Dockerfile
│   ├── .dockerignore
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             Next.js App Router pages
│   │   ├── components/      React components (BacktestForm, charts, panels)
│   │   └── lib/             API client, TypeScript types, formatters
│   ├── Dockerfile
│   ├── .dockerignore
│   └── package.json
├── docs/
│   ├── PROJECT_OVERVIEW.md  Module descriptions and data flow
│   ├── ROADMAP.md           Completed phases and future plans
│   ├── LIMITATIONS.md       Known constraints and caveats
│   └── screenshots/         Screenshot placeholders
├── .github/
│   └── workflows/
│       └── ci.yml           GitHub Actions CI
├── docker-compose.yml
└── README.md
```

---

## Known Limitations

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for the full list. Key points:

- Price data from yfinance may have gaps, splits, or quality issues
- No survivorship-bias-free database
- No intraday data or live trading
- Annualisation assumes 252 trading days (equities convention)
- Parameter sweeps can overfit in-sample — always check out-of-sample results

---

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full phase plan. Completed phases:

- Phase 0 — project setup and structure
- Phase 1 — backend MVP (backtest engine + metrics)
- Phase 2 — frontend dashboard
- Phase 3 — strategy expansion (RSI, Bollinger, Momentum, VB, Pairs)
- Phase 4 — research tools (sweep, train/test, walk-forward, comparison)
- Phase 5 — engineering infrastructure (CI, Docker, numeric input UX)

---

## Educational Disclaimer

QuantLab is a learning and research tool. **Nothing on this platform constitutes investment advice.** Strategy backtests reflect historical simulated performance only. Past performance is not indicative of future results. Real trading involves costs, market impact, execution risk, and other factors not modelled here.

---

## Troubleshooting

### Port already in use

```powershell
# Windows — free port 3000
Stop-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess -Force

# macOS / Linux
lsof -ti:3000 | xargs kill
```

Substitute `8000` for the backend port.

### Frontend shows "Backend request failed"

1. Confirm both containers are running: `docker compose ps`
2. Check backend health: `curl http://localhost:8000/health`
3. Check logs: `docker compose logs backend`
4. After editing source code, rebuild: `docker compose up --build`

### Changes not reflected after editing source

The Docker image is built once. After editing source code:

```bash
docker compose up --build
```

For faster iteration, use the local dev workflow (`npm run dev` + `uvicorn --reload`).
