# Traditional Market AI Quant Research Platform — Architecture

> **Status:** planning artifact. This is the long-term direction for re-targeting
> **QuantLab** toward futures / CFDs / options as first-class instruments, plus a
> real ML + AI research layer on top of the existing methodology toolkit.
>
> **Decision (2026-06-23):** build *inside* the existing QuantLab repo. Do **not**
> fork a parallel project — that would re-implement the backtest engine, options
> stack, and AFML layer already built and tested here.
>
> Status labels: **built** · **extend** · **build-new**.

---

## 0. Reality check — what already exists

This is not a greenfield project. QuantLab already has:

- A lookahead-free vectorized backtest engine + a cross-sectional portfolio
  engine (`backend/app/backtest.py`, `backend/app/scanner/`).
- A full **options stack**: Black–Scholes + Greeks + IV solver, CRR binomial
  tree with American exercise, Monte Carlo (Asian/barrier), IV surface + SVI,
  Heston (`backend/app/options*.py`).
- FX, yield-curve, short-rate (Vasicek/CIR), and credit (Merton/hazard/CDS) labs.
- An **AFML methodology layer**: CUSUM event sampling, triple-barrier labeling,
  purged K-fold + embargo CV, sequential bootstrap, fractional differentiation
  (`backend/app/finml/`).
- Cost model, position sizing, risk management, robustness, sensitivity,
  reproducibility (config hashing), benchmark analytics.
- A Next.js frontend (Globe explore experience, chart system, report export).

**Implication:** the only genuinely new infrastructure is (a) futures
continuous-contract construction and (b) the ML training/inference loop.
Everything else is reuse or a thin overlay.

| Capability | Status | Real work remaining |
|---|---|---|
| Options pricing / Greeks | built (v1) | options *strategy* backtesting on real chains |
| Backtest engine, metrics, risk | built | futures-aware execution (multiplier/tick/rollover) |
| Feature eng / labeling / CV | built (AFML) | wire into an actual training pipeline |
| ML signal module | build-new | the train→predict→backtest loop |
| AutoML engine | build-new | Phase 3 |
| AI research report | build-new | Phase 4 |
| Futures data | research | continuous-contract construction = the hard part |
| CFD data | build-new (small) | a *financing overlay*, not a new data source |
| Experiment tracking | build-new | Phase 2 prerequisite |

---

## 1. Vision

**What it is:** a research-and-education platform to design, validate, and
explain systematic signals on traditional markets (futures, CFDs, options), with
leakage-aware ML and AI-generated research write-ups. Every number is
reproducible; every limitation is stated.

**What it is NOT (hard constraints):**

- Not a live trading bot, broker integration, or order router.
- Not investment advice — the AI assistant *explains computed results and never
  recommends trades*.
- No fabricated data, no cherry-picked benchmarks, no "guaranteed alpha" copy.
- No paid-data key management until a phase explicitly takes it on.

**Horizons:**

- **3 months:** Futures research MVP — ES daily, continuous-contract pipeline,
  AFML features/labels, one ML classifier under purged walk-forward,
  futures-aware backtest, an auto-generated research report. One market, end to
  end, correct.
- **6 months:** ML Signal Lab + AutoML + experiment tracking; 3–5 futures
  markets; AI report generator producing publishable notes.
- **12 months:** CFD financing overlay, options strategy backtesting on real
  chains, dashboard/visualizer polish, a portfolio-grade README with example
  reports and a demo video.

---

## 2. Core modules

Mapped to reuse / extend / build-new so the work is where the table says it is.

1. **Market data module** *(extend `data.py`/`market_data.py`)* — add an
   `instruments/` registry (contract specs) and an `Instrument` abstraction so
   futures/CFD/options share one interface.
2. **Futures data module** *(build-new)* — raw individual contracts →
   **continuous series** via Panama (back-adjusted) and ratio-adjusted methods;
   rollover calendar (volume/OI-based); store *both* raw and adjusted.
3. **CFD data module** *(thin overlay)* — a CFD is the underlying index/FX spot
   **plus a financing/spread model**. Reuse the underlying series; add
   `CFDFinancingModel` (spread, overnight swap/carry, leverage).
