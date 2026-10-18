# Phase 70 Independent Adversarial Review

Date: 2026-10-18. VERSION remains `4.88.0-dev`.

## Verdict and exact target

**Safe to keep: YES for the bounded local read-only synthetic demo and hosting
plan. Ready for a later user review commit: YES.** Seven confirmed defects were
corrected and the affected local checks passed. No unresolved pre-commit defect
was identified within this review scope. This permits review of these pending
changes; it does not accept public hosting or close the later runtime gates.

The review began on attached, clean `main`: zero staged paths, zero unstaged
tracked paths and zero nonignored untracked paths. Target verification matched:

- Implementation: `8860ce7bdfb20367debdaf9e36b9ea3900dea0f9`.
- Subject: `Add read only hosted demo deployment hardening plan v1`.
- Implementation tree: `614027cba879ec6abfda3fc1ef48ceab411973b6`.
- Exactly one parent: `1062ec48b4128af867ab5a3329951511ebff285c`.
- Existing annotated tag `v4.87.0-deterministic-evidence-grounded-research-explainer-v1`
  peels to that parent, whose tree is `3a06cbef017e1828781d2e6861c17eecf4afd014`.
- VERSION: `4.88.0-dev`, unchanged throughout review.

Applicable `AGENTS.md` and `CLAUDE.md`, the complete implementation diff,
implementation report, current runbook/deployment guidance, shared startup/DB/
saved/replay/explainer/provider contracts, runner/conftest guards, frontend and
concrete container configuration were inspected. No branch switch or Git
mutation was needed. The old implementation verdict was not used as proof of
correctness. Initial raw index: 126906 bytes, SHA-256
`c98e483d7b6ed2faaac868232cba02ab787da166bb24aea95dea65bb8d95a73e`.

## Confirmed findings, fixes and independent regressions

Severity is relative to the delivered local feature. No public deployment or
hostile-native-code security boundary is asserted.

| Severity | Confirmed before-fix defect | Correction and source | Independent regression |
| --- | --- | --- | --- |
| P2 | An ordinary `app.main` imported under local configuration could remain cached while explicit demo/invalid configuration appeared before lifespan; the old import-only guard no longer preceded writable initialization in that sequence. | `backend/app/main.py:388-393` rechecks `guard_local_entrypoint()` immediately before `init_db()`. | Three cached-import refusal configurations prove no initialization, plus two ordinary lifespan controls prove one initialization. |
| P2 | Corpus saved JSON reached the legacy full decoder before structural preflight. A byte cap alone did not bound nesting/member allocation, and duplicate members could be lost during projection. | `backend/app/demo_corpus.py:67-81,89-95` preflights the manifest and all four stored JSON fields before full strict decoding; requires the expected container shapes. | Four all-fields-before-any-decoder sentinels, four duplicate-member cases and a manifest-depth no-effect case. |
| P2 | Required SQLite names could be views queried by `count(*)` before being classified as real tables; `SELECT *` also acquired unnecessary extension columns. | `backend/app/demo_corpus.py:116-135` requires the real tables/columns first and selects the explicit 16 required columns. | Two owned-view SQL sentinels prove rejection before the view expression can execute. |
| P2 | `prepare`/`copy_stopped` published ordinary `corpus.json` before their final complete verification. A final verification failure could leave a serving manifest behind. | `backend/app/demo_corpus.py:170-225` validates unpublished candidate manifest bytes against the actual destination DB and explanation, then publishes the manifest exclusively. | Real preparation/copy failures at the destination explanation-validation seam leave owned DB evidence without a normal manifest; public verification refuses. Interrupted publication and a real complete round trip are also covered. |
| P3 | New corpus path refusal checked symlink/reparse paths but omitted regular-file hardlinks despite the documented linked-path restriction. | `backend/app/demo_corpus.py:27-37` requires regular-file link count one. | Actual owned hardlinks to `demo.db` and `corpus.json` refuse before any SQLite connection or opening the linked file, with source/alias bytes preserved. The manifest case first reads/checks the ordinary DB. These are new Phase 70 cases. |
| P3 | A supplied clock moving backward advanced the bucket's `last` backward; returning to the old time could refill tokens again. | `backend/app/read_only_demo.py:64-70` retains the clock high-water mark. | Controlled 10 -> 9 -> 10 sequence does not mint a token. The default clock is monotonic; this is not a demonstrated real-clock exploit. |
| P3 | One `TimeoutError` handler covered both initial-frame waiting and the inner dispatched application, misreporting an inner timeout as 408 before dispatch. | `backend/app/read_only_demo.py:148-169` limits the 408 handler to the initial receive deadline; a pre-response dispatched error receives the fixed 503. | Separate controlled initial-frame and dispatched-timeout cases, permit-release assertions and safe-error/log assertions. The initial-frame test injects the timeout at the receive seam; it is not a measured one-second transport test. |

