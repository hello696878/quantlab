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
│       ├── datastore/                # NEW — futures data layer (named to avoid app/data.py)
│       │   ├── store.py              #   raw schema validation + parquet/CSV storage
│       │   └── futures_continuous.py #   roll calendar + ratio/Panama stitching
│       ├── data.py, market_data.py   # EXISTS — provider modules (yfinance/CSV)
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

### A.3 `datastore/futures_continuous.py` — the hard part
Responsibilities, in order:
1. **Ingest** individual contract OHLCV+volume+OI (raw, never mutated).
2. **Roll calendar**: pick roll dates by volume/OI crossover (front loses
   leadership to next) with a fallback calendar rule; persist roll dates.
3. **Stitch** a continuous series two ways: **ratio-adjusted** (multiplicative,
   safe for returns) and **Panama/back-adjusted** (additive, for charting only).
4. **Store both** raw and each adjusted series via `datastore/store.py`, tagged with a
   data-version hash.
5. **Return-correctness contract**: returns are computed within the *held*
   contract, never across the roll seam.

### A.4 `datastore/store.py` — cache
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

---

## Appendix B — Phase 1 progress (futures data pipeline)

Built incrementally on the `phase1-futures` branch (worktree-isolated from
concurrent work on `main`). Modules live under `backend/app/instruments/` and
`backend/app/datastore/` (the `datastore` name avoids colliding with the
existing `app.data` provider module).

| Commit | Scope |
|---|---|
| **Commit 1** | ES futures instrument spec layer (`instruments/`: validated, immutable `FuturesSpec`; CME month codes; third-Friday expiry; registry). |
| **Commit 2** | Raw futures schema validation + local storage (`datastore/store.py`: `validate_raw_futures`, `raw_data_version_hash`, `RawFuturesStore`, CSV fallback when parquet is unavailable). |
| **Commit 2.5** | Local data/artifact `.gitignore` safety (block raw/processed data, models, experiment outputs from being committed). |
| **Commit 3** | Futures roll calendar (`datastore/futures_continuous.py`: `compute_roll_schedule` — volume/OI primary rule, days-before-expiry fallback, deterministic, no silent assumptions). |
| **Commit 4** | Continuous futures stitching with ratio and Panama adjustment (`build_continuous_futures`); raw vs adjusted stored separately. |
| **Commit 5** | Reproducibility hash (`continuous_config_hash`) + end-to-end synthetic validation; this progress note. |

### B.1 Adjustment warnings (must be surfaced in any report)

- **Prefer ratio-adjusted** series for return-based analysis: it preserves the
  held contract's percentage returns across roll seams.
- **Panama-adjusted** series preserves *point changes* but **distorts percentage
  returns** — use it for level/spread study and charting, not return P&L.
- **Back-adjusted historical price levels are fictitious** (both methods); never
  apply absolute-price logic to them.
- **Raw held-contract prices (`*_raw`) remain the source of truth for execution**
  — adjusted columns are derived and must never be treated as traded prices.

> Scope note: Phase 1 is the futures *data pipeline* only — no ML, no backtest
> integration, no AI report, no CFD/options, no real-data download. Data is
> synthetic/illustrative; correctness (lookahead-free, seam-correct, reproducible)
> comes before breadth.

---

## Appendix C — Phase 2 Futures Feature Engineering

Phase 2 builds the **feature engineering layer** on top of the Phase 1 ES
continuous pipeline: it turns a **ratio-adjusted** continuous frame into a
**leakage-safe feature matrix** for later ML and backtesting. **Implemented** in
`backend/app/features/` (commits 1–5). Sections C.1–C.9 describe the design;
**§C.10 records the as-built status.**

### C.1 Scope

**In scope:** a `backend/app/features/` package that consumes the Phase 1
`CONTINUOUS_COLUMNS` frame and produces a deterministic, trailing-window-only
feature matrix with explicit warmup handling and a feature config hash chained to
Phase 1's `continuous_config_hash`. Synthetic-only tests.

**Explicitly NOT in scope:** **ML training/inference, target labels** (features
only — no future-return columns of any kind), **backtest integration**, AI report
generation, **CFD, options**, **frontend**, and **real-data download / network**.
ES only; no cross-sectional/multi-instrument features; no feature scaling or
one-hot encoding (the ML layer owns those).

