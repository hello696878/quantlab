# Read-Only Synthetic Demo and Deployment Hardening v1

Current: 2026-10-18, Phase 70, `4.88.0-dev`. This is local implementation plus
a hosting plan. Nothing has been hosted, certified, or provisioned. Phase 69
is frozen at `1062ec48b4128af867ab5a3329951511ebff285c`, tree
`3a06cbef017e1828781d2e6861c17eecf4afd014`. Its user-supplied final-document CI
`39091756914` succeeded in both jobs; it is not Phase 70 verification.

## Local Container Continuation (2026-10-18)

The separate `compose.read-only-demo.yml` now declares a local-only hardened
topology. It is standalone, never an override for docker-compose.yml. Dedicated
Dockerfile.read-only-demo recipes do not change ordinary development recipes.
See [post-review topology evidence](PHASE_70_CONTAINER_TOPOLOGY.md) for exact
baseline, static checks, inventory, limitations and review decision. The completed
PHASE_70_REVIEW.md remains historical evidence, not review of this continuation.

Two serving containers use numeric UID/GID 10001, cap_drop ALL,
no-new-privileges, read-only roots, one declared writable application tmpfs
at /tmp (64 MiB, noexec/nosuid/nodev),
one CPU each, backend/frontend memory 512/768 MiB, PID limits 96/128 and
nofile 1024. Backend has no host port, one worker, no raw access log and no
proxy-header trust. Its /corpus named volume is read-only with nocopy. It joins
only an internal bridge; frontend joins that bridge and an edge bridge and
publishes only 127.0.0.1:3180 (operator-selectable unprivileged port).
Both stdlib health probes check readiness/policy/pinned corpus identity. Local
Docker logs are capped at two 5 MiB files per service. No automatic restart,
preparation dependency, seed, migration or repair is added.

These are implemented declarations and static policy checks, NOT observed
Docker Desktop enforcement. Internal backend membership is not a measured
egress firewall; the frontend edge bridge permits outbound traffic. No public
ingress/TLS/authentication, multi-user isolation, blanket secret exclusion or
production guarantee is supplied. Retain all restrictions if runtime fails.

Explicit offline preparation reuses the backend image with networking disabled,
all capabilities dropped, read-only root and a NEW writable named volume.
Docker's empty-volume copy-up from the image's /corpus directory supplies owner
10001:10001; the preparation command checks that owner and an empty volume
before invoking existing app.demo_corpus.prepare. If copy-up/ownership differs
on a platform, STOP: do not run serving as root, loosen permissions, repair or
silently chown existing data. Actual copy-up and non-root startup remain pending.
Serving uses nocopy and never initializes an empty volume. Interrupted preparation
retains its owned partial volume; only fully verified manifest publication can
complete. Do not reuse the earlier Windows acceptance corpus.

The frontend builder uses declared package/lock manifests with engine-strict
Node 24 dependency installation, explicitly bakes BACKEND_URL=http://demo-backend:8000
and NEXT_PUBLIC_QUANTLAB_EXPECTED_MODE=read_only_demo, then validates the compiled
route manifest. The final image retains .next/routes-manifest.json and
demo-build-contract.json. That contract records build inputs/compiled rewrite,
not proof of every client bundle: the later browser gate still verifies actual UI.
Runtime env cannot repair an old build. Runtime image has no host bind mounts.
Build COPY sources are explicit; local .env/.env.local, .next and node_modules
are excluded. Build from the exact Git archive below, not an arbitrary live
directory. Static patterns alone are not a complete context/layer secret audit.

### Later User-Controlled Container Acceptance

The following PowerShell procedure is NOT executed during implementation.
Run only after independent review and a user-created commit. Keep all evidence,
including failures. No cloud/public/provider request is part of these commands.
Use an existing supported Node and project Python; do not install host packages.
Replace the approved commit placeholder, then execute each block in the same
shell. A nonzero native exit stops the sequence; capture diagnostics and do not
remove a failed restriction. No cleanup/volume deletion is prescribed.

