# ML Research Lifecycle v1

Phase 65 adds a local, snapshot-backed registry. ExperimentStore still owns its
filesystem runs; this registry does not serve models, retrain imports, resolve
arbitrary hashes, select models or implement Phase 66 replay. Hashes establish
content consistency, not historical authenticity or investment usefulness.

## Explicit Actions

Backend prefix `/ml-lifecycles`; browser proxy `/api/ml-lifecycles`:

| Method/path | Action |
|---|---|
| GET `/` | Bounded list; page 1..10000, size 1..50; completeness/integrity filters |
| GET `/{id}` | Snapshot and current linked integrity, without executing labs |
| POST `/` | Validated legacy snapshot registration against an existing dataset version |
| POST `/{id}/links` | Explicit adapter action; `adapter` is a fixed enum |
| GET `/{id}/links/{adapter}` | Read-only detail of the pinned diagnostic record |
| GET `/compare?a=...&b=...` | Neutral side-by-side metadata/metrics, no ranking |
| GET `/{id}/export` | Schema 1 JSON; refuses changed/invalidated content |
| POST `/demo` | Create/resume the one bounded synthetic lifecycle |

The browser workspace is reachable from Sidebar, Command Palette and
`/?view=mllifecycle`. Opening it only lists stored records. Its sole mutating
control is explicitly named **Create / resume synthetic demo**. Individual
adapter actions are API-only in v1. Linked detail is read-only; Open Lab uses
the canonical workspace, not an invented detail route.

No filesystem path is accepted by the API. Lists inspect at most 500 records;
larger registries fail clearly instead of returning misleading filtered totals.
There is no multi-user or untrusted public-hosting claim.

## Actual Demo Lineage

1. Fixed seed 650 produces 220 synthetic ES daily OHLCV bars. The existing
   continuous-futures builder creates a ratio-adjusted single-contract series.
2. Existing feature functions produce return(20) and moving-average gap(10,50),
   in that exact order. Existing labels produce direction(1) and forward return(1).
3. Trailing feature warmup is excluded. The last two source bars are retained
   as label-outcome price context, not selected based on their outcomes.
4. The final 32 eligible decisions form an outer chronological holdout. All
   splits are constructed first, with existing closed-interval purge and a
   two-day post-test embargo policy. Expanding causal training means the
   post-test embargo normally removes zero additional rows; purge counts remain
   explicit. Inner walk-forward uses 60 initial samples and 24-sample blocks.
5. Existing logistic estimators fit separately for each inner fold. Predictions
   carry their actual generating model hash. Existing sigmoid calibration fits
   only inner OOF probabilities and binary `direction_1 == +1` labels.
6. Final logistic fit uses only retained outer-training samples. Calibration
   and threshold 0.5 are frozen before held-out evaluation. Calibration-fit
   quality is not relabeled held-out quality. No profitable result is required.
7. Existing prediction-to-signal and futures backtest functions evaluate the
   held-out period. The target is unshifted; the backtest applies its lag once.
8. An owned Dataset Registry version binds the actual retained source table.
   Five new diagnostic records consume this lifecycle's actual samples and
   inputs, not unrelated lab demo seeders.

### Timing and Cost Limitations

The pre-existing label is `close[t+2] / close[t+1] - 1`. The existing backtest
uses `position[t] = target[t-1]` against `close[t] / close[t-1] - 1`.
These are **different evaluation intervals**, retained and named explicitly;
this phase does not change existing quant logic or covertly shift signals a
second time. Probability quality describes the declared label horizon, not a
claim that every trading-return period is that label. Feature availability,
decision time, label end time, training cutoff and execution policy stay separate.

Ten bps is an explicit synthetic evaluation assumption. Cost Diagnostics receives
gross returns and actual effective-position turnover. Already-net returns and
exact compounded drag remain metadata. Its fixed 10000 reference-notional,
linear fee calculation is not substituted for the original engine's compounded
equity path. Signal Decay uses the fixed label horizon/lag, one entity, and the
linked fee assumptions as context, not a new deduction from stored net returns.