### C.2 Feature engineering principles

1. **Trailing-window only** — every window is `[t-w+1, t]`; no centered windows,
   no negative shifts, no peeking `min_periods`.
2. **No future data** — a value at `t` uses rows `≤ t` only (proven by the
   truncation-invariance test, §C.6).
3. **No same-bar execution leakage** — features may use `close_t`; the consuming
   backtest executes at `t+1`'s open (Phase 1 rule). The feature layer emits no
   labels and never assumes same-bar fills.
4. **Ratio-adjusted series for return-based features** — return / volatility /
   level / indicator features read `*_adjusted` and the builder **requires
   `adjustment_method == "ratio"`** (ratio preserves held-contract % returns
   across seams).
5. **Panama-adjusted series is rejected for percentage-return features** — a
   Panama continuous frame passed to a ratio-required feature raises
   `FeatureError`. Panama distorts % returns (preserves point changes only).
6. **`*_raw` prices remain execution/reference prices, not the default input for
   return features** — raw held-contract prices are available only via an
   explicit `price_space = RAW`; the default input for return-based features is
   the ratio-adjusted series.
7. **Deterministic computation** — pure pandas/numpy, no RNG, no wall-clock; same
   input + config ⇒ identical matrix.
8. **Feature config hash** — SHA-256 over canonical JSON of the `FeatureSpec`
   set, **chained with the upstream `continuous_config_hash`** (raw → continuous
   → features provenance).
9. **No network calls in tests; synthetic fixtures first.**

### C.3 Proposed module structure (no naming collisions; `app/features` is free)

| File | Responsibility |
|---|---|
| `backend/app/features/__init__.py` | Public exports. |
| `backend/app/features/spec.py` | `FeatureSpec` model + enums (`TransformType`, `PriceSpace`), `DEFAULT_ES_FEATURES` registry, `feature_config_hash`. Pure config, no math. |
| `backend/app/features/futures_features.py` | `build_feature_matrix(continuous_df, specs)` + per-transform pure functions. |
| `backend/app/features/validation.py` | Input/spec validation + leakage helpers (`validate_continuous_input`, `validate_feature_specs`, `mark_warmup`, `assert_causal`). |
| `backend/tests/test_futures_features.py` | All Phase 2 tests (synthetic). |

Dependency direction: `features/` → `datastore/` + `instruments/` (never the reverse).

### C.4 `FeatureSpec` design

Frozen, strict (Pydantic v2, `frozen=True, extra="forbid"`), fields:

| Field | Meaning |
|---|---|
| `name` | unique feature id (default output column name) |
| `transform` | `RETURN, REALIZED_VOL, ROLLING_MAX, ROLLING_MIN, RATIO_TO_ROLLING_MAX, RATIO_TO_ROLLING_MIN, MA_GAP, RSI, ATR, ZSCORE, CALENDAR_DOW, PASSTHROUGH, DAYS_SINCE_FLAG` |
| `input_columns` | continuous columns consumed (e.g. `["close_adjusted"]`; ATR → high/low/close) |
| `windows` | trailing windows (`[20]`, `[10,50]`, or `[]` for pointwise) |
| `price_space` | `ADJUSTED` (default, requires ratio), `RAW` (execution ref), `NONE` (calendar/volume/roll) |
| `required_adjustment` | `RATIO` for return/level/indicator features; `None` for calendar/roll/volume |
| `params` | transform-specific (e.g. `{"period": 14}`) |
| `warmup` | computed leading-invalid row count |
| `output_name` | defaults to `name` |
| `description` | intent + adjustment rationale |

Validation: unique names; positive windows; required `params` present; `price_space`
consistent with `required_adjustment` (ADJUSTED ⇒ a method; NONE ⇒ None).

### C.5 Initial ES feature set

All trailing; all read `*_adjusted` (ratio) unless noted.

