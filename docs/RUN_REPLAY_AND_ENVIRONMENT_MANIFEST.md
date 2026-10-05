# Run Replay and Environment Manifest v1

Phase 66 is inspect/prefill provenance, not an automatic rerun service.
No GET, navigation, refresh, history, restore or settings effect executes
research. The ordinary Run button is a separate explicit action.

## Support Matrix

| Source | Persisted information | Restore/data/target | Limitation |
|---|---|---|---|
| New SMA provider result | Original strict wire JSON when available, otherwise labelled validated model/defaults; canonical settings; execution/save manifests; result identity | Existing Backtest Studio SMA form | History is not retained; Run deliberately fetches current provider data |
| SMA CSV result | Validated request/defaults, canonical raw-byte fingerprint, execution metadata | Existing SMA form, verified CSV reselection | Fingerprint alone cannot recover upload; no fallback |
| Explicit local demo/rerun | Above plus owned Registry version, material pin and retained bounded UTF-8 CSV | SMA form; explicit Run uses existing CSV engine | Fixed historical ticker/date range; no remote custom benchmark |
| Verified legacy SMA saved row | Existing params.reproducibility only, after explicit registration | Canonical settings prefill | Original request, diagnostics and execution environment unknown |
| Other saved single-asset strategies/pairs with valid legacy hashes | Config-only registration/inspection | No executable restore/export adapter | Never translated into SMA |
| Comparison, portfolio, options/rates/credit, research/ML labs | No new persistence adapter | Deferred | Existing hashes/artifacts unchanged |

The adapter checks every canonical field by rebuilding through the existing
normalizer and comparing identical canonical JSON. Effective simple bps may
replace an omitted legacy cost UI representation; auto annualization retains
the original choice when recorded, otherwise uses its resolved convention.
Partial risk rules remain blank in the form rather than acquiring fake defaults.
Original JSON is not fabricated from a canonical legacy record.
Exact form restoration requires `YYYY-MM-DD` dates. Compact and week-date
representations are unsupported; historical strings and hashes are not rewritten.
Recorded requests retain effective cost precision and known diagnostics.
Config-only legacy restoration recovers canonical values, including the
existing six-decimal cost precision; discarded UI representations remain unknown.

## Identity Layers

- Existing `backtest_config_v1` and `comparison_config_v1` algorithms and
  12-character display prefixes are unchanged. Lookup requires full lowercase
  64-character hashes; prefixes/malformed hashes return 422; unknown returns 404.
- `replay_input_v1` includes the canonical configuration, adapter, actual
  effective cost precision, known robustness/sensitivity settings, real Registry
  material/content/manifest pins and optional declared lifecycle provenance.
  Environment/result differences do not change this input identity.
- `environment_manifest_v1` is separate. Python, pandas, numpy, scipy, FastAPI,
  Pydantic, app version, source SHA/dirty are allowlisted; missing Git metadata,
  frontend build and Node remain unknown. No usernames, paths, environment
  inventories, dependency installation or runtime switching.
- `saved_execution_v1` includes database-local saved ID/time, input/environment
  hashes and result hash. Equal numerical results may have equal result hashes
  but distinct executions. IDs are local, not cross-database portable.

The new serializer does not replace the legacy serializer. Arrays and timestamp
strings retain order/meaning. Plain JSON rejects duplicate keys, nonfinite or
unsafe numbers (magnitude above 2^53-1), excessive depth (20), nodes (300000)
or bytes. Request mapping separately rejects unknown fields and coerced
executable numeric/Boolean values.

## Persistence and Trust

Startup schema changes are additive/idempotent: nullable indexed full hash/schema
columns and `run_replay_contexts`, unique per saved row, not per config hash.
Existing results/notes are preserved. An explicit new save with capture inserts
result and replay context in one transaction, rolling back both on error; it
performs no provider request or numerical rerun. Deletes remove companion rows.
No GET/startup backfill occurs. Explicit legacy registration is idempotent and
does not invent data/environment history or overwrite a prior context.

Integrity checks compare actual stored canonical/result/snapshot content and
material Dataset Registry metadata, not only caller-supplied checksum labels.
Recorded request, saved scalar fields, canonical configuration, dataset pins
and declared environment roles must agree independently, even if corrupted
payloads have been rehashed. Parent contexts must refer to an earlier saved
record with matching fixed ticker/date/provider/fingerprint and dataset pin;
parameter edits may produce a new result. Provider parent settings do not
freeze historical prices. Repeated saves produce distinct saved-context
identities, without establishing that the engine ran twice.
Hashes detect mismatches, not authenticity: a database writer can forge content
and all hashes. Result/execution metadata supplied to the local save API are
declared and not attested. Save-time context is never execution-time context.

