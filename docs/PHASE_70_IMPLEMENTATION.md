# Phase 70 Implementation - Read-Only Demo and Deployment Hardening Plan v1

Date: 2026-10-18. Implementation handoff, not independent review, hosting,
release acceptance, security certification or an authorization to deploy.

## Baseline and Authority

- Repository: C:\quantlab, hello696878/quantlab.
- Initial clean `main`, HEAD `1062ec48b4128af867ab5a3329951511ebff285c`, tree
  `3a06cbef017e1828781d2e6861c17eecf4afd014`; empty index/untracked set.
- Existing annotated tag v4.87.0-deterministic-evidence-grounded-research-explainer-v1
  resolved to that exact commit/tree; never moved/recreated.
- Authorized branch created at that commit:
  `phase70-read-only-demo-deployment-hardening-plan`. No prior Phase 70 work
  or unrelated changes were present. VERSION changes to `4.88.0-dev`.
- User-supplied final-document CI `39091756914` succeeded in both jobs. It is
  inherited Phase 69 evidence, not independently retrieved or rerun here.
  Historical implementation/review/browser/build/platform evidence is untouched.
- No staging, commit, push, tag, PR, workflow trigger, deployment, provisioning,
  package installation, application service or browser execution is authorized.

## Actual Source-to-Capability Map

| Actual source | Reuse / bounded change |
| --- | --- |
| main.py ordinary lifespan/init_db and writable saved/replay helpers | Kept for local mode; dedicated demo factory never imports/registers the ordinary app |
| serving.py | Strict local/read_only_demo selection before app imports; wrong entrypoint/partial/unknown demo config refuses |
| read_only_demo.py | Independent six-route FastAPI core behind an outer deny-by-default ASGI gate; no lab/provider router |
| db.py and saved_backtests.py | Optional explicit path only for offline preparation; existing default signatures/call paths retained |
| demo_corpus.py | Operator-owned synthetic preparation, bounded RO verification and exclusive stopped copy/restore |
| Existing SMA/engine/metrics/save schema | Offline preparation of one real computed 180-bar synthetic result; no strategy or quant algorithm edits |
| Phase 69 explainer acquisition/render/verify | Optional explicit corpus path; same rollback/no-sidecar restrictions and legacy-unverified wording |
| Globe/provider configuration | Existing ordinary GETs may fetch; none is registered/called by demo, even with enabled flags |
| Existing page/shell/saved list/detail/explanation/export | Capability handshake before mounting local research; explicit demo notice, disabled mutations/unsupported views, no fake results |
| Docker context exclusions | Private env/runtime/DB material excluded; ordinary root/public-port topology is NOT claimed hardened |

See [operations, full policy and unbuilt requirements](READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md).
The approved GET surface is health, ready, capabilities, saved list, saved ID 1
and its explanation. Other methods/routes/body uploads/provider requests refuse
before dependencies/body parsing. HEAD/OPTIONS/redirect/raw-path/mount/WebSocket
variants and route drift are covered by focused tests.

Startup uses no writable factory, migrations or seeding. It verifies a pinned
explicit corpus ID through bounded actual RO SQLite transactions and compares
observed bytes across startup. Public projections are cached; subsequent reads
check source observations. No active/default DB fallback, immutable=1, WAL repair
or atomic-race/native-writer claim. Normal/demo state is instance-scoped without
changing db._db_path_override in preparation/serving. Operator prepare/copy requires
new owned paths; interrupted/invalid outputs remain retained and unservable.

The client validates serving_capabilities_v1 without a cached writable fallback.
Missing/malformed/offline/mismatched capabilities lock initial workspace loading;
this intentionally requires the paired backend and blocks old offline navigation
until verification/retry. Negotiated mode is fixed for a page lifecycle; reload
after an operator mode change, rather than silently replacing unsaved forms.
Demo reads carry a restrictive expected-corpus header. Changed/duplicate IDs
refuse before demo dispatch; the ordinary app refuses that header before saved
handlers, preventing a stale demo page from reading ordinary saved user data.
This is not HTTP mode selection or authentication. No-header local requests
retain their existing semantics.
Existing settings are not overwritten. Google font requests are removed.
Client flags do not authorize backend operations; direct/proxy refusal remains
the same backend policy. The new browser spec verifies that later, not now.