| Feature | Formula | Warmup | Adj. | Notes |
|---|---|---|---|---|
| `return_1` | `close_t/close_{t-1} − 1` | 1 | ratio | scale-invariant |
| `return_5` | `close_t/close_{t-5} − 1` | 5 | ratio | |
| `return_20` | `close_t/close_{t-20} − 1` | 20 | ratio | |
| `realized_vol_20` | std of `return_1` over 20, **annualized ×√252** | ~21 | ratio | **annualized by default — see assumption below** |
| `rolling_high_20` | rolling max of high, 20 | 20 | ratio | absolute level is in back-adjusted space |
| `rolling_low_20` | rolling min of low, 20 | 20 | ratio | back-adjusted level |
| `close_to_rolling_high_20` | `close/rolling_high − 1` | 20 | ratio | scale-invariant (preferred) |
| `close_to_rolling_low_20` | `close/rolling_low − 1` | 20 | ratio | scale-invariant |
| `moving_average_gap_10_50` | `(MA10 − MA50)/MA50` | 50 | ratio | relative, scale-invariant |
| `RSI_14` | Wilder RSI of close | 14 (+recursive tail) | ratio | scale-invariant |
| `ATR_14` | Wilder ATR (true range) | 14 (+tail) | ratio | points in adjusted space |
| `ATR_14_pct` | `ATR_14 / close` | 14 (+tail) | ratio | **preferred over `ATR_14` for ML — scale-relative** |
| `volume_zscore_20` | `(vol − roll_mean20)/roll_std20` | 20 | none | volume has a contract-level discontinuity at rolls (documented) |
| `day_of_week` | weekday of session date (0–4) | 0 | none | numeric; ML layer may one-hot |
| `roll_flag` | passthrough | 0 | none | known at `t` |
| `days_since_roll` | sessions since last `roll_flag ≤ t` | 0 | none | NaN before the first roll in the frame (explicit) |

**Annualization assumption (`realized_vol_20`):** the default output is the
standard deviation of daily ratio-adjusted returns over a 20-session trailing
window, **multiplied by √252** (252 trading days/year). This is a convention, not
a measured value; the un-annualized daily σ is `realized_vol_20 / √252`.

**`ATR_14_pct` is preferred over `ATR_14` for ML** because it is scale-relative
(comparable across time and price levels), whereas raw `ATR_14` is expressed in
back-adjusted points whose absolute scale is fictitious for history. The same
preference applies to `close_to_rolling_*` over the absolute `rolling_high/low`.

### C.6 Leakage checks (tests)

| Test | Method |
|---|---|
| features at `t` use only data ≤ `t` | **Truncation-invariance:** matrix on full frame vs on `frame[:t+1]` must give identical row `t` (incl. across a roll seam). |
| no future returns | structural (no negative lag/window) + invariance test |
| rolling windows trailing only | manual recompute of a rolling value + invariance |
| input continuous frame not mutated | `assert_frame_equal(input, before)` |
| deterministic output | build twice → `assert_frame_equal` |
| feature hash changes on config change | change a window → hash differs |
| feature hash stable for same input/config | same specs + same `continuous_config_hash` → same hash |
| warmup handled explicitly | `is_warmup` marks exactly the invalid rows; NaNs confined to warmup; **no fill/interpolation** |
| Panama rejected for returns | Panama frame → `FeatureError` |
| seam uses adjusted, not raw gap | `return_1` at a roll = held ratio return, not the raw inter-contract gap |

### C.7 Output feature-matrix schema

| Column | Meaning |
|---|---|
| `timestamp` | tz-aware UTC, unique, monotonic |
| `root_symbol` | `ES` |
| `active_contract` | held contract |
| `<feature columns…>` | the features above |
| `is_warmup` | bool — True until all trailing-window features are valid |
| `source_adjustment_method` | `ratio` (the space features were built on) |
| `feature_config_hash` | constant per build; chains `continuous_config_hash` + spec-set hash |

Metadata columns are constant per build (provenance). The feature layer never
drops or fills silently — `is_warmup` lets the ML layer drop warmup rows
explicitly (`drop_warmup=False` default).

### C.8 Commit plan

