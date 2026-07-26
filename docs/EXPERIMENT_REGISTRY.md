# Research Experiment Registry & Reproducibility Dashboard (Phase 48.0)

A **local-first, single-user** registry that records reproducibility metadata for
QuantLab research runs and presents them in an interactive frontend dashboard.

> **Honest scope.** The fingerprints and the reproducibility assessment are
> **integrity and reproducibility aids only**. They are *not* a regulatory audit
> trail, *not* tamper-proof security, and *not* proof of scientific
> reproducibility or model correctness. Nothing here is investment, trading, or
> risk-management advice.

This registry is intentionally distinct from `backend/app/experiments/` — that
package is a file-based store for ML training runs keyed by `train_run_hash`.
The registry here is a broad SQLite catalogue for *any* module's deterministic
research run.

---

## 1. Purpose

The registry answers ten questions about a research run:

1. What experiment was run? (`name`, `description`)
2. Which module and configuration? (`module`, `experiment_type`, `parameters`)
3. Which dataset/fixture? (`dataset_name`, `dataset_version`, `dataset_fingerprint`)
4. Which parameters and seed? (`parameters`, `random_seed`)
5. Which Git commit produced it? (`git_commit`, `app_version`)
6. What metrics resulted? (`metrics`, `result_fingerprint`)
7. Did it succeed, fail, or become invalid? (`status`)
8. Can it be reproduced? (`reproducibility_status` + the assessment endpoint)
9. How do two experiments differ? (the comparison endpoint)
10. Which saved result is the current baseline? (`is_baseline`)

## 2. Data model

One row per experiment in the `experiment_registry` table. Structured fields that
genuinely vary are stored as JSON text (`parameters`, `metrics`, `tags`,
`provenance`); everything used for filtering, sorting, relationships, status,
fingerprints, baseline selection, and timestamps is an explicit column.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `created_at`, `updated_at` | TEXT | ISO-8601 UTC (`…Z`) |
| `name`, `description` | TEXT | bounded |
| `module`, `experiment_type` | TEXT | filter/sort |
| `status` | TEXT | see lifecycle |
| `reproducibility_status` | TEXT | see statuses |
| `started_at`, `completed_at` | TEXT | optional ISO-8601 |
| `duration_ms` | INTEGER | optional |
| `git_commit`, `app_version` | TEXT | provenance (cached, best-effort) |
| `dataset_name`, `dataset_version`, `dataset_fingerprint` | TEXT | dataset identity |
| `configuration_fingerprint` | TEXT NOT NULL | SHA-256, server-computed |
| `result_fingerprint` | TEXT | SHA-256, server-computed when metrics exist |
| `random_seed` | INTEGER | optional |
| `parameters_json`, `metrics_json`, `tags_json`, `provenance_json` | TEXT | JSON |
| `notes` | TEXT | free text |
| `parent_experiment_id` | INTEGER | self-reference (reference run) |
| `is_baseline` | INTEGER | 0/1 |
| `error_message` | TEXT | populated on failure |
| `demo_key` | TEXT UNIQUE | non-null only for demo records (idempotent seeding) |

Indexes cover `created_at`, `module`, `experiment_type`, `status`,
`reproducibility_status`, `is_baseline`, `configuration_fingerprint`,
`dataset_fingerprint`, `parent_experiment_id`, and a UNIQUE index on `demo_key`.

## 3. Status lifecycle

```
pending ─┐
running ─┼─▶ completed ──▶ invalidated
         ├─▶ failed ─────▶ invalidated
         └───────────────▶ invalidated
```

- `complete` and `fail` are allowed only from `pending`/`running` (else HTTP 409).
- `invalidate` is allowed from any non-invalidated status and clears `is_baseline`.
- A record may also be *created* directly in any status (e.g. a completed run
  recorded after the fact). Creating a `failed` record requires an
  `error_message`.

## 4. Reproducibility statuses

`unknown` · `reproducible` · `partially_reproducible` · `not_reproducible`.
See [`EXPERIMENT_REPRODUCIBILITY_POLICY.md`](EXPERIMENT_REPRODUCIBILITY_POLICY.md)
for the exact rules. The assessment compares a candidate against a **reference**
(its `parent_experiment_id`, or the baseline in the same scope) and persists the
derived status so list/detail badges stay in sync.

## 5. Fingerprint policy