Host/origin, header/query/path/body checks, no-store/safe-error headers and one
process-local token bucket/concurrency gate are implemented. This is not auth,
distributed rate limiting, ingress/transport protection or DDoS certification.
Limits/clock/cancellation semantics are documented in the operations file.

## Verification and Preserved Attempts

Existing environments were inspected, not installed/upgraded: project .venv
executes CPython 3.13.5 (Anaconda), pytest 9.0.3, FastAPI 0.136.3,
Starlette 1.1.0, Pydantic 2.13.4, pandas 3.0.3, NumPy 2.4.6 and httpx 0.28.1
on Windows 11. Available Python 3.11.9 and uv Python 3.11.17 lack pytest;
no dependency installation was authorized. Python 3.11/Linux runtime remains
an exact-commit CI gate, not inferred from syntax or historical link evidence.

System Node 24.15.0 and bundled primary Node 24.19.0 were below project engines.
Discovery located an existing Codex runtime Node 24.21.0, used with actual npm
11.17.0, satisfying >=24.20 <25/>=11 <12. No runtime/package installation.
Exact paths/versions are retained in the external evidence, not assumed from
an older hashed runtime location.

Initial backend candidate (before final strengthening/frontend/docs/version):

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused --test backend/tests/test_read_only_demo.py
```

External evidence: `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-ftjs5eej`.
47 selected/passed, zero skips/failures/errors; 141 passed setup/call/teardown
records. Printed pytest 109.50s; machine pytest 110.82062079999014s, child
114.0883904999937s, outer 132.30921609999496s, snapshot setup 14.01688050001394s.
pytest/child/outer exits 0/0/0; source/snapshot/active-DB protection true.
Snapshot manifest SHA-256
`c92199d7a9bc48342ca509ccd22560d5b00283ff8c1e3363f2dcbc5e82f73b14`.
Later startup observations, stricter configuration/public projections, isolation,
context rules and physical corpus-path regression were NOT in that snapshot.
These 47 are not added to a later run or relabelled as final-source acceptance.

Frontend evidence root:
`C:\Users\jimli\AppData\Local\Temp\quantlab-phase70-1a14d149759`.
Initial frontend units: 273 passed /27 files, 0 failed/pending, parent 34.2036893s,
exit 0 (frontend-unit-initial.json). No separate initial byte manifest was
retained; this candidate is not a final-source byte attestation. Initial
TypeScript failed with exit 2 in 17.5515895s: four new Testing Library selectors
incorrectly used Playwright's exact option. All four were corrected without
weakening assertions. typescript.log/typescript-execution.json preserve failure.
The gate also gained an explicit, safely bounded mode-mismatch error message.
Stabilized frontend execution/source hashes and protected backend results are
recorded below. No test/build/browser result is inferred from discovery or from
these earlier snapshots.

## Final Verification Results

### Earlier Broad Snapshot (Before Conditional Corpus Reads)

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused `
  --test backend/tests/test_read_only_demo.py `
  --test backend/tests/test_saved_backtests.py `
  --test backend/tests/test_run_replay.py `
  --test backend/tests/test_run_replay_identity_review.py `
  --test backend/tests/test_run_replay_persistence_review.py `
  --test backend/tests/test_research_explainer_storage.py `
  --test backend/tests/test_research_explainer_storage_review.py `
  --test backend/tests/test_research_explainer_api_review.py `
  --test backend/tests/test_globe.py