| Commit | Objective | Files | Tests | Acceptance |
|---|---|---|---|---|
| **1 — FeatureSpec + validation** | config + input/spec validation, no math | `features/__init__.py`, `spec.py`, `validation.py`, `tests/test_futures_features.py` | spec validation, ratio-input guard, hash stability | specs validate; non-ratio input rejected; hash deterministic |
| **2 — Price/return/vol features** | `build_feature_matrix` + `return_*`, `realized_vol_20`, `rolling_high/low_20`, `close_to_rolling_*` | `futures_features.py`, `spec.py`, tests | truncation-invariance, not-mutated, determinism, manual rolling, seam-uses-adjusted, warmup | features match hand-computed values; invariance holds across seam |
| **3 — Indicators (RSI/ATR/MA gap)** | `moving_average_gap_10_50`, `RSI_14`, `ATR_14`, `ATR_14_pct` | `futures_features.py`, `spec.py`, tests | RSI/ATR vs reference; Wilder warmup documented; invariance | indicators match reference within tolerance; trailing-only |
| **4 — Roll metadata features** | `volume_zscore_20`, `day_of_week`, `roll_flag`, `days_since_roll` | `futures_features.py`, `spec.py`, tests | `days_since_roll` resets per roll & NaN before first roll; weekday/passthrough correct | roll/calendar features correct and causal |
| **5 — Hash chaining + e2e + docs** | finalize `feature_config_hash` chaining, full e2e, docs | `spec.py`/`futures_features.py`, tests, this doc | e2e raw→continuous→features; hash changes on either config change | matrix reproducible by hash; all leakage/determinism tests green |

### C.9 Risks & mitigations

| Risk | Mitigation |
|---|---|
| Look-ahead bias | trailing-only windows + truncation-invariance test |
| Using raw continuous gaps for returns | return/level features read `*_adjusted`; seam test asserts held return, not raw gap |
| Using Panama for % returns | builder rejects Panama for ratio-required features (`FeatureError`) |
| Bad warmup handling | explicit `is_warmup`; NaNs confined to warmup; no fill/interpolation |
| Accidental mutation | build on a copy; `assert_frame_equal(input, before)` test |
| Mixing raw/adjusted incorrectly | per-spec `price_space` + `required_adjustment`, validated against the frame's `adjustment_method` |
| Volume contract discontinuity at rolls | documented on `volume_zscore_20`; per-contract normalization is future work |
| RSI/ATR recursive tail | Wilder stabilization documented; ~3×period treated as low-confidence |

> Scope note: Phase 2 is feature engineering only — **no ML training, no target
> labels, no backtest integration, no CFD/options, no frontend, no real-data
> download.** Ratio-adjusted continuous futures are the input for return-based
> features; Panama is rejected for percentage returns; `*_raw` stays as
> execution/reference prices.

### C.10 As-built status (Phase 2 complete)

Implemented in `backend/app/features/` across five commits; tests are synthetic
only, no network. `build_feature_matrix(continuous_df, specs=DEFAULT_ES_FEATURES,
upstream_continuous_hash=None, drop_warmup=False)` consumes a Phase 1 continuous
frame and returns the matrix below.

**16 ES features (all built):** `return_1`, `return_5`, `return_20`,
`realized_vol_20`, `rolling_high_20`, `rolling_low_20`,
`close_to_rolling_high_20`, `close_to_rolling_low_20`,
`moving_average_gap_10_50`, `RSI_14`, `ATR_14`, `ATR_14_pct`, `volume_zscore_20`,
`day_of_week`, `roll_flag`, `days_since_roll`.

**Adjustment discipline (enforced):** return / level / indicator features read
`*_adjusted` and require `adjustment_method == "ratio"`; a Panama (or any
non-ratio) frame raises `FeatureError`. **`*_raw` prices stay as
execution/reference and are never the default feature input.** Volume / calendar
/ roll features use `price_space = NONE` (no adjustment).

**Warmup:** `is_warmup` is True on any row where a trailing-window feature is
still NaN (longest is `moving_average_gap_10_50`, first valid at index 49). No
fill / interpolation. **`days_since_roll` is excluded from `is_warmup`** — it is
NaN before the first roll in the frame *by design* (a documented condition, not a
warmup), so a non-warmup row may legitimately carry a NaN `days_since_roll`.

**Per-feature conventions:**
- `realized_vol_20`: sample std (ddof=1) of daily ratio-adjusted returns over 20
  sessions, **annualized ×√252** (a convention, not a measured value).
- `RSI_14`: Wilder smoothing (seed = SMA of the first 14 changes, then the
  recursive update); **zero-loss windows → RSI 100**.
- `ATR_14`: Wilder ATR in **adjusted price points** (back-adjusted absolute scale
  is fictitious for history). The first bar has no prior close, so no true range.
  **`ATR_14_pct = ATR_14 / close` is the ML-preferred, scale-relative form.**
