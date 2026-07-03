# Instruments Layer — Architecture Note

> **Status:** documents the *implemented* Phase 1 instrument spec layer
> (commits `f695a90`, `35c3255`). For the long-term plan this layer belongs to,
> see [AI_QUANT_ARCHITECTURE.md](AI_QUANT_ARCHITECTURE.md).
>
> **Scope guard:** this layer is futures-only. It contains no ML, CFD,
> options, or continuous-contract-stitching (`futures_continuous`) code —
> those live outside the instruments layer and are covered by other phases of
> the plan. The planning doc's `cfd.py` / `options_chain.py` are intentionally
> absent.

## 1. What the layer does

The instruments layer is the **single source of truth for contract metadata**.
It loads YAML spec files into validated, immutable Pydantic models so that
every downstream layer (data pipeline, backtester, reports) reads contract
economics from one place instead of hard-coding multipliers and tick sizes.

It is deliberately **pure**: no market-data access, no pandas, no caching.
Spec files are tiny, so the registry re-reads them on every lookup — obvious
behaviour, hermetic tests.

```
backend/app/instruments/
├── base.py       # generic InstrumentSpec + shared enums/errors (pure, no I/O)
├── futures.py    # FuturesSpec (calendar + rollover) + CME symbol/expiry math
├── registry.py   # YAML loading from configs/instruments/ (the only I/O)
└── __init__.py   # public API — import from `app.instruments`, not submodules
```

| Module | Responsibility | Key exports |
|---|---|---|
| `base.py` | Asset-class-agnostic spec model, validation invariants | `InstrumentSpec`, `AssetClass`, `SettlementType`, `AdjustmentMethod`, `InstrumentError`, `UnknownInstrumentError` |
| `futures.py` | Futures calendar/rollover config; contract-symbol parse/build; third-Friday expiry | `FuturesSpec`, `RolloverConfig`, `SessionConfig`, `CostConfig`, `MarginConfig`, `DataConfig`, `RollMethod`, `ExpiryRule`, `CME_MONTH_CODES`, `ContractCode`, `parse_contract_symbol()`, `third_friday()` |
| `registry.py` | Resolve root symbol → YAML file → validated spec | `get_instrument()`, `list_instruments()`, `load_spec()`, `default_instruments_dir()` |

Typical use:

```python
from app.instruments import get_instrument

es = get_instrument("ES")          # -> FuturesSpec (frozen)
es.tick_value                      # 12.5
es.build_contract_symbol("Z", 2024)  # "ESZ24"
es.expiry_for_symbol("ESZ24")      # datetime.date(2024, 12, 20)
```

## 2. Where instrument configs live

- Directory: **`configs/instruments/`** at the repo root (currently `es.yaml`,
  `nq.yaml`, `ym.yaml`, and `rty.yaml`).
- **Filename = lowercase root symbol** + `.yaml`: `get_instrument("ES")` reads
  `configs/instruments/es.yaml` and `get_instrument("NQ")` reads `nq.yaml`.
  `list_instruments()` is just the sorted uppercase stems of `*.yaml` files in
  that directory.
- The directory is resolved from `registry.py`'s own location
  (`default_instruments_dir()`), so lookups work regardless of the current
  working directory. Tests can pass an explicit `instruments_dir` to stay
  hermetic.

## 3. Required fields

`load_spec()` reads `asset_class` first and picks the model: all four current
`AssetClass` values (`equity_index_future`, `commodity_future`, `fx_future`,
`rates_future`) map to `FuturesSpec`. An unknown `asset_class` is handed to
the strict base model so Pydantic raises a precise `ValidationError`.

### Base identity & economics (`InstrumentSpec`, all specs)

| Field | Type / allowed values | Required | Constraint |
|---|---|---|---|
| `schema_version` | int | no (default `1`) | — |
| `root_symbol` | str | **yes** | non-empty, must be uppercase |
| `name` | str | **yes** | non-blank (whitespace stripped) |
| `asset_class` | `AssetClass` enum | **yes** | one of the four values above |
| `exchange` | str | **yes** | non-blank (whitespace stripped) |
| `underlying` | str | no (default `null`) | — |
| `settlement_type` | `cash` \| `physical` | **yes** | — |
| `currency` | str | **yes** | non-blank (whitespace stripped) |
| `contract_multiplier` | float | **yes** | > 0 |
| `tick_size` | float | **yes** | > 0 |
| `tick_value` | float | **yes** | > 0 **and** = `contract_multiplier × tick_size` |
| `price_quotation` | str | **yes** | non-blank (whitespace stripped) |
| `warnings` | list[str] | no (default `[]`) | surfaced in every report later |

