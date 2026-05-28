# QuantLab Frontend

Interactive backtesting and research dashboard built with **Next.js 14 · React 18 · Tailwind CSS 3 · Recharts 2**.

All displayed results come from the FastAPI backend — no fake data.

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
│   │   └── SmaWalkForwardPanel.tsx   SMA walk-forward optimization UI
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

**Interpreting parameter stability:**

Parameters are flagged as **unstable** when no single (fast, slow) pair is chosen in more than 50 % of the windows.  Instability is not a definitive failure — it may reflect genuine regime adaptation — but it means the strategy's future behaviour is harder to predict and warrants additional scrutiny.

---

## Production build

```powershell
cd C:\quantlab\frontend
npm run build
npm start
```