- `volume_zscore_20`: trailing z-score of `volume`; futures volume is
  contract-specific and not back-adjusted, so it can **jump around roll periods**.
- `day_of_week`: session weekday 0–4 (numeric, no one-hot).

**Reproducibility / provenance:** `feature_config_hash(specs,
continuous_config_hash=None)` is SHA-256 over a canonical JSON of the spec set
(order-stable by name), **chained with the upstream Phase 1
`continuous_config_hash`** — giving full raw → continuous → features provenance.
The hash changes when the feature config changes OR when the upstream continuous
hash changes; it is stable for identical config. It is emitted as a constant
column in the matrix alongside `source_adjustment_method`.

**Leakage guarantees (test-proven):**
- **Truncation-invariance** — a feature at `t` is identical whether computed on
  the full frame or on `frame[:t+1]` (tested before / on / after a roll seam).
- **Roll-seam return** — `return_1` at a roll equals the held contract's
  ratio-adjusted return, never the raw inter-contract price gap.
- **Input non-mutation** — the continuous input frame is never modified.
- **Deterministic output** — identical input + config ⇒ identical matrix, and
  row-order differences in the raw input wash out after normalization.

---

## Appendix D — Phase 3 Futures Labels, Signal Timing, and Backtest Integration Plan

Phase 3 turns the Phase 1 continuous data + Phase 2 feature matrix into
**supervised-learning-ready datasets** and a **deterministic rule-based baseline**
run through a **futures-aware vectorized backtest** — all leakage-safe and
reproducible by hash. This appendix is a plan — not yet implemented.

**Locked design decisions:**

1. **Do not create `backend/app/backtest/`** — `backend/app/backtest.py` already
   exists as a module and a same-named package would collide (the Phase 1
   `app/data.py` situation).
2. The futures backtest adapter lives in **`backend/app/futures_backtest/`**.
3. It **reuses `app.backtest.run_backtest` internally** rather than replacing it.
4. **Forward-return labels respect the `t+1` execution rule:**
   `forward_return_h(t) = close_adjusted[t + execution_lag + h] /
   close_adjusted[t + execution_lag] − 1`, with `execution_lag` defaulting to 1.
5. Features at `t` are observed **after `close_t`**.
6. A signal generated from features at `t` may execute **no earlier than
   `open_{t+1}`**.
7. Backtest positions use **`signal.shift(1)`**.
8. **Ratio-adjusted** prices are used for return labels and strategy return math.
9. **Raw held-contract** prices are execution/reference prices — fills, tick
   rounding, and dollar-PnL reference.
10. **No ML training in Phase 3.**

### D.1 Scope

**In scope:** `LabelSpec` + forward-return / direction / vol-adjusted /
triple-barrier labels; a supervised **dataset assembler** (features + labels +
provenance hashes + `is_warmup`); a **non-ML baseline signal** (momentum + vol
filter + roll avoidance); a **futures backtest adapter** reusing `run_backtest`
with explicit costs / slippage / tick / multiplier and roll handling.

**Explicitly NOT in scope:** **ML model training/inference** (no fit/predict, no
sklearn/LightGBM), AutoML, hyperparameter search, purged-CV wiring (the AFML CV
exists; wiring it is a later phase), AI report, CFD, options, frontend,
real-data download, paid feeds, live trading.

### D.2 Labeling principles

1. **No look-ahead leakage in features.** Features at `t` use data `≤ t` (Phase 2
   guarantee, truncation-tested). Labels are the only thing allowed to read the future.
2. **Labels may use future returns; features may not.** Disjoint column
   namespaces; the assembler never feeds a label (or any forward-looking column)
   into the feature set.
3. **Explicit label-timestamp alignment.** A sample is keyed at `t`: `X(t)` =
   features (`≤ t`), `Y(t)` = the return realized by acting on the signal at `t`,
   measured **from the execution bar `t + execution_lag`**.
4. **Signal-at-`t` executes at `t+1`.** In the backtest `position = signal.shift(1)`.
   No same-bar fills.
5. **Raw held-contract prices are the execution/PnL reference** — fills at
   `open_raw[t+1]`, rounded to tick; commissions per contract in dollars.
