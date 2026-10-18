# Read-Only Synthetic Demo and Deployment Hardening v1

Current: 2026-10-18, Phase 70, `4.88.0-dev`. This is local implementation plus
a hosting plan. Nothing has been hosted, certified, or provisioned. Phase 69
is frozen at `1062ec48b4128af867ab5a3329951511ebff285c`, tree
`3a06cbef017e1828781d2e6861c17eecf4afd014`. Its user-supplied final-document CI
`39091756914` succeeded in both jobs; it is not Phase 70 verification.

## Serving Boundary and Source Reuse

| Entry/source | Demo decision |
| --- | --- |
| `app.serving:create_app --factory` | Capture strict operator mode/config before importing an app |
| Ordinary `app.main:app` | Local default preserved; explicit demo configuration refuses this wrong entrypoint before its imports/startup |
| Ordinary lifespan / db.init_db / get_connection | Never used by demo startup or requests |
| Saved CRUD / replay / reports / all labs | Ordinary route registration is bypassed, not filtered by GET or URL prefix |
| SMA signals / run_backtest / compute_metrics / SavedBacktestCreate / saved save | Reused only in deliberate offline preparation |
| Phase 69 acquisition/render/verify | Explicit corpus path, rollback-mode RO transactions during corpus verification; no default path fallback |
| Demo list/detail/explanation | Approved pinned public projections cached at startup; bounded corpus byte observations before reads |
| Globe / FRED / quotes / yfinance / other providers | No routes or calls in demo, regardless of ordinary enable flags |
| Existing app shell / saved list/detail / explanation panel | Reused after validated capabilities; no parallel research dashboard |

The factory reads QUANTLAB_SERVING_MODE: absent means `local`; exact
`read_only_demo` selects the separate demo app. Empty/unknown/case/whitespace
variants refuse. Demo variables with local mode or unknown QUANTLAB_DEMO_ keys
refuse rather than silently opening the writable app. The ordinary lifespan
rechecks configuration immediately before writable initialization, including
when its module was cached under an earlier environment. There is no HTTP toggle.
Each demo app owns its corpus observation and admission state. Local operation
retains its existing singleton/database semantics; v1 deployment uses one
process, one event loop and one worker, not concurrent operator preparation.

## Versioned Route Policy

`read_only_demo_v1` permits exactly these GET patterns:

- `/health`: process liveness only, no corpus access.
- `/ready`: approved observed corpus availability, not initialization.
- `/capabilities`: `serving_capabilities_v1`, mode/policy/public corpus identity.
- `/saved-backtests`: one bounded synthetic summary.
- `/saved-backtests/1`: the corresponding public saved result.
- `/research-explainer/saved-backtests/1`: existing pinned deterministic bundle.

All other methods/routes are 403 before endpoint dependencies or body parsing,
including stateless research POSTs, uploads, seeds, resets, imports, migrations,
registrations, saves, deletes, reports, all provider GETs, OpenAPI/docs/debug,
HEAD/OPTIONS, unknown routes, extra path segments and unsupported mounts.
There are no trailing-slash redirects. Raw/decoded paths must agree exactly;
encoded variants, backslashes, non-ASCII paths and nonempty root_path refuse.
Only ID 1 is public. Query fields are prohibited except exactly one lowercase
64-hex `expected` fingerprint on the explanation route (mismatch is 409).
Unknown routes stay refused even if accidentally registered. Tests compare the
actual demo route inventory and exercise the ordinary registered route surface
against this separate deny-by-default app. UI flags do not authorize requests.

## Corpus Preparation, Verification and Lifecycle

The corpus is a NEW operator-owned directory containing `demo.db` and
`corpus.json`, not backend/data/quantlab.db. Preparation never accepts an
arbitrary source database, scans private directories, or clones saved user work.
It creates the current schema and one 180-business-day deterministic synthetic
SMA(5,20), long-only result using the existing engine, 100000 initial capital,
10 bps cost and declared 252-period convention. Other schema tables are empty.
Dates beginning 2000-01-03 are illustrative series indices, not historical
execution dates. created_at/prepared_at are actual preparation times.