The new backend modules contain **51 cases: 31 gate/startup/admission and 20
corpus cases**. There are six new frontend cases. They are included in the final
219/283 counts below, not additional passes to add to those totals. No strategy,
engine, metric, dependency, shared runner/conftest or historical-report code was
changed by this review. No production frontend defect was confirmed; frontend
changes are tests and the later acceptance spec.

## Six-route enforcement, startup and corpus identity

The actual factory is `app.serving:create_app --factory`. Absent
`QUANTLAB_SERVING_MODE` selects ordinary local mode; only exact `local` or
`read_only_demo` is accepted. Empty/unknown/case/whitespace variants refuse.
Demo variables under local mode and unknown `QUANTLAB_DEMO_` keys refuse. The
wrong ordinary entrypoint guards both import and, after this fix, lifespan.
Request query/header/cookie values cannot turn off the selected server mode.

`read_only_demo_v1` has these exact public combinations:

| Method/path | Capability and storage behavior |
| --- | --- |
| GET `/health` | Process liveness only; no corpus read or initialization. |
| GET `/ready` | Compare bounded current corpus observation with the approved startup observation; ready or fixed 503. |
| GET `/capabilities` | Same observation check, then closed `serving_capabilities_v1` demo policy/corpus contract. |
| GET `/saved-backtests` | Same observation check, one approved public summary cached at startup. |
| GET `/saved-backtests/1` | Same observation check, the approved cached saved result. |
| GET `/research-explainer/saved-backtests/1` | Same observation check, the cached verified stored explanation; optional exact `expected=<64 lowercase hex>` fingerprint precondition. |

The actual last two registered patterns contain `{saved_id}`; the outer ASGI
matcher admits only the exact string `1`. It does not authorize arbitrary GETs
or prefixes. The actual route inventory test inspects the constructed app,
adds an otherwise dangerous new route with a dependency sentinel and compares
the ordinary registered surface against the separate demo app.

All other methods/routes, HEAD/OPTIONS, docs/OpenAPI/debug, extra segments,
trailing slashes, encoded/raw-decoded mismatches, backslashes, non-ASCII paths,
nonempty `root_path` and unknown/new routes refuse before endpoint dependencies,
uploads or body parsing. Slash redirects are disabled. WebSockets close with
1008 before accept. No ordinary labs, CRUD, seed/reset/import/migration or
provider router is registered in the demo app. Controlled denied-dispatch and
receive sentinels supplement the actual route/provider integration tests.

Demo startup receives an explicit absolute operator corpus path and full ID.
Missing/corrupt/incompatible/substituted corpus refuses without default DB
fallback, mkdir, seeding, migration, repair or provider work. Verification uses
explicit SQLite `mode=ro`, `query_only`, a read transaction and the preserved
rollback-header/no WAL/journal/SHM restriction. It does not use `immutable=1`,
checkpoint or remove sidecars. Existing helper aliases were inspected; the
implementation's explicit path arguments do not alter the ordinary global DB
override. Ordinary startup, simultaneous local/demo storage isolation and stale
demo-to-local requests have actual integration coverage. Saved API tests alone
do not enter lifespan; startup conclusions also rely on the demo integration
and new explicit lifespan controls.

Manifest `public_sma_corpus_v1` binds DB bytes, public material, allowed ID,
schema, timestamps and synthetic provenance. Verification checks bounded real
table inventory, no other populated user tables, fixed labels/notes/parameters,
exact public equity/trade shapes, stored-result material and the existing
explainer validation. It reads only the required saved columns. The preparation
test independently checks all 180 actual input prices against code-owned
synthetic closes, `100 + i*0.12 + 8*sin(i/9)`, the first date 2000-01-03,
SMA 5/20, capital 100000, cost 10 bps and the stored 252-period parameter.
Preparation source constructs business-day indices; the test does not assert
every date in that index.
Preparation legitimately computes that result before serving; verification and
HTTP reads cannot invoke those setup/default-storage helpers in the test.

The digest is consistency metadata, not authentication, a signature, historical
market provenance or proof against a coherent privileged rewrite. The public
projection and fixed synthetic preparation are separate privacy controls. No
active-user DB clone, user-note import or private-directory scan is provided.

Frontend data requests carry the negotiated full
`X-QuantLab-Expected-Corpus`. Stale/duplicate/malformed values refuse before
dispatch; the ordinary app refuses any such header before saved handlers.
Unconditional public demo reads remain possible: this is a restrictive
precondition, not visitor authorization or mode selection. Capability/readiness
and the other data reads re-observe DB/manifest bytes. Changed/deleted/renamed
or sidecar-bearing sources refuse. Startup also compares across verification.
These are observed-state checks; path replacement/ABA/native races are not an
atomic filesystem sandbox. No hot replacement of an in-use corpus is supported.

## Offline operations, provider/privacy and admission conclusions