Three deterministic SHA-256 fingerprints, all over **canonical JSON** (UTF-8,
recursively sorted keys, compact separators, whole-number floats normalized to
ints, **NaN/Infinity rejected**, unsupported types rejected):

- **Configuration fingerprint** — module, experiment type, parameters, random
  seed, and dataset identity. Never includes timestamps, database ids, notes, or
  tags, so the same inputs fingerprint identically regardless of when they ran or
  field order.
- **Result fingerprint** — metrics + optional result metadata, bound to the
  configuration fingerprint.
- **Dataset fingerprint** — a caller-supplied verified SHA-256, or one derived
  from a deterministic fixture's *identity metadata* (never by hashing
  multi-gigabyte data during a request), or `null`.

Fingerprints identify *inputs* or *outputs*. They are integrity aids, not proof
of validity and not a security control.

## 6. Baseline policy

At most **one active baseline per scope**, where a scope is
`(module, experiment_type, dataset identity)` and dataset identity is
`COALESCE(dataset_fingerprint, dataset_name, '')`. Marking a new baseline
transactionally unmarks any other baseline in the same scope; baselines in other
scopes are untouched. Only a `completed` experiment may become a baseline.

## 7. Persistence and migration

Reuses the project's existing stdlib-`sqlite3` layer (`app/db.py`). The table and
indexes are created with `CREATE TABLE/INDEX IF NOT EXISTS` inside `init_db()`,
which runs once at startup and is fully idempotent. This is **non-destructive**:
no existing table is dropped, no data is deleted, and a pre-existing database
(e.g. one that only had `saved_reports`) upgrades cleanly by gaining the new
table. Tests redirect the database path via `app.db._db_path_override` to a
temporary file — the real `backend/data/quantlab.db` is never touched by tests.

## 8. API

