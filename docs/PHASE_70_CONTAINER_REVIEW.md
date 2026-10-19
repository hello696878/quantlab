# Phase 70 Independent Container Hardening Review

2026-10-18. VERSION remains `4.88.0-dev`.

## Verdict and exact target

**Safe to keep: YES as a local, statically checked topology foundation.
Ready for a user review commit: YES.** One P2 build-contract defect and one P3
effective-configuration policy defect were fixed with independent regressions.
No unresolved scoped pre-commit defect remains. Actual image/runtime acceptance
is still pending; this is not public hosting, authentication, multi-user
isolation, production readiness or security certification.

The fresh review began on attached clean `main`, with empty index, no unstaged
changes and no nonignored untracked paths:

- Implementation: `a4120d66f705dc72cef07e9ac05b8d565972b122`.
- Subject: `Add local hardened read only demo container topology v1`.
- Source tree: `ef3873d627e9733740e6b06d8ec4023e2e85b11f`.
- Exactly one parent: `5b29bbd27b4a7b4c482b7bc12fac8c7a4f92fa08`, tree
  `4ef8e2ac03e4113065a7d77a2f18cd06fb023ee5`.
- VERSION `4.88.0-dev`; existing v4.87 annotated tag still peels to
  `1062ec48b4128af867ab5a3329951511ebff285c`.
- Complete implementation inventory: **12 paths, 4 modified /8 added**.

Applicable `AGENTS.md`/`CLAUDE.md`, all twelve implementation diffs, the complete
[container implementation report](PHASE_70_CONTAINER_TOPOLOGY.md), current
[runbook](READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md), dedicated/ordinary recipes,
installed Next routing/build contracts and protected runner/fixture boundaries
were inspected. The earlier product review was not repeated. Its reports,
Phase 69 evidence, dependencies, product/quant code, VERSION and ordinary
development recipes are unchanged. Initial raw index: 128188 bytes, SHA-256
`9898444d488442d090373f0ab8c82afb018d8abb6480b01208cafcbc2c15a3ad`.

## Confirmed findings and narrow fixes

| Severity | Confirmed defect | Correction and independent regression |
| --- | --- | --- |
| P2 | `checkDemoBuild` accepted the correct private rewrite/environment while ignoring compiled redirects and rewrite conditions. An `/api/*` redirect could intercept the request before the private rewrite; `has`/`missing` could make that rewrite conditional. The old positive fixture did not exercise the real Next custom-route compiler. | `frontend/container/check-demo-build.cjs:16-45` now requires the expected manifest version/base path, no custom headers, the standard internal 308 slash redirect and one unconditional private rewrite in the supported route position. Compiled regex metadata is bound to the locked compiler expressions. `check-demo-build.test.cjs:14-100` invokes installed Next 15 route loading/compilation on the actual repository config, then exercises external/localhost/relative redirects, conditions, changed headers/base path/route groups and two regex mutations. **14 added cases; 26 total passed.** |
| P3 | The effective Compose validator checked logical network membership but accepted shared/foreign physical network names and attachment overrides. It also accepted optional backend readiness, dependency restart/unknown fields and unsupported port options. Its static green result therefore exceeded its closed-topology claim. | `scripts/validate_demo_compose.py:24-101` requires explicit project-derived distinct networks, empty supported attachment options, closed port/dependency fields, required health dependency and no dependency restart. `backend/tests/test_demo_container_topology.py:70-102` adds eleven negative mutations plus one supported-normalization case: **12 added cases; 47 total policy cases passed.** The actual standalone file already resolves to the stricter policy; no Compose change or privilege relaxation was needed. |

The P3 finding is a static-policy false-green, not an observed network exposure.
For P2, real redirect/condition semantics were checked through the installed
Next compiler without building or serving. On this Next version the server
reconstructs custom-route matchers from `source`; a mismatched stored regex is
a compiled-metadata identity failure, not a demonstrated request bypass. This
guard is still not a complete arbitrary manifest/image attestation mechanism.
Its locked version/expressions intentionally refuse unsupported future compiler
output until reviewed.

