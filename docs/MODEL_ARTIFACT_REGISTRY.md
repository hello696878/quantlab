# Model Artifact Registry Contract

## Identity and Immutability

Schema-1 canonical JSON sorts object keys, preserves array/feature-column order,
uses finite plain JSON scalars and SHA-256 with an explicit kind/version envelope.
Tables declare scalar types, keys and nullability; rows sort on their full typed
keys. UTC timestamps retain intraday precision. Duplicate keys and sample IDs,
ambiguous timestamps, invalid finite values and inconsistent row widths fail.
Schema versions and counts require integers, never coerced Booleans. JSON
integer/float/Boolean/null/string identities are distinct. Declared `number`
table columns normalize finite values to binary64; integers outside the exact
binary64 integer range are refused. Duplicate JSON object keys are also refused
at the HTTP boundary, before framework model parsing.

Physical file-byte SHA-256 is distinct from normalized semantic fingerprints:
CSV/Parquet/JSON formatting can differ physically while describing the same
table. Original upstream configuration and `train_run_hash` values are preserved;
they are not redefined as data or fitted-model identities.

Separate lifecycle, source, source environment, feature/label specs, splits,
models, calibration, predictions and evaluation identities are exposed. Every
fold has a distinct fitted-model artifact, safe parameters, exact ordered
features and retained training-data/membership hashes. Split identity excludes
descriptive audit label statistics, which would otherwise make an unchanged
trained model depend on held-out labels. Those audit statistics remain covered
by the overall snapshot integrity hash.

Lifecycle semantic identity excludes importer environment and physical byte
hashes; it never includes incidental database IDs, name, import time, temporary
paths or duration. Scientific event/availability/cutoff timestamps are included.
Source environment is allowlisted Python/numpy/scipy/pandas/Pydantic/application
versions and available Git identity, marked `source`. A legacy source environment
stays `unknown`; the current importer is separately marked `inspection`.

No username, home directory, environment variable inventory, token, unrestricted
package inventory or executable serialization is collected. JSON parameters are
snapshots, not classes to instantiate from imported code. There is no eval,
dynamic artifact import, shell expression or model-upload execution path.

## File and Persistence Safety

One explicitly selected root/run only; no startup scanning. Maximum 4 MiB per
file and combined source, 2000 rows, 80 columns, nesting depth 16 and bounded JSON
collections. Bare lowercase SHA-256 run IDs and root-level allowlisted artifact
locators only. Unknown files, duplicate JSON keys, alternate frame copies,
symlinks, Windows reparse points/junctions, hardlinks and special files fail.
The importer checks ancestry, opened handle identity, size/time consistency,
then rereads every selected file and directory inventory to detect concurrent
mutation. Source files are never modified. The registry retains typed snapshots,
so later removal of the source folder does not pretend a pinned live file still
exists; physical hashes describe the bytes at import time only.
Directory ancestry is pinned and its identity rechecked while reading (Windows
handles; POSIX descriptor-relative reads). A blocked or detected replacement
refuses import; no unconditional Windows rename-lock guarantee is made. The explicit destination database
also rejects linked ancestry/hardlinks; the CLI restores its prior database
override after success or failure. This is bounded local import, not a hostile
same-user filesystem sandbox or a general atomic multi-file snapshot facility.
The existing SQLite API opens a destination pathname; a hostile same-user
concurrent replacement is not a proven portable write boundary, especially on
POSIX. Use an operator-owned destination with exclusive filesystem control.

SQLite initialization adds `ml_lifecycles` and `ml_lifecycle_links` idempotently.
No existing table is dropped or rewritten. Unique semantic identity plus dataset
version makes duplicate imports idempotent; the first physical snapshot is kept.
Parameterized SQL is used. Scientific snapshots are immutable through the API.
The review adds a nullable `dataset_material_hash` pin over the actual stored
dataset/version metadata, including schema/statistics/provenance/event times.
Old records retain a missing pin and fail closed as changed/unverified; migration
never certifies their current content retroactively or overwrites old evidence.
Dataset row IDs, inspection timestamps and storage locations are excluded.
Known child database envelopes omit incidental IDs/runtime metadata while nested
scientific metadata remains material. Destination content pins preserve inherited
destination hashes, which may themselves include legacy IDs; they are integrity
pins, not cross-database scientific-equivalence claims.

Stored, processing, completeness, integrity and validation states are independent.
An imported legacy record can be stored/intact while incomplete/unverified.
The complete label requires the internally generated demo and all five intact
diagnostic links. An external caller cannot register a claimed complete/OOF demo.

Each adapter claims its own job transactionally. A downstream failure remains
failed/incomplete with no stale completed badge. A retry reuses the same owned
destination ID/key. Multi-service operations are not globally atomic. A process
crash leaving a `running` claim requires operator inspection; the service does
not guess that a concurrent job has stopped or silently repeat it. No automatic
retry on list, detail or export. Demo creation can be resumed explicitly.

## Verification Boundary

Closed-interval purge and independent audits are reused from Model Validation.
Training/call order is verified by the deterministic fixture and adversarial
tests, not inferred from a caller's OOF flag. Held-out-label mutation must leave
all model and calibration parameters and thresholds unchanged. Prefix tests
apply to causal feature outputs, not full-data identities.

The API rejects missing/invalidated/incompatible dataset versions. It recomputes
snapshot and linked content before strict export/compare; missing or altered
content cannot be promoted to verified by its advertised hash alone. No model
ranking/promotion or profitability acceptance criterion exists.

See [review evidence](PHASE_65_REVIEW.md), [implementation evidence](PHASE_65_IMPLEMENTATION.md) for historical runs and
[lifecycle workflow](ML_RESEARCH_LIFECYCLE.md) for adapter and timing limitations.