```powershell
$ErrorActionPreference = 'Stop'
$Repo = 'C:\quantlab'
$Expected = '<full user-approved topology commit>'
if ($Expected -notmatch '^[0-9a-f]{40}$') { throw 'Set an approved exact commit' }
Set-Location $Repo
if ((git rev-parse HEAD).Trim() -cne $Expected -or (git status --porcelain)) { throw 'Require exact clean source' }
$Token = [guid]::NewGuid().ToString('N')
$Evidence = Join-Path $env:TEMP "quantlab-p70-container-$Token"
New-Item -ItemType Directory -Path $Evidence -ErrorAction Stop | Out-Null
New-Item -ItemType File -Path "$Evidence/empty.env" -ErrorAction Stop | Out-Null
function Run([string]$Name, [string]$Exe, [string[]]$ArgumentList) {
    $Watch = [Diagnostics.Stopwatch]::StartNew()
    $Output = & $Exe @ArgumentList 2>&1
    $Code = $LASTEXITCODE
    $Output | Out-File -LiteralPath "$Evidence/$Name.log" -Encoding utf8
    [pscustomobject]@{name=$Name;exe=$Exe;args=$ArgumentList;exit=$Code;seconds=$Watch.Elapsed.TotalSeconds} |
        ConvertTo-Json -Compress | Add-Content -LiteralPath "$Evidence/executions.jsonl" -Encoding utf8
    if ($Code -ne 0) { throw "$Name failed ($Code); preserve logs and inspect, do not relax restrictions" }
    return ($Output -join "`n")
}
$Tree = (Run 'source-tree' git @('rev-parse', 'HEAD^{tree}')).Trim()
$Engine = (Run 'docker-version' docker @('version', '--format', 'json')) | ConvertFrom-Json
if ($Engine.Server.Os -cne 'linux') { throw 'Require a Linux Docker engine' }
$null = Run 'compose-version' docker @('compose', 'version')
$Archive = "$Evidence/source.tar"
$null = Run 'source-archive' git @('-c','core.autocrlf=false','archive','--format=tar',"--output=$Archive",$Expected)
Get-FileHash -LiteralPath $Archive | Format-List | Out-File "$Evidence/archive-sha256.txt"
$Source = "$Evidence/source"
New-Item -ItemType Directory -Path $Source -ErrorAction Stop | Out-Null
$null = Run 'extract-source' tar @('-xf',$Archive,'-C',$Source)
$Project = "p70-$Token"
$Volume = "quantlab-p70-$Token"
$Tag = "p70-$Token"
$BackendImage = "quantlab-demo-backend:$Tag"
$FrontendImage = "quantlab-demo-frontend:$Tag"
$Python = "$Repo/.venv/Scripts/python.exe"
$Node = (Get-Command node -ErrorAction Stop).Source # choose an existing supported executable
$null = Run 'node-engine' $Node @('-e',"const [a,b]=process.versions.node.split('.').map(Number);if(a!==24||b<20)process.exit(2);console.log(process.version)")
$Names = Run 'volume-collision' docker @('volume','ls','--filter',"name=^$Volume`$",'--format','{{.Name}}')
if ($Names.Trim()) { throw 'Destination volume already exists' }
$null = Run 'create-volume' docker @('volume','create','--driver','local','--label','quantlab.phase=70','--label',"quantlab.owner=$Token",$Volume)
$OwnedVolume = @(Run 'new-volume-ownership' docker @('volume','inspect',$Volume) | ConvertFrom-Json)
if ($OwnedVolume.Count -ne 1 -or $OwnedVolume[0].Name -cne $Volume -or
    $OwnedVolume[0].Driver -cne 'local' -or $OwnedVolume[0].Scope -cne 'local' -or
    $OwnedVolume[0].Labels.'quantlab.phase' -cne '70' -or
    $OwnedVolume[0].Labels.'quantlab.owner' -cne $Token -or
    ($null -ne $OwnedVolume[0].Options -and @($OwnedVolume[0].Options.PSObject.Properties).Count -ne 0)) {
    throw 'Require the newly labelled ordinary local volume with no driver options; do not mount or repair it'
}
$null = Run 'build-backend' docker @('build','--pull','-f',"$Source/backend/Dockerfile.read-only-demo",'-t',$BackendImage,"$Source/backend")
$Offline = @('run','--read-only','--network','none','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges:true',
    '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777','--cpus','1','--memory','512m','--pids-limit','96')