6. **Ratio-adjusted prices for return labels and the return/equity math** —
   `close_adjusted` (ratio) gives the held-contract return across roll seams, so
   labels and equity carry **no fake roll PnL**. (Using raw close for *returns*
   would manufacture the inter-contract gap — the trap to avoid.)
7. **Costs/slippage explicit** from the instrument spec
   (`commission_per_contract_per_side`, `slippage_ticks_per_side`, `tick_size`,
   `tick_value`, `contract_multiplier`) — never zero by default.
8. **Warmup excluded.** Training/backtest datasets drop `is_warmup` rows and rows
   with NaN labels (the last `execution_lag + horizon` bars).

### D.3 Proposed module structure (collisions resolved)

| File | Responsibility |
|---|---|
| `backend/app/labels/__init__.py` | exports |
| `backend/app/labels/spec.py` | `LabelSpec` + enums (`LabelType`, `ReturnType`, `PriceSpace`), `DEFAULT_ES_LABELS`, `label_config_hash` |
| `backend/app/labels/futures_labels.py` | `build_label_matrix(continuous_df, specs)` + per-type label fns; wraps `finml.triple_barrier_labels` |
| `backend/app/labels/dataset.py` | `build_supervised_dataset(...)` — joins features + labels + provenance; drops warmup / NaN-label rows |
| `backend/app/signals/__init__.py` | exports |
| `backend/app/signals/baseline.py` | `momentum_baseline(feature_df, config)` → deterministic position series |
| `backend/app/futures_backtest/__init__.py` | exports |
| `backend/app/futures_backtest/futures_vectorized.py` | `run_futures_backtest(...)` — reuses `app.backtest.run_backtest`, adds tick / multiplier / roll-cost layer |
| `backend/tests/test_futures_labels.py` | label + dataset tests |
| `backend/tests/test_futures_signal_backtest.py` | signal + backtest tests |

Dependency direction: `labels` / `signals` / `futures_backtest` → `features` →
`datastore` → `instruments` (+ reuse `app.backtest`, `app.cost_model`,
`app.metrics`, `app.finml`). Never the reverse.

### D.4 `LabelSpec` design

Frozen, strict Pydantic (matching `FeatureSpec` / `FuturesSpec`):

| Field | Meaning |
|---|---|
| `name` | unique label id / default output column |
| `label_type` | `FORWARD_RETURN, DIRECTION, VOL_ADJUSTED_RETURN, TRIPLE_BARRIER` |
| `horizon` | bars held (e.g. 1, 5) |
| `input_column` | price source — **`close_adjusted`** for return labels (ratio) |
| `price_space` | `ADJUSTED` (ratio, required for returns) — Panama/raw rejected, as in Phase 2 |
| `return_type` | `SIMPLE` (`p[t+L+h]/p[t+L] − 1`) or `LOG` |
| `threshold` | deadband for `DIRECTION` (e.g. ±0.0 → sign; >0 → neutral zone) |
| `execution_lag` | **default 1** — label measured from the execution bar `t+L` |
| `output_column` | defaults to `name` |
| `warmup` / `drop_rule` | trailing `execution_lag + horizon` rows have no label → NaN; dataset drops them |
| `params` | type-specific (triple-barrier: `profit_take`, `stop_loss`, `vertical_barrier`, vol source, event source) |

**Label definitions (`L = execution_lag`, default 1):**
- `forward_return_h(t) = close_adj[t+L+h] / close_adj[t+L] − 1` — the return
  earned by acting on signal(`t`) at `t+1`, held `h`.
- `direction_h(t) = sign(forward_return_h(t))` with optional `threshold` deadband
  → `{−1, 0, +1}` (or `{0,1}` binary).
- `volatility_adjusted_return(t) = forward_return_h(t) / realized_vol_20(t)` —
  the vol scaler is the *trailing feature* at `t` (leakage-free); only the
  numerator is forward.
- `triple_barrier(t)` — wraps `finml.triple_barrier_labels` on `close_adj` with
  CUSUM events (`finml.cusum`) and `rolling_vol`; AFML guarantees label-only
  future use. Optional AFML uniqueness `sample_weight`.

The last `L + h` rows get NaN labels (no forward window) — explicit, never fabricated.

### D.5 Supervised dataset schema

`build_supervised_dataset` returns one row per session with disjoint
feature/label namespaces:

| Column group | Columns |
|---|---|
| keys | `timestamp`, `root_symbol`, `active_contract` |
| features | the 16 Phase 2 features |
| labels | `label__forward_return_5`, `label__direction_1`, … |
| flags | `is_warmup` (from features), `is_label_valid` (label not NaN) |
| provenance | `continuous_config_hash`, `feature_config_hash`, `label_config_hash` |
| optional | `sample_weight` (e.g. AFML uniqueness for triple-barrier), `split` (train/val/test, filled later) |

A `trainable` view = rows where `not is_warmup and is_label_valid`.
`label_config_hash` chains `feature_config_hash` (which chains
`continuous_config_hash`) → full **raw → continuous → features → labels**
provenance.

### D.6 Signal timing & execution rules

```
close_t observed ─► features X(t) (≤ t) ─► signal s(t) decided after close_t
                                                  │
                                 position effective at open_{t+1}  (= s(t))
backtest:  position = signal.shift(1) ; return_t = position_t × pct_change(close_adj)_t
fills:     reference price = open_raw[t+1], rounded to tick_size ; cost in $ per contract
```

- Features at `close_t`; signal after `close_t`; earliest execution `open_{t+1}`;
  `position = signal.shift(1)` enforces it (no same-bar leakage).
- PnL/return from **ratio-adjusted close** (seam-safe); **raw prices are the
  execution reference** (fill price + tick rounding + $-denominated cost).
- Last rows with no forward label are excluded from training; in the backtest the
  final position has no forward return and contributes nothing (or is dropped).

### D.7 Baseline signal strategy (non-ML, deterministic)

`momentum_baseline(feature_df, cfg)` → position series in `{0, +1}` (long/flat) or
`{−1, 0, +1}` (long/short):
- **Momentum entry:** `return_20 > 0` **and** `moving_average_gap_10_50 > 0`.
- **Volatility filter:** require `realized_vol_20 ≤ cfg.vol_cap` (or
  `ATR_14_pct ≤ cfg.atr_cap`) — flat when too volatile.
- **Roll avoidance:** flat for `cfg.roll_buffer` sessions around any `roll_flag`
  (uses `days_since_roll` / `roll_flag`, both known at `t`).
- **Long/short option:** symmetric short when both momentum signals are negative.
- Deterministic (pure function of the feature matrix); warmup rows → flat (0).
  Output is the *target* position at `t`; the backtest applies the `t+1` shift.

### D.8 Backtest integration

`run_futures_backtest(continuous_df, position, spec, *, slippage_ticks=None,
commission_per_contract=None, roll_buffer_cost=True)`:
- **Position alignment:** `position.shift(1).fillna(0)` (signal-at-`t` →
  effective `t+1`).
- **Return/equity:** reuse `app.backtest.run_backtest(close=close_adjusted,
  position=shifted, transaction_cost_bps=…)` — correct held-contract returns, no
  roll-gap PnL.
- **Execution price reference:** `open_raw[t+1]`, rounded to `spec.tick_size`;
  used to translate returns ↔ dollars and to compute tick-based slippage.
- **Costs:** commission `spec.costs.commission_per_contract_per_side`
  ($/contract, both sides) + slippage `spec.costs.slippage_ticks_per_side ×
  tick_value`, converted to effective per-side bps for the engine (reported in
  dollars). **Charged only on `|Δposition| > 0`.**
- **Roll-day handling:** on `roll_flag` days the held position is rolled (close
  old + open new) → an **extra round-turn cost** even if the strategy position is
  unchanged; returns stay seam-safe (ratio) so no fake roll PnL.
- **Contract multiplier / tick** from `spec` for $-denominated P&L, contract
  sizing, and tick rounding.
- **Output metrics:** reuse `app.metrics` (Sharpe / Sortino / maxDD / turnover) +
  the trade log from `run_backtest`; report cost-on vs cost-off.

### D.9 Tests

