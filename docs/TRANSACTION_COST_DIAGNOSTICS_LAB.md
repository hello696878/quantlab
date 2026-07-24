# Transaction Cost, Slippage, Market Impact & Capacity Diagnostics Lab (v1)

Phase 55.0 adds a local-first research diagnostics lab that applies
explicitly configured execution-cost assumptions to supplied historical
strategy, candidate, validation, or experiment observations. It answers,
for a given run: what gross result was supplied, which cost assumptions
were applied, which components were supplied / derived / estimated /
unavailable, what the commission / spread / slippage / market-impact
estimates are, what the net result is after each component, how sensitive
the result is to the assumptions, where break-even sits, how scaling
notional changes participation and impact, which observations exceed the
configured participation threshold, how costs differ across stored market
regimes, which results depend on incomplete metadata, and whether the
result reproduces from deterministic fingerprints.

**The lab is NOT** an order execution system, broker simulator, or live
trading engine. It does not predict real fills, guarantee market capacity,
execute orders, recommend trade sizes or brokers, prove profitability,
certify execution quality, or provide investment, execution, allocation,
tax, legal, compliance, or risk-management advice. Every output is an
estimate under configured assumptions.

Related policies:
- [EXECUTION_COST_MODEL_POLICY.md](EXECUTION_COST_MODEL_POLICY.md) — units,
  commission / spread / slippage semantics, reconciliation.
- [MARKET_IMPACT_AND_CAPACITY_POLICY.md](MARKET_IMPACT_AND_CAPACITY_POLICY.md)
  — the square-root impact approximation, participation, capacity scaling.
- [EXECUTION_INPUT_NO_LOOKAHEAD_POLICY.md](EXECUTION_INPUT_NO_LOOKAHEAD_POLICY.md)
  — information timing for spread / volatility / ADV / volume inputs.
- [COST_DIAGNOSTICS_RUNBOOK.md](COST_DIAGNOSTICS_RUNBOOK.md) — operations.

## 1. Observation models

One run holds exactly one observation type:

**Trade-level** (`observation_type: "trade"`, monetary values primary):
round-trip trades with `trade_id`, `candidate_id`, `side` (long/short),
entry/exit timestamps (ISO-8601, tz-consistent, exit never before entry),
positive entry/exit prices and quantity, an explicit `contract_multiplier`
(default 1.0, always echoed back — never hidden), one shared `currency`
(mixed currencies are rejected; there is no silent FX conversion), optional
supplied `gross_pnl`, optional per-observation `cost_inputs`, and bounded
scalar metadata. Gross PnL is taken as supplied when present (source
`supplied`; a material disagreement with the price-derived value is
warned), otherwise derived by the documented transformation
`direction × (exit − entry) × quantity × multiplier`
(source `derived_from_prices`). Quantity is never inferred from PnL.
Derived notionals: `entry_notional = entry_price × quantity × multiplier`,
`traded_notional = entry_notional + exit_notional`.

**Period-level** (`observation_type: "period"`, return fractions primary):
`observation_id`, `candidate_id`, `timestamp`, `gross_return` (finite),
optional `turnover` (fraction of capital traded that period, ≥ 0),
optional `traded_notional` (currency, used for notional participation),
optional `cost_inputs`, metadata. Period observations carry no capital
base, so monetary cost models are rejected for period runs and no monetary
view is fabricated.

Bounds: 2–2000 observations, ≤ 16 candidates, unique ids, deterministic
chronological ordering on the parsed timestamps (a lexicographic string
sort would misorder heterogeneous UTC offsets), finite values only, no
arbitrary expressions.

## 2. Cost model (summary)

Four non-overlapping components — commission, spread cost, slippage,
market impact — each configured explicitly with declared units (see the
cost-model policy for exact semantics). For every observation the lab
records each component as available (with its amount), unavailable (with
an explicit reason), or not configured. **Total cost equals the exact sum
of available components and net equals gross minus total cost.** A missing
input is never treated as zero: the observation's completeness drops to
`partial` (its net excludes the unavailable components and is disclosed as
a cost under-estimate) or `gross_only` (no configured component could be
computed), and run-level counts stay visible.

Completeness states: `complete` / `partial` / `gross_only` / `invalid`.

## 3. Integrity states

Execution inputs (spread, volatility, ADV, volume, realized slippage)
carry provenance. Trust order (least → most trusted):

`invalid < unknown < full_sample_descriptive < declared <
verified_from_dataset_lineage < verified_causal_input < supplied_realized`