Only four source/test files were changed for these defects. No Dockerfile,
Compose topology, product factory, corpus producer, UI or E2E bytes were changed
by this review. The two original dedicated recipes are retained.

Necessary current runbook corrections distinguish declared controls from
enforcement, retain the user's earlier product attestations separately, and
clarify Docker-managed pseudo-filesystems. The later offline procedure now
checks new volume driver/scope/options/ownership labels before its first mount;
stopped-copy instructions repeat fresh destination, UID/owner/empty-root,
distinct-name and stopped-state checks. These are operator-procedure corrections,
not executed Docker proofs. All five PowerShell blocks and four embedded Python
snippets parse; none of their acceptance operations was executed.

## Effective Compose and image-contract conclusions

Fresh Docker Compose **5.1.3** resolved the actual standalone file with explicit
`--env-file`, `--project-name` and **one `-f compose.read-only-demo.yml`**.
The static project `p70-review-w70990te`, image/volume names and `a` repeated
64 times are validation placeholders only; they identify no built image,
created volume or prepared corpus.

Resolved services are exactly `demo-backend` and `demo-frontend`. Backend has
no published ports and joins only `p70-review-w70990te_demo_private`, declared
internal. Frontend joins that network plus distinct
`p70-review-w70990te_demo_edge`; its only publication is TCP target 3000 at
`127.0.0.1:3180`. No host-IP omission, wildcard/IPv6 publication, host networking,
external network, bind mount, checkout/home/socket/credential/active DB mount or
preparation service is accepted. Deliberately merging ordinary
`docker-compose.yml` produces four services and is refused by policy. Missing
the required corpus ID makes Compose itself refuse.

The backend command is exactly Python/Uvicorn `app.serving:create_app --factory`,
one worker, port 8000, `--no-access-log --no-proxy-headers`. The environment
requires `read_only_demo`, `/corpus/v1`, full corpus ID and the exact approved
backend hosts/origin. Frontend build/runtime URL is `http://demo-backend:8000`,
and the build mode is `read_only_demo`. The frontend depends on backend health;
no automatic prepare, seed, migration, reset, repair or ordinary factory fallback
is introduced. Existing missing/unfinished-preparation refusal tests passed.

The external corpus volume has a controlled explicit name and is the backend's
only application volume, mounted read-only with `nocopy`; frontend has no data
volume. The image's empty `/corpus` directory is owned by numeric 10001:10001
for explicit offline empty-volume copy-up. Serving never chowns/chmods or
initializes active data. Actual engine copy-up/permissions are unverified.

Dedicated Dockerfiles use explicit COPY sources. They do not copy developer
root `.env`, local `.next` or `node_modules`; declared ignore rules add another
layer. This is not a complete secret/image-layer audit. The backend installs
only its declared requirements and exposes Python/urllib for the health probe.
The frontend installs its locked package set with engine-strict, sets build
arguments before the real future `npm run build`, and invokes the guard on the
generated `.next/routes-manifest.json`. The runtime retains that manifest,
Build ID and `demo-build-contract.json` for inspection. Runtime environment
cannot repair stale baked rewrites. A guard environment record alone does not
prove every client bundle; the later real UI check is still required.

`USER 10001:10001`, matching Compose user, root-owned readable application files,
`HOME=/tmp`, disabled telemetry and Python bytecode writes are declared. The
supported frontend source has no identified Next image optimizer, ISR/revalidate
or server-fetch cache requirement. That inspection does not establish that the
actual Next production process works under the read-only root and temp budget.
Numeric users, image package contents/imports and startup remain runtime gates.

### Static versus actual runtime enforcement