$Prepare = @'
import os
from pathlib import Path
from app.demo_corpus import prepare
p = Path('/corpus')
assert os.getuid() == os.getgid() == 10001
assert p.stat().st_uid == p.stat().st_gid == 10001
assert not list(p.iterdir()), 'Refuse a nonempty or interrupted destination'
print(prepare(p / 'v1'))
'@
$Id = (Run 'prepare' docker ($Offline + @('--name',"$Project-prep",'--mount',"type=volume,source=$Volume,target=/corpus",'--entrypoint','python',$BackendImage,'-B','-c',$Prepare))).Trim()
if ($Id -notmatch '^[0-9a-f]{64}$') { throw 'Preparation did not return exactly one full identity' }
$ReadMount = "type=volume,source=$Volume,target=/corpus,readonly,volume-nocopy"
$Verified = (Run 'verify' docker ($Offline + @('--name',"$Project-verify",'--mount',$ReadMount,'--entrypoint','python',$BackendImage,
    '-B','-m','app.demo_corpus','verify','--source','/corpus/v1','--expected-id',$Id))).Trim()
if ($Verified -cne $Id) { throw 'Verification identity mismatch' }
$env:QL_DEMO_IMAGE_TAG=$Tag; $env:QL_DEMO_VOLUME=$Volume; $env:QL_DEMO_CORPUS_ID=$Id; $env:QL_DEMO_PORT='3180'
$Compose = @('compose','--env-file',"$Evidence/empty.env",'--project-name',$Project,'-f',"$Source/compose.read-only-demo.yml")
$Effective = Run 'effective-compose' docker ($Compose + @('config','--format','json'))
[IO.File]::WriteAllText("$Evidence/effective-compose.json",$Effective)
$null = Run 'effective-policy' $Python @('-B',"$Source/scripts/validate_demo_compose.py","$Evidence/effective-compose.json",'--repo',$Source)
$null = Run 'build-frontend' docker ($Compose + @('build','--pull','demo-frontend'))
$null = Run 'images' docker @('image','inspect',$BackendImage,$FrontendImage)
$null = Run 'volume' docker @('volume','inspect',$Volume)
```

Keep image IDs and RepoDigests as actually reported (local tags may have no
RepoDigest). Mutable base tags are not a pin or a security audit. The extracted
archive identifies the build source; do not claim labels alone prove it.
The static placeholder corpus ID used during implementation is NOT a prepared
corpus. Only the actual $Id above may be used to start these services.

```powershell
$Inventory = @'
import hashlib,json,os
from pathlib import Path
p=Path('/corpus/v1')
assert sorted(x.name for x in p.iterdir()) == ['corpus.json','demo.db']
print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'files':[
 {'name':x.name,'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()}
 for x in sorted(p.iterdir())]},sort_keys=True))