### Futures additions (`FuturesSpec`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `contract_months` | list of CME month codes | **yes** | non-empty; each in `F G H J K M N Q U V X Z` |
| `expiry_rule` | `ExpiryRule` enum | **yes** | **only `third_friday` exists in V1** |
| `expiry_time_local` | str | no | informational only |
| `rollover` | `RolloverConfig` | **yes** | see below |
| `session` | `SessionConfig` | **yes** | see below |
| `costs` | `CostConfig` | **yes** | placeholders, flagged `is_placeholder` |
| `margin` | `MarginConfig` | **yes** | nullable placeholders (values go stale) |
| `data` | `DataConfig` | **yes** | consumed by the (future) data layer |

Nested config fields (all sub-models are also frozen + strict):

- `rollover`: `primary_rule` (**required**; `volume_open_interest` \|
  `days_before_expiry`), `confirmation_days` (default 1, ≥ 1),
  `lookback_window_days` (default 15, ≥ 1), `fallback_rule` (**required**),
  `fallback_days_before_expiry` (**required**, ≥ 0)
- `session`: `timezone` (**required**), `rth_equity_window_et`,
  `globex_window_ct`, `holiday_calendar` (all optional),
  `bar_frequency` (default `"1d"`)
- `costs`: `commission_per_contract_per_side` (**required**, ≥ 0),
  `slippage_ticks_per_side` (**required**, int ≥ 0),
  `is_placeholder` (default `true`), `note` (optional)
- `margin`: `initial_margin_usd`, `maintenance_margin_usd` (both optional,
  ≥ 0 when set), `is_placeholder` (default `true`), `note` (optional)
- `data`: `required_fields` (**required** list),
  `contract_symbol_format` (**required**, e.g. `"{root}{month_code}{yy}"`),
  `default_adjustment` (**required**; `ratio` \| `panama` \| `none`)

## 4. Validation rules

Validation happens at **load time** — a bad spec file fails loudly instead of
loading into a backtest.

1. **Strict schema** (`extra="forbid"` on every model): an unknown or typo'd
   key raises `ValidationError`.
2. **Immutable** (`frozen=True` on every model): assigning to any field after
   load raises `ValidationError`.
3. **`root_symbol`** must be non-empty and uppercase.
4. **Identity strings** (`name`, `exchange`, `currency`, `price_quotation`)
   must be non-blank; surrounding whitespace is stripped.
5. **Tick-value invariant**: `tick_value == contract_multiplier × tick_size`
   (checked with `math.isclose`, tolerance 1e-9). This is the core economic
   invariant — it catches transcription errors in the fields P&L depends on.
6. **Month codes**: `contract_months` must be non-empty and every entry must
   be a valid CME code.
7. **Numeric bounds**: `contract_multiplier`, `tick_size`, `tick_value` > 0;
   rollover/costs/margin bounds as listed in §3.
8. **Registry-level errors**: unknown root symbol →
   `UnknownInstrumentError` (message names the missing spec path and lists
   available roots); a YAML file that doesn't parse to a mapping →
   `InstrumentError`.

Calendar helpers in `futures.py` validate at call time:
`parse_contract_symbol("ESZ24")` rejects bad month codes / year digits
(2-digit years map to 2000–2099); `build_contract_symbol()` rejects months
outside the instrument's cycle; `expiry_for_symbol()` rejects symbols whose
root doesn't match the spec.

## 5. How tests verify the registry

