# Phase 70 Local Hardened Container Topology v1

Post-review implementation, 2026-10-18. Not independent review or runtime acceptance.

## Baseline and Authority

Initial attached clean main, HEAD `5b29bbd27b4a7b4c482b7bc12fac8c7a4f92fa08`,
tree `4ef8e2ac03e4113065a7d77a2f18cd06fb023ee5`, empty index/untracked set.
VERSION remains 4.88.0-dev. Existing v4.87 annotated tag peels to
1062ec48b4128af867ab5a3329951511ebff285c / tree
3a06cbef017e1828781d2e6861c17eecf4afd014. No tag or branch was changed/created.
Applicable AGENTS.md, CLAUDE.md, implementation/review reports, source, actual
ordinary Compose/Dockerfiles, provider/serving/corpus and runner contracts read.

The user reports successful exact-review CI (5254 backend passes /18 skips on
Linux/Python3.11), production build exit0, one real Edge scenario, direct/proxy
mode/readiness proofs, owned Windows corpus preservation and clean source.
These pre-hardening results are user-attested, not rerun/retrieved, and do NOT
accept this patch. Completed PHASE_70_REVIEW.md and PHASE_70_IMPLEMENTATION.md
are unchanged historical evidence; old pending runtime wording is not rewritten.

## Delivered Boundaries

- Standalone compose.read-only-demo.yml, exactly demo-backend/demo-frontend;
  no include/extends, dev override or automatic preparation dependency.
- Dedicated Python3.11/Node24 Dockerfiles reuse declared requirements/lockfile.
  Existing development recipes, Next config, product mode/quant/API/corpus
  identity logic and VERSION are untouched. No host package installation.
- Serving UID/GID10001, cap-drop ALL, no-new-privileges, read-only roots,
  64MiB /tmp only; CPU/memory/PID/nofile/log budgets, readiness health checks,
  private backend/no published port, one worker/no raw access/proxy-header trust.
- Backend corpus volume is external, explicitly uniquely named, RO/nocopy.
  Offline preparation uses the existing synthetic producer in a separate
  network-none container with a fresh volume, checked copy-up owner and empty
  destination. No existing Windows corpus or active DB is mounted/copied.
- Frontend build bakes private backend URL and demo mode; a small Node guard
  refuses a wrong compiled rewrite/build environment and retains the build
  contract plus actual route manifest. Explicit COPY does not import local
  env/build/dependency trees. This is not proof of complete secret exclusion.
- Existing browser spec gains an explicit private-container proxy-only setting.
  It refuses ambiguous backend-URL/flag combinations, retains all UI/proxy
  assertions and annotates its reduced direct-probe scope. Default mode retains
  both-origin acceptance. Separate direct container-exec proofs are mandatory;
  the backend is never published for E2E convenience.

