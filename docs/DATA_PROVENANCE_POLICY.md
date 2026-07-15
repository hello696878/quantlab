# Data Provenance Policy (Phase 49.0)

What "provenance" means — and does **not** mean — in the QuantLab Dataset
Lineage registry.

## What provenance means here

Provenance is **declared metadata about where a dataset came from and how it
was produced**: its source type, upstream references, license metadata, the
transformations and parent versions that produced it, and deterministic
fingerprints over that metadata. It lets you ask, later, "is this the same
data the run claimed to use?" at the metadata level.

## What it does NOT prove

Provenance records do not prove: that the data is correct, complete, or
suitable for any purpose; who authored it; that it was not modified outside
the registry (this is not a tamper-proof ledger — anyone with the SQLite file
can edit it); regulatory or scientific validity; or anything about market
accuracy. A `complete` provenance status means "all three identity signals
were recorded", nothing more.

## Provenance states (derived, documented)

Derived from the **current version's** recorded metadata, from three signals:
a content/source fingerprint, a declared `provenance.source`, and a non-empty
schema snapshot.

- **complete** — all three signals present.
- **partial** — at least one signal present.
- **unknown** — none present.
- **invalidated** — the dataset's current version has been invalidated.

## Source identity

`source_type` declares the origin class (deterministic fixture, local file,
generated, derived, optional provider, manual, unknown). `source_reference`
and locators are sanitized — never absolute paths, never credentials.
Optional-provider datasets record only a logical identifier
(`provider://fred/CPIAUCSL`); registering one never calls the provider.

## License metadata

`license_name` / `license_url` are informational fields the user declares.
The registry does not verify licenses and does not grant rights.

## Dataset versions

Versions are immutable snapshots of identity metadata. New data ⇒ new version;
history is never edited. Corrections happen by invalidating (with a recorded
reason) and creating a new version — the invalidated record, its lineage, and
its experiment links are preserved.

## Transformation recording

Lineage edges record which transformation (name, version, parameters, optional
repository-relative code reference, best-effort git commit) produced a child
from its parents. Edges are facts about declared derivation — the registry
does not re-run transformations to verify them.

## Fingerprint interpretation

Equal fingerprints mean equal **canonical declared metadata** (schema /
manifest) or equal supplied content hashes. They do not prove the underlying
bytes are correct, and a missing content fingerprint means identity is
metadata-only (the `content_fingerprint_present` check surfaces this as a
warning).

## Large-file hashing policy

Content is **never hashed during ordinary API requests**. Acceptable sources
for a content fingerprint: a caller-supplied verified SHA-256, or an explicit
operation at fixture-creation/test time. Version listing and detail never
touch data files.

## Local-path privacy

Absolute local paths (`C:\Users\…`, `/home/…`, UNC) are rejected at
validation, never stored, and never exported. Local files are identified by
sanitized basename (`local-file://prices_2025.csv`) only.

## Optional-provider policy

Provider locators are inert identifiers. The registry performs no provider
calls, stores no API keys, and inherits the platform rule that external
providers are opt-in, fail closed, and never relied on in tests.

## What to record for a trustworthy chain

For deterministic fixtures: the fixture identity, schema snapshot, content
fingerprint (computed at creation), and `deterministic: true`. For derived
data: a lineage edge per transformation with parameters. For experiments: a
link (role `input`/`features`/…) to the exact version used — the link then
reports whether the experiment's recorded dataset fingerprint matches the
version's.