Run integrity is the least-trusted state across configured components:
fixed configured assumptions are `declared`; components consuming supplied
per-observation inputs inherit those inputs' classified provenance;
trailing-derived inputs are `verified_causal_input`; a centered window or
non-positive lag makes the run `invalid`; full-sample inputs stay
descriptive and are never leakage-safe. A configured trailing derivation
never silently falls back to supplied per-observation inputs — an
unresolved trailing value is honestly unavailable, so unclassified
provenance can never hide behind a verified label.

## 4. Aggregates, break-even, sensitivity, capacity

- **Aggregates**: totals, per-component totals (None — never 0.0 — when
  nothing was computable), cost as a fraction of |gross| and of traded
  notional (period runs use turnover as the dimensionally correct
  per-notional basis; ratios are withheld when the denominator does not
  cover every observation), gross/net mean/median/std (ddof=1),
  per-observation Sharpe-like values (never annualized), positive rates,
  turnover, the count of gross-positive observations becoming
  net-nonpositive (neutral wording — never "failed trades"), and
  unavailable / partial counts.
- **Break-even**: aggregate break-even in bps of traded notional, mean
  break-even per observation, the maximum uniform cost multiplier before
  the measured aggregate net reaches zero, per-component break-even
  multipliers, and the break-even impact coefficient (the square-root
  model is linear in its coefficient). Unavailable when gross is
  non-positive; never negative, never Infinity; not claimed achievable in
  markets; no maximum acceptable broker cost is recommended. Exact
  formulas: `backend/app/cost_diagnostics/aggregates.py` docstring.
- **Sensitivity**: a bounded deterministic grid of component multipliers
  (≤ 5 values per component, ≤ 60 scenarios, deduplicated, deterministic
  order, base scenario always present and marked). Multipliers scale
  computed base amounts; unavailable components stay unavailable; supplied
  realized slippage is a historical fact and is never scaled. No scenario
  is selected or called optimal. Each scenario has its own fingerprint.
- **Capacity**: bounded notional scale factors (defaults 0.25/0.5/1/2/5×,
  ≤ 8 values, 1× always present) scale observation size — never
  historical prices. Fixed fees stay fixed, per-unit/per-contract fees
  scale with quantity, bps costs scale with notional, and square-root
  impact scales superlinearly (cost ∝ scale^1.5) through participation.
  An optional integer-contract policy floors scaled quantities and reports
  exclusions (whole-number base quantities are required when enabled).
  Results are labelled "estimated under configured assumptions" — no
  assumption that fills remain available, no executable-capacity claim,
  no maximum-capacity recommendation.
- **Participation**: per observation, quantity or notional participation
  against ADV/volume with a configured threshold (default 0.25, bounds
  0.001–10); statuses `within_configured_threshold` /
  `above_configured_threshold` / `unavailable` / `invalid`; participation
  above 100% stays visible as a warning — nothing is auto-rejected or
  resized.

## 5. Delay / adverse-price stress — omitted in v1

Stored observations carry no per-bar price paths, so a delayed fill price
cannot be derived without fabricating prices. The feature is therefore
honestly omitted; the decision is recorded in every run's configuration
(`delay_stress.supported = false` with the rationale).

## 6. Multiple comparisons

v1 reports descriptive cost estimates only: no hypothesis tests are
performed and no p-values are produced (recorded in every run's
configuration). The Phase 53 corrections remain the sanctioned path for
callers with genuinely tested p-values.

## 7. Integrations (all read-only)

- **Experiment Registry** — an idempotent neutral record (module
  `transaction_cost_diagnostics`) with cost models, counts, completeness,
  gross/net summary, participation warnings, and fingerprints. No
  recommendations are stored.
- **Dataset Lineage** — linked dataset version identity, fingerprints,
  provenance/quality states, and an invalidation warning; inputs claiming
  `dataset_lineage` provenance without a linked version degrade to
  `declared` with a warning.
- **Model Validation** — linked run's method, leakage status and
  fingerprints displayed; split memberships are never changed.
- **Regime Diagnostics** — stored effective assignments of one named
  definition are joined by exact timestamp (never recomputed); per-regime
  gross/cost/net/component/participation tables with rare-regime warnings;
  no regime is called cheapest, most profitable, or recommended.
- **Overfitting Diagnostics** — linked run's PBO/PSR/DSR displayed
  read-only; for ≥ 2 candidates the run records both a gross and a
  cost-adjusted (net) candidate-matrix fingerprint. A descriptive PBO
  comparison for net returns requires a new explicitly executed Phase 53
  analysis — stored PBO values are never reused or rewritten, and costs
  are never claimed to eliminate or prove overfitting.