The manifest binds schema `public_sma_corpus_v1`, explicit synthetic provenance,
public saved IDs, preparation timestamp, database SHA-256 and public material
SHA-256 into a corpus_id. The operator must pin its full ID when serving.
This is consistency metadata, not a signature or authenticity attestation.
Different runtime/SQLite/preparation times may produce different bytes/IDs;
cross-runtime byte identity is not promised.

Verification bounds the DB to 2 MiB and manifest to 16 KiB, structurally
preflights the manifest and all four stored JSON fields before full strict
decoding, and refuses duplicate JSON members. It checks full identity,
fixed public labels/params, exact equity/trade projections, saved inventory,
empty other user tables (bounded identifier/inventory checks), required real
tables/columns before application data queries, integrity,
public result material, existing explanation validation, and before/after byte
observations. SQLite opens use explicit `mode=ro`, query_only and transactions.
The Phase 69 rollback-header/no journal/WAL/SHM restriction is preserved. Missing,
symlinked/reparse/hardlinked, changed, malformed or unsupported material refuses without creating
directories, repairing, seeding, migrating or changing journal modes.
Startup compares observations across verification before marking readiness.
Serving uses the validated in-memory result/bundle; later changes refuse reads.

These are observed-state checks, not an atomic filesystem sandbox against
privileged/native writers or all path-replacement races. Enforce operator-owned
read-only mounts/permissions in a future deployment. No `immutable=1` shortcut.
No hot replacement while serving: stop the process, prepare/verify a NEW version,
switch the configured path/ID and restart. Preserve previous artifacts.

The application does not write corpus DB/manifest/sidecar contents in supported
serving state. This is not a claim that OS access metadata, process memory or
operator-configured temporary files/logs never change. Future read-only mounts
and permissions provide a different enforcement layer and are not yet verified.

### Operator Commands (Not Executed by Implementation)

Use an existing suitable Python environment; never install into a user's global
environment merely to run these examples. Choose a NEW explicit external parent
and stop on any nonzero exit. The backend cwd below is required for `app.*`.

```powershell
cd C:\quantlab\backend
$Python = 'C:\quantlab\.venv\Scripts\python.exe' # operator-selected existing environment
$Root = 'C:\QuantLabDemo\phase70-owned-UNIQUE'    # choose a new owned parent
New-Item -ItemType Directory -Path $Root -ErrorAction Stop
$Corpus = Join-Path $Root 'corpus-v1'            # MUST NOT already exist
$Id = & $Python -B -m app.demo_corpus prepare --destination $Corpus
if ($LASTEXITCODE -ne 0) { throw 'Preparation refused; preserve its evidence' }
& $Python -B -m app.demo_corpus verify --source $Corpus --expected-id $Id
if ($LASTEXITCODE -ne 0) { throw 'Verification refused; do not serve' }
$env:QUANTLAB_SERVING_MODE = 'read_only_demo'
$env:QUANTLAB_DEMO_CORPUS = $Corpus
$env:QUANTLAB_DEMO_CORPUS_ID = $Id
$env:QUANTLAB_DEMO_HOSTS = '127.0.0.1,localhost'
& $Python -m uvicorn app.serving:create_app --factory --host 127.0.0.1 --port 8780 --workers 1 --no-access-log
```

No HTTP preparation/reset endpoint exists. Preparation fully verifies the
actual database and explanation against candidate manifest bytes before
exclusively publishing corpus.json. Complete manifest publication defines
completion; an interruption before it retains owned non-serving database
evidence, and a missing/invalid manifest cannot become ready. A completed corpus
is verified against its configured ID; an incompatible schema refuses rather
than migrating during startup. This is not an atomic hostile-writer defense.

## Offline Backup, Restore and Migration

For a STOPPED prepared corpus with supported rollback storage and no sidecars:

```powershell
& $Python -B -m app.demo_corpus copy-stopped --source $Corpus --destination (Join-Path $Root 'backup-v1') --expected-id $Id --stopped
& $Python -B -m app.demo_corpus copy-stopped --source (Join-Path $Root 'backup-v1') --destination (Join-Path $Root 'restored-v1') --expected-id $Id --stopped
& $Python -B -m app.demo_corpus verify --source (Join-Path $Root 'restored-v1') --expected-id $Id
```

