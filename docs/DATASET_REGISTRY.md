# Data Provenance & Dataset Lineage Registry (Phase 49.0)

A **local-first, single-user** registry of dataset identity, immutable
versions, transformation lineage, metadata-driven quality checks, and links to
the Experiment Registry — so a research run's data can be identified, compared,
and re-verified later.

> **Honest scope.** Provenance records are metadata the user (or a fixture)
> declared, plus deterministic SHA-256 fingerprints over that metadata. They
> are **integrity aids only** — not a regulatory audit trail, not a
> tamper-proof ledger, not digital signatures, not proof of authorship or data
> correctness, and not an enterprise data catalog. Nothing here fetches live
> data or calls providers.

## 1. Purpose

The registry answers: which dataset (and exact version) was used, where it came
from, what schema/date range it contained, which transformations and parents
produced it, which quality checks passed, whether its schema changed, which
experiments used it, whether its identity can be re-verified later, whether it
is demo/local/provider data — and what is still unknown.

## 2. Dataset identity

One row per dataset in `datasets`: `name` (unique), `description`, `domain`,
`dataset_type`, `source_type`, optional `provider` / `source_reference`
(sanitized, never an absolute path) / license fields / `symbol_scope` /
`asset_class` / `frequency` / `timezone`, `format`, `schema_version`,
`current_version_id`, `tags`, `metadata`, `notes`, `is_demo`, `is_active`, and
a derived `provenance_status`. Explicit columns carry everything used for
filtering/status; only genuinely varying structures (tags/metadata) are JSON.

## 3. Dataset versions

Versions (`dataset_versions`) are **immutable after creation** — the only
permitted mutations are quality/validation status updates (from a quality run)
and invalidation. There is no endpoint that edits a stored fingerprint, so
fingerprints can never change silently. Each version carries row/column counts,
date range, format/compression, a validated storage locator, ingestion method,
a `deterministic` flag, a schema snapshot, a statistics summary, provenance,
and four fingerprints (schema / manifest / content / source).
`(dataset_id, version_label)` is unique. **Invalidation preserves the record,
its lineage, and its experiment links** — it stamps `invalidated_at` +
`invalidation_reason` and never deletes anything.

## 4. Source types

`deterministic_fixture` · `local_file` · `generated` · `derived` ·
`optional_provider` · `manual` · `unknown`.

## 5. Storage locator policy

Locators are **logical URIs, never filesystem paths**, and never
network-accessible URLs:

- `fixture://pairs/ko-pep/v1` — tracked deterministic fixtures
- `generated://features/orderflow-5m/v1` — locally generated data
- `local-file://prices_2025.csv` — a user file, **basename only**
- `provider://fred/CPIAUCSL` — an optional-provider identifier

Validation rejects absolute Windows/POSIX/UNC paths, drive letters, `..`
traversal, embedded credentials (`@`), query strings/fragments, whitespace, and
control characters. Absolute local paths are never stored, returned, or
exported.

## 6. Fingerprints

Deterministic SHA-256 over the shared canonical JSON (sorted keys, whole-float
normalization, **NaN/Infinity rejected**):

- **Schema fingerprint** — field names, normalized types (`float64`≡`double`≡
  `float`), nullable flags, ordering (only when declared significant), and the
  schema version. No timestamps, no database ids.
- **Manifest fingerprint** — dataset name, version label, row/column counts,
  date range, format, schema fingerprint, source fingerprint, deterministic
  flag, and declared provenance inputs. No database ids, no absolute paths.
- **Content fingerprint** — supplied by the caller (a verified SHA-256) or
  computed by an **explicit** operation (fixture creation, tests). Never
  computed by hashing files during list/detail API calls; large files are never
  hashed on an ordinary request.
- **Source fingerprint** — optional identity of the upstream source.

Fingerprints are integrity aids — not signatures, not tamper-proofing, not
certification.

## 7. Lineage