| Test | Where |
|---|---|
| forward-return labels match manual `close_adj[t+L+h]/close_adj[t+L]−1` | `test_futures_labels` |
| label uses future price but the feature matrix at `t` does not | `test_futures_labels` |
| feature row `t` aligns with label `t` and execution `t+1` | `test_futures_signal_backtest` |
| no same-bar execution leakage — backtest return at `t` uses `position.shift(1)` | `test_futures_signal_backtest` |
| last `L+h` rows have NaN labels / are dropped explicitly | `test_futures_labels` |
| warmup rows excluded from the trainable dataset | `test_futures_labels` |
| `label_config_hash` stable for same config; changes on spec / feature / continuous-hash change | `test_futures_labels` |
| signal positions deterministic (build twice → equal) | `test_futures_signal_backtest` |
| transaction cost applied only when position changes | `test_futures_signal_backtest` |
| backtest PnL uses ratio-adjusted returns (raw for execution ref), not raw close returns | `test_futures_signal_backtest` |
| synthetic roll seam creates no fake PnL (flat-through-roll → ~0 PnL across the seam) | `test_futures_signal_backtest` |
| no network calls; synthetic data only | both |

### D.10 Commit plan

| Commit | Objective | Files | Tests | Acceptance |
|---|---|---|---|---|
| **1 — LabelSpec + forward-return labels** | `LabelSpec`, enums, `label_config_hash`, `build_label_matrix` for forward_return / direction / vol_adjusted (ratio-only; `execution_lag`) | `labels/__init__.py`, `labels/spec.py`, `labels/futures_labels.py`, `tests/test_futures_labels.py` | manual formula, NaN-tail, ratio enforcement, hash stability/sensitivity | labels match formulas; last `L+h` rows NaN; Panama rejected |
| **2 — Dataset assembly + provenance** | `build_supervised_dataset` joining features+labels, disjoint namespaces, `is_warmup`/`is_label_valid`, the three chained hashes; `trainable` view | `labels/dataset.py`, tests | namespace separation; warmup + NaN-label rows excluded; `label_config_hash` chains upstream | dataset schema correct; provenance chain verified |
| **3 — Baseline signal generator** | `momentum_baseline` (momentum + vol filter + roll avoidance), long/flat & long/short | `signals/__init__.py`, `signals/baseline.py`, `tests/test_futures_signal_backtest.py` | deterministic positions; warmup → flat; roll-buffer flattening | positions deterministic, leakage-free at signal stage |
| **4 — Futures vectorized backtest adapter** | `run_futures_backtest` reusing `run_backtest`; shift, ratio-return PnL, tick/multiplier/commission/slippage, roll cost | `futures_backtest/__init__.py`, `futures_backtest/futures_vectorized.py`, tests | `position.shift(1)` timing; cost only on change; PnL from adjusted not raw close; no fake roll PnL; metrics present | backtest correct, seam-safe, cost-aware |
| **5 — End-to-end synthetic test + docs** | raw → continuous → features → labels → dataset → baseline signal → backtest with full hash provenance; docs Appendix D as-built | tests, `docs/AI_QUANT_ARCHITECTURE.md` | e2e determinism + provenance; seam/leakage end to end | full pipeline reproducible by hash; all leakage guards green |

### D.11 Risks & mitigations

| Risk | Mitigation |
|---|---|
| Label leakage (label bleeding into features) | disjoint `feature__`/`label__` namespaces; assembler never passes labels into X; feature truncation-invariance unchanged by future rows |
| Same-bar execution leakage | `position = signal.shift(1)`; tested |
| Using adjusted prices for $ PnL vs raw for returns | returns/equity from ratio-adjusted (seam-safe); raw used *only* as execution reference (fill/tick/$) — both roles documented and tested |
| Roll-gap fake PnL | ratio-adjusted returns guarantee held-contract return at the seam; flat-through-roll test asserts ~0 PnL |
| Bad feature/label alignment | explicit `execution_lag`; label measured from `t+L`; alignment test |
| Accidental warmup inclusion | `trainable` = `not is_warmup and is_label_valid`; tested |
| Transaction-cost misapplication | cost only on `|Δposition|>0`; roll-day extra cost explicit; cost-on/off reported |
| Mixing strategy returns and model labels | labels are ML targets (from `t+L`); backtest returns are realized from positions — kept in separate modules and columns |

> Scope note: Phase 3 is labels + signal timing + backtest integration only —
> **no ML training/inference, no AutoML, no CFD/options, no frontend, no
> real-data download.** Ratio-adjusted prices drive return labels and strategy
> returns; raw held-contract prices are the execution/PnL reference; signals
> execute at `t+1` via `signal.shift(1)`.