```

Evidence: `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-etielic7`.
357 selected/passed, zero deselected/skipped/failed/errors; 1071 passed phase
records. Module counts: demo57, saved31, replay43, replay identity50, replay
persistence33, explainer storage28, storage review26, API review7, Globe82.
Printed pytest 271.60s; machine pytest 271.83310070002335s, child
274.15498309998657s, outer 282.7795238000108s, setup 4.506863000016892s.
pytest/child/outer exits 0/0/0; child evidence complete and all three protection
flags true. Snapshot manifest SHA-256:
`0323f59cf780a275920c12a43e6a9a67a6ae113e1ebe98a9d9cc614a50ada5e1`.

After this run, implementation inspection found a stale-demo-page integration
risk after backend restart. Conditional corpus headers now refuse changed demo
content and ordinary saved-data fallback before dispatch. Two backend regressions
and frontend pin/restart regressions were added; no strategy or replay/explainer
quant calculation changed. The 357 snapshot does NOT include that last fix.

### Final Affected Backend Snapshot

```powershell
& .\.venv\Scripts\python.exe -B scripts/backend_test_runner.py --scope focused `
  --test backend/tests/test_read_only_demo.py `
  --test backend/tests/test_saved_backtests.py `
  --test backend/tests/test_run_replay.py `
  --test backend/tests/test_research_explainer_storage.py `
  --test backend/tests/test_research_explainer_api_review.py
```

The default sandbox first stopped at the initial runner-result.json write with
PermissionError, host exit 1, before snapshot/test launch. Its retained empty
directory is `C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-dfln8s76`;
no pytest/child exit is available for that setup-only attempt. Normal approval
then allowed the same command to use a separate external owned evidence root:
`C:\Users\jimli\AppData\Local\Temp\quantlab-backend-focused-_kdc1ur0`.
No source/assertion change or completed-test rerun occurred between those two
attempts. The setup error is also recorded in backend-setup-permission-failure.json
under the frontend evidence root. Evidence inspection had two corrected
PowerShell array/HEAD quoting errors; neither executed tests or changed files.

**168 selected/passed, zero deselected/skipped/failed/errors**, with 504 passed
setup/call/teardown records. Exact module counts: demo59, saved31, replay43,
explainer storage28, explainer API review7. Printed pytest 182.43s; machine
pytest 182.7149152000202s, child 184.93873870000243s, outer 196.33982219998143s,
snapshot setup 6.375506099982886s. pytest/child/outer exits **0/0/0**;
child_evidence_complete, worktree_bytes_unchanged, snapshot_bytes_unchanged and
active_db_unchanged are true. SQLite violations inventory is empty. Snapshot
manifest SHA-256:
`3b19d826ddac8eba37ac2f8dde49f48de81e2b41758ec3a07479499576ec0bc8`.

Every selected node ID/outcome/duration is retained in collection.json,
phases.jsonl, junit.xml and pytest.log; counts/exits/runtime/protection are in
pytest-result.json, runner-result.json and runtime.json. Tests execute serially
on the private source snapshot with owned storage. This is not a whole-tree
suite, and the earlier 47/357 results are never added to 168.

The final run includes real prepare/verify/stopped-copy/restore, exclusive
collision/interruption, RO connection spies, no default DB fallback, startup
byte observations, method/path/mount/WebSocket drift/refusal, provider-seam
failure spies with enabled dummy flags, private/corrupt/changed corpus refusal,
controlled-clock admission/release, local/demo isolation and stale-corpus reads.
The new test_operator_corpus_link_refused_before_read executed and passed using
the existing helper's actual Windows directory link (not a mock or capability
skip). None of the five historical Phase 69 physical-link nodes was selected.
No Linux/3.11 or network-egress-firewall result is inferred from this Windows run.

### Frontend Final Candidate and Discovery

Using the discovered existing Node 24.21.0 with npm 11.17.0, cwd frontend:

```powershell
& $Node node_modules/vitest/vitest.mjs run --reporter=json --outputFile="$Evidence/frontend-pinned-unit.json"
& $Node node_modules/typescript/bin/tsc --noEmit
& $Node node_modules/@playwright/test/cli.js test e2e/read-only-demo.spec.ts --list --reporter=json
& $Node node_modules/@playwright/test/cli.js test --list --reporter=json
```

$Node was the discovered existing executable
`C:\Users\jimli\AppData\Local\OpenAI\Codex\runtimes\cua_node\a5a02988362ca169\bin\node.exe`,
not a newly installed runtime. Actual Next15.5.25, React19.2.8, Vitest4.1.11,
TypeScript5.9.3 and Playwright1.61.1 are recorded in the evidence.