| Property | Classification and evidence boundary |
| --- | --- |
| Standalone services, commands, environment, build arguments and health dependency | Implemented and statically verified using actual resolved Compose JSON plus negative cases. Actual startup/order/health remains runtime-pending. |
| UID/GID 10001:10001 | Implemented declaration in both recipes/config; running UID/GID, file readability and volume copy-up require runtime verification. No claim that an image directive measured a running process. |
| `cap_drop: ALL`, no-new-privileges, init, read-only root/corpus | Implemented and static policy verified; effective kernel capabilities/NoNewPrivs/mount flags and denied writes unverified. |
| Writable paths | Declared application `/tmp` only, 64 MiB rw/noexec/nosuid/nodev tmpfs; corpus RO/nocopy. Docker-managed `/dev`, `/dev/shm`, proc/sys and other pseudo-filesystems must be inspected separately. This is not a claim that every process-visible path is read-only. |
| Resources/logging | One CPU per service, memory backend/frontend 512/768 MiB, PID 96/128, nofile 1024, two 5 MiB local log files; static declarations verified. Engine enforcement, measured sufficiency and actual raw-log behavior remain pending. |
| Host ports/networks | Explicit loopback frontend, private unpublished backend and distinct internal/edge network declarations verified. Actual Docker Desktop publication/routing/isolation unmeasured; frontend edge permits outbound traffic. |
| Image identity/version/digest | Mutable `python:3.11-slim`/`node:24-alpine` recipes implemented; no pull/build/image inspection here. Local Node/Python test versions do not establish image versions. Real image IDs/digests/imports/support must be retained later. |
| Health probes | Exact bounded Python stdlib ready/policy/ID and Node fetch ready/policy/ID programs statically checked; tool availability and results in the built images are runtime-pending. |
| Proxy and demo client mode | Build inputs and actual installed compiler configuration tested; actual image routes-manifest, baked client mode, proxy/server and browser behavior remain pending. |
| HTTPS, public ingress and complete egress denial | Documented future requirements, not implemented. Internal network membership alone is not proof of every egress/host/native boundary. |
| Authentication, multi-user confidentiality, public-host guarantees | Not implemented/unsupported. No production/security/trading certification or hosted deployment. |

Source checks in `validate_sources` are limited declaration/COPY/context checks,
not a complete Dockerfile instruction parser. Manual recipe review, source hashes
and the future actual image inspection are separate evidence; no source-only
grep was treated as the resolved Compose result or runtime acceptance.

## Offline lifecycle, script safety and proxy-only browser review

The later runbook builds from a clean exact-commit archive with conversion
disabled, not a mounted live checkout. Its controlled GUID names, explicit
argument arrays and no shell evaluation prevent user strings from becoming
shell commands. There is no recursive deletion, volume/container removal,
overwrite/reset or secret import procedure. Unsetting the E2E backend URL is an
environment operation, not filesystem cleanup. Native `Run` records argv, exit,
duration/stdout/stderr and stops on a nonzero exit; failures retain evidence.
Initial exact-source checking and later final Git identity are explicit.

Offline preparation is a separate non-root, read-only-root, network-none image
operation with a new writable owned volume. It checks UID/GID, `/corpus` owner
and empty root before existing `prepare('/corpus/v1')`. The existing synthetic
source, exclusive destination, full identity/material checks, before-manifest
verification, unsupported WAL/journal/SHM refusal and failure retention remain
unchanged. No active-user DB or earlier Windows corpus is imported. Missing or
unfinished data cannot become ready; serving has no writable fallback. No hot
replacement is supported. Driver/label checks improve accidental-reuse refusal;
GUIDs and operator attestations are not a hostile concurrent-Docker-daemon sandbox.

Stopped backup/restore requires both serving containers verified stopped, source
RO/nocopy and a different newly allocated/checked destination. Copies reuse the
existing stopped/identity/exclusive-publication contract. Preserve prior volumes
and byte inventories; never checkpoint/delete sidecars to pass. General online
backup/migration/authentication remains outside scope. Actual named-volume
prepare/serve/stop/backup/restore has not been executed in this review.

The proxy-only E2E option is explicit `E2E_READ_ONLY_DEMO_PROXY_ONLY=1` with no
backend URL; invalid/ambiguous combinations refuse. It still verifies the closed
capability mode/policy/corpus contract, readiness, pinned list/detail/explanation,
refusals/stale pins, notices/navigation, exact export and browser request allowlist.
It annotates its reduced direct-probe scope. Default mode still requires both
loopback origins and direct/proxy material equality. Proxy-only cannot silently
waive product identity, and does not count as direct-backend/physical-byte proof:
the separate container-exec direct proof and before/after corpus inventory are
mandatory. No browser, stale-server replacement, download/layout or container
proxy behavior was executed. Application provider refusal remains separate from
a network egress mechanism; no real provider request was made.

