"""
Static illustrative sample dataset for the Global Markets Globe (Phase 20.2).

Mirrors the 15 bundled frontend markets. **All values are static, deterministic,
illustrative placeholders** — not live, not real-time, not a market data feed.
Index levels / FX rates / macro figures are samples (every record carries
`is_sample=True` and `source_status` is `static_sample`). A future phase can
swap individual sources to live via the adapters in `adapters.py`.
"""

from __future__ import annotations

from typing import List

from app.globe.models import (
    MarketDossier,
    MarketFx,
    MarketHeadline,
    MarketIndex,
    MarketLink,
    MarketMacro,
    MarketRates,
    MarketStructure,
    SourceStatus,
)

STATIC_DATA_NOTICE = (
    "Static illustrative data is the default. Optional FRED macro and delayed "
    "index/FX quote adapters may enrich supported fields when configured; news "
    "integration is planned."
)

# Shared cross-links (open the related QuantLab module). The frontend routes
# these through its in-app view router; the hrefs here are descriptive metadata.
_LINKS = [
    {"label": "Backtest this index", "href": "/studio"},
    {"label": "Open Scanner", "href": "/scanner"},
    {"label": "View FX Lab", "href": "/fx"},
    {"label": "View Rates Lab", "href": "/rates"},
]


def _sparkline(seed: int, base: float, n: int = 16) -> List[float]:
    """Deterministic illustrative price-shaped series around ``base``."""
    s = seed & 0xFFFFFFFF
    out: List[float] = []
    v = base
    for _ in range(n):
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        step = ((s / 0x7FFFFFFF) - 0.5) * 0.02
        v = v * (1.0 + step)
        out.append(round(v, 2))
    return out