Suite: `backend/tests/test_instruments_registry.py` (31 cases). Run it with
the backend venv from the repo root:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_instruments_registry.py
```

What it covers:

- **Loading & invariants** — `ES` loads as a `FuturesSpec` with the expected
  economics; `tick_value == multiplier × tick_size == 12.5`.
- **Validation failures** — wrong `tick_value`, missing required field, bad
  month code, unknown field, mutation of a frozen spec, and blank identity
  fields (parametrized over 4 fields × 2 blank variants) all raise
  `ValidationError`; whitespace stripping is asserted.
- **Symbol / expiry math** — `ESZ24` parses to (ES, Z, 2024); its expiry is
  the third Friday of Dec 2024 (2024-12-20); build→parse→build round-trips;
  off-cycle months are rejected.
- **Registry lookup** — `get_instrument("ES")` works and `"ES"` appears in
  `list_instruments()`; an unknown root raises `UnknownInstrumentError`
  naming the symbol.
- **Additional instruments (NQ, YM, RTY)** — each loads as a `FuturesSpec`
  with its documented economics (NQ: multiplier 20 / tick 0.25; YM:
  multiplier 5 / tick 1.0; RTY: multiplier 50 / tick 0.1 — all `tick_value`
  5.0); `NQZ25` / `YMZ25` / `RTYZ25` expiry is the third Friday of Dec 2025
  (2025-12-19).

A key pattern: failure tests mutate a **valid baseline dict loaded from the
real `es.yaml`** (`_es_dict()` helper), so they can never drift out of sync
with the actual config file. When adding an instrument, keep this pattern.

For a quick manual check outside pytest, a read-only smoke script loads every
registered spec and re-checks the tick-value invariant (exit 0 = all pass):
`backend\venv\Scripts\python.exe scripts\check_instruments.py`.

## 6. Checklist — adding a new futures instrument later

> Applies to CL, GC, etc. **Do not add these yet** — this is the procedure
> for when we do. (NQ, YM, and RTY were already added this way; use their
> yamls in `configs/instruments/` as further references.)

**First, check the expiry rule.** `ExpiryRule` currently supports only
`third_friday`, and `FuturesSpec.expiry_date()` raises `NotImplementedError`
for anything else. Consequences:

- **Equity index futures** (quarterly H/M/U/Z, third-Friday SOQ like ES):
  **config-only addition** — no code change needed. NQ, YM, and RTY were all
  added exactly this way.
- **CL / GC** (energy/metals): expiry is *not* a third Friday (CL expires
  ~3 business days before the 25th of the month preceding delivery; GC on the
  third-last business day of the delivery month). These need a **small code
  change first**: add an `ExpiryRule` variant + expiry math in `futures.py`,
  with tests, as its own tiny commit — *before* the YAML is added.

Then, per instrument (one tiny commit each):

1. Copy `configs/instruments/es.yaml` to `<root>.yaml` — **lowercase**
   filename (e.g. `nq.yaml`), since the registry resolves
   `get_instrument("NQ")` → `nq.yaml`.
2. Fill identity/economics from the **exchange's contract spec page** (do not
   guess): `root_symbol` (uppercase), `name`, `asset_class` (must be one of
   the four `AssetClass` values), `exchange`, `settlement_type`, `currency`,
   `contract_multiplier`, `tick_size`, `price_quotation`.
3. Set `tick_value = contract_multiplier × tick_size` **exactly** — the
   validator rejects anything else (e.g. NQ: 20 × 0.25 = 5.00).
4. Set `contract_months` to the instrument's actual cycle (equity index =
   quarterly `[H, M, U, Z]`; CL is monthly — all 12 codes).
5. Review `rollover` and `session` — the ES defaults are a reasonable start
   for CME equity index futures, but check timezone and session windows for
   other exchanges/asset classes.
6. Keep `costs` and `margin` as placeholders with `is_placeholder: true` and
   a `note`; never hard-code current margin values.
7. Write honest `warnings` — copy the ES ones that apply (back-adjustment,
   free-data limitations, daily-bars-only) and add instrument-specific ones
   (e.g. physical delivery for CL/GC).
8. Verify it loads: `get_instrument("<ROOT>")` returns a `FuturesSpec`, and
   `list_instruments()` includes the new root.
9. Add tests mirroring the ES suite (or parametrize the existing suite over
   `list_instruments()`), including at least one known-good expiry date.
10. Run the suite and report exact output:
    `backend\venv\Scripts\python.exe -m pytest backend/tests/test_instruments_registry.py`