4. **Options data module** *(extend)* — pricing is built; the gap is a **chain
   data model** (per-expiry, per-strike quotes + IV) and a historical store.
5. **Feature engineering module** *(extend `finml/`)* — declarative feature spec
   (rolling stats, vol estimators, term-structure/carry features) with a
   leakage-safe transform contract.
6. **Target labeling module** *(built — `finml/labeling.py`, `cusum.py`)* —
   triple-barrier + CUSUM exist; reuse directly.
7. **Strategy module** *(extend `strategies.py`)* — add an `MLSignalStrategy`
   adapter so a trained model's predictions plug into the same backtest engine.
8. **Backtesting engine** *(extend `backtest.py`)* — futures execution layer:
   multiplier, tick rounding, margin, rollover P&L. Keep lookahead discipline.
9. **Options pricing / Greeks module** *(built)* — consume from the
   options-strategy backtester.
10. **ML signal module** *(build-new)* — the `fit/predict` pipeline: feature
    matrix → purged-CV training → out-of-fold predictions → backtest.
11. **AutoML experiment engine** *(build-new, Phase 3)* — bounded search wrapped
    in purged CV + deflated-Sharpe guards.
12. **Risk management module** *(built)* — reuse; add margin-based sizing.
13. **AI research assistant module** *(build-new, Phase 4)* — constrained LLM
    that consumes computed metrics/JSON only, fills a structured template, and
    is forbidden from inventing numbers or recommending trades. Models:
    `claude-opus-4-8` / `claude-sonnet-4-6`.
14. **Report generator** *(extend `saved_reports.py` + `printReport.ts`)* — add
    the AI-narrative section on top of existing Markdown/PDF export.
15. **Dashboard / visualizer** *(extend frontend)* — add experiment-comparison
    and signal-diagnostic views.
16. **Experiment tracking system** *(build-new, Phase 2)* — MLflow local (or a
    sqlite-backed runs table reusing `db.py`). Logs params, metrics, feature
    spec hash, data version hash, CV config, and the existing config hash.

---

## 3. Repository structure

Build inside QuantLab. New/changed pieces marked.

```text
quantlab/
├── backend/
│   └── app/
│       ├── instruments/              # NEW — instrument abstraction & specs
│       │   ├── registry.py           #   contract specs: ES, NQ, CL, GC, 6E…
│       │   ├── base.py               #   Instrument interface (multiplier, tick, sessions)
│       │   ├── futures.py            #   futures-specific (expiry, rollover rules)
│       │   ├── cfd.py                #   CFD wrapper over an underlying (financing/spread)
│       │   └── options_chain.py      #   chain model (expiries, strikes, quotes, IV)
│       ├── data/                     # REFACTOR existing data.py/market_data.py into a pkg
│       │   ├── providers/            #   yfinance, csv, (future) paid feeds
│       │   ├── futures_continuous.py # NEW — Panama / ratio adjustment, roll calendar
│       │   └── store.py              #   parquet/sqlite cache; raw + adjusted separation
│       ├── features/                 # NEW — declarative, leakage-safe feature specs
│       │   ├── spec.py               #   FeatureSpec + transform contract
│       │   └── library.py            #   momentum, vol, carry, term-structure features
│       ├── finml/                    # EXISTS — labeling, cv, bootstrap, frac_diff (reuse)
│       ├── ml/                       # NEW — the training/inference loop
│       │   ├── pipeline.py           #   feature matrix → purged-CV fit → OOF preds
│       │   ├── models.py             #   sklearn/LightGBM wrappers, common interface
│       │   ├── inference.py          #   model → signal series for the backtester
│       │   └── automl.py             #   Phase 3 — bounded search under CV guards
│       ├── experiments/              # NEW — tracking
│       │   ├── tracker.py            #   MLflow or sqlite runs table
│       │   └── registry.py           #   model + dataset versioning
│       ├── ai/                       # NEW — Phase 4
│       │   ├── report_writer.py      #   template-filling over computed JSON
│       │   ├── prompts/              #   versioned prompt templates
│       │   └── guards.py             #   "no invented numbers / no advice" validation
│       ├── backtest.py               # EXTEND — futures execution layer
│       ├── strategies.py             # EXTEND — MLSignalStrategy adapter
│       ├── options*.py               # EXISTS — pricing/Greeks (reuse)
│       ├── cost_model.py             # EXTEND — futures commission + CFD financing
│       ├── metrics.py, risk_*.py     # EXISTS (reuse)
│       └── main.py / schemas.py      # EXTEND — new endpoints/contracts
│       └── tests/                    # mirror every new module 1:1
├── configs/                          # NEW — YAML experiment/instrument/data configs
│   ├── instruments/es.yaml
│   └── experiments/es_triple_barrier_lgbm.yaml
├── data/                             # gitignored — raw/, interim/, processed/, models/
├── notebooks/                        # NEW — EDA only; never the source of truth
├── frontend/                         # EXISTS — extend with experiment & signal views
└── docs/                             # EXISTS — this doc + example reports
```