`dataset_lineage` edges connect a parent version to a child version with a
relationship type (`derived_from`, `filtered_from`, `aggregated_from`,
`joined_with`, `normalized_from`, `resampled_from`, `feature_generated_from`,
`labeled_from`, `copied_from`), a transformation name/version, parameters, an
optional repository-relative `code_reference`, and a best-effort `git_commit`.
Rules: no self-edges, **cycles rejected** (BFS reachability check with an
absolute edge cap — appropriate for local SQLite scale), missing versions
rejected (404), identical duplicate edges are idempotent, multiple parents per
child supported, invalidated ancestors remain visible. Traversal
(`GET /dataset-versions/{id}/lineage`) is bounded by `max_depth` (≤12) and
`node_limit` (≤200) and reports `truncated` honestly.

## 8. Quality checks

Metadata-driven checks (`quality.py`) validate the **declared structural
properties** a version recorded — they never open files and never prove a
dataset is financially or scientifically correct. Built-ins:
`row_count_nonzero`, `required_columns_present`, `schema_matches_expected`,
`timestamps_parseable`, `date_range_valid`, `timezone_known`,
`no_non_finite_values`, `missing_ratio_within_limit`,
`duplicate_ratio_within_limit`, `content_fingerprint_present`,
`source_identity_present`. No dataset is forced to run every check. Results
carry status (`passed`/`warning`/`failed`/`skipped`/`unknown`), severity
(`info`→`critical`), observed/expected values, and a checker version; the
version's `quality_status` rolls up worst-of.

## 9. Schema drift

`GET /dataset-versions/compare?a=&b=` detects added/removed columns, type
changes, nullable changes, meaningful ordering changes, and range/format
context changes, described **neutrally** — drift is not automatically bad.
Conservative classes: `none` (fingerprints match, no diffs), `compatible`
(additions, nullable loosening, insignificant ordering),
`potentially_breaking` (nullable tightening, coercible type changes such as
int↔float, significant ordering changes), `breaking` (removed columns,
incompatible type changes), `unknown` (missing snapshots). Renames are treated
as remove+add unless explicitly mapped (no rename inference in v1).

## 10. Experiment links

`experiment_dataset_links` associates an experiment with a dataset version in a
role (`input`, `benchmark`, `labels`, `features`, `reference`, `output`).
Links are idempotent per `(experiment, version, role)`. Deleting is not part of
v1; invalidating a version never deletes experiments, and no experiment
operation deletes datasets. Each hydrated link reports `fingerprint_match`:
whether the experiment's recorded `dataset_fingerprint` matches one of the
version's fingerprints (`null` when the experiment recorded none). Historical
experiments with only `dataset_name`/`dataset_fingerprint` keep working —
links are additive context, never required.

## 11. Demo lineage

`POST /datasets/demo-seed` (or the "Load demo lineage" button) loads three
deterministic chains — raw macro fixture → normalized factors → severe
scenario inputs (linked to the Scenario Studio demo experiment); raw KO/PEP
prices → aligned prices → spread/z-score features (linked to the KO/PEP demo
experiment); and an alt-data example with a quality **warning**, deliberate
**schema drift** between v1/v2, an **invalidated** v1, and **partial**
provenance. Seeding is idempotent (unique `demo_key`), seeds the Experiment
Registry demo records first (their own idempotent loader), never overwrites or
deletes real records, and uses no network.

## 12. Export

`GET /datasets/export` returns `{schema_version, exported_at, filters,
datasets, versions, lineage, quality_results, experiment_links}`. It never
contains absolute paths, database paths, credentials, environment variables,
API keys, or home directories. Export is read-only; the frontend downloads it
as a JSON file — nothing is written into the repository.

## 13. Persistence / migration

Five tables (`datasets`, `dataset_versions`, `dataset_lineage`,
`dataset_quality_results`, `experiment_dataset_links`) created idempotently in
`app/db.py::init_db()` with `CREATE TABLE/INDEX IF NOT EXISTS` — non-destructive,
no drops, no rewrites; a pre-existing database gains the tables on startup with
all prior data (experiments, saved reports/backtests) intact. Tests redirect to
temporary files via `app.db._db_path_override`.

