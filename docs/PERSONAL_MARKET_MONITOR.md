# Personal Market Monitor v1

## Scope and Workflow

The immediate product priority is personal market awareness: markets, rates, oil,
companies, announcements, world headlines and the next official scheduled event.
The proposed EMA increment is deferred. Existing quant/research workspaces remain
accessible; this addition does not change their calculations or persistence.

After local capabilities are validated, the app opens `monitor`. Add instruments,
move them up/down or remove them; Refresh checks the selected sources. Select a
company for its daily observation and SEC filings. Filter the timeline by source,
official/publisher category, or the explicitly labeled company-name/ticker text
match. Follow original links; use the sidebar/search to return to existing tools.
`home` remains the research overview and is not repurposed for the read-only demo.

No fake observations, demo performance or illustrative Globe fallback is used.
Synthetic fixtures exist only in tests. Monitor is not investment advice, an
exchange feed, a 24/7 collector, an alerting service or an execution system.

## Catalog and Source Semantics

| Canonical ID | Mapping | Kind / displayed unit |
|---|---|---|
| `sp500` | Yahoo `^GSPC` | S&P 500 index / index points (USD metadata) |
| `nasdaq100` | Yahoo `^NDX` | Nasdaq-100 index / index points (USD metadata), not NQ or US100.cash |
| `taiwan` | Yahoo `^TWII` | Taiwan Weighted Index / index points (TWD metadata) |
| `nikkei225` | Yahoo `^N225` | Nikkei 225 / index points (JPY metadata) |
| `gold_reference` | Yahoo `GC=F` | Futures reference / USD per troy ounce |
| `wti_reference` | Yahoo `CL=F` | Futures reference / USD per barrel |
| `brent_reference` | Yahoo `BZ=F` | Futures reference / USD per barrel |
| `nvda` | Yahoo NVDA; SEC 0001045810 | NVIDIA / USD per share |
| `msft` | Yahoo MSFT; SEC 0000789019 | Microsoft / USD per share |
| `aapl` | Yahoo AAPL; SEC 0000320193 | Apple / USD per share |
| `treasury2y` | Treasury `BC_2YEAR` | Daily par yield / percent |
| `treasury10y` | Treasury `BC_10YEAR` | Daily par yield / percent |
| `treasury30y` | Treasury `BC_30YEAR` | Daily par yield / percent |
| `treasury10y2y` | Same-date 10Y minus 2Y | Yield spread / basis points |
| `eia_wti` | EIA `RWTC` | Cushing WTI spot FOB / USD per barrel |
| `eia_brent` | EIA `RBRTE` | Europe Brent spot FOB / USD per barrel |

Default watchlist: S&P 500, Nasdaq-100, Taiwan, WTI futures reference and NVIDIA.
At most 16 unique known IDs are accepted. Yahoo symbol, currency and instrument
kind must match the catalog; a mismatched response is unavailable, not relabeled.
SEC CIK/ticker pairs were checked against official company metadata.

Yahoo uses five days of `interval="1d"` history with `auto_adjust=True`,
`back_adjust=False`, `actions=False`. Values are the latest available **adjusted
daily close**, not a total-return series or a completed-session guarantee. Date-only
observations stay date-only, with available provider timezone metadata. No
guaranteed delay or realtime claim. Change is percent against the prior available
comparable observation; without one, change is unavailable, not zero. EIA signed
spot prices remain actual signed values; percent change is unavailable when the
prior value is zero or negative. Nonpositive
Yahoo observations are currently refused, including any exceptional negative
futures price; no alternate value is substituted.

GC=F/CL=F/BZ=F are provider futures references, not spot, a specified expiry or a
broker CFD. EIA spot entries are separate. Treasury yields are not the Fed policy
rate. Yield changes are `(latest - prior) * 100` bps; the spread is computed only
from two yields on the same date, with its change also in bps. Missing values
remain missing. Two recent calendar months are requested, including year rollover.