All routes are under `/experiment-registry` (proxied by the frontend at
`/api/experiment-registry/*`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/summary` | counts + filter facets |
| GET | `/experiments` | list (filtered, sorted, paginated) |
| POST | `/experiments` | record an experiment (201) |
| GET | `/experiments/{id}` | full record |
| PATCH | `/experiments/{id}` | update name/description/notes/tags |
| DELETE | `/experiments/{id}` | delete one record |
| POST | `/experiments/{id}/complete` | complete a run |
| POST | `/experiments/{id}/fail` | fail a run |
| POST | `/experiments/{id}/mark-baseline` | make the sole baseline in scope |
| POST | `/experiments/{id}/invalidate` | invalidate a run |
| GET | `/experiments/{id}/reproducibility` | assess vs the reference |
| GET | `/compare?a=&b=` | neutral two-experiment diff |
| GET | `/export` | JSON export (respects filters) |
| POST | `/demo-seed` | load deterministic demo records (idempotent) |

List filters: `module`, `experiment_type`, `status`, `reproducibility_status`,
`baseline`, `tag`, `query` (name/description), `created_from`, `created_to`,
`configuration_fingerprint`, `dataset_fingerprint`. Sorting is whitelisted;
page size is bounded (default 25, max 100); the response carries `total`,
`page`, `page_size`, `total_pages`.

Errors: validation → 422, unknown id → 404, disallowed transition → 409. Request
validation is hardened so non-standard `NaN`/`Infinity` JSON tokens produce a
stable 422 (never a 500 or a stack trace).

## 9. Frontend workflow

Sidebar → **Experiment Registry** (Product Workflow group; also in the command
palette). The view has three modes:

- **List** — summary cards, a filter bar, and a sortable/paginated table with
  loading/empty/error states, an "Export JSON" download, and "Load demo
  registry".
- **Detail** — identity/status, reproducibility assessment, full fingerprints
  (copy-to-clipboard), provenance & lineage, timing, parameters, metrics, tags,
  notes, error message, and a read-only raw-JSON view; lifecycle actions
  (mark-baseline / invalidate / delete) and "Compare with…".
- **Compare** — pick two experiments (row checkboxes or the detail action) and
  see grouped, neutral differences.

Notes are rendered as text (never as HTML); there is no `dangerouslySetInnerHTML`.

## 10. Comparison semantics

Exactly two records are compared. Differences are grouped into identity,
parameters, dataset, seed, provenance, metrics, fingerprints, and status/timing.
Each field is `same` / `changed` / `only_in_a` / `only_in_b`. Numeric metrics
also report the absolute difference and a **percentage difference only when it is
mathematically valid** (finite values and a non-zero A denominator). The diff is
factual: a larger or smaller value is never labelled better or worse, and no
experiment is recommended.

## 11. Demo fixture

`POST /demo-seed` (or the "Load demo registry" button) loads six deterministic,
clearly-marked demo records covering: Scenario Studio severe stress (a baseline
and a reproducible rerun), a KO/PEP pairs backtest baseline, a macro-regime
baseline and a partial-reproduction rerun, and one failed run. Loading is
idempotent (stable `demo_key`), never overwrites or deletes real records, and
uses fixed fixture timestamps. Metrics mirror QuantLab's known frozen demo
outputs; no quant logic is re-run.

## 12. Export

`GET /export` returns `{schema_version, exported_at, filters, count,
experiments}`. It never includes secrets, environment variables, absolute local
paths, home paths, database file paths, or API keys — only the recorded fields
and provenance. Export is read-only and never mutates the registry. The frontend
turns it into a browser download with a safe filename; nothing is written into
the repository.

## 13. Integration guide

Existing modules can record runs incrementally via
`app.experiment_registry.integration` without being rewritten:
`record_experiment`, `start_experiment`, `complete_experiment`,
`fail_experiment`, `mark_experiment_invalid`. **Failure policy:** these are
best-effort — every function catches all exceptions, logs a warning, and returns
`None`, so a registry problem can never corrupt or block the caller's main
result. A module should compute and return its real result first, then record.

Flagship-workflow decision (v1): the Scenario Studio and KO/PEP endpoints are
**not** auto-instrumented. They are pure request/response endpoints with frozen
quantitative outputs called on every interaction; auto-recording each call would
add a per-request database side-effect and pollute the registry. Instead, both
flagship workflows are represented by demo records, and the opt-in helper is
available for modules that choose to record.

## 14. Testing

- Backend: `test_experiment_registry_fingerprints.py`, `_store.py`, `_service.py`,
  `_api.py`, `_integration.py` — fingerprint determinism/NaN rejection, schema on
  fresh + pre-existing DBs, CRUD, pagination, filtering, baseline scope, parent
  relationship, reproducibility states, comparison, demo idempotence, export,
  API happy/error/adversarial paths, and Saved Reports preservation. All use
  isolated temporary SQLite databases.
- Frontend: `npx tsc --noEmit`.
- Browser E2E: `frontend/e2e/experiment-registry.spec.ts` (see the runbook).

## 15. Limitations

Single-user, local-first, no auth, no history/versioning of a record beyond its
`updated_at`, no soft-undo of a delete, and the reproducibility assessment is a
metadata check — not a re-execution of the experiment. Registries are only as
honest as the metadata modules record into them.

## 16. Security / privacy

No login, no telemetry, no analytics, no external network, no secrets. All SQL is
parameterised. Inputs are strictly validated (bounded strings/tags/JSON, finite
numbers only, SHA-256 validation, forbidden extra fields). Export and provenance
deliberately exclude paths and secrets.

## 17. Dataset Lineage links (Phase 49.0)

The Dataset Lineage registry ([`DATASET_REGISTRY.md`](DATASET_REGISTRY.md))
can associate an experiment with the exact dataset **versions** it used
(roles: input / benchmark / labels / features / reference / output) via
`experiment_dataset_links`. The experiment detail shows a "Linked datasets"
section, each link reports whether the experiment's recorded
`dataset_fingerprint` matches one of the version's fingerprints, and the
reciprocal list is available at
`GET /experiment-registry/experiments/{id}/datasets`. Links are additive
context — historical experiments that recorded only
`dataset_name`/`dataset_fingerprint` keep working unchanged.

## 18. Model Validation Lab records (Phase 50.0)

Executed validation runs from the Model Validation Lab
([`MODEL_VALIDATION_LAB.md`](MODEL_VALIDATION_LAB.md)) can create experiment
records here (module `model_validation`, type = validation method, split/
leakage metrics) — idempotently: a run creates at most one record, and
re-execution reuses it.

## 19. Feature Diagnostics records (Phase 52.0)

Executed feature-diagnostics runs
([`FEATURE_DIAGNOSTICS_LAB.md`](FEATURE_DIAGNOSTICS_LAB.md)) can create
experiment records here (module `feature_diagnostics`, type =
`importance_<method>`, held-out integrity + top feature names as descriptive
parameters, stability/drift summary metrics) — idempotently: a run creates
at most one record and re-execution reuses it. No recommendation is ever
recorded.

## 20. Overfitting Diagnostics records (Phase 53.0)

Executed overfitting-diagnostic runs
([`BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md`](BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md))
can create experiment records here (module `overfitting_diagnostics`, type =
`cscv_pbo_<metric>`, PBO/PSR/DSR + trial-count assumptions as metrics, both
fingerprints as parameters) — idempotently: a run creates at most one record
and re-execution reuses it.  No recommendation is stored and no candidate is
ever marked as selected for deployment.

## 21. Regime Diagnostics records (Phase 54.0)

Executed regime-diagnostic runs
([`REGIME_DIAGNOSTICS_LAB.md`](REGIME_DIAGNOSTICS_LAB.md)) can create
experiment records here (module `regime_diagnostics`, dimensions +
integrity status as parameters, coverage/stability counts as metrics, both
fingerprints) — idempotently: a run creates at most one record and
re-execution reuses it.  No recommendation is stored.

## 22. Cost Diagnostics records (Phase 55.0)

Executed cost-diagnostic runs
([`TRANSACTION_COST_DIAGNOSTICS_LAB.md`](TRANSACTION_COST_DIAGNOSTICS_LAB.md))
can create experiment records here (module `transaction_cost_diagnostics`,
cost-model choices + integrity/completeness states as parameters,
gross/net/cost totals and participation-warning counts as metrics, both
fingerprints) — idempotently: a run creates at most one record and
re-execution reuses it.  No recommendation is stored.

## 23. Portfolio Diagnostics records (Phase 56.0)

Executed portfolio-diagnostic runs
([`PORTFOLIO_DIAGNOSTICS_LAB.md`](PORTFOLIO_DIAGNOSTICS_LAB.md)) can
create experiment records here (module `portfolio_diagnostics`,
construction/covariance methods + integrity/solver states as parameters,
portfolio volatility / effective positions / budget deviation / turnover
/ violation counts as metrics, both fingerprints) — idempotently: a run
creates at most one record and re-execution reuses it.  No recommendation
or preferred allocation is stored.

## 24. Portfolio Stress records (Phase 57.0)

Executed portfolio-stress runs
([`PORTFOLIO_STRESS_LAB.md`](PORTFOLIO_STRESS_LAB.md)) can create
experiment records here (module `portfolio_stress_diagnostics`, scenario
type + linked portfolio run/rebalance + integrity/completeness states and
both fingerprints as parameters; net scenario return, stressed volatility,
breach count, episode count and maximum drawdown as metrics) —
idempotently: a run creates at most one record and re-execution reuses it.
A stored scenario result is a measurement under stated assumptions, never
a prediction, a worst case, or a recommended action.

## 25. Portfolio Attribution records (Phase 58.0)

Executed attribution runs
([`PORTFOLIO_ATTRIBUTION_LAB.md`](PORTFOLIO_ATTRIBUTION_LAB.md)) can create
experiment records here (module `portfolio_performance_attribution`, with the
portfolio and benchmark identity, attribution method, linking method, period
count, integrity / completeness / reconciliation states and both
fingerprints as parameters; gross and net portfolio return, benchmark
return, active return, tracking error and contribution concentration as
metrics) — idempotently: a run creates at most one record and re-execution
reuses it.  No claim of alpha, manager skill or a preferred portfolio or
benchmark is ever stored.

## 26. Factor Diagnostics records (Phase 59.0)

Executed factor-diagnostic runs
([`FACTOR_DIAGNOSTICS_LAB.md`](FACTOR_DIAGNOSTICS_LAB.md)) can create
experiment records here (module `factor_diagnostics`, with the analysis
mode, regression method, timing and vintage policies, intercept and rank
policies, the ordered factor ids, the target type, the observation count and
the configuration fingerprint as parameters; observations, factor count,
R-squared, adjusted R-squared, residual standard deviation, condition
number, held-out R-squared, integrity state, rank state and the result
fingerprint as metrics) — idempotently: a run creates at most one record and
re-execution reuses it.  No claim of causality, alpha, skill, prediction or
a recommended factor exposure is ever stored.

## 27. Future extensions

Per-record change history, richer charts (timeline / module distribution),
optional CSV export, cross-scope baseline dashboards, and opt-in recording from
more modules — all local-first, with the same honest-scope caveats.