Owned real tests exercise prepare -> verify -> stopped backup -> stopped restore
-> read-only acquisition. Source, backup and restored DB/manifest bytes agree;
explicit RO connection spies and forbidden default-storage/computation seams
separate setup effects from serving. Existing destination collisions refuse
without overwrite. Directory links, new regular-file hardlinks, missing renamed
DB, closed WAL and live rollback-journal sources are exercised on test-owned
paths. Unsupported copies refuse before destination creation/connection.

Complete manifest publication is the completion boundary. Failures before it
retain a non-serving owned partial directory/DB for inspection; no cleanup,
reset or overwrite is performed. Interruption after a complete valid manifest
has been published is not claimed to erase that completed corpus. `--stopped`
is an operator attestation, not process detection. Backup/restore requires
supported stopped storage and a new destination; general online backup,
concurrent writers, migrations and disaster recovery are not implemented.

Allowed-route provider spies cover the actual demo startup/read path with
ordinary provider-enable flags present. No real network request is made; no
provider route/call is authorized by those flags. Supported frontend views use
local/system fonts and no supported-path remote provider image/embed/telemetry
dependency was found by static inspection. This is application behavior, not
an executed browser network capture or network egress firewall.

The gate checks canonical path <=160, query <=256 bytes, <=100 headers/8192
header bytes, exact host/origin lists, duplicate/missing/malformed host/body
declarations and prohibited query cardinality before expensive dispatch.
Missing content length is allowed only with an empty single initial ASGI frame;
declared bodies, transfer encoding, bytes or continuation refuse. At most one
frame is inspected without upload accumulation. Initial receive has a one-second
deadline. Transport-level allocation/connection budgets remain external.

Admission is one bounded process/event-loop token bucket: burst 60, refill one
per second, two admitted slots. It ignores forwarded client identity and keeps
no per-client dictionary. Deterministic events/queues/futures and clocks test
concurrency refusal, initial-receive cancellation, exceptions and slot release,
including the corrected high-water and timeout branches. No sleeps, per-user
quota, distributed limit, physical worker cancellation or DDoS guarantee is
claimed. Deployment v1 is one process/event loop/worker; ordinary global DB
semantics and concurrent operator preparation are not a supported multi-app
deployment topology.

Responses/refusals get no-store/nosniff/no-referrer and JSON-only backend CSP;
fixed errors do not echo private exception/query/path/env text. Application log
records use a fixed policy, approved route pattern and status. Operators must
disable Uvicorn raw access logs as in the runbook and handle future ingress log
redaction separately. Neither global logger rewriting nor a collector/alert
service was added. The backend CSP is not accepted as a Next HTML CSP.

## UI and browser-spec conclusions

`ServingGate` fetches fresh no-store capabilities before mounting ordinary work;
malformed/unavailable contracts fail closed with retry, not cached writable
permission. Mode stays fixed for that page lifecycle. The optional
`NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE` is a build-time mismatch check. Read-only
saved/detail/explanation clients require a valid corpus pin. Unsupported labs and
run/save/delete/import/replay/report persistence cannot be reached by demo
navigation; the backend remains the authority.

Six new controlled component cases cover stale local permission, an old normal
handshake finishing after a new demo gate, edited ordinary child/settings
preservation, disabled navigation/history without hidden write requests, same-ID
new-corpus detail races and explanation races with exact displayed-response
export. Ordinary form preservation uses an edited child control; it is not
acceptance of every ordinary research form. No live backend restart was run.
Existing reset/cancellation/keying protects detail/explanation ticket changes;
local exports do not call Save Report. Synthetic/read-only notices and unavailable
states remain explicit. Browser keyboard, layout and download behavior remain
runtime-pending.

The strengthened `frontend/e2e/read-only-demo.spec.ts` requires user-prepared
synthetic corpus and already-running clean loopback backend/frontend origins,
configured full corpus ID and positive direct/proxy capabilities plus readiness.
It never uses the old mutation-enabled seed harness, assumes no old port/token/
Build ID, and has no service-start hook. It covers browse -> View -> Explain ->
source inspection -> fingerprint check -> exact JSON download, disabled controls,
direct method/provider/wrong-pin refusals, pinned browser data requests, no
unexpected external/API fallback, navigation/history and widths 1440/1024/768.
Selectors were checked against source without force clicks, arbitrary first(),
sleeps, increased timeouts or retries. Discovery cannot validate actual selectors,
keyboard interaction, downloads or rendered layouts. These widths do not imply
phone-layout or accessibility acceptance.

The spec compares exact public response projections before/after refusals and
checks corpus readiness/identity. It does not hash the physical DB/manifest or
inspect sidecars. That byte-preservation evidence belongs to the owned backend
tests and still needs runtime corroboration in later owned acceptance. Replacing
a running server during browser execution remains untested; controlled unit/API
stale-response checks are distinct evidence.

## Container/configuration classification and later owned acceptance