# Each spec: concise per-market data; sparklines are generated deterministically.
_SPECS = [
    {
        "id": "us", "country": "United States", "region": "Americas",
        "subregion": "North America", "flag": "🇺🇸", "lat": 38.0, "lon": -97.0,
        "currency": "USD", "exchange": "NYSE / Nasdaq",
        "trading_hours": "09:30–16:00 ET", "timezone": "America/New_York",
        "indices": [("S&P 500", "SPX", 5200.0, 0.42), ("Nasdaq 100", "NDX", 18200.0, 0.68), ("Dow Jones", "DJIA", 39000.0, 0.21)],
        "macro": (2.1, 3.2, 3.9, 5.25, 122.0),
        "fx": [("DXY (USD index)", 104.0, -0.12)],
        "structure": ("Very large (sample)", "~5,000 (sample)", "T+1", "Deep, highly liquid equity market; mega-cap technology drives index concentration."),
        "headlines": [("Mega-cap technology leads the benchmark higher", "Bullish"), ("Rate-path uncertainty weighs on small caps", "Bearish"), ("Earnings season opens with mixed guidance", "Neutral")],
    },
    {
        "id": "ca", "country": "Canada", "region": "Americas",
        "subregion": "North America", "flag": "🇨🇦", "lat": 56.0, "lon": -106.0,
        "currency": "CAD", "exchange": "Toronto Stock Exchange (TSX)",
        "trading_hours": "09:30–16:00 ET", "timezone": "America/Toronto",
        "indices": [("S&P/TSX Composite", "TSX", 22000.0, 0.15)],
        "macro": (1.4, 3.1, 5.7, 5.0, 107.0),
        "fx": [("USD/CAD", 1.36, 0.09)],
        "structure": ("Large (sample)", "~3,400 (sample)", "T+1", "Index tilted toward financials and energy / natural resources."),
        "headlines": [("Energy names support the resource-heavy index", "Bullish"), ("Housing-sensitive financials trade cautiously", "Neutral"), ("Loonie softens as rate-cut bets build", "Bearish")],
    },
    {
        "id": "uk", "country": "United Kingdom", "region": "Europe",
        "subregion": "Western Europe", "flag": "🇬🇧", "lat": 54.0, "lon": -2.0,
        "currency": "GBP", "exchange": "London Stock Exchange (LSE)",
        "trading_hours": "08:00–16:30 GMT", "timezone": "Europe/London",
        "indices": [("FTSE 100", "UKX", 8100.0, 0.11), ("FTSE 250", "MCX", 20500.0, -0.08)],
        "macro": (0.6, 4.0, 4.2, 5.25, 101.0),
        "fx": [("GBP/USD", 1.27, 0.17)],
        "structure": ("Large (sample)", "~1,900 (sample)", "T+2", "Large-cap index is internationally exposed; heavy weight in energy, miners, and banks."),
        "headlines": [("Sterling strength caps overseas-earner gains", "Neutral"), ("Defensive dividend payers attract flows", "Bullish"), ("Domestic mid-caps lag on growth worries", "Bearish")],
    },
    {
        "id": "de", "country": "Germany", "region": "Europe",
        "subregion": "Western Europe", "flag": "🇩🇪", "lat": 51.0, "lon": 10.0,
        "currency": "EUR", "exchange": "Deutsche Börse (Xetra)",
        "trading_hours": "09:00–17:30 CET", "timezone": "Europe/Berlin",
        "indices": [("DAX 40", "DAX", 18300.0, 0.34)],
        "macro": (0.2, 2.9, 5.9, 4.0, 64.0),
        "fx": [("EUR/USD", 1.08, 0.06)],
        "structure": ("Large (sample)", "~450 (sample)", "T+2", "Export- and industrials-heavy benchmark; sensitive to global manufacturing cycles."),
        "headlines": [("Industrials rebound on improving order books", "Bullish"), ("Auto sector watches China demand closely", "Neutral"), ("Manufacturing PMI stays in contraction", "Bearish")],
    },
    {
        "id": "fr", "country": "France", "region": "Europe",
        "subregion": "Western Europe", "flag": "🇫🇷", "lat": 46.0, "lon": 2.0,
        "currency": "EUR", "exchange": "Euronext Paris",
        "trading_hours": "09:00–17:30 CET", "timezone": "Europe/Paris",
        "indices": [("CAC 40", "CAC", 8000.0, 0.19)],
        "macro": (0.8, 3.0, 7.3, 4.0, 111.0),
        "fx": [("EUR/USD", 1.08, 0.06)],
        "structure": ("Large (sample)", "~470 (sample)", "T+2", "Strong luxury-goods and consumer weighting alongside industrials and energy."),
        "headlines": [("Luxury leaders pace the index", "Bullish"), ("Investors weigh fiscal-deficit headlines", "Neutral"), ("Consumer demand signals soften", "Bearish")],
    },
    {
        "id": "ch", "country": "Switzerland", "region": "Europe",
        "subregion": "Western Europe", "flag": "🇨🇭", "lat": 47.0, "lon": 8.0,
        "currency": "CHF", "exchange": "SIX Swiss Exchange",
        "trading_hours": "09:00–17:30 CET", "timezone": "Europe/Zurich",
        "indices": [("SMI", "SMI", 11800.0, 0.07)],
        "macro": (1.0, 1.4, 2.1, 1.75, 38.0),
        "fx": [("USD/CHF", 0.88, -0.11)],
        "structure": ("Large (sample)", "~250 (sample)", "T+2", "Defensive, low-volatility index dominated by pharma and consumer staples."),
        "headlines": [("Defensive heavyweights underpin the index", "Bullish"), ("Strong franc pressures exporters", "Bearish"), ("Low domestic inflation supports policy patience", "Neutral")],
    },
    {
        "id": "jp", "country": "Japan", "region": "Asia-Pacific",
        "subregion": "East Asia", "flag": "🇯🇵", "lat": 36.0, "lon": 138.0,
        "currency": "JPY", "exchange": "Tokyo Stock Exchange (TSE)",
        "trading_hours": "09:00–15:00 JST", "timezone": "Asia/Tokyo",
        "indices": [("Nikkei 225", "NKY", 39500.0, 0.81), ("TOPIX", "TPX", 2750.0, 0.63)],
        "macro": (1.3, 2.8, 2.5, -0.1, 255.0),
        "fx": [("USD/JPY", 150.0, 0.24)],
        "structure": ("Very large (sample)", "~3,900 (sample)", "T+2", "Corporate-governance reform and a weak yen are recurring index themes."),
        "headlines": [("Governance-reform optimism lifts exporters", "Bullish"), ("Weak yen flatters overseas earnings", "Neutral"), ("Markets watch for a policy-rate exit", "Bearish")],
    },
    {
        "id": "cn", "country": "China", "region": "Asia-Pacific",
        "subregion": "East Asia", "flag": "🇨🇳", "lat": 35.0, "lon": 104.0,
        "currency": "CNY", "exchange": "Shanghai / Shenzhen",
        "trading_hours": "09:30–15:00 CST", "timezone": "Asia/Shanghai",
        "indices": [("CSI 300", "CSI300", 3550.0, -0.27), ("SSE Composite", "SHCOMP", 3050.0, -0.14)],
        "macro": (4.8, 0.4, 5.1, 3.45, 84.0),
        "fx": [("USD/CNY", 7.20, 0.08)],
        "structure": ("Very large (sample)", "~5,300 (sample)", "T+1", "Onshore A-shares with notable retail participation and daily price limits."),
        "headlines": [("Property-sector concerns linger", "Bearish"), ("Stimulus speculation supports sentiment", "Bullish"), ("Low inflation keeps policy easing in view", "Neutral")],
    },
    {
        "id": "hk", "country": "Hong Kong", "region": "Asia-Pacific",
        "subregion": "East Asia", "flag": "🇭🇰", "lat": 22.3, "lon": 114.2,
        "currency": "HKD", "exchange": "HKEX",
        "trading_hours": "09:30–16:00 HKT", "timezone": "Asia/Hong_Kong",
        "indices": [("Hang Seng", "HSI", 17500.0, -0.19)],
        "macro": (3.2, 1.9, 2.9, 5.75, 4.0),
        "fx": [("USD/HKD", 7.80, 0.01)],
        "structure": ("Large (sample)", "~2,600 (sample)", "T+2", "Gateway for mainland listings; HKD operates under a USD currency peg band."),
        "headlines": [("Southbound flows steady the index", "Neutral"), ("Mainland tech listings rebound", "Bullish"), ("High USD-linked rates pressure valuations", "Bearish")],
    },
    {
        "id": "tw", "country": "Taiwan", "region": "Asia-Pacific",
        "subregion": "East Asia", "flag": "🇹🇼", "lat": 23.7, "lon": 121.0,
        "currency": "TWD", "exchange": "Taiwan Stock Exchange (TWSE)",
        "trading_hours": "09:00–13:30 CST", "timezone": "Asia/Taipei",
        "indices": [("TAIEX", "TWII", 22000.0, 0.72)],
        "macro": (3.1, 2.2, 3.4, 2.0, 28.0),
        "fx": [("USD/TWD", 32.0, 0.12)],
        "structure": ("Large (sample)", "~1,000 (sample)", "T+2", "Index dominated by semiconductors; highly geared to the global tech cycle."),
        "headlines": [("Semiconductor demand drives the benchmark", "Bullish"), ("AI supply-chain orders stay firm", "Bullish"), ("Index concentration raises single-name risk", "Neutral")],
    },
    {
        "id": "kr", "country": "South Korea", "region": "Asia-Pacific",
        "subregion": "East Asia", "flag": "🇰🇷", "lat": 36.5, "lon": 127.8,
        "currency": "KRW", "exchange": "Korea Exchange (KRX)",
        "trading_hours": "09:00–15:30 KST", "timezone": "Asia/Seoul",
        "indices": [("KOSPI", "KOSPI", 2650.0, 0.41)],
        "macro": (2.2, 2.6, 2.8, 3.5, 55.0),
        "fx": [("USD/KRW", 1330.0, 0.15)],
        "structure": ("Large (sample)", "~2,500 (sample)", "T+2", "Export- and memory-chip-sensitive market; large single-name index weights."),
        "headlines": [("Memory-chip upcycle hopes lift sentiment", "Bullish"), ("Won weakness draws policy attention", "Neutral"), ("Exporters eye softer global demand", "Bearish")],
    },
    {
        "id": "in", "country": "India", "region": "Asia-Pacific",
        "subregion": "South Asia", "flag": "🇮🇳", "lat": 22.0, "lon": 79.0,
        "currency": "INR", "exchange": "NSE / BSE",
        "trading_hours": "09:15–15:30 IST", "timezone": "Asia/Kolkata",
        "indices": [("NIFTY 50", "NIFTY", 22500.0, 0.55), ("SENSEX", "SENSEX", 74000.0, 0.49)],
        "macro": (6.5, 5.1, 7.8, 6.5, 82.0),
        "fx": [("USD/INR", 83.0, 0.07)],
        "structure": ("Large (sample)", "~5,400 (sample)", "T+1", "Fast-growing market with strong domestic retail (SIP) inflows."),
        "headlines": [("Domestic inflows underpin the rally", "Bullish"), ("Valuations screen rich versus peers", "Neutral"), ("Sticky food inflation tempers rate-cut hopes", "Bearish")],
    },
    {
        "id": "sg", "country": "Singapore", "region": "Asia-Pacific",
        "subregion": "Southeast Asia", "flag": "🇸🇬", "lat": 1.35, "lon": 103.8,
        "currency": "SGD", "exchange": "Singapore Exchange (SGX)",
        "trading_hours": "09:00–17:00 SGT", "timezone": "Asia/Singapore",
        "indices": [("Straits Times", "STI", 3300.0, 0.13)],
        "macro": (1.8, 3.4, 2.0, 3.8, 168.0),
        "fx": [("USD/SGD", 1.35, -0.04)],
        "structure": ("Mid (sample)", "~640 (sample)", "T+2", "Regional financial hub; index is bank- and REIT-heavy. Policy runs via the exchange-rate band, not a policy rate."),
        "headlines": [("Bank dividends anchor the index", "Bullish"), ("REITs steady as rate expectations ease", "Neutral"), ("Trade-exposed names track global demand", "Bearish")],
    },
    {
        "id": "au", "country": "Australia", "region": "Asia-Pacific",
        "subregion": "Oceania", "flag": "🇦🇺", "lat": -25.0, "lon": 133.0,
        "currency": "AUD", "exchange": "Australian Securities Exchange (ASX)",
        "trading_hours": "10:00–16:00 AEST", "timezone": "Australia/Sydney",
        "indices": [("S&P/ASX 200", "AS51", 7800.0, 0.23)],
        "macro": (1.5, 3.6, 4.1, 4.35, 50.0),
        "fx": [("AUD/USD", 0.66, 0.14)],
        "structure": ("Large (sample)", "~2,000 (sample)", "T+2", "Index dominated by banks and miners; sensitive to commodity prices and China demand."),
        "headlines": [("Miners track firmer commodity prices", "Bullish"), ("Banks steady amid stable margins", "Neutral"), ("Sticky services inflation delays cuts", "Bearish")],
    },
    {
        "id": "br", "country": "Brazil", "region": "Americas",
        "subregion": "South America", "flag": "🇧🇷", "lat": -10.0, "lon": -55.0,
        "currency": "BRL", "exchange": "B3 (Brasil Bolsa Balcão)",
        "trading_hours": "10:00–17:00 BRT", "timezone": "America/Sao_Paulo",
        "indices": [("Ibovespa", "IBOV", 128000.0, 0.36)],
        "macro": (2.9, 4.5, 7.5, 10.5, 74.0),
        "fx": [("USD/BRL", 5.10, -0.21)],
        "structure": ("Mid (sample)", "~430 (sample)", "T+2", "Commodity- and financials-heavy index; high real policy rates are a recurring theme."),
        "headlines": [("Commodity exporters lead gains", "Bullish"), ("Falling policy rate aids domestic names", "Bullish"), ("Fiscal-trajectory questions cap upside", "Bearish")],
    },
]


