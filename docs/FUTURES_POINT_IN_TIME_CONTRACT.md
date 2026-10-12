# Futures Point-in-Time Contract v1

Phase 67 supports **local daily individual contracts** compatible with existing
instrument specifications. No acquisition, trading, official calendar, registry
registration, HTTP endpoint or fully PIT-qualified continuous-series claim.

## Source-to-Contract Map

| Existing source | Reuse / boundary |
| --- | --- |
| `app/instruments/futures.py`, `configs/instruments/*.yaml` | Canonical contracts, cycles, positive-price legacy scope, spec-derived third-Friday expiry. Not certified official last-trade/holiday-adjusted schedules. |
| `app/datastore/daily_bar.py`, `csv_fixtures.py`, `ingest.py` | Legacy local CSV ingestion remains intact. New read-only `preview_futures_source` is the typed adapter entry at that seam. |
| `app/datastore/store.py` | Twelve-column normalizer, store behavior and `raw_data_version_hash` unchanged. Extra knowledge/revision metadata is retained separately, never passed to a destructive store overwrite. |
| `app/datastore/futures_continuous.py` | Existing adjustment/stitching engine; optional `declared_calendar` delegates scheduling only. Default behavior and legacy identity unchanged. |
| `app/ml_lifecycle/importer.py` | Reuses inspected local-path, pinned-directory and bounded regular-file read safeguards. No codec/model import or database execution. |
| `app/run_replay/identity.py` | Existing bounded plain-JSON parser/canonical digest; no replay adapter/engine changes. |
| Dataset Registry public services, lineage, locators | Audited immutable-version/provenance conventions; no real registration needed here, no direct table writes or locator dereference. |
| External-provider source audit | No pre-existing futures provider or futures enable flag exists. Globe FRED/quotes are unrelated; ordinary equity yfinance is not an acceptable futures substitute. New ingestion-seam external selection always fails before I/O. |

The ingestion plan and several module docstrings retain historical deferred
claims for store/continuous work subsequently implemented in Phases 7/8.
Those historical documents are not rewritten or treated as current source truth.

## Immutable Declarations

`Snapshot` (`futures_snapshot_v1`) retains source/root, snapshot ID, explicit
`trading_session_label` timestamp role, price basis (`last_trade`, `settlement`,
`unknown`), calendar ID/version, actual spec-content hash, revision policy,
license declarations and 1..2000 frozen bars. Nested collections are tuples;
Pydantic rejects extra fields. Input strings are not executed or dereferenced.

Each bar retains source/root/canonical individual contract, ISO trading label,
spec-derived expiry, OHLC, nonnegative integer volume, nullable nonnegative OI,
revision ID, optional superseded revision and explicit availability fields.
Numbers reject Boolean/string coercion, nonfinite values and unsafe large
integers. Positive-price/OHLC rules intentionally preserve this existing local
instrument scope; this is not a universal negative-price futures contract.
Futures roots require bounded canonical uppercase letters/digits before local
spec lookup; a generic identifier cannot become a drive-relative or stream path.

Labels are dates, **not actual UTC closing instants**. The legacy bridge stores
midnight UTC with the same label. Converting that instant to Chicago may show
the previous civil day; the new contract never derives its label that way.
Actual session intervals are declared separately by the calendar. No intraday
observations are reconstructed from daily bars.

## Knowledge Time

`Availability` separates price, volume and OI declared availability from
`local_received_at`. All instants require explicit offsets and normalize to UTC;
naive timestamps, numeric epochs and guessed zones are refused. Binding to the
calendar refuses full daily-field availability before the session ends. A
known local receipt cannot precede a known field's declared availability.

The supported conservative record boundary is the **latest of all three
required field availability times**, not price availability alone. Any unknown
required availability makes this record boundary unknown, including missing OI
publication information. Missing OI remains null, never zero. A caller may use
the price/volume-only helper explicitly, but the default as-of selector requires
the full daily record. It does not silently substitute modes:

- `declared_source`: record-level source availability <= inclusive cutoff.
- `local_observed`: recorded local receipt <= inclusive cutoff.

Neither mode attests source statements. Historical local receipt in a submitted
file is also an unverified declaration, not independently reconstructed receipt
evidence. `inspected_at` is the actual current preview time and **never fills in
historical receipt**. Unknown receipt stays unknown. Calendar and instrument
historical knowledge are separate limitations; selected bars do not certify a
historically known calendar/spec. Call `validate_binding` on each snapshot with
its material calendar before selection (the public adapter does so).