See [exact PowerShell acceptance and volume lifecycle](READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md#later-user-controlled-container-acceptance).
Commands build from a clean exact-commit archive with conversion disabled, not
a live checkout mount. They retain image IDs/digests, actual runtime versions,
effective config, UID/caps/mounts/networks/ports/resources/commands/build manifest,
positive/negative direct/proxy proofs, one selected Edge scenario and corpus
hash/inventory comparisons. Nonzero exits stop and retain evidence.

## Classification and Limits

| Class | Actual scope |
| --- | --- |
| Implemented/static-testable | Effective config policy and negative mutations, explicit build/env/volume/network declarations and compiled-rewrite guard. |
| Implemented/runtime-pending | Real image build, non-root volume copy-up, read-only root/corpus enforcement, capabilities, tmpfs/budgets/health/log behavior and private container proxy/browser integration on Docker Desktop. |
| Documented/not implemented | Public HTTPS/ingress/TLS, enforced complete egress denial, secret/image-layer audit, distributed abuse controls, general live DB migration/backup and disaster recovery. |
| Unsupported | Authentication, accounts/multi-user confidentiality, public hosting, production/trading/security certification. |

Frontend edge network permits outbound traffic. Backend is attached only to an
internal bridge; actual engine routing/enforcement is NOT measured here, and
network membership is not proof of every egress/native/host boundary. Preserve
the restrictions if copy-up or startup fails; do not silently use root or writable
serving data. Mutable python:3.11-slim/node:24-alpine contents/digests/support were
not pulled or audited. Docker engine/server connectivity/enforcement is not
inferred from successful Compose config compilation.

## Verification Evidence

External static/frontend evidence:
`C:\Users\jimli\AppData\Local\Temp\quantlab-p70-topology-c9d3850d28a64f42bfd1c8fbb07d5582`.
Docker Compose v5.1.3 is installed at the existing Docker Desktop CLI. No image
build, service startup, Docker run, browser execution or host installation occurred.

### Effective Configuration and Preserved Attempts

Actual commands used an explicit empty owned env file, project p70-static-check,
unique static-only image/volume names, placeholder `a`*64 ID and port3180. Those
placeholders are NOT a prepared corpus, image or created volume. All commands
were config/validation only, no service start or build:

```powershell
docker compose --env-file <evidence>/empty.env --project-name p70-static-check -f compose.read-only-demo.yml config --format json
.\.venv\Scripts\python.exe -B scripts/validate_demo_compose.py <evidence>/effective-compose-final.json
docker compose --env-file <evidence>/empty.env --project-name p70-static-check -f docker-compose.yml -f compose.read-only-demo.yml config --format json
```

Final standalone compile exit0/0.4441754s and policy exit0/0.2053314s. The
deliberate merged-dev compile exit0/0.4983353s produced four services; policy
refused it exit2/0.1848659s. Removing the required corpus ID made Compose refuse
exit1/0.568869s. These expected negative exits are not pytest failures. JSON,
stderr and per-command exits/durations remain in static-final-execution.json and
the matching effective/policy/missing-pin files.

Initial standalone compile succeeded (exit0/0.6275199s), but first policy failed
(exit2/1.1847685s). Inspection identified Compose5 normalization: null entrypoint,
decimal byte-string memory limits, empty IPAM. Only these empty/equivalent
representations were accepted; non-null entrypoints, root users, extra networks,
mounts, capabilities or unbounded resources still refuse. Corrected policy
exit0/0.4988791s is preserved separately. The diagnostic ValueError exit1 was
an inspection command, not a test run or container error.

One read-only Docker-info metadata probe failed exit1/3.6271875s: Linux engine
pipe dockerDesktopLinuxEngine was absent (`The system cannot find the file
specified`). The attempted template also reported unsupported CpuCfsQuota in
system.dockerInfo. Both errors remain in engine-advertised-capabilities.log;
the partial JSON is NOT usable platform proof. No permission bypass, engine
start/reset, installation or repeated request to start Docker followed.
Actual engine-advertised capability/enforcement evidence is unavailable. It is
a later runtime blocker, not grounds to remove declared restrictions.

### Focused Protected Backend and Frontend Checks

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused --test backend/tests/test_demo_container_topology.py --test backend/tests/test_read_only_demo.py::test_startup_reads_are_ro_and_requests_never_initialize_or_call_providers --test backend/tests/test_read_only_demo.py::test_actual_route_inventory_drift_and_new_routes_deny_before_dependencies
```

Existing Windows-11-10.0.26100-SP0, project Python3.13.5 (Anaconda), pytest9.0.3,
one serial worker. Earlier integration snapshot evidence root:
`C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-y9uswx50`.
**35 selected/passed, zero deselected/skipped/failures/errors**: 33 new pure
policy cases plus two existing owned-storage/provider/actual-route cases.
All 105 setup/call/teardown records passed. Reported pytest42.53s, machine
pytest43.86662330001127s, child47.99705740000354s, outer80.6185527999769s,
snapshot setup21.045922000019345s. pytest/child/outer exits0/0/0;
child evidence complete, snapshot/worktree/observed active-DB unchanged true,
SQLite violations empty. No active DB was opened via SQL; preservation is the
runner's bounded file/sidecar observation, not a fresh general data audit.
Snapshot manifest SHA-256:
`39ef9dac01d1ea6a6e16d530730c26d3371859f679d2ef9fd4c155bec7d5936a`.
collection.json, phases.jsonl, junit.xml, pytest.log, runtime.json and result
files retain exact node outcomes, actual dependency versions and distinct exits.
Source stayed frozen during execution. No full suite or historical five-case
platform/browser acceptance was rerun; no Linux/Python3.11 result is inferred.

Final inspection strengthened only the static validator and its tests: a
disabled or substituted readiness probe could previously retain matching URL
text. Closed health-check fields and the exact bounded probe scripts now
refuse both cases. No Compose, Dockerfile, application or frontend bytes changed
in this strengthening. The retained real effective Compose JSON still passes:
policy-health-final-execution.json exit0/1.2783854s. The earlier merged-dev and
missing-pin refusals remain separate evidence.

Final affected command:

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused --test backend/tests/test_demo_container_topology.py
```

Evidence `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-iui34agz`:
**35 selected/passed pure policy cases**, zero deselected/skips/failures/errors,
105 passed phase records; pytest/child/outer exits0/0/0. Reported pytest0.20s,
machine pytest0.40165800001705065s, child1.3159178999485448s,
outer13.714087200001813s, snapshot setup6.443190400023013s. Same actual runtime;
all protection flags and child completeness true, SQLite violations empty.
Manifest SHA-256:
`87d60c759cff988622c2bc15e09debc9a7273c045bb1a098440f55b6cd239bf3`.
The earlier 35 (33 old policy +2 integration) and final 35 (strengthened policy)
are different snapshots/scopes, NOT 70 final passes or a full backend suite.

Existing Node24.21.0 was rediscovered under the current Codex cua_node runtime;
no npm install or host runtime upgrade occurred. Cwd frontend:

```text
node --test --test-reporter=tap container/check-demo-build.test.cjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/@playwright/test/cli.js test e2e/read-only-demo.spec.ts --list --reporter=json
```

Build-contract units: **12 passed**, zero skipped/failed/cancelled/todo, process
exit0/0.2441265s (TAP duration148.0655ms). TypeScript exit0/21.9569492s, no
diagnostics. Focused browser discovery exit0/1.9690061s: **one scenario only,
none executed**; list-mode skipped is a discovery placeholder. Results, exact
commands/durations and logs are retained under the static/frontend evidence root.
Ordinary UI units/pre-hardening build/Edge/CI were not rerun or relabelled.

Runbook parser checks: five PowerShell blocks and four embedded Python snippets
parse successfully without executing acceptance. The initial embedded-Python
inspection command had a PowerShell dollar-parenthesis quoting error before
Python could launch; corrected inspection exit0, setup error retained in
runbook-parse-setup-failure.json. No acceptance operation ran from Markdown.
The first link-check command also failed on an empty parent for a root Markdown
path; resolving absolute parents corrected inspection only. Its setup error is
retained in link-inspection-setup-failure.json. Final local-link/anchor check
found 33 valid links and no broken targets. Neither inspection error changed
source or executed any acceptance command. An initial final-prose patch failed
its exact-context guard before writing; the corrected patch only updates prose.

Only current prose/status documents are finalized after verification. Final
executable/test/spec bytes are compared with the protected snapshot and the
pre-verification source hashes. Exact inventory/plan, whitespace/EOF, links,
frozen screenshots/historical reports, unchanged development recipes/quant/
requirements/version/runner and empty index are checked at handoff; external
final-hygiene.json retains the final raw source hashes for later staging.

### Verdict and Remaining Gates

**Safe to keep: YES as a local, statically checked topology foundation.
Ready for independent review: YES.** No confirmed implementation defect remains
from these focused checks. Docker engine connectivity, actual volume copy-up,
image builds/contents, every runtime restriction and the containerized Edge
scenario remain UNVERIFIED, not successful. The unavailable Linux pipe is an
explicit runtime-verification blocker. User build/browser/image inspection and
review of this patch are required before accepting this local topology. Public
hosting, complete egress denial and production certification remain unsupported.

## Exact Pending Inventory and Later User-Only Plan

12 paths: 4 modified /8 new, all unstaged. No generated serving databases,
evidence, credentials, dependency/runtime/cache/browser/build outputs are source.

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

Only after fresh user authority and exact base/inventory/hash verification:

```powershell
git --literal-pathspecs add -- STOP_POINT.md TASKS.md backend/Dockerfile.read-only-demo backend/tests/test_demo_container_topology.py compose.read-only-demo.yml docs/PHASE_70_CONTAINER_TOPOLOGY.md docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md frontend/Dockerfile.read-only-demo frontend/container/check-demo-build.cjs frontend/container/check-demo-build.test.cjs frontend/e2e/read-only-demo.spec.ts scripts/validate_demo_compose.py
```

This plan is not executed here. No staging, commit, push, tag, deployment,
container startup, cloud action or Phase71. A fresh independent review and later
user-controlled runtime acceptance of this exact patch remain separate gates.
