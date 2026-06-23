# Global Markets Globe — Data and optional adapters

The Global Markets Globe ships in **stages**. Today it is a static-data showcase
with optional, opt-in integrations for selected **macro** figures (FRED) and
**delayed primary index/FX quotes** (yfinance). Everything else is static
illustrative sample data, and there is **no live/real-time market data, live
news, scraping, or investment advice** anywhere.

## Default behaviour (no setup needed)

Out of the box, with no environment configuration:

- The Globe works fully on **static illustrative sample data** (15 markets).
- `GET /globe/markets` returns `data_status: "static_sample"`, every dossier's
  `source_status.macro` is `static_sample`, and no external call is made.
- The frontend loads the backend data layer, and if the backend is unreachable
  it falls back to the bundled static dataset with a visible warning.

You never need an API key for local development.

## Data sources & status

| Section | Source today | Status value | Future |
|---|---|---|---|
| Macro (GDP/inflation/unemployment/policy rate/debt-GDP) | static sample (optional FRED for US) | `static_sample` · `fred_live` · `fred_unavailable` | broader FRED coverage |
| Equity indices | static sample (optional delayed quote) | `static_sample` · `delayed_quote` · `quote_unavailable` | broader coverage |
| FX | static sample (optional delayed quote) | `static_sample` · `delayed_quote` · `quote_unavailable` | broader coverage |
| Headlines / sentiment | static sample (scaffold) | `static_sample` · `news_unavailable` | live news feed (planned) |

The markets-response `data_status` is `static_sample` normally, or one of
`mixed_static_and_fred`, `mixed_static_and_quotes`, or `mixed_static_fred_quotes`
when at least one market's macro (FRED) and/or index/FX (delayed quote) was
enriched.

## Enabling the optional FRED macro adapter (advanced, local only)

The adapter is **disabled by default**. To try FRED-sourced macro enrichment locally:

1. Get a free FRED API key: <https://fred.stlouisfed.org/docs/api/api_key.html>.
2. Copy `backend/.env.example` to `backend/.env` (which is **gitignored**) and set:
   ```
   GLOBE_FRED_ENABLED=true
   FRED_API_KEY=your_personal_key_here
   ```
   Optional: `FRED_BASE_URL`, `FRED_TIMEOUT_SECONDS` (default 5),
   `GLOBE_FRED_CACHE_TTL_SECONDS` (default 3600).
3. Start or restart the backend with that file explicitly loaded:
   ```powershell
   cd C:\quantlab\backend
   uvicorn app.main:app --reload --port 8000 --env-file .env
   ```

`FRED_BASE_URL` must be HTTPS. Unsafe values fall back to the official FRED
endpoint; timeout and cache settings are bounded to safe local defaults.

**Never commit a real key.** The key is read from the environment at runtime and
is **never** placed in any API response.

### What enrichment does (v1 coverage)

- **United States only.** v1 maps three FRED series whose latest observation is
  already a percentage rate: `policy_rate` → `FEDFUNDS`, `unemployment` →
  `UNRATE`, `gdp_growth` → `A191RL1Q225SBEA`. `inflation` and `debt_to_gdp`
  remain static sample (partial, honest coverage). Other markets stay static.
- When at least one mapped field succeeds, the US dossier's
  `source_status.macro` becomes `fred_live` and response
  `data_status` becomes `mixed_static_and_fred`. This internal status means
  “at least one field was FRED-sourced,” not that the whole macro block is live.
- `macro.is_sample` remains `true` in v1 because inflation and debt/GDP stay
  illustrative. `macro.fred_fields` identifies exactly which values came from
  FRED, `macro.fred_as_of` gives each observation date, and
  `macro.as_of_date` is the oldest date among those enriched fields.
- The dossier shows **"Macro: Partial FRED"** and marks only sourced metric cards.

### Fail-closed behaviour

The adapter never breaks the app:

- `GLOBE_FRED_ENABLED=true` but **no key** → macro stays static,
  the supported US dossier reports `source_status.macro = fred_unavailable`,
  and a warning is returned. Unsupported markets remain `static_sample`.
- FRED **network error / invalid value / missing data** → static fallback with a
  warning. A latest `.` observation is skipped while the adapter checks a small
  bounded window for the most recent valid observation.
- Partial series success retains static values for failed fields, records only
  successful fields as FRED-sourced, and returns a partial-data warning.
- A small in-memory TTL cache (default 1h) avoids refetching the same series.

## Enabling the optional delayed index / FX quote adapter (advanced, local only)

The quote adapter is **disabled by default** and requires **no API key**. When
enabled it enriches the **primary index** and **FX pair** of *supported* markets
with **delayed** (never real-time) quotes, reusing the project's existing free
**yfinance** dependency. To try it locally, in `backend/.env`:

```
GLOBE_QUOTES_ENABLED=true
# GLOBE_QUOTES_PROVIDER=yfinance   # default; any other value → static fallback
# GLOBE_QUOTES_TIMEOUT_SECONDS=5
# GLOBE_QUOTES_CACHE_TTL_SECONDS=900
```