## 14. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/datasets/summary` | counts + filter facets |
| GET | `/datasets` | list (filters, sort, bounded pagination) |
| POST | `/datasets` | register a dataset (201) |
| GET/PATCH | `/datasets/{id}` | detail / mutable metadata |
| GET/POST | `/datasets/{id}/versions` | version history / new immutable version |
| GET | `/dataset-versions/{id}` | version detail |
| POST | `/dataset-versions/{id}/invalidate` | invalidate (record preserved) |
| GET | `/dataset-versions/{id}/lineage` | bounded lineage neighborhood |
| POST | `/dataset-lineage` | add an edge (idempotent duplicates) |
| GET | `/dataset-versions/{id}/quality` | results |
| POST | `/dataset-versions/{id}/quality-checks` | run built-in checks |
| GET | `/dataset-versions/compare?a=&b=` | neutral comparison + drift class |
| POST | `/dataset-links` | link a version to an experiment |
| GET | `/dataset-versions/{id}/experiments` | linked experiments |
| GET | `/experiment-registry/experiments/{id}/datasets` | linked versions |
| GET | `/datasets/export` | JSON export |
| POST | `/datasets/demo-seed` | idempotent demo lineage |

Errors: 422 validation, 404 unknown id, 409 conflict (duplicate name/label,
double invalidation). All SQL parameterised; no raw stack traces (non-finite
JSON tokens return a stable 422 via the app-wide handler).

## 15. Frontend workflow

Sidebar → **Dataset Lineage** (Product Workflow group; also in the command
palette). List mode: summary cards, dark-theme (`ql-input`) filters, a
min-width table that scrolls inside its card. Detail: dataset identity,
version history (checkbox-select two versions to compare), per-version
fingerprints/schema/quality, the SVG lineage graph (bounded, invalidated nodes
dashed, quality dots, clickable nodes, tabular parents/children fallback as the
accessible alternative), and linked experiments. The Experiment Registry detail
shows a reciprocal "Linked datasets" section. Notes render as text — no
`dangerouslySetInnerHTML`.

## 16. Testing

`backend/tests/test_dataset_registry_core.py` (locators, fingerprints, drift,
quality), `_service.py` (schema/migration, CRUD, immutability, invalidation,
lineage rules, comparison, links, demo idempotence), `_api.py` (happy paths,
error/adversarial paths, export privacy, coexistence with the Experiment
Registry and Saved Reports) — all on temporary SQLite databases. Browser E2E:
`frontend/e2e/dataset-lineage.spec.ts` (see the runbook).

## 17. Privacy / security

No login, no telemetry, no network, no secrets, no provider tokens. Locators
and `source_reference`/`code_reference` reject absolute paths and credentials;
`license_url` rejects embedded credentials; exports never carry paths or
secrets. Strict bounded validation everywhere; parameterised SQL only.

## 18. Model Validation Lab links (Phase 50.0)

Validation runs ([`MODEL_VALIDATION_LAB.md`](MODEL_VALIDATION_LAB.md)) may
bind a `dataset_version_id`; the run detail shows the version's fingerprints,
provenance, and quality states, warns visibly when the version was
invalidated, and always preserves the recorded identity on historical runs.

## 19. Feature Diagnostics links (Phase 52.0)

Feature-diagnostics runs
([`FEATURE_DIAGNOSTICS_LAB.md`](FEATURE_DIAGNOSTICS_LAB.md)) may bind a
`dataset_version_id`; the run detail shows the version's fingerprints,
provenance and quality states and warns visibly when the version was
invalidated. Feature `source_column`s are checked against the version's
schema snapshot — a missing column produces a recorded warning, never a
fabricated mapping.

## 20. Overfitting Diagnostics links (Phase 53.0)

Overfitting-diagnostic runs
([`BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md`](BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md))
may bind a `dataset_version_id` (run-level and per-candidate); the run detail
shows the version's fingerprints, provenance and quality states and warns
visibly when the version was invalidated.  Dataset metadata is never mutated
by a diagnostic run.

## 21. Limitations

Single-user local-first; content fingerprints for user files rely on
explicitly supplied hashes (no background file scanning in v1); quality checks
validate declared metadata, not the underlying bytes; rename detection is not
inferred; the lineage view shows a bounded neighborhood, not an unbounded
graph; and provenance is only as honest as the metadata recorded into it.