| Other source | Coverage | Cadence / limits |
|---|---|---|
| Federal Reserve RSS | Monetary-policy releases | Event; up to 30 retained items |
| ECB RSS | Press releases, speeches, interviews, press-conference transcripts | Event; up to 30 |
| BBC World RSS | Publisher world headlines, not official announcements | Event; up to 30 |
| SEC submissions | Selected issuer's 10-K, 10-Q, 8-K and amendments | Event; up to 20 relevant recent filings |
| FOMC calendar | Current/next-year upcoming official meeting date ranges | Date-only; up to 12 events |
| EIA schedule | Official weekly release-schedule link | Link only; no guessed Wednesday schedule |

RSS text is rendered as text, source-host HTTPS links are validated, and items
deduplicate by GUID/link. A structurally valid empty RSS channel is a successful
empty result; malformed or nonempty wholly unusable entries remain failures.
Missing publication time stays unavailable. Company
headline text matching is neither issuer attribution nor comprehensive/causal
coverage. SEC requires matching issuer identity and aligned filing arrays;
document paths and optional timezone-aware acceptance timestamps are validated
for the supported forms. Other forms are skipped after global issuer/array
validation, so their undisplayed document paths cannot invalidate supported filings.
No full articles, bulk filing history, earnings estimates, CPI/payroll dates or
invented announcement times are added.

## Setup and Boundaries

Use the existing project environment/dependencies. Frontend engines require
Node `>=24.20.0 <25` and npm `>=11 <12` (packageManager declares npm 11.17.0).
The implementation checks used discovered Node 24.22.1 and the invoked npm CLI
11.12.1, which satisfies the engine. No installation or dependency change occurred.

Optional settings belong in the **backend process environment**, never browser
storage or committed credentials. Replace these placeholders with existing valid
configuration before starting/restarting the backend:

```powershell
$env:MARKET_MONITOR_EIA_API_KEY = "<existing EIA API key>"
$env:MARKET_MONITOR_SEC_USER_AGENT = "<application or organization> <your real contact email>"
```

Missing EIA key or missing/invalid SEC identification yields `not_configured`
and zero requests to that adapter. Do not invent a contact. The local syntactic
check cannot verify contact ownership; the operator is responsible for it.
EIA uses encoded query parameters required by its API; provider exceptions/URLs
are not exposed, and this adapter does not use httpx INFO URL logging for keys.
Do not enable external transport/proxy logging that records secret query strings.

User-controlled local startup (two terminals):

```powershell
Set-Location C:\quantlab\backend
& C:\quantlab\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

```powershell
Set-Location C:\quantlab\frontend
npm run dev
```

Open `http://localhost:3000`. Existing `/api/:path*` rewriting proxies to the
configured backend; no proxy configuration change was needed. **Ordinary FastAPI
startup initializes the research database in its lifespan.** The database-free
Monitor router does not change that. This task never started the real backend.

Only the normal app registers GET `/market-monitor/catalog` and GET
`/market-monitor/snapshot?ids=sp500,nvda&company=nvda`. Empty `ids=` is allowed;
unknown/duplicate/oversized IDs or unsupported company return 422. No user URL or
arbitrary provider symbol is accepted. No Monitor mounting/request occurs during
pending, failed or demo ServingGate states; no demo endpoint allowlist was extended.

Watchlist key `quantlab.monitor.watchlist.v1` holds `{version:1,ids:[...]}`.
Shape/version/known IDs/uniqueness/length are validated. An empty list is valid;
hydration never writes defaults. Corrupt/unavailable storage and quota failures
show a warning while preserving usable in-memory choices. Only explicit watchlist
edits write this key, not other settings or database tables. Company selection is
session-local and is not another persisted preference. Clearing the selected
company also clears company-only headline matching; switching between companies
keeps that filter preference.

## Freshness, Caching and Failures

Source status (`ready`, `stale`, `unavailable`, `not_configured`) is distinct from
daily/event cadence. Responses separate observation date, publication time,
successful retrieval time and check time. Failed refreshes retain last-good values
with their original retrieval timestamp and visible failure state. Failed snapshot
requests retain the prior same-selection frontend snapshot and an error banner.
Selection identity, abort cleanup and obsolete-response guards prevent late
responses from replacing another company's/watchlist's result.

