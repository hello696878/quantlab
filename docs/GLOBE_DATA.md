# Global Markets Globe — Data & the optional FRED macro adapter

The Global Markets Globe ships in **stages**. Today it is a static-data showcase
with an *optional, opt-in* first real-data integration for **macro** figures
(FRED). Everything else — index levels, FX quotes, market structure, headlines —
is static illustrative sample data, and there is **no live/real-time market
data, no news, no scraping, and no investment advice** anywhere.

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
| Equity indices | static sample | `static_sample` | delayed quotes (planned) |
| FX | static sample | `static_sample` | delayed quotes (planned) |
| Headlines / sentiment | static sample | `static_sample` | news feed (planned) |

The markets-response `data_status` is `static_sample` normally, or
`mixed_static_and_fred` when at least one market's macro was enriched from FRED.

## Enabling the optional FRED macro adapter (advanced, local only)

The adapter is **disabled by default**. To try live macro enrichment locally:

1. Get a free FRED API key: <https://fred.stlouisfed.org/docs/api/api_key.html>.
2. Copy `backend/.env.example` to `backend/.env` (which is **gitignored**) and set:
   ```
   GLOBE_FRED_ENABLED=true
   FRED_API_KEY=your_personal_key_here
   ```
   Optional: `FRED_BASE_URL`, `FRED_TIMEOUT_SECONDS` (default 5),
   `GLOBE_FRED_CACHE_TTL_SECONDS` (default 3600).
3. Restart the backend.

**Never commit a real key.** The key is read from the environment at runtime and
is **never** placed in any API response.

### What enrichment does (v1 coverage)

- **United States only.** v1 maps three FRED series whose latest observation is
  already a percentage rate: `policy_rate` → `FEDFUNDS`, `unemployment` →
  `UNRATE`, `gdp_growth` → `A191RL1Q225SBEA`. `inflation` and `debt_to_gdp`
  remain static sample (partial, honest coverage). Other markets stay static.
- When enrichment succeeds, the US dossier's `source_status.macro` becomes
  `fred_live`, `macro.is_sample` becomes `false`, and `macro.as_of_date` is set.
  The dossier macro chip shows **"Macro: FRED"**; everything else stays static.

### Fail-closed behaviour

The adapter never breaks the app:

- `GLOBE_FRED_ENABLED=true` but **no key** → macro stays static,
  `source_status.macro = fred_unavailable`, and a warning is returned:
  *"FRED macro adapter enabled but no API key configured; using static sample data."*
- FRED **network error / invalid value (`.`) / missing data** → macro stays
  static, `source_status.macro = fred_unavailable`, warning included.
- A small in-memory TTL cache (default 1h) avoids refetching the same series.

## Honesty guardrails

- Not real-time. Not a live market terminal. No complete global macro coverage.
- Index prices, FX, and news are static/planned — not live.
- No live trading, broker integration, paid providers, or scraping.
- Educational / research only — **not investment advice**.