'@
$Before = Run 'corpus-before' docker ($Offline + @('--name',"$Project-before",'--mount',$ReadMount,'--entrypoint','python',$BackendImage,'-B','-c',$Inventory))
$null = Run 'start' docker ($Compose + @('up','-d','--no-build','--pull','never','--wait','--wait-timeout','120'))
$Backend = (Run 'backend-id' docker ($Compose + @('ps','-q','demo-backend'))).Trim()
$Frontend = (Run 'frontend-id' docker ($Compose + @('ps','-q','demo-frontend'))).Trim()
if (!$Backend -or !$Frontend) { throw 'Missing serving container' }
$null = Run 'runtime-inspect' docker @('inspect',$Backend,$Frontend)
$null = Run 'network-inspect' docker @('network','inspect',"${Project}_demo_private","${Project}_demo_edge")
$null = Run 'ports' docker ($Compose + @('ps','--format','json'))
$null = Run 'runtime-python' docker @('exec',$Backend,'python','-c',"import sys,sqlite3,importlib.metadata as m;print(sys.version);print(sqlite3.sqlite_version);print({k:m.version(k) for k in ['fastapi','starlette','pydantic','numpy','pandas','uvicorn']})")
$null = Run 'runtime-node' docker @('exec',$Frontend,'node','-p',"JSON.stringify({node:process.version,next:require('next/package.json').version})")
$null = Run 'compiled-manifest' docker @('exec',$Frontend,'node','-e',"const fs=require('fs');console.log(JSON.stringify({contract:JSON.parse(fs.readFileSync('demo-build-contract.json')),routes:JSON.parse(fs.readFileSync('.next/routes-manifest.json')),build_id:fs.readFileSync('.next/BUILD_ID','utf8')}))")
$BackendBoundary = @'
import errno,json,os
from pathlib import Path
assert os.getuid()==os.getgid()==10001
for p in ('/app/.demo-write-probe','/corpus/.demo-write-probe'):
 try:
  f=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 except OSError as e:
  assert e.errno in (errno.EROFS,errno.EACCES)
 else:
  os.close(f)
  raise AssertionError('Unexpected write succeeded; retain evidence and stop')
print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'status':Path('/proc/self/status').read_text(),'mounts':Path('/proc/self/mountinfo').read_text(),'routes':Path('/proc/net/route').read_text()}))
'@
$null = Run 'backend-boundary' docker @('exec',$Backend,'python','-c',$BackendBoundary)
$null = Run 'frontend-boundary' docker @('exec',$Frontend,'node','-e',"const fs=require('fs');if(process.getuid()!==10001||process.getgid()!==10001)process.exit(2);try{const f=fs.openSync('/app/.demo-write-probe','wx');fs.closeSync(f);throw Error('Unexpected write; retain evidence')}catch(e){if(!['EROFS','EACCES'].includes(e.code))throw e}console.log(JSON.stringify({uid:process.getuid(),gid:process.getgid(),status:fs.readFileSync('/proc/self/status','utf8'),mounts:fs.readFileSync('/proc/self/mountinfo','utf8'),routes:fs.readFileSync('/proc/net/route','utf8')}))")
```

Inspect the retained JSON before proceeding: actual serving UID/GID 10001,
CapEff/CapPrm/CapBnd zero and NoNewPrivs 1, HostConfig.ReadonlyRootfs true,
CapDrop ALL, SecurityOpt no-new-privileges, 1e9 NanoCpus, memory/PID/nofile
budgets as declared, /tmp as the only configured writable application mount,
corpus Mounts.RW false and no frontend application-data/cache mounts. Enumerate
Docker-managed /dev, /dev/shm, /proc and other pseudo-filesystems separately;
read-only root and a tmpfs declaration do not prove every process-visible path
is read-only. Reject unexpected host/data/socket mounts. Verify correct
commands/factory and one worker, backend only on
internal demo_private and no PortBindings, frontend only 127.0.0.1 with no IPv6
wildcard publication. Record actual health/state/logging settings. Default
image entrypoint and init are not proof of UID; inspect the running process.
If Docker Desktop normalizes or fails to enforce a setting, retain that actual
result and STOP for a narrow correction. Do not reduce controls to pass.
Private networking alone is not proof against all egress/native/host pathways;
no external connectivity probe or provider request is authorized here.

```powershell
$Probe = @'
import hashlib,json,sys,urllib.request,urllib.error
base,identity=sys.argv[1:]
def get(path,method='GET'):
 req=urllib.request.Request(base+path,data=None if method=='GET' else b'not parsed',method=method,headers={'X-QuantLab-Expected-Corpus':identity})
 try:
  with urllib.request.urlopen(req,timeout=5) as r: return r.status,r.read(65537)
 except urllib.error.HTTPError as e: return e.code,e.read(65537)