Legacy frames remain readable through existing APIs. `legacy_status` explicitly
reports incomplete/unsupported strict provenance rather than inferring PIT.

## Revision and As-of Policy

`explicit_supersession_v1` comparison distinguishes exact duplicate, new
observation, explicit revision, same-version contradiction and ambiguous
provenance. Comparisons reject mixed provenance/calendar/spec contexts. No source
file is merged, replaced or repaired. Corrections live in independent immutable
input snapshots, with original data retained.
Here exact duplicate means identical normalized bar/revision declarations;
physical byte equality (including formatting/line endings) is reported separately.

`as_of` accepts 1..16 compatible snapshots, at most 4000 records in total.
It deduplicates identical revision material; refuses contradictions, missing
parents, multiple roots, branches, cycles, disconnected chains and non-increasing
known revision times (including equal-time ties). Supersession, not input order
or lexical revision ID, determines which eligible version succeeds another.
Unknown and future records are counted explicitly. Appending a valid correction
whose relevant availability is after the cutoff cannot change earlier selection
under that policy. Newly supplied evidence already eligible at the cutoff may
legitimately change the selection. Comparison recognizes explicit parents in
either supplied snapshot; the selector separately validates the complete graph.
No eligible records is an incomplete result, not invented empty success.

## Identity Layers

- Physical SHA-256: exact bytes read for CSV, metadata and calendar, reported
  separately for correction inputs too.
- `futures_market_table_v1`: selected market keys/values, order-independent;
  requires a nonempty single vintage, excludes availability/revision identity.
- Existing `raw_data_version_hash`: unchanged legacy normalized twelve columns.
- `declared_futures_calendar_v1`: full material calendar, coverage and knowledge
  declaration; same display ID/version with changed material changes the hash.
- `futures_pit_envelope_v1`: market values, revision graph/knowledge declarations,
  price basis/source/license, material calendar, actual instrument specification
  and policy. Snapshot display ID and physical whitespace are not scientific
  identity. Revision order is canonically sorted only for hashing, not selection.
- `declared_continuous_futures_v1`: retained input envelopes, selected revisions,
  mode/cutoff, calendar, spec/roll policy and adjustment policy. The CLI binds the
  selected vintage, never mislabels the legacy continuous config hash.

Integrity comparisons are not proof of authenticity, ownership, historical
publication, licensing or profitable/tradable results.

## Adapter, Local I/O and Licensing

`AdapterRequest`, `AdapterResult`, `Capabilities` and `AdapterFailure` are the
typed v1 seam. Explicit `external` fails with `provider_disabled` before reading
paths or contacting a network, regardless of environment flags or inert
provider-looking metadata. No enable flag, fallback, provider client or dynamic
import is added. Local results expose basis/source in the snapshot, coverage,
missing fields, vintage/calendar identities, physical hashes and limitations.

Only operator-selected CSV plus metadata/calendar JSON are supported, 256 KiB
per file, 2000 CSV rows, exact unique columns and bounded cells. Parsing occurs
in memory. Existing safeties refuse symlinks/reparse points, hardlinks, nonregular
files, UNC/drive-relative paths and observed file/parent replacement. Traversal,
archives, recursive scans and executable formats are not supported. All reads
are read-only; material is reread after validation to detect cross-file mutation.
This is **not an atomic multi-file or adversarial-filesystem snapshot guarantee**.
The existing lower-level bounded reader caps at 4 MiB before the narrower 256 KiB
adapter limit. No artifact export or database initialization exists in v1.
Public failures use bounded diagnostics without echoing declaration values,
parser payloads or operating-system paths. Unknown instruments and timestamps
whose UTC conversion exceeds the supported datetime range are invalid inputs.

License status (`unknown`, `synthetic`, `user_declared`), intended use,
redistribution and attribution are inert declarations. Rights remain unknown
unless separately established; no vendor is approved and no legal certification
is supplied. The acceptance corpus is invented repository data, not vendor
history. Dataset Registry registration/lineage integration remains deferred
because this read-only path has no actual registration operation.

See [calendar, diagnostics and CLI runbook](FUTURES_DECLARED_CALENDAR_AND_VALIDATION.md)
and [implementation evidence](PHASE_67_IMPLEMENTATION.md).