Final: **277 tests passed /27 files**, zero failed/pending, parent 7.8134684s,
exit0. TypeScript exit0 in 12.5808145s. Focused/overall discovery exits0/0 in
0.4332485s/0.4563919s, **1/280 scenarios discovered, zero executed**. List-mode
JSON stats.skipped are discovery placeholders, not runtime capability skips;
test result arrays are empty. No services/builds/browser launch occurred.
frontend-pinned-source.json records exact frontend SHA-256/sizes before checks;
frontend-pinned-execution.json records unchanged source bytes across execution.
Full per-test unit assertions, discovery, logs and earlier failures remain in
the external frontend evidence root, not in source.

An earlier stabilized candidate passed 274 tests /27 files (7.0822465s, exit0),
TypeScript (15.2911857s, exit0), discovery1/280 (exits0/0). It predates corpus
pinning and is separate. An E2E-only probe change then reran TypeScript/discovery
(27.9971587s/0.8706103s/0.9291939s, exits0/0/0); it also predates the pinning fix.
Neither candidate is added to the final 277, or substituted for browser execution.

### Final Source and Hygiene Boundary

The exact pending inventory below and its later literal staging plan match.
All 39 changes remain unstaged; no unrelated changes were found. The index is
semantically empty against HEAD, not claimed raw-byte-identical (no initial raw
index hash was captured). Working files are never staged by this task.
Final whitespace/EOF, changed-link/anchor and protected-diff checks are recorded
in the external final-hygiene.json together with pending SHA-256/sizes.

The protected runner records the active database file/sidecar inventory and
byte checks within its actual configured scope. This is not a new blanket
user-directory/data-protection audit or an active-DB SQL connection. No earlier
47/49-file protection count is imported. Historical reports/frozen screenshots,
core quant calculations, conftest/runner, dependencies, workflows and Docker
runtime topology remain unchanged. No generated DBs/logs/snapshots/caches/build/
browser outputs or credentials are included in the 39-path source inventory.

Only documentation evidence/current-status edits follow the final backend run;
final executable/test bytes are checked against its manifest, and frontend
bytes against frontend-pinned-source.json. This does not relabel final prose
as the exact whole-tree snapshot that pytest executed.

## Exact Pending Inventory and Later User-Only Git Plan

Expected complete implementation scope relative to the frozen baseline:
**39 paths: 27 modified /12 new**, all intentionally unstaged. Reconcile exact
membership/classification after verification; do not force a count or use an
earlier phase's inventory. New files are source/tests/docs, not generated DBs.

| Change | Repository-relative path |
| --- | --- |
| M | CHANGELOG.md |
| M | README.md |
| M | STOP_POINT.md |
| M | TASKS.md |
| M | VERSION |
| M | backend/.dockerignore |
| M | backend/.env.example |
| M | backend/app/db.py |
| A | backend/app/demo_corpus.py |
| M | backend/app/main.py |
| A | backend/app/read_only_demo.py |
| M | backend/app/research_explainer/service.py |
| M | backend/app/saved_backtests.py |
| A | backend/app/serving.py |
| A | backend/tests/test_read_only_demo.py |
| M | docs/DEPLOYMENT_READINESS.md |
| M | docs/FORWARD_ROADMAP_PHASES_63_70.md |
| A | docs/PHASE_70_IMPLEMENTATION.md |
| A | docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md |
| M | docs/VERSION_MANIFEST.md |
| M | frontend/.dockerignore |
| M | frontend/.env.example |
| A | frontend/e2e/read-only-demo.spec.ts |
| M | frontend/src/app/layout.tsx |
| M | frontend/src/app/page.tsx |
| M | frontend/src/components/AppShell.tsx |
| A | frontend/src/components/ReadOnlyDemo.tsx |
| M | frontend/src/components/ResearchExplanationPanel.tsx |
| M | frontend/src/components/ResearchExplanationPanel.test.tsx |
| M | frontend/src/components/SavedBacktestDetail.tsx |
| M | frontend/src/components/SavedBacktestsList.tsx |
| A | frontend/src/components/ServingGate.test.tsx |
| A | frontend/src/components/ServingGate.tsx |
| M | frontend/src/components/Sidebar.tsx |
| M | frontend/src/components/TopBar.tsx |
| M | frontend/src/lib/api.ts |
| M | frontend/src/lib/researchExplainer.ts |
| A | frontend/src/lib/servingCapabilities.test.ts |
| A | frontend/src/lib/servingCapabilities.ts |