## Fresh review verification

Evidence root:
`C:\Users\jimli\AppData\Local\Temp\quantlab-p70-container-review-w70990te`.
All executable/config/test bytes and the corrected runbook were frozen during
the checks. Source and index preservation are independent of test outcomes.

### Protected backend scope

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused --test backend/tests/test_demo_container_topology.py --test backend/tests/test_read_only_demo.py::test_missing_corpus_never_created_or_falls_back --test backend/tests/test_read_only_demo.py::test_interrupted_preparation_retains_unservable_owned_destination
```

Existing project Python **3.13.5 (Anaconda/MSVC AMD64)**, pytest **9.0.3**,
Windows-11-10.0.26100-SP0, one serial worker. Runner/conftest/URI/link guards
were inspected and unchanged. Scope is 47 pure policy cases and two existing
owned missing/unfinished-preparation boundary cases; not a repeat product review.

Evidence directory:
`C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-4si32xrk`.

| Actual result | Value |
| --- | --- |
| Selected / passed / deselected | 49 /49 /0 |
| Skips / failures / errors | 0 /0 /0; no skip reasons |
| Reported pytest | 49 passed in 30.80s |
| Machine pytest / collection seconds | 31.690774799964856 /29.035995299986098 |
| Child / outer wall seconds | 35.01114660000894 /53.57203490001848 |
| Snapshot setup seconds | 4.4559958999743685 |
| pytest / child / outer exits | 0 /0 /0 |
| JUnit | 49 tests, zero failures/errors/skips, 30.787s |
| Per-node phases | 49 setup, 49 call, 49 teardown passed |
| Protection / completeness | Worktree, snapshot, observed active-file bytes unchanged; child evidence complete; SQLite violations `[]`. |

Manifest SHA-256:
`486f4b76dcd81e01a8deaebea7b849713b7d888f04ee0e861c5ffce42a493587`.
It contains 1201 paths with `missing=[]`, `omitted=[]`. Exact node IDs, individual
durations and outcomes are in `collection.json`, `phases.jsonl`, `junit.xml` and
`pytest.log`; separate results/runtime/argv are in `pytest-result.json`,
`runner-result.json`, `runtime.json` and `run-config.json`. No active database
was connected through SQL. Runner file/sidecar observations are bounded
protection evidence, not a fresh general data/security audit.

### Effective Compose and frontend contract checks

Existing Docker Desktop CLI: `C:\Program Files\Docker\Docker\resources\bin\docker.exe`.
Fresh Compose metadata: **5.1.3**. Existing supported Node **24.21.0** was
rediscovered at
`C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\a5a02988362ca169\bin\node.exe`.
Default system Node24.15 was observed and not used. Installed packages are
Next15.5.25, TypeScript5.9.3 and Playwright1.61.1. No package/runtime was installed.

Actual commands used an owned empty env file and the static placeholders above:

```text
docker compose --env-file <evidence>/empty.env --project-name p70-review-w70990te -f C:/quantlab/compose.read-only-demo.yml config --format json
python -B scripts/validate_demo_compose.py <evidence>/standalone-config.stdout
docker compose --env-file <evidence>/empty.env --project-name p70-review-w70990te -f C:/quantlab/docker-compose.yml -f C:/quantlab/compose.read-only-demo.yml config --format json
python -B scripts/validate_demo_compose.py <evidence>/merged-config.stdout
node --test --test-reporter=tap container/check-demo-build.test.cjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/@playwright/test/cli.js test e2e/read-only-demo.spec.ts --list --reporter=json
```

Python denotes the existing project executable above; frontend commands use
the discovered Node executable, cwd `C:\quantlab\frontend`. The missing-pin case
uses the standalone command with only `QL_DEMO_CORPUS_ID` removed from the
controlled environment. Full argv, cwd, host duration and process exits are in
`execution.jsonl`; matching `.stdout`/`.stderr` and `verification-result.json`
are retained. No Compose operation builds or starts anything.

| Fresh check | Actual outcome / process exit | Host seconds |
| --- | --- | --- |
| Standalone effective compile | Valid resolved JSON /0 | 0.4486862999619916 |
| Standalone policy | Accepted; runtime_verified false /0 | 0.47045910003362224 |
| Deliberate development merge compile | Four services /0 | 0.3740531000075862 |
| Merged policy | Expected refusal /2 | 0.10103129997150972 |
| Missing corpus ID compile | Expected Compose refusal /1 | 0.379657200013753 |
| Node compiled-contract suite | 26 passed, zero fail/cancelled/skipped/todo /0 | 0.3803304999601096 |
| TypeScript, no incremental output | No diagnostics /0 | 32.86385439999867 |
| Focused Playwright discovery | One scenario, zero runtime results/errors /0 | 1.1710577000048943 |

Node TAP reports 26 tests, 307.0106ms. Fourteen new cases are included, not added
again to the total. The real Next custom-route compiler tests are equivalent
configuration compilation, not a Next production build or server. Discovery's
one `skipped` is a list placeholder, not an executed skip/pass. No browser was
executed. Source manifests before/after all static/frontend checks cover 1201
paths with no membership or byte differences. The external before-manifest
SHA-256 is `74ed3722dfd68e07605582b7bfd1e6674c25e8dad26e87f60df357b8a9e37015`.
PowerShell7.6.5 parsed all five runbook blocks with zero errors; Python AST parsed
Prepare/Inventory/BackendBoundary/Probe, four snippets, without executing them.

### Frozen reviewed working-file identities

Raw SHA-256, including current line endings:

| Path | SHA-256 |
| --- | --- |
| `scripts/validate_demo_compose.py` | `b7974efb373019f1a820ea5073a8c341e8271944aee67f906f39b5e2642b1ecc` |
| `backend/tests/test_demo_container_topology.py` | `702a52072372ba9e11ae1b7960ca10da09e20490ce25120e1997fd3b949c64a7` |
| `frontend/container/check-demo-build.cjs` | `09fdf211182253bdf85be857bfefa2bc3c7aa0b41a1438c12b6761de3e488145` |
| `frontend/container/check-demo-build.test.cjs` | `3be72313e806d62402817891907a3286a4a323b4d4ba3445702063fff002c0a8` |
| `docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md` | `13bd12e753012b4c377d2635e08bde91e53cb289b5d3f102f6cc94c72e65cf25` |

Only STOP_POINT/TASKS status prose and this new report were finalized after
verification. The corrected runbook was already included in the frozen source
and separately parsed; parser success is not execution of its Docker procedure.
The four tested source/test files and runbook above retain these hashes.

## Inherited evidence and preserved failures

The unchanged implementation report and actual retained evidence were read;
these are separate snapshots, not fresh review results:

| Inherited run | Scope/result | Reported pytest; machine pytest /child /outer seconds | pytest/child/outer |
| --- | --- | --- | --- |
| `quantlab-backend-focused-y9uswx50` | 33 original policy +2 product integration =35 passed, zero skips/failures/errors | 42.53s; 43.86662330001127 /47.99705740000354 /80.6185527999769 | 0/0/0 |
| `quantlab-backend-focused-iui34agz` | Strengthened health-policy cases only =35 passed, zero skips/failures/errors | 0.20s; 0.40165800001705065 /1.3159178999485448 /13.714087200001813 | 0/0/0 |

Both identify the existing Windows/Python3.13.5/pytest9.0.3 runtime, complete
child evidence and unchanged snapshot/worktree/observed active files, with no
SQLite violations. Both have 1201 paths, no missing/omitted sources. Manifest
hashes are respectively
`39ef9dac01d1ea6a6e16d530730c26d3371859f679d2ef9fd4c155bec7d5936a` and
`87d60c759cff988622c2bc15e09debc9a7273c045bb1a098440f55b6cd239bf3`.
They are not 70 final passes. The actual snapshot difference includes two
executable/test files and four docs: validator, topology tests, STOP_POINT,
TASKS, container implementation report and runbook. Later final implementation
prose is recorded separately. The original final-hygiene twelve raw file records
were reconciled to the committed target/retained working bytes; Git-normalized
blob hashes were not falsely called raw working hashes.

Inherited actual effective-config checks: standalone compile0/0.4441754s,
policy0/0.2053314s; deliberate merged compile0/0.4983353s and policy2/0.1848659s;
missing-pin compile1/0.568869s. The first policy attempt failed exit2/1.1847685s
after successful compile0/0.6275199s because Compose normalized null entrypoint,
decimal memory strings and empty IPAM. Its later normalization correction
passed0/0.4988791s, and strengthened health policy passed0/1.2783854s. These
failures/corrections are retained, not replaced by a claim of an initial pass.

Inherited frontend: 12 Node passes, exit0/0.2441265s, TAP148.0655ms; TypeScript
exit0/21.9569492s; one focused discovery exit0/1.9690061s, none executed.
PowerShell quoting/link-parent/inspection guard failures remain in the original
external evidence; they did not execute acceptance or become test failures.

The existing engine metadata attempt failed **exit1, 3.6271875s**, with:

```text
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
template: :1:238: executing "" at <.CpuCfsQuota>: can't evaluate field CpuCfsQuota in type system.dockerInfo
```

That is the exact retained implementation error, not a new probe or a claim
about current engine availability. Partial JSON is not platform proof. This
review did not repeat engine probes, restart/reset Docker or weaken controls;
build/start/runtime execution is outside its authority regardless of availability.

This review's initial external baseline write failed PermissionError before
publication/tests; the owned directory was retained and the baseline was written
with authorized evidence access. An ordinary-process read of that protected
evidence was also denied; elevated read succeeded without rerunning any check.
These are evidence-access setup failures, not pytest/Docker test failures.

The earlier product review's 219/283, implementation 168/357 snapshots and
historical failures remain in their unchanged reports. The container implementation
records **user-attested** pre-hardening Linux/Python3.11 CI5254/18 skips, production
build and Edge acceptance. Those attestations were not rerun or retrieved here;
no skip identities or final-container coverage are inferred. No snapshots are
summed into a whole-tree pass and no previous Edge/Phase 69 physical-link gate
was repeated.

## Unconfirmed risks and required later user-owned acceptance

No additional confirmed scoped defect remains. Unconfirmed runtime risks are
actual volume copy-up/permissions, numeric user/library behavior, Next cache/temp
writes and read-only compatibility, health/proxy startup, engine resource/kernel
restrictions and actual host-port/network isolation. Complete egress/ingress,
public TLS, image/secret-layer assurance, hostile native/Docker-daemon races,
distributed abuse controls and general online recovery are not established.

The minimum later acceptance sequence, with the runbook's complete commands, is:

1. User creates the reviewed commit, then retains exact clean commit/tree,
   byte-exact archive, CLI/engine/runtime versions and every command exit/log.
   Check a usable Linux engine once; on failure retain the exact error and stop.
2. Allocate uniquely labelled ordinary local volumes with no driver options;
   inspect metadata before mounting. Build actual backend/frontend images from
   that archive, record real image IDs/RepoDigests (including absent digest),
   package versions, Build ID and baked route manifest/build contract. No labels
   or build success substitute for runtime/source proof.
3. Prepare offline under UID/GID10001, network none, new empty volume and explicit
   owner checks; verify the real full corpus ID. Missing/partial data must fail
   serving without repair. Retain the complete corpus byte/sidecar inventory.
4. Resolve and pass the standalone effective-policy check with actual IDs, then
   start only that topology. Inspect running process user, factory/one-worker
   command, capabilities/NoNewPrivs, root/corpus mount flags, all writable and
   pseudo-filesystem paths, budgets/logs/health and ports/networks. Backend must
   have no published host port; frontend only the intended loopback address.
   Test denied writes on expendable owned probes; preserve any unexpected write
   and stop rather than cleaning it or granting root/writable data.
5. Retain positive direct-container and frontend-proxy mode/corpus/readiness/data
   identity, denied mutation/provider/unknown-path and stale-pin outputs, and
   actual storage preservation. Then execute exactly one prepared-container
   browser scenario with annotation/JUnit/download evidence. Proxy-only does not
   replace the separate direct proof or physical file inventory.
6. Compare final corpus DB/manifest hashes and sidecars, source/index identity
   and actual final runtime state; retain failures. Verify stopped backup/restore
   onto separately checked fresh volumes before accepting that lifecycle.

**Exact-container-review-commit Python 3.11/Linux CI, actual image builds and
compiled proxy/client inspection, hardened-container runtime acceptance and the
single new container browser acceptance remain pending.** No default local
whole-tree suite was run. A successful `compose config`, unit suite, build or
older product acceptance alone cannot close these gates. They limit acceptance,
not the local review-commit verdict.

## Exact implementation inventory

Committed scope relative to the single parent: **12 paths, 4 M /8 A**.
This is not the pending REVIEW inventory below.

```text
M STOP_POINT.md
M TASKS.md
A backend/Dockerfile.read-only-demo
A backend/tests/test_demo_container_topology.py
A compose.read-only-demo.yml
A docs/PHASE_70_CONTAINER_TOPOLOGY.md
M docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md
A frontend/Dockerfile.read-only-demo
A frontend/container/check-demo-build.cjs
A frontend/container/check-demo-build.test.cjs
M frontend/e2e/read-only-demo.spec.ts
A scripts/validate_demo_compose.py
```

## Exact pending REVIEW inventory and later USER-ONLY staging plan

**8 intended paths: 7 modified /1 new, all unstaged.** The new review report is
nonignored untracked until later staging. No other source/artifact belongs here.

```text
M STOP_POINT.md
M TASKS.md
M backend/tests/test_demo_container_topology.py
A docs/PHASE_70_CONTAINER_REVIEW.md
M docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md
M frontend/container/check-demo-build.cjs
M frontend/container/check-demo-build.test.cjs
M scripts/validate_demo_compose.py
```

Only after a new user authorization and exact branch/base/inventory/content
verification, the user may execute this literal path list. It was **not executed
here**; never run this Markdown report as a script or use blanket staging.

```powershell
git --literal-pathspecs add -- STOP_POINT.md TASKS.md backend/tests/test_demo_container_topology.py docs/PHASE_70_CONTAINER_REVIEW.md docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md frontend/container/check-demo-build.cjs frontend/container/check-demo-build.test.cjs scripts/validate_demo_compose.py
```

Later verify exact 8-path/7 M/1 A staged membership, cached whitespace/EOF, source
hashes, VERSION/screenshots/historical evidence and unchanged working bytes;
preserve unrelated staging and stop on unexpected content. Do not stage the
earlier twelve-path implementation again or add paths to reach a count.
The review root's `final-hygiene.json` retains final raw hashes/sizes for all eight
review paths, including post-test status prose and this report, for later checks.
No file, runtime, dependency, credential, database, backup, cache/build/browser
output or new repository evidence manifest is added outside this inventory.

## Preservation and stop boundary

The recorded 1190 tracked files outside the allowed existing edit set retain
their raw hashes/sizes, including VERSION, Phase 69/earlier Phase 70 reports,
the container implementation report, frozen screenshots, ordinary Compose/
Dockerfiles, dependencies, product/quant source and runner/conftest. Dedicated
Dockerfiles, standalone Compose and E2E also remain unchanged. Index hash/size
match entry; staged paths remain zero. The final pending inventory is exact,
whitespace/EOF and local links pass, and no generated/runtime path is pending.
Known LF-to-CRLF Git warnings did not trigger normalization or configuration edits.
Protection of the active DB is only the runner's recorded bounded observations;
no fresh general audit or active SQL connection occurred.

No staging, commit, push, tag, deployment, workflow/cloud action, dependency
installation, cleanup, image build, container/service startup, browser execution
or Phase 71 occurred. Future tag
`v4.88.0-read-only-hosted-demo-deployment-hardening-plan-v1` remains unauthorized
and uncreated. Stop at this single independent container review handoff.
