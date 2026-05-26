# QuantLab Backend — Phase 1 MVP

A **correct** FastAPI backtesting engine for a long-only SMA crossover strategy.

---

## Architecture

```
backend/
├── app/
│   ├── __init__.py       package marker
│   ├── main.py           FastAPI app, routes, input validation
│   ├── schemas.py        Pydantic request / response models
│   ├── data.py           yfinance OHLCV download layer
│   ├── strategies.py     SMA crossover signal generation (lookahead-bias-free)
│   ├── backtest.py       vectorised backtest engine + transaction costs
│   ├── metrics.py        Sharpe, Sortino, CAGR, drawdown, win-rate, …
│   └── utils.py          shared helpers
├── tests/
│   ├── test_metrics.py   25 unit tests for metrics
│   ├── test_strategies.py  signal shape / bias / economic behaviour tests
│   └── test_backtest.py  equity curve, trades, benchmark tests
├── pyproject.toml        pytest config (pythonpath, testpaths)
└── requirements.txt
```

---

## Setup

> **Prerequisite:** Python 3.11+ and a virtual environment activated.

```powershell
cd C:\quantlab

# activate the existing venv (Windows PowerShell)
.venv\Scripts\Activate.ps1

# install dependencies
pip install -r backend\requirements.txt
```

---

## Running the server

```powershell
cd C:\quantlab\backend
uvicorn app.main:app --reload --port 8000
```

The interactive API docs are available at:

- Swagger UI → http://localhost:8000/docs  
- ReDoc      → http://localhost:8000/redoc

---

## API Endpoints

### `GET /health`

Liveness check.

```json
{ "status": "ok", "version": "0.1.0" }
```

---

### `POST /backtest/sma-crossover`

Run a long-only SMA crossover backtest.

**Request body** (all fields have defaults):

```json
{
  "ticker":               "SPY",
  "start_date":           "2015-01-01",
  "end_date":             "2023-12-31",
  "fast_window":          50,
  "slow_window":          200,
  "transaction_cost_bps": 10.0,
  "initial_capital":      100000.0
}
```

| Field | Type | Constraint | Default |
|---|---|---|---|
| `ticker` | string | valid Yahoo Finance symbol | `"SPY"` |
| `start_date` | string | YYYY-MM-DD | `"2015-01-01"` |
| `end_date` | string | YYYY-MM-DD, after start | `"2023-12-31"` |
| `fast_window` | int | ≥ 2, < slow_window | `50` |
| `slow_window` | int | ≥ 2 | `200` |
| `transaction_cost_bps` | float | one-way bps, ≥ 0 and < 10,000 | `10.0` |
| `initial_capital` | float | > 0 | `100000.0` |

**Response** includes:

- `strategy_metrics` / `benchmark_metrics` — total_return, CAGR, Sharpe, Sortino, max_drawdown, volatility, win_rate
- `equity_curve` — daily `{ date, strategy, benchmark }` values
- `trades` — list of `{ date, action, price, shares, cost }` records

**Quick test with curl:**

```bash
curl -X POST http://localhost:8000/backtest/sma-crossover \
  -H "Content-Type: application/json" \
  -d '{"ticker":"SPY","start_date":"2015-01-01","end_date":"2023-12-31"}'
```

---

## Running the tests

```powershell
cd C:\quantlab\backend
pytest
```

All tests are unit tests; they use synthetic price series and do **not** make network calls.  
Expected output: **~35 tests, all passing, < 5 seconds**.

To run a specific file:

```powershell
pytest tests/test_metrics.py -v
pytest tests/test_strategies.py -v
pytest tests/test_backtest.py -v
```

---

## Correctness guarantees

| Risk | Mitigation |
|---|---|
| **Lookahead bias** | Signal from day T is shifted to become the close-to-close position for day T+1 (`signal.shift(1)`) |
| **Incorrect benchmark** | Benchmark is always 100 % long from day 1 with no transaction costs |
| **Wrong return calculation** | Uses `pct_change()` on adjusted close; tested against known values |
| **Transaction cost omission** | Costs charged on every position change (both entry and exit) |
| **Overfitting warning** | Single in-sample window only; walk-forward is a Phase 2 feature |

---

## Phase roadmap

- **Phase 0** ✅ Project scaffold, folder structure, clean repo  
- **Phase 1** ✅ SMA crossover backtest engine (this README)  
- **Phase 2** 🔲 Additional strategies (EMA, RSI, Bollinger Bands)  
- **Phase 3** 🔲 Frontend (React + Recharts)  
- **Phase 4** 🔲 Walk-forward testing, parameter sweeps  
- **Phase 5** 🔲 User accounts, saved backtests, CSV upload