## Adapter Contracts

| Adapter | Actual inputs and retained limit |
|---|---|
| Model Validation | Same sample IDs/closed intervals, same outer configuration; exact train/test/purge/embargo membership checked against the fitted final model. Inner fold memberships and audits remain in the lifecycle. |
| Meta-Labeling | Frozen calibrated held-out probabilities with explicit long primary side and zero outcome threshold. Destination `raw_probability` means adapter input, not the original uncalibrated score. Destination calibration method `none` prevents fitting on held-out outcomes. It does not claim those held-out values are OOF. |
| Feature Diagnostics | Actual ordered feature vectors, binary targets and outer split. The existing lab refits a **separate diagnostic model**; its permutation importance is not the original stored estimator's parameters. |
| Cost Diagnostics | Actual gross returns, effective-position changes and explicit 10 bps reference model; original net returns remain separate. |
| Signal Decay | Actual held-out calibrated score, exact entity/time, explicit availability, source prices, horizon 1 and entry lag 1; linked cost context. Single-entity descriptive diagnostics, not cross-sectional alpha. |

Records are pinned using recomputed material content, including child result
tables, not just advertised result hashes. Invalidation, deletion or mutation
makes the lifecycle changed/incomplete. Viewing/export never executes adapters.
Legacy imports lack the required feature and membership payload; all execution
adapters refuse them with an explicit reason instead of manufacturing evidence.

## Local Import

Use the repository virtual environment. These are operator commands, **not run
against user data during implementation**:

```powershell
backend/venv/Scripts/python.exe scripts/import_ml_lifecycle.py --source-root <owned-experiment-root> --run <64-lowercase-hex-run>
backend/venv/Scripts/python.exe scripts/import_ml_lifecycle.py --source-root <owned-experiment-root> --run <run> --write --destination-db <explicit-existing-registry.db> --dataset-version-id <existing-version>
```

Preview creates neither a database nor artifacts. It reports the semantic source
fingerprint and physical file hashes. Registration requires an existing Dataset
Registry version whose content fingerprint matches that **experiment snapshot**.
This is an archived artifact dataset binding, not proof of the missing historical
training dataset. The complete demo instead binds its actual continuous data
table, schema, column order and row count. No version is invented on legacy import.

Only schema-1 metadata, safe JSON parameters/metrics and exactly one CSV or
Parquet copy of each predictions/signal/backtest frame are supported. Keys are
full timezone-aware timestamp, root symbol and active contract. Naive timestamps
are refused rather than assigning an unknown historical timezone. Nulls are
explicit; numeric NaN/Infinity are refused. `signal_state` is a string and
`roll_flag` a boolean; other non-key frame columns are numeric in v1.

Parquet requires the existing optional pyarrow package. Metadata row/column and
uncompressed-size bounds are checked before scalar-column parsing; nested
Parquet columns are refused. There is no dependency installation or fallback
that silently selects an alternate file. Unusual legacy frame schemas remain
unsupported and are not rewritten in place.

## Manual Verification Gates

Production build, browser execution and independent review remain user-owned.
Do not run browser mutations against the ordinary backend. The optional
`scripts.ml_lifecycle_e2e:create_app` factory extends the existing disposable
Phase 64 harness with a guard on every lifecycle request. It verifies the
database path, file identity, owner token and actual SQLite connection.

For a later isolated user-run browser check, use a fresh process with the repo
root importable, set `E2E_STRATEGY_ENSEMBLE_TOKEN` to a fresh 64-hex secret, run
the factory without reload/workers on a separate port, point `BACKEND_URL` at
that port before building/starting the frontend, and set Playwright's configured
base URL to that frontend. Run `e2e/ml-lifecycle.spec.ts` only after both proxy
identity handshakes succeed. The token is test-only and never persisted in Git.
No service or actual browser was started by this implementation task.