Retained input is UTF-8 CSV, at most 128 KiB and 2000 cleaned rows, with schema,
dates/counts/raw-byte fingerprint checked. Registry locators are never followed.
The existing parser uses daily closes: timezone-aware inputs convert to UTC
calendar dates, naive inputs keep their calendar dates; it drops invalid rows,
keeps the last uploaded duplicate date and sorts. Literal close takes precedence
over adjusted close. Ticker is a declared label, not independently verified
entity identity in the price series.
Optional OHLCV columns are not a replayed intraday table contract. Raw-byte
identity is distinct from parsed daily-close semantics.
Material mutations, invalidation/inactivity or missing versions block local
execution. Missing CSV requires deliberate upload and raw-byte comparison.
Local date/ticker changes require the existing CSV Upload workspace, not silent
filtering or a remote fetch. Parameter edits retain the local input binding but
detach the exact restored-form hash claim; deliberate rerun saves a new record.
Dataset/artifact material is rechecked immediately before local execution.
Separate registry reads and engine entry are not an atomic cross-registry
snapshot; concurrent writes can also shift offset pagination.

Optional Phase 65 links are declared `provenance_only` references checked through
public read-only lifecycle APIs. They are not predictions-to-returns adapters or
proof that a model generated the strategy. Changed/missing/incomplete links
block context readiness. No training, imports or diagnostic execution on reads.

## API and Navigation

Backend paths (frontend prepends `/api` through the existing proxy):

| Method/path | Behavior |
|---|---|
| GET `/run-replay/hash/{full_hash}?page=1&page_size=20` | Canonical settings and bounded explicit contexts; page size <=50, page <=1000; never chooses newest |
| GET `/run-replay/contexts/{id}` | Read-only material preflight/environment comparison; changed stored content returns 409 |
| GET `/run-replay/contexts/{id}/export` | Versioned JSON with references/settings/limitations, no CSV bytes or locators; unsupported adapter refused |
| POST `/run-replay/register/{saved_id}` | Explicit idempotent legacy registration |
| POST `/run-replay/demo` | Creates one owned local dataset/version and actual SMA result, explicitly saves it |
| POST `/run-replay/contexts/{id}/check-input` | Bounded CSV comparison only; no research or persistence |
| POST `/run-replay/contexts/{id}/execute-local` | Explicit Run action, existing CSV signals/engine; never overwrites parent |

Replay JSON request limit is 256 KiB; saved-result requests are bounded to 4 MiB
before model parsing. Context snapshots <=512 KiB, original requests <=32 KiB,
environment <=8 KiB. IDs are positive integers <=2^31-1. Export includes no input
bytes and does not imply underlying data are bundled.

Run Replay is in Sidebar/palette/canonical workspace registry. Saved detail
offers inspection or explicit registration for legacy rows. URL state is
`?view=runreplay&hash=<full hash>&context=<id>`, <=512 characters; never raw JSON,
dataset bytes or credentials. Context/hash mismatches and stale responses refuse
restore. Confirmation protects unsaved settings, Cancel leaves them untouched.
Confirmation fetches fresh preflight; stale context responses and stale Run
results cannot replace newer settings. Selecting the active SMA is inert;
retained local input stays attached until an explicit detach/preset action.
Editing/removing replay settings is explicit; demo/library presets detach replay.

Environment comparison is field-level `same`/`different`/`unknown` (the response
type reserves `not_applicable` for future fields). Patch differences remain
differences. Matching fields never promise compatibility or bit identity.
Git/source comparisons remain unknown whenever either checkout is dirty or
its cleanliness is unknown. Package versions compare independently; a different
Git SHA alone does not establish changed numerical behavior. VERSION and Git
collection fail independently, and save/inspection metadata are never backdated.

## Local Demo and Later Verification

Explicitly create the local SMA demo in Run Replay, select/inspect its context,
confirm restoration, then separately click Run. No profitable-result promise.
Dataset, version and saved-result demo stages commit separately. A failure
reports confirmed owned IDs and leaves those records in place; no cross-stage
rollback is claimed.
Backend deterministic tests exercise this complete real-engine/persistence path.
Frontend component tests check confirmation/stale/changed/offline/reselection
states and the real destination form. Discovery is not browser execution.

User-only browser gate uses `scripts.run_replay_e2e:create_app` in a fresh
process/single worker with a newly generated `E2E_STRATEGY_ENSEMBLE_TOKEN`.
Use the existing isolated browser runbook, pointing the frontend proxy at that
harness. Both strategy-ensemble and replay ownership proofs must return equal
verified database identities. Every replay/save request rechecks ownership.
Do not point this scenario at the active user database or ordinary backend.
No services, browsers, installs or builds were started during implementation.
The independent review also started no services or browsers and ran no builds.
See [PHASE_66_REVIEW.md](PHASE_66_REVIEW.md) for its separate evidence and gates.