| Source/key | In-memory success TTL |
|---|---|
| Each selected Yahoo ID | 15 minutes |
| Treasury / EIA | 30 minutes each |
| Each RSS feed | 10 minutes |
| Each selected SEC issuer | 15 minutes |
| FOMC calendar | 6 hours |

All use 60-second failure backoff and shared shielded in-flight work per key.
At most four retrievals run concurrently; the finite registry bounds cache keys.
SEC is additionally serialized with at least one second between requests.
HTTP responses are capped at 2 MiB with 12-second operation timeouts and no
redirect following. HTTPX additionally has a 15-second total deadline per GET
(including streaming); Treasury makes two bounded GETs. Blocking EIA transport
runs in a disposable child with a 15-second communication timeout that kills and
waits for that child. Its request key is passed through stdin, not command-line
arguments; ordinary backend environment inheritance still applies. A consumer
timeout alone is not evidence that underlying provider work stopped. Yahoo runs
in a separate process with a 25-second outer bound,
five daily bars, memory-only cache hooks and a SQLite-refusing audit hook. These
yfinance private hooks/metadata fields are dependency-version-sensitive; an
incompatible version fails unavailable rather than falling back to disk storage.

While Monitor is active, refresh attempts occur at most every five minutes on
the visible-tab timer, or by manual action (deduplicated while pending). Reopening
or changing selection can check again, subject to backend TTLs/backoff. Refresh is
not a force-provider-cache bypass. Requests abort after 90 seconds and timers/
listeners are removed on navigation. Previously failed source data are stale;
daily observations over seven calendar days old are also flagged stale. That
heuristic is not an exchange/holiday calendar. Old news/filing age alone does not
make a freshly checked event source stale. Cache is process-local, not durable or
shared across workers. There is no background collection after leaving Monitor.

## Independent Integration Review (2026-11-10)

**READY_FOR_COMMIT**, scoped to this integration snapshot, after three independent
initial read-only review passes, coordinator confirmation/corrections, and an
independent final correction inspection. Five P2 defects were fixed: signed-price
change denominators, empty RSS refresh semantics, provider total elapsed bounds,
filtering irrelevant SEC forms before their document parsing, and clearing the
company-only filter when company selection is cleared. The mixed-form SEC case
is synthetic regression evidence, not configured live SEC acceptance.

Separate new checks: protected Monitor backend **39 passed** (terminal 4.41s,
pytest wall 4.5657s, child 5.7353s); Panel/ServingGate frontend **15 passed /2 files**
(Vitest 2.47s, process 3.1995s); TypeScript native 0 (28.7871s); one final corrected
production build native 0 (68.1600s). Guard violations are `[]`; current executable
hashes match these executions. Documentation was finalized afterward. Pre-fix
backend 5 failed /3 passed /27 deselected and frontend 1 failed /10 skipped under
a name filter are preserved separately, both exit 1. No counts are summed across
runs. No new browser, live-provider, audit, service, Docker or installation ran.

Offline replay of the captured real Fed/ECB/BBC/FOMC payloads passed through the
corrected parser (15/14/30 items; nine date ranges), with network/SQLite refused.
The earlier ten Yahoo live outcomes remain recorded source checks. That original
live smoke has no execution-source manifest; do not hash-bind it to final bytes.
The original mocked production-browser pass supports its original tested UI
behavior, not final corrected-UI or live full-stack acceptance; its E2E spec and
frontend configs were omitted from the original per-execution manifests. New
review checks record relevant configs/spec/source hashes without revealing keys.

Review evidence and exact final working-file hashes are external:
`C:\Users\jimli\AppData\Local\Temp\quantlab-monitor-review-20261110-5993eb29f75b41d881ebb01f83b40f19`.
It references the original implementation directory below. Treasury live XML,
configured EIA/SEC, live full-stack browser and inherited release gaps remain open.

## Implementation Verification and Current Source Availability

Evidence root (external, not staged):
`C:\Users\jimli\AppData\Local\Temp\quantlab-monitor-20261110-5d42829d8a0d4f379cef86031bf99496`.

