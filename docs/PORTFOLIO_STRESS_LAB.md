# Portfolio Stress Testing, Scenario Shock & Drawdown Attribution Lab (v1)

Phase 57.0. A local-first research lab that applies **explicit deterministic
stress scenarios** to **stored Phase 56 portfolio weights** and attributes the
measured losses, risk-estimate changes, liquidity/cost effects and historical
drawdowns. Everything persists in local SQLite with deterministic SHA-256
fingerprints. Configuration identity includes the selected weight/covariance
decision timestamps, pinned linked identities, and causal observation slices;
result and sensitivity fingerprints cover their complete material outputs.

## Honest scope

- A scenario is an **explicit assumption**, never a prediction. No scenario is
  a worst case; a measured loss is not a guaranteed loss.
- The lab never hedges, rebalances, trades, executes, or recommends an action.
  Post-shock drifted weights are pure arithmetic — no automatic rebalancing.
- Results are research diagnostics under stated assumptions — never proof of
  safety or robustness, not regulatory stress testing, not capital-adequacy
  analysis, and not investment, trading, or risk-management advice.
- Linked records (Phase 56 weights/covariance, Phase 55 cost models, Phase 54
  regime runs, datasets) are consumed **read-only**; no linked fingerprint
  ever changes. Their material identities are pinned into the stress-run
  configuration and checked again on execution; a changed/missing linked
  identity is refused, while an invalidated dataset remains visible with an
  audit warning and is ineligible for baseline promotion. The lab's only
  cross-lab **write** is an optional new
  Experiment Registry record for an executed run (at most one per run,
  reused on re-execution) — it creates a record, it never modifies one.
  A linked Phase 54 regime run is provenance only in v1: no stored regime
  assignment is consumed and nothing is conditioned on regimes.
- **Factor shocks are deferred in v1**: no estimated, run-linked
  factor-exposure system exists in this repository, and exposures are never
  inferred from asset names. `linked_to_stored_regime` integrity is reserved
  and unused in v1.

## Execution order (documented and fingerprinted)

1. validate the baseline portfolio and linked inputs
2. apply price-return shocks (direct P&L attribution, drifted weights)
3. apply volatility shocks
4. apply correlation shocks
5. rebuild and validate the stressed covariance (explicit repair only)
6. recalculate risk (baseline vs stressed MCR/CCR/PCR)
7. apply liquidity and cost stress (stressed cost-model copy, new fingerprint)
8. final scenario reconciliation (P&L and risk effects kept strictly separate)

Plus trailing-only drawdown analysis of the recomputed portfolio-return series
and per-asset attribution of the deepest episode. A verified historical run
uses only observations strictly before its selected decision timestamp;
descriptive/hypothetical runs use the full stored realized series and say so.
No timestamp-aligned realized cost path is stored, so drawdown cost attribution
is explicitly unavailable.

## Data model (SQLite)

| Table | Contents |
| --- | --- |
| `portfolio_stress_runs` | run identity, scenario type, integrity/completeness, headline results, reconciliation/risk/cost/drawdown JSON blocks, fingerprints, links |
| `stress_scenario_definitions` | the validated scenario definition stored verbatim (one per run) |
| `stress_asset_results` | per asset: weight, resolved shock + source, contribution, abs share, drifted weight |
| `stress_risk_results` | per asset: baseline vs stressed MCR/CCR/PCR, ΔPCR, rank change |
| `stress_constraint_results` | breaches per book (`original` / `drifted`) |
| `drawdown_episodes` | peak/trough/recovery timestamps, depth, durations, recovered/unrecovered |
| `drawdown_attribution_results` | per-asset contribution over the deepest episode |
| `stress_sensitivity_results` | bounded one-at-a-time probes (base row + ≤39 probes) |

## Integrity states

`verified_historical_window` (stored observations; ex-ante claims must end
strictly before the portfolio decision cutoff — otherwise **invalid**),
`verified_deterministic_rule`, `supplied_descriptive`,
`full_sample_descriptive`, `unknown`, `invalid`. Baselines require a verified
integrity state, a complete result, and — where risk stress is configured —
an available stressed covariance.

Integrity is classified and stored at create time, so a pending run already
reports its true state. Off-timeline and reversed historical windows are
rejected at create (422) because their replay is arithmetically undefined;
a future-looking ex-ante claim is still creatable and executes, but is
labelled `invalid` and can never become a baseline.

## Frontend

Sidebar view **Portfolio Stress Lab** (command palette registered): six
live summary cards, status / integrity / scenario-type filters, the runs
table with neutral pills, and a detail view with the reconciliation block,
a signed contribution waterfall, the per-asset table (weight, shock,
resolved source, contribution, |share|, drifted weight), baseline-vs-stressed
MCR/CCR/PCR values, requested/effective correlation matrices with explicit
unitless labels, constraint breach or clean-state panels, the cost panel with
participation, the causally labelled drawdown chart + episode table +
deepest-episode attribution, the
sensitivity table, and the scenario definition stored verbatim with its
execution order. Comparison is neutral with comparability warnings.

## API

17 routes under `/portfolio-stress/*`: `GET /summary`, `GET|POST /runs`,
`GET /runs/{id}`,
`POST /runs/{id}/execute|invalidate|mark-baseline`, `GET /runs/{id}/scenario|
asset-results|risk-results|constraint-results|episodes|attribution|sensitivity`,
`GET /compare?a=&b=`, `GET /export`, `POST /demo-seed` (idempotent, 16
documented cases). Validation errors → 422, unknown ids → 404, conflicts →
409, unexpected execution failures → 500 with a sanitized message.

## Downstream: Portfolio Attribution Lab (Phase 58.0)

The Portfolio Attribution Lab
([`PORTFOLIO_ATTRIBUTION_LAB.md`](PORTFOLIO_ATTRIBUTION_LAB.md)) may link a
completed stress run of the **same** portfolio to attribute performance over
this lab's stored drawdown episodes: the peak→trough interval is reused
exactly, and this lab's episodes, results and fingerprints are read-only.
Attribution describes what was measured over that interval — it never
explains why the drawdown occurred.

## Related policies

- `STRESS_SCENARIO_DEFINITION_POLICY.md` — types, units, precedence, integrity
- `PORTFOLIO_STRESS_ATTRIBUTION_POLICY.md` — contributions, reconciliation, drifted books, cost stress
- `STRESS_COVARIANCE_AND_CORRELATION_POLICY.md` — volatility/correlation stress, PSD, repair
- `DRAWDOWN_AND_EPISODE_ATTRIBUTION_POLICY.md` — drawdown conventions and episode attribution
- `PORTFOLIO_STRESS_RUNBOOK.md` — operations, demo cases, verification

## Downstream: Factor Diagnostics Lab (Phase 59.0)

The Factor Diagnostics Lab can link a stored stress run to report an
exposure-implied factor contribution: `measured exposure × SUPPLIED factor
shock`, in each factor's transformed unit. Factor shocks are **never
inferred** from this lab's asset, group or global shocks — the caller must
supply them explicitly — the two shock families stay distinct, this lab's
records are read-only and fingerprint-pinned, the hypothetical scenario's
residual component is reported as undefined, and no hedge or reallocation
follows from the number.
