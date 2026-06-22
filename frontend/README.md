# QuantLab Frontend

Interactive backtesting and research dashboard built with **Next.js 14 · React 18 · Tailwind CSS 3 · Recharts 2**.

Analysis results come from the FastAPI backend. The Global Markets Globe uses a
typed backend static-sample API and an explicitly labelled bundled static fallback;
it never presents sample data as live market data.

---

## Folder structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css               Tailwind directives + shared component classes
│   │   ├── layout.tsx                Root layout: nav bar, footer, metadata
│   │   └── page.tsx                  Main page: mode tabs, backtest state, research tabs
│   ├── components/
│   │   ├── BacktestForm.tsx          Parameter inputs + Run button + validation
│   │   ├── MetricsGrid.tsx           Strategy vs benchmark comparison table
│   │   ├── EquityCurveChart.tsx      Equity curve (strategy + benchmark overlay)
│   │   ├── DrawdownChart.tsx         Drawdown area chart (strategy + benchmark)
│   │   ├── TradeTable.tsx            Paginated trade log table
│   │   ├── SmaSweepPanel.tsx         SMA parameter sweep form + result table
│   │   ├── SmaSweepTable.tsx         Sortable SMA sweep result table
│   │   ├── SmaTrainTestPanel.tsx     SMA train/test out-of-sample validation UI
│   │   ├── SmaWalkForwardPanel.tsx   SMA walk-forward optimization UI
│   │   └── StrategyComparisonPanel.tsx  Multi-strategy comparison UI
│   └── lib/
│       ├── types.ts                  TypeScript interfaces (mirrors backend schemas)
│       ├── api.ts                    Fetch wrappers for all backend endpoints
│       └── format.ts                 Number/date formatters used across components
├── .env.local                        BACKEND_URL env var (default: http://localhost:8000)
├── .env.example                      Example backend URL configuration
├── next.config.js                    /api/* → backend rewrite (no CORS needed)
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

---

## Install

```powershell
cd C:\quantlab\frontend
npm install
Copy-Item .env.example .env.local
```

---

## Run (development)

```powershell
# Terminal 1 — backend
cd C:\quantlab\backend
..\\.venv\\Scripts\\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd C:\quantlab\frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## API routing

The frontend calls relative URLs; Next.js rewrites them to the backend transparently — no CORS headers needed.

| Browser request | Backend request |
|---|---|
| `POST /api/backtest/sma-crossover` | `POST /backtest/sma-crossover` |
| `POST /api/backtest/rsi-mean-reversion` | `POST /backtest/rsi-mean-reversion` |
| `POST /api/backtest/bollinger-band` | `POST /backtest/bollinger-band` |
| `POST /api/backtest/momentum` | `POST /backtest/momentum` |
| `POST /api/backtest/volatility-breakout` | `POST /backtest/volatility-breakout` |
| `POST /api/backtest/pairs` | `POST /backtest/pairs` |
| `POST /api/research/sma-parameter-sweep` | `POST /research/sma-parameter-sweep` |
| `POST /api/research/sma-train-test` | `POST /research/sma-train-test` |
| `POST /api/research/sma-walk-forward` | `POST /research/sma-walk-forward` |
| `POST /api/research/strategy-comparison` | `POST /research/strategy-comparison` |
| `GET /api/globe/markets` | `GET /globe/markets` |
| `GET /api/globe/markets/:id` | `GET /globe/markets/{market_id}` |
| `GET /api/globe/regions` | `GET /globe/regions` |

The Globe renders bundled static sample data immediately, then uses the validated
backend static dataset when available. If the backend is unavailable or returns an
invalid payload, the UI keeps the bundled dataset and shows a visible fallback notice.

Default backend base URL: `http://localhost:8000`

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Backend base URL used by Next.js rewrites |

Copy `frontend/.env.example` to `frontend/.env.local`, then edit
`BACKEND_URL` only if your FastAPI server runs somewhere other than
`http://localhost:8000`.

---

## UI sections

### Backtest mode

| Section | Description |
|---|---|
| **Strategy selector** | SMA Crossover, RSI, Bollinger Band, Momentum, Volatility Breakout, Pairs |
| **Parameter form** | Strategy-specific inputs; validated before submit |
| **Performance Summary** | `strategy_metrics` vs `benchmark_metrics` side-by-side |
| **Equity Curve** | Daily `strategy` and `benchmark` equity values from API |
| **Drawdown Chart** | Running-peak drawdown computed client-side from equity curve |
| **Trade Log** | Paginated trade events from API (20 per page) |

### Research Tools mode

| Tab | Endpoint | Description |
|---|---|---|
| **SMA Parameter Sweep** | `POST /research/sma-parameter-sweep` | Sweep all (fast, slow) combinations over a single period; sortable result table |
| **SMA Train/Test Validation** | `POST /research/sma-train-test` | IS parameter selection + OOS evaluation; degradation stats, collapse flag |
| **SMA Walk-Forward** | `POST /research/sma-walk-forward` | Rolling IS sweep → OOS test → stitch; aggregate metrics, parameter stability analysis |
| **Strategy Comparison** | `POST /research/strategy-comparison` | Five strategies on same ticker/dates with fixed defaults; ranking, comparison table, multi-line equity curve |

#### Walk-Forward panel details

The Walk-Forward panel exposes:

- **Window settings** — training window length, test window length, step size (trading days)
- **Parameter grid** — comma-separated fast and slow SMA windows (up to 10 each, ≤ 100 combinations)
- **Selection metric** — Sharpe ratio, CAGR, or Calmar ratio used to pick the best IS pair
- **Results:**
  - Amber warning banner when parameters are unstable across windows
  - Aggregate OOS metrics table (strategy vs benchmark)
  - Stitched OOS equity curve chart (capital compounded across all windows)
  - Parameter stability card — stat boxes + colour-coded chip array (emerald = most-selected pair, slate = others)
  - Per-window table — train/test periods, selected (fast, slow), IS Sharpe, OOS Sharpe, OOS CAGR, OOS max drawdown, trades

#### Strategy Comparison panel details

The Strategy Comparison panel exposes:

- **Inputs** — ticker, start/end dates, transaction cost (bps), initial capital
- **Fixed-params note** — a visible reminder of the default parameters used per strategy
- **Results:**
  - Ranking cards (Best Sharpe, Best CAGR, Best Calmar, Lowest Max Drawdown)
  - Comparison table — all five strategies + benchmark row (CAGR, Total Return, Sharpe, Sortino, Calmar, Max DD, Vol, Trades); best-Sharpe row highlighted
  - Multi-line equity curve — each strategy in a distinct colour plus a dashed benchmark line
  - Default-parameters reference cards — one per strategy showing the exact params used
  - Disclaimer — interpretation guidance and limitations notice

**Limitations:**

- Uses fixed default parameters; per-strategy customisation is not supported in this version
- Pairs Trading is excluded (two-asset strategy incompatible with single-asset comparison)
- Single in-sample period only — validate any findings with the Train/Test or Walk-Forward tools before drawing conclusions

---

**Interpreting parameter stability:**

Parameters are flagged as **unstable** when no single (fast, slow) pair is chosen in more than 50 % of the windows.  Instability is not a definitive failure — it may reflect genuine regime adaptation — but it means the strategy's future behaviour is harder to predict and warrants additional scrutiny.

---

## Production build

```powershell
cd C:\quantlab\frontend
npm run build
npm start
```
