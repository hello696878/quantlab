import asyncio
from datetime import date, timedelta
import json
from pathlib import Path
import subprocess
import sys

import httpx

from .catalog import BY_ID, COMPANIES, FEEDS, FOMC_URL
from .parsers import MAX_BYTES, parse_eia, parse_feed, parse_fomc, parse_market, parse_sec, parse_treasury

HTTP_TOTAL_SECONDS = 15
EIA_TOTAL_SECONDS = 15


class Providers:
    def __init__(self, eia_key=None, sec_user_agent=None):
        self.eia_key = eia_key
        self.sec_user_agent = sec_user_agent
        self._sec_lock = asyncio.Lock()

    async def get(self, url, params=None, headers=None):
        # URLs are internal constants. No user URL, redirect or provider symbol input.
        async with asyncio.timeout(HTTP_TOTAL_SECONDS):
            async with httpx.AsyncClient(timeout=httpx.Timeout(12), follow_redirects=False) as client:
                async with client.stream("GET", url, params=params, headers=headers) as response:
                    response.raise_for_status()
                    if response.status_code != 200:
                        raise ValueError("Unexpected source status")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise ValueError("Source response exceeds limit")
                    return bytes(data)

    async def market(self, id):
        # A process bounds total yfinance work and isolates its mutable caches.
        def run():
            result = subprocess.run([sys.executable, "-m", "app.market_monitor.market_worker", id],
                                    cwd=Path(__file__).resolve().parents[2], capture_output=True, timeout=25)
            if result.returncode or len(result.stdout) > 32_768:
                raise ValueError("Daily provider unavailable")
            return parse_market(json.loads(result.stdout), id)
        return await asyncio.to_thread(run)

    async def treasury(self, today):
        first = today.replace(day=1)
        months = [first - timedelta(days=1), first]
        payloads = [await self.get("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml",
                                   {"data": "daily_treasury_yield_curve", "field_tdr_date_value_month": month.strftime("%Y%m")}) for month in months]
        return parse_treasury(payloads)

    async def feed(self, id):
        _, _, url, hosts = FEEDS[id]
        return parse_feed(await self.get(url), id, hosts)

    async def eia(self):
        if not self.eia_key:
            raise ValueError("EIA is not configured")
        # The blocking, key-bearing request is isolated in a disposable process.
        # subprocess.run kills and waits on timeout; cancelling a thread alone
        # would leave the underlying provider work running. The key uses stdin.
        def fetch():
            result = subprocess.run([sys.executable, "-m", "app.market_monitor.eia_worker"],
                                    cwd=Path(__file__).resolve().parents[2], capture_output=True,
                                    input=json.dumps({"api_key": self.eia_key}).encode("utf-8"),
                                    timeout=EIA_TOTAL_SECONDS)
            if result.returncode or len(result.stdout) > MAX_BYTES:
                raise ValueError("EIA provider unavailable")
            return result.stdout
        return parse_eia(json.loads(await asyncio.to_thread(fetch)))

    async def sec(self, company):
        if not self.sec_user_agent:
            raise ValueError("SEC is not configured")
        async with self._sec_lock:
            # At most one SEC request per second per local process, plus 15m cache.
            try:
                raw = await self.get(f"https://data.sec.gov/submissions/CIK{COMPANIES[company][1]}.json",
                                     headers={"User-Agent": self.sec_user_agent, "Accept-Encoding": "gzip, deflate"})
                return parse_sec(json.loads(raw), company)
            finally:
                await asyncio.sleep(1)

    async def calendar(self, today):
        return parse_fomc(await self.get(FOMC_URL), today)
