# QuantLab Frontend — Phase 2

Interactive backtesting dashboard built with **Next.js 14 · React 18 · Tailwind CSS 3 · Recharts 2**.

All displayed results come from the FastAPI backend — no fake data.

---

## Folder structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css          Tailwind directives + shared component classes
│   │   ├── layout.tsx           Root layout: nav bar, footer, metadata
│   │   └── page.tsx             Main page: state, form → results
│   ├── components/
│   │   ├── BacktestForm.tsx     Parameter inputs + Run button + validation
│   │   ├── MetricsGrid.tsx      Strategy vs benchmark comparison table
│   │   ├── EquityCurveChart.tsx Equity curve (strategy + benchmark overlay)
│   │   ├── DrawdownChart.tsx    Drawdown area chart (strategy + benchmark)
│   │   └── TradeTable.tsx       Paginated trade log table
│   └── lib/
│       ├── types.ts             TypeScript interfaces (mirrors backend schemas)
│       ├── api.ts               Fetch wrappers for /api/backtest/* endpoints
│       └── format.ts            Number/date formatters used across components
├── .env.local                   BACKEND_URL env var (default: http://localhost:8000)
├── .env.example                 Example backend URL configuration
├── next.config.js               /api/* → backend rewrite (no CORS needed)
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

The frontend calls the backend through Next.js rewrites:

- Browser request: `POST /api/backtest/sma-crossover`
- Backend request: `POST /backtest/sma-crossover`
- Browser request: `POST /api/backtest/rsi-mean-reversion`
- Backend request: `POST /backtest/rsi-mean-reversion`
- Browser request: `POST /api/backtest/bollinger-band`
- Backend request: `POST /backtest/bollinger-band`
- Default backend base URL: `http://localhost:8000`

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Backend base URL used by Next.js rewrites |

Copy `frontend/.env.example` to `frontend/.env.local`, then edit
`BACKEND_URL` only if your FastAPI server runs somewhere other than
`http://localhost:8000`.

---

## How the proxy works

`next.config.js` rewrites every request to `/api/*` → `http://localhost:8000/*`.

The frontend therefore calls relative URLs such as
**`/api/backtest/bollinger-band`**. Next.js forwards them to the backend
transparently — no CORS headers needed in the browser, no hard-coded
`localhost:8000` in client-side code.

---

## UI sections

| Section | Source |
|---|---|
| **Parameter form** | User input; validated before submit |
| **Performance Summary** | `strategy_metrics` / `benchmark_metrics` from API |
| **Equity Curve** | `equity_curve[].strategy` and `.benchmark` |
| **Drawdown Chart** | Computed client-side from `equity_curve` (running peak) |
| **Trade Log** | `trades[]` from API — paginated 20 per page |

---

## Production build

```powershell
cd C:\quantlab\frontend
npm run build
npm start
```
