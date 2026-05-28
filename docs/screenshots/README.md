# Screenshots

This folder is a placeholder for QuantLab UI screenshots.

Screenshots should be added after the first full deployment or local run.
Recommended format: PNG, captured at 1440 × 900 or similar widescreen resolution.

---

## Planned Screenshots

### 1. `backtest_dashboard.png`

The main backtest results page after running a strategy.

Should show:
- Performance metrics grid (Total Return, CAGR, Sharpe, Sortino, Calmar, Max Drawdown, Volatility, Win Rate)
- Equity curve chart with strategy vs. buy-and-hold benchmark
- Drawdown chart
- Trade log table
- Strategy and parameter selection panel on the left

Suggested run: `AAPL`, SMA Crossover, fast=50, slow=200, 2015-01-01 → 2024-01-01

---

### 2. `strategy_comparison.png`

The Strategy Comparison research tool showing all five single-asset strategies on the same ticker.

Should show:
- Overlay equity curve with all five strategies + benchmark
- Metrics table with Sharpe, CAGR, Max Drawdown, Win Rate columns
- Ranking summary (best by Sharpe, CAGR, Calmar, lowest drawdown)

Suggested run: `SPY`, 2015-01-01 → 2024-01-01

---

### 3. `sma_parameter_sweep.png`

The SMA Parameter Sweep research tool.

Should show:
- The full results table with fast/slow window pairs sorted by Sharpe ratio
- Column headers: Fast Window, Slow Window, Total Return, CAGR, Sharpe, Sortino, Calmar, Max Drawdown, Trades

Suggested run: `AAPL`, fast windows 10–50, slow windows 50–200

---

### 4. `sma_train_test.png`

The SMA Train/Test Out-of-Sample Validation tool.

Should show:
- In-sample vs. out-of-sample metrics side by side
- Degradation row (Sharpe degradation, CAGR degradation)
- OOS equity curve chart
- `oos_collapsed` flag indicator (ideally `false` for a well-behaved example)

Suggested run: `AAPL`, 2010-01-01 → 2024-01-01, split 2020-01-01

---

### 5. `sma_walk_forward.png`

The SMA Walk-Forward Optimization tool.

Should show:
- Stitched OOS equity curve across all walk-forward windows
- Per-window table (train dates, test dates, selected fast/slow, OOS Sharpe)
- Parameter stability summary (most common parameter pair, unique sets)

Suggested run: `SPY`, 2010-01-01 → 2024-01-01, train=504, test=126, step=63

---

### 6. `fastapi_docs.png`

The auto-generated Swagger UI at `http://localhost:8000/docs`.

Should show:
- The full list of endpoints grouped by tag (`backtest`, `research`, `ops`)
- One endpoint expanded to show request/response schema

---

## How to Take Screenshots

### Local dev

1. Start the app: `npm run dev` (frontend) + `uvicorn app.main:app --reload` (backend)
2. Open http://localhost:3000
3. Run a backtest with the suggested parameters above
4. Capture with your OS screenshot tool or browser dev tools

### Docker

```bash
docker compose up --build
# open http://localhost:3000
```

### Adding to README

Once screenshots are saved here, add them to `README.md` under the Screenshots section:

```markdown
## Screenshots

### Backtest Dashboard
![Backtest Dashboard](docs/screenshots/backtest_dashboard.png)

### Strategy Comparison
![Strategy Comparison](docs/screenshots/strategy_comparison.png)
```