out={}
for path in ['/capabilities','/ready','/saved-backtests','/saved-backtests/1','/research-explainer/saved-backtests/1']:
 status,body=get(path)
 assert status==200 and len(body)<=65536
 obj=json.loads(body)
 if path=='/capabilities': assert obj['mode']=='read_only_demo' and obj['corpus_id']==identity and obj['policy']=='read_only_demo_v1'
 if path=='/ready': assert obj=={'status':'ready','policy':'read_only_demo_v1','corpus_id':identity}
 out[path]=hashlib.sha256(body).hexdigest()
for method,path in [('POST','/saved-backtests'),('DELETE','/saved-backtests/1'),('POST','/custom-strategies/import'),('POST','/backtest/sma-crossover'),('GET','/globe/markets'),('GET','/not-approved')]:
 status,body=get(path,method)
 assert status==403
 out[method+' '+path]=status
print(json.dumps(out,sort_keys=True))
'@
$Direct = Run 'direct-proof' docker @('exec',$Backend,'python','-c',$Probe,'http://127.0.0.1:8000',$Id)
$Proxy = Run 'proxy-proof' $Python @('-c',$Probe,"http://127.0.0.1:$env:QL_DEMO_PORT/api",$Id)
if ($Direct -cne $Proxy) { throw 'Direct/proxy approved material differs' }
# Run exactly one Edge scenario; no server-start or old seed harness.
$env:E2E_BASE_URL="http://127.0.0.1:$env:QL_DEMO_PORT"
$env:E2E_READ_ONLY_DEMO_CORPUS_ID=$Id
$env:E2E_READ_ONLY_DEMO_PROXY_ONLY='1'
Remove-Item Env:E2E_READ_ONLY_DEMO_BACKEND_URL -ErrorAction SilentlyContinue
$env:E2E_BROWSER_CHANNEL='msedge'
$env:PLAYWRIGHT_JUNIT_OUTPUT_FILE="$Evidence/edge.xml"
Set-Location "$Repo/frontend"
$null = Run 'edge' $Node @('node_modules/@playwright/test/cli.js','test','e2e/read-only-demo.spec.ts','--reporter=list,junit','--output',"$Evidence/browser-results")
Set-Location $Repo
$After = Run 'corpus-after' docker @('exec',$Backend,'python','-c',$Inventory)
if ($After -cne $Before) { throw 'Owned corpus bytes/inventory changed' }
$null = Run 'service-logs' docker ($Compose + @('logs','--no-color','--tail','200'))
$null = Run 'final-runtime-inspect' docker @('inspect',$Backend,$Frontend)
$FinalStatus = Run 'final-git-status' git @('status','--porcelain')
if ($FinalStatus.Trim()) { throw 'Source/index changed during acceptance' }
$FinalHead = Run 'final-head' git @('rev-parse','HEAD','HEAD^{tree}')
if ($FinalHead -cne "$Expected`n$Tree") { throw 'Source identity changed during acceptance' }
```

Require one JUnit case, no failures/errors/skips, browser exit0, all preceding
process exits0 and exact corpus-before/after equality. The explicit proxy-only
browser annotation means it DOES NOT perform direct-backend probes; direct-proof.log
and its matching proxy proof are mandatory separate evidence. Default ordinary
loopback E2E mode still requires both origins and performs both probes. Never
publish a backend host port merely to accommodate browser tooling. If any step
fails, retain executions.jsonl and gather `docker ... logs` / `docker inspect`
for the owned containers before stopping. Do not retry successful gates for a
cleaner summary, fabricate absent exits, or claim a build closed runtime gates.

### Stopped Docker Volume Backup and Restore

Stop both serving containers explicitly (`docker` with `$Compose + @('stop')`)
and inspect both container states as stopped before copying; --stopped remains
an operator attestation. Allocate a NEW GUID/token/name for each destination;
repeat the volume collision, local-driver/no-options and ownership-label checks
above before its first mount. Source and destination names must differ. In the
non-root offline operation, check actual UID/GID 10001, destination /corpus owner
10001:10001 and an empty destination volume root before copying. A driver,
label, owner or emptiness mismatch stops without chown, reuse or cleanup.
Reuse the same non-root `$Offline` image operation: source volume at /source
read-only/nocopy, destination at /corpus with empty-volume copy-up; run
`python -B -m app.demo_corpus copy-stopped --source /source/v1 --destination /corpus/v1 --expected-id $Id --stopped`.
Verify the new volume with an RO/nocopy mount and compare DB/manifest hashes
before selecting its NEW external volume name in Compose. Restore is the same
operation from stopped backup to another NEW volume. Destination existence or
ownership mismatch is a stop, not permission to overwrite/chown/repair. Preserve
the old volume and evidence. No live WAL copy, checkpoint, sidecar deletion,
HTTP reset, automatic migration or general user-DB backup service is implemented.

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
hardened demo. The new standalone file documented above does not inherit those
ports/mounts. No Docker builds/servers ran during either implementation task.

Declared context exclusions cover backend developer env patterns, data/,
SQLite/sidecar/log patterns and common key directories; frontend env variants
are excluded except .env.example. Static tests check specified rule membership,
not all Docker pattern matching, arbitrary private files or resulting image layers.
They are not an executed Docker context/image inspection
or a replacement for secret scanning and deployment-runtime verification.

The standalone local topology now declares non-root UID/GID, dropped
capabilities, no-new-privileges, read-only root/corpus, bounded application /tmp,
loopback frontend, private backend and CPU/memory/PID/nofile limits. Before
acceptance, independently verify their actual running enforcement and one-worker
startup. Connection/ingress budgets, complete network egress denial and public
hosting controls remain future work. Size limits with measurements, not a certification.
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

The [product review](PHASE_70_REVIEW.md) and
[product implementation](PHASE_70_IMPLEMENTATION.md) remain historical evidence.
The container implementation records the user's pre-hardening CI 5254/18 skips,
build and Edge acceptance as user-attested, not rerun/retrieved or acceptance of
this topology. See [container implementation evidence](PHASE_70_CONTAINER_TOPOLOGY.md)
and the [independent container review](PHASE_70_CONTAINER_REVIEW.md).
Exact-container-review-commit Python 3.11/Linux CI, new image builds/proxy-manifest
inspection, prepared-container browser acceptance and actual hardened runtime
verification remain separate gates. Phase 69 physical-link checks were not repeated.

`frontend/e2e/read-only-demo.spec.ts` is for later user execution against
already-running loopback services. Prepare the corpus BEFORE serving. Default
mode requires E2E_READ_ONLY_DEMO_CORPUS_ID, E2E_READ_ONLY_DEMO_BACKEND_URL and
E2E_BASE_URL. Explicit proxy-only mode sets E2E_READ_ONLY_DEMO_PROXY_ONLY=1 with
no backend URL; separate direct container-exec proof above remains mandatory.
It verifies direct/proxy mode/readiness/identity, mutation/provider refusals, real
browse/detail/pinned download, no automatic mutation/external browser requests and
bounded viewports. It never calls an HTTP seed/reset or the old writable harness.
Discovery is not browser execution. Nothing here authorizes hosting or Phase 71.