### What enrichment does (v1 coverage)

- **Limited coverage.** Primary equity index for a curated set of markets
  (US, Canada, UK, Germany, France, Switzerland, Japan, Hong Kong, Taiwan,
  South Korea, India, Singapore, Australia, Brazil) and the primary FX pair for
  the non-USD-base markets. Unmapped markets/fields stay static and are never
  fetched or labelled as delayed quotes.
- On success, the market's `source_status.indices` / `source_status.fx` becomes
  `delayed_quote`, the enriched value's `is_sample` becomes `false`, and an
  `as_of_date` is attached. Only the **primary** index / FX row is enriched;
  secondary rows stay static.
- Response `data_status` becomes `mixed_static_and_quotes` (or
  `mixed_static_fred_quotes` if FRED is also live).

### Fail-closed behaviour

- Quotes disabled → no provider call; everything static.
- Enabled but provider unavailable (unknown provider, or yfinance import fails)
  → supported markets report `quote_unavailable` + a warning; data stays static.
- Provider error or invalid value/provenance (non-finite or nonpositive value,
  mismatched symbol, missing ISO date, or non-delayed result) → that field stays
  static and is marked `quote_unavailable`.
- A small in-memory TTL cache (default 15 min) avoids refetching the same symbol.
- Enabling quotes can slow the first `/globe/markets` response on a cold cache
  (several delayed-quote fetches); the frontend's graceful fallback may show the
  bundled static dataset if the backend is slow. This is expected and safe.

### Honesty

Quotes are **delayed**, never real-time. No live tick data, no streaming, no
websocket, no broker, no trading, no paid feed. Unsupported markets never claim a
delayed quote.

## News sentiment (scaffold only — no live news)

Phase 20.5 adds a **safe news-sentiment scaffold**, not live news. v1 **always**
serves the bundled **static sample headlines** in each dossier, each with a
`sentiment` of **Bullish / Bearish / Neutral** (illustrative, not a model
output). There is **no live news fetch, no scraping, no external news/LLM API,
and no API key** anywhere.

```
GLOBE_NEWS_ENABLED=false      # default; static sample headlines
# GLOBE_NEWS_PROVIDER=static  # default static provider; no real provider in v1
```

- Disabled (default) or `GLOBE_NEWS_PROVIDER=static` → `source_status.news =
  static_sample`, no warning.
- Enabled with any *other* provider → no real provider is wired in v1, so
  headlines stay static and `source_status.news = news_unavailable` with a
  non-blocking warning: *"Globe news adapter is not configured; using static
  sample headlines."* Still no external call; never crashes.
- News never changes `data_status` and never affects macro / index / FX status.
  The dossier shows a **"News: static sample"** (or "News unavailable — static
  fallback") chip and the copy *"Sample headlines — live news integration
  planned."* No "live/latest/breaking/current/real-time news" wording.

## Dossier permalinks & cross-module routing (Phase 20.6)

QuantLab is a single-page workspace switcher, so country dossiers are shareable
via **query-param permalinks** on the app page:

- Canonical: **`/?view=globe&market=<id>`** (e.g. `…&market=tw`).
- Convenience: **`/globe?market=<id>`** — a thin route that redirects to the
  canonical form. `/globe` (no market) opens the globe with no selection.

Behaviour:

- Opening a permalink selects the market and opens its dossier automatically,
  in **both** backend-available and bundled-static-fallback modes (selection is
  by id, independent of the data source).
- An **unknown market id** does not crash: the globe falls back to the default
  market (United States), shows *"Market not found; showing default market."*,
  and the address bar is normalised to the default.
- Clicking a marker / market row updates the URL (`?market=<id>`) without a page
  reload, and **browser back/forward** walks the visited dossiers.
- If a search/region filter hides the selected market, the dossier closes and
  `?market` is dropped (documented, stable behaviour).
- The dossier header has a **Share** button that copies the permalink
  (`navigator.clipboard`, with a manual-copy fallback message). It works in
  fallback mode too, since the URL doesn't depend on the backend.
- The Command Palette exposes **Open `<Country>` Market Dossier** for all 15
  markets (US/Taiwan/Japan/Germany/India searchable by abbreviation), plus
  **Open Global Markets Globe** / **Explore Global Markets**. The Dashboard globe
  card links straight to the US/Taiwan/Japan/Germany/India dossiers.
- Dossier **QuantLab Actions** (Backtest this index, Open Scanner, View FX Lab,
  View Rates Lab) route into the existing modules. Market-specific pre-filling of
  those modules is **future work** (the links open the module, not a prefilled
  state). No fake or broken routes are created.

This is navigation/UX only — no new data, no live data, no investment advice.

## Honesty guardrails

- Not real-time. Not a live market terminal. No complete global macro coverage.
- Index/FX fields are static by default and only supported primary rows may use
  optional delayed quotes. News remains static/planned. Nothing is real-time.
- No live trading, broker integration, paid providers, or scraping.
- Educational / research only — **not investment advice**.