Reused completed checks without rerunning after interruption; final manifests
compare tested source bytes with the final working tree. Documentation follows
the tests/build and is not represented as executable coverage. Commands, native
exits, timings, JSON/JUnit outcomes and raw manifests remain in that directory.

| Separate final selection | Result |
|---|---|
| Existing protected runner `--execute backend-final/run-config.json` on private source; pytest `backend/tests/test_market_monitor.py -vv -ra -p no:cacheprovider ...` | 28 passed /28 selected, zero skips/warnings/failures; terminal 2.21s, recorded pytest wall 2.4499s, process 3.5247s; pytest/child/outer 0/0/0 |
| Vitest new watchlist/Panel/Isolation plus existing workspaceRegistry/Sidebar/ServingGate | 75 passed /6 files, zero skips/failures; Vitest 2.43s, process 3.2441s; native/outer 0/0 |
| `tsc --noEmit --incremental false` | Exit 0, 28.9349s |
| One `npm run build`, BACKEND_URL=http://localhost:8000 | Exit 0, 74.7692s; Next 15.5.28; no subsequent production edit |
| Edge `playwright test e2e/market-monitor.spec.ts --workers=1 --retries=0 --reporter=json` on final production frontend | 1 passed, zero skips/flaky/failures; runner 3.0132s, wrapper 4.3770s, browser/outer 0/0; task-owned server stop 0 |

Backend coverage includes parser identity/date/bounds, missing prior observations,
Treasury missing values/same-date bps, feed safety, SEC array alignment, missing
configuration/zero requests, per-source cache/failure isolation and cancellation,
422 bounds, import side effects, worker SQLite refusal and demo policy. Frontend
coverage includes storage safety/empty lists, watchlist editing, status rendering,
late responses/cleanup, company links, ServingGate isolation and existing registry/
navigation contracts. This is not a complete backend/frontend suite or Python
3.11/Linux evidence: backend used project Python 3.13.5/pytest 9.0.3 on Windows.

Failed/corrected runs are retained, not summed into the final results:

- `backend-1`: temporary-directory permission/setup errors, native 1; no test-body
  passes. `backend-2`: 25 passed/native 0 with one unknown-marker warning because
  the snapshot initially omitted pyproject.toml. The external harness copy was
  corrected before `backend-final`; no project configuration was changed.
- `frontend-1`: spawn EPERM before collection/native 1; its wrapper also failed
  to print Unicode under the default console encoding. `frontend-2`: 71 passed,
  3 failed/native 1 (registry keyword casing and two ambiguous test selectors).
  `frontend-3`: 74 passed/native 0 on the earlier snapshot. `frontend-final`:
  74 passed/1 failed/native 1 (ambiguous stale-state selector); the corrected
  scoped selector passed in `frontend-corrected-final` above.
- `types-1`: exit 2 for unsupported Testing Library selector options; corrected.
  `types-final`: exit 0 on an earlier test snapshot; `types-current` above covers
  the final test selector as well. No false pass is inferred from the first run.
- First development-browser scenario failed on its final mobile navigation click
  because Next's development overlay intercepted input. Earlier interactions and
  both screenshots completed; native/outer 1/1, server stop 0. A first production
  attempt then failed at worker spawn EPERM before any test, native/outer 1/1.
  Its initial taskkill was access-denied; the same task-owned PID was stopped via
  normal approved execution, exit 0. The separately retained approved production
  attempt passed without forced clicks/overlay workarounds or another build.

The browser route responses are deliberately synthetic and all unexpected API/
external requests are refused. Desktop/mobile screenshots were inspected; the
scenario tests add/reorder/remove, company selection, refresh, no page-width
overflow, and Backtest/Monitor navigation. It does not verify live full-stack data
or all research workflows. All task-owned frontend servers were stopped.