Rule: **notebooks are scratchpads, `app/` is truth.** Anything a notebook proves
gets promoted into a module with a test before it counts.

---

## 4. Development roadmap

Phases extend the existing blueprint rather than restarting numbering.

- **Phase 1 — Futures research MVP (months 0–3):** instrument registry (ES
  first), continuous-contract pipeline, feature spec, reuse triple-barrier
  labels, one classifier under purged walk-forward, futures-aware backtest,
  deterministic Markdown report. *Exit:* one market, leakage-audited,
  reproducible by config hash.
- **Phase 2 — ML Signal Lab + experiment tracking (months 3–5):** `ml/pipeline.py`,
  model interface, MLflow tracking, OOF-prediction backtests, deflated Sharpe.
  Add NQ, CL, GC, 6E. *Exit:* compare N experiments by tracked metrics.
- **Phase 3 — AutoML experiment engine (months 5–6):** bounded grid/Bayesian
  search wrapped in CV + PBO guards; every trial logged; overfitting alarms.
  *Exit:* AutoML cannot beat the guards silently.
- **Phase 4 — AI research report generator (months 6–7):** constrained LLM
  narrative over computed JSON; prompt versioning; guard layer. *Exit:* a
  publishable note where every number traces to a computed artifact.
- **Phase 5 — CFD support (months 7–9):** `CFDFinancingModel` overlay +
  spread/overnight-swap costs; reuse underlying series. *Exit:* CFD vs
  underlying P&L difference fully explained by financing.
- **Phase 6 — Options strategy backtesting (months 9–11):** chain data model +
  historical options store; backtest defined-risk structures using the existing
  pricer for marks. *Exit:* one options strategy backtested with honest bid/ask
  + liquidity caveats.
- **Phase 7 — Dashboard & visualization (month 11):** experiment comparison,
  signal diagnostics, vol-surface views.
- **Phase 8 — Portfolio polish (month 12):** README, architecture diagram, 3
  example reports, screenshots, demo video, limitations.

---

## 5. MVP scope (smallest *serious* MVP)

**One instrument: ES, daily OHLCV.** End to end:

1. **Data:** front-month ES continuous series, ratio-adjusted *and* raw kept
   side by side; roll on volume/OI crossover; roll dates persisted.
2. **Features:** ~10–15 from `features/library.py` (multi-horizon returns,
   realized vol, ATR, momentum, RSI, day-of-week) — strictly trailing-window.
3. **Labels:** triple-barrier (`finml/labeling.py`) with vol-scaled barriers;
   CUSUM event sampling so not every bar is labeled.
4. **Split:** purged K-fold + embargo for tuning, then a single held-out final
   test window touched once.
5. **Model:** logistic regression baseline → LightGBM. Baseline first to prove
   the ML adds value.
6. **Backtest:** predictions → `MLSignalStrategy` → existing engine with ES
   execution: multiplier **50**, tick **0.25 = $12.50**, commission + slippage
   in ticks, next-bar-open execution (no signal-bar fill).
7. **Metrics:** existing Sharpe/Sortino/maxDD/turnover + **deflated Sharpe**
   given the number of trials run.
8. **Report:** deterministic Markdown first (template + computed numbers, no
   LLM); the LLM narrative is Phase 4. Includes leakage/cost/overfitting caveats
   automatically.

