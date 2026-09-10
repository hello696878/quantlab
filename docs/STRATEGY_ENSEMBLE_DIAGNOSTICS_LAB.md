# Strategy Return Stream and Portfolio Ensemble Diagnostics Lab v1

Phase 64.0, `4.82.0-dev`. Implementation is available for manual verification
and independent review, not a release certification. See the
[implementation report](PHASE_64_IMPLEMENTATION.md) for actual verification.

## Scope

Phase 61 combines **signal values**. This lab compares **complete strategy
return streams**, then evaluates equal or explicitly supplied static weights.
It never chooses strategies, weights, thresholds, horizons or regimes. No
optimizer, external data download, order execution or investment recommendation.
A weighted strategy-return reference is not a fully funded executable portfolio.

## Existing source audit

| Source inspected | What exists | v1 decision |
|---|---|---|
| Single-strategy responses (`schemas.BacktestResponse`, `EquityPoint`) | Dated strategy/benchmark equity, metrics, parameters and trades | No complete periodic return, cost-basis and information-availability contract; no implicit equity-to-return conversion |
| Saved backtests (`schemas.SavedBacktestFull`, SQLite layer) | Persisted equity/trades/parameters/metrics and capital/cost settings | Old snapshots lack explicit interval and availability provenance; not advertised as linked streams |
| Strategy Comparison (`schemas.StrategyComparisonResponse`) | Per-strategy equity and metrics | Response is not a persisted, availability-qualified stream registry |
| Portfolio and walk-forward responses (`schemas.py`, research handlers) | Equity, window metrics, selected parameters and portfolio output | Not a uniform persisted strategy-return identity; no inferred stitching or cost convention |
| Cross-sectional scanner (`schemas.py`, scanner implementation) | Scanner research output, return/equity diagnostics | No qualified portable strategy-return identity spanning costs and publication timing |
| Local futures research (`futures_backtest/futures_vectorized.py`, `experiments/store.py`) | Gross and net returns, transaction costs, equity and experiment frame artifacts | Promising later adapter, but file-root, interval, availability and capital conventions need a separate contract; no arbitrary file reader added |
| Explicit supplied returns | Complete bounded observations and caller-declared identities | Supported v1 source; declarations are never called independently verified |

`source_type` is only `supplied`. An optional opaque `source_run_id` is a label,
not a promise to fetch another module's run. A dataset version may be explicitly
linked; a dataset label alone remains **unlinked**.

## Layers and limits

- `backend/app/strategy_ensemble/models.py`: strict Pydantic inputs, unknown
  fields rejected; 2-12 strategies, 2-2,000 observations each, 24,000 total,
  at most 12 explicit additional weight scenarios.
- `core.py`: pure alignment, correlations, tails, trailing drawdowns, common
  matrix diagnostics, fixed-weight returns and arithmetic contributions.
- `links.py`: read-only, content-pinned Dataset Lineage, Regime Diagnostics
  and Model Validation snapshots, rechecked before execution/comparison/baseline.
- `store.py` / `service.py`: bounded SQLite lifecycle, fingerprints, explicit
  baseline, JSON export and optional Experiment Registry record.
- `strategy_ensemble_routes.py`: FastAPI routes; frontend uses the existing
  Next proxy. No existing backtest engine or API contract was changed.
- `StrategyEnsemblePanel.tsx` / `StrategyEnsembleDetail.tsx`: real saved runs,
  explicit JSON inputs, accessible tables, wealth chart and honest null states.

## Identities and lifecycle

A definition records strategy/name, source/config SHA-256, dataset identity,
simple-arithmetic return convention, cost basis, frequency/currency, leverage,
exposure, configuration availability and observation window. Definitions and
observations are canonically sorted. Each definition gets a fingerprint.

Canonical SHA-256 partitions are `universe`, `observations`, `ensemble_policy`,
`analysis_policy`, `configuration` and `result`. Policy hashes include weights,
availability, scenarios and pinned links. Result hashes bind material results
to configuration. Local DB primary keys, run timestamps/runtime and storage
locators are excluded from these hashes; caller source identifiers are semantic
identities and remain included. Input reordering is immaterial; material
changes are tested. Non-finite numbers are rejected.

One additive `strategy_ensemble_runs` table stores bounded canonical JSON
snapshots, status, indexes, fingerprints and reference metadata. Initialization
is idempotent and uses the existing SQLite path override. No old tables are
dropped; results are replaced atomically. Creating a run does not execute it.
Executing verifies timing and pinned identities; invalid timing leaves a failed
record with no results or baseline. Invalidated records cannot execute.

A **baseline** is an explicit comparison reference, never a winner. A transaction
permits one baseline per universe/observation scope. Eligibility requires a
completed, unmodified result, declared timing, full common coverage, enough
observations, known active cost basis and leverage, reconciliation and acceptable
linked regime integrity. No performance criterion is used.

An optional Experiment Registry record uses module
`strategy_ensemble_diagnostics`. It contains counts, policies, integrity,
completeness and fingerprints, not recommendations. An atomic request flag
prevents duplicate attempts on rerun. Registry recording is best-effort; a
requested record with a null `experiment_id` is unavailable, not a successful
link, and is not automatically retried.

## Integrations

Stored regime assignments join exact **period starts**, not row positions. The
original assignment contents and integrity status are pinned; rare/unassigned
regimes have unavailable statistics. Group summaries show correlations, joint
loss, mean/per-period volatility, contributions and observations of the **full
trailing path's** drawdown, not a fabricated contiguous regime equity history.

One completed leakage-clean validation run and named valid split may be linked.
Train/test/purged/embargoed IDs are preserved. Every retained train/test sample
must map to an exact common period; period end equals evaluation time, and the
interval must encompass publication availability. Same configured weights in
both blocks; no fitting or selection. Each block starts wealth at 1. Full-sample
descriptive output stays separate. Caller-declared weight availability is not
proof that a human did not inspect held-out data.

Multi-window walk-forward is deferred because a single stored split is the
validated v1 contract. Factor/stress links are unavailable without corresponding
strategy-return identities. Bootstrap is deferred because the existing signal
bootstrap does not implement this period-return sampling contract. Allocation
cost/drift, geometric attribution linking and negative weights are not implemented.

## Further reading

- [Alignment and timing](STRATEGY_RETURN_STREAM_ALIGNMENT_POLICY.md)
- [Similarity, tails and drawdown](STRATEGY_SIMILARITY_DRAWDOWN_TAIL_POLICY.md)
- [Weights, contributions and costs](STRATEGY_ENSEMBLE_WEIGHT_CONTRIBUTION_COST_POLICY.md)
- [API and manual runbook](STRATEGY_ENSEMBLE_RUNBOOK.md)

All results are descriptive. Correlation does not establish diversification or
independence; contribution does not establish causality. No alpha, downside
protection, execution realism or investment suitability is certified.