| Source | Actual bounded outcome |
|---|---|
| Yahoo | **Verified live**: all ten catalog symbol/currency/instrument-kind mappings; actual date/timezone metadata and observations retained in `live-smoke.json` |
| Fed / ECB / BBC | **Verified live payload parsing**: bounded HTTP 200 responses retained, then parsed through the adapter (15 /14 /30 items). Not merely an XML content-type check |
| FOMC | **Verified live payload parsing**: nine upcoming date ranges, no invented times; first 2026-12-08 to 2026-12-09 |
| Treasury | **Unavailable live**: ReadTimeout. Namespace/missing-value/date/bps behavior is deterministic-test-only; the requested live XML-structure confirmation remains open |
| EIA | **Not configured**, zero provider requests; parser deterministic-test-only |
| SEC | **Not configured**, zero provider requests; curated CIKs checked against official metadata, submission parser deterministic-test-only |

The backend runner's source-copy and isolated `--execute` entry installed test-owned
SQLite boundaries before application imports; recorded violations `[]`, with live
and snapshot source checks true. The task did not invoke the runner's active-DB
snapshot path, nor open/read/hash/copy/migrate/modify the active research DB.
Live market workers refused SQLite before importing yfinance. No normal FastAPI
service, installation, Docker, audit, backup or external alert integration ran.

## Review Inventory and Remaining Work

**7 modified tracked files, all unstaged:**

```text
STOP_POINT.md
backend/app/main.py
docs/BLUEPRINT_STATUS_MATRIX.md
frontend/src/app/page.tsx
frontend/src/components/AppShell.tsx
frontend/src/components/Sidebar.tsx
frontend/src/lib/workspaceRegistry.ts
```

**19 new files, all untracked:**

```text
backend/app/market_monitor/__init__.py
backend/app/market_monitor/catalog.py
backend/app/market_monitor/eia_worker.py
backend/app/market_monitor/market_worker.py
backend/app/market_monitor/models.py
backend/app/market_monitor/parsers.py
backend/app/market_monitor/providers.py
backend/app/market_monitor/service.py
backend/app/market_monitor_routes.py
backend/tests/test_market_monitor.py
docs/PERSONAL_MARKET_MONITOR.md
frontend/e2e/market-monitor.spec.ts
frontend/src/components/MarketMonitorIsolation.test.tsx
frontend/src/components/MarketMonitorPanel.test.tsx
frontend/src/components/MarketMonitorPanel.tsx
frontend/src/lib/marketMonitor.ts
frontend/src/lib/marketMonitorWatchlist.test.ts
frontend/src/lib/marketMonitorWatchlist.ts
frontend/src/test/fixtures/marketMonitor.ts
```

Ready for a **separately authorized commit task**, not deployment or a universal
source-availability claim. Final inventory is 26 paths (7 modified /19 new),
including the bounded EIA worker added during independent review. Treasury real XML acceptance, EIA/SEC configured live
acceptance and live full-stack browser acceptance remain open. Source layout/
provider compatibility can change, Yahoo nonpositive values are refused, RSS
matching is limited and local caches/preferences are not cross-device storage.
No financial-statement engine, earnings calendar, alerts, realtime guarantee,
background collection, EMA, authentication or cloud service is implied.

Historical release gaps remain separate: seven retained dependency findings
(2 high /4 moderate /1 low), and Phase 70 hardened-container/backup verification.
No audit rerun or remediation is claimed here. VERSION remains `4.88.0-dev`;
there is no new numbered phase, staging, commit, push, PR, merge or deployment.

Source references: [yfinance](https://ranaroussi.github.io/yfinance/),
[Treasury XML documentation](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed),
[Fed feeds](https://www.federalreserve.gov/feeds/feeds.htm),
[ECB feeds](https://www.ecb.europa.eu/home/html/rss.en.html),
[BBC World RSS](https://feeds.bbci.co.uk/news/world/rss.xml),
[EIA API](https://www.eia.gov/opendata/documentation.php),
[WTI spot](https://www.eia.gov/dnav/pet/hist/RWTCd.htm),
[Brent spot](https://www.eia.gov/dnav/pet/hist/RBRTEd.htm),
[SEC API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[SEC company mapping](https://www.sec.gov/files/company_tickers.json),
[FOMC calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm),
[EIA release schedule](https://www.eia.gov/petroleum/supply/weekly/schedule.php).