Resist adding markets until this single pipeline is correct and reproducible.

---

## 6. Data assumptions & what's hard

**Futures backtesting needs:** individual contract OHLCV + volume/OI (for roll
timing) + contract specs (multiplier, tick, expiry, session). *Hard part:*
**continuous-contract construction.** Back-adjusted (Panama) series shift
historical prices so absolute levels are fictitious — never run absolute-price
logic (e.g. "price > 4000") or naive percentage-return calcs on back-adjusted
data near rolls. Keep raw contracts; compute returns from the *held* contract,
not across the roll seam. Roll method and date are logged parameters — they
change results.

**CFD backtesting needs:** essentially the underlying spot/index/FX series + a
**financing model**. The hard part isn't data, it's honesty: CFD P&L =
underlying move − spread − **overnight financing** (long pays, short may
receive; rate ≈ benchmark ± broker markup) − dividend adjustment. Broker-specific
and opaque; model it explicitly and label results "illustrative,
broker-dependent."

**Options backtesting needs:** historical **chains** (per expiry/strike:
bid/ask, IV, volume, OI) + the underlying. Hard parts: bid/ask spreads dominate
P&L, liquidity is concentrated, the IV surface must be arbitrage-aware, and EOD
marks ≠ executable prices. Free historical chain data barely exists — hence
Phase 6, not MVP. Until then, the existing pricer marks positions but the
bid/ask realism gap must be flagged.

---

## 7. Backtesting assumptions (mechanics to model explicitly)

- **Transaction costs:** commission per contract (futures); charge on entry and exit.
- **Slippage:** model in *ticks* for futures, not bps; conservative default 1 tick/side.
- **Spread:** half-spread on each fill for CFDs/options; dominant cost for options.
- **Overnight fees / carry:** CFD financing (above); futures have no overnight
  fee but carry is embedded in the term structure — capture via roll yield.
- **Margin & leverage:** size by initial/maintenance margin; cap CFD notional;
  surface a margin-call check.
- **Contract multiplier & tick size:** from `instruments/registry.py`; round all
  fills to tick; P&L = ticks × tick-value.
- **Expiry / rollover (futures):** roll on the calendar rule; realize the old
  position and open the new at *its* price — no phantom P&L from the
  back-adjusted seam.
- **Option expiration:** settle ITM at intrinsic, OTM at zero; model assignment
  for short legs.
- **Greeks / IV:** reuse the engine; mark with surface-consistent IV, not flat vol.

**Execution timing rule (non-negotiable):** a signal computed from bar *t*'s
close executes at bar *t+1*'s open. This is already the engine's discipline —
keep it for ML signals.

---

## 8. Risk & bias checklist

Bake these into the report as automated checks where possible.

- **Look-ahead bias** — features use only data ≤ signal time; next-bar execution.
- **Data leakage** — purged CV + embargo; feature scaling fit on train folds
  only; the embargo must cover the max triple-barrier horizon.
- **Survivorship bias** — include delisted/expired contracts in any universe work.
- **Overfitting** — baseline-first; deflated Sharpe and PBO; cap and log the
  number of trials.
- **Timestamp alignment** — one timezone (exchange time), explicit sessions,
  aligned across instruments before joining.
- **Unrealistic execution price** — no signal-bar fills; tick rounding;
  slippage + spread always on.
- **Costs/slippage/spread ignored** — engine shows cost-laden Sharpe alongside
  any frictionless number.
- **Futures rollover mistakes** — within-contract returns; roll method logged;
  sanity-check no return spike on roll dates.
- **Options bid/ask, liquidity, surface errors** — flag wide spreads, thin OI,
  arbitrage violations.
- **Wrong train/test split** — final test window touched exactly once; no
  re-tuning after peeking.

---

## 9. Coding standards

- **Style:** `ruff` + `black`, `mypy` on `app/`. Type every public function.
- **Testing:** `pytest`; mirror each new module with a test. Run with
  `backend\venv\Scripts\python.exe -m pytest` (global Python lacks pytest). Add
  "leakage tests": shuffled-label sanity checks, embargo-coverage assertions.
