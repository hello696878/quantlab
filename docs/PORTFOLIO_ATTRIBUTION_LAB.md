# Portfolio Performance Attribution, Benchmark & Active Risk Lab (v1)

Phase 58.0. A local-first research lab that attributes **measured** portfolio
performance across assets, groups, periods, benchmark-relative decisions,
transaction costs, market regimes and stored drawdown episodes — using
**stored Phase 56 portfolio weights** and an **explicitly declared
benchmark**. Everything persists in local SQLite with deterministic SHA-256
fingerprints.

## Honest scope

- Every number is a **measurement under a stated convention**, not evidence
  about a manager. The lab does **not** prove alpha, prove manager skill,
  recommend a benchmark, recommend a portfolio, rank portfolios, guarantee
  future performance, produce GIPS-compliant reporting, perform tax
  accounting, do live portfolio accounting, rebalance, execute trades, or
  provide investment, trading or performance-reporting advice.
- A benchmark is **never selected automatically** and never falls back to an
  implicit equal-weight book — an equal-weight benchmark must be written out
  explicitly by the caller.
- Residuals are reported verbatim and **never redistributed** into the three
  Brinson effects.
- Linked records (Phase 56 weights, Phase 55 cost estimates, Phase 54 regime
  assignments, Phase 57 drawdown episodes, Model Validation runs, datasets)
  are consumed **read-only**. The lab's only cross-lab **write** is an
  optional new Experiment Registry record for an executed run.
- **Factor attribution is deferred in v1**: no validated exposure and
  factor-return matrices exist in this repository, factors are never inferred
  from asset names, and factor attribution is not advertised in the UI.

## Execution order (documented and fingerprinted)

1. validate the linked portfolio run and the explicit attribution policy
2. build the period/asset observation set from stored weights and returns
3. validate the explicit benchmark definition
4. per period: asset contributions → portfolio market return → costs → net
5. per period: benchmark return → active return → Brinson decomposition
6. multi-period linking (arithmetic reference and/or Carinó)
7. active-risk, concentration, regime and drawdown views
8. reconciliation status and result fingerprint

## Observation model

Period `t` spans `timestamps[t] → timestamps[t+1]`; its return is the stored
`returns[t]` and its weights are those known at `timestamps[t]`. Periods are
strictly increasing and non-overlapping by construction, asset/period
alignment is identical for every asset, and a period with no stored book is
**excluded and disclosed** — never back-filled. Bounds: ≤ 20 assets, ≤ 8
groups, ≤ 2000 periods.

## Integrity states

`verified_from_stored_rebalance` · `verified_causal_weights` ·
`supplied_descriptive` · `full_sample_descriptive` · `unknown` · `invalid`
(an end-of-period weight declaration, or a linked centered weight basis).
Baselines require verified provenance, a complete result **and**
reconciliation within the configured tolerance.

## Data model (SQLite)

| Table | Contents |
| --- | --- |
| `portfolio_attribution_runs` | run identity, method/variant/linking, policy, window, headline returns, integrity/completeness/reconciliation, fingerprints, links |
| `attribution_benchmarks` | the validated benchmark definition (one per run) |
| `attribution_period_results` | per period: market/cost/net/benchmark/active returns, Brinson effects, residual, cash weight, regime label |
| `attribution_asset_results` | per asset: average weight, arithmetic/positive/negative/absolute contribution, shares |
| `attribution_group_results` | per group totals (reconcile with the asset totals) |
| `attribution_brinson_results` | per group: allocation / selection / interaction, arithmetic and linked, window presence |
| `attribution_regime_results` | per stored regime label |
| `attribution_drawdown_results` | per stored Phase 57 episode |

## API

19 routes under `/portfolio-attribution/*`: `GET /summary`,
`GET|POST /runs`, `GET /runs/{id}`,
`POST /runs/{id}/execute|invalidate|mark-baseline`,
`GET /runs/{id}/benchmark|periods|assets|groups|brinson|active-risk|regimes|drawdowns`,
`GET /compare?a=&b=`, `GET /export`, `POST /demo-seed` (idempotent, 17
documented cases). Validation errors → 422, unknown ids → 404, conflicts →
409, unexpected execution failures → 500 with a sanitized message.

## Frontend

Sidebar view **Portfolio Attribution** (command palette registered): six
summary cards, status / integrity / method / linking filters, the runs table,
and a detail view with return reconciliation, the benchmark definition, an
asset-contribution waterfall, group contributions with asset drilldown,
Brinson effect bars and table with the residual stated, the linking block
(arithmetic vs geometric), cost attribution, active-risk diagnostics, the
active-return timeline (chart **and** table), regime and drawdown views, and
the stored policy. Comparison is neutral with comparability warnings.

## Related policies

- `PORTFOLIO_RETURN_CONTRIBUTION_POLICY.md` — weights, timing, contributions, reconciliation
- `BENCHMARK_AND_ACTIVE_RETURN_POLICY.md` — benchmark definitions and active return
- `BRINSON_ATTRIBUTION_POLICY.md` — variants, formulas, group returns, residuals
- `MULTI_PERIOD_ATTRIBUTION_LINKING_POLICY.md` — arithmetic, Carinó, TWR
- `PORTFOLIO_ATTRIBUTION_RUNBOOK.md` — operations, demo cases, verification