Each destination is exclusive/new; collisions refuse without overwrite.
The stopped flag is an operator attestation, not detection of another process.
Bounded main-file/manifest acquisition is checked before/after copying and the
destination is fully verified against unpublished candidate bytes before its
normal manifest is exclusively published. Interrupted copies are retained,
not cleaned/repaired; a failure before complete publication cannot be ready.
Never copy only a live WAL main file or delete/checkpoint sidecars to make it
pass. General live-user-DB backup, concurrent writers, online migration and
disaster recovery are unimplemented. Future schema upgrades require an offline
new owned copy or newly prepared corpus, explicit compatibility verification and
rollback to the preserved prior version; the read-only server never migrates.

## Frontend and Provider Governance

The existing page waits for a fresh no-store capability response before mounting
ordinary research workspaces. Missing/malformed/unavailable capabilities fail
closed with retry; they are not cached in localStorage as permission. A paired
backend with this contract is required, including for local mode. Backend-offline
initial load therefore locks workspaces rather than assuming a writable server.
Once negotiated, mode is fixed for that page lifecycle; restart/reload on operator
mode changes, not hot switching or silently reinterpreting existing form data.
Demo list/detail/explanation reads send X-QuantLab-Expected-Corpus with the full
negotiated ID. A different demo corpus refuses with 409 before dispatch; the
ordinary app also refuses this header before saved-data handlers can run.
Duplicate/mismatched values refuse. This is a restrictive precondition, NOT
authentication, permission, or HTTP mode/corpus selection. Unconditional public
demo reads remain possible. Reload after an operator restart/version change;
an old demo notice cannot silently accompany fresh ordinary saved user data.
Existing user settings are not overwritten. Direct query/hash navigation cannot
mount the ordinary research page in demo mode. Disabled workspace/delete controls
and absent save/replay actions are UX only; the backend enforces the boundary.

Optional NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE (`local` or `read_only_demo`) is a
BUILD-TIME mismatch check; invalid/mismatched configuration visibly locks the UI.
Unset means negotiate either valid backend mode, not assume local on failure.
Explanation JSON and local Markdown/print are public-content client exports;
Save Report is disabled. No report persistence or new research is triggered.
Supported views use system/local font fallbacks; Google font requests were
removed. No demo view uses Globe images, embeds, external APIs or telemetry.
This is application-level no-provider behavior, not an implemented network egress
firewall or confidentiality boundary. All served content is intentionally public.

## Implemented Local Controls

- Exact backend host allowlist (localhost/127.0.0.1 by default); at most 8 explicit
  hosts and origins, no wildcard. Optional approved Origin values are exact
  request checks, not CORS authentication. X-Forwarded-For is ignored.
- Canonical paths <=160 bytes/chars, query <=256 bytes, <=100 headers/8192 bytes.
  Disallowed routes do not consume request bodies. Approved GETs reject declared
  bodies/transfer encoding and inspect at most one ASGI frame, refusing any bytes
  or continuation without accumulating/parsing uploads, even if length claimed 0.
  One-second initial-frame deadline; transport allocation/connection limits remain
  reverse-proxy/server responsibilities.
- Process-local token bucket: burst 60, refill 1 request/second using monotonic
  time, at most 2 admitted requests per event loop. Approved routes share one
  bounded bucket, no identity dictionary; 429 with Retry-After: 1. Slots release
  on success/failure/cancellation; no per-user fairness or distributed/DDoS claim.
  Timeouts/cancellation do not prove synchronous worker computation was cancelled.
- No-store, nosniff, no-referrer and JSON-only backend CSP on responses/refusals;
  safe fixed errors, no echoed query/body/path/environment/traceback details.
  The backend CSP is NOT a tested CSP for the Next HTML application.
- Standard local logging emits fixed policy, route pattern and status for admitted
  requests, not submitted paths, queries, headers, tokens or bodies. No collector,
  telemetry SDK, per-user tracking, structured-log formatter or alert service.

Those are application log records, emitted when the operator enables INFO.
Disable Uvicorn raw access logging as in the command above: its default access
logger can otherwise log arbitrary submitted URLs/queries before/after refusal.
Future proxy/ingress logs also require explicit redaction or disabling; the app
does not rewrite global logging state shared with normal-mode instances. This
operational boundary must be verified in the later running-server/container gate.