No staging is authorized now. This is a later USER-ONLY plan, not a script to
execute from Markdown. A later authorized task must revalidate branch/base,
complete pending/staged sets, reviewed source hashes and protections before
explicit literal staging. Never stage .next/node_modules/DBs/sidecars/logs,
evidence, snapshots, credentials or browser artifacts, and never use blanket
directory staging, --force, --renormalize or changes to Git configuration.

```powershell
git --literal-pathspecs add -- `
  'CHANGELOG.md' 'README.md' 'STOP_POINT.md' 'TASKS.md' 'VERSION' `
  'backend/.dockerignore' 'backend/.env.example' 'backend/app/db.py' `
  'backend/app/demo_corpus.py' 'backend/app/main.py' `
  'backend/app/read_only_demo.py' 'backend/app/research_explainer/service.py' `
  'backend/app/saved_backtests.py' 'backend/app/serving.py' `
  'backend/tests/test_read_only_demo.py' 'docs/DEPLOYMENT_READINESS.md' `
  'docs/FORWARD_ROADMAP_PHASES_63_70.md' 'docs/PHASE_70_IMPLEMENTATION.md' `
  'docs/READ_ONLY_DEMO_AND_DEPLOYMENT_HARDENING.md' 'docs/VERSION_MANIFEST.md' `
  'frontend/.dockerignore' 'frontend/.env.example' `
  'frontend/e2e/read-only-demo.spec.ts' 'frontend/src/app/layout.tsx' `
  'frontend/src/app/page.tsx' 'frontend/src/components/AppShell.tsx' `
  'frontend/src/components/ReadOnlyDemo.tsx' `
  'frontend/src/components/ResearchExplanationPanel.tsx' `
  'frontend/src/components/ResearchExplanationPanel.test.tsx' `
  'frontend/src/components/SavedBacktestDetail.tsx' `
  'frontend/src/components/SavedBacktestsList.tsx' `
  'frontend/src/components/ServingGate.test.tsx' `
  'frontend/src/components/ServingGate.tsx' 'frontend/src/components/Sidebar.tsx' `
  'frontend/src/components/TopBar.tsx' `
  'frontend/src/lib/api.ts' 'frontend/src/lib/researchExplainer.ts' `
  'frontend/src/lib/servingCapabilities.test.ts' `
  'frontend/src/lib/servingCapabilities.ts'
```

Later require exact staged membership/classification, cached whitespace/EOF
checks, unchanged working-file bytes, no residual intended changes and protected
data/screenshots/historical reports unchanged. No staged-tree identity is claimed
by this implementation, and no commit/push/tag follows without separate authority.

## Remaining Gates and Limitations

Fresh independent review must examine the actual diff, especially factory/startup
isolation, read-only/public projections, early ASGI refusal, cancellation/admission
scope and ordinary-mode compatibility. Exact-commit Python 3.11/Linux whole-tree
CI, user production build and baked proxy target check, one owned prepared-corpus
browser acceptance and later non-root/read-only/ingress/container-runtime checks
remain required. No complete local backend suite, audit, production/Docker build,
service, browser execution or provider request is authorized or inferred here.

Legacy explanation remains unverified; support is bounded saved SMA only. Hashes
are not authenticity/statistical/security/production certification. Corpus changes
require stopped replacement, no live WAL copying/hot migration. Global limits are
per process, not per user/distributed quotas; native/privileged races, ingress/TLS,
general user-DB online backup and disaster recovery remain unimplemented. Phase 38
deployment notes are explicitly historical, not a reason to delete user artifacts.

Expected later user subjects: `Add read only hosted demo deployment hardening plan v1`,
then `Review read only hosted demo deployment hardening plan v1`. Future user tag
`v4.88.0-read-only-hosted-demo-deployment-hardening-plan-v1` is not created here.
Implementation decision: safe to keep as the bounded local opt-in foundation,
and ready for fresh independent review of the actual unstaged diff. It is NOT
accepted for hosting or production; the separate gates above remain open.
No staging, commit, push, tag, PR, workflow trigger, cloud action, deployment or
unplanned later roadmap phase. Stop after the single implementation handoff.