def _build(spec: dict, seed: int) -> MarketDossier:
    gdp, inflation, unemployment, policy_rate, debt = spec["macro"]
    cap, listed, settlement, notes = spec["structure"]
    indices = [
        MarketIndex(
            name=n, ticker=t, level=lvl, change_pct=chg,
            sparkline=_sparkline(seed + i * 7, lvl),
        )
        for i, (n, t, lvl, chg) in enumerate(spec["indices"])
    ]
    return MarketDossier(
        id=spec["id"],
        country=spec["country"],
        region=spec["region"],
        subregion=spec["subregion"],
        flag=spec["flag"],
        lat=spec["lat"],
        lon=spec["lon"],
        currency=spec["currency"],
        exchange=spec["exchange"],
        trading_hours=spec["trading_hours"],
        timezone=spec["timezone"],
        static_data_notice=STATIC_DATA_NOTICE,
        indices=indices,
        macro=MarketMacro(
            gdp_growth=gdp, inflation=inflation, unemployment=unemployment,
            policy_rate=policy_rate, debt_to_gdp=debt,
        ),
        fx=[MarketFx(pair=p, rate=r, change_pct=c) for (p, r, c) in spec["fx"]],
        rates=MarketRates(policy_rate=policy_rate, ten_year_yield=None),
        market_structure=MarketStructure(
            market_cap=cap, listed_companies=listed, settlement=settlement, notes=notes,
        ),
        headlines=[MarketHeadline(title=t, sentiment=s) for (t, s) in spec["headlines"]],
        links=[MarketLink(**lk) for lk in _LINKS],
        source_status=SourceStatus(),
    )


SAMPLE_MARKETS: List[MarketDossier] = [
    _build(spec, seed=1000 + idx * 101) for idx, spec in enumerate(_SPECS)
]