## Proposed Hosting Shape and Unbuilt Requirements

One concrete future topology: browser -> same-origin HTTPS reverse proxy -> Next
frontend and private backend, with one versioned public corpus mounted read-only
at a fixed backend path. Backend has no public port. Operator owns image/corpus
versions, ingress trust and restart/replacement. TLS certificates/domains and all
cloud resources remain unprovisioned. CORS is not access control; no auth/accounts.

The existing Compose/Dockerfiles remain ORDINARY LOCAL DEVELOPMENT configuration:
backend port 8000 and frontend 3000 have no explicit loopback binding, Dockerfiles
declare no non-root USER, and there are
no enforced read-only root/corpus or resource limits. Do not expose them as the
hardened demo. No Compose override/profile is supplied that could accidentally
inherit those ports or writable mounts. No Docker builds/servers ran here.

Declared context exclusions cover backend developer env patterns, data/,
SQLite/sidecar/log patterns and common key directories; frontend env variants
are excluded except .env.example. Static tests check specified rule membership,
not all Docker pattern matching, arbitrary private files or resulting image layers.
They are not an executed Docker context/image inspection
or a replacement for secret scanning and deployment-runtime verification.

Before hosting, implement and independently verify non-root UID/GID, dropped
capabilities, no-new-privileges, read-only root/corpus, only bounded tmpfs /tmp,
loopback-only local frontend entrypoint, backend/private network, bounded CPU,
memory, process/file-descriptor/connection/header/body budgets and network egress
denial. Start with one worker; size limits with measurements, not a certification.
Do not mount checkout/home/socket/active data or import a developer .env wholesale.
Use an image-available stdlib HTTP health probe; keep liveness/readiness separate.

BACKEND_URL rewrites are baked into the Next build. A future user build must
inspect .next/routes-manifest.json for the intended private backend destination;
runtime environment alone cannot fix an old build. No production build or
container-runtime compatibility is claimed. Establish compatible Next security
headers/CSP, HTTPS termination, trusted proxy handling and cookies if ever needed;
do not apply the backend's JSON-only CSP to Next HTML without testing it.

Operator monitoring plan: bounded rotating local structured logs, /health and
/ready probes with corpus/policy IDs, startup/readiness/admission failure alerts,
retention/redaction review and restore drills on owned copies. Define access and
disk budgets before enabling logs; no external telemetry by default. Secret plan:
no provider secrets needed/accepted by demo paths; never bake credentials into
images, public NEXT_PUBLIC variables, corpus metadata or logs. Future secrets
must be narrowly injected outside source and audited separately. Ordinary provider
enable flags do not authorize any demo request. Future abuse controls belong at
ingress: global connection/rate/response budgets and authenticated operator changes,
not an invented public reset or per-user quota. Patch/support reviews, image
digests, exact-commit CI, backup/restore drills and deployment acceptance remain
operator gates, not proof supplied by old audits or this plan.

## Verification Gates

See [independent review](PHASE_70_REVIEW.md) for seven corrected defects,
219 focused backend passes/zero skips, 283 frontend passes, exact source
identities, retained failures and the REVIEW inventory. Historical
[implementation evidence](PHASE_70_IMPLEMENTATION.md) remains separate.
Exact-review-commit Python 3.11 whole-tree CI, user production build/proxy-manifest
check, one prepared-corpus browser scenario and later hardened-container runtime
checks remain separate gates. Phase 69's five physical-link cases were not rerun;
new Phase 70 corpus-link and storage-operation checks cover changed dependencies.

The new `frontend/e2e/read-only-demo.spec.ts` is for later user execution against
already-running loopback services. Prepare the corpus BEFORE serving; configure
E2E_READ_ONLY_DEMO_CORPUS_ID and E2E_READ_ONLY_DEMO_BACKEND_URL plus E2E_BASE_URL.
It verifies direct/proxy mode/readiness/identity, mutation/provider refusals, real
browse/detail/pinned download, no automatic mutation/external browser requests and
bounded viewports. It never calls an HTTP seed/reset or the old writable harness.
Discovery is not browser execution. Nothing here authorizes hosting or Phase 71.