- **Logging:** stdlib `logging` with structured context (run_id, instrument,
  config_hash) — not `print`.
- **Configuration:** YAML in `configs/`, loaded into Pydantic models. No magic
  numbers in code.
- **Data storage:** parquet for processed feature matrices; sqlite (reuse
  `db.py`) for runs/metadata; `data/` gitignored; raw vs processed separated.
- **Notebooks vs scripts:** notebooks for EDA only; promote to `app/` + test
  before anything depends on it.
- **Reproducibility:** seed everything; persist config hash + data version hash +
  feature spec hash + library versions per run.
- **Experiment tracking:** MLflow local; every run logged with the hashes above
  so any number in a report is replayable.

---

## 10. Final deliverables (portfolio package)

- **README** leading with honest positioning + a "real vs illustrative" table.
- **Architecture diagram** (data → features → labels → ML → backtest → report).
- **3 example AI reports** with every number traceable.
- **Backtest results** with cost-on/cost-off and deflated Sharpe side by side.
- **Dashboard screenshots** (experiment comparison + signal diagnostics).
- **Sample notebooks** showing EDA → promotion to module.
- **Demo video script** (extend `docs/DEMO_SCRIPT.md`).
- **Limitations section** (extend `docs/LIMITATIONS.md`) — data quality, no live
  execution, options bid/ask gap, CFD broker-dependence, overfitting risk.
```

---

## Appendix A — Phase 1 build plan: futures data pipeline

The chosen first build. Design-level (no implementation code yet).

### A.1 `instruments/base.py` — Instrument interface
Responsibilities: a frozen dataclass / Pydantic model describing one tradable
contract spec. Fields: `symbol`, `name`, `asset_class`, `currency`,
`multiplier`, `tick_size`, `tick_value`, `exchange`, `session_tz`,
`roll_rule` (enum: volume_oi, calendar_n_days_before_expiry),
`adjustment_default` (panama|ratio|none). No I/O, no pandas — pure spec.

### A.2 `instruments/registry.py` — contract specs
Responsibilities: a dict/registry of `Instrument` specs loaded from
`configs/instruments/*.yaml`. Phase 1 ships **ES** only; structure must make
adding NQ/CL/GC/6E a one-file change. Reference values to encode:

| Symbol | Multiplier | Tick | Tick value |
|---|---|---|---|
| ES | 50 | 0.25 | $12.50 |
| NQ | 20 | 0.25 | $5.00 |
| CL | 1,000 | 0.01 | $10.00 |
| GC | 100 | 0.10 | $10.00 |
| 6E | 125,000 | 0.00005 | $6.25 |

### A.3 `data/futures_continuous.py` — the hard part
Responsibilities, in order:
1. **Ingest** individual contract OHLCV+volume+OI (raw, never mutated).
2. **Roll calendar**: pick roll dates by volume/OI crossover (front loses
   leadership to next) with a fallback calendar rule; persist roll dates.
3. **Stitch** a continuous series two ways: **ratio-adjusted** (multiplicative,
   safe for returns) and **Panama/back-adjusted** (additive, for charting only).
4. **Store both** raw and each adjusted series via `data/store.py`, tagged with a
   data-version hash.
5. **Return-correctness contract**: returns are computed within the *held*
   contract, never across the roll seam.

### A.4 `data/store.py` — cache
Responsibilities: parquet read/write for raw + adjusted series; sqlite metadata
(roll dates, data-version hash, provider, fetch timestamp). Reuse `db.py`.

### A.5 Tests (write alongside, not after)
- Roll calendar picks the expected date on a synthetic volume/OI crossover.
- Ratio-adjusted series has **no return spike** on roll dates (within tolerance).
- Back-adjusted series is explicitly flagged not-for-returns.
- Data-version hash is stable for identical inputs, changes when inputs change.
- A leakage guard: continuous series at time *t* uses no contract data dated > *t*.

### A.6 Phase 1 exit criteria
ES continuous series (both adjustments) reproducible from raw by config hash,
roll dates persisted and explained, zero phantom-return artifacts at the seam,
all tests green under `backend\venv\Scripts\python.exe -m pytest`.