No Docker/Compose command, container, production build, service or image
inspection ran. Static source inspection found one concrete Compose file,
`docker-compose.yml`, and no hardened override/profile. There is consequently
no hidden merged demo profile to accept.

| Requirement | Actual delivered state and classification |
| --- | --- |
| Strict demo factory, six-route policy, corpus/pin checks, bounded gate, existing UI | Implemented and locally tested; running-server/container integration pending. |
| `.dockerignore`/`.env.example` guidance | Implemented; tests assert named ignore-rule membership. Actual context matching/image layers and secret exclusion remain runtime-pending, not a complete secret scan. |
| Effective entrypoint and exposed ports | Existing development Compose publishes `8000:8000` and `3000:3000` without explicit host-IP/loopback binding. Backend Dockerfile runs ordinary `app.main:app`; it is not the demo factory. No hardened profile implemented. |
| Proxy/build consistency | Existing frontend Docker build takes `BACKEND_URL=http://backend:8000` from Compose; `next.config.js` bakes `/api/:path*` rewrites. Runtime env alone cannot repair an old build. Exact user build/routes-manifest inspection pending. |
| Non-root, capabilities, filesystem/corpus mounts | Dockerfiles declare no `USER`; no actual image UID was inspected. Compose supplies no `read_only`, cap-drop, no-new-privileges, read-only corpus mount or bounded tmpfs. Documented plan, not implemented enforcement. |
| Resource/process/connection/descriptor budgets | Application request/admission bounds tested; container/server/ingress resource settings not implemented or measured. |
| Health, host and proxy trust | App liveness/readiness and exact host/origin checks tested. Image-available stdlib health probe, private network/proxy trust, raw-access-log behavior and running health configuration pending. No assumptions about uninspected image defaults. |
| Network privacy, TLS, domains, secrets, monitoring | No application provider path for demo; egress denial, HTTPS/certificates, ingress logging, secret injection, rotating logs/alerts remain documented plans. No cloud resources provisioned. |
| Auth/accounts/multi-user isolation and public-host certification | Not implemented and outside this feature. No new generic audit or security-certification claim. |

The concrete images use mutable `python:3.11-slim` and `node:24-alpine` bases;
this review did not pull them or establish their current contents/support/security.
The backend Dockerfile's pip installation and frontend npm/build steps were
inspected, not executed. Ignore rules do not prove that arbitrary private files
or all nested paths cannot enter a build. Current docs now state that limit.

The smallest meaningful **later user-owned hardened-container acceptance** is:

1. On a new disposable owned corpus/storage root, retain exact review commit/tree,
   effective Compose/config output and image IDs/digests, runtime versions,
   prepared corpus ID plus DB/manifest hashes. Implement the hardened topology
   first; do not expose the current development profile.
2. Inspect actual running command/factory, mode/pin/mount path, one worker,
   approved host, frontend build ID and `.next/routes-manifest.json` destination.
   Capture direct and proxy `/capabilities`/`ready` JSON showing the same mode,
   policy and corpus ID. Health must use an actually available stdlib tool.
3. Capture running UID/GID, dropped capabilities/security options, read-only
   root/corpus mount inspection and a denied write probe on an expendable owned
   location; record only bounded writable temp mounts and no checkout/home/socket/
   active-data mounts. Retain effective memory/CPU/PID and server/ingress limits.
4. Inspect actual published addresses/ports/network: only the intended local
   frontend loopback entry, backend private with no accidental ordinary-profile
   port. Record the intended proxy/host and disabled/redacted raw access logging.
   Runtime network/secret claims require direct supporting inspection, not YAML.
5. Exercise one supported list/detail/explanation read and one denied mutation
   plus provider/unknown-path refusal, without provider network access or handler
   effects. Retain exact status/response output and before/after DB/manifest hashes
   and sidecar inventory. Then execute the single prepared-corpus browser spec
   against this positively identified product mode. Keep earlier setup failures.

A successful image build alone cannot close this gate. This list is a later
acceptance definition, not an executed check or authorization to implement/deploy
it during this review.

## New protected backend evidence

Both new runs used existing `C:\quantlab\.venv\Scripts\python.exe`, **Python
3.13.5 (Anaconda/MSVC AMD64), Windows-11-10.0.26100-SP0, pytest 9.0.3, one worker**.
Runner, conftest, SQLite URI/link/owned-path guards were inspected and unchanged.
All fixture DB work was isolated; no active/default user database was opened
through SQLite or queried.
The runner's before/after file observations are bounded protection evidence,
not a complete filesystem/security audit.

