# Futures Data Ingestion Plan

> **Status: design only.** Nothing in this document is implemented by this
> document. It defines how real futures data should enter QuantLab *later*,
> so that when ingestion code is written it lands in tiny, testable commits
> on top of the storage and validation machinery that already exists.
>
> **Scope guard:** daily bars, individual contracts, ES/NQ/YM/RTY. No ML, no
> CFDs, no options, no continuous stitching, no vendor downloads yet — see
> [Non-goals](#10-non-goals).
>
> Companion docs: [INSTRUMENTS_LAYER.md](INSTRUMENTS_LAYER.md) (contract
> metadata), [AI_QUANT_ARCHITECTURE.md](AI_QUANT_ARCHITECTURE.md) (long-term
> plan this belongs to).

## 0. What already exists (do not re-plan it)

The ingestion *destination* is already built and tested. The missing piece is
only the *entry path* — code that takes data from outside the repo and hands
it to these components:

| Component | Where | Role in ingestion |
|---|---|---|
| Instrument registry | `backend/app/instruments/` + `configs/instruments/*.yaml` | Source of truth for contract metadata; every ingested row must resolve against it |
| Per-record bar schema | `backend/app/datastore/daily_bar.py` (`FuturesDailyBar`) | Record-at-a-time validation (fixtures, manual entry, future API payloads) |
| Frame schema + validation | `backend/app/datastore/store.py` (`validate_raw_futures`, `REQUIRED_COLUMNS`) | Bulk validation + normalization of incoming dataframes |
| Local store | `backend/app/datastore/store.py` (`RawFuturesStore`) | Writes one file per `(source, root, contract)` under `raw/futures/`; also implements continuous write/read (`write_continuous`/`read_continuous`) under `continuous/futures/` |
| Content hash | `raw_data_version_hash()` | Deterministic sha256 of normalized data — versioning / change detection |
| Continuous futures module | `backend/app/datastore/futures_continuous.py` | Roll schedule (`compute_roll_schedule`) **and** continuous stitching/adjustment (`build_continuous_futures`, `continuous_config_hash`) — implemented and tested, but **deferred**: not part of ingestion (§3) |
| Smoke scripts | `scripts/check_futures_metadata.py`, `scripts/run_synthetic_futures_report.py` | Read-only synthetic checks that the metadata link and P&L arithmetic work |

So "ingestion" here means exactly: **outside data → canonical dataframe →
`validate_raw_futures` → `RawFuturesStore.write_raw()`**, with instrument
metadata resolved from the registry at every step.

## 1. Why real futures data is different from crypto spot/perp data

The existing spot path (`backend/app/data.py` — a generic yfinance
`fetch_ohlcv` used for crypto and equities alike) gets away with a simple
worldview: one ticker = one continuous price series, no expiry, no roll,
adjusted closes are fine. Crypto spot/perp fits that worldview naturally
(24/7 trading, no contract lifecycle); futures break every part of it:

- **Contracts expire.** "ES" is not a price series; it is a *family* of
  contracts (ESH25, ESM25, ESU25, ESZ25, …), each with its own prices,
  volume, open interest, and a hard end date. Any "one price series per
  symbol" assumption smuggles in a stitching decision someone else made.
- **The tradable instrument changes over time.** Which contract you would
  actually have held (the "front month") rolls forward every quarter. Raw
  prices of consecutive contracts differ by a spread (carry / dividends /
  rates), so naive concatenation creates fake jumps on roll dates that look
  like tradable returns but are not.
- **Open interest exists and matters.** It is a core input to roll decisions
  (`rollover.primary_rule: volume_open_interest` in the specs). Crypto spot
  has no equivalent, and free futures feeds often omit it — that absence must
  be recorded, not papered over.
- **Sessions and calendars.** CME Globex trades ~23h with a daily break and
  exchange holidays; the "daily bar" boundary is a settlement convention in
  `America/Chicago` time, not a UTC midnight. Crypto's 24/7 UTC-day bars have
  no such subtlety.
- **Contract economics are external metadata.** A bar's P&L meaning depends
  on `contract_multiplier` / `tick_size` / `tick_value` from the instrument
  spec — data vendors don't ship these, and hard-coding them is how errors
  creep in. Crypto notional is just price × quantity.
- **Settlement vs last-trade prices.** Futures dailies usually quote the
  exchange settlement price, which is not the last trade. Different vendors
  make different choices; the `source` column exists so we never mix them
  silently.

Consequence: futures ingestion must be **per-contract first**, with the
continuous view as a separately constructed, clearly-labeled derived product
(§3).

## 2. Front-month proxy vs true per-contract data

Two different things get sold as "futures data":

- **Front-month proxy** (e.g. yfinance `ES=F`): a vendor pre-stitched series
  that always shows "the" front contract. Cheap and easy, but: the roll rule
  is the vendor's, undocumented, and unchangeable; roll-date price jumps are
  baked in (or adjusted invisibly); per-contract volume/open interest are
  gone; you cannot reconstruct what you would actually have traded. The ES
  spec's `warnings` already call this out.
- **True per-contract data**: one series per contract symbol (ESM25, ESU25,
  …), each with its own OHLCV + open interest. This is the only form from
  which a *correct* continuous series can be constructed later, because the
  roll rule (volume/OI crossover with a days-before-expiry fallback — already
  encoded in `configs/instruments/*.yaml`) needs both contracts' volume and
  OI on the overlap days.

**Position of this plan:** the canonical store holds per-contract data only.
A front-month proxy may be ingested *for comparison/sanity purposes* under
its own `source` label (e.g. `source="yfinance_frontmonth_proxy"`, stored
under a pseudo-contract name), but it must never feed roll logic or be
presented as per-contract history. Until real per-contract files arrive
(local CSVs, ingestion phase I2; proven at multi-contract scale in I3),
everything runs on synthetic fixtures (I1).

## 3. Why continuous futures stitching is deferred

Continuous construction (roll calendar → stitch → ratio/Panama back-adjust)
is deliberately **not** part of ingestion, even though the code for it
already exists and is tested (`backend/app/datastore/futures_continuous.py`:
`compute_roll_schedule` *and* the full builder `build_continuous_futures`
with ratio/Panama adjustment; `RawFuturesStore.write_continuous`/
`read_continuous` for the `continuous/futures/` namespace). What is deferred
is not writing that code — it is *running* it and wiring its output into
anything:

1. **It is a derived product, not data.** A continuous series is a function
   of (raw per-contract data × roll rule × adjustment method). Storing it as
   if it were data hides those choices. Raw-first means we can always rebuild
   continuous series when the rule changes; proxy-first means we can never
   recover the truth.
2. **Its correctness depends on inputs we don't have yet.** The volume/OI
   crossover rule needs real per-contract volume and open interest on overlap
   days. Free sources don't provide that reliably, so any continuous series
   built today would silently run on the fallback rule and *look* fine.
3. **Back-adjusted prices are fictitious in absolute level** (ratio and
   Panama both). Every consumer must know it is looking at adjusted data —
   the continuous schema's `*_raw` vs `*_adjusted` columns and
   `adjustment_method` column exist for exactly this. Wiring that through
   reports is its own careful step.
4. **Project discipline.** `futures_continuous` is on the "Do Not Do Yet"
   list (TASKS.md, CLAUDE.md). It becomes Ingestion Phase 4 (§9) only after
   per-contract ingestion is proven on synthetic and then real local data.

## 4. Required raw data fields (vendor-native, before normalization)

The minimum a source must provide **per contract, per day** to be ingestible:

| Field | Why it is required |
|---|---|
| trade date (or bar timestamp) | bar identity; converted to tz-aware UTC on normalization |
| open, high, low, close | OHLC; settlement-as-close is acceptable if the source says so |
| volume | needed for roll decisions later; 0 is valid, missing is not |
| contract identity | either a full contract symbol (`ESM25`) or (root, month, year) parts we can build one from via `spec.build_contract_symbol()` |

Nice-to-have but nullable:

| Field | Handling when absent |
|---|---|
| open interest | column stays, values NaN/None; recorded limitation — forces the fallback roll rule later |
| settlement flag / price type | if absent, note the vendor's convention in the source registration (§8) |

Everything else the canonical schema needs (`expiry`, `source`, `timezone`,
`root_symbol`) is **attached by the loader**, not expected from the vendor:
expiry comes from the spec's expiry math, `source` from the loader's own
identity, `timezone` from `spec.session.timezone`.

If a source cannot supply the minimum (e.g. daily bars without volume, or
front-month-only series), it is not a per-contract source — see §2 for the
proxy carve-out.

## 5. Normalized daily bar schema (canonical, already implemented)

Every ingested frame must pass `validate_raw_futures` and come out with
exactly these columns (`REQUIRED_COLUMNS` in `store.py`), in this order:

```text
timestamp        tz-aware UTC (naive input assumed UTC)
open/high/low/close  float64, > 0, high >= max(open,close), low <= min(open,close)
volume           int64, >= 0
open_interest    float64, nullable (NaN allowed; >= 0 where present)
root_symbol      e.g. "ES"    — must exist in the instrument registry*
contract_symbol  e.g. "ESM25" — must parse; root must match root_symbol*
expiry           tz-aware UTC datetime; must equal the spec-derived third Friday*
source           non-empty string identifying the provider ("synthetic", "csv_local", …)
timezone         exchange session timezone string ("America/Chicago")
```

Uniqueness: one row per `(contract_symbol, timestamp)`; frames are sorted by
that key. Extra vendor columns are dropped so storage and
`raw_data_version_hash` stay schema-stable.

\* Enforcement today is split, and partly missing: the registry link and
root/contract match are enforced by `FuturesDailyBar` (record-at-a-time),
not by the frame validator; the month-in-cycle and expiry-equals-spec checks
are enforced by **neither** and are new loader-side code (§6, §8 layer 2 —
the frame validator only checks that `expiry` parses). Loaders should get
both layers (§8): frame validation for bulk shape/value rules, plus the
registry cross-checks so a typo'd contract file cannot slip through.

## 6. How instrument metadata attaches to every row

**By reference, not by copy.** Every row carries `root_symbol` +
`contract_symbol`, and those two keys resolve to the full immutable spec via
`get_instrument(root_symbol)` — multiplier, tick size/value, currency,
session, rollover config, warnings. We deliberately do **not** denormalize
multiplier/tick columns into the data files:

- the spec is validated and single-source (`tick_value ==
  contract_multiplier × tick_size` is enforced at spec load);
- copies go stale and invite row-vs-spec disagreement with no arbiter;
- `scripts/check_futures_metadata.py` and the daily-bar model already prove
  the join works.

The loader's obligations are therefore: (1) `root_symbol` must load from the
registry, (2) `contract_symbol` must parse and match the root and the
instrument's `contract_months` cycle, (3) the `expiry` column must match
`spec.expiry_for_symbol(contract_symbol)` — compared on the UTC calendar
date (`expiry.date() == spec.expiry_for_symbol(...)`, the same truncation
`FuturesDailyBar` applies; the stored column value is midnight UTC of that
date). The raw column is informational; the spec is authoritative — same
stance the roll-schedule module takes. And (4) `timezone` should equal
`spec.session.timezone`. Downstream code reads
economics from the spec, never from the data file.

## 7. Where data lives on disk

All market data stays **outside git** (the repo's `.gitignore` already
ignores `data/`). Canonical local layout, using the existing
`RawFuturesStore` path scheme with a repo-root base directory:

```text
C:\quantlab\data\                       <- store base_dir (gitignored)
├── incoming\futures\<source>\...       <- vendor-native drop zone (as-received, read-only)
│     e.g. C:\quantlab\data\incoming\futures\csv_local\ESM25.csv
├── raw\futures\<source>\<root>\<contract>.parquet    <- canonical per-contract bars
│     e.g. C:\quantlab\data\raw\futures\csv_local\ES\ESM25.parquet
│     (written ONLY via RawFuturesStore.write_raw; parquet preferred, CSV fallback)
├── logs\                               <- ingestion audit log (I2) — beside, never inside, the raw tree
│     e.g. C:\quantlab\data\logs\futures_ingest.jsonl
└── continuous\futures\<source>\<root>\<adjustment>.parquet
      write/read code exists (RawFuturesStore.write_continuous) but stays
      operationally unused until ingestion phase I4
      e.g. C:\quantlab\data\continuous\futures\csv_local\ES\ratio.parquet
```

- **`incoming\`** ("raw" in the as-downloaded sense): exact files as received
  from a vendor or exported by hand. Never edited, never parsed by anything
  but its loader. Keeping originals means normalization bugs are recoverable.
  This tier is a convention only — no code knows about it yet.
- **`raw\futures\`** ("raw" in the schema sense — individual contracts,
  unadjusted prices, canonical columns): the store's namespace, one file per
  `(source, root, contract)`. This is what all downstream code reads.
- **`continuous\futures\`**: structurally separate so raw writes can never
  clobber adjusted data. Stays empty in practice for now — only tests
  exercise the write path.
- `backend\data\` remains what it is today (SQLite app DB), not market data.

Naming note: both tiers under `data\` are keyed by `source` first, so the
same contract from two providers never collides and cross-source comparison
(§8 layer 5, ingestion phase I5) is a directory diff.

## 8. How to validate incoming data

Layered, fail-loud, in this order. Layer 1 exists; layer 2 is partially
built (the registry link exists, the cycle/expiry cross-checks are new
loader code); layer 3's hash function exists but the log that records it is
I2 work; layer 4 is new; layer 5 is procedure.

1. **Frame schema** — `validate_raw_futures`: required columns, dtypes,
   positive prices, OHLC envelope (`high >= max(open, close)`,
   `low <= min(open, close)`, `high >= low`), integer non-negative volume,
   nullable non-negative OI, non-empty identity strings, no duplicate
   `(contract_symbol, timestamp)`.
2. **Registry link** — root loads from the registry; contract symbol parses
   and its root matches (already enforced per record by `FuturesDailyBar`);
   the contract month is in the instrument's `contract_months` cycle and
   `expiry` equals the spec-derived expiry (§6 obligations 2–3 — enforced by
   **no** existing validator; these two are new loader-side checks).
3. **Versioning** — record `raw_data_version_hash` of every normalized frame
   in the ingestion log (§9, I2), so re-downloads and silent vendor
   revisions are detectable as hash changes.
4. **Calendar/continuity sanity (new, small)** — per contract: timestamps
   strictly increasing; no bars after expiry; no bars on weekends; gap
   report for missing weekdays (warn, don't fail — holidays are not modeled
   in V1, so a hard business-day rule would false-positive on every CME
   holiday); flag zero-volume and OI-missing spans so data quality is
   visible per source.
5. **Cross-source checks (procedure, I5)** — same contract from two
   sources: overlapping closes should agree within a small tolerance;
   settlement-vs-last-trade differences show up here and get documented per
   source rather than "fixed".

Rejected input is rejected loudly (`RawSchemaError` / `ValidationError`) —
never auto-corrected. Fixes happen in the loader with a test, or upstream.

## 9. Phased plan

Numbering note: these are **ingestion phases, written I1–I5** — local to
this plan, and deliberately prefixed everywhere so they cannot be confused
with the repo-wide phase numbering in AI_QUANT_ARCHITECTURE.md (where the
same numbers mean entirely different work). Each phase is one or more tiny
commits; a phase starts only when the previous one is green.

### Ingestion Phase 1 (I1) — synthetic CSV fixture loader

> Status: commit 1 landed 2026-07-04 — `backend/app/datastore/csv_fixtures.py`
> (`load_futures_bars_csv` returns validated `FuturesDailyBar` records; the
> fixtures carry all 12 columns rather than loader-attached metadata, so the
> loader enforces the §6 cross-checks — month-in-cycle, expiry == spec,
> timezone == spec session — against the file's values). The store
> round-trip below is I1 commit 2, still open.

Prove the whole path with data we invent, so no download questions arise.

- Check in 2–3 tiny synthetic per-contract CSVs as **test fixtures** (e.g.
  `backend/tests/fixtures/futures_csv/ESM25.csv`, ~10 rows each, whole-tick
  prices, plausible volume/OI, one file with OI blank).
- One loader function: fixture CSV → canonical dataframe (attach
  `root_symbol`, spec-derived `expiry`, `source="synthetic"`, spec
  `timezone`) → `validate_raw_futures` → `RawFuturesStore.write_raw()` into
  a temp dir → read back → assert round-trip equality + stable version hash.
- Deliverable: the loader + pytest coverage; no new script needed yet.

### Ingestion Phase 2 (I2) — local CSV daily bars loader

> Status: read-only precursor landed 2026-07-04 —
> `scripts/check_local_futures_csv.py` validates local CSVs (default
> `data\raw\futures_daily\`, `--path` override) through the I1 loader and
> prints per-file summaries + per-symbol economics without writing anything.
> Also landed 2026-07-04: `scripts/normalize_local_futures_csv.py` — validates
> local CSVs through the same loader and, only if ALL inputs pass, writes one
> canonical-column CSV per root (sorted, round-trips through the loader) to
> `data\processed\futures_daily\` (or `--output-dir`). CSV only for now; the
> parquet-backed store ingest CLI and ingestion log below remain open.
> Also landed 2026-07-05: `scripts/report_local_futures_csv.py` — read-only
> per-root summary of the normalized output (metadata lookup + one-contract
> first-close→last-close P&L, direct == tick-based). This closes the local,
> synthetic-only workflow (validate → normalize → report) as **v0.1 stable**.

Same loader generalized to files a human places under
`C:\quantlab\data\incoming\futures\csv_local\`, plus operational trimmings:

- Explicit column-mapping config per layout (vendor CSVs never match our
  names); dates parsed with an explicit format, no silent inference.
- A small read-only-in→write-once-out CLI script
  (`scripts/ingest_local_futures_csv.py`) that prints what §8 found and
  where it wrote, mirroring the existing smoke-script style (exit 0/nonzero).
- An **ingestion log** (append-only file, e.g.
  `C:\quantlab\data\logs\futures_ingest.jsonl` — beside, never inside, the
  store-owned `raw\futures\` tree, which only `write_raw` writes to, §7):
  timestamp, source, files in, contracts written, row counts, version
  hashes, warnings. This is the audit trail everything later leans on.
- Still no network. "Real data" here means: whatever daily bars the user
  legally has as files.

### Ingestion Phase 3 (I3) — per-contract data support (breadth + lifecycle)

I2 handles one file cleanly; I3 makes multi-contract reality safe:

- Ingest many contracts per root; per-root coverage report (which contracts,
  date ranges, gap/OI-quality summary from §8 layer 4).
- Idempotent re-ingest semantics: same data → same hash → no-op; changed
  data → explicit versioned overwrite recorded in the ingestion log. No
  silent merges of overlapping files.
- Overlap-window check: consecutive contracts should coexist for a few
  sessions with volume on both — this is the data the roll rule will need,
  so verify *now* that sources provide it.

### Ingestion Phase 4 (I4) — continuous futures construction (currently forbidden)

Only after I1–I3 are proven on real per-contract data, and only after the
"Do Not Do Yet" entry is consciously lifted: run the **existing, tested**
continuous builder (`compute_roll_schedule` + `build_continuous_futures`,
ratio/Panama per `data.default_adjustment`) on real raw data, write via the
existing `RawFuturesStore.write_continuous` path, and surface the
back-adjustment warnings in every consumer. No new stitching code should be
needed — I4 is wiring and verification, and its design details live with
that phase, not here.

### Ingestion Phase 5 (I5) — real vendor integration

Pick one vendor (§10 survey), one root, behind the same loader interface as
I2 (a vendor fetch is just another way to fill `incoming\`). Compare
against the local-CSV source via §8 layer 5 before trusting it. API keys via
environment variables, never committed; rate limits respected; every fetch
appended to the ingestion log.

## 10. Future data source options (survey only — nothing chosen, nothing implemented)

| Option | Per-contract? | Open interest? | Cost | Notes |
|---|---|---|---|---|
| Manual/broker CSV export | yes | often | free-ish | Lowest risk; exactly what I2–I3 are built for |
| yfinance (`ES=F`) | **no** (front-month proxy) | no | free | Proxy/sanity only (§2); never feeds roll logic |
| yfinance per-contract tickers | partial | unreliable | free | Sparse history for back contracts; treat as experiment |
| Nasdaq Data Link / similar aggregators | historically yes | varies | freemium | Coverage/licensing must be re-verified at I5 time |
| Databento | yes | yes | paid, per-GB | CME-licensed, clean per-contract dailies; strong I5 candidate |
| Portara / CSI / PitData (historical vendors) | yes | yes | paid, bulk | Deep history one-time purchase; ingest as local CSV (the I2 path!) |
| IBKR API | yes | limited (snapshot-oriented) | account + subscriptions | Realtime-oriented; historical daily backfill is clunky; **explicit non-goal for now** |

Selection criteria when the time comes: true per-contract series with volume
**and** OI on overlap days (the roll rule's input), documented
settlement-price convention, redistribution terms compatible with a research
repo, and boring file-based delivery beating clever APIs.

## 11. Non-goals (explicit)

Not in any phase of this document's scope until deliberately re-decided:

- **No yfinance implementation** — not even the proxy path; §2/§10 only
  define how it *would* be labeled.
- **No IBKR implementation** — surveyed in §10, that is all.
- **No continuous futures construction** — I4 is a placeholder with
  preconditions, and `futures_continuous` remains on the Do-Not-Do-Yet list
  (the code exists and is tested, §3; running it is what is forbidden).
- **No ML** — ingestion produces validated bars, nothing downstream.
- **No CFDs, no options** — futures-only, per the repo's hard constraints.
- **No production/live trading** — research and education only; nothing here
  connects to an order route, and nothing should.
- **No new dependencies and no downloads** were introduced by this plan.

## 12. Next tiny step

Ingestion Phase 1, commit 1: add the synthetic per-contract CSV fixtures +
the fixture-loader function + its pytest file. Small, offline, and it turns
this plan's §4–§6 rules into executable assertions.
