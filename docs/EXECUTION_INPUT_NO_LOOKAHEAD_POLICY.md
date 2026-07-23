# Execution-Input No-Look-Ahead Policy (v1)

Information-timing rules for every execution input the Cost Diagnostics
Lab consumes — spread, volatility, ADV, volume, realized slippage
(`backend/app/cost_diagnostics/liquidity.py`). A value used to estimate
the cost of an execution at timestamp *t* must have been observable at
*t*.

## 1. Trailing derivation (the verified path)

When a run configures `trailing_volume` (ADV) or `trailing_returns`
(volatility) sources with a run-level liquidity series:

- the trailing statistic at series index *j* uses
  `values[j − lag − lookback + 1 … j − lag]` **only**, with `lag ≥ 1`
  enforced — the value effective for an execution never includes the
  execution period itself;
- lookback ∈ [1, 250] (≥ 2 for volatility — a sample std with ddof=1 is
  undefined at n = 1), lag ∈ [1, 30];
- **centered windows and negative lags are rejected outright (422)**;
- insufficient history yields None (honestly unavailable, never
  zero-filled);
- series timestamps are parsed and must be strictly increasing **in
  time** with consistent timezone-awareness — a lexicographic string
  comparison could accept chronologically disordered mixed-offset
  timestamps and silently defeat the trailing guarantee;
- observations map to the series by exact timestamp match — no
  interpolation, no nearest-neighbour fallback;
- adversarial future-data mutation tests prove the property: changing
  every series value after an observation's permitted window changes
  nothing about that observation's derived inputs or costs.

A configured trailing derivation **never silently falls back** to
per-observation supplied inputs: an unresolved trailing value leaves the
component unavailable, so unclassified provenance can never hide behind a
verified label, and `verified_causal_input` is claimed only when at least
one value actually derived.

## 2. Supplied inputs and provenance classification

Per-observation inputs declare a `basis` (plus optional `lag`,
`lookback`, `window`); nothing is silently upgraded:

| Declared basis | Integrity state |
| --- | --- |
| `supplied_realized` (realized slippage only) | `supplied_realized` |
| `trailing` with lag ≥ 1 and valid lookback | `verified_causal_input` |
| `trailing` with lag ≤ 0, missing lookback, or volatility lookback < 2 | `invalid` |
| any input with `window: "centered"` or negative lag | `invalid` |
| `dataset_lineage` with a linked dataset version | `verified_from_dataset_lineage` |
| `dataset_lineage` without a linked version | `declared` + warning |
| `declared` | `declared` |
| `full_sample` | `full_sample_descriptive` + "descriptive only, never leakage-safe" warning |
| missing / unknown | `unknown` |

Trust order (least → most): `invalid < unknown < full_sample_descriptive
< declared < verified_from_dataset_lineage < verified_causal_input <
supplied_realized`. Run integrity = the least-trusted state across
configured components (fixed configured assumptions contribute
`declared`); a run with no execution inputs at all is `declared`.

## 3. Consequences

- `invalid` or `unknown` integrity blocks baselines and is prominently
  warned; costs still compute numerically so the damage is inspectable,
  but the run is flagged untrustworthy as causal evidence.
- Full-sample average volume/volatility is always descriptive — never
  verified, never leakage-safe.
- Training-only liquidity estimates via a linked validation run are not
  implemented in v1 (the `dataset_lineage` and trailing paths cover the
  verified states); this is listed as a limitation.
- Future changes to a liquidity series never alter earlier causal cost
  inputs (mutation-tested at both the engine and service level).