Commands from `C:\quantlab`:

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused --test backend/tests/test_read_only_demo_review_gate.py --test backend/tests/test_demo_corpus_review.py
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused --test backend/tests/test_read_only_demo.py --test backend/tests/test_read_only_demo_review_gate.py --test backend/tests/test_demo_corpus_review.py --test backend/tests/test_saved_backtests.py --test backend/tests/test_run_replay.py --test backend/tests/test_research_explainer_storage.py --test backend/tests/test_research_explainer_api_review.py
```

| New run | Defect regressions | Final affected scope |
| --- | --- | --- |
| Evidence directory under `C:\Users\jimli\AppData\Local\Temp` | `quantlab-backend-focused-_m9k9og4` | `quantlab-backend-focused-gg_t3m4h` |
| Selected / passed / deselected | 51 / 51 / 0 | 219 / 219 / 0 |
| Skips / failures / errors | 0 / 0 / 0 | 0 / 0 / 0 |
| Reported pytest duration | 40.05s | 357.32s (0:05:57) |
| Machine pytest wall seconds | 40.17923660000088 | 357.43019600003026 |
| Child process wall seconds | 42.56338870001491 | 360.6718148999498 |
| Outer wall seconds | 61.87698810000438 | 380.04956230003154 |
| Snapshot setup seconds | 4.375147200014908 | 3.9811682000290602 |
| pytest / child process / outer exits | 0 / 0 / 0 | 0 / 0 / 0 |
| JUnit cases / failures / errors / skips; time | 51 / 0 / 0 / 0; 40.042s | 219 / 0 / 0 / 0; 357.273s |
| Worktree / snapshot / observed active DB unchanged | true / true / true | true / true / true |
| Child evidence complete; SQLite violations | true; `[]` | true; `[]` |

Final actual collected files/counts: `test_read_only_demo.py` 59,
`test_read_only_demo_review_gate.py` 31, `test_demo_corpus_review.py` 20,
`test_saved_backtests.py` 31, `test_run_replay.py` 43,
`test_research_explainer_storage.py` 28 and
`test_research_explainer_api_review.py` 7. Collection was 219/219 selected,
zero deselected, 4.155065700004343s startup/collection. All 219 setup, call and
teardown outcomes passed (657 phase records); no skip reason exists. Exact node
IDs, individual durations and outcomes are retained in `collection.json`,
`phases.jsonl`, `junit.xml`, `pytest-result.json` and `pytest.log`; process/outer
identities are separately in `runner-result.json`, with `runtime.json` and
`run-config.json`. No node was dropped to obtain a pass.

Both runs have the **same raw source manifest SHA-256**:
`76a634a50d2107d6b42ffd2c6e6239b9d968a986adb9b50bdc88f8f7a9dcbd2d`.
Each snapshots 1192 tracked/nonignored source paths, `missing=[]`, `omitted=[]`,
at implementation HEAD above plus exactly seven pending source/test/spec paths.
All 1192 current raw hashes matched the final snapshot immediately after the
runner completed, before documentation finalization. Source was frozen during
both runs. These are focused snapshots, not a final whole-tree backend pass.

The final scope rechecks the original affected 168 targets plus the new 51.
It covers actual startup/routes/provider refusals and shared saved/replay/
explainer consumers. Unchanged Globe 82 and replay identity/persistence 83 were
not rerun merely to repeat the inherited 357. Phase 69's five named Linux
physical-link cases were not repeated; new Phase 70 hardlink and copy-storage
tests are justified by the changed corpus path/operations dependency.

### Tested raw review source identities

These seven pending executable/test/spec files remain byte-identical after
verification. Hashes are raw working-file SHA-256, including line endings.

| Path | SHA-256 |
| --- | --- |
| `backend/app/demo_corpus.py` | `7e9cb2f4267cd54bd2aba0bb26eb601be4654789c6b92d94b98dcdfca030dbb3` |
| `backend/app/main.py` | `b5e60e1f08c3ab59898fb90a325eeeffd427e556a87b8210066c4252189f88e8` |
| `backend/app/read_only_demo.py` | `a8b8b6b54373f468c005b2f0371a7a0fe4a47468c6013f7d789319bdfb7e5e05` |
| `backend/tests/test_demo_corpus_review.py` | `a84769e8ea3b227dcd095fcf1932dcb90d389809c2c58fa6f9bd56db875e9ba7` |
| `backend/tests/test_read_only_demo_review_gate.py` | `2dcdb7daea4d2a9a65b4aa44111264ca6bd60e35c9269e54a31cf8e3c42f819c` |
| `frontend/e2e/read-only-demo.spec.ts` | `b660d06634bcb9f5de61454a2977def168480eabe39a4c6c12899611ad2c62de` |
| `frontend/src/components/ReadOnlyDemo.review.test.tsx` | `76d56530eaa05b6bbb7186f9969556fe033a6008542da28cfb29328f972a3acf` |

## New frontend evidence and preserved setup failure

Fresh read-only runtime discovery selected existing Node **24.21.0** at
`C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\a5a02988362ca169\bin\node.exe`;
actual npm **11.17.0** CLI is
`C:\Users\jimli\AppData\Roaming\npm\node_modules\npm\bin\npm-cli.js`.
System npm 11.12.1 was separately observed, not substituted. A guessed bundled
npm location returned MODULE_NOT_FOUND during discovery; no tests ran in that
probe. No runtime/package was installed or replaced. Actual package metadata:
Next 15.5.25, React 19.2.8, Vitest 4.1.11, TypeScript 5.9.3, Playwright 1.61.1.

Commands use that Node executable, cwd `C:\quantlab\frontend`:

```text
node node_modules/vitest/vitest.mjs run --reporter=json --outputFile=<evidence>/frontend-review-unit-approved.json
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/@playwright/test/cli.js test e2e/read-only-demo.spec.ts --list --reporter=json
node node_modules/@playwright/test/cli.js test --list --reporter=json
```

Evidence root:
`C:\Users\jimli\AppData\Local\Temp\quantlab-phase70-review-f6508c5ca83a4c0c8c2e1c5c56012e56`.

| Check | Actual result | Process exit | Host seconds |
| --- | --- | --- | --- |
| Initial units | esbuild `spawn EPERM` while loading Vitest configuration, before collection; no unit JSON/count | 1 | 0.3973414 |
| Same frozen source, permitted-process unit retry | 283 passed / 28 files; zero failures/pending | 0 | 6.6690544 |
| TypeScript, incremental output disabled | Passed, no diagnostics | 0 | 14.8903506 |
| Focused Playwright list | 1 scenario / 1 file discovered; zero runtime results | 0 | 0.6380377 |
| Overall Playwright list | 280 scenarios / 24 files discovered; zero runtime results | 0 | 0.7151966 |

The initial EPERM remains in `frontend-review-unit.log` and its execution JSON;
it was an environment startup failure, not a failed assertion silently removed.
Final raw unit node outcomes/durations are in `frontend-review-unit-approved.json`;
the six new cases all passed. Before/after manifests cover 289 frontend source,
config and harness paths with identical membership, bytes and hashes. No unit
source changed between failure and retry. The Playwright JSON `skipped` totals
1/280 are discovery placeholders: every runtime results array is empty, with
zero browser cases executed. They are not executed skips or passes.

## Inherited implementation evidence reconciliation

The unchanged [implementation report](PHASE_70_IMPLEMENTATION.md) and actual
retained records were read. These results belong to earlier source snapshots;
none is added to the new final count or represented as final-tree verification.
Backend runtime records identify the same Windows/Python 3.13.5 environment.

| Inherited backend snapshot | Actual selected/passed; skips/failures/errors | Reported pytest; machine pytest / child / outer wall seconds | pytest / child / outer exits | Manifest SHA-256 |
| --- | --- | --- | --- | --- |
| `quantlab-backend-focused-ftjs5eej` | 47/47; 0/0/0, initial demo module | 109.50s; 110.82062079999014 / 114.0883904999937 / 132.30921609999496 | 0/0/0 | `c92199d7a9bc48342ca509ccd22560d5b00283ff8c1e3363f2dcbc5e82f73b14` |
| `quantlab-backend-focused-etielic7` | 357/357; 0/0/0, broader snapshot | 271.60s; 271.83310070002335 / 274.15498309998657 / 282.7795238000108 | 0/0/0 | `0323f59cf780a275920c12a43e6a9a67a6ae113e1ebe98a9d9cc614a50ada5e1` |
| `quantlab-backend-focused-_kdc1ur0` | 168/168; 0/0/0, final affected implementation snapshot | 182.43s; 182.7149152000202 / 184.93873870000243 / 196.33982219998143 | 0/0/0 | `3b19d826ddac8eba37ac2f8dde49f48de81e2b41758ec3a07479499576ec0bc8` |

These directories are under `C:\Users\jimli\AppData\Local\Temp`. Each recorded
child evidence complete and snapshot/worktree/observed-active-DB unchanged.
The broader run's actual scope was demo57, saved31, replay43, replay identity50,
replay persistence33, explainer storage28, storage review26, explainer API7 and
Globe82. The final 168 was demo59 + saved31 + replay43 + storage28 + API7.
Those are separate runs, not 525 final passes. Commands used the protected
runner `--scope focused` with those explicit `backend/tests/test_*.py` targets;
actual argv is retained in each `run-config.json`/`runner-result.json`.

Actual broad-to-final manifest comparison found **17 changed paths**, not merely
the four backend paths, with no missing/omitted source paths:

```text
backend/app/main.py
backend/app/read_only_demo.py
backend/app/serving.py
backend/tests/test_read_only_demo.py
docs/PHASE_70_IMPLEMENTATION.md
docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md
frontend/e2e/read-only-demo.spec.ts
frontend/src/components/ReadOnlyDemo.tsx
frontend/src/components/ResearchExplanationPanel.test.tsx
frontend/src/components/ResearchExplanationPanel.tsx
frontend/src/components/SavedBacktestDetail.tsx
frontend/src/components/SavedBacktestsList.tsx
frontend/src/components/ServingGate.test.tsx
frontend/src/lib/api.ts
frontend/src/lib/researchExplainer.ts
frontend/src/lib/servingCapabilities.test.ts
frontend/src/lib/servingCapabilities.ts
```

The backend change in that interval added stale-demo corpus preconditions and
two demo cases. Final 168 rechecked the affected API/storage/replay/explainer
consumers after those changes; strategy/engine mathematics was unchanged.
Frontend corpus pinning and stale-client cases also changed, so the earlier
frontend runs must not be substituted for the final pinned implementation run.

Inherited frontend root `quantlab-phase70-1a14d149759` retains runtime, execution,
source, unit/discovery JSON and logs. Its final pinned source had frontend277/
27 files, units exit0 in 7.8134684s, TypeScript exit0 in 12.5808145s, focused
list1 exit0 in 0.4332485s and overall list280 exit0 in 0.4563919s, zero browser
execution. Earlier 273 units/27 files passed (34.2036893s, exit0); the initial
TypeScript run failed four Testing Library selector option diagnostics (exit2,
17.5515895s). A corrected earlier 274/27 unit run passed (7.0822465s, exit0),
TypeScript passed (15.2911857s), and a later spec-only checkpoint recorded
TypeScript 27.9971587s plus lists 0.8706103/0.9291939s, exits0. These precede
the final pinning snapshot and remain history, not extra current results.

The inherited backend setup attempt `quantlab-backend-focused-dfln8s76` failed
with temp evidence `PermissionError`, host exit1, before snapshot/test launch.
It has no pytest/child result to infer. The later approved 168 retained the same
source and completed. Read-only PowerShell inspection/quoting errors and this
review's first exact-span documentation guard failure were not test failures;
the documentation guard validated all edits before writing and changed no file.
Protected evidence initially required elevated read access; the denied read did
not change application state or rerun verification.

Inherited raw frontend hashes also require a checkout distinction. Ten of 19
recorded final frontend paths differed only by observed current CRLF conversion;
the browser spec was intentionally review-edited. `page.tsx` had mixed endings
in the actual old protected snapshot (2575 CRLF +46 LF) and now has 2621 CRLF.
Old raw SHA `3846706d9bcce3a1e2ebad170668462e8a8c249d3bebf554f0e9686be36f6cbe`
differs from current `85a1cc821b123a3d724d01b87d1466a92f62269dbcf27b5803bf17cc643b8336`.
Normalizing both strings only in memory produces exact text equality. This was
not silently presented as raw-byte identity, and no file was normalized by this
review. The fresh 1192/289-path raw manifests are the current verification basis.

## Unconfirmed risks and remaining gates

No further confirmed defect was found in the inspected bounded surface.
Unconfirmed/unsupported risks remain distinct from fixed defects: hostile native
path/ABA races and coherent privileged metadata rewrites, operator stopped-state
attestation, physical worker cancellation, multi-process/distributed abuse limits,
running proxy/header/log/egress enforcement, actual Next CSP and browser/runtime
layout/download behavior. Authentication, general online migration/backup,
production/trading/security certification and public hosting were not added.

Required later gates remain:

- **Exact-review-commit Python 3.11/Linux whole-tree CI**, with actual runtime,
  process exits, node outcomes and skip identities retained. It must include the
  new corpus hardlink cases, existing Phase 70 directory-link refusal, candidate
  publication failures, full synthetic copy/restore and shared startup/storage
  consumers. Local Windows hardlink/link passes do not establish Linux behavior.
  Valid earlier Phase 69 five-case Linux evidence remains inherited; no separate
  repetition was authorized merely for this phase. A skip is not a pass.
- **User production build** at the review source identity and inspection of the
  baked `.next/routes-manifest.json` private-backend rewrite, mode/pin environment
  and Build ID. No local production or Docker build ran.
- **One isolated prepared-corpus browser scenario**, positive direct/proxy product
  identity, retained runtime results/download/assertions, relevant owned corpus
  preservation. Discovery 1/280 is not execution.
- **Hardened-container runtime acceptance** defined above, after actual hardened
  configuration exists. Current development Docker/Compose does not satisfy it.

These later gates are not unresolved defects preventing this local review
commit. They prevent deployment/runtime acceptance claims. Historical audits or
successful earlier phase CI/build/browser checks do not close them.

## Exact implementation inventory verified at review entry

This committed implementation inventory is **39 paths: 27 modified /12 added**
relative to the single parent. It is historical scope, not the pending REVIEW
staging inventory below.

```text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M VERSION
M backend/.dockerignore
M backend/.env.example
M backend/app/db.py
A backend/app/demo_corpus.py
M backend/app/main.py
A backend/app/read_only_demo.py
M backend/app/research_explainer/service.py
M backend/app/saved_backtests.py
A backend/app/serving.py
A backend/tests/test_read_only_demo.py
M docs/DEPLOYMENT_READINESS.md
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/PHASE_70_IMPLEMENTATION.md
A docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md
M docs/VERSION_MANIFEST.md
M frontend/.dockerignore
M frontend/.env.example
A frontend/e2e/read-only-demo.spec.ts
M frontend/src/app/layout.tsx
M frontend/src/app/page.tsx
M frontend/src/components/AppShell.tsx
A frontend/src/components/ReadOnlyDemo.tsx
M frontend/src/components/ResearchExplanationPanel.test.tsx
M frontend/src/components/ResearchExplanationPanel.tsx
M frontend/src/components/SavedBacktestDetail.tsx
M frontend/src/components/SavedBacktestsList.tsx
A frontend/src/components/ServingGate.test.tsx
A frontend/src/components/ServingGate.tsx
M frontend/src/components/Sidebar.tsx
M frontend/src/components/TopBar.tsx
M frontend/src/lib/api.ts
M frontend/src/lib/researchExplainer.ts
A frontend/src/lib/servingCapabilities.test.ts
A frontend/src/lib/servingCapabilities.ts
```

## Exact pending REVIEW inventory and later USER-ONLY staging plan

**16 intended paths: 12 modified /4 new, all unstaged.** `A` below means the
intended added classification when later staged; those four paths are currently
nonignored untracked. This set includes this final report. It does not repeat
the committed 39-path implementation inventory.

```text
M CHANGELOG.md
M README.md
M STOP_POINT.md
M TASKS.md
M backend/app/demo_corpus.py
M backend/app/main.py
M backend/app/read_only_demo.py
A backend/tests/test_demo_corpus_review.py
A backend/tests/test_read_only_demo_review_gate.py
M docs/DEPLOYMENT_READINESS.md
M docs/FORWARD_ROADMAP_PHASES_63_70.md
A docs/PHASE_70_REVIEW.md
M docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md
M docs/VERSION_MANIFEST.md
M frontend/e2e/read-only-demo.spec.ts
A frontend/src/components/ReadOnlyDemo.review.test.tsx
```

The report and eight current-status/runbook documents were finalized **after
backend verification**. They are post-test prose, not newly tested executable
bytes. All seven tested pending source/test/spec hashes above remain unchanged.
Historical implementation/review reports, VERSION and frozen screenshots are
preserved. Current-document changes are bounded byte replacements preserving
other content and earlier line endings; no checkout normalization was performed.

Later, only after fresh user authorization and verification of branch/base,
exact pending membership/classifications and reviewed contents, the user may
stage these explicit literal paths. **This command was not executed here. Do
not execute the Markdown document as a script or use directory/blanket staging.**

```powershell
git --literal-pathspecs add -- CHANGELOG.md README.md STOP_POINT.md TASKS.md backend/app/demo_corpus.py backend/app/main.py backend/app/read_only_demo.py backend/tests/test_demo_corpus_review.py backend/tests/test_read_only_demo_review_gate.py docs/DEPLOYMENT_READINESS.md docs/FORWARD_ROADMAP_PHASES_63_70.md docs/PHASE_70_REVIEW.md docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md docs/VERSION_MANIFEST.md frontend/e2e/read-only-demo.spec.ts frontend/src/components/ReadOnlyDemo.review.test.tsx
```

Preserve unrelated staging; stop on an unexpected path/content/base. Later
staging must verify exact approved/staged membership, 16 paths/12 M/4 A,
`git diff --cached --check` including EOF, unchanged working-file bytes and no
remaining intended unstaged/untracked paths. Do not add files to reach a count.
No DB/sidecar, credential, log, runtime output, dependency/cache/build/browser
artifact or frozen screenshot belongs in this REVIEW inventory.

Expected later user-created review subject:
`Review read only hosted demo deployment hardening plan v1`.
Future user-controlled tag, not created here:
`v4.88.0-read-only-hosted-demo-deployment-hardening-plan-v1`.

## Final preservation and stop boundary

Final pending membership is exactly the 16-path REVIEW set; the index remains
empty and its raw hash/size match entry. The recorded 57 non-database protected
files (VERSION, tracked data placeholder, historical phase implementation/review
reports including Phase 70 implementation, and frozen screenshot trees) retain
their hashes/sizes. Active-file preservation comes only from the two protected
runner records; no new application DB audit or SQL access was performed.
Tracked diff whitespace exits 0. The four explicit new-file `--no-index --check`
comparisons exit 1 for new-file differences and emit only the existing Git
LF-to-CRLF warning, with no whitespace diagnostic; bytes were not normalized.
All 16 paths have one final line terminator and no excess blank EOF line.
No unintended
artifact/evidence/runtime path is in the pending set. Existing artifacts were
retained. Test evidence lives outside the repository at the named owned roots.

No staging, commit, push, tag, PR, workflow trigger, cloud provisioning,
deployment, authentication expansion, dependency/runtime installation, external
service, production/Docker build, browser execution or Phase 71 occurred.
No staged-tree identity is claimed because no staging was authorized. Stop at
this single independent review handoff.
