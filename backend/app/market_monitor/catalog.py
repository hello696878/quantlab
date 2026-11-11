from .models import Instrument

TREASURY_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FEEDS = {
    "fed": ("Federal Reserve", "official", "https://www.federalreserve.gov/feeds/press_monetary.xml", {"federalreserve.gov", "www.federalreserve.gov"}),
    "ecb": ("European Central Bank", "official", "https://www.ecb.europa.eu/rss/press.html", {"ecb.europa.eu", "www.ecb.europa.eu"}),
    "bbc": ("BBC World", "news", "https://feeds.bbci.co.uk/news/world/rss.xml", {"bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"}),
}
COMPANIES = {"nvda": ("NVDA", "0001045810"), "msft": ("MSFT", "0000789019"), "aapl": ("AAPL", "0000320193")}


def market(id, name, kind, region, unit, symbol, currency):
    return Instrument(id=id, name=name, kind=kind, region=region, unit=unit, currency=currency,
                      source="yahoo", symbol=symbol, source_url=f"https://finance.yahoo.com/quote/{symbol.replace('^', '%5E').replace('=', '%3D')}/",
                      note="Latest available adjusted daily close via yfinance; session completion and delay are not established. Not a total-return series.")


CATALOG = [
    market("sp500", "S&P 500", "index", "US", "index points", "^GSPC", "USD"),
    market("nasdaq100", "Nasdaq-100", "index", "US", "index points", "^NDX", "USD"),
    market("taiwan", "Taiwan Weighted Index", "index", "TW", "index points", "^TWII", "TWD"),
    market("nikkei225", "Nikkei 225", "index", "JP", "index points", "^N225", "JPY"),
    market("gold_reference", "Gold futures reference", "futures_reference", "US", "USD/troy ounce", "GC=F", "USD"),
    market("wti_reference", "WTI futures reference", "futures_reference", "US", "USD/barrel", "CL=F", "USD"),
    market("brent_reference", "Brent futures reference", "futures_reference", "global", "USD/barrel", "BZ=F", "USD"),
    *[market(id, name, "company", "US", "USD/share", symbol, "USD") for id, name, symbol in (
        ("nvda", "NVIDIA", "NVDA"), ("msft", "Microsoft", "MSFT"), ("aapl", "Apple", "AAPL"))],
    *[Instrument(id=id, name=name, kind="rates", region="US", unit=unit, currency=None, source="treasury",
                 symbol=symbol, source_url=TREASURY_URL, note="Daily Treasury par yield, not the Fed policy rate. Spread uses the same observation date.")
      for id, name, symbol, unit in (("treasury2y", "Treasury 2Y", "BC_2YEAR", "%"), ("treasury10y", "Treasury 10Y", "BC_10YEAR", "%"),
                                      ("treasury30y", "Treasury 30Y", "BC_30YEAR", "%"), ("treasury10y2y", "Treasury 10Y - 2Y", "10Y-2Y", "bps"))],
    *[Instrument(id=id, name=name, kind="spot", region=region, unit="USD/barrel", currency="USD", source="eia", symbol=symbol,
                 source_url=f"https://www.eia.gov/dnav/pet/hist/{symbol}d.htm", note="EIA daily spot observation, separate from Yahoo futures references.")
      for id, name, symbol, region in (("eia_wti", "EIA Cushing WTI spot FOB", "RWTC", "US"), ("eia_brent", "EIA Europe Brent spot FOB", "RBRTE", "Europe"))],
]
BY_ID = {instrument.id: instrument for instrument in CATALOG}
DEFAULT_IDS = ["sp500", "nasdaq100", "taiwan", "wti_reference", "nvda"]