- **Feature Diagnostics / Meta-Labeling** — optional context links only.
- **Portfolio Diagnostics** (Phase 56.0,
  [`PORTFOLIO_DIAGNOSTICS_LAB.md`](PORTFOLIO_DIAGNOSTICS_LAB.md)) — a
  portfolio run may link a run from this lab read-only to estimate
  descriptive rebalance costs from its STORED cost model (only
  turnover-proportional components apply; trade-level fields are
  honestly unavailable there); this lab's rows and fingerprints are
  never mutated, and generated weights are never submitted here.

## 8. Fingerprints

Deterministic SHA-256 over canonical JSON (floats quantized to 12 decimal
places; NaN/Infinity rejected): observation-universe, cost-model,
configuration, result, and per-scenario fingerprints, composed exactly as
documented in `backend/app/cost_diagnostics/fingerprints.py`. Database
ids, created timestamps, runtime durations and absolute paths are never
hashed.

## 9. Persistence

Five SQLite tables (idempotent `CREATE TABLE IF NOT EXISTS`, no drops, no
startup demo insertion): `cost_diagnostic_runs` (explicit summary columns
+ bounded JSON for configuration/observations/aggregates/break-even/
regimes/warnings), `cost_models` (one row per run), and explicit-row
`cost_observation_results`, `cost_sensitivity_results`,
`cost_capacity_results`. Child rows are replaced deterministically on
re-execution; baseline replacement is transactional; 18 indexes support
the API filters. Failed executions are recorded as `failed` with an error
message — never left `running`.

## 10. Baselines

A completed run may become the comparison baseline for its scope
(`dataset version | universe fp | cost-model fp | base scale | window`).
Requirements: completed, result fingerprint present, integrity in
{supplied_realized, verified_causal_input, verified_from_dataset_lineage,
declared}, completeness `complete`, not invalidated. Same-scope
replacement is transactional, unrelated baselines are preserved, repeated
marking is idempotent, and no run is ever auto-selected by highest net or
lowest cost. Baseline means comparison reference only.

## 11. API

`/cost-diagnostics`: `GET /summary`, `GET|POST /runs`, `GET /runs/{id}`,
`POST /runs/{id}/execute|invalidate|mark-baseline`,
`GET /runs/{id}/observations|sensitivity|capacity|regimes`,
`GET /compare?a=&b=`, `GET /export`, `POST /demo-seed`. Bounded
pagination, stable sorting, safe filters, parameterized SQL, 404/409/422
error mapping, no raw stack traces, no file access, no provider calls, no
order submission.

## 12. Frontend

Sidebar view **Cost & Capacity** (command palette: "Open Cost &
Capacity"): local-first badge, explicit-assumptions explanation and
no-execution disclaimer, refresh / demo / export actions, six live summary
cards, dark filter controls with accessible labels, and a runs table with
completeness/integrity pills and truncated fingerprints. The detail view
shows fingerprints, baseline action, warnings, linked-record cards, a
gross-to-net waterfall with its table, cost composition with shares,
aggregate diagnostics with explicit units, break-even, per-observation
reconciliation (paginated, missing components listed by name), the
sensitivity grid with the base scenario marked neutrally, the capacity
table plus an SVG participation-by-scale curve (values printed — never
color-only), and the regime-conditioned cost table. Responsive at 1440 /
1024 / 768 with internal horizontal scrolling.

## 13. Demo, export, testing

- Deterministic idempotent demo (`POST /demo-seed`, seeds 55xxx,
  `demo:cd:*` keys) with six runs covering the twelve documented cases;
  loading twice creates nothing.
- Export (`cost_diagnostics_export_v1`) contains runs, cost models,
  observation results, sensitivity and capacity rows and fingerprints —
  no absolute paths, credentials, or broker data; NaN/Infinity rejected.
- 43 backend tests (`backend/tests/test_cost_diagnostics.py`) including
  adversarial future-data mutation tests, plus 18 Playwright tests
  (`frontend/e2e/cost-diagnostics.spec.ts`). An independent adversarial
  verification workflow (5 reviewers, 197 hand-computed checks) audited
  the engine before release; every finding was fixed with a regression
  test.

## 14. Limitations

Costs are estimates under configured assumptions, not predictions of real
fills. The square-root impact model is a bounded research approximation.
Capacity results assume historical per-unit results scale with size and
say nothing about fill availability. Period-level runs support only
notional-proportional cost models. Delay stress is omitted in v1. Break-
even values describe the measured sample only. Upstream causality of
supplied observation PnL is the caller's responsibility.
